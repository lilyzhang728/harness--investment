"""行情与资讯抓取。

设计原则：**每个数据源都可能失败，失败就返回 None，绝不让整条流水线崩掉。**
行情优先用新浪（国内外都能访问），中证指数用东方财富 / 中证指数官网双备份。
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta

import requests

from config import (
    CN, DATA_DIR, HISTORY_FILE, HISTORY_KEEP, HTTP_TIMEOUT, UA,
)

SINA_H = {"User-Agent": UA, "Referer": "https://finance.sina.com.cn"}

# ---------------------------------------------------------------- 标的定义
US_INDEX = [
    ("gb_$ixic", "nasdaq", "纳斯达克综指"),
    ("gb_$ndx", "ndx100", "纳斯达克100"),
    ("gb_$inx", "sp500", "标普500"),
    ("gb_$dji", "dow", "道琼斯"),
]

FUTURES = [
    ("hf_GC", "gold", "纽约黄金"),
    ("hf_SI", "silver", "纽约白银"),
    ("hf_CL", "wti", "WTI原油"),
    ("hf_OIL", "brent", "布伦特原油"),
]

CN_INDEX = [
    ("s_sh000001", "sh", "上证指数"),
    ("s_sz399001", "sz", "深证成指"),
    ("s_sz399006", "cyb", "创业板指"),
    ("s_sh000016", "sz50", "上证50"),
]

# 强相关词（命中直接入选）与弱相关词（三个才凑够分），避免"美元""基金"这类泛词刷屏
STRONG_WORDS = [
    "美联储", "加息", "降息", "CPI", "PCE", "非农", "通胀",
    "纳指", "纳斯达克", "标普500", "道指", "英伟达", "OpenAI", "Anthropic",
    "黄金", "金价", "红利", "股息", "沪指", "创业板", "QDII", "证监会",
    "国债收益率", "央行", "纳斯达克100", "科技股", "AI泡沫",
]
WEAK_WORDS = [
    "美股", "A股", "芯片", "半导体", "AI", "人工智能", "算力", "美元",
    "美债", "原油", "油价", "关税", "基金", "比特币", "中概", "白银",
    "特朗普", "降准", "MLF", "LPR", "保险资金", "公募",
]


def news_score(text):
    return 3 * sum(1 for w in STRONG_WORDS if w in text) + \
           sum(1 for w in WEAK_WORDS if w in text)


# ---------------------------------------------------------------- 基础工具
def _get(url, headers=None, timeout=HTTP_TIMEOUT):
    try:
        r = requests.get(url, headers={**SINA_H, **(headers or {})}, timeout=timeout)
        if r.status_code != 200:
            return None
        return r
    except Exception:
        return None


def _f(v, default=None):
    try:
        x = float(v)
        if x != x:                      # NaN
            return default
        return x
    except (TypeError, ValueError):
        return default


def _pct(cur, prev):
    if cur is None or prev in (None, 0):
        return None
    return round((cur / prev - 1) * 100, 2)


# ---------------------------------------------------------------- 新浪行情
def _sina_batch(codes):
    """一次性拉多个代码，返回 {code: [字段...]}。"""
    if not codes:
        return {}
    r = _get("https://hq.sinajs.cn/list=" + ",".join(codes))
    if r is None:
        return {}
    r.encoding = "gbk"
    out = {}
    for line in r.text.split(";"):
        line = line.strip()
        if not line.startswith("var hq_str_"):
            continue
        try:
            code = line.split("hq_str_", 1)[1].split("=", 1)[0]
            payload = line.split('="', 1)[1].rstrip('"')
            if payload:
                out[code] = payload.split(",")
        except IndexError:
            continue
    return out


def fetch_us_index():
    raw = _sina_batch([c for c, _, _ in US_INDEX])
    rows = []
    for code, key, name in US_INDEX:
        f = raw.get(code)
        if not f or len(f) < 27:
            continue
        close = _f(f[1])
        pct = _f(f[2])
        high52 = _f(f[8])
        low52 = _f(f[9])
        prev = _f(f[26])
        if close is None:
            continue
        rows.append({
            "key": key, "name": name, "close": close, "pct": pct,
            "prev": prev, "high52": high52, "low52": low52,
            "day_high": _f(f[6]), "day_low": _f(f[7]),
            "quote_time": (f[3] or "").strip(),
            "source": "sina",
        })
    return rows


def fetch_futures():
    raw = _sina_batch([c for c, _, _ in FUTURES])
    rows = []
    for code, key, name in FUTURES:
        f = raw.get(code)
        if not f or len(f) < 8:
            continue
        close = _f(f[0])
        prev = _f(f[7]) or _f(f[8])
        if close is None:
            continue
        rows.append({
            "key": key, "name": name, "close": close,
            "pct": _pct(close, prev), "prev": prev,
            "day_high": _f(f[4]), "day_low": _f(f[5]),
            "source": "sina",
        })
    return rows


def fetch_cn_index():
    raw = _sina_batch([c for c, _, _ in CN_INDEX])
    rows = []
    for code, key, name in CN_INDEX:
        f = raw.get(code)
        if not f or len(f) < 4:
            continue
        close = _f(f[1])
        if close is None:
            continue
        rows.append({
            "key": key, "name": name, "close": close,
            "pct": _f(f[3]), "amount_wan": _f(f[5]) if len(f) > 5 else None,
            "source": "sina",
        })
    return rows


# ---------------------------------------------------------------- 红利低波 100
def _fetch_930955_eastmoney():
    s = requests.Session()
    s.trust_env = True
    try:
        r = s.get(
            "https://push2.eastmoney.com/api/qt/stock/get"
            "?secid=2.930955&fields=f43,f58,f60,f170",
            headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT,
        )
        d = (r.json() or {}).get("data") or {}
        raw_close = _f(d.get("f43"))
        if raw_close is None:
            return None
        # 东财指数价格常被放大 100 倍，用合理区间反推
        for div in (100, 10, 1, 1000):
            v = raw_close / div
            if 3000 < v < 40000:
                return {
                    "key": "div100", "name": "红利低波100", "close": round(v, 2),
                    "pct": (_f(d.get("f170")) or 0) / 100,
                    "prev": round(_f(d.get("f60")) / div, 2) if _f(d.get("f60")) else None,
                    "source": "eastmoney",
                }
        return None
    except Exception:
        return None


def _fetch_930955_csindex():
    end = date.today()
    start = end - timedelta(days=20)
    url = ("https://www.csindex.com.cn/csindex-home/perf/index-perf"
           f"?indexCode=930955&startDate={start:%Y%m%d}&endDate={end:%Y%m%d}")
    r = _get(url)
    if r is None:
        return None
    try:
        rows = (r.json() or {}).get("data") or []
        rows = [x for x in rows if x.get("tradeDate")]
        rows.sort(key=lambda x: x["tradeDate"])
        if len(rows) < 2:
            return None
        last, prev = rows[-1], rows[-2]
        close = _f(last.get("close") or last.get("closePoint"))
        p = _f(prev.get("close") or prev.get("closePoint"))
        if close is None:
            return None
        return {
            "key": "div100", "name": "红利低波100", "close": round(close, 2),
            "pct": _pct(close, p), "prev": round(p, 2) if p else None,
            "trade_date": last.get("tradeDate"), "source": "csindex",
        }
    except Exception:
        return None


def fetch_dividend100():
    for fn in (_fetch_930955_eastmoney, _fetch_930955_csindex):
        try:
            v = fn()
            if v:
                return v
        except Exception:
            continue
    return None


# ---------------------------------------------------------------- 可选指标
def _yahoo(symbol):
    for host in ("query1", "query2"):
        r = _get(f"https://{host}.finance.yahoo.com/v8/finance/chart/"
                 f"{requests.utils.quote(symbol)}?range=5d&interval=1d")
        if r is None:
            continue
        try:
            res = r.json()["chart"]["result"][0]
            closes = [c for c in res["indicators"]["quote"][0]["close"] if c]
            if len(closes) >= 2:
                return closes[-1], closes[-2]
        except Exception:
            continue
    return None


def fetch_optional():
    """VIX / 美债 10Y / 美元指数 —— 拿不到就算了，笔记里会写“未获取”。"""
    out = {}
    for sym, key, name, scale in [
        ("^VIX", "vix", "VIX 恐慌指数", 1),
        ("^TNX", "ust10y", "美国10年期国债收益率", 0.1),
        ("DX-Y.NYB", "dxy", "美元指数", 1),
    ]:
        try:
            q = _yahoo(sym)
            if not q:
                continue
            cur, prev = q
            if key == "ust10y" and cur > 20:      # 有的源报价是收益率×10
                cur, prev = cur / 10, prev / 10
            out[key] = {
                "key": key, "name": name, "close": round(cur, 3),
                "pct": _pct(cur, prev), "prev": round(prev, 3),
                "is_rate": key == "ust10y", "source": "yahoo",
            }
        except Exception:
            continue
        time.sleep(0.3)
    return out


# ---------------------------------------------------------------- 资讯
def fetch_news(limit=30, pages=3):
    items, seen = [], set()
    for page in range(1, pages + 1):
        url = ("https://zhibo.sina.com.cn/api/zhibo/feed"
               f"?page={page}&page_size=50&zhibo_id=152&tag_id=0&dire=f&dpc=1")
        r = _get(url)
        if r is None:
            break
        try:
            lst = (((r.json() or {}).get("result") or {})
                   .get("data") or {}).get("feed", {}).get("list") or []
        except Exception:
            break
        for it in lst:
            text = (it.get("rich_text") or "").strip()
            if not text or text in seen:
                continue
            if news_score(text) < 3:
                continue
            seen.add(text)
            items.append({
                "time": (it.get("create_time") or "")[5:16],
                "text": text[:220],
            })
        time.sleep(0.3)
    items.sort(key=lambda x: x["time"], reverse=True)
    return items[:limit]


# ---------------------------------------------------------------- 东财日线（补周涨跌与回撤）
EM_SECID = {
    "nasdaq": "100.NDX",
    "sp500": "100.SPX",
    "dow": "100.DJIA",
    "div100": "2.930955",
    "sh": "1.000001",
    "sz": "0.399001",
    "cyb": "0.399006",
    "sz50": "1.000016",
    "gold": "101.GC00Y",
    "silver": "101.SI00Y",
    "wti": "101.CL00Y",
}

_EM_CACHE = {}


def _load_em_cache():
    try:
        return json.loads((DATA_DIR / "em_cache.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_em_cache(cache):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "em_cache.json").write_text(
        json.dumps(cache, ensure_ascii=False), encoding="utf-8")


def em_closes(secid, days=300):
    """取东财日线收盘价（升序）。失败返回 []。同一天内命中磁盘缓存，避免重复请求。"""
    if secid in _EM_CACHE:
        return _EM_CACHE[secid]
    today = date.today().isoformat()
    disk = _load_em_cache()
    hit = disk.get(secid)
    if hit and hit.get("date") == today and hit.get("closes"):
        _EM_CACHE[secid] = hit["closes"]
        return hit["closes"]

    out = []
    beg = (date.today() - timedelta(days=days * 2)).strftime("%Y%m%d")
    url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get"
           f"?secid={secid}&klt=101&fqt=1&beg={beg}&end=20500101&lmt=600"
           "&fields1=f1,f2,f3&fields2=f51,f53")
    for attempt in range(3):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT)
            klines = ((r.json() or {}).get("data") or {}).get("klines") or []
            for k in klines:
                parts = k.split(",")
                if len(parts) >= 2:
                    v = _f(parts[1])
                    if v is not None:
                        out.append(v)
            if out:
                break
        except Exception:
            pass
        time.sleep(1.0 + attempt)
    _EM_CACHE[secid] = out
    if out:
        disk[secid] = {"date": today, "closes": out[-300:]}
        try:
            _save_em_cache(disk)
        except Exception:
            pass
    return out


# ---------------------------------------------------------------- 历史与派生指标
def load_history():
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_history(hist):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(hist, ensure_ascii=False, indent=1, sort_keys=True),
        encoding="utf-8",
    )


def update_history(hist, rows, today_str):
    for r in rows:
        if not r or r.get("close") is None:
            continue
        series = hist.setdefault(r["key"], {})
        series[today_str] = round(float(r["close"]), 4)
        if len(series) > HISTORY_KEEP:
            for old in sorted(series)[: len(series) - HISTORY_KEEP]:
                series.pop(old, None)
    return hist


def enrich(rows, hist, today: date):
    """补上周涨跌与回撤。数据不够就留 None，不做任何猜测。"""
    for r in rows:
        if not r:
            continue
        series = hist.get(r["key"], {})
        # --- 一周涨跌：找 7 天前最近的一条
        cutoff = (today - timedelta(days=6)).isoformat()
        past = [(d, v) for d, v in series.items() if d <= cutoff]
        if past:
            base = max(past)[1]
            r["week"] = _pct(r["close"], base)
            r["week_base_date"] = max(past)[0]
        else:
            r.setdefault("week", None)
        # --- 先用东财日线补齐周涨跌与 52 周高点（比自建历史更快见效）
        secid = EM_SECID.get(r["key"])
        closes = em_closes(secid) if secid else []
        # 防串号：日线最后一个值必须和我们拿到的现价对得上（误差 2% 以内）
        if closes and r.get("close"):
            if abs(closes[-1] / r["close"] - 1) > 0.02:
                closes = []
        if closes:
            last_n = closes[-250:]
            if r.get("high") is None and len(last_n) > 60:
                r["high"] = max(last_n)
            if r.get("week") is None and len(closes) >= 6:
                base = closes[-6]
                r["week"] = _pct(r["close"], base)
                r["week_base_date"] = "em_kline_6d_ago"

        # --- 回撤：优先用数据源自带的 52 周高点，否则用我们自己积累的历史
        high = r.get("high52")
        if not high and len(series) >= 20:
            high = max(series.values())
        r["high"] = high
        r["dd"] = _pct(r["close"], high) if high else None
    return rows


# ---------------------------------------------------------------- 汇总
def build_snapshot():
    now = datetime.now(CN)
    today = now.date()
    today_str = today.isoformat()

    hist = load_history()
    us = fetch_us_index()
    fut = fetch_futures()
    cn = fetch_cn_index()
    div = fetch_dividend100()
    opt = fetch_optional()

    all_rows = us + fut + cn + ([div] if div else [])
    update_history(hist, all_rows, today_str)
    save_history(hist)
    for rows in (us, fut, cn):
        enrich(rows, hist, today)
    if div:
        enrich([div], hist, today)

    return {
        "date": today_str,
        "weekday": "周" + "一二三四五六日"[today.weekday()],
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "is_weekend": today.weekday() >= 5,
        "us": us,
        "futures": fut,
        "cn": cn,
        "dividend100": div,
        "optional": opt,
        "news": fetch_news(),
        "history_days": {k: len(v) for k, v in hist.items()},
    }


if __name__ == "__main__":
    snap = build_snapshot()
    snap["news"] = snap["news"][:5]
    print(json.dumps(snap, ensure_ascii=False, indent=1))
