# WeChat Draft Publisher Skill

Turn a Markdown article into a WeChat Official Account draft.

This kit contains a reusable Codex Skill plus a Python publishing script. It is designed for creators, consultants, educators, and teams who want a repeatable workflow:

```text
Markdown article → WeChat-style HTML preview → image upload → WeChat draft box
```

## What it supports

- Convert Markdown to WeChat-compatible inline-style HTML
- Apply configurable account branding, intro, footer, colors, and CTA
- Insert local images from Markdown image links
- Upload article images to WeChat
- Upload cover image as WeChat permanent material
- Create a WeChat Official Account draft through the official API
- Keep secrets in local `.env`, not in the Skill or repository

## Install into Codex

Copy the skill folder into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
cp -R skill/wechat-draft-publisher ~/.codex/skills/
```

Restart Codex or open a new task so the skill list refreshes.

## Configure

Copy the config template:

```bash
cp skill/wechat-draft-publisher/assets/config.example.json my-config.json
```

Edit:

- `brand`
- `author`
- `intro`
- `footer`
- `accent`
- `cta.reply_keyword`
- `cta.gift_name`

Create a local `.env` file. Do not commit it.

```bash
cp .env.example .env
```

Fill in:

```bash
WECHAT_MP_APPID=your_app_id
WECHAT_MP_APPSECRET=your_app_secret
```

Your WeChat Official Account backend must whitelist the current outbound IP.

## Markdown frontmatter

```markdown
---
title: 播放量不等于订单：跨境卖家必须重新理解流量
author: 明鉴
digest: 播放高不等于有订单。真正的流量，是合适的人沿路径走向真实行动。
cover: images/cover.png
source_url:
---
```

## Generate HTML preview

```bash
python3 skill/wechat-draft-publisher/scripts/wechat_publisher.py article.md \
  --config my-config.json
```

## Publish to WeChat draft box

```bash
python3 skill/wechat-draft-publisher/scripts/wechat_publisher.py article.md \
  --config my-config.json \
  --publish
```

The script prints a JSON result with `draft_media_id`.

## Notes

- The script intentionally uses inline styles because WeChat drafts do not reliably preserve local CSS.
- If Pillow is installed, images are compressed before upload. Without Pillow, the original image is uploaded.
- For public-facing articles, avoid exposing unregistered project names, book titles, trademarks, or method names.

