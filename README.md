# RAG in Practice — Sample Data

Sample documents for the [RAG Article Series](https://dev.to/gursharansingh/series/37906) on DEV.

These files represent a fictional product support library for **TechNova**, a fictional audio products company. The series uses them to demonstrate chunking, retrieval, and generation decisions in a RAG pipeline.

Part 4 uses these files as reading examples; Part 5 loads them in code from the `data/` folder. Each part's code lives in its own directory (e.g. `part5/`).

## Files

| File | Purpose in the series |
|---|---|
| `data/return-policy.md` | Short document (~250 words) — tests whether chunking is even necessary |
| `data/warranty-terms.md` | Clean structure with headers — recursive chunking handles it without surprises |
| `data/troubleshooting-guide.md` | Numbered procedures under section headers — shows what breaks with fixed-size chunking |
| `data/firmware-changelog.md` | Three version entries — creates a retrieval trap when versions are chunked together |
| `data/product-specs.html` | HTML comparison table — demonstrates the parsing challenge before chunking |

## Articles that use these files

- **[Part 4: Chunking, Retrieval, and the Decisions That Break RAG](https://dev.to/gursharansingh/rag-in-practice-part-4-chunking-retrieval-and-the-decisions-that-break-rag-39ig)** — references the files conceptually
- **[Part 5: Build a RAG System in Practice](https://dev.to/gursharansingh/rag-in-practice-part-5-build-a-rag-system-in-practice-4knd)** — loads and processes these files in code → [`part5/`](part5/)

## Note

These are fictional documents created for teaching purposes. TechNova is not a real company. Product names, specifications, and policies are entirely made up.
