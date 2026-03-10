import os
from pathlib import Path
import threading
from typing import List, Optional, Sequence, Tuple

import faiss
import numpy as np
from huggingface_hub import InferenceClient
from pypdf import PdfReader

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

PDF_KNOWLEDGE_BASE =[
    "docs/policy_manual.pdf",
    "docs/overview.pdf",
    "docs/doc618.pdf",


]

# Prefer env-provided token; keep startup resilient when token is not set.
hf_token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
client = InferenceClient(provider="auto", api_key=hf_token)


def load_pdf(file_path: str) -> str:
    """Load a PDF and concatenate text from all pages."""
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """Split text into overlapping character chunks."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be >= 0 and < chunk_size")

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def _to_1d_embedding(response: Sequence) -> np.ndarray:
    """Normalize HF embedding output into a single 1D float32 vector."""
    arr = np.asarray(response, dtype=np.float32)
    if arr.ndim == 1:
        return arr
    if arr.ndim == 2:
        # For token-level outputs, mean-pool to a sentence embedding.
        return arr.mean(axis=0)
    raise ValueError(f"Unexpected embedding shape: {arr.shape}")


def embed_texts(texts: Sequence[str]) -> List[np.ndarray]:
    """Embed a list of strings using Hugging Face Inference API."""
    if not hf_token:
        raise RuntimeError("HF token not configured. Set HF_TOKEN or HUGGINGFACEHUB_API_TOKEN.")

    embeddings: List[np.ndarray] = []
    for text in texts:
        response = client.feature_extraction(text=text, model=EMBEDDING_MODEL)
        embeddings.append(_to_1d_embedding(response))
    return embeddings


def create_vector_db(embeddings: Sequence[np.ndarray]) -> faiss.IndexFlatL2:
    """Create a FAISS L2 index from 1D embeddings."""
    if not embeddings:
        raise ValueError("No embeddings provided to create_vector_db")

    matrix = np.asarray(embeddings, dtype=np.float32)
    if matrix.ndim != 2:
        raise ValueError(f"Embeddings must be a 2D matrix, got shape {matrix.shape}")

    dimension = matrix.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(matrix)
    return index


def build_vector_store(pdf_file: Path) -> Tuple[faiss.IndexFlatL2, List[str]]:
    """Build FAISS index and chunks from a single PDF."""
    pdf_text = load_pdf(str(pdf_file))
    pdf_chunks = chunk_text(pdf_text)
    embeddings = embed_texts(pdf_chunks)
    index = create_vector_db(embeddings)
    return index, pdf_chunks


def build_vector_store_from_pdfs(
    pdf_paths: List[str], base_dir: Path
) -> Tuple[Optional[faiss.IndexFlatL2], List[str]]:
    """Build FAISS index and combined chunks from all PDFs in the list."""
    all_chunks: List[str] = []
    all_embeddings: List[np.ndarray] = []

    for rel_path in pdf_paths:
        path = base_dir / rel_path
        if not path.exists():
            print(f"[rag] Warning: PDF not found, skipping: {path}")
            continue
        try:
            pdf_text = load_pdf(str(path))
            pdf_chunks = chunk_text(pdf_text)
            if not pdf_chunks:
                continue
            embeddings = embed_texts(pdf_chunks)
            all_chunks.extend(pdf_chunks)
            all_embeddings.extend(embeddings)
        except Exception as exc:
            print(f"[rag] Warning: Failed to load {path}: {exc}")
            continue

    if not all_embeddings or not all_chunks:
        return None, []

    index = create_vector_db(all_embeddings)
    return index, all_chunks


def retrieve(
    query: str, index: Optional[faiss.IndexFlatL2], chunks: Sequence[str], k: int = 3
) -> List[str]:
    """Retrieve top-k relevant chunks for a query."""
    _initialize_rag_once()

    # Callers may pass stale imported globals from `from rag import vector_db, chunks`.
    # Fall back to module state so retrieval still works after lazy initialization.
    if index is None:
        index = vector_db
    if not chunks:
        chunks = rag_chunks

    if index is None or not chunks:
        return []

    if k <= 0:
        return []

    query_embedding = embed_texts([query])[0]
    query_vector = np.asarray([query_embedding], dtype=np.float32)

    top_k = min(k, len(chunks))
    _distances, indices = index.search(query_vector, top_k)
    return [chunks[i] for i in indices[0] if 0 <= i < len(chunks)]


_base_dir = Path(__file__).resolve().parents[1]
_init_lock = threading.Lock()
_initialized = False

# Keep these names for compatibility with callers importing `vector_db, chunks`.
vector_db: Optional[faiss.IndexFlatL2] = None
rag_chunks: List[str] = []
chunks = rag_chunks


def _initialize_rag_once() -> None:
    """Build RAG index lazily so app startup is not blocked by PDF embedding work."""
    global _initialized, vector_db, rag_chunks, chunks
    if _initialized:
        return

    with _init_lock:
        if _initialized:
            return

        if not hf_token:
            print("[rag] Warning: HF token missing. RAG retrieval disabled.")
            vector_db = None
            rag_chunks = []
            chunks = rag_chunks
            _initialized = True
            return

        try:
            vector_db, rag_chunks = build_vector_store_from_pdfs(PDF_KNOWLEDGE_BASE, _base_dir)
            chunks = rag_chunks
            if vector_db is None:
                print("[rag] Warning: No PDFs could be loaded. RAG retrieval will return empty results.")
        except Exception as exc:
            # Keep app functionality alive even when RAG setup fails.
            print(f"[rag] Warning: RAG initialization failed: {exc}")
            vector_db = None
            rag_chunks = []
            chunks = rag_chunks
        finally:
            _initialized = True