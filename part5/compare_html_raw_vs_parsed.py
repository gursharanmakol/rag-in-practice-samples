"""
compare_html_raw_vs_parsed.py

Companion to Part 5 of RAG in Practice — "Build a RAG System in Practice"
Section: Structured HTML and Tables

This script runs the same question against two versions of product-specs.html:
  1. Raw HTML passed straight into the chunker (what a naive pipeline does)
  2. HTML preprocessed by html_table_to_text.py into labeled rows before chunking

Run it to see:
  - what chunk the retriever surfaces for each approach
  - what answer the model generates from each retrieved chunk
  - whether the model can identify which product "8 hours" belongs to
    when the surrounding HTML structure has been stripped away

When the HTML is chunked raw, the retriever may surface a chunk containing
"<td>8 hours</td>" — technically the right number, but with the table row
and column context stripped out. The model has to guess which product and
which attribute that value belongs to.

When the HTML is parsed first, the retriever surfaces something like:
  "Specification: Battery Life | WH-1000 Premium Headphones: 30 hours (ANC off),
   20 hours (ANC on) | WH-500 Sport Headphones: 8 hours"
The value is self-contained. The model does not have to guess.

Cost: approximately $0.01 per run (2 embedding calls + 2 generation calls
at current OpenAI pricing). Cheap to run repeatedly while experimenting.

Experiment with:
  - QUESTION below: try "What is the weight of the WH-1000?" or
    "Does the WH-500 support active noise cancellation?" to see the
    contrast on other attributes. Some attributes may retrieve better
    from raw HTML than others — it depends on what surrounding tag text
    lands in the same chunk.
  - CHUNK_SIZE: try larger values to see whether giving the raw HTML
    chunker more room lets it capture both the column header and the
    value in a single chunk. Does this fix the problem, or just delay it?
  - The soundbar table: the product-specs.html file has two tables.
    Ask about the SB-300 soundbar ("What is the SB-300's total output
    power?") to see how the parser handles the second table's rows.
"""

import sys
import logging
import chromadb
from chromadb.config import Settings
from pathlib import Path

# Silence ChromaDB 0.6.3's telemetry error messages.
# See part5_rag.py for the full explanation — short version: a posthog
# version mismatch makes every capture() call raise TypeError, which
# ChromaDB catches and logs. Suppressing this logger cleans the output
# without affecting functionality (telemetry is disabled on the Client
# below via Settings(anonymized_telemetry=False)).
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

# Add the part5 directory to the path so this script can be run from
# the repo root, the part5 directory, or an IDE without adjustment.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import pipeline helpers from the baseline — same chunker, embedder,
# retriever, and generator that part5_rag.py uses. This keeps the
# comparison honest: only the input text changes between the two approaches.
# The chunker, embedding model, retrieval algorithm, and generation model
# are identical. Any difference in answer quality comes from the parsing
# decision alone.
from part5_rag import chunk_document, get_embeddings, store_chunks, retrieve, generate_answer, DATA_DIR

# Import the HTML-to-text converter. We do not re-implement it here —
# the article references html_table_to_text.py by name, and using it
# directly shows the reader exactly what preprocessing was applied.
from html_table_to_text import html_table_to_text


# ============================================================
# Configuration — the knobs to experiment with
# ============================================================

# --- Experiment ---
# Change QUESTION to explore other attributes from the product-specs tables.
# Good ones to try:
#   "What is the weight of the WH-1000?"
#   "Does the WH-500 support active noise cancellation?"
#   "What Bluetooth version does the WH-500 use?"
#   "What is the SB-300 soundbar's total output power?"
# Watch whether the raw HTML approach improves for some attributes but not
# others — the difference depends on how close the column header is to the
# value within the HTML markup structure.
QUESTION = "What is the battery life of the WH-500?"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

SEPARATOR = "=" * 60


# ============================================================
# Main comparison
# ============================================================

def run_comparison(data_dir):
    html_path = Path(data_dir) / "product-specs.html"
    raw_html = html_path.read_text(encoding="utf-8")

    # ============================================================
    # Approach 1: Raw HTML chunked as-is
    # ============================================================
    # This is what a naive pipeline does: read the file, pass it to the
    # chunker, embed whatever text comes out.
    #
    # The chunker sees the HTML source as a stream of characters. It splits
    # on double newlines (paragraph boundaries), which in an HTML file often
    # fall between tags rather than between meaningful content units. The
    # result is chunks that contain raw markup: "<td>8 hours</td>" or
    # "<td>Battery Life</td>\n<td>30 hours...</td>\n<td>8 hours</td>".
    #
    # The embedding captures the words "battery" and "hours" but loses the
    # relationship between those words and the column header ("Battery Life")
    # or the row context ("WH-500 Sport Headphones"). The structure that makes
    # the table interpretable is not in the text — it is in the HTML schema.
    raw_doc = {"filename": "product-specs.html (raw)", "text": raw_html}
    raw_chunks = chunk_document(raw_doc, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)

    # ============================================================
    # Approach 2: HTML converted to labeled rows before chunking
    # ============================================================
    # html_table_to_text.py converts each table row into a flat string:
    #   "Specification: Battery Life | WH-1000 Premium Headphones: 30 hours
    #    (ANC off), 20 hours (ANC on) | WH-500 Sport Headphones: 8 hours"
    #
    # Now the value "8 hours" is embedded alongside its attribute name
    # ("Battery Life") and its product name ("WH-500 Sport Headphones").
    # The retriever can find it, and the model can answer without guessing
    # which number belongs to which product.
    #
    # The key insight: we are NOT changing the chunker, the embedding model,
    # the retriever, or the generation model between these two approaches.
    # Only the input text changes. Any difference in answer quality comes
    # entirely from the parsing decision made before any of those steps run.
    # This is the article's claim made visible: the pipeline can lose meaning
    # before embeddings ever happen.
    parsed_text = html_table_to_text(raw_html)
    parsed_doc = {"filename": "product-specs.html (parsed)", "text": parsed_text}
    parsed_chunks = chunk_document(parsed_doc, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)

    # ============================================================
    # Two separate ChromaDB collections — one per approach
    # ============================================================
    # We use separate collections rather than a flag on one collection because
    # the article's point is that a parsing decision made BEFORE chunking
    # changes everything downstream. Embedding the raw HTML and the parsed
    # text into separate collections makes that visible — you can see the same
    # question retrieve different chunks depending on what was embedded.
    client = chromadb.Client(Settings(anonymized_telemetry=False))

    try:
        client.delete_collection("technova_raw_html")
        client.delete_collection("technova_parsed_html")
    except Exception:
        pass

    raw_collection = client.get_or_create_collection("technova_raw_html")
    parsed_collection = client.get_or_create_collection("technova_parsed_html")

    # ============================================================
    # Print header and embed both versions
    # ============================================================
    print(SEPARATOR)
    print("TechNova HTML Comparison — Part 5")
    print("Section: Structured HTML and Tables")
    print(SEPARATOR)
    print(f"\nQuestion: {QUESTION}\n")
    print(f"chunk_size={CHUNK_SIZE}   overlap={CHUNK_OVERLAP}")
    print()
    print("Embedding and storing both versions of product-specs.html…")
    print(f"  Raw HTML approach:    {len(raw_chunks)} chunk(s)")
    print(f"  Parsed text approach: {len(parsed_chunks)} chunk(s)")
    print()

    store_chunks(raw_collection, raw_chunks)
    store_chunks(parsed_collection, parsed_chunks)

    # ============================================================
    # Approach 1: Retrieve and generate from raw HTML
    # ============================================================
    print(SEPARATOR)
    print("Approach 1: Raw HTML (no preprocessing)")
    print(SEPARATOR)

    raw_retrieved = retrieve(raw_collection, QUESTION, n_results=1)
    raw_chunk_text = raw_retrieved[0]["text"] if raw_retrieved else "(nothing retrieved)"

    # Print the full retrieved chunk so the reader can see exactly what the
    # model was given. If the chunk contains raw markup like "<td>8 hours</td>",
    # note the absence of product name context around that value.
    print("\nRetrieved chunk (what the model sees):")
    print("-" * 40)
    print(raw_chunk_text[:400])
    if len(raw_chunk_text) > 400:
        print(f"  … ({len(raw_chunk_text) - 400} more characters)")
    print("-" * 40)
    print()

    raw_answer = generate_answer(QUESTION, raw_retrieved)
    print("Generated answer:")
    print(f"  {raw_answer}")
    print()

    # ============================================================
    # Approach 2: Retrieve and generate from parsed text
    # ============================================================
    print(SEPARATOR)
    print("Approach 2: Structure-preserving parsed text")
    print(SEPARATOR)

    parsed_retrieved = retrieve(parsed_collection, QUESTION, n_results=1)
    parsed_chunk_text = parsed_retrieved[0]["text"] if parsed_retrieved else "(nothing retrieved)"

    print("\nRetrieved chunk (what the model sees):")
    print("-" * 40)
    print(parsed_chunk_text[:400])
    if len(parsed_chunk_text) > 400:
        print(f"  … ({len(parsed_chunk_text) - 400} more characters)")
    print("-" * 40)
    print()

    parsed_answer = generate_answer(QUESTION, parsed_retrieved)
    print("Generated answer:")
    print(f"  {parsed_answer}")
    print()

    # ============================================================
    # Side-by-side summary
    # ============================================================
    print(SEPARATOR)
    print("Side-by-side summary")
    print(SEPARATOR)
    print()
    print(f"Question: {QUESTION}")
    print()

    print("Raw HTML — retrieved:")
    # Show just the first 120 chars of each retrieved chunk as a fingerprint
    print(f"  {raw_chunk_text[:120].replace(chr(10), ' ')} …")
    print()
    print("Parsed text — retrieved:")
    print(f"  {parsed_chunk_text[:120].replace(chr(10), ' ')} …")
    print()

    print("Raw HTML — answer:")
    print(f"  {raw_answer[:250]}")
    print()
    print("Parsed text — answer:")
    print(f"  {parsed_answer[:250]}")
    print()

    print(SEPARATOR)
    print("Takeaway")
    print(SEPARATOR)
    print()
    print("  The inputs to the model differed only in how product-specs.html")
    print("  was preprocessed before chunking. Same chunker. Same embedding")
    print("  model. Same retriever. Same generation model.")
    print()
    print("  The parsing decision — made before any of those steps ran —")
    print("  determined whether the retrieved chunk carried enough context")
    print("  for the model to answer correctly.")
    print()
    print("  This is the article's point: the pipeline can lose meaning before")
    print("  embeddings ever happen. Better chunking or a smarter retriever")
    print("  cannot recover structure that was discarded at parse time.")
    print()


if __name__ == "__main__":
    import os

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError(
            "OPENAI_API_KEY is not set. Export it before running:\n"
            "  export OPENAI_API_KEY=your-key-here"
        )

    if not Path(DATA_DIR).exists():
        raise FileNotFoundError(
            f"Data folder not found: {DATA_DIR}. "
            "This script expects the shared data/ folder at the repo root."
        )

    run_comparison(DATA_DIR)
