#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
TARGETS = [ROOT / "content", ROOT / "assets" / "css"]

URL_RE = re.compile(r"https?://[^\s\"'<>)]*\.(?:png|jpe?g|gif|webp|svg|woff2?|ttf|otf|css|js)(?:\?[^\s\"'<>)]*)?", re.I)
BASE_URL_RE = re.compile(r"(?m)^\s*baseURL\s*=\s*[\"']([^\"']+)[\"']")


def site_base_path() -> str:
    config = ROOT / "hugo.toml"
    if not config.exists():
        return ""
    match = BASE_URL_RE.search(config.read_text(encoding="utf-8"))
    if not match:
        return ""
    path = urllib.parse.urlparse(match.group(1)).path.strip("/")
    return f"/{path}" if path else ""


def local_path_for(url: str) -> tuple[Path, str]:
    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path).lstrip("/")
    if path.startswith("wp-content/uploads/"):
        local_rel = Path("uploads") / path.removeprefix("wp-content/uploads/")
    else:
        safe_parts = [part for part in Path(path).parts if part not in ("", ".", "..")]
        if not safe_parts:
            safe_parts = ["asset"]
        local_rel = Path("remote-assets") / parsed.netloc / Path(*safe_parts)

    if parsed.query:
        stem = local_rel.stem
        suffix = local_rel.suffix
        digest = hashlib.sha1(parsed.query.encode("utf-8")).hexdigest()[:8]
        local_rel = local_rel.with_name(f"{stem}-{digest}{suffix}")

    return STATIC / local_rel, "/" + local_rel.as_posix()


def download(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 0:
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            data = response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        print(f"FAILED {url}: {exc}", file=sys.stderr)
        return False
    if not data:
        print(f"FAILED {url}: empty response", file=sys.stderr)
        return False
    temporary = dest.with_name(f".{dest.name}.{os.getpid()}.part")
    try:
        temporary.write_bytes(data)
        os.replace(temporary, dest)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def main(best_effort: bool = False) -> int:
    files: list[Path] = []
    for target in TARGETS:
        files.extend(path for path in target.rglob("*") if path.is_file() and path.suffix in {".md", ".css"})

    urls: set[str] = set()
    for path in files:
        urls.update(URL_RE.findall(path.read_text(encoding="utf-8")))

    replacements: dict[str, str] = {}
    failed: list[str] = []
    base_path = site_base_path()
    for url in sorted(urls):
        dest, public_path = local_path_for(url)
        if download(url, dest):
            replacements[url] = base_path + public_path
        else:
            failed.append(url)

    for path in files:
        text = path.read_text(encoding="utf-8")
        updated = text
        for url, replacement in replacements.items():
            updated = updated.replace(url, replacement)
        if updated != text:
            path.write_text(updated, encoding="utf-8")

    print(f"localized={len(replacements)} failed={len(failed)}")
    for url in failed:
        print(url)
    return 0 if not failed or best_effort else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Localize remote assets used by Hugo content and CSS.")
    parser.add_argument("--best-effort", action="store_true", help="report failed downloads but return success")
    raise SystemExit(main(parser.parse_args().best_effort))
