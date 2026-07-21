#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import http.client
import ipaddress
import os
import re
import socket
import ssl
import sys
import urllib.error
import urllib.parse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"
TARGETS = [ROOT / "content", ROOT / "assets" / "css"]
MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
CHUNK_SIZE = 64 * 1024
MAX_REDIRECTS = 5

URL_RE = re.compile(r"https?://[^\s\"'<>)]*\.(?:png|jpe?g|gif|webp|svg|woff2?|ttf|otf|css|js)(?:\?[^\s\"'<>)]*)?", re.I)
BASE_URL_RE = re.compile(r"(?m)^\s*baseURL\s*=\s*[\"']([^\"']+)[\"']")
WP_ID_RE = re.compile(r"(?m)^wp_id\s*(?:=|:)\s*[\"']?\d+[\"']?\s*$")


def validate_remote_url(url: str) -> tuple[urllib.parse.ParseResult, str, int]:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("only http(s) URLs with a hostname are allowed")
    if parsed.username or parsed.password:
        raise RuntimeError("URLs containing credentials are not allowed")
    if any(char in url for char in "\r\n\x00"):
        raise RuntimeError("URL contains invalid control characters")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise RuntimeError("invalid URL port") from exc
    try:
        addresses = socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise RuntimeError(f"cannot resolve hostname: {exc}") from exc
    if not addresses:
        raise RuntimeError("hostname resolved to no addresses")
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise RuntimeError(f"destination address {ip} is not public")
    return parsed, addresses[0][4][0], port


class PinnedHTTPConnection(http.client.HTTPConnection):
    def __init__(self, hostname: str, address: str, port: int):
        super().__init__(hostname, port, timeout=8)
        self.address = address

    def connect(self) -> None:
        self.sock = socket.create_connection((self.address, self.port), self.timeout, self.source_address)


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname: str, address: str, port: int):
        super().__init__(hostname, port, timeout=8, context=ssl.create_default_context())
        self.address = address

    def connect(self) -> None:
        sock = socket.create_connection((self.address, self.port), self.timeout, self.source_address)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except Exception:
            sock.close()
            raise


def open_pinned(url: str) -> tuple[http.client.HTTPResponse, http.client.HTTPConnection]:
    current_url = url
    for redirect_count in range(MAX_REDIRECTS + 1):
        parsed, address, port = validate_remote_url(current_url)
        connection_class = PinnedHTTPSConnection if parsed.scheme == "https" else PinnedHTTPConnection
        connection = connection_class(parsed.hostname or "", address, port)
        target = urllib.parse.urlunparse(("", "", parsed.path or "/", parsed.params, parsed.query, ""))
        try:
            connection.request("GET", target, headers={"Host": parsed.netloc, "User-Agent": "Mozilla/5.0"})
            response = connection.getresponse()
        except Exception:
            connection.close()
            raise
        if response.status not in {301, 302, 303, 307, 308}:
            if not 200 <= response.status < 300:
                response.close()
                connection.close()
                raise RuntimeError(f"unexpected HTTP status {response.status}")
            return response, connection
        location = response.headers.get("Location")
        response.close()
        connection.close()
        if not location:
            raise RuntimeError("redirect response is missing Location")
        if redirect_count == MAX_REDIRECTS:
            raise RuntimeError("too many redirects")
        current_url = urllib.parse.urljoin(current_url, location)
    raise RuntimeError("too many redirects")


def safe_destination(path: Path) -> Path:
    static = STATIC.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(static)
    except ValueError as exc:
        raise RuntimeError("localized path escapes static directory") from exc
    return resolved


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
    if parsed.netloc in {".", ".."} or "\\" in parsed.netloc or "\x00" in parsed.netloc:
        raise RuntimeError("unsafe URL host")
    path = urllib.parse.unquote(parsed.path).lstrip("/")
    if "\x00" in path or "\\" in path or any(part in {".", ".."} for part in path.split("/")):
        raise RuntimeError("unsafe URL path")
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

    return safe_destination(STATIC / local_rel), "/" + local_rel.as_posix()


def download(url: str, dest: Path) -> bool:
    temporary: Path | None = None
    connection: http.client.HTTPConnection | None = None
    try:
        dest = safe_destination(dest)
        temporary = dest.with_name(f".{dest.name}.{os.getpid()}.part")
        if dest.exists() and dest.stat().st_size > 0:
            return True
        response, connection = open_pinned(url)
        try:
            content_type = response.headers.get_content_type().lower()
            if content_type in {"text/html", "application/xhtml+xml"}:
                raise RuntimeError(f"unexpected HTML content type {content_type}")
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > MAX_DOWNLOAD_BYTES:
                raise RuntimeError(f"response exceeds {MAX_DOWNLOAD_BYTES} bytes")
            dest.parent.mkdir(parents=True, exist_ok=True)
            total = 0
            first = True
            with temporary.open("wb") as output:
                while chunk := response.read(CHUNK_SIZE):
                    total += len(chunk)
                    if total > MAX_DOWNLOAD_BYTES:
                        raise RuntimeError(f"response exceeds {MAX_DOWNLOAD_BYTES} bytes")
                    if first:
                        prefix = chunk.lstrip()[:64].lower()
                        if prefix.startswith((b"<!doctype html", b"<html", b"<head", b"<body")):
                            raise RuntimeError("response appears to be HTML")
                        first = False
                    output.write(chunk)
            if not total:
                raise RuntimeError("empty response")
        finally:
            response.close()
        os.replace(temporary, dest)
        return True
    except (OSError, RuntimeError, http.client.HTTPException, urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"FAILED {url}: {exc}", file=sys.stderr)
        return False
    finally:
        if connection is not None:
            connection.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def frontmatter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0] not in {"+++", "---"}:
        return ""
    try:
        end = lines.index(lines[0], 1)
    except ValueError:
        return ""
    return "\n".join(lines[1:end])


def target_files(target: str) -> list[Path]:
    if target == "synchronized-posts":
        posts = ROOT / "content" / "posts"
        if not posts.exists():
            return []
        return [
            path
            for path in posts.rglob("*.md")
            if WP_ID_RE.search(frontmatter(path.read_text(encoding="utf-8")))
        ]
    files: list[Path] = []
    for root in TARGETS:
        files.extend(path for path in root.rglob("*") if path.is_file() and path.suffix in {".md", ".css"})
    return files


def main(best_effort: bool = False, target: str = "all") -> int:
    files = target_files(target)

    urls: set[str] = set()
    for path in files:
        urls.update(URL_RE.findall(path.read_text(encoding="utf-8")))

    replacements: dict[str, str] = {}
    failed: list[str] = []
    base_path = site_base_path()
    for url in sorted(urls):
        try:
            dest, public_path = local_path_for(url)
        except (OSError, RuntimeError, ValueError) as exc:
            print(f"FAILED {url}: {exc}", file=sys.stderr)
            failed.append(url)
            continue
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
    parser.add_argument("--target", choices=("all", "synchronized-posts"), default="all")
    args = parser.parse_args()
    raise SystemExit(main(args.best_effort, args.target))
