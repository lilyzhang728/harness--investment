"""调用 DeepSeek 生成当天的 Markdown 学习材料。

硬约束：只能使用传入的数据；缺失的指标一律写“未获取”，不允许编造。
"""
from __future__ import annotations

import json
import re

import requests

from config import DS_KEY, DS_MODEL, DS_URL

SYSTEM = """你是一位有 15 年经验的投资顾问，正在给一位"只能在支付宝买场外基金"的投资新手写每日学习材料。

【绝对红线】
1. 只能使用我提供的数据。任何数字（点位、涨跌幅、金价、汇率、利率）都必须来自我给的 JSON 或新闻原文。
2. 我没有提供的数据，一律写"未获取"，绝不允许估算、补全或用记忆里的旧数据。
3. 新闻只能引用我给的快讯原文，不得添加我未提供的事件、政策、机构观点。
4. 不预测具体点位，不承诺收益，不做"必涨/必跌"判断。

【写作要求】
- 读者是新手：每个专业术语出现时必须紧跟一句大白话解释。
- 关注范围固定为：纳斯达克、标普500、美股科技/AI、红利低波100、黄金。
- 语气像老师，具体、克制、有取舍，不说套话。
- 中文，简体。"""

STRUCTURE = """请严格按下面的结构输出 Markdown（不要用代码块包裹，直接从一级标题开始）：

# 每日投资学习材料 · 第 {episode} 期

**{date_cn}（{weekday}）｜主题：<一句话点出今天最值得学的东西>**

> 你的关注清单：纳指 · 标普500 · 美股科技/AI · 红利低波100 · 黄金 ｜ 渠道：支付宝场外基金
> 阅读时间约 15 分钟

## 一、今天只看这一张图

![{date} 市场快照](images/{date}_market.png)

**三句话总结今天：**
1. …
2. …
3. …

> **一句话记住今天**：…

## 二、今日价格表

（用 Markdown 表格复述我给的行情，分三张：美股 / 贵金属与商品 / A股与红利低波100。只写我给了的字段；没有的写"—"）

## 三、今天必须搞懂的一个概念

（挑一个由今天行情自然引出的概念，讲清楚原理 + 传导链条 + 一句"直白解释"。200~400 字）

## 四、术语小词典

（表格：术语 | 大白话解释 | 今天为什么重要。选 6~10 个今天材料里真正用到的词）

## 五、新闻与政策解读

（挑 3~5 条我给的快讯，每条：一句事实 + 一条"教学点"。没有相关新闻就写"今日快讯中未出现与你关注范围直接相关的内容"）

## 六、市场情绪读数

（表格：指标 | 读数 | 怎么读。只用我给的 VIX／涨跌幅／新闻里的情绪信号，没有就少写几行）

## 七、K 线与趋势结构

（用我给的现价、周涨跌、回撤描述趋势位置；强调"均线是事后确认工具"这类认知）

## 八、场外基金实操课

（结合今天的行情，讲一个场外基金的具体操作知识点：限购/净值滞后/汇率/A·C 类/溢价/定投节奏，任选其一讲透）

## 九、投资建议（教学示例，非个性化建议）

（先给"你必须自己回答的三个问题"，再给一个分层参考框架表，最后列"这周不要做的事"清单。必须声明这是教学示例）

## 十、今日作业

（2~3 条可执行的小任务）

## 十一、明日预告

（一句话，下一期讲什么）

## 数据来源

（列出我给你的数据源名称即可，不要编造链接）

> **免责声明**：本文为投资知识学习材料，不构成任何投资建议。市场有风险，决策请独立判断。
"""


def _fmt(v, suffix="", nd=2):
    if v is None:
        return "—"
    try:
        return f"{v:,.{nd}f}{suffix}"
    except (TypeError, ValueError):
        return str(v)


def _market_table(snap):
    lines = []
    lines.append("### 美股（最近一个交易日收盘）")
    lines.append("| 指数 | 收盘 | 单日 | 本周 | 距52周高点 |")
    lines.append("|---|---|---|---|---|")
    for r in snap.get("us", []):
        lines.append(f"| {r['name']} | {_fmt(r['close'])} | "
                     f"{_fmt(r.get('pct'), '%')} | {_fmt(r.get('week'), '%')} | "
                     f"{_fmt(r.get('dd'), '%')} |")
    if snap.get("futures"):
        lines.append("")
        lines.append("### 贵金属与商品")
        lines.append("| 品种 | 最新 | 单日 | 本周 | 距高点 |")
        lines.append("|---|---|---|---|---|")
        for r in snap["futures"]:
            lines.append(f"| {r['name']} | {_fmt(r['close'])} | "
                         f"{_fmt(r.get('pct'), '%')} | {_fmt(r.get('week'), '%')} | "
                         f"{_fmt(r.get('dd'), '%')} |")
    if snap.get("cn"):
        lines.append("")
        lines.append("### A 股")
        lines.append("| 指数 | 收盘 | 单日 | 本周 |")
        lines.append("|---|---|---|---|")
        for r in snap["cn"]:
            lines.append(f"| {r['name']} | {_fmt(r['close'])} | "
                         f"{_fmt(r.get('pct'), '%')} | {_fmt(r.get('week'), '%')} |")
    d = snap.get("dividend100")
    if d:
        lines.append("")
        lines.append("### 红利低波100（930955）")
        lines.append(f"- 收盘：{_fmt(d['close'])}")
        lines.append(f"- 单日：{_fmt(d.get('pct'), '%')}")
        lines.append(f"- 本周：{_fmt(d.get('week'), '%')}")
        lines.append(f"- 距高点：{_fmt(d.get('dd'), '%')}")
    opt = snap.get("optional") or {}
    if opt:
        lines.append("")
        lines.append("### 其他")
        for k, v in opt.items():
            lines.append(f"- {v['name']}：{_fmt(v.get('close'), nd=3)}"
                         f"（单日 {_fmt(v.get('pct'), '%')}）")
    return "\n".join(lines)


def build_messages(snap, episode, prev_title=""):
    news = snap.get("news") or []
    news_txt = "\n".join(f"- [{n['time']}] {n['text']}" for n in news) or "（今日未抓到相关快讯）"

    facts = {
        "日期": snap["date"],
        "星期": snap["weekday"],
        "是否周末": snap["is_weekend"],
        "抓取时间": snap["generated_at"],
        "历史积累天数": snap.get("history_days", {}),
    }

    weekend_hint = ""
    if snap.get("is_weekend"):
        weekend_hint = (
            "\n【今天是周末，市场休市】请把主题改成「本周复盘 + 一个专题知识点」："
            "价格表用最近一个交易日（也就是 JSON 里的收盘数据）写，"
            "正文重点放在本周发生了什么、以及一个可以从本周行情里长出来的知识点。\n"
        )

    user = f"""今天是 {snap['date']}（{snap['weekday']}）。
{weekend_hint}

【结构化行情数据（唯一可用数字来源）】
{_market_table(snap)}

原始 JSON（供你核对，不要直接贴进正文）：
```json
{json.dumps(facts, ensure_ascii=False)}
```

【今日快讯（新浪财经 7×24，原文，未核实）】
{news_txt}

{('【上一期主题】' + prev_title) if prev_title else ''}

【结构要求】
{STRUCTURE.format(episode=episode, date_cn=snap['date'], weekday=snap['weekday'],
                  date=snap['date'])}
"""

    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]


def call_deepseek(messages, temperature=0.6, max_tokens=6000):
    if not DS_KEY:
        raise RuntimeError("缺少 DEEPSEEK_API_KEY")
    r = requests.post(
        DS_URL,
        headers={"Authorization": f"Bearer {DS_KEY}", "Content-Type": "application/json"},
        json={
            "model": DS_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        },
        timeout=180,
    )
    r.raise_for_status()
    data = r.json()
    content = data["choices"][0]["message"]["content"]
    return _clean(content)


def _clean(text):
    text = text.strip()
    text = re.sub(r"^```(?:markdown|md)?\s*\n", "", text)
    text = re.sub(r"\n```\s*$", "", text)
    return text.strip() + "\n"


def generate(snap, episode, prev_title, out_path):
    md = call_deepseek(build_messages(snap, episode, prev_title))
    if not md.lstrip().startswith("#"):
        raise RuntimeError("模型输出不是 Markdown 标题开头，丢弃")
    out_path.write_text(md, encoding="utf-8")
    return md


def stub(snap, episode, out_path):
    """离线兜底：不调用模型，用数据拼一份最小可用材料（用于测试链路）。"""
    table = _market_table(snap)
    news = "\n".join(f"- [{n['time']}] {n['text']}" for n in (snap.get("news") or [])[:8])
    md = f"""# 每日投资学习材料 · 第 {episode} 期

**{snap['date']}（{snap['weekday']}）｜主题：离线草稿（未调用模型）**

> 这是一份由程序直接生成的占位稿，用于验证排版与投递链路。正式版请配置 DEEPSEEK_API_KEY。

## 一、今日价格表

{table}

## 二、今日快讯

{news or '（未抓到）'}

## 三、投资建议

本节为占位内容，不构成投资建议。

> **免责声明**：本文为投资知识学习材料，不构成任何投资建议。
"""
    out_path.write_text(md, encoding="utf-8")
    return md
