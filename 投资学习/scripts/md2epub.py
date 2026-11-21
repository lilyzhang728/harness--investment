#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
md2epub.py — 把《每日投资学习材料》的 Markdown 转成适合墨水屏（7.1 寸）阅读的 EPUB 3

设计目标：
  1. 零外部依赖（只用到 python 的 markdown 包）
  2. 每个 `## ` 一级小节拆成一章 —— 墨水屏翻页更快、目录可跳转
  3. 表格、引用块、图片都做小屏适配（字号、折行、边距）
  4. 输出标准 EPUB3 + ncx 回退，兼容老旧阅读器

用法：
    python3 md2epub.py <input.md> [output.epub]
"""

import os
import re
import sys
import shutil
import zipfile
import hashlib
from datetime import datetime, timezone

import markdown

VOID_TAGS = ("img", "br", "hr", "meta", "link", "input", "col", "area", "base")

# ---------------------------------------------------------------- 墨水屏样式
# 7.1" / 300ppi / 4GB RAM：字号偏大、行距宽松、表格缩排、图片不超宽
CSS = """@charset "utf-8";

html, body { margin: 0; padding: 0; }

body {
  font-family: "Noto Serif CJK SC", "Source Han Serif SC", "Songti SC", "STSong", serif;
  font-size: 1em;
  line-height: 1.68;
  color: #111;
  text-align: justify;
  word-wrap: break-word;
}

/* ---------- 封面 / 章节标题 ---------- */
.cover {
  padding: 22% 8% 0 8%;
  text-align: center;
  page-break-after: always;
}
.cover .kicker {
  font-size: 0.8em;
  letter-spacing: 0.25em;
  color: #666;
  margin-bottom: 1.6em;
}
.cover h1 {
  font-size: 1.75em;
  line-height: 1.4;
  margin: 0 0 1.1em 0;
  font-weight: bold;
  text-align: center;
}
.cover .sub {
  font-size: 1.05em;
  color: #333;
  line-height: 1.9;
  margin: 1.4em 0 0 0;
}
.cover .rule {
  border: 0;
  border-top: 1px solid #999;
  width: 40%;
  margin: 2.2em auto;
}
.cover .hint {
  font-size: 0.82em;
  color: #777;
  line-height: 1.9;
  text-align: left;
  margin-top: 2.5em;
}

h1 { font-size: 1.5em; line-height: 1.4; margin: 1.2em 0 0.5em; text-align: left; }
h2 {
  font-size: 1.28em;
  line-height: 1.45;
  margin: 1.1em 0 0.7em;
  padding-left: 0.55em;
  border-left: 5px solid #333;
  text-align: left;
  page-break-after: avoid;
}
h3 { font-size: 1.1em; margin: 1.3em 0 0.45em; text-align: left; page-break-after: avoid; }
h4 { font-size: 1em; margin: 1.1em 0 0.4em; text-align: left; page-break-after: avoid; }

p { margin: 0 0 0.75em 0; text-indent: 0; }

/* ---------- 引用块：用来放"一句话总结""教学点" ---------- */
blockquote {
  margin: 1em 0;
  padding: 0.7em 0.85em;
  border-left: 4px solid #888;
  background: #f2f2f2;
  font-size: 0.94em;
  line-height: 1.62;
}
blockquote p { margin: 0 0 0.5em 0; }
blockquote p:last-child { margin-bottom: 0; }

/* ---------- 列表 ---------- */
ul, ol { margin: 0.5em 0 0.85em 1.25em; padding: 0; }
li { margin: 0.28em 0; line-height: 1.6; }
li > p { margin: 0.2em 0; }

/* ---------- 表格：小屏缩排，允许折行 ---------- */
table {
  border-collapse: collapse;
  width: 100%;
  margin: 0.9em 0 1.1em 0;
  font-size: 0.72em;
  line-height: 1.45;
}
th, td {
  border: 1px solid #8c8c8c;
  padding: 0.36em 0.3em;
  vertical-align: top;
  word-break: break-word;
  text-align: left;
}
th { background: #e6e6e6; font-weight: bold; }
tbody tr:nth-child(even) td { background: #f7f7f7; }

/* ---------- 图片 ---------- */
img { max-width: 100%; height: auto; display: block; margin: 0.9em auto; }

/* ---------- 其他 ---------- */
hr { border: 0; border-top: 1px solid #b5b5b5; margin: 1.4em 0; }
strong { font-weight: bold; }
em { font-style: italic; }
code {
  font-family: "SF Mono", Menlo, monospace;
  font-size: 0.88em;
  background: #efefef;
  padding: 0 0.15em;
}
a { color: #111; text-decoration: underline; }

.chapter-end {
  text-align: center;
  color: #999;
  font-size: 0.8em;
  margin: 2.2em 0 1em 0;
  letter-spacing: 0.4em;
}
"""

XHTML = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-CN" lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <title>{title}</title>
  <link rel="stylesheet" type="text/css" href="../style.css"/>
</head>
<body>
{body}
</body>
</html>
"""

COVER = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-CN" lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <title>{title}</title>
  <link rel="stylesheet" type="text/css" href="style.css"/>
</head>
<body>
  <div class="cover">
    <p class="kicker">{kicker}</p>
    <h1>{title}</h1>
    <p class="sub">{subtitle}</p>
    <hr class="rule"/>
    <p class="hint">{hint}</p>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------- 工具函数
def strip_md(text):
    """去掉行内 markdown 标记，只留纯文本（用于标题 / 元数据）。"""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = text.replace("\\", "")
    return text.strip(" 　\n")


def md2html(text):
    return markdown.markdown(
        text,
        extensions=["tables", "fenced_code", "sane_lists", "attr_list"],
        output_format="xhtml",
    )


def fix_void_tags(html):
    """markdown 可能输出 <img ...>，XHTML 必须自闭合。"""
    for tag in VOID_TAGS:
        html = re.sub(
            r"<%s(?=[\s/])([^>]*?)(?<!/)>" % tag, r"<%s\1/>" % tag, html
        )
    return html


def escape(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def embed_images(html, base_dir, img_dir):
    """把 md 里引用的本地图片复制进 EPUB，并改写为相对路径。"""
    found = set(re.findall(r'<img[^>]+src="([^"]+)"', html))
    for src in found:
        if re.match(r"^[a-z]+://", src):
            continue
        path = os.path.normpath(os.path.join(base_dir, src))
        if not os.path.exists(path):
            print(f"  ! 图片不存在，跳过：{src}")
            html = re.sub(r'<img[^>]*src="%s"[^>]*/>' % re.escape(src), "", html)
            continue
        # 约定：若存在同名 _portrait 变体，优先用它（墨水屏竖屏排版）
        root, ext = os.path.splitext(path)
        cand = root + "_portrait" + ext
        if os.path.exists(cand):
            path = cand
        name = os.path.basename(path)
        shutil.copy2(path, os.path.join(img_dir, name))
        html = html.replace('src="%s"' % src, 'src="../images/%s"' % name)
    return html


# ---------------------------------------------------------------- 主流程
def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    src = os.path.abspath(sys.argv[1])
    base_dir = os.path.dirname(src)
    stem = os.path.splitext(os.path.basename(src))[0]
    out = os.path.abspath(sys.argv[2]) if len(sys.argv) > 2 else os.path.join(base_dir, stem + ".epub")

    raw = open(src, encoding="utf-8").read().replace("\r\n", "\n")

    # --- 1. 拆出书名（第一个 # ）
    lines = raw.split("\n")
    book_title = ""
    body_start = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            book_title = strip_md(line[2:])
            body_start = i + 1
            break
    if not book_title:
        book_title = stem
    body = "\n".join(lines[body_start:])

    # --- 2. 按 `## ` 拆章
    parts = re.split(r"(?m)^##[ \t]+", body)
    intro_md = parts[0]
    sections = []
    for part in parts[1:]:
        first_nl = part.find("\n")
        if first_nl == -1:
            head, rest = part.strip(), ""
        else:
            head, rest = part[:first_nl].strip(), part[first_nl + 1:]
        sections.append((strip_md(head), rest))

    # --- 3. 准备临时目录
    build_root = os.path.join(base_dir, "build", "_epub")
    if os.path.isdir(build_root):
        shutil.rmtree(build_root)
    oebps = os.path.join(build_root, "OEBPS")
    text_dir = os.path.join(oebps, "text")
    img_dir = os.path.join(oebps, "images")
    os.makedirs(text_dir, exist_ok=True)
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(os.path.join(build_root, "META-INF"), exist_ok=True)

    with open(os.path.join(oebps, "style.css"), "w", encoding="utf-8") as f:
        f.write(CSS)

    modified = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    today = datetime.now().strftime("%Y-%m-%d")

    # --- 4. 封面
    subtitle = ""
    for line in intro_md.split("\n"):
        if "主题" in line and "｜" in line:
            subtitle = strip_md(line).replace("**", "")
            break
    if not subtitle:
        subtitle = today
    else:
        # 形如「2026年11月21日（周六）｜主题：xxx」→ 拆两行
        chunks = [c.strip() for c in subtitle.split("｜") if c.strip()]
        subtitle = "<br/>".join(escape(c) for c in chunks)

    hint = (
        "阅读提示<br/><br/>"
        "· 表格在小屏上会自动折行，横屏阅读更清楚<br/>"
        "· 「教学点」「一句话记住」都在灰底引用块里<br/>"
        "· 文末有数据来源与免责声明，请务必读完"
    )
    tp = [x.strip() for x in book_title.split("·") if x.strip()]
    kicker = tp[0] if len(tp) > 1 else "每日投资学习"
    main_title = tp[-1] if len(tp) > 1 else book_title
    cover_xhtml = COVER.format(
        kicker=escape(kicker),
        title=escape(main_title),
        subtitle=subtitle,
        hint=hint,
    )
    with open(os.path.join(oebps, "cover.xhtml"), "w", encoding="utf-8") as f:
        f.write(cover_xhtml)

    # --- 5. 章节
    manifest_items = [
        '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
        '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>',
        '<item id="css" href="style.css" media-type="text/css"/>',
        '<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>',
    ]
    spine = ['<itemref idref="cover"/>']
    nav_lis = []
    chapters = []  # (id, title, filename)

    def add_chapter(idx, title, md_text):
        cid = "ch%02d" % idx
        fname = "text/%s.xhtml" % cid
        html_body = fix_void_tags(md2html(md_text))
        html_body = embed_images(html_body, base_dir, img_dir)
        page = XHTML.format(title=escape(title), body=html_body)
        with open(os.path.join(oebps, fname), "w", encoding="utf-8") as f:
            f.write(page)
        manifest_items.append(
            '<item id="%s" href="%s" media-type="application/xhtml+xml"/>' % (cid, fname)
        )
        spine.append('<itemref idref="%s"/>' % cid)
        nav_lis.append('<li><a href="%s">%s</a></li>' % (fname, escape(title)))
        chapters.append((cid, title, fname))

    idx = 1
    if intro_md.strip(" \n-—"):
        add_chapter(idx, "本期导读", intro_md)
        idx += 1
    for title, rest in sections:
        add_chapter(idx, title or "（无标题）", rest)
        idx += 1

    # --- 6. nav / ncx
    nav = """<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="zh-CN" lang="zh-CN">
<head><meta charset="utf-8"/><title>目录</title>
<link rel="stylesheet" type="text/css" href="style.css"/></head>
<body>
<nav epub:type="toc" id="toc">
<h1>目录</h1>
<ol>
{items}
</ol>
</nav>
</body>
</html>
""".format(items="\n".join(nav_lis))
    with open(os.path.join(oebps, "nav.xhtml"), "w", encoding="utf-8") as f:
        f.write(nav)

    nav_points = []
    for i, (cid, title, fname) in enumerate(chapters, start=1):
        nav_points.append(
            """  <navPoint id="np%d" playOrder="%d">
    <navLabel><text>%s</text></navLabel>
    <content src="%s"/>
  </navPoint>"""
            % (i, i, escape(title), fname)
        )
    ncx = """<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1" xml:lang="zh-CN">
<head>
  <meta name="dtb:uid" content="urn:uuid:{uid}"/>
  <meta name="dtb:depth" content="1"/>
  <meta name="dtb:totalPageCount" content="0"/>
  <meta name="dtb:maxPageNumber" content="0"/>
</head>
<docTitle><text>{title}</text></docTitle>
<navMap>
{points}
</navMap>
</ncx>
""".format(uid=hashlib.md5((book_title + today).encode()).hexdigest(),
           title=escape(book_title),
           points="\n".join(nav_points))
    with open(os.path.join(oebps, "toc.ncx"), "w", encoding="utf-8") as f:
        f.write(ncx)

    # --- 7. 图片清单
    for name in sorted(os.listdir(img_dir)):
        manifest_items.append(
            '<item id="img_%s" href="images/%s" media-type="image/%s"/>'
            % (re.sub(r"\W", "_", os.path.splitext(name)[0]), name,
               "png" if name.lower().endswith("png") else "jpeg")
        )

    # --- 8. container.xml
    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    with open(os.path.join(build_root, "META-INF", "container.xml"), "w", encoding="utf-8") as f:
        f.write(container)

    # --- 9. content.opf
    uid = "urn:uuid:" + hashlib.md5((book_title + today + str(len(raw))).encode()).hexdigest()
    opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="bookid" xml:lang="zh-CN">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="bookid">{uid}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:creator>每日投资学习</dc:creator>
    <dc:language>zh-CN</dc:language>
    <dc:date>{date}</dc:date>
    <dc:publisher>DSH 投资学习计划</dc:publisher>
    <dc:description>关注纳指、标普500、美股科技/AI、红利低波100、黄金；渠道为支付宝场外基金。</dc:description>
    <meta property="dcterms:modified">{modified}</meta>
  </metadata>
  <manifest>
{manifest}
  </manifest>
  <spine toc="ncx">
{spine}
  </spine>
</package>
""".format(uid=uid, title=escape(book_title), date=today, modified=modified,
           manifest="\n    ".join(manifest_items), spine="\n    ".join(spine))
    with open(os.path.join(oebps, "content.opf"), "w", encoding="utf-8") as f:
        f.write(opf)

    # --- 10. 打包
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    if os.path.exists(out):
        os.remove(out)
    with zipfile.ZipFile(out, "w") as z:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        z.writestr(info, "application/epub+zip")
        for root, dirs, files in os.walk(build_root):
            for name in files:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, build_root)
                if rel == "mimetype":
                    continue
                z.write(full, rel, compress_type=zipfile.ZIP_DEFLATED)

    size_kb = os.path.getsize(out) / 1024
    print("✅ EPUB 已生成")
    print("   文件：%s" % out)
    print("   大小：%.1f KB" % size_kb)
    print("   书名：%s" % book_title)
    print("   章节：%d 章" % len(chapters))
    for cid, title, _ in chapters:
        print("     - %s" % title)


if __name__ == "__main__":
    main()
