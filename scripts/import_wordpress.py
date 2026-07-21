#!/usr/bin/env python3
"""Import a WordPress WXR export into Hugo content files.

The importer keeps WordPress archive IDs as canonical URLs, stores old
comments in data/comments.json, and leaves HTML content intact so Gutenberg
blocks, tables, images, and legacy markup render as close as possible.
"""

from __future__ import annotations

import argparse
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
XML = ROOT / "wordpress-export.xml"
NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
    "wp": "http://wordpress.org/export/1.2/",
}
TZ = timezone(timedelta(hours=8))


def text(node: ET.Element | None, default: str = "") -> str:
    return (node.text or default) if node is not None else default


def child(node: ET.Element, path: str) -> str:
    return text(node.find(path, NS))


def toml_string(value: str) -> str:
    return json.dumps(value or "", ensure_ascii=False)


def toml_array(values: list[str]) -> str:
    return "[" + ", ".join(toml_string(v) for v in values if v) + "]"


def filename(value: str, fallback: str = "untitled") -> str:
    value = unquote(value).strip().lower()
    value = re.sub(r"[^0-9a-zA-Z._-]+", "-", value).strip("-._")
    return value or fallback


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
    value = value or ""
    value = re.sub(r"<!--\s*/?wp:[^>]*-->", "", value)
    value = value.replace("\r\n", "\n")
    return value.strip() + "\n"


def clean_comment(value: str) -> str:
    value = re.sub(r"<br\s*/?>|</p\s*>", "\n", value or "", flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    return html.unescape(value).strip()


def avatar_for(email: str) -> str:
    digest = hashlib.md5((email or "").strip().lower().encode(), usedforsecurity=False).hexdigest()
    return f"https://cn.gravatar.com/avatar/{digest}?s=50&r=g"


def collect_comments(item: ET.Element) -> list[dict[str, str]]:
    comments: list[dict[str, str]] = []
    for comment in item.findall("wp:comment", NS):
        if child(comment, "wp:comment_approved") not in {"1", "approve"}:
            continue
        ctype = child(comment, "wp:comment_type")
        if ctype not in {"", "comment"}:
            continue
        content = clean_comment(child(comment, "wp:comment_content"))
        comments.append(
            {
                "author": child(comment, "wp:comment_author") or "匿名",
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


def remove_path(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def replace_transactionally(replacements: list[tuple[Path, Path]], backup: Path) -> None:
    if backup.exists():
        raise RuntimeError(f"recovery backup already exists: {backup}; restore or remove it before importing")
    backup.mkdir(parents=True)
    backed_up: list[tuple[Path, Path]] = []
    installed: list[Path] = []
    keep_backup = False
    try:
        for _, target in replacements:
            if not target.exists():
                continue
            backup_path = backup / target.relative_to(ROOT)
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(target), str(backup_path))
            backed_up.append((target, backup_path))

        for source, target in replacements:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source), str(target))
            installed.append(target)
    except Exception as install_error:
        rollback_errors: list[str] = []
        for target in reversed(installed):
            try:
                remove_path(target)
            except Exception as exc:
                rollback_errors.append(f"remove {target}: {exc}")
        for target, backup_path in reversed(backed_up):
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(backup_path), str(target))
            except Exception as exc:
                rollback_errors.append(f"restore {target}: {exc}")
        if rollback_errors:
            keep_backup = True
            raise RuntimeError("import failed and rollback was incomplete: " + "; ".join(rollback_errors)) from install_error
        raise
    finally:
        if not keep_backup:
            shutil.rmtree(backup, ignore_errors=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import a WordPress WXR export into Hugo.")
    parser.add_argument("xml", nargs="?", type=Path, default=XML)
    parser.add_argument("--replace-existing", action="store_true", help="replace existing content/posts and content/page after a successful import")
    parser.add_argument("--allow-empty", action="store_true", help="allow an export with no published posts or pages")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    xml_path = args.xml.resolve()
    if not xml_path.exists():
        print(f"missing export: {xml_path}", file=sys.stderr)
        return 1

    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as exc:
        print(f"invalid WXR XML: {exc}", file=sys.stderr)
        return 1
    channel = tree.getroot().find("channel")
    if channel is None:
        print("invalid WXR export", file=sys.stderr)
        return 1

    target_posts = ROOT / "content" / "posts"
    target_pages = ROOT / "content" / "page"
    if not args.replace_existing and any(path.exists() and any(path.iterdir()) for path in (target_posts, target_pages)):
        print("refusing to replace existing content; rerun with --replace-existing", file=sys.stderr)
        return 1
    staging = ROOT / ".wordpress-import-staging"
    backup = ROOT / ".wordpress-import-backup"
    if backup.exists():
        print(f"refusing import because a recovery backup exists: {backup}", file=sys.stderr)
        return 1
    shutil.rmtree(staging, ignore_errors=True)
    try:
        posts_dir = staging / "posts"
        pages_dir = staging / "page"
        data_dir = staging / "data"
        posts_dir.mkdir(parents=True)
        pages_dir.mkdir(parents=True)
        data_dir.mkdir(parents=True, exist_ok=True)

        items = channel.findall("item")
        attachments: dict[str, str] = {}
        for item in items:
            if child(item, "wp:post_type") == "attachment":
                attachments[child(item, "wp:post_id")] = child(item, "wp:attachment_url")

        comments_data: dict[str, list[dict[str, str]]] = {}
        generated_paths: set[Path] = set()
        imported_posts = imported_pages = 0

        for item in items:
            post_type = child(item, "wp:post_type")
            status = child(item, "wp:status")
            if post_type not in {"post", "page"} or status != "publish":
                continue

            post_id = child(item, "wp:post_id")
            if not post_id.isdigit() or int(post_id) <= 0:
                print(f"invalid WordPress post ID for published {post_type}: {post_id or '(missing)'}", file=sys.stderr)
                return 1
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
                page_slug = filename(slug, f"untitled-{post_id or '0'}")
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

            if path in generated_paths:
                print(f"duplicate generated path: {path.relative_to(staging)}", file=sys.stderr)
                return 1
            generated_paths.add(path)
            write_file(path, frontmatter(fields) + content)

        if imported_posts + imported_pages == 0 and not args.allow_empty:
            print("refusing empty import; no published posts or pages found (use --allow-empty to override)", file=sys.stderr)
            return 1

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
                frontmatter({"title": "网站地图", "date": "1970-01-01T00:00:00+08:00", "draft": False, "type": "page", "url": "/ditu/", "layout": "ditu"}),
            )

        staged_comments = data_dir / "comments.json"
        write_file(staged_comments, json.dumps(comments_data, ensure_ascii=False, indent=2))
        replacements = [
            (posts_dir, target_posts),
            (pages_dir, target_pages),
            (staged_comments, ROOT / "data" / "comments.json"),
        ]
        try:
            replace_transactionally(replacements, backup)
        except Exception as exc:
            print(f"failed to install import: {exc}", file=sys.stderr)
            return 1

        print(f"Imported {imported_posts} posts and {imported_pages} pages")
        return 0
    finally:
        shutil.rmtree(staging, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
