#!/usr/bin/env python3
"""Sync published WordPress REST API posts into Hugo content files.

The script is designed for cron/systemd timers: it stores the newest seen
WordPress modified timestamp in .wordpress-sync-state.json and only asks for
newer posts on the next run.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, TextIO

try:
    import fcntl
except ImportError:  # pragma: no cover - unavailable on Windows
    fcntl = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = ROOT / ".wordpress-sync-state.json"
DEFAULT_CONTENT_DIR = ROOT / "content" / "posts"
USER_AGENT = "hugo-akina-starter-wordpress-sync/1.0"
WP_ID_RE = re.compile(r"(?m)^wp_id\s*(?:=|:)\s*[\"']?(\d+)[\"']?\s*$")
COMMENT_COUNT_RE = re.compile(r"(?m)^comment_count\s*(?:=|:)\s*[\"']?(\d+)[\"']?\s*$")
VIEWS_RE = re.compile(r"(?m)^views\s*(?:=|:)\s*[\"']?(\d+)[\"']?\s*$")
PRUNE_MAX_FRACTION = 0.25


def env_first(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def clean_site_url(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        raise RuntimeError("missing WordPress site URL; set WORDPRESS_URL or pass --site-url")
    if not value.startswith(("http://", "https://")):
        value = "https://" + value
    return value


def parse_timezone(value: str) -> timezone:
    value = value.strip().upper()
    if value in {"Z", "UTC", "+00:00", "+0000"}:
        return timezone.utc
    match = re.fullmatch(r"([+-])(\d{2}):?(\d{2})", value)
    if not match:
        raise RuntimeError(f"invalid timezone {value!r}; use a value like +08:00")
    sign, hours, minutes = match.groups()
    if int(hours) > 23 or int(minutes) > 59:
        raise RuntimeError(f"invalid timezone {value!r}; use a value like +08:00")
    delta = timedelta(hours=int(hours), minutes=int(minutes))
    if sign == "-":
        delta = -delta
    return timezone(delta)


def auth_header(username: str, password: str) -> str:
    if not username or not password:
        return ""
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def api_url(site_url: str, path: str, params: dict[str, str] | None = None) -> str:
    url = f"{site_url}/wp-json/wp/v2/{path.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    return url


def fetch_json(url: str, auth: str) -> tuple[Any, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    if auth:
        request.add_header("Authorization", auth)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(charset)
            return json.loads(body), response.headers
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"WordPress API HTTP {exc.code} for {url}: {body[:400]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"WordPress API request failed for {url}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"WordPress API returned invalid JSON for {url}") from exc


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"posts": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid state file: {path}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid state file: {path}")
    posts = data.setdefault("posts", {})
    if not isinstance(posts, dict):
        raise RuntimeError(f"invalid posts data in state file: {path}")
    if "modified_cursors" in data and not isinstance(data["modified_cursors"], dict):
        raise RuntimeError(f"invalid modified_cursors data in state file: {path}")
    if "pending_postprocess" in data and not isinstance(data["pending_postprocess"], list):
        raise RuntimeError(f"invalid pending_postprocess data in state file: {path}")
    return data


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_text_atomic(path, json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_text_atomic(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(value, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def display_path(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def document_frontmatter(document: str) -> str:
    if document.startswith("+++\n"):
        end = document.find("\n+++", 4)
        return document[: end + 4] if end >= 0 else ""
    if document.startswith("---\n"):
        end = document.find("\n---", 4)
        return document[: end + 4] if end >= 0 else ""
    return ""


def rendered(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("rendered", "")
    return str(value or "")


def strip_markup(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value or "")
    value = html.unescape(value)
    return re.sub(r"\s+", " ", value).strip()


def clean_content(value: str) -> str:
    value = re.sub(r"<!--\s*/?wp:[^>]*-->", "", value or "")
    value = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    return value + "\n" if value else ""


def toml_string(value: str) -> str:
    return json.dumps(value or "", ensure_ascii=False)


def toml_array(values: list[str]) -> str:
    return "[" + ", ".join(toml_string(value) for value in values if value) + "]"


def frontmatter(fields: dict[str, Any]) -> str:
    lines = ["+++"]
    for key, value in fields.items():
        if isinstance(value, bool):
            lines.append(f"{key} = {str(value).lower()}")
        elif isinstance(value, int):
            lines.append(f"{key} = {value}")
        elif isinstance(value, list):
            lines.append(f"{key} = {toml_array([str(item) for item in value])}")
        else:
            lines.append(f"{key} = {toml_string(str(value or ''))}")
    lines.append("+++")
    return "\n".join(lines) + "\n\n"


def format_wp_date(value: str, fallback_tz: timezone) -> str:
    value = (value or "").strip()
    if not value or value.startswith("0000-00-00"):
        return datetime(1970, 1, 1, tzinfo=fallback_tz).isoformat()
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError:
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=fallback_tz)
    return dt.isoformat()


def modified_gmt(post: dict[str, Any]) -> str:
    value = str(post.get("modified_gmt") or post.get("modified") or "").strip()
    if not value:
        return ""
    if value.endswith("Z") or re.search(r"[+-]\d{2}:?\d{2}$", value):
        return value
    return value + "Z"


def modified_after_value(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError:
        return value
    dt = dt - timedelta(seconds=1)
    result = dt.isoformat()
    return result.replace("+00:00", "Z")


def post_terms(post: dict[str, Any], taxonomy: str) -> list[str]:
    result: list[str] = []
    embedded = post.get("_embedded", {})
    groups = embedded.get("wp:term", []) if isinstance(embedded, dict) else []
    for group in groups:
        if not isinstance(group, list):
            continue
        for term in group:
            if not isinstance(term, dict) or term.get("taxonomy") != taxonomy:
                continue
            name = strip_markup(str(term.get("name") or ""))
            if name and name not in result:
                result.append(name)
    return result


def featured_image(post: dict[str, Any]) -> str:
    embedded = post.get("_embedded", {})
    media_items = embedded.get("wp:featuredmedia", []) if isinstance(embedded, dict) else []
    if not media_items or not isinstance(media_items[0], dict):
        return ""
    media = media_items[0]
    return str(media.get("source_url") or "")


def author_name(post: dict[str, Any]) -> str:
    embedded = post.get("_embedded", {})
    authors = embedded.get("author", []) if isinstance(embedded, dict) else []
    if authors and isinstance(authors[0], dict):
        return strip_markup(str(authors[0].get("name") or ""))
    return "wordpress"


def extract_views(post: dict[str, Any]) -> int | None:
    meta = post.get("meta", {})
    if not isinstance(meta, dict):
        return None
    for key in ("views", "post_views_count", "post_views", "view_count"):
        value = meta.get(key)
        if isinstance(value, list):
            value = value[0] if value else 0
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            continue
    return None


def post_url(post: dict[str, Any], mode: str) -> str:
    post_id = str(post.get("id") or "")
    slug = str(post.get("slug") or post_id)
    if mode == "id":
        return f"/archives/{post_id}/"
    if mode == "slug":
        return ""
    link = str(post.get("link") or "")
    if link:
        path = urllib.parse.urlparse(link).path
        if not path or path == "/":
            return f"/archives/{post_id}/"
        path = "/" + path.lstrip("/")
        return path if path.endswith("/") else path + "/"
    return f"/archives/{post_id}/"


def existing_post_paths(content_dir: Path) -> dict[int, Path]:
    result: dict[int, Path] = {}
    if not content_dir.exists():
        return result
    for path in sorted(content_dir.rglob("*.md")):
        match = WP_ID_RE.search(document_frontmatter(path.read_text(encoding="utf-8")))
        if not match:
            continue
        post_id = int(match.group(1))
        previous = result.get(post_id)
        if previous and previous != path:
            raise RuntimeError(f"duplicate wp_id {post_id} in {display_path(previous)} and {display_path(path)}")
        result[post_id] = path
    return result


def post_path(content_dir: Path, post: dict[str, Any], existing: dict[int, Path]) -> Path:
    numeric_id = int(post.get("id") or 0)
    if numeric_id in existing:
        return existing[numeric_id]
    post_id = str(post.get("id") or "untitled")
    return content_dir / f"wp-{post_id}.md"


def existing_comment_count(document: str) -> int:
    match = COMMENT_COUNT_RE.search(document_frontmatter(document))
    return int(match.group(1)) if match else 0


def existing_views(document: str) -> int:
    match = VIEWS_RE.search(document_frontmatter(document))
    return int(match.group(1)) if match else 0


def state_cursor(state: dict[str, Any], status: str) -> str:
    cursors = state.get("modified_cursors", {})
    if isinstance(cursors, dict) and cursors.get(status):
        return str(cursors[status])
    if status == "publish":
        return str(state.get("last_seen_modified_gmt") or "")
    return ""


def fetch_comment_count(site_url: str, auth: str, post_id: int) -> int:
    url = api_url(site_url, "comments", {"post": str(post_id), "status": "approve", "per_page": "1"})
    data, headers = fetch_json(url, auth)
    total = headers.get("X-WP-Total")
    if total is not None:
        try:
            return int(total)
        except ValueError:
            pass
    return len(data) if isinstance(data, list) else 0


def fetch_posts(site_url: str, auth: str, args: argparse.Namespace, state: dict[str, Any]) -> list[dict[str, Any]]:
    if args.post_id is not None:
        data, _headers = fetch_json(api_url(site_url, f"posts/{args.post_id}", {"_embed": "1"}), auth)
        if not isinstance(data, dict):
            raise RuntimeError(f"unexpected WordPress post response for post {args.post_id}")
        return [data]

    since = "" if args.all else modified_after_value(state_cursor(state, args.status))
    posts: list[dict[str, Any]] = []
    page = 1
    while True:
        params = {
            "_embed": "1",
            "status": args.status,
            "per_page": "100",
            "page": str(page),
            "orderby": "modified",
            "order": "asc",
        }
        if since:
            params["modified_after"] = since
        data, headers = fetch_json(api_url(site_url, "posts", params), auth)
        if not isinstance(data, list):
            raise RuntimeError("unexpected WordPress posts response")
        posts.extend(item for item in data if isinstance(item, dict))
        total_pages = int(headers.get("X-WP-TotalPages") or "1")
        if page >= total_pages or not data:
            break
        page += 1
    return posts


def build_document(
    post: dict[str, Any],
    args: argparse.Namespace,
    fallback_tz: timezone,
    comment_count: int,
    views: int,
) -> str:
    post_id = int(post.get("id") or 0)
    slug = str(post.get("slug") or post_id)
    fields: dict[str, Any] = {
        "title": strip_markup(rendered(post.get("title"))) or f"Untitled {post_id}",
        "date": format_wp_date(str(post.get("date") or post.get("date_gmt") or ""), fallback_tz),
        "draft": str(post.get("status") or args.status) != "publish",
        "type": "posts",
    }
    canonical_url = post_url(post, args.url_mode)
    if canonical_url:
        fields["url"] = canonical_url
    fields.update(
        {
            "slug": slug,
            "wp_id": post_id,
            "author": author_name(post),
            "categories": post_terms(post, "category"),
            "tags": post_terms(post, "post_tag"),
            "featured_image": featured_image(post),
            "views": views,
            "comment_count": comment_count,
            "excerpt": strip_markup(rendered(post.get("excerpt"))),
        }
    )
    return frontmatter(fields) + clean_content(rendered(post.get("content")))


def sync_posts(
    posts: list[dict[str, Any]],
    site_url: str,
    auth: str,
    args: argparse.Namespace,
    state: dict[str, Any],
) -> int:
    fallback_tz = parse_timezone(args.timezone)
    content_dir = Path(args.content_dir)
    if not content_dir.is_absolute():
        content_dir = ROOT / content_dir
    existing = existing_post_paths(content_dir)
    changed = 0
    newest_modified = state_cursor(state, args.status)
    now = datetime.now(timezone.utc).isoformat()
    incremental = not args.all and args.post_id is None
    post_state = state.setdefault("posts", {})

    for post in posts:
        post_id = int(post.get("id") or 0)
        if post_id <= 0:
            continue
        path = post_path(content_dir, post, existing)
        seen_modified = modified_gmt(post)
        previous = post_state.get(str(post_id), {})
        if incremental and path.exists() and isinstance(previous, dict) and previous.get("modified_gmt") == seen_modified:
            if not args.quiet:
                print(f"unchanged {display_path(path)}")
            previous["path"] = display_path(path)
            previous["synced_at"] = now
            if seen_modified and seen_modified > newest_modified:
                newest_modified = seen_modified
            continue

        old = path.read_text(encoding="utf-8") if path.exists() else ""
        comments = existing_comment_count(old) if args.skip_comment_count else fetch_comment_count(site_url, auth, post_id)
        api_views = extract_views(post)
        document = build_document(post, args, fallback_tz, comments, existing_views(old) if api_views is None else api_views)
        if old != document:
            changed += 1
            if args.dry_run:
                if not args.quiet:
                    print(f"would write {display_path(path)}")
            else:
                write_text_atomic(path, document)
                if not args.quiet:
                    print(f"wrote {display_path(path)}")
        elif not args.quiet:
            print(f"unchanged {display_path(path)}")

        if seen_modified and seen_modified > newest_modified:
            newest_modified = seen_modified
        post_state[str(post_id)] = {
            "path": display_path(path),
            "modified_gmt": seen_modified,
            "synced_at": now,
        }

    if not args.dry_run:
        state["last_sync_utc"] = now
        if newest_modified and args.post_id is None:
            state.setdefault("modified_cursors", {})[args.status] = newest_modified
            if args.status == "publish":
                state["last_seen_modified_gmt"] = newest_modified
    return changed


def prune_missing_posts(
    posts: list[dict[str, Any]],
    args: argparse.Namespace,
    state: dict[str, Any],
) -> int:
    if not args.prune:
        return 0
    current_ids = {str(post.get("id")) for post in posts if post.get("id")}
    content_dir = Path(args.content_dir)
    if not content_dir.is_absolute():
        content_dir = ROOT / content_dir
    changed = 0
    post_state = state.setdefault("posts", {})
    existing = existing_post_paths(content_dir)

    for numeric_id, path in sorted(existing.items()):
        post_id = str(numeric_id)
        if post_id in current_ids:
            continue
        if path.exists():
            match = WP_ID_RE.search(document_frontmatter(path.read_text(encoding="utf-8")))
            if not match or match.group(1) != post_id:
                raise RuntimeError(f"refusing to prune {display_path(path)} because wp_id does not match {post_id}")
            changed += 1
            if args.dry_run:
                if not args.quiet:
                    print(f"would remove {display_path(path)}")
            else:
                path.unlink()
                if not args.quiet:
                    print(f"removed {display_path(path)}")
        post_state.pop(post_id, None)
    return changed


def validate_prune(posts: list[dict[str, Any]], args: argparse.Namespace) -> None:
    if not args.prune or args.dry_run:
        return
    if not posts:
        raise RuntimeError("refusing to prune from an empty WordPress API result")
    content_dir = Path(args.content_dir)
    if not content_dir.is_absolute():
        content_dir = ROOT / content_dir
    current_ids = {int(post.get("id") or 0) for post in posts if int(post.get("id") or 0) > 0}
    if not current_ids:
        raise RuntimeError("refusing to prune because the WordPress API result contains no valid post IDs")
    existing = existing_post_paths(content_dir)
    delete_count = sum(post_id not in current_ids for post_id in existing)
    large = delete_count > 0 and delete_count / max(len(existing), 1) > PRUNE_MAX_FRACTION
    if large and not getattr(args, "force_prune", False):
        raise RuntimeError(
            f"refusing to prune {delete_count} of {len(existing)} synchronized posts; review with --dry-run and repeat with --force-prune"
        )


def run_command(command: str) -> int:
    try:
        return subprocess.run(shlex.split(command), cwd=ROOT, check=False).returncode
    except OSError as exc:
        print(f"error: failed to run {command}: {exc}", file=sys.stderr)
        return 127


def process_actions(actions: list[str], args: argparse.Namespace, state: dict[str, Any], state_file: Path) -> int:
    failed_actions: list[str] = []
    localize_failed = False
    if "localize_assets" in actions:
        localize_failed = run_command(args.localize_command) != 0
        if localize_failed:
            failed_actions.append("localize_assets")
    if "build" in actions and run_command(args.hugo_command) != 0:
        failed_actions.append("build")
    if localize_failed and "build" in actions and "build" not in failed_actions:
        failed_actions.append("build")

    if failed_actions:
        state["pending_postprocess"] = failed_actions
        save_state(state_file, state)
        print(f"error: pending actions will retry: {', '.join(failed_actions)}", file=sys.stderr)
        return 1
    if actions:
        state.pop("pending_postprocess", None)
        save_state(state_file, state)
    return 0


def acquire_lock(state_file: Path) -> TextIO | None:
    if fcntl is None:
        return None
    lock_path = state_file.with_name(state_file.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise RuntimeError(f"another WordPress sync is already running for {state_file}") from exc
    return handle


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync WordPress REST API posts into Hugo content/posts.")
    parser.add_argument("--site-url", default=env_first("WORDPRESS_URL", "WP_URL", "WP_SITE_URL"), help="WordPress site URL, or set WORDPRESS_URL")
    parser.add_argument("--username", default=env_first("WORDPRESS_USERNAME", "WP_USERNAME"), help="WordPress username for private/authenticated APIs")
    parser.add_argument("--password", default=env_first("WORDPRESS_APP_PASSWORD", "WP_APP_PASSWORD", "WORDPRESS_PASSWORD"), help="WordPress application password")
    parser.add_argument("--status", default="publish", help="WordPress post status to fetch; default: publish")
    parser.add_argument("--timezone", default="+08:00", help="timezone for WordPress local dates; default: +08:00")
    parser.add_argument("--url-mode", choices=("wp", "id", "slug"), default="wp", help="canonical URL mode: wp preserves WordPress link path, id uses /archives/ID/, slug uses Hugo permalinks")
    parser.add_argument("--content-dir", default=str(DEFAULT_CONTENT_DIR.relative_to(ROOT)), help="Hugo posts directory; default: content/posts")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE.relative_to(ROOT)), help="sync state file; default: .wordpress-sync-state.json")
    parser.add_argument("--skip-comment-count", action="store_true", help="do not query wp/v2/comments for comment totals")
    parser.add_argument("--prune", action="store_true", help="with --all, remove local wp_id posts missing from this API result")
    parser.add_argument("--force-prune", action="store_true", help="allow a large prune after reviewing a dry run")
    parser.add_argument("--dry-run", action="store_true", help="fetch and compare posts without writing files or state")
    parser.add_argument("--quiet", action="store_true", help="only print warnings and errors")

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--all", action="store_true", help="sync all matching posts")
    mode.add_argument("--since-last-run", action="store_true", help="sync posts modified after the saved state timestamp; this is the default")
    mode.add_argument("--post-id", type=int, help="sync one WordPress post ID")

    parser.add_argument("--localize-assets", action="store_true", help="run scripts/localize_remote_assets.py after changed posts are written")
    parser.add_argument("--localize-command", default=f"{shlex.quote(sys.executable)} scripts/localize_remote_assets.py --best-effort --target synchronized-posts", help="asset localization command used by --localize-assets")
    parser.add_argument("--build", action="store_true", help="run Hugo after changed posts are written")
    parser.add_argument("--build-always", action="store_true", help="run --localize-assets/--build even when no post changed")
    parser.add_argument("--hugo-command", default=os.environ.get("HUGO_COMMAND", "hugo --minify --cleanDestinationDir"), help="Hugo build command used by --build")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    lock_handle: TextIO | None = None
    try:
        site_url = clean_site_url(args.site_url)
        state_file = Path(args.state_file)
        if not state_file.is_absolute():
            state_file = ROOT / state_file
        lock_handle = acquire_lock(state_file)
        state = load_state(state_file)
        saved_site_url = str(state.get("site_url") or "").rstrip("/")
        if saved_site_url and saved_site_url != site_url:
            raise RuntimeError(f"state file belongs to {saved_site_url}, not {site_url}; use a different --state-file")
        state["site_url"] = site_url
        if args.prune and not args.all:
            raise RuntimeError("--prune requires --all")
        if args.prune and args.status != "publish":
            raise RuntimeError("--prune only supports --status publish")
        auth = auth_header(args.username, args.password)
        posts = fetch_posts(site_url, auth, args, state)
        if not args.quiet:
            print(f"fetched {len(posts)} post(s)")
        validate_prune(posts, args)
        changed = sync_posts(posts, site_url, auth, args, state)
        changed += prune_missing_posts(posts, args, state)
        if args.dry_run:
            if not args.quiet:
                print(f"dry run: would change {changed} post(s)")
        else:
            pending = state.get("pending_postprocess", [])
            if not isinstance(pending, list):
                pending = []
            requested = []
            if args.localize_assets:
                requested.append("localize_assets")
            if args.build:
                requested.append("build")
            actions = list(dict.fromkeys(pending + (requested if changed or args.build_always else [])))
            if actions:
                state["pending_postprocess"] = actions
            else:
                state.pop("pending_postprocess", None)
            save_state(state_file, state)

            if process_actions(actions, args, state, state_file) != 0:
                return 1
            if not actions and not args.quiet:
                print("no changed posts")
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    finally:
        if lock_handle is not None:
            if fcntl is not None:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)
            lock_handle.close()


if __name__ == "__main__":
    raise SystemExit(main())
