"""
inspect_chunks.py

Companion to Part 5 of RAG in Practice — "Build a RAG System in Practice"
Section: Procedural Troubleshooting Documents (and all four document categories)

This script shows exactly where the chunker splits each TechNova document —
no embeddings, no API calls, no cost. Run it as many times as you like while
experimenting with chunk sizes.

Run it to see:
  - how many chunks each of the five documents becomes at the default size
  - exactly where each chunk begins and ends (chunk boundaries shown explicitly)
  - where the Bluetooth reset procedure splits in troubleshooting-guide.md —
    steps 1–2 land in one chunk, steps 3–4 in the next, step 5 in a third

The script prints full chunk content for troubleshooting-guide.md so you can
read every line and find the split point yourself. For the other four files it
prints an 80-character preview per chunk — enough to see what each chunk is
about without scrolling through everything.

Experiment with:
  - CHUNK_SIZE (default 500): try 200 to force more aggressive splits, try
    1500 to see the Bluetooth procedure stay in one chunk. Watch how chunk
    count changes across all five files — the effect is uneven, because
    document structure varies.
  - CHUNK_OVERLAP (default 50): increasing this carries more text from one
    chunk into the next. Does it fix the Bluetooth procedure split? Run it
    and see. Overlap can mask a structural problem but does not resolve it —
    the procedure unit is still divided, the duplicate content just spans
    the boundary.
  - FULL_CONTENT_FILES: add any filename to this set to see its full chunk
    content instead of previews. Try "firmware-changelog.md" to see how
    version entries land across chunks.
"""

import sys
from pathlib import Path

# Add the part5 directory to the path so this script can be run from
# anywhere — the repo root, the part5 directory, or an IDE.
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import the same load_documents and chunk_document functions that
# part5_rag.py uses as its baseline. We do not re-implement chunking here.
# If you change chunk_document in part5_rag.py, the inspection output here
# changes automatically — the two scripts stay in sync.
from part5_rag import load_documents, chunk_document, DATA_DIR

# ============================================================
# Configuration — these are the knobs to experiment with
# ============================================================

# --- Experiment ---
# Change CHUNK_SIZE to 200 and rerun: the Bluetooth procedure in
# troubleshooting-guide.md splits more aggressively. Change it to 1500:
# the whole troubleshooting section may stay in one chunk, but then
# ask yourself whether retrieval still returns the right thing for a
# specific question — large chunks broaden the semantic signal.
# The article's point: chunk SIZE and chunk BOUNDARIES are different
# problems. Changing the number does not change the strategy.
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50

# Files whose chunks are printed in full rather than as 80-char previews.
# troubleshooting-guide.md is here because that is where the procedural
# split lives — you need to read every line to find the exact split point.
# Add "firmware-changelog.md" to see how version boundaries land.
FULL_CONTENT_FILES = {"troubleshooting-guide.md"}


# ============================================================
# Chunk inspection
# ============================================================

def inspect_all_documents(data_dir):
    docs = load_documents(data_dir)

    print("=" * 60)
    print("TechNova Chunk Inspector — Part 5")
    print(f"chunk_size={CHUNK_SIZE}   overlap={CHUNK_OVERLAP}")
    print(f"Full content printed for: {FULL_CONTENT_FILES}")
    print("=" * 60)
    print()

    for doc in docs:
        filename = doc["filename"]
        chunks = chunk_document(doc, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)

        print("=" * 60)
        print(f"  File:         {filename}")
        print(f"  Total chunks: {len(chunks)}")
        print("=" * 60)

        for i, chunk in enumerate(chunks):
            chunk_num = i + 1
            total = len(chunks)
            char_count = len(chunk["text"])

            print(f"\n  ── Chunk {chunk_num} of {total}  ({char_count} chars) ──")

            if filename in FULL_CONTENT_FILES:
                # Print every line of this chunk so the reader can see exactly
                # where the content was cut. For troubleshooting-guide.md, this
                # lets you identify the specific step where the Bluetooth
                # procedure was split — if it was split at all.
                print()
                for line in chunk["text"].splitlines():
                    print(f"    {line}")
                print()
            else:
                # For shorter or policy-style documents, a preview is enough
                # to confirm what each chunk contains. The full content is not
                # needed to make the article's point for these files.
                preview = chunk["text"][:80].replace("\n", " ")
                print(f"    Preview: {preview}…")

            # Show a visible boundary between consecutive chunks so the reader
            # can see exactly where one chunk ends and the next begins.
            # This boundary is the thing that matters for retrieval: if a user's
            # question spans this line, retrieval may only surface one side.
            if i < len(chunks) - 1:
                print()
                print("  " + "·" * 56)
                print(f"  ↑ chunk {chunk_num} ends here  ·  chunk {chunk_num + 1} begins below ↓")
                print("  " + "·" * 56)

        print()

    # ============================================================
    # Summary: Where did the Bluetooth procedure split?
    # ============================================================
    # The article describes a "half-fix": a user asks how to fix a Bluetooth
    # disconnection problem, retrieval returns only part of the 5-step reset
    # procedure, and the generated answer sounds complete because a partial
    # step sequence is still grammatically coherent.
    #
    # With the default settings (chunk_size=500, overlap=50), the chunker
    # promotes each numbered step to its own paragraph-boundary section, then
    # accumulates them with overlap until chunk_size is reached. The result
    # is a 3-chunk split across the Bluetooth procedure:
    #   Chunk N:   steps 1–2 (the setup steps: open Bluetooth, forget device)
    #   Chunk N+1: steps 3–4 (the reset action: hold power button, re-pair)
    #   Chunk N+2: step 5  ("Wait for 'Connected' confirmation before playing audio")
    #
    # If retrieval surfaces only chunk N, the user gets steps 1 and 2 — the
    # preparatory steps — but misses step 3, which is the actual reset action
    # (holding the power button for 7 seconds). Steps 1–2 form a plausible-
    # looking sequence: "Open Bluetooth settings, forget the device." That
    # sounds like a complete troubleshooting response. Step 3 is never seen.
    #
    # The split is structural and deterministic: the same settings produce
    # the same split every run.
    print("=" * 60)
    print("Summary: Bluetooth Procedure Check")
    print("=" * 60)
    print()

    troubleshooting_doc = next(
        (d for d in docs if d["filename"] == "troubleshooting-guide.md"), None
    )

    if troubleshooting_doc is None:
        print("  troubleshooting-guide.md not found in data directory.")
        return

    chunks = chunk_document(
        troubleshooting_doc, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP
    )

    # The Bluetooth section begins with "If your TechNova headphones will not
    # connect…follow these steps:" and the steps are numbered 1–5. We look for
    # the specific markers for steps 1 and 5 to determine whether they landed
    # in the same chunk. Step 1 starts with "1. Open Settings" (unique to this
    # section). Step 5 contains "Wait for" and "Connected".
    step1_chunk = None
    step5_chunk = None

    for i, chunk in enumerate(chunks):
        text = chunk["text"]
        # Step 1 of the Bluetooth reset: unique enough to identify this section
        if "1. Open Settings" in text and step1_chunk is None:
            step1_chunk = i + 1  # 1-indexed for readability
        # Step 5 of the Bluetooth reset: "Wait for "Connected" confirmation"
        if "5. Wait for" in text and step5_chunk is None:
            step5_chunk = i + 1

    if step1_chunk is None:
        print("  Could not locate the Bluetooth procedure (step 1) in any chunk.")
        print("  Check that troubleshooting-guide.md is in the data directory.")
    elif step5_chunk is None:
        print(f"  Found step 1 in chunk {step1_chunk}, but could not locate step 5.")
    elif step1_chunk == step5_chunk:
        print(f"  The Bluetooth reset procedure (steps 1–5) is entirely in chunk {step1_chunk}.")
        print()
        print("  With CHUNK_SIZE={}, the procedure stayed intact.".format(CHUNK_SIZE))
        print("  This can happen if CHUNK_OVERLAP was reduced below ~43 words")
        print("  (~215 chars), which prevents the second-pass line split from")
        print("  triggering. The default overlap of 50 words is needed to expose")
        print("  the split. Try restoring CHUNK_OVERLAP=50 and rerunning.")
    else:
        print(f"  Step 1 of the Bluetooth procedure is in chunk {step1_chunk}.")
        print(f"  Step 5 of the Bluetooth procedure is in chunk {step5_chunk}.")
        print()
        print("  This is the 'half-fix' the article describes.")
        print()
        print("  If retrieval surfaces only chunk {}, the user gets steps 1".format(step1_chunk))
        print("  through some middle step — enough to look like a complete answer.")
        print("  The step that actually completes the reset (step 5) is in")
        print(f"  chunk {step5_chunk}, which may never be retrieved for this question.")
        print()
        print("  A response that cites steps 1–2 confidently still sounds")
        print("  authoritative. The user follows the partial steps, the reset")
        print("  does not complete, and they conclude the headphones are broken.")
        print("  That is worse than a clearly wrong answer, because it is not")
        print("  obviously wrong.")

    print()
    print("  To experiment:")
    print(f"  - CHUNK_SIZE=200  → more splits, procedure breaks earlier")
    print(f"  - CHUNK_SIZE=1500 → procedure stays together, but ask whether")
    print(f"    large chunks still retrieve the right content for short questions")
    print(f"  - CHUNK_OVERLAP=100 → does more overlap fix the split, or just")
    print(f"    add duplicate text around the boundary?")
    print()


if __name__ == "__main__":
    if not Path(DATA_DIR).exists():
        raise FileNotFoundError(
            f"Data folder not found: {DATA_DIR}. "
            "This script expects the shared data/ folder at the repo root."
        )

    inspect_all_documents(DATA_DIR)
