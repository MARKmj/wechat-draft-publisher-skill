---
name: wechat-draft-publisher
description: Create WeChat Official Account article drafts from Markdown files. Use when the user asks to turn a .md article into a WeChat/微信公众号 draft, generate WeChat-compatible HTML, apply a configurable account style, include local images, or publish to the WeChat draft box through the Official Account API.
---

# WeChat Draft Publisher

Use this skill to convert a Markdown article into a WeChat-compatible article and optionally create a draft through the WeChat Official Account API.

## Workflow

1. Read the input Markdown.
2. If the article needs images, create or collect local image files first, then insert them as Markdown image links.
3. Create or update a JSON config from `assets/config.example.json`.
4. Run `scripts/wechat_publisher.py` to generate a local HTML preview.
5. If credentials are available and the user asked to publish to draft, run the script with `--publish`.
6. Report the local HTML path and the returned `draft_media_id`.

## Markdown contract

Use optional frontmatter:

```markdown
---
title: 播放量不等于订单：跨境卖家必须重新理解流量
author: 明鉴
digest: 播放高不等于有订单。真正的流量，是合适的人沿路径走向真实行动。
cover: images/cover.png
source_url:
---
```

Supported Markdown:

- `#` title, `##` and `###` headings
- paragraphs
- `> quote` highlight cards
- `-` or `*` bullet lists
- `![caption](relative/or/absolute/path.png)` images
- `**emphasis**` blue emphasis
- horizontal rule `---`

## Publishing command

Generate local HTML only:

```bash
python3 scripts/wechat_publisher.py /path/to/article.md --config /path/to/config.json
```

Create a WeChat draft:

```bash
python3 scripts/wechat_publisher.py /path/to/article.md --config /path/to/config.json --publish
```

The script prints JSON containing the HTML path and, after publishing, `draft_media_id`.

## Credentials

Never put secrets in the skill or a public repo. Use environment variables or a local `.env` file beside the Markdown, in the current directory, or beside the script:

```bash
WECHAT_MP_APPID=...
WECHAT_MP_APPSECRET=...
```

The WeChat Official Account IP whitelist must include the current outbound IP. If WeChat returns an IP whitelist error, show the returned IP and ask the user to add it in the WeChat backend.

## Image guidance

Before publishing, verify all images exist locally. If the user wants AI-generated images, generate them first and save them into an `images/` directory beside the Markdown. Then insert Markdown image links in the article.

Prefer images that clarify a concept: cover, model diagram, comparison diagram, process diagram, and closing quote image. Avoid decorative images that do not improve comprehension.

## Style customization

Use `assets/config.example.json` as the starting point. Users can customize:

- account name and author
- intro and footer
- accent colors
- CTA text
- reply keyword and gift name
- digest/source URL

Do not hard-code personal branding into the universal skill. Put personal style in config.
