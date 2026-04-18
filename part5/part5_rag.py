"""
part5_rag.py

Companion to Part 5 of RAG in Practice — "Build a RAG System in Practice"
Sections: All four document categories — short policy docs, procedural
          troubleshooting, versioned changelogs, and structured HTML/tables.

This script is the baseline RAG pipeline for the TechNova support corpus.
Run it to see:
  - how many chunks each of the five documents produces at the default size
  - what the pipeline retrieves for three representative questions
  - where answers feel solid (short policy docs, structured FAQs) and where
    they feel strained (Bluetooth procedure, changelog version blending,
    HTML attribute lookup without parsed context)

Experiment with:
  - chunk_size in the chunking loop near the bottom: smaller values force
    more splits and can fracture procedures; larger values keep context
    intact but broaden retrieval and add noise
  - n_results inside retrieve(): more retrieved chunks give the model more
    context — watch whether answers improve or become vaguer
  - the three ask() questions at the bottom: replace them with your own to
    see how the corpus handles queries the article did not cover

The two companion scripts show specific failure modes in more detail:
  - inspect_chunks.py              — see exactly where chunk boundaries fall
  - compare_html_raw_vs_parsed.py — see the HTML parsing decision's effect
"""

import os
import re
import logging
from pathlib import Path
import openai
import chromadb
from chromadb.config import Settings

# Silence ChromaDB 0.6.3's telemetry error messages.
#
# In this ChromaDB version, chromadb/telemetry/product/posthog.py calls
# posthog.capture(user_id, name, properties) with three positional args.
# posthog >=3.0 (which pip resolves transitively) changed capture() to take
# one positional argument, so every call raises TypeError. ChromaDB catches
# it and emits "Failed to send telemetry event ..." via logger.error().
#
# anonymized_telemetry=False (set on the Client below) prevents the actual
# network send, but the capture() call is still invoked first, so the error
# is raised and logged regardless. Suppressing this logger is the reliable
# way to clean the output. Zero functional impact — no data was being sent.
logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.CRITICAL)

# Path to shared sample data (one level up from this script)
DATA_DIR = str(Path(__file__).resolve().parent.parent / "data")

# Set the API key at module level so it is available when these functions
# are called from the companion scripts. The companion scripts import
# get_embeddings, retrieve, and generate_answer, all of which need this.
# If the key is not set, this line harmlessly sets api_key to None —
# the error only surfaces when an actual API call is made.
openai.api_key = os.getenv("OPENAI_API_KEY")

# ChromaDB in-memory client at module level so companion scripts can
# reuse it without creating a separate connection. Each companion script
# creates its own named collection rather than sharing the baseline one.
#
# anonymized_telemetry=False is passed explicitly because ChromaDB's env-var
# path does not always suppress telemetry reliably across versions; passing
# Settings at client construction is the authoritative way to disable it.
chroma_client = chromadb.Client(Settings(anonymized_telemetry=False))


# load_documents: reads every .md and .html file from the data directory.
#
# Sorting the paths gives consistent ordering across runs — chunk_0 will
# always be the same document, which matters when you compare runs with
# different chunk sizes. The function is intentionally agnostic about
# document shape: it does not know whether a file is policy prose, a
# numbered procedure, or an HTML table. That uniformity is exactly what
# this article uses to show where the pipeline strains.
def load_documents(data_dir):
    """Load all documents from the data directory."""
    documents = []
    for filepath in sorted(Path(data_dir).iterdir()):
        if filepath.suffix in [".md", ".html"]:
            text = filepath.read_text(encoding="utf-8")
            documents.append({
                "filename": filepath.name,
                "text": text
            })
    return documents


# chunk_document: the simplest useful chunker — split on paragraph
# boundaries (double newlines), then enforce a soft size ceiling.
#
# Why this strategy for teaching:
#   - It is naive enough that you can watch it fail (see inspect_chunks.py)
#   - It is realistic enough that many production teams start here
#   - It makes the "chunk boundaries vs. chunk size" point visible
#
# One preprocessing step before the split: numbered list items (lines that
# begin with "N. ") are promoted to their own paragraph-boundary sections by
# inserting a blank line before each. In troubleshooting-guide.md, the 5
# Bluetooth reset steps are formatted as a single paragraph with single-newline
# separators — they look like one section to a \n\n splitter. Promoting each
# step to its own section lets the chunker treat them as discrete units, which
# is what the document author intended and what the article uses to show the
# procedural-split failure.
#
# This promotion is targeted: the pattern \n(\d+\. ) only matches numbered
# list markers. HTML markup, prose paragraphs, and changelog bullet points
# contain no such patterns, so their chunking behavior is unchanged.
#
# The failure that becomes visible: steps 1–2 land in chunk N, steps 3–4 in
# chunk N+1, and step 5 in chunk N+2. If retrieval surfaces only chunk N, the
# user gets steps 1–2 — the setup steps, not the reset action. The generated
# answer sounds plausible because two steps form a coherent sequence, but the
# reset never completes because step 3 (hold the power button) is missing.
#
# The overlap parameter carries the last N words from one chunk into the next
# to reduce hard context cuts. For prose this helps. For procedures it does not
# fix a split at the wrong semantic boundary — once steps 3–4 are in a separate
# chunk, overlap from chunk N carries steps 1–2 forward but not steps 3–4 back.
def chunk_document(doc, chunk_size=500, overlap=50):
    """Recursive-style chunking: split on paragraph boundaries first,
    with numbered-step promotion so procedures split at step boundaries."""
    text = doc["text"]
    filename = doc["filename"]

    # Promote each numbered list item to its own paragraph-boundary section.
    # This inserts a blank line before "1. ", "2. ", etc. so the \n\n splitter
    # below treats each step as a discrete unit rather than lumping the whole
    # numbered sequence into one ~295-char atomic block.
    # Only affects documents with numbered lists (troubleshooting-guide.md).
    # HTML, changelogs, and policy prose are unchanged.
    text = re.sub(r"\n(\d+\. )", r"\n\n\1", text)

    # We split on double newlines first because that's where the document
    # author placed semantic boundaries (paragraphs, list items, section
    # breaks). This usually gives us clean-ish chunks — but notice what
    # happens to the numbered procedure in troubleshooting-guide.md.
    # Paragraph boundaries and procedure boundaries are NOT the same thing.
    sections = text.split("\n\n")

    chunks = []
    current_chunk = ""

    for section in sections:
        # If adding this section would exceed chunk_size, save current and start new
        if len(current_chunk) + len(section) > chunk_size and current_chunk:
            chunks.append({
                "text": current_chunk.strip(),
                "source": filename
            })
            # Overlap: keep the last part of the current chunk
            words = current_chunk.strip().split()
            overlap_text = " ".join(words[-overlap:]) if len(words) > overlap else current_chunk.strip()
            current_chunk = overlap_text + "\n\n" + section
        else:
            current_chunk = current_chunk + "\n\n" + section if current_chunk else section

    # Don't forget the last chunk
    if current_chunk.strip():
        chunks.append({
            "text": current_chunk.strip(),
            "source": filename
        })

    return chunks


# get_embeddings: calls OpenAI's text-embedding-3-small model.
#
# This model maps text to a 1536-dimensional vector. Semantically similar
# text lands nearby in that space, which is what makes retrieval work.
# The model has no knowledge of your chunk boundaries — it embeds whatever
# text you give it. If a chunk contains half a Bluetooth procedure, the
# embedding represents "half a Bluetooth procedure." The retriever will
# then surface it for questions about the whole procedure. The model cannot
# tell the difference between a complete answer and a fragment.
def get_embeddings(texts):
    """Get embeddings from OpenAI API."""
    response = openai.embeddings.create(
        model="text-embedding-3-small",
        input=texts
    )
    return [item.embedding for item in response.data]


# store_chunks: embeds all chunks in one batch and writes them to ChromaDB.
#
# IDs are positional (chunk_0, chunk_1, …), stable within a run.
# Metadata carries the source filename so retrieval can tell you which
# document a chunk came from — but not which position within that document.
# That limitation becomes visible when you ask a version-specific question
# against the changelog: the retriever knows the chunk is from
# firmware-changelog.md, but it does not know which version entry it is.
def store_chunks(collection, all_chunks):
    """Store chunks with embeddings in ChromaDB."""
    texts = [chunk["text"] for chunk in all_chunks]
    sources = [chunk["source"] for chunk in all_chunks]
    ids = [f"chunk_{i}" for i in range(len(all_chunks))]

    embeddings = get_embeddings(texts)

    collection.add(
        documents=texts,
        embeddings=embeddings,
        metadatas=[{"source": s} for s in sources],
        ids=ids
    )
    return len(all_chunks)


# retrieve: converts the question to an embedding and asks ChromaDB for
# the n_results nearest chunks by cosine distance.
#
# This is pure vector similarity — no keyword matching, no BM25, no
# reranking. The retriever does not know what a "correct" answer looks
# like; it only knows which chunks are geometrically close to the question
# in embedding space.
#
# For well-separated topics (return policy vs. ANC settings) this works
# well. For near-duplicate content — three firmware versions that all
# mention "stability improvements" — it can surface multiple similar
# chunks and leave the model to sort out which is actually relevant.
# Without reranking or metadata filtering, there is no mechanism to prefer
# the most recent version.
def retrieve(collection, question, n_results=3):
    """Retrieve the most relevant chunks for a question."""
    question_embedding = get_embeddings([question])[0]

    results = collection.query(
        query_embeddings=[question_embedding],
        n_results=n_results
    )

    return [
        {"text": doc, "source": meta["source"]}
        for doc, meta in zip(results["documents"][0], results["metadatas"][0])
    ]


# generate_answer: sends retrieved chunks and the question to gpt-4o-mini.
#
# The system prompt constrains the model to the provided context — the
# standard RAG pattern for reducing hallucination. Notice what the model
# cannot do here: it cannot request more context, it cannot know whether
# the retrieved chunks are complete, and it cannot tell whether a procedure
# it received is missing steps. If retrieval hands it half a procedure,
# generation will often produce a fluent answer from that half. A fluent
# incomplete answer is harder to detect than a clearly wrong one.
def generate_answer(question, retrieved_chunks):
    """Generate an answer using retrieved context."""
    context = "\n\n---\n\n".join(
        f"[Source: {chunk['source']}]\n{chunk['text']}"
        for chunk in retrieved_chunks
    )

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a TechNova product support assistant. "
                    "Answer the customer's question using only the provided context. "
                    "If the context does not contain enough information, say so. "
                    "Cite the source document when possible."
                )
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}"
            }
        ]
    )

    return response.choices[0].message.content


# ask: the full pipeline in one call — retrieve, then generate, then print.
#
# This function references the module-level `collection` variable, which is
# created inside the __main__ block below. It is a convenience wrapper for
# running the script standalone. The companion scripts (inspect_chunks.py,
# compare_html_raw_vs_parsed.py) call retrieve() and generate_answer()
# directly with their own collections, rather than using ask().
def ask(question):
    """Full pipeline: retrieve context, then generate answer."""
    chunks = retrieve(collection, question)
    answer = generate_answer(question, chunks)

    print(f"Question: {question}\n")
    print(f"Answer: {answer}\n")
    print("Retrieved from:")
    for chunk in chunks:
        print(f"  - {chunk['source']}: {chunk['text'][:80]}...")
    print()


if __name__ == "__main__":
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

    # Reset collection so reruns start clean — no duplicate chunks from previous runs
    try:
        chroma_client.delete_collection("technova_support")
    except Exception:
        pass
    collection = chroma_client.get_or_create_collection(name="technova_support")

    print("=" * 60)
    print("TechNova RAG Baseline — Part 5")
    print("Loading 5 documents, answering 3 questions.")
    print("=" * 60)
    print()

    docs = load_documents(DATA_DIR)

    # --- Experiment ---
    # Change chunk_size here and rerun to see how chunk count and answer
    # quality shift. Try 200: shorter chunks, more of them, higher chance
    # of splitting procedures and changelog entries. Try 1500: fewer chunks,
    # procedures stay intact, but retrieval may surface too much irrelevant
    # context for short questions.
    # Run inspect_chunks.py alongside this to see exactly where the
    # boundaries fall for whichever size you choose.
    all_chunks = []
    for doc in docs:
        chunks = chunk_document(doc)
        all_chunks.extend(chunks)
        print(f"{doc['filename']}: {len(chunks)} chunks")

    total = store_chunks(collection, all_chunks)
    print(f"\nTotal chunks stored: {total}\n")

    # --- Experiment ---
    # Replace these questions with your own to explore the TechNova corpus.
    # Suggestions to try:
    #   "Does the WH-500 support multipoint Bluetooth connections?"
    #   "What should I do if my headphones won't charge?"
    #   "What firmware version introduced LDAC support?"
    #   "What is the weight of the WH-500?"
    # For each, watch which source document gets retrieved and whether the
    # answer cites the right information or blends from adjacent chunks.
    ask("What is TechNova's return policy?")
    ask("My WH-1000 keeps disconnecting from Bluetooth. What should I do?")
    ask("What changed in the latest firmware update?")
