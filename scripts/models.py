#!/usr/bin/env python3
"""Model loading helpers for indexing."""

from __future__ import annotations

import sys
from pathlib import Path

from fastembed import SparseTextEmbedding
from sentence_transformers import SentenceTransformer

from app.config import MODEL_CACHE_DIR, SPARSE_MODEL_NAME

# Add parent directory to path for app imports
sys.path.append(str(Path(__file__).parent.parent))


def load_dense_model() -> SentenceTransformer:
    """Load dense embedding model from local cache."""

    return SentenceTransformer("all-MiniLM-L6-v2", cache_folder=MODEL_CACHE_DIR)


def load_sparse_model() -> SparseTextEmbedding:
    """Load sparse embedding model."""

    return SparseTextEmbedding(model_name=SPARSE_MODEL_NAME)
