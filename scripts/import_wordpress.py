#!/usr/bin/env python3
"""Import a WordPress WXR export into Hugo content files.

The importer keeps WordPress archive IDs as canonical URLs, stores old
comments in data/comments.json, and leaves HTML content intact so Gutenberg
blocks, tables, images, and legacy markup render as close as possible.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
XML = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "wordpress-export.xml"
NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
    "wp": "http://wordpress.org/export/1.2/",
}
TZ = timezone(timedelta(hours=8))


def text(node: ET.Element | None, default: str = "") -> str:
    return html.unescape(node.text or default) if node is not None else default


def child(node: ET.Element, path: str) -> str:
    return text(node.find(path, NS))


def toml_string(value: str) -> str:
    return json.dumps(value or "", ensure_ascii=False)


def toml_array(values: list[str]) -> str:
    return "[" + ", ".join(toml_string(v) for v in values if v) + "]"


def filename(value: str) -> str:
    value = unquote(value).strip().lower()
    value = re.sub(r"[^0-9a-zA-Z._-]+", "-", value).strip("-._")
    return value or "untitled"


def parse_date(value: str) -> str:
    value = value.strip()
    if not value or value.startswith("0000-00-00"):
        return "1970-01-01T00:00:00+08:00"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            dt = datetime.strptime(value, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=TZ)
            return dt.isoformat()
        except ValueError:
            pass
    return value


def postmeta(item: ET.Element) -> dict[str, str]:
    meta: dict[str, str] = {}
    for postmeta_node in item.findall("wp:postmeta", NS):
        key = child(postmeta_node, "wp:meta_key")
        val = child(postmeta_node, "wp:meta_value")
        if key:
            meta[key] = val
    return meta


def taxonomies(item: ET.Element, domain: str) -> list[str]:
    values: list[str] = []
    for node in item.findall("category"):
        if node.attrib.get("domain") == domain and (node.text or "").strip():
            values.append(html.unescape(node.text or ""))
    return values


def clean_content(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<!--\s*/?wp:[^>]*-->", "", value)
    value = value.replace("\r\n", "\n")
    return value.strip() + "\n"


def avatar_for(email: str) -> str:
    digest = hashlib.sha256((email or "").strip().lower().encode()).hexdigest()
    return f"https://cn.gravatar.com/avatar/{digest}?s=50&r=g"


def collect_comments(item: ET.Element) -> list[dict[str, str]]:
    comments: list[dict[str, str]] = []
    for comment in item.findall("wp:comment", NS):
        if child(comment, "wp:comment_approved") not in {"1", "approve"}:
            continue
        ctype = child(comment, "wp:comment_type")
        if ctype not in {"", "comment"}:
            continue
        content = clean_content(child(comment, "wp:comment_content"))
        comments.append(
            {
                "author": child(comment, "wp:comment_author") or "匿名",
                "email": child(comment, "wp:comment_author_email"),
                "url": child(comment, "wp:comment_author_url"),
                "date": child(comment, "wp:comment_date") or child(comment, "wp:comment_date_gmt"),
                "content": content,
                "avatar": avatar_for(child(comment, "wp:comment_author_email")),
            }
        )
    return comments


def frontmatter(fields: dict[str, object]) -> str:
    lines = ["+++"]
    for key, value in fields.items():
        if isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, int):
            lines.append(f"{key} = {value}")
        elif isinstance(value, list):
            lines.append(f"{key} = {toml_array([str(v) for v in value])}")
        else:
            lines.append(f"{key} = {toml_string(str(value))}")
    lines.append("+++")
    return "\n".join(lines) + "\n\n"


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    if not XML.exists():
        print(f"missing export: {XML}", file=sys.stderr)
        return 1

    tree = ET.parse(XML)
    channel = tree.getroot().find("channel")
    if channel is None:
        print("invalid WXR export", file=sys.stderr)
        return 1

    posts_dir = ROOT / "content" / "posts"
    pages_dir = ROOT / "content" / "page"
    data_dir = ROOT / "data"
    if posts_dir.exists():
        shutil.rmtree(posts_dir)
    if pages_dir.exists():
        shutil.rmtree(pages_dir)
    posts_dir.mkdir(parents=True)
    pages_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    items = channel.findall("item")
    attachments: dict[str, str] = {}
    for item in items:
        if child(item, "wp:post_type") == "attachment":
            attachments[child(item, "wp:post_id")] = child(item, "wp:attachment_url")

    comments_data: dict[str, list[dict[str, str]]] = {}
    imported_posts = imported_pages = 0

    for item in items:
        post_type = child(item, "wp:post_type")
        status = child(item, "wp:status")
        if post_type not in {"post", "page"} or status != "publish":
            continue

        post_id = child(item, "wp:post_id")
        title = child(item, "title") or f"Untitled {post_id}"
        slug = child(item, "wp:post_name") or post_id
        date = parse_date(child(item, "wp:post_date") or child(item, "pubDate"))
        meta = postmeta(item)
        categories = taxonomies(item, "category")
        tags = taxonomies(item, "post_tag")
        comments = collect_comments(item)
        comments_data[post_id] = comments
        content = clean_content(child(item, "content:encoded"))
        excerpt = clean_content(child(item, "excerpt:encoded"))
        thumbnail = attachments.get(meta.get("_thumbnail_id", ""), "")

        if post_type == "post":
            fields = {
                "title": title,
                "date": date,
                "draft": False,
                "type": "posts",
                "url": f"/archives/{post_id}/",
                "slug": post_id,
                "wp_id": int(post_id or 0),
                "author": child(item, "dc:creator") or "wordpress",
                "categories": categories,
                "tags": tags,
                "featured_image": thumbnail,
                "views": int(meta.get("views", "0") or 0),
                "comment_count": len(comments),
                "excerpt": excerpt,
            }
            path = posts_dir / f"{post_id}-{filename(slug)}.md"
            imported_posts += 1
        else:
            page_slug = filename(slug)
            url_slug = {
                "i-m-%e8%93%9d%e8%89%b2peach": "about",
                "i-m-peach": "about",
                "im-peach": "about",
            }.get(page_slug, page_slug)
            fields = {
                "title": title,
                "date": date,
                "draft": False,
                "type": "page",
                "url": f"/{url_slug}/",
                "slug": url_slug,
                "wp_id": int(post_id or 0),
                "comment_count": len(comments),
            }
            if url_slug == "archives":
                fields["layout"] = "archives"
                content = ""
            path = pages_dir / f"{url_slug}.md"
            imported_pages += 1

        write_file(path, frontmatter(fields) + content)

    # Ensure core utility pages exist even if the WordPress export did not include them.
    archive_path = pages_dir / "archives.md"
    if not archive_path.exists():
        write_file(
            archive_path,
            frontmatter({"title": "归档", "date": "1970-01-01T00:00:00+08:00", "draft": False, "type": "page", "url": "/archives/", "layout": "archives"}),
        )

    sitemap_path = pages_dir / "ditu.md"
    if not sitemap_path.exists():
        write_file(
            sitemap_path,
            frontmatter({"title": "网站地图", "date": "1970-01-01T00:00:00+08:00", "draft": False, "type": "page", "url": "/ditu/"})
            + "<ul>\n<li><a href=\"/archives/\">文章归档</a></li>\n<li><a href=\"/index.xml\">RSS</a></li>\n<li><a href=\"/sitemap.xml\">Sitemap XML</a></li>\n</ul>\n",
        )

    write_file(data_dir / "comments.json", json.dumps(comments_data, ensure_ascii=False, indent=2))
    print(f"Imported {imported_posts} posts and {imported_pages} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
