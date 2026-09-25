import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import agent_reader as reader


class AgentReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "data").mkdir()
        for lang, text in [("chs", "# 简介\n\n中文正文。\n"), ("eng", "# Intro\n\nEnglish text.\n")]:
            folder = self.root / "locals" / lang
            folder.mkdir(parents=True)
            (folder / "introduction.md").write_text(text)
        self.config = {
            "schema_version": 1, "languages": ["chs", "eng"], "default_language": "eng",
            "documents": [{"id": "introduction", "file": "introduction.md",
                           "titles": {"chs": "简介", "eng": "Intro"}, "type": "project_vision"}],
        }
        self.write_config()

    def write_config(self):
        (self.root / "data/reading-map.json").write_bytes(reader.encode(self.config))

    def test_round_trip_and_default_language(self):
        reader.build(self.root)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(reader.main(["read", "introduction"], root=self.root), 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["language"], "eng")
        self.assertEqual(result["content"], "# Intro\n\nEnglish text.\n")
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(reader.main(["read", "introduction", "--language", "chs"], root=self.root), 0)
        self.assertEqual(json.loads(out.getvalue())["content"], "# 简介\n\n中文正文。\n")

    def test_missing_corpus_has_build_instruction(self):
        with self.assertRaisesRegex(reader.CorpusError, "Run:"):
            reader.validate(self.root)

    def test_source_edit_requires_rebuild(self):
        reader.build(self.root)
        (self.root / "locals/chs/introduction.md").write_text("changed")
        with self.assertRaisesRegex(reader.CorpusError, "stale"):
            reader.validate(self.root)
        reader.build(self.root)
        self.assertEqual(reader.validate(self.root)[1]["introduction"]["content"]["chs"], "changed")

    def test_tampered_document_is_rejected(self):
        reader.build(self.root)
        (self.root / "locals/agent/documents/introduction.json").write_text("{}")
        with self.assertRaisesRegex(reader.CorpusError, "modified agent document"):
            reader.validate(self.root)

    def test_missing_translation_does_not_publish_partial_build(self):
        reader.build(self.root)
        old_index = (self.root / "locals/agent/index.json").read_bytes()
        (self.root / "locals/eng/introduction.md").unlink()
        with self.assertRaises(FileNotFoundError):
            reader.build(self.root)
        self.assertEqual((self.root / "locals/agent/index.json").read_bytes(), old_index)

    def test_duplicate_ids_and_traversal_are_rejected(self):
        self.config["documents"].append(dict(self.config["documents"][0]))
        self.write_config()
        with self.assertRaisesRegex(reader.CorpusError, "Duplicate"):
            reader.build(self.root)
        self.config["documents"].pop()
        self.config["documents"][0]["file"] = "../eng/introduction.md"
        self.write_config()
        with self.assertRaisesRegex(reader.CorpusError, "Unsafe path"):
            reader.build(self.root)

    def test_symlink_cannot_escape_language_directory(self):
        source = self.root / "locals/chs/introduction.md"
        source.unlink()
        source.symlink_to(self.root / "locals/eng/introduction.md")
        with self.assertRaisesRegex(reader.CorpusError, "escapes"):
            reader.build(self.root)

    def test_unsupported_version_and_encryption_are_rejected(self):
        reader.build(self.root)
        path = self.root / "locals/agent/index.json"
        index = json.loads(path.read_text())
        index["schema_version"] = 999
        path.write_bytes(reader.encode(index))
        with self.assertRaisesRegex(reader.CorpusError, "Unsupported"):
            reader.validate(self.root)
        index["schema_version"] = 1
        index["encryption"] = "custom"
        path.write_bytes(reader.encode(index))
        with self.assertRaisesRegex(reader.CorpusError, "Encrypted content is unsupported"):
            reader.validate(self.root)

    def test_unknown_id_returns_machine_readable_error(self):
        reader.build(self.root)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(reader.main(["read", "missing"], root=self.root), 1)
        self.assertEqual(json.loads(err.getvalue())["status"], "error")

    def test_rebuild_is_deterministic(self):
        reader.build(self.root)
        first = (self.root / "locals/agent/index.json").read_bytes()
        reader.build(self.root)
        self.assertEqual((self.root / "locals/agent/index.json").read_bytes(), first)


if __name__ == "__main__":
    unittest.main()
