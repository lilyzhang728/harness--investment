# 每日投资学习材料 · 自动流水线

每天早上 08:30（北京时间）自动生成一份**投资学习材料**，转成适配墨水屏的 EPUB，
推送到坚果云，用汉王 Clear7 锦鲤的「网盘」直接打开阅读。

关注范围：纳斯达克 · 标普 500 · 美股科技 / AI · 红利低波 100 · 黄金
投资渠道：支付宝场外基金

---

## 它是怎么跑的

```
GitHub Actions（cron 00:30 UTC = 08:30 CST）
  │
  ├─ ① 抓行情     新浪财经（美股/A股/商品）+ 东方财富日线（周涨跌、回撤）
  ├─ ② 抓快讯     新浪财经 7×24（关键词打分筛选）
  ├─ ③ 画图       matplotlib → 横版（网页用）+ 竖版（墨水屏用）
  ├─ ④ 写正文     DeepSeek API → Markdown（术语解释、教学点、建议）
  ├─ ⑤ 转 EPUB    每个 `##` 拆一章，表格/图片按 7.1 寸屏适配
  ├─ ⑥ 投递       坚果云 WebDAV → 投资学习/YYYY-MM/*.epub
  └─ ⑦ 归档       提交回本仓库（Markdown + 图片 + 历史收盘价）
```

设备端：锦鲤「传书 → 网盘 → 添加 WebDAV」
地址 `https://dav.jianguoyun.com/dav/`，账号=邮箱，密码=**应用密码**。

---

## 一次性配置（约 10 分钟）

### 1. 填三个 Secrets

`Settings → Secrets and variables → Actions → New repository secret`

| 名称 | 内容 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | `sk-...` | DeepSeek 控制台创建 |
| `JGY_USER` | 你的坚果云邮箱 | 例如 `withzhangli@163.com` |
| `JGY_PASS` | 坚果云**应用密码** | 网页端「账户信息 → 安全选项 → 添加应用密码」，**不是登录密码** |

> ⚠️ 不要用登录密码，也不要把任何密钥写进代码或发在聊天里。

### 2. 可选变量（`Variables` 页）

| 名称 | 默认 | 说明 |
|---|---|---|
| `JGY_DIR` | `投资学习` | 网盘里的根目录 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 想换模型可改 |

### 3. 手动跑一次

`Actions → daily-invest-note → Run workflow`

跑完去坚果云看 `投资学习/2026-11/` 下有没有当天的 `.epub`。

---

## 本地怎么调试

```bash
pip install -r requirements.txt

# 只验证链路，不调模型、不上传
python scripts/run.py --stub --no-upload

# 只抓数据，看抓到了什么
python scripts/sources.py

# 指定日期补跑
python scripts/run.py --date 2026-11-21 --no-upload
```

`--stub` 生成的稿子带 `_stub.md` 后缀，**不会覆盖正式稿**。

---

## 目录说明

```
.github/workflows/daily.yml   # 定时任务
scripts/
  config.py     # 路径、时区、密钥（只从环境变量读）
  sources.py    # 行情 + 快讯抓取（多源兜底，失败不崩）
  chart.py      # 横版 / 竖版行情图
  note.py       # DeepSeek 提示词与调用
  epub.py       # Markdown → EPUB3（墨水屏排版）
  upload.py     # 坚果云 WebDAV
  run.py        # 串联全流程
投资学习/
  YYYY-MM-DD_第NN期_主题.md   # 每期正文
  images/                       # 行情图（横版 + _portrait 竖版）
  index.md                      # 自动生成的期数索引
data/history.json               # 每日收盘价，用于算周涨跌（会持续累积）
```

**图片命名约定**：Markdown 里引用 `xxx_market.png`，如果同目录存在
`xxx_market_portrait.png`，EPUB 转换时会**自动改用竖版**，正文不用改。

---

## 已知限制

| 限制 | 说明 |
|---|---|
| 定时不准 | GitHub 的 cron 是 best-effort，通常延迟 5~60 分钟，不会准点 08:30 |
| 公开仓库 60 天不活动会停用 cron | 我们每天提交，天然规避 |
| 周涨跌可能缺失 | 依赖东方财富日线；抓不到时该面板自动隐藏，等本地历史攒够 5 天会补上 |
| VIX / 美债 / 美元指数 | 走 Yahoo，被限流时留空，正文写"未获取" |
| 模型不联网 | 新闻来自抓取的快讯原文，不是模型自己"想起来"的 |
| 仓库体积 | 每天约 500KB（两张图），一年约 90MB |

---

## 排错

- **EPUB 没到坚果云**：看 Actions 日志里 `[6/6]` 那一步，多半是 `JGY_PASS` 用了登录密码
- **中文变方块**：Actions 里字体没装上，检查第一步 `fc-list :lang=zh`
- **正文像模板**：`DEEPSEEK_API_KEY` 没配或额度用完，会退回占位稿
- **图表只有一栏**：周涨跌/回撤数据缺失，属正常降级

---

*本仓库内容仅用于投资知识学习，不构成任何投资建议。*
