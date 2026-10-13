import os
import re
import shutil
import uuid
from pathlib import Path
from typing import List

import chromadb
import fitz
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from groq import Groq
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from starlette.requests import Request

from prompts import PROMPT_TEMPLATES, TEST_QUESTIONS

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "documents"
UPLOAD_DIR = BASE_DIR / "uploads"
CHROMA_DIR = BASE_DIR / "chroma_db"
for folder in (DOCS_DIR, UPLOAD_DIR, CHROMA_DIR):
    folder.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="AI Knowledge Assistant", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# First run downloads this model from Hugging Face; allow time for the download.
embedding_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
collection = chroma_client.get_or_create_collection(
    name="knowledge_documents",
    metadata={"hnsw:space": "cosine"}
)

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md"}
CHUNK_SIZE = 850
CHUNK_OVERLAP = 150


class AskRequest(BaseModel):
    question: str
    prompt_type: str = "Role-based"
    top_k: int = 3


class EvaluateRequest(BaseModel):
    questions: List[str] = TEST_QUESTIONS


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        pages = []
        with fitz.open(path) as pdf:
            for page_number, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()
                if text:
                    pages.append(f"[Page {page_number}]\n{text}")
        return "\n\n".join(pages)
    return path.read_text(encoding="utf-8", errors="replace")


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE,
                      overlap: int = CHUNK_OVERLAP) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def index_document(path: Path, display_name: str | None = None) -> int:
    text = extract_text(path)
    chunks = split_into_chunks(text)
    if not chunks:
        raise ValueError("No readable text was found in this document.")
    # Re-uploading the same filename replaces its older indexed chunks.
    existing = collection.get(where={"source": display_name or path.name})
    if existing and existing.get("ids"):
        collection.delete(ids=existing["ids"])
    vectors = embedding_model.encode(chunks, normalize_embeddings=True).tolist()
    source = display_name or path.name
    ids = [f"{uuid.uuid4().hex}_{i}" for i in range(len(chunks))]
    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=vectors,
        metadatas=[{"source": source, "chunk": i + 1} for i in range(len(chunks))]
    )
    return len(chunks)


def index_sample_documents():
    if collection.count() > 0:
        return
    for path in sorted(DOCS_DIR.iterdir()):
        if path.is_file() and path.suffix.lower() in ALLOWED_EXTENSIONS:
            try:
                index_document(path, path.name)
            except Exception as exc:
                print(f"Skipping sample {path.name}: {exc}")


@app.on_event("startup")
def startup():
    index_sample_documents()


def retrieve(question: str, top_k: int = 3):
    if collection.count() == 0:
        return []
    query_vector = embedding_model.encode([question], normalize_embeddings=True).tolist()[0]
    result = collection.query(
        query_embeddings=[query_vector],
        n_results=min(max(top_k, 1), 3, collection.count()),
        include=["documents", "metadatas", "distances"]
    )
    items = []
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    for doc, meta, distance in zip(docs, metas, distances):
        items.append({
            "text": doc,
            "source": meta.get("source", "Unknown"),
            "chunk": meta.get("chunk", "?"),
            "distance": round(float(distance), 4),
            # Cosine distance is 1 - cosine similarity for this collection.
            "similarity": round(max(0.0, min(1.0, 1.0 - float(distance))), 4)
        })
    return items


def build_context(chunks):
    if not chunks:
        return "No relevant document chunks were found."
    return "\n\n".join(
        f"[Source: {item['source']}, chunk {item['chunk']}]\n{item['text']}"
        for item in chunks
    )


def generate_answer(question: str, context: str, prompt_type: str):
    template = PROMPT_TEMPLATES.get(prompt_type)
    if not template:
        raise HTTPException(status_code=400, detail="Unknown prompting technique.")
    prompt = template.format(context=context, question=question)
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return (
            "LLM API key is not configured. The retrieved document context is shown "
            "below so you can still inspect the evidence. Add GROQ_API_KEY to .env "
            "and restart the server to enable generated answers.\n\n"
            + context[:2500]
        ), prompt
    try:
        client = Groq(api_key=api_key)
        response = client.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=800,
        )
        return response.choices[0].message.content or "No answer was returned.", prompt
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"LLM request failed: {exc}. Check your API key, model name, and connection."
        )


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"sample_count": collection.count()}
    )


@app.get("/api/documents")
def list_documents():
    results = collection.get(include=["metadatas"])
    counts = {}
    for meta in results.get("metadatas") or []:
        source = meta.get("source", "Unknown")
        counts[source] = counts.get(source, 0) + 1
    return {
        "total_chunks": collection.count(),
        "documents": [{"name": name, "chunks": count} for name, count in sorted(counts.items())]
    }


@app.post("/api/upload")
async def upload_documents(files: List[UploadFile] = File(...)):
    output = []
    for upload in files:
        filename = Path(upload.filename or "upload.txt").name
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            output.append({"filename": filename, "ok": False, "message": "Only PDF, TXT, and MD files are supported."})
            continue
        target = UPLOAD_DIR / f"{uuid.uuid4().hex}_{filename}"
        try:
            content = await upload.read()
            if not content:
                raise ValueError("The selected file is empty.")
            target.write_bytes(content)
            chunks = index_document(target, filename)
            output.append({"filename": filename, "ok": True, "chunks": chunks, "message": f"Indexed {chunks} chunks."})
        except Exception as exc:
            output.append({"filename": filename, "ok": False, "message": str(exc)})
        finally:
            await upload.close()
    return {"results": output, "total_chunks": collection.count()}


@app.post("/api/ask")
def ask(payload: AskRequest):
    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Please enter a question.")
    chunks = retrieve(question, payload.top_k)
    context = build_context(chunks)
    answer, used_prompt = generate_answer(question, context, payload.prompt_type)
    return {
        "question": question,
        "prompt_type": payload.prompt_type,
        "answer": answer,
        "retrieved_chunks": chunks,
        "prompt": used_prompt
    }


@app.post("/api/evaluate")
def evaluate(payload: EvaluateRequest):
    questions = [q.strip() for q in payload.questions if q.strip()]
    if len(questions) != 5:
        raise HTTPException(status_code=400, detail="Provide exactly five non-empty questions.")
    results = []
    for index, question in enumerate(questions, start=1):
        chunks = retrieve(question, 3)
        context = build_context(chunks)
        for technique in ("Zero-shot", "Few-shot", "Role-based"):
            answer, _ = generate_answer(question, context, technique)
            results.append({
                "question_number": index,
                "question": question,
                "technique": technique,
                "answer": answer,
                "sources": list(dict.fromkeys(item["source"] for item in chunks)),
                "accuracy": None,
                "clarity": None,
                "relevance": None
            })
    return {
        "results": results,
        "note": "Rate each answer from 1–5 against the retrieved context. Scores are intentionally left blank rather than fabricated."
    }


@app.get("/api/health")
def health():
    return {"status": "ok", "indexed_chunks": collection.count(), "llm_configured": bool(os.getenv("GROQ_API_KEY", "").strip())}
