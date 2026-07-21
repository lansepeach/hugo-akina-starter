from __future__ import annotations

import argparse
import importlib.util
import io
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO = Path(__file__).resolve().parents[1]


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(f"test_{name}", REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


sync = load_script("sync_wordpress_api")
manager = load_script("manage_wordpress_sync")
localizer = load_script("localize_remote_assets")


def post(post_id: int, title: str = "New title") -> dict:
    return {
        "id": post_id,
        "title": {"rendered": title},
        "content": {"rendered": "<p>new body</p>"},
        "excerpt": {"rendered": ""},
        "date": "2026-01-01T00:00:00",
        "modified_gmt": "2026-01-02T00:00:00",
        "status": "publish",
        "slug": f"post-{post_id}",
        "link": f"https://example.com/not-the-id/{post_id}/",
        "_embedded": {},
        "meta": {},
    }


class FakeResponse:
    def __init__(
        self, chunks: list[bytes], content_type: str = "image/png", length: str | None = None,
        status: int = 200, location: str | None = None,
    ):
        self.chunks = iter(chunks)
        self.status = status
        self.read_sizes: list[int] = []
        self.closed = False
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if length is not None:
            self.headers["Content-Length"] = length
        if location is not None:
            self.headers["Location"] = location

    def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        return next(self.chunks, b"")

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.requests = []
        self.closed = False

    def request(self, method, target, headers):
        self.requests.append((method, target, headers))

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class SyncSafetyTests(unittest.TestCase):
    def test_stateless_bootstrap_compares_and_rewrites_existing_wp_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            posts = root / "content" / "posts"
            posts.mkdir(parents=True)
            path = posts / "existing.md"
            path.write_text("+++\nwp_id = 1\ncomment_count = 0\nviews = 0\n+++\n\nold\n", encoding="utf-8")
            args = argparse.Namespace(
                all=False, post_id=None, quiet=True, skip_comment_count=True, dry_run=False,
                timezone="+00:00", content_dir=str(posts), status="publish", url_mode="id",
            )
            with mock.patch.object(sync, "ROOT", root):
                changed = sync.sync_posts([post(1)], "https://example.com", "", args, {"posts": {}})
            self.assertEqual(changed, 1)
            self.assertIn('title = "New title"', path.read_text(encoding="utf-8"))

    def test_prune_rejects_empty_and_large_results_but_dry_run_previews(self):
        with tempfile.TemporaryDirectory() as directory:
            posts = Path(directory) / "posts"
            posts.mkdir()
            for post_id in range(20):
                (posts / f"{post_id}.md").write_text(f"+++\nwp_id = {post_id}\n+++\n", encoding="utf-8")
            args = argparse.Namespace(prune=True, dry_run=False, force_prune=False, content_dir=str(posts))
            with self.assertRaisesRegex(RuntimeError, "empty"):
                sync.validate_prune([], args)
            with self.assertRaisesRegex(RuntimeError, "valid post IDs"):
                sync.validate_prune([{}], args)
            with self.assertRaisesRegex(RuntimeError, "force-prune"):
                sync.validate_prune([post(post_id) for post_id in range(5)], args)
            args.dry_run = True
            sync.validate_prune([], args)
            args.dry_run = False
            args.force_prune = True
            sync.validate_prune([post(post_id) for post_id in range(5)], args)

    def test_prune_protects_small_sites(self):
        with tempfile.TemporaryDirectory() as directory:
            posts = Path(directory) / "posts"
            posts.mkdir()
            for post_id in range(1, 4):
                (posts / f"{post_id}.md").write_text(f"+++\nwp_id = {post_id}\n+++\n", encoding="utf-8")
            args = argparse.Namespace(prune=True, dry_run=False, force_prune=False, content_dir=str(posts))
            with self.assertRaisesRegex(RuntimeError, "force-prune"):
                sync.validate_prune([post(1)], args)

    def test_auto_worktree_check_includes_sync_paths_and_untracked_files(self):
        result = SimpleNamespace(stdout=" M content/posts/wp-1.md\n?? scratch.txt\n")
        with mock.patch.object(manager, "run", return_value=result) as run:
            self.assertEqual(manager.worktree_changes(), [" M content/posts/wp-1.md", "?? scratch.txt"])
        run.assert_called_once_with(["git", "status", "--porcelain", "--untracked-files=all"], capture=True)

    def test_managed_localizer_targets_only_wp_id_posts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            posts = root / "content" / "posts"
            page = root / "content" / "page"
            posts.mkdir(parents=True)
            page.mkdir(parents=True)
            managed = posts / "managed.md"
            unmanaged = posts / "manual.md"
            body_only = posts / "example.md"
            managed.write_text("+++\nwp_id = 1\n+++\n", encoding="utf-8")
            unmanaged.write_text("+++\ntitle = \"manual\"\n+++\n", encoding="utf-8")
            body_only.write_text("+++\ntitle = \"example\"\n+++\n\n```toml\nwp_id = 3\n```\n", encoding="utf-8")
            (page / "about.md").write_text("+++\nwp_id = 2\n+++\n", encoding="utf-8")
            with mock.patch.object(localizer, "ROOT", root):
                self.assertEqual(localizer.target_files("synchronized-posts"), [managed])

    def test_url_validation_rejects_non_http_and_non_public_addresses(self):
        with self.assertRaises(RuntimeError):
            localizer.validate_remote_url("file:///etc/passwd")
        for address in ("127.0.0.1", "10.0.0.1", "169.254.1.1", "192.0.2.1"):
            with self.subTest(address=address), mock.patch.object(
                localizer.socket, "getaddrinfo", return_value=[(2, 1, 6, "", (address, 80))]
            ):
                with self.assertRaisesRegex(RuntimeError, "not public"):
                    localizer.validate_remote_url("http://example.test/a.png")

    def test_local_paths_reject_traversal_and_main_records_failure(self):
        traversal = "https://example.com/wp-content/uploads/%2e%2e/%2e%2e/escape.png"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            static = root / "static"
            content = root / "post.md"
            content.write_text(traversal, encoding="utf-8")
            with mock.patch.object(localizer, "STATIC", static):
                with self.assertRaisesRegex(RuntimeError, "unsafe"):
                    localizer.local_path_for(traversal)
                with self.assertRaisesRegex(RuntimeError, "unsafe URL host"):
                    localizer.local_path_for("https://../escape.png")
                with self.assertRaisesRegex(RuntimeError, "escapes"):
                    localizer.local_path_for("https://example.com/wp-content/uploads//tmp/escape.png")
                with mock.patch.object(localizer, "target_files", return_value=[content]), mock.patch.object(
                    localizer, "download"
                ) as download, mock.patch("sys.stderr", new_callable=io.StringIO):
                    self.assertEqual(localizer.main(best_effort=True), 0)
                    download.assert_not_called()

    def test_https_connection_uses_pinned_ip_and_original_sni(self):
        raw_socket = object()
        context = mock.Mock()
        wrapped_socket = object()
        context.wrap_socket.return_value = wrapped_socket
        with mock.patch.object(localizer.ssl, "create_default_context", return_value=context), mock.patch.object(
            localizer.socket, "create_connection", return_value=raw_socket
        ) as create_connection:
            connection = localizer.PinnedHTTPSConnection("assets.example", "93.184.216.34", 443)
            connection.connect()
        create_connection.assert_called_once_with(("93.184.216.34", 443), 8, None)
        context.wrap_socket.assert_called_once_with(raw_socket, server_hostname="assets.example")
        self.assertIs(connection.sock, wrapped_socket)

    def test_redirects_are_re_resolved_and_re_pinned(self):
        first = FakeConnection(FakeResponse([], status=302, location="https://cdn.example/b.png"))
        second = FakeConnection(FakeResponse([b"png"]))
        connections = iter([first, second])

        def make_connection(_hostname, _address, _port):
            return next(connections)

        resolved = [
            (localizer.urllib.parse.urlparse("https://origin.example/a.png"), "93.184.216.1", 443),
            (localizer.urllib.parse.urlparse("https://cdn.example/b.png"), "93.184.216.2", 443),
        ]
        with mock.patch.object(localizer, "validate_remote_url", side_effect=resolved) as validate, mock.patch.object(
            localizer, "PinnedHTTPSConnection", side_effect=make_connection
        ) as pinned:
            response, connection = localizer.open_pinned("https://origin.example/a.png")
        self.assertIs(response, second.response)
        self.assertIs(connection, second)
        self.assertEqual([call.args[0] for call in validate.call_args_list], [
            "https://origin.example/a.png", "https://cdn.example/b.png"
        ])
        self.assertEqual([call.args for call in pinned.call_args_list], [
            ("origin.example", "93.184.216.1", 443), ("cdn.example", "93.184.216.2", 443)
        ])
        self.assertEqual(first.requests[0][2]["Host"], "origin.example")
        self.assertEqual(second.requests[0][2]["Host"], "cdn.example")
        self.assertTrue(first.closed)

    def test_download_rejects_html_and_streams_with_size_limit(self):
        with tempfile.TemporaryDirectory() as directory:
            static = Path(directory) / "static"
            dest = static / "asset.png"
            html = FakeResponse([b"<html>not an image</html>"], "application/octet-stream")
            with mock.patch.object(localizer, "STATIC", static), mock.patch.object(
                localizer, "open_pinned", return_value=(html, FakeConnection(html))
            ):
                self.assertFalse(localizer.download("https://example.com/a.png", dest))
            oversized = FakeResponse([b"12345"])
            with mock.patch.object(localizer, "STATIC", static), mock.patch.object(
                localizer, "MAX_DOWNLOAD_BYTES", 4
            ), mock.patch.object(localizer, "open_pinned", return_value=(oversized, FakeConnection(oversized))):
                self.assertFalse(localizer.download("https://example.com/a.png", dest))
            self.assertFalse(dest.exists())
            self.assertEqual(oversized.read_sizes, [localizer.CHUNK_SIZE])

    def test_open_pinned_rejects_non_success_status(self):
        response = FakeResponse([b"missing"], status=404)
        connection = FakeConnection(response)
        resolved = (localizer.urllib.parse.urlparse("https://example.com/a.png"), "93.184.216.34", 443)
        with mock.patch.object(localizer, "validate_remote_url", return_value=resolved), mock.patch.object(
            localizer, "PinnedHTTPSConnection", return_value=connection
        ):
            with self.assertRaisesRegex(RuntimeError, "HTTP status 404"):
                localizer.open_pinned("https://example.com/a.png")
        self.assertTrue(response.closed)
        self.assertTrue(connection.closed)

    def test_query_hashing_and_content_length_limit_are_retained(self):
        with tempfile.TemporaryDirectory() as directory:
            static = Path(directory) / "static"
            with mock.patch.object(localizer, "STATIC", static):
                first, _ = localizer.local_path_for("https://example.com/a.png?v=1")
                second, _ = localizer.local_path_for("https://example.com/a.png?v=2")
                self.assertNotEqual(first, second)
                response = FakeResponse([], length=str(localizer.MAX_DOWNLOAD_BYTES + 1))
                with mock.patch.object(localizer, "open_pinned", return_value=(response, FakeConnection(response))):
                    self.assertFalse(localizer.download("https://example.com/a.png", static / "a.png"))


if __name__ == "__main__":
    unittest.main()
