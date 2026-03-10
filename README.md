# Embodied Paper Radar

Minimal one-person literature workflow for embodied intelligence:

- fetch fresh arXiv papers from a few relevant categories
- filter and score them with real-robot, manipulation, VLA, and RL weighted keywords
- store everything in local SQLite
- emit a weekly Markdown report you can feed into Codex/OpenCode

This is intentionally small. It avoids brittle crawling and keeps the workflow inspectable.

## What You Get

- `config/example_config.toml`: feed list and keyword filters
- `data/papers.db`: local SQLite database
- `reports/weekly-YYYY-MM-DD.md`: weekly radar report
- `reports/weekly-YYYY-MM-DD.ris`: Zotero-importable RIS export
- `reports/screen-YYYY-MM-DD.json`: Codex screening result
- `reports/screen-YYYY-MM-DD.md`: human-readable Codex screening result
- `reports/read_now-YYYY-MM-DD.ris`: RIS containing only `read_now` papers
- `reports/read_later-YYYY-MM-DD.ris`: RIS containing only `read_later` papers
- `prompts/weekly_summary.md`: prompt for Codex/OpenCode

## Setup

No external dependencies are required.

```bash
cd /home/b5090/embodied-paper-radar
python3 radar.py --config config/example_config.toml fetch
python3 radar.py --config config/example_config.toml report
python3 radar.py --config config/example_config.toml export-ris
python3 radar.py --config config/example_config.toml screen-codex
python3 radar.py --config config/example_config.toml weekly
```

The fetch step pulls recent items from:

- `arXiv cs.RO`
- `arXiv cs.AI`
- `arXiv cs.CV`
- `arXiv cs.LG`

The report step writes a Markdown file under `reports/`.
The `export-ris` step writes a RIS file you can import into Zotero via `File -> Import`.
The `screen-codex` step sends recent candidate papers to your local `codex` CLI and asks it to label each one as `read_now`, `read_later`, or `skip`.
The current screening prompt is configured to return Chinese explanations.
The `weekly` step runs `fetch + report + screen-codex + export-ris` in one command.
When `weekly` runs with Codex screening enabled, it also creates filtered RIS files for `read_now` and `read_later` only.
Weekly markdown summaries are bilingual by default and use a free translation backend with local cache.
The default translation path uses `MyMemory`, and automatically falls back to a secondary free endpoint if rate-limited.
Default window and volume:

- `days = 7`
- `limit-per-feed = 25`
- `limit = 30`

## Recommended Weekly Routine

1. Run `fetch` two or three times per week.
2. Run `report` once per week.
3. Run `export-ris` and import the RIS file into Zotero.
4. Open the report, move the must-read papers into Zotero `01_must_read`.
5. Run `screen-codex` to get an LLM pass over the candidates.
6. Paste the report into Codex/OpenCode with [`prompts/weekly_summary.md`](/home/b5090/embodied-paper-radar/prompts/weekly_summary.md) if you want a broader weekly summary.
7. Put the best resulting ideas into Zotero `03_idea_pool`.

If you want the short version, just run:

```bash
python3 radar.py --config config/example_config.toml weekly
```

Useful variants:

```bash
python3 radar.py --config config/example_config.toml weekly --skip-codex
python3 radar.py --config config/example_config.toml weekly --limit-per-feed 10 --limit 10
```

## Why RIS Instead Of CSV

Zotero imports standardized bibliographic formats such as `RIS`, `BibTeX`, and `CSL JSON`.
It does not support direct bibliographic import from generic CSV files, so this project exports RIS for Zotero ingestion.

## Suggested Zotero Collections

- `00_inbox`
- `01_must_read`
- `02_summarized`
- `03_idea_pool`

## Adjusting For Your Research Topic

Edit [`config/example_config.toml`](/home/b5090/embodied-paper-radar/config/example_config.toml):

- add or remove `term_weights`
- raise `min_score` if too many weak papers get through
- lower `min_score` if you are missing good candidates
- change feed weights if you want `cs.RO` to dominate more strongly
- change `translation.backend` if you want to switch between `mymemory` and `libretranslate`

## Next Small Upgrade

If this becomes useful, the next feature to add is `OpenReview` venue tracking for `CoRL`.
