#!/usr/bin/env python3
"""Convert a Markdown article to WeChat-compatible HTML and optionally create a draft.

Environment variables for publishing:
  WECHAT_MP_APPID
  WECHAT_MP_APPSECRET

Optional:
  WECHAT_MP_AUTHOR
  WECHAT_MP_SOURCE_URL

Usage:
  python scripts/wechat_publisher.py article.md --config assets/config.example.json
  python scripts/wechat_publisher.py article.md --config assets/config.example.json --publish
"""

from __future__ import annotations

import argparse
import html
import json
import mimetypes
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import requests
except Exception as exc:  # pragma: no cover
    raise SystemExit("Missing dependency: requests. Install with `python3 -m pip install requests`.") from exc

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None


DEFAULT_CONFIG: Dict[str, Any] = {
    "brand": "公众号名称",
    "author": "作者",
    "intro": "作者简介：用一句话建立信任。",
    "footer": "公众号名称｜一句话定位",
    "digest": "这篇文章的摘要。",
    "source_url": "",
    "accent": "#126BFF",
    "muted": "#8A94A6",
    "ink": "#273142",
    "soft_bg": "#FAFCFF",
    "cta": {
        "enabled": True,
        "follow_text": "如果你也关注这个主题，欢迎关注我。",
        "body": "后面我会持续分享系统方法和实操经验。",
        "reply_keyword": "资料",
        "gift_name": "资料包",
    },
}


def load_env(start: Path) -> None:
    for env_path in [start / ".env", Path.cwd() / ".env", Path(__file__).resolve().parent / ".env"]:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def load_config(path: Path | None) -> Dict[str, Any]:
    if not path:
        return dict(DEFAULT_CONFIG)
    data = json.loads(path.read_text(encoding="utf-8"))
    return deep_merge(DEFAULT_CONFIG, data)


def parse_frontmatter(text: str) -> Tuple[Dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    raw = text[4:end].strip()
    body = text[end + 4 :].lstrip("\n")
    meta: Dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, body


def slugify(value: str) -> str:
    value = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", value, flags=re.U).strip("-")
    return value[:80] or "wechat-article"


def inline_markdown(text: str, accent: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", rf'<span style="color:{accent};font-weight:700;">\1</span>', escaped)
    escaped = re.sub(r"`([^`]+)`", r'<code style="background:#F3F6FA;border-radius:4px;padding:1px 4px;color:#3D4856;">\1</code>', escaped)
    return escaped


def paragraph(text: str, cfg: Dict[str, Any]) -> str:
    return (
        f'<p style="margin:0 0 15px;color:{cfg["ink"]};font-size:16px;line-height:1.9;">'
        f'{inline_markdown(text, cfg["accent"])}</p>'
    )


def render_image(src: str, alt: str, caption: str, cfg: Dict[str, Any]) -> str:
    return (
        '<figure style="margin:24px 0 32px;text-align:center;">'
        f'<img src="{html.escape(src)}" alt="{html.escape(alt)}" '
        'style="display:block;width:100%;max-width:100%;height:auto;border-radius:14px;'
        'border:1px solid #E8EEF6;margin:0 auto;background:#fff;">'
        f'<figcaption style="margin-top:8px;text-align:center;color:{cfg["muted"]};font-size:12px;line-height:1.5;">'
        f'{html.escape(caption or alt)}</figcaption></figure>'
    )


def markdown_to_body(md: str, cfg: Dict[str, Any]) -> Tuple[str, str, List[str]]:
    meta, body = parse_frontmatter(md)
    lines = body.splitlines()
    title = meta.get("title", "")
    parts: List[str] = []
    images: List[str] = []
    list_buf: List[str] = []
    para_buf: List[str] = []

    def flush_para() -> None:
        nonlocal para_buf
        if para_buf:
            parts.append(paragraph(" ".join(x.strip() for x in para_buf), cfg))
            para_buf = []

    def flush_list() -> None:
        nonlocal list_buf
        if list_buf:
            items = "".join(
                f'<li style="margin:0 0 8px;color:{cfg["ink"]};font-size:15px;line-height:1.8;">'
                f'{inline_markdown(item, cfg["accent"])}</li>'
                for item in list_buf
            )
            parts.append(f'<ul style="margin:0 0 18px 20px;padding:0;">{items}</ul>')
            list_buf = []

    h2_count = 0
    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_para()
            flush_list()
            continue

        image_match = re.match(r"!\[(.*?)\]\((.*?)\)", line.strip())
        if image_match:
            flush_para()
            flush_list()
            alt, src = image_match.group(1), image_match.group(2)
            images.append(src)
            parts.append(render_image(src, alt, alt, cfg))
            continue

        if line.startswith("# "):
            flush_para()
            flush_list()
            title = title or line[2:].strip()
            continue
        if line.startswith("## "):
            flush_para()
            flush_list()
            h2_count += 1
            heading = line[3:].strip()
            parts.append(
                f'<h2 style="margin:36px 0 18px;color:#111827;font-size:21px;line-height:1.45;font-weight:800;">'
                f'<span style="display:inline-block;margin-right:9px;color:{cfg["accent"]};font-size:18px;">{h2_count:02d}</span>'
                f'{html.escape(heading)}</h2>'
            )
            continue
        if line.startswith("### "):
            flush_para()
            flush_list()
            parts.append(
                f'<h3 style="margin:28px 0 14px;color:#172033;font-size:18px;line-height:1.5;font-weight:800;">'
                f'{html.escape(line[4:].strip())}</h3>'
            )
            continue
        if line.strip() == "---":
            flush_para()
            flush_list()
            parts.append('<hr style="border:0;border-top:1px solid #EEF2F7;margin:28px 0;">')
            continue
        if line.startswith("> "):
            flush_para()
            flush_list()
            quote = inline_markdown(line[2:].strip(), cfg["accent"])
            parts.append(
                f'<section style="margin:22px 0 28px;padding:18px;border-radius:16px;'
                f'background:#F7FFFD;border:1px solid #CFEFEB;">'
                f'<p style="margin:0;color:#173B3A;font-size:17px;line-height:1.85;font-weight:700;">{quote}</p>'
                f'</section>'
            )
            continue
        if re.match(r"^\s*[-*]\s+", line):
            flush_para()
            list_buf.append(re.sub(r"^\s*[-*]\s+", "", line).strip())
            continue

        para_buf.append(line)

    flush_para()
    flush_list()
    title = meta.get("title") or title or "未命名文章"
    return title, "\n".join(parts), images


def build_html(md_path: Path, cfg: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    md = md_path.read_text(encoding="utf-8")
    meta, _ = parse_frontmatter(md)
    title, body_html, images = markdown_to_body(md, cfg)
    page_title = meta.get("title") or title
    author = meta.get("author") or cfg.get("author", "")
    digest = meta.get("digest") or cfg.get("digest", "")
    cover = meta.get("cover") or cfg.get("cover", "")
    intro = meta.get("intro") or cfg.get("intro", "")
    footer = meta.get("footer") or cfg.get("footer", "")
    cta = cfg.get("cta", {})

    intro_html = ""
    if intro:
        intro_html = (
            '<section style="margin:4px auto 24px;padding:10px 10px 12px;text-align:center;border-bottom:1px solid #EEF2F7;">'
            f'<p style="margin:0 0 7px;color:{cfg["muted"]};font-size:12px;line-height:1.6;letter-spacing:.08em;">'
            f'{html.escape(cfg.get("brand", ""))}</p>'
            f'<p style="margin:0 auto;color:#5D6675;font-size:13px;line-height:1.75;max-width:520px;">'
            f'{html.escape(intro)}</p></section>'
        )

    cta_html = ""
    if cta.get("enabled", True):
        cta_html = (
            '<section style="margin:30px 0 10px;padding:18px;border-radius:18px;background:#FAFCFF;border:1px solid #E6EDF7;">'
            f'<p style="margin:0 0 10px;color:#172033;font-size:16px;line-height:1.85;font-weight:700;">{html.escape(cta.get("follow_text", ""))}</p>'
            f'<p style="margin:0 0 10px;color:#3D4856;font-size:15px;line-height:1.85;">{html.escape(cta.get("body", ""))}</p>'
            f'<p style="margin:0;color:#3D4856;font-size:15px;line-height:1.85;">如果你想要我整理的实操资料，可以在后台回复：'
            f'<span style="color:{cfg["accent"]};font-weight:700;">{html.escape(cta.get("reply_keyword", "资料"))}</span>。</p>'
            '</section>'
        )

    footer_html = ""
    if footer:
        footer_html = (
            f'<p style="margin:20px 0 0;text-align:center;color:{cfg["muted"]};font-size:12px;'
            f'letter-spacing:.08em;line-height:1.6;">{html.escape(footer)}</p>'
        )

    article = f"{intro_html}\n{body_html}\n{cta_html}\n{footer_html}"
    doc = (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{html.escape(page_title)}</title></head>'
        '<body style="margin:0;background:#f6f8fb;color:#273142;'
        "font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',Arial,sans-serif;\">"
        '<main style="max-width:760px;margin:0 auto;background:#ffffff;padding:18px 16px 44px;">'
        '<article class="wechat-article" style="max-width:680px;margin:0 auto;color:#273142;line-height:1.86;font-size:16px;">'
        f"{article}</article></main></body></html>"
    )
    info = {
        "title": page_title,
        "author": author,
        "digest": digest,
        "cover": cover,
        "source_url": meta.get("source_url") or cfg.get("source_url", ""),
        "images": images,
    }
    return doc, info


def absolutize(src: str, base: Path) -> Path:
    if src.startswith("file://"):
        return Path(src[7:])
    path = Path(src)
    return path if path.is_absolute() else (base / path).resolve()


def compress_image(src: Path, max_bytes: int = 900_000) -> Path:
    if Image is None:
        return src
    img = Image.open(src).convert("RGB")
    tmp = Path(tempfile.mkdtemp(prefix="wximg_")) / (src.stem + ".jpg")
    width, height = img.size
    scale, quality = 1.0, 90
    while True:
        resized = img.resize((max(1, int(width * scale)), max(1, int(height * scale))))
        resized.save(tmp, format="JPEG", quality=quality, optimize=True, progressive=True)
        if tmp.stat().st_size <= max_bytes:
            return tmp
        if quality > 62:
            quality -= 8
        else:
            scale *= 0.88


def wx_json(resp: requests.Response) -> dict:
    try:
        data = resp.json()
    except Exception as exc:
        raise RuntimeError(f"WeChat returned non-JSON: HTTP {resp.status_code} {resp.text[:300]}") from exc
    if data.get("errcode") not in (None, 0):
        raise RuntimeError(json.dumps(data, ensure_ascii=False))
    return data


def get_token(appid: str, secret: str) -> str:
    data = wx_json(
        requests.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={"grant_type": "client_credential", "appid": appid, "secret": secret},
            timeout=60,
        )
    )
    return data["access_token"]


def upload_article_image(token: str, path: Path) -> str:
    upload = compress_image(path)
    mime = mimetypes.guess_type(str(upload))[0] or "image/jpeg"
    with upload.open("rb") as f:
        data = wx_json(
            requests.post(
                "https://api.weixin.qq.com/cgi-bin/media/uploadimg",
                params={"access_token": token},
                files={"media": (upload.name, f, mime)},
                timeout=60,
            )
        )
    return data["url"]


def upload_cover(token: str, path: Path) -> str:
    upload = compress_image(path, max_bytes=1_800_000)
    mime = mimetypes.guess_type(str(upload))[0] or "image/jpeg"
    with upload.open("rb") as f:
        data = wx_json(
            requests.post(
                "https://api.weixin.qq.com/cgi-bin/material/add_material",
                params={"access_token": token, "type": "image"},
                files={"media": (upload.name, f, mime)},
                timeout=60,
            )
        )
    return data["media_id"]


def replace_image_srcs(doc: str, image_map: Dict[str, str]) -> str:
    for old, new in sorted(image_map.items(), key=lambda item: len(item[0]), reverse=True):
        doc = doc.replace(f'src="{html.escape(old)}"', f'src="{new}"')
        doc = doc.replace(f"src=\"{old}\"", f'src="{new}"')
    return doc


def create_draft(token: str, info: Dict[str, Any], content: str, thumb_media_id: str) -> str:
    payload = {
        "articles": [
            {
                "title": str(info["title"])[:64],
                "author": str(info.get("author") or "")[:8],
                "digest": str(info.get("digest") or "")[:120],
                "content": content,
                "content_source_url": str(info.get("source_url") or ""),
                "thumb_media_id": thumb_media_id,
                "need_open_comment": 0,
                "only_fans_can_comment": 0,
            }
        ]
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    data = wx_json(
        requests.post(
            "https://api.weixin.qq.com/cgi-bin/draft/add",
            params={"access_token": token},
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=60,
        )
    )
    return data["media_id"]


def publish_to_draft(md_path: Path, html_doc: str, info: Dict[str, Any], out_dir: Path) -> Dict[str, Any]:
    load_env(md_path.parent)
    appid = os.environ.get("WECHAT_MP_APPID", "").strip()
    secret = os.environ.get("WECHAT_MP_APPSECRET", "").strip()
    if not appid or not secret:
        raise SystemExit("Missing WECHAT_MP_APPID/WECHAT_MP_APPSECRET. Put them in .env or environment variables.")

    token = get_token(appid, secret)
    base = md_path.parent
    image_map: Dict[str, str] = {}
    for src in info["images"]:
        path = absolutize(src, base)
        if not path.exists():
            raise FileNotFoundError(f"Article image not found: {src}")
        image_map[src] = upload_article_image(token, path)

    cover_src = info.get("cover") or (info["images"][0] if info["images"] else "")
    if not cover_src:
        raise SystemExit("No cover image found. Add `cover: path/to/cover.png` to Markdown frontmatter or include an image.")
    cover_path = absolutize(str(cover_src), base)
    if not cover_path.exists():
        raise FileNotFoundError(f"Cover image not found: {cover_src}")
    thumb_media_id = upload_cover(token, cover_path)

    content = replace_image_srcs(html_doc, image_map)
    # Only send the article body to WeChat.
    m = re.search(r'(<article class="wechat-article".*?</article>)', content, flags=re.S)
    content = m.group(1) if m else content
    draft_media_id = create_draft(token, info, content, thumb_media_id)
    return {
        "ok": True,
        "title": info["title"],
        "draft_media_id": draft_media_id,
        "thumb_media_id": thumb_media_id,
        "uploaded_article_images": len(image_map),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("markdown", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--publish", action="store_true", help="Create a WeChat Official Account draft.")
    args = parser.parse_args()

    md_path = args.markdown.resolve()
    if not md_path.exists():
        raise SystemExit(f"Markdown not found: {md_path}")
    cfg = load_config(args.config.resolve() if args.config else None)
    out_dir = (args.out_dir or (md_path.parent / "wechat-output")).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    html_doc, info = build_html(md_path, cfg)
    html_path = out_dir / f"{slugify(info['title'])}.html"
    html_path.write_text(html_doc, encoding="utf-8")
    result: Dict[str, Any] = {"ok": True, "html": str(html_path), "title": info["title"], "images": len(info["images"])}
    if args.publish:
        result["draft"] = publish_to_draft(md_path, html_doc, info, out_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
