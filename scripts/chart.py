"""行情快照图：横排（网页）与竖排（墨水屏 EPUB）两种版式。

竖排版式按汉王 Clear7 锦鲤的屏幕（7.0" / 300ppi / 1264×1680）1:1 出图：
   · 画布固定 3:4，一张图恰好一屏，不会被裁切
   · 每个面板单独一屏，字号不会为了塞进一屏而缩到看不清
   · 标签用衬线宋体（Noto Serif CJK），比黑体更接近纸质书
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter

RED, GREEN, GREY = "#B03A2E", "#1E7B4D", "#2F3640"

# 汉王 Clear7 锦鲤：7.0 英寸 / 300ppi / 1264×1680
SCREEN_W, SCREEN_H = 1264, 1680
DPI = 300
PAGE_W = (SCREEN_W + 0.5) / DPI  # 4.215 in（+0.5 抵消取整，正好 1264×1680）
PAGE_H = (SCREEN_H + 0.5) / DPI  # 5.602 in

# 优先衬线（宋体），退路才是黑体
CJK_CANDIDATES = [
    "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", "STSong",
    "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Zen Hei",
    "WenQuanYi Micro Hei", "Microsoft YaHei", "PingFang SC", "Heiti TC",
    "Hiragino Sans GB", "Arial Unicode MS", "SimHei",
]


def _setup_font():
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in CJK_CANDIDATES:
        if name in available:
            # 第二个字体兜底 U+2212（真减号），宋体里通常没有这个字形
            plt.rcParams["font.family"] = [name, "DejaVu Sans"]
            plt.rcParams["font.sans-serif"] = [name, "DejaVu Sans"]
            break
    plt.rcParams["axes.unicode_minus"] = True


def _em(text):
    """粗略估算一段文字的宽度（单位：em）。中文算 1，西文数字算 0.55。"""
    return sum(1.0 if ord(c) > 0x2E80 else 0.55 for c in text)


def _panels(snap):
    """把快照整理成三组柱状图数据。缺失的指标自动剔除。"""
    rows = []
    for r in snap.get("us", []):
        rows.append((r["name"], r.get("pct")))
    for r in snap.get("futures", []):
        rows.append((r["name"], r.get("pct")))
    for r in snap.get("cn", []):
        rows.append((r["name"], r.get("pct")))
    if snap.get("dividend100"):
        rows.append(("红利低波100", snap["dividend100"].get("pct")))
    day = sorted([(n, v) for n, v in rows if v is not None], key=lambda x: x[1])

    allrows = snap.get("us", []) + snap.get("futures", []) + snap.get("cn", [])
    if snap.get("dividend100"):
        allrows = allrows + [snap["dividend100"]]
    week = sorted([(r["name"], r["week"]) for r in allrows if r.get("week") is not None],
                  key=lambda x: x[1])
    dd = sorted([(r["name"], r["dd"]) for r in allrows if r.get("dd") is not None],
                key=lambda x: x[1])
    return day, week, dd


def _source_line(snap):
    names = {r.get("source") for r in snap.get("us", []) + snap.get("futures", []) +
             snap.get("cn", [])}
    label = {"sina": "新浪财经", "eastmoney": "东方财富", "csindex": "中证指数"}
    src = " / ".join(label.get(n, n) for n in sorted(filter(None, names)))
    return f"数据来源：{src or '—'}　·　涨跌幅为当日收盘，周涨跌与回撤按日线计算"


# ------------------------------------------------------------------ 横版（网页）
def _bar(ax, rows, title, subtitle, xmin, xmax, fmt, fs=10.5, fs_title=15,
         fs_sub=10, pad=20):
    labels = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    # 自动缩放：保证标签永远不被切掉
    lo, hi = min(vals + [0.0]), max(vals + [0.0])
    span0 = max(hi - lo, 1.0)
    pad0 = max(1.2, span0 * 0.16)
    xmin = min(lo - pad0, -pad0) if xmin is None else xmin
    xmax = max(hi + pad0, pad0) if xmax is None else xmax
    colors = [RED if v < 0 else GREEN for v in vals]
    y = list(range(len(vals)))[::-1]
    bars = ax.barh(y, vals, color=colors, height=0.62, edgecolor="none", alpha=0.92)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=fs, color=GREY)
    ax.axvline(0, color=GREY, lw=1.0)
    span = xmax - xmin
    for b, v in zip(bars, vals):
        off = span * 0.012 if v >= 0 else -span * 0.012
        ax.text(v + off, b.get_y() + b.get_height() / 2,
                fmt.format(v).replace("-", "−"), va="center",
                ha="left" if v >= 0 else "right", fontsize=fs,
                color=RED if v < 0 else GREEN, fontweight="bold",
                bbox=dict(facecolor="white", edgecolor="none", pad=1.2))
    ax.set_title(title, fontsize=fs_title, fontweight="bold", color=GREY,
                 pad=pad + 8, loc="left")
    ax.text(0, 1.0, subtitle, transform=ax.transAxes, fontsize=fs_sub,
            color="#7F8C8D", va="bottom")
    ax.set_xlim(xmin, xmax)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f"{x:.0f}%"))
    ax.grid(axis="x", color="#ECECEC", lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.tick_params(axis="both", length=0)
    ax.tick_params(axis="x", labelsize=fs - 1, colors="#7F8C8D")


def landscape(snap, out, date_cn):
    day, week, dd = _panels(snap)
    n = 1 + (1 if week else 0) + (1 if dd else 0)
    fig, axes = plt.subplots(1, n, figsize=(5.8 * n, 6.4))
    if n == 1:
        axes = [axes]
    fig.patch.set_facecolor("white")
    i = 0
    if day:
        _bar(axes[i], day, "① 单日涨跌幅", f"{date_cn} 收盘", None, None, "{:.2f}%")
        i += 1
    if week:
        _bar(axes[i], week, "② 本周累计涨跌幅", "近 5 个交易日", None, None, "{:.1f}%")
        i += 1
    if dd:
        _bar(axes[i], dd, "③ 距高点回撤", "回撤 = 从最高点跌下来的幅度", None, None, "{:.1f}%")
        for x in (-10, -20):
            axes[i].axvline(x, color="#95A5A6", ls=(0, (4, 3)), lw=1.1)
    fig.text(0.045, 1.075, f"{date_cn} 市场快照", fontsize=19, fontweight="bold",
             color=GREY, ha="left", va="bottom")
    fig.text(0.045, 1.012, _source_line(snap), fontsize=8.5, color="#95A5A6",
             ha="left", va="bottom")
    fig.tight_layout(rect=[0, 0, 1, 1.0], w_pad=4.0)
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)


# ------------------------------------------------------------------ 竖版（墨水屏）
def _bar_portrait(ax, rows, fmt, fs, marks=()):
    """一屏之内的一组横向条形图：数值标签贴着条形末端，不压住条形。"""
    labels = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    lo, hi = min(vals + [0.0]), max(vals + [0.0])
    span0 = max(hi - lo, 0.5)
    lo -= span0 * 0.04
    hi += span0 * 0.04

    # 数值标签会伸出条形，按英寸估宽后换算成数据单位，避免被裁掉
    axis_w_in = ax.get_position().width * PAGE_W
    lab_em = max(_em(fmt.format(v)) for v in vals) + 0.12
    lab_in = lab_em * fs * 0.86 / 72
    left_in = lab_in if any(v < 0 for v in vals) else 0.02
    right_in = lab_in if any(v > 0 for v in vals) else 0.02
    base = hi - lo
    extra = (left_in + right_in) / max(axis_w_in, 0.5)
    total = base / max(1.0 - extra, 0.55)
    per_in = total / axis_w_in
    lo -= left_in * per_in
    hi += right_in * per_in

    colors = [RED if v < 0 else GREEN for v in vals]
    y = list(range(len(vals)))[::-1]
    bars = ax.barh(y, vals, color=colors, height=0.64, edgecolor="none", alpha=0.95)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=fs, color=GREY)
    ax.axvline(0, color=GREY, lw=1.0, zorder=3)
    for b, v in zip(bars, vals):
        off = (hi - lo) * 0.008 if v >= 0 else -(hi - lo) * 0.008
        ax.text(v + off, b.get_y() + b.get_height() / 2,
                fmt.format(v).replace("-", "−"), va="center",
                ha="left" if v >= 0 else "right", fontsize=fs * 0.86,
                color="#333333", zorder=4)
    for x in marks:
        ax.axvline(x, color="#95A5A6", ls=(0, (4, 3)), lw=1.0, zorder=1)
    ax.set_xlim(lo, hi)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f"{x:.0f}%"))
    ax.grid(axis="x", color="#ECECEC", lw=0.7)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#BBBBBB")
    ax.tick_params(axis="both", length=0)
    ax.tick_params(axis="y", pad=8)
    ax.tick_params(axis="x", labelsize=fs * 0.78, colors="#7F8C8D", pad=2)


DD_NOTE = "−10% 常称「技术性回调」，−20% 常称「熊市」。\n回撤越深，回本需要的涨幅越大。"

MAX_ROWS_PER_PAGE = 18


def _paginate(panels, limit=MAX_ROWS_PER_PAGE):
    """按行数把面板装进一屏一页，行太多就换页，保证字号不被压得太小。"""
    pages, cur, rows = [], [], 0
    for panel in panels:
        n = len(panel[2])
        if cur and rows + n > limit:
            pages.append(cur)
            cur, rows = [], 0
        cur.append(panel)
        rows += n
    if cur:
        pages.append(cur)
    return pages


def _page(panels, out, date_cn, snap, first):
    """把一组面板画成一张 3:4 的整屏图（面板从上往下排）。"""
    fig = plt.figure(figsize=(PAGE_W, PAGE_H), dpi=DPI)
    fig.patch.set_facecolor("white")

    top = 0.850 if first else 0.958
    bottom = 0.070
    header = 0.088          # 标题 + 副标题
    tick = 0.052            # x 轴刻度文字 + 与下一块标题的间距
    rows_total = sum(len(p[2]) for p in panels)
    avail = top - bottom - len(panels) * (header + tick)
    pitch = avail / max(rows_total, 1)
    fs = max(8.6, min(15.5, pitch * PAGE_H * 72 * 0.62))
    if pitch * PAGE_H * 72 * 0.62 > 15.5:
        # 行数很少时别把条格拉成巨无霸
        pitch = 15.5 / (PAGE_H * 72 * 0.62)
    fs_title = 16.5
    fs_sub = 9.5

    max_em = max(_em(r[0]) for p in panels for r in p[2])
    left = (max_em * fs / 72 + 0.18) / PAGE_W
    right = 1.0 - 0.07 / PAGE_W

    last_note = panels[-1][5] if panels else ""
    y = top
    for title, sub, rows, fmt, marks, note in panels:
        ax = fig.add_axes([left, y - header - len(rows) * pitch,
                           right - left, len(rows) * pitch])
        _bar_portrait(ax, rows, fmt, fs, marks)
        fig.text(0.045, y - 0.006, title, fontsize=fs_title, fontweight="bold",
                 color=GREY, va="top")
        fig.text(0.045, y - 0.006 - fs_title / (72 * PAGE_H) - 0.010, sub,
                 fontsize=fs_sub, color="#7F8C8D", va="top")
        y -= header + len(rows) * pitch + tick

    if first:
        fig.text(0.045, 0.968, f"{date_cn} 市场快照", fontsize=18,
                 fontweight="bold", color=GREY, va="top")
        fig.text(0.045, 0.918, "每日投资学习材料 · 行情附表", fontsize=10.5,
                 color="#5D6D7E", va="top")

    # 只有一两个面板的稀疏页，补一句读图提示，别让下半页空着
    if last_note and y - 0.045 > 0.12:
        fig.text(0.045, y - 0.045, last_note, fontsize=10, color="#5D6D7E",
                 va="top", linespacing=1.9)

    fig.text(0.045, 0.016, f"{date_cn}　·　{_source_line(snap)}", fontsize=6.2,
             color="#95A5A6", va="bottom")
    fig.savefig(out, dpi=DPI, facecolor="white")
    plt.close(fig)


def portrait(snap, out, date_cn):
    """竖排：按行数自动分页，每页 3:4 恰好一屏。返回生成的文件列表。"""
    day, week, dd = _panels(snap)
    day_p = ("① 单日涨跌幅", f"{date_cn} 收盘", day, "{:.2f}%", (), "") if day else None
    week_p = ("② 本周累计涨跌幅", "近 5 个交易日", week, "{:.1f}%", (), "") if week else None
    dd_p = ("③ 距高点回撤", "回撤 = 从最高点跌下来的幅度", dd, "{:.1f}%",
            (-10, -20), DD_NOTE) if dd else None

    pages = _paginate([p for p in (day_p, week_p, dd_p) if p])

    out = str(out)
    stem, ext = os.path.splitext(out)
    made = []
    for i, page in enumerate(pages):
        path = out if i == 0 else f"{stem}{i + 1}{ext}"
        _page(page, path, date_cn, snap, i == 0)
        made.append(path)
    # 清掉上一次残留的多余分页
    for i in range(len(pages), 4):
        try:
            os.remove(out if i == 0 else f"{stem}{i + 1}{ext}")
        except OSError:
            pass
    return made


def render(snap, date_cn, img_dir, prefix="market"):
    _setup_font()
    img_dir.mkdir(parents=True, exist_ok=True)
    land = img_dir / f"{prefix}.png"
    port = img_dir / f"{prefix}_portrait.png"
    landscape(snap, str(land), date_cn)
    made = portrait(snap, str(port), date_cn)
    return land, [img_dir / os.path.basename(p) for p in made]
