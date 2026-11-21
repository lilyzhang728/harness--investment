"""每日流水线：抓数据 → 画图 → 写笔记 → 转 EPUB → 推送到坚果云。

用法：
    python scripts/run.py                # 正式跑（需要 DEEPSEEK_API_KEY / JGY_*）
    python scripts/run.py --stub         # 不调模型，用数据拼占位稿（测链路）
    python scripts/run.py --no-upload    # 只生成，不上传
    python scripts/run.py --date 2026-11-21
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import chart
import epub
import note
import sources
import upload
from config import BUILD_DIR, CN, IMG_DIR, NOTE_DIR

EP_RE = re.compile(r"_第(\d+)期")
THEME_RE = re.compile(r"主题：\s*([^\n*]+)")


def next_episode(today_str):
    """今天已有文件就沿用它的期号（重跑覆盖），否则取最大期号 +1。"""
    files = sorted(NOTE_DIR.glob("*.md"))
    for f in files:
        if f.name.startswith(today_str):
            m = EP_RE.search(f.name)
            if m:
                return int(m.group(1)), f
    nums = [int(m.group(1)) for f in files if (m := EP_RE.search(f.name))]
    return (max(nums) + 1 if nums else 1), None


def prev_title(exclude=None):
    files = [f for f in sorted(NOTE_DIR.glob("*.md")) if f != exclude]
    if not files:
        return ""
    text = files[-1].read_text(encoding="utf-8")[:600]
    m = THEME_RE.search(text)
    return m.group(1).strip() if m else ""


def slugify(md_text):
    m = THEME_RE.search(md_text[:800])
    raw = m.group(1) if m else "每日笔记"
    raw = re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]+", "", raw)
    return (raw[:12] or "每日笔记")


def build_index():
    rows = []
    for f in sorted(NOTE_DIR.glob("*.md"), reverse=True):
        m = EP_RE.search(f.name)
        if not m or f.name.startswith("index") or f.name.endswith("_stub.md"):
            continue
        first = ""
        for line in f.read_text(encoding="utf-8").splitlines()[:8]:
            if "主题" in line:
                first = THEME_RE.search(line)
                first = first.group(1).strip() if first else ""
                break
        rows.append(f"| 第 {int(m.group(1)):02d} 期 | {f.name[:10]} | "
                    f"[{first or '—'}]({f.name}) |")
    body = ("# 学习档案索引\n\n"
            "> 由流水线自动生成，按日期倒序。\n\n"
            "| 期数 | 日期 | 主题 |\n|---|---|---|\n" + "\n".join(rows) + "\n")
    (NOTE_DIR / "index.md").write_text(body, encoding="utf-8")
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stub", action="store_true", help="不调用模型")
    ap.add_argument("--no-upload", action="store_true", help="不上传坚果云")
    ap.add_argument("--date", help="覆盖日期 YYYY-MM-DD（仅用于补跑）")
    args = ap.parse_args()

    today_str = args.date or datetime.now(CN).date().isoformat()
    today = date.fromisoformat(today_str)
    date_cn = f"{today.year}年{today.month}月{today.day}日"
    print(f"== 开始：{today_str} ==")

    print("[1/6] 抓行情与快讯 ...")
    snap = sources.build_snapshot()
    if args.date:
        snap["date"] = today_str
        snap["weekday"] = "周" + "一二三四五六日"[today.weekday()]
        snap["is_weekend"] = today.weekday() >= 5
    print(f"      美股 {len(snap['us'])}｜商品 {len(snap['futures'])}｜"
          f"A股 {len(snap['cn'])}｜红利100 {'有' if snap['dividend100'] else '无'}｜"
          f"快讯 {len(snap['news'])}｜可选 {list(snap['optional'])}")

    print("[2/6] 生成行情图 ...")
    prefix = f"{today_str}_market"
    land, ports = chart.render(snap, date_cn, IMG_DIR, prefix=prefix)
    print(f"      {land.name} / " + " / ".join(p.name for p in ports))

    ep, existing = next_episode(today_str)
    if existing and existing.name.endswith("_stub.md"):
        existing = None
    print(f"[3/6] 第 {ep} 期，写正文 ...")
    tmp_md = BUILD_DIR / f".tmp_{today_str}.md"
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    if args.stub:
        md = note.stub(snap, ep, tmp_md)
        print("      使用占位稿（--stub）")
    else:
        md = note.generate(snap, ep, prev_title(existing), tmp_md)
        print(f"      模型输出 {len(md)} 字")

    # 同一天重跑时沿用原文件名；--stub 另存 _stub 后缀，永不覆盖正式稿
    if args.stub:
        target = NOTE_DIR / f"{today_str}_第{ep:02d}期_stub.md"
    else:
        target = existing if existing else NOTE_DIR / f"{today_str}_第{ep:02d}期_{slugify(md)}.md"
    target.write_text(md, encoding="utf-8")
    tmp_md.unlink(missing_ok=True)
    print(f"      {target.name}")

    print("[4/6] 转 EPUB ...")
    out_epub = BUILD_DIR / f"{today_str}_第{ep:02d}期.epub"
    _, n_ch, kb = epub.build_epub(target, out_epub)
    print(f"      {out_epub.name}（{n_ch} 章，{kb:.0f} KB）")

    print("[5/6] 更新索引 ...")
    print(f"      index.md 收录 {build_index()} 期")

    if args.no_upload:
        print("[6/6] 跳过上传（--no-upload）")
        return 0
    print("[6/6] 推送到坚果云 ...")
    urls = upload.upload(out_epub, today_str)
    for u in urls:
        print(f"      {u}")
    print("== 完成 ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
