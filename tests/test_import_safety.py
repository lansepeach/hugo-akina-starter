from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


REPO = Path(__file__).resolve().parents[1]


def load_importer():
    spec = importlib.util.spec_from_file_location("test_import_wordpress", REPO / "scripts/import_wordpress.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module


def item(post_id: int, post_type: str, slug: str) -> str:
    return f"""
    <item>
      <title>Item {post_id}</title>
      <content:encoded><![CDATA[<p>Body {post_id}</p>]]></content:encoded>
      <excerpt:encoded>Excerpt</excerpt:encoded>
      <dc:creator>author</dc:creator>
      <wp:post_type>{post_type}</wp:post_type>
      <wp:status>publish</wp:status>
      <wp:post_id>{post_id}</wp:post_id>
      <wp:post_name>{slug}</wp:post_name>
      <wp:post_date>2026-01-01 00:00:00</wp:post_date>
    </item>
    """


def write_export(path: Path, items: str = "") -> None:
    path.write_text(
        f"""<?xml version="1.0"?>
        <rss xmlns:content="http://purl.org/rss/1.0/modules/content/"
             xmlns:dc="http://purl.org/dc/elements/1.1/"
             xmlns:excerpt="http://wordpress.org/export/1.2/excerpt/"
             xmlns:wp="http://wordpress.org/export/1.2/">
          <channel>{items}</channel>
        </rss>""",
        encoding="utf-8",
    )


class ImportSafetyTests(unittest.TestCase):
    def setUp(self):
        self.importer = load_importer()

    def run_import(self, root: Path, xml: Path, *, allow_empty: bool = False) -> int:
        args = SimpleNamespace(xml=xml, replace_existing=True, allow_empty=allow_empty)
        with mock.patch.object(self.importer, "ROOT", root), mock.patch.object(self.importer, "parse_args", return_value=args):
            return self.importer.main()

    def test_empty_import_refuses_to_replace_existing_content(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "content/posts/existing.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("keep", encoding="utf-8")
            (root / "content/page").mkdir(parents=True)
            xml = root / "export.xml"
            write_export(xml)
            self.assertEqual(self.run_import(root, xml), 1)
            self.assertEqual(existing.read_text(encoding="utf-8"), "keep")

    def test_duplicate_page_path_refuses_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "content/posts").mkdir(parents=True)
            (root / "content/page").mkdir(parents=True)
            xml = root / "export.xml"
            write_export(xml, item(1, "page", "same") + item(2, "page", "same"))
            self.assertEqual(self.run_import(root, xml), 1)

    def test_missing_post_id_refuses_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "content/posts").mkdir(parents=True)
            (root / "content/page").mkdir(parents=True)
            xml = root / "export.xml"
            write_export(xml, item(1, "post", "post").replace("<wp:post_id>1</wp:post_id>", "<wp:post_id></wp:post_id>"))
            self.assertEqual(self.run_import(root, xml), 1)

    def test_successful_import_uses_unique_non_ascii_page_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "content/posts/existing.md"
            existing.parent.mkdir(parents=True)
            existing.write_text("old", encoding="utf-8")
            (root / "content/page").mkdir(parents=True)
            xml = root / "export.xml"
            write_export(xml, item(1, "post", "post") + item(2, "page", "留言板"))
            self.assertEqual(self.run_import(root, xml), 0)
            self.assertFalse(existing.exists())
            self.assertTrue((root / "content/posts/1-post.md").exists())
            self.assertTrue((root / "content/page/untitled-2.md").exists())

    def test_transaction_rolls_back_all_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.importer.ROOT = root
            sources = [root / "stage/posts", root / "stage/page", root / "stage/comments.json"]
            targets = [root / "content/posts", root / "content/page", root / "data/comments.json"]
            for source in sources[:2]:
                source.mkdir(parents=True)
                (source / "new.md").write_text("new", encoding="utf-8")
            sources[2].parent.mkdir(parents=True, exist_ok=True)
            sources[2].write_text("new", encoding="utf-8")
            for target in targets[:2]:
                target.mkdir(parents=True)
                (target / "old.md").write_text("old", encoding="utf-8")
            targets[2].parent.mkdir(parents=True, exist_ok=True)
            targets[2].write_text("old", encoding="utf-8")

            real_move = self.importer.shutil.move
            calls = 0

            def fail_second_install(source, target):
                nonlocal calls
                calls += 1
                if calls == 5:
                    raise OSError("injected failure")
                return real_move(source, target)

            with mock.patch.object(self.importer.shutil, "move", side_effect=fail_second_install):
                with self.assertRaises(OSError):
                    self.importer.replace_transactionally(list(zip(sources, targets)), root / ".wordpress-import-backup")
            self.assertEqual((targets[0] / "old.md").read_text(encoding="utf-8"), "old")
            self.assertEqual((targets[1] / "old.md").read_text(encoding="utf-8"), "old")
            self.assertEqual(targets[2].read_text(encoding="utf-8"), "old")

    def test_existing_recovery_backup_is_never_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup_file = root / ".wordpress-import-backup/content/posts/recover.md"
            backup_file.parent.mkdir(parents=True)
            backup_file.write_text("recover", encoding="utf-8")
            xml = root / "export.xml"
            write_export(xml, item(1, "post", "post"))
            self.assertEqual(self.run_import(root, xml), 1)
            self.assertEqual(backup_file.read_text(encoding="utf-8"), "recover")

    def test_incomplete_rollback_keeps_recovery_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.importer.ROOT = root
            source = root / "stage/posts"
            target = root / "content/posts"
            source.mkdir(parents=True)
            target.mkdir(parents=True)
            (source / "new.md").write_text("new", encoding="utf-8")
            (target / "old.md").write_text("old", encoding="utf-8")
            real_move = self.importer.shutil.move
            calls = 0

            def fail_install_and_restore(source_path, target_path):
                nonlocal calls
                calls += 1
                if calls >= 2:
                    raise self.importer.shutil.Error("injected rollback failure")
                return real_move(source_path, target_path)

            backup = root / ".wordpress-import-backup"
            with mock.patch.object(self.importer.shutil, "move", side_effect=fail_install_and_restore):
                with self.assertRaisesRegex(RuntimeError, "rollback was incomplete"):
                    self.importer.replace_transactionally([(source, target)], backup)
            self.assertTrue((backup / "content/posts/old.md").exists())


if __name__ == "__main__":
    unittest.main()
