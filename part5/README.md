# Part 5 — What Happens When a RAG Pipeline Meets Real Documents

Companion code for Part 5 of the [RAG in Practice](https://dev.to/gursharansingh/series/37906) series.

**Article:** [RAG in Practice — Part 5: Build a RAG System in Practice](https://dev.to/gursharansingh/rag-in-practice-part-5-build-a-rag-system-in-practice-4knd)

---

## What this repo contains

`part5_rag.py` is the baseline pipeline — it loads five TechNova support documents, chunks them, embeds them into ChromaDB, and answers three questions. `inspect_chunks.py` shows exactly where the chunker splits each document, so you can see the procedural-split failure the article describes without spending any API credits. `compare_html_raw_vs_parsed.py` runs one question against two versions of the product-specs HTML — raw and parsed — and lets you see the difference the parsing decision makes on the generated answer.

---

## Prerequisites

- Python **3.10+**
- An OpenAI API key (needed for `part5_rag.py` and `compare_html_raw_vs_parsed.py`; not needed for `inspect_chunks.py`)
- Expected cost for a full run across all three scripts: under **$0.05** at current OpenAI pricing
- A bash shell to run the `.sh` scripts (macOS/Linux Terminal, or Git Bash / WSL on Windows — see Windows users section below)

---

## Windows users

The `.sh` script requires a bash shell. The easiest setup is often to open the repo in VS Code and set the integrated terminal to Git Bash or WSL. Options:

- **Git Bash** (recommended): install [Git for Windows](https://git-scm.com/download/win), open Git Bash, then run `bash run_part5.sh` as shown below
- **WSL**: open a WSL terminal, then run the same command
- **Manual fallback** (no bash needed):
  ```
  cd part5
  python -m venv .venv
  .venv\Scripts\python -m pip install -r requirements.txt
  set OPENAI_API_KEY=your-key-here
  .venv\Scripts\python part5_rag.py
  .venv\Scripts\python inspect_chunks.py
  .venv\Scripts\python compare_html_raw_vs_parsed.py
  ```

---

## Start here: the baseline

Run the three scripts in this order on first use:

1. `part5_rag.py` — the baseline pipeline (this section)
2. `inspect_chunks.py` — chunk boundary inspector (below)
3. `compare_html_raw_vs_parsed.py` — HTML parsing comparison (below)

Each script corresponds to a specific section of the article. You can run them in any order on rereads, but the first-time sequence above matches the article's flow.

**`part5_rag.py`** — the canonical RAG pipeline for the TechNova corpus.

Corresponds to: all four document categories the article covers (short policy docs, procedural troubleshooting, versioned changelogs, structured HTML/tables).

```bash
# From the part5/ directory
export OPENAI_API_KEY="your-key-here"    # Windows: $env:OPENAI_API_KEY="your-key-here"
python part5_rag.py
```

The `part5/` directory includes a `.env.example` file — copy it to `.env` if you prefer to keep your API key in a file rather than export it in your shell. The scripts read `OPENAI_API_KEY` from the environment either way.

Or use the shell script from `part5/`, which handles virtual environment setup automatically:

```bash
bash run_part5.sh
```

**What you will see:** chunk counts for each document, then three questions with answers and retrieved sources. Pay attention to the third question ("What changed in the latest firmware update?") — the retriever surfaces chunks from multiple firmware versions, and the answer blends them.

**Experiment with:**
- `chunk_size` in the chunking loop (search for `--- Experiment ---` near the bottom of the file)
- The three `ask()` questions — replace them with your own

---

## Then see the failure modes

### `inspect_chunks.py` — procedural split

Corresponds to: the "Procedural Troubleshooting Documents" section of the article.

```bash
python inspect_chunks.py
```

No API key needed. No cost. Run it as many times as you like.

**What you will see:** chunk boundaries for all five documents. For `troubleshooting-guide.md`, every chunk is printed in full so you can read the exact line where the Bluetooth reset procedure splits (if it does at the current `CHUNK_SIZE`).

**Experiment with:**
- `CHUNK_SIZE = 200` at the top of the file — forces a split in the Bluetooth procedure
- `FULL_CONTENT_FILES` — add `"firmware-changelog.md"` to see how version entries land across chunks
- `CHUNK_OVERLAP` — increase it and watch whether overlap actually fixes a structural split, or just repeats content across the boundary

### `compare_html_raw_vs_parsed.py` — HTML parsing decision

Corresponds to: the "Structured HTML and Tables" section of the article.

```bash
python compare_html_raw_vs_parsed.py
```

**What you will see:** the same question ("What is the battery life of the WH-500?") answered twice — once from raw HTML chunks, once from chunks built from parsed labeled rows. The retrieved chunk for each approach is printed in full so you can see exactly what context the model was given.

**Experiment with:**
- `QUESTION` at the top of the file — try `"What is the weight of the WH-1000?"` or `"Does the WH-500 support active noise cancellation?"`
- `CHUNK_SIZE` — try larger values to see whether giving the raw-HTML chunker more room fixes the problem or just delays it

---

## Rerunning

Each script creates its ChromaDB collections in-memory, so every run starts fresh — no cleanup step, no cached state. You can freely change `CHUNK_SIZE`, `QUESTION`, or any other experimentation value at the top of a script and rerun to see the effect immediately.

---

## Repo layout

```
rag-in-practice-samples/
├── data/                            shared sample files (used by Parts 5–8)
│   ├── firmware-changelog.md
│   ├── product-specs.html
│   ├── return-policy.md
│   ├── troubleshooting-guide.md
│   └── warranty-terms.md
├── part5/
│   ├── part5_rag.py                 baseline pipeline — run this first
│   ├── inspect_chunks.py            chunk boundary inspector — no API needed
│   ├── compare_html_raw_vs_parsed.py  HTML parsing comparison
│   ├── html_table_to_text.py        HTML table parser used by the comparison script
│   ├── requirements.txt
│   ├── run_part5.sh
│   └── .env.example
└── README.md
```

---

## Files

| File | What it does |
|---|---|
| `part5_rag.py` | Baseline pipeline: load, chunk, embed, store, retrieve, generate. Run this first. |
| `inspect_chunks.py` | Prints chunk boundaries for all five documents. Full content for `troubleshooting-guide.md`. No API calls. |
| `compare_html_raw_vs_parsed.py` | Runs one question against raw HTML and parsed labeled-row versions of `product-specs.html`. Shows the retrieved chunk and generated answer for each. |
| `html_table_to_text.py` | Converts HTML tables to labeled row text (`Specification: Battery Life \| WH-500: 8 hours`). Used by the comparison script. |
| `requirements.txt` | `openai` and `chromadb` — the only two dependencies. |
| `run_part5.sh` | Shell script that creates a virtual environment, installs dependencies, and runs `part5_rag.py`. |

---

## What this code is not

This is baseline teaching code — recursive-style paragraph chunking, vector-only retrieval, no reranking, no metadata filtering. It is intentionally simple so the failure modes stay visible. The patterns that address those failures (structure-aware chunking, hybrid retrieval, reranking by metadata) are covered in Parts 7 and 8.
