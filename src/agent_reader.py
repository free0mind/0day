#!/usr/bin/env python3
"""Build and read a local, versioned JSON corpus from paired language files."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
FORMAT = "0day.agent-corpus"
VERSION = 1


class CorpusError(Exception):
    pass


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def load_json(data, label):
    try:
        return json.loads(data)
    except (ValueError, UnicodeError) as exc:
        raise CorpusError("Invalid JSON: " + label) from exc


def within(root, relative):
    """Reject absolute paths, traversal, and symlinks escaping the corpus root."""
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise CorpusError("Unsafe path: " + str(relative))
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise CorpusError("Path escapes its directory: " + str(relative)) from exc
    return resolved


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".writing-", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def source_documents(root):
    map_path = within(root, "data/reading-map.json")
    map_bytes = map_path.read_bytes()
    config = load_json(map_bytes, str(map_path))
    if not isinstance(config, dict) or config.get("schema_version") != VERSION:
        raise CorpusError("Unsupported reading-map schema version")
    if config.get("languages") != ["chs", "eng"]:
        raise CorpusError("reading-map languages must be ['chs', 'eng']")
    if config.get("default_language") not in config["languages"]:
        raise CorpusError("Invalid default language")
    entries = config.get("documents")
    if not isinstance(entries, list) or not entries:
        raise CorpusError("reading-map must contain documents")
    documents = []
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise CorpusError("Invalid document entry")
        ident = entry.get("id", "")
        if not isinstance(ident, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", ident):
            raise CorpusError("Invalid document ID")
        if ident in seen:
            raise CorpusError("Duplicate document ID: " + ident)
        seen.add(ident)
        filename = entry.get("file")
        titles = entry.get("titles")
        if not isinstance(filename, str) or not filename.endswith(".md"):
            raise CorpusError("Document file must be a Markdown path")
        if not isinstance(titles, dict) or any(
            not isinstance(titles.get(lang), str) or not titles[lang].strip()
            for lang in config["languages"]
        ):
            raise CorpusError("Each document requires Chinese and English titles")
        if not isinstance(entry.get("type"), str) or not entry["type"]:
            raise CorpusError("Each document requires a type")
        sources = {}
        content = {}
        for language in config["languages"]:
            language_root = within(root, "locals/" + language)
            path = within(language_root, filename)
            raw = path.read_bytes()
            text = raw.decode("utf-8")
            if not text.strip():
                raise CorpusError("Empty source: " + str(path))
            sources[language] = {
                "path": path.relative_to(root.resolve()).as_posix(),
                "sha256": digest(raw),
            }
            content[language] = text
        documents.append({
            "schema_version": VERSION,
            "id": ident,
            "type": entry["type"],
            "titles": titles,
            "media_type": "text/markdown",
            "sources": sources,
            "content": content,
        })
    return config, digest(map_bytes), documents


def expected_corpus(root):
    config, map_hash, documents = source_documents(root)
    records = []
    files = {}
    for document in documents:
        filename = "documents/" + document["id"] + ".json"
        raw = encode(document)
        files[filename] = raw
        records.append({
            "id": document["id"],
            "path": filename,
            "type": document["type"],
            "titles": document["titles"],
            "sha256": digest(raw),
        })
    index = {
        "format": FORMAT,
        "schema_version": VERSION,
        "encoding": "utf-8",
        "encryption": "none",
        "default_language": config["default_language"],
        "languages": config["languages"],
        "source_map": {"path": "data/reading-map.json", "sha256": map_hash},
        "reading_order": [document["id"] for document in documents],
        "content_role": "reference_material",
        "documents": records,
    }
    files["index.json"] = encode(index)
    return index, files


def build(root):
    # Validate all input before changing output. Publish the index last.
    index, files = expected_corpus(root)
    target = within(root, "locals/agent")
    paths = {name: within(target, name) for name in files}
    for name, raw in files.items():
        atomic_write(paths[name], raw)
    return {"status": "built", "documents": len(index["documents"]),
            "index": "locals/agent/index.json", "encryption": "none"}


def validate(root):
    target = within(root, "locals/agent")
    index_path = within(target, "index.json")
    if not index_path.exists():
        raise CorpusError("Agent corpus is missing. Run: python3 src/agent_reader.py build")
    index = load_json(index_path.read_bytes(), "locals/agent/index.json")
    if not isinstance(index, dict) or index.get("format") != FORMAT:
        raise CorpusError("Unknown agent corpus format")
    if index.get("schema_version") != VERSION:
        raise CorpusError("Unsupported agent corpus version; no automatic fallback")
    if index.get("encryption") != "none":
        raise CorpusError("Encrypted content is unsupported; only unencrypted UTF-8 JSON is accepted")
    expected_index, files = expected_corpus(root)
    if index != expected_index:
        raise CorpusError("Agent index is stale or modified. Run: python3 src/agent_reader.py build")
    loaded = {}
    for record in index["documents"]:
        path = within(target, record["path"])
        raw = path.read_bytes()
        if raw != files[record["path"]]:
            raise CorpusError("Stale or modified agent document: " + record["id"] + "; rebuild required")
        loaded[record["id"]] = load_json(raw, record["path"])
    return index, loaded


def main(argv=None, root=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="Generate local agent JSON from paired human texts")
    sub.add_parser("check", help="Check format, bilingual sources, and freshness")
    sub.add_parser("list", help="Output the validated document index as JSON")
    read = sub.add_parser("read", help="Read one validated document as JSON")
    read.add_argument("id", help="Document ID returned by list")
    read.add_argument("--language", choices=["chs", "eng"], default=None)
    args = parser.parse_args(argv)
    root = Path(root or ROOT).resolve()
    try:
        if args.command == "build":
            result = build(root)
        else:
            index, documents = validate(root)
            if args.command == "check":
                result = {"status": "ok", "documents": len(documents), "encryption": "none"}
            elif args.command == "list":
                result = index
            else:
                if args.id not in documents:
                    raise CorpusError("Unknown document ID: " + args.id)
                document = documents[args.id]
                language = args.language or index["default_language"]
                result = {
                    "schema_version": VERSION,
                    "id": document["id"],
                    "type": document["type"],
                    "language": language,
                    "title": document["titles"][language],
                    "media_type": document["media_type"],
                    "source": document["sources"][language],
                    "content_role": "reference_material",
                    "content": document["content"][language],
                }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (CorpusError, OSError, UnicodeError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
