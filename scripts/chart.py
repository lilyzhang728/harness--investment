"""行情快照图：横排（网页）与竖排（墨水屏 EPUB）两种版式。"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.ticker import FuncFormatter

RED, GREEN, GREY = "#C0392B", "#1E8449", "#2C3E50"

CJK_CANDIDATES = [
    "Noto Sans CJK SC", "Noto Sans CJK JP", "WenQuanYi Zen Hei", "WenQuanYi Micro Hei",
    "Source Han Sans SC", "Microsoft YaHei", "PingFang SC", "Heiti TC",
    "Hiragino Sans GB", "Arial Unicode MS", "SimHei",
]


def _setup_font():
    available = {f.name for f in font_manager.fontManager.ttflist}
    for name in CJK_CANDIDATES:
        if name in available:
            plt.rcParams["font.family"] = name
            plt.rcParams["font.sans-serif"] = [name]
            break
    plt.rcParams["axes.unicode_minus"] = False


def _bar(ax, rows, title, subtitle, xmin, xmax, fmt, fs=10.5, fs_title=15,
         fs_sub=10, sub_y=1.04, pad=20):
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
                 pad=pad, loc="left")
    ax.text(0, sub_y, subtitle, transform=ax.transAxes, fontsize=fs_sub,
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
    fig.suptitle(f"{date_cn} 市场快照", fontsize=19, fontweight="bold",
                 color=GREY, x=0.045, ha="left", y=1.04)
    fig.text(0.045, 0.995, _source_line(snap), fontsize=9, color="#95A5A6", ha="left")
    fig.tight_layout(rect=[0, 0, 1, 1.0], w_pad=4.0)
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)


def portrait(snap, out, date_cn):
    """竖排：7.1 寸墨水屏一屏放下，字号相对更大。"""
    day, week, dd = _panels(snap)
    panels = []
    if day:
        panels.append(("① 单日涨跌幅", f"{date_cn} 收盘", day, None, None, "{:.2f}%", 10))
    if week:
        panels.append(("② 本周累计涨跌幅", "近 5 个交易日", week, None, None, "{:.1f}%", 4.3))
    if dd:
        panels.append(("③ 距高点回撤", "回撤 = 从最高点跌下来的幅度", dd, None, None,
                       "{:.1f}%", 4.3))
    if not panels:
        return
    weights = [p[6] for p in panels]
    fig = plt.figure(figsize=(7.4, 12.6 if len(panels) == 3 else 4.0 * len(panels) + 1))
    gs = fig.add_gridspec(len(panels), 1, height_ratios=weights)
    gs.update(left=0.235, right=0.965, top=0.845 if len(panels) == 3 else 0.80,
              bottom=0.045, hspace=0.62)
    fig.patch.set_facecolor("white")
    for idx, (title, sub, rows, xmin, xmax, fmt, _w) in enumerate(panels):
        ax = fig.add_subplot(gs[idx])
        _bar(ax, rows, title, sub, xmin, xmax, fmt, fs=11, fs_title=17,
             fs_sub=9.8, sub_y=1.008, pad=24)
        if title.startswith("③"):
            for x in (-10, -20):
                ax.axvline(x, color="#95A5A6", ls=(0, (4, 3)), lw=1.1)
    fig.text(0.045, 0.983, f"{date_cn} 市场快照", fontsize=19, fontweight="bold",
             color=GREY, va="top")
    fig.text(0.045, 0.952, "每日投资学习材料 · 行情附表", fontsize=12,
             color="#5D6D7E", va="top")
    fig.text(0.045, 0.933, _source_line(snap), fontsize=7.2,
             color="#95A5A6", va="top")
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight", pad_inches=0.32)
    plt.close(fig)


def render(snap, date_cn, img_dir, prefix="market"):
    _setup_font()
    img_dir.mkdir(parents=True, exist_ok=True)
    land = img_dir / f"{prefix}.png"
    port = img_dir / f"{prefix}_portrait.png"
    landscape(snap, str(land), date_cn)
    portrait(snap, str(port), date_cn)
    return land, port
