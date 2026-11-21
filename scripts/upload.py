"""坚果云 WebDAV 投递。

只用标准 WebDAV：MKCOL 建目录，PUT 传文件。坚果云对个人免费账号友好，
每天几次请求远低于它的频率限制。
"""
from __future__ import annotations

import os
from pathlib import Path

import requests

from config import JGY_BASE, JGY_DIR, JGY_PASS, JGY_USER

TIMEOUT = 60


def _auth():
    if not JGY_USER or not JGY_PASS:
        raise RuntimeError("缺少 JGY_USER / JGY_PASS（坚果云账号 + 应用密码）")
    return (JGY_USER, JGY_PASS)


def _url(*parts):
    path = "/".join(str(p).strip("/") for p in parts if p not in (None, ""))
    base = JGY_BASE.rstrip("/")
    return f"{base}/{path}"


def ensure_dir(*parts):
    """逐级 MKCOL，已存在（405）视为成功。"""
    segs = [p for p in parts if p]
    for i in range(1, len(segs) + 1):
        url = _url(*segs[:i])
        try:
            r = requests.request("MKCOL", url, auth=_auth(), timeout=TIMEOUT)
        except Exception:
            continue
        if r.status_code not in (200, 201, 204, 301, 405):
            # 坚果云对已存在目录返回 405，其他错误不阻断（PUT 还会再试一次）
            pass


def put_file(local_path, *remote_parts):
    local = Path(local_path)
    url = _url(*remote_parts)
    with local.open("rb") as fh:
        r = requests.put(url, data=fh, auth=_auth(), timeout=TIMEOUT)
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f"上传失败 {r.status_code}: {url} -> {r.text[:200]}")
    return url


def upload(epub_path, date_str):
    """上传到 <JGY_DIR>/<YYYY-MM>/<date>.epub，并刷新一份 <JGY_DIR>/最新一期.epub。"""
    month = date_str[:7]
    ensure_dir(JGY_DIR, month)
    urls = [put_file(epub_path, JGY_DIR, month, f"{date_str}.epub")]
    try:
        ensure_dir(JGY_DIR)
        urls.append(put_file(epub_path, JGY_DIR, "最新一期.epub"))
    except Exception:
        pass
    return urls


def self_check():
    """检查账号是否可用：列一下根目录。"""
    r = requests.request(
        "PROPFIND", _url(JGY_DIR) if JGY_DIR else JGY_BASE,
        auth=_auth(), timeout=TIMEOUT,
        headers={"Depth": "0"},
    )
    return r.status_code
