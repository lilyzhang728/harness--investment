# -*- coding: utf-8 -*-
"""
生成每日市场快照图（2026-11-21）

两种版式：
  landscape —— 三栏横排，用于 Markdown / 网页
  portrait  —— 三行竖排，用于 EPUB / 7.1 寸墨水屏（字更大、不挤）

用法：
  python3 make_chart.py            # 两张都生成
  python3 make_chart.py landscape
  python3 make_chart.py portrait
"""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

plt.rcParams["font.family"] = "Arial Unicode MS"
plt.rcParams["axes.unicode_minus"] = False

RED = "#C0392B"      # 下跌
GREEN = "#1E8449"    # 上涨
GREY = "#2C3E50"

DATE_CN = "2026-11-21"

# ---------- 数据（截至 2026-11-20 收盘） ----------
day = [
    ("COMEX 白银", -7.41),
    ("纳斯达克100", -5.61),
    ("纳斯达克综指", -5.28),
    ("COMEX 黄金", -4.62),
    ("标普500", -3.70),
    ("罗素2000", -2.76),
    ("道琼斯", -1.93),
    ("上证指数", -1.23),
    ("红利低波100", -0.38),
    ("上证50", 0.45),
]

week = [
    ("纳斯达克综指", -10.02),
    ("COMEX 黄金", -9.00),
    ("标普500", -8.61),
    ("道琼斯", -8.02),
]

drawdown = [
    ("COMEX 黄金\n(年内高点)", -36.00),
    ("纳斯达克综指\n(10/6高点)", -18.05),
    ("标普500\n(10/6高点)", -11.62),
    ("道琼斯\n(8/5高点)", -11.41),
]

SOURCE = ("数据来源：新华社 / 新华财经 / 东方财富 / 上海证券报 / 21世纪经济报道；"
          "黄金为COMEX 12月合约、回撤按年内高点计")


def bar(ax, rows, title, subtitle, xmin, xmax, fmt, fs_tick=10.5, fs_title=15, fs_sub=10,
        sub_y=1.04, title_pad=20):
    labels = [r[0] for r in rows]
    vals = [r[1] for r in rows]
    colors = [RED if v < 0 else GREEN for v in vals]
    y = list(range(len(vals)))[::-1]
    bars = ax.barh(y, vals, color=colors, height=0.62, edgecolor="none", alpha=0.92)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=fs_tick, color=GREY)
    ax.axvline(0, color=GREY, lw=1.0)
    for b, v in zip(bars, vals):
        off = (xmax - xmin) * 0.012 if v >= 0 else -(xmax - xmin) * 0.012
        ha = "left" if v >= 0 else "right"
        ax.text(v + off, b.get_y() + b.get_height() / 2, fmt.format(v).replace("-", "−"),
                va="center", ha=ha, fontsize=fs_tick,
                color=RED if v < 0 else GREEN, fontweight="bold",
                bbox=dict(facecolor="white", edgecolor="none", pad=1.2))
    ax.set_title(title, fontsize=fs_title, fontweight="bold", color=GREY, pad=title_pad, loc="left")
    ax.text(0, sub_y, subtitle, transform=ax.transAxes, fontsize=fs_sub, color="#7F8C8D",
            va="bottom")
    ax.set_xlim(xmin, xmax)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: f"{x:.0f}%"))
    ax.grid(axis="x", color="#ECECEC", lw=0.8)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#CCCCCC")
    ax.tick_params(axis="both", length=0)
    ax.tick_params(axis="x", labelsize=fs_tick - 1, colors="#7F8C8D")


def add_thresholds(ax, ymin, ymax, labels=True):
    for x, txt in [(-10, "−10% 技术性回调线"), (-20, "−20% 熊市线")]:
        ax.axvline(x, color="#95A5A6", ls=(0, (4, 3)), lw=1.1)
        if labels:
            ax.text(x - 0.9, ymin + 0.06 * (ymax - ymin), txt, fontsize=9, color="#7F8C8D",
                    ha="center", va="bottom", rotation=90, rotation_mode="anchor")


def landscape(out):
    fig, axes = plt.subplots(1, 3, figsize=(17.2, 6.4),
                             gridspec_kw={"width_ratios": [1.25, 1.0, 1.0]})
    fig.patch.set_facecolor("white")
    bar(axes[0], day, "① 单日涨跌幅", "2026年11月20日（周五）收盘", -10.5, 4.5, "{:.2f}%")
    bar(axes[1], week, "② 本周累计涨跌幅", "11月16日 — 11月20日", -13.5, 3.0, "{:.1f}%")
    bar(axes[2], drawdown, "③ 距近期高点回撤", "回撤 = 从最高点跌下来的幅度",
        -45, 6, "{:.1f}%")
    axes[2].set_ylim(-0.95, 3.55)
    add_thresholds(axes[2], -0.95, 3.55)

    fig.suptitle(f"{DATE_CN} 市场快照 · 风险资产与黄金同步下跌",
                 fontsize=19, fontweight="bold", color=GREY, x=0.045, ha="left", y=1.045)
    fig.text(0.045, 0.995, SOURCE, fontsize=9.2, color="#95A5A6", ha="left")
    fig.tight_layout(rect=[0, 0, 1, 1.0], w_pad=4.0)
    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight", pad_inches=0.35)
    plt.close(fig)
    print("saved", out)


def portrait(out):
    """三行竖排：7.1 寸墨水屏竖屏阅读，字号更大、不挤压。"""
    short_lab = [
        ("COMEX 黄金", -36.00),
        ("纳斯达克综指", -18.05),
        ("标普 500", -11.62),
        ("道琼斯", -11.41),
    ]
    fig = plt.figure(figsize=(7.4, 9.9))
    gs = fig.add_gridspec(3, 1, height_ratios=[10, 4.3, 4.3])
    gs.update(left=0.235, right=0.965, top=0.845, bottom=0.042, hspace=0.62)
    fig.patch.set_facecolor("white")

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])
    ax3 = fig.add_subplot(gs[2])

    bar(ax1, day, "① 单日涨跌幅", "2026年11月20日（周五）收盘", -10.5, 4.8, "{:.2f}%",
        fs_tick=11, fs_title=17, fs_sub=9.8, sub_y=1.008, title_pad=24)
    bar(ax2, week, "② 本周累计涨跌幅", "11月16日 — 11月20日", -13.5, 3.2, "{:.1f}%",
        fs_tick=11, fs_title=17, fs_sub=9.8, sub_y=1.008, title_pad=24)
    bar(ax3, short_lab, "③ 距近期高点回撤",
        "回撤 = 从最高点跌下来的幅度（标普·纳指 10/6 · 道指 8/5 · 黄金年内高）",
        -47, 8, "{:.1f}%", fs_tick=11, fs_title=17, fs_sub=8.8, sub_y=1.008, title_pad=24)
    ax3.set_ylim(-0.72, 3.62)
    add_thresholds(ax3, -0.72, 3.62, labels=False)

    fig.text(0.045, 0.983, f"{DATE_CN} 市场快照", fontsize=19, fontweight="bold",
             color=GREY, va="top")
    fig.text(0.045, 0.952, "风险资产与黄金同步下跌", fontsize=12, color="#5D6D7E", va="top")
    fig.text(0.045, 0.933, "数据：新华社 / 新华财经 / 东方财富 / 上海证券报 / 21世纪经济报道",
             fontsize=7.6, color="#95A5A6", va="top")

    fig.savefig(out, dpi=200, facecolor="white", bbox_inches="tight", pad_inches=0.32)
    plt.close(fig)
    print("saved", out)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    if which in ("both", "landscape"):
        landscape("images/2026-11-21_market.png")
    if which in ("both", "portrait"):
        portrait("images/2026-11-21_market_portrait.png")
