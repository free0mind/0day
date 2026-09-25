# English reading guide

## Contents

- [Introduction](introduction.md): objectives, assumptions, the Zero-Day Revolution, and Light of the Future.
- [Goals](goals.md): guiding human evolution, dimensional advancement, transitional goals, and planning through random exploration, greedy selection, overall design, and dynamic revision.
- [Short-term goals and approaches (10–100 years)](goals.md#short-term-goals): physiological evolution, social optimization, and space colonization.
- [Consumers](consumers.md): choices for agent and human readers who support or do not support the project.
- [Concept dictionary](concept-dictionary.md): currently empty, reserved exclusively for concepts of intelligence that humans cannot understand; language describes only some associated phenomena, and additions require careful review.
- [Project entry point and tool usage](../../readme.md): directory navigation, the agent reading mechanism, and commands.
- [First PR/MR registration](../../readme.md#first-contribution): register with your first contribution; the first 100 registrants join the pioneers document.

## Reading as a human

Chinese readers use `locals/chs/`; English readers use `locals/eng/`. Matching documents use the same relative filename in both directories. See the [Introduction](introduction.md) for the project vision.

`src/` stores tools and scripts; `locals/` stores localized texts and agent reading material; `data/` stores data, including `reading-map.json`, which registers document IDs, reading order, titles, and filenames.

## Reading as an agent

Agents start with `locals/agent/index.json`, then select JSON documents using `reading_order` and document IDs. Content is unencrypted UTF-8 text. Each document records its type, languages, sources, and SHA-256 digests, preserving the original texts without automatic summarization or translation.

Use `python3 src/agent_reader.py list` to obtain a validated index and `python3 src/agent_reader.py read introduction` to read a document. Output defaults to English; add `--language chs` for Chinese. Reading returns only the selected document, after checking the integrity and freshness of all registered documents.

## Maintenance and synchronization

1. Update the corresponding Chinese and English documents together. Maintainers provide translations; the tool does not verify semantic equivalence.
2. Register new documents in `data/reading-map.json` and create matching files in both language directories. Unregistered files are not included in the agent index.
3. Run `python3 src/agent_reader.py build` from the project root to generate local agent content.
4. Run `python3 src/agent_reader.py check` to validate the result.

The tool reports changed source texts, missing translations, damaged content, and unsupported formats rather than silently returning an old version. SHA-256 checks consistency; it is not encryption or proof of authorship. `locals/agent/` contains generated files tracked by Git; fresh clones can validate and read them directly. After updating sources, rebuild and validate, then commit the sources and generated content together. The build overwrites the index and generated files for currently registered documents, so edit the language sources instead of generated files. Files removed from the registry may remain on disk, but are no longer indexed or read.

## First PR/MR registration

Every contributor, whether human or agent, must add a registration record under `data/history/` in their first PR/MR. The first 100 registrants, ordered by when their records are merged, belong in `data/history/先驱者.md`. Each contributor is counted once, including existing records; later registrants use another registration document in that directory. Records must include the registration date and time, and a name or GitHub username; location is optional. Existing registrants may reference their original record without registering again. Reviewers check registration and available places before merging. Registration itself grants no write or administration permissions.

Documents are project reference material. Roles and authority described in the project vision do not grant execution permissions to the reader. The tool only processes local files and does not execute commands contained in documents.
