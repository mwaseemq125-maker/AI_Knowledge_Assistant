# AI Knowledge Assistant

A complete FastAPI project for document Q&A, semantic retrieval, and prompt-engineering evaluation.

## Features
- PDF, TXT, Markdown uploads
- Sentence Transformer embeddings (`all-MiniLM-L6-v2`)
- Persistent ChromaDB cosine-distance collection
- Top-three semantic retrieval with distance and similarity display
- Groq-powered grounded answers (optional API key)
- Zero-shot, few-shot, role-based prompt templates
- Five standard questions; 15 answers; manual 1–5 evaluation and CSV export
- Five included sample documents
- Responsive dark dashboard UI

## Ubuntu / VS Code setup

```bash
cd ai-knowledge-assistant
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add your Groq key to enable generated answers. You can obtain a key from the Groq developer console. Never commit `.env`.

Run:

```bash
uvicorn main:app --reload --port 8050
```

Open http://127.0.0.1:8050

On first startup, Sentence Transformers downloads the embedding model, so the first run needs internet and may take several minutes. The five included documents are indexed automatically on a fresh ChromaDB store.

## API endpoints
- `GET /api/health` — app status
- `GET /api/documents` — indexed sources and chunk counts
- `POST /api/upload` — multipart upload (`files`)
- `POST /api/ask` — JSON: `{"question":"What are embeddings?","prompt_type":"Role-based","top_k":3}`
- `POST /api/evaluate` — JSON with exactly five questions; runs 15 prompt answers

## Prompt evaluation
The evaluation endpoint uses the same retrieved context for all three prompt templates for each question. In the UI, score each answer from 1 to 5:
- Accuracy: Is each claim supported by the retrieved chunks?
- Clarity: Is the answer easy to understand?
- Relevance: Does it answer the question directly?

Scores are intentionally manual so the project does not claim fabricated accuracy results. Export the completed rubric to CSV.

## Semantic vs keyword search
Keyword search relies on terms or token matches and can miss synonyms. Semantic search embeds queries and chunks into vectors and ranks them by semantic proximity. This project uses ChromaDB cosine distance; lower distance means closer vectors. The displayed similarity is `1 - cosine_distance`, rounded for readability. Similarity is a ranking signal, not proof of factual correctness.

## Notes
- ChromaDB data persists in `chroma_db/`; uploaded source files persist in `uploads/`.
- Only upload documents you are allowed to process.
- Scanned PDFs with no embedded text need OCR, which is not included in this version.
- For deployment, use a persistent volume for `chroma_db`, configure `GROQ_API_KEY` as a secret, and account for the model's disk/RAM requirements.
