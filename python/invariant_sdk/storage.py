"""
sdk/storage.py — Storage and Embedding Components
"""

import sqlite3
import pickle
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

# ============================================================================
# EMBEDDINGS
# ============================================================================

class EmbeddingProvider:
    def __init__(self, dim: int = 32):
        self.dim = dim
    def encode(self, text: str) -> List[float]:
        raise NotImplementedError
# Default embedding model (can be overridden)
DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"


class RealEmbeddings(EmbeddingProvider):
    """
    Embeddings using sentence-transformers.
    
    The model is configurable - pass any HuggingFace sentence-transformers
    model name to customize for your domain.
    """
    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL):
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
            super().__init__(dim=self.model.get_sentence_embedding_dimension())
        except ImportError:
            raise ImportError(
                "sentence-transformers required for embeddings. "
                "Install with: pip install sentence-transformers"
            )
    
    def encode(self, text: str) -> List[float]:
        return self.model.encode(text).tolist()


def get_embedder(model_name: str = DEFAULT_EMBEDDING_MODEL) -> EmbeddingProvider:
    """
    Get an embedding provider.
    
    Args:
        model_name: HuggingFace model name for sentence-transformers.
                    Default: 'all-MiniLM-L6-v2' (fast, good quality).
                    Alternatives: 'all-mpnet-base-v2' (higher quality),
                                  'paraphrase-multilingual-MiniLM-L12-v2' (multilingual)
    Returns:
        RealEmbeddings instance.
    """
    return RealEmbeddings(model_name)

def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if len(v1) != len(v2): return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    return max(0.0, dot)

# ============================================================================
# BLOCK STORE (SQLite)
# ============================================================================

class BlockStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path))
        self._init_db()
    
    def _init_db(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS blocks (
                id TEXT PRIMARY KEY,
                text TEXT,
                content TEXT,
                source TEXT,
                position INTEGER,
                timestamp TEXT
            )
        """)
        self.conn.commit()
    
    def save(self, block_id: str, text: str, content: str, 
             source: str, position: int, timestamp: str = ""):
        self.conn.execute("""
            INSERT OR REPLACE INTO blocks 
            (id, text, content, source, position, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (block_id, text, content, source, position, timestamp))
        self.conn.commit()
    
    def get(self, block_id: str) -> Optional[dict]:
        cur = self.conn.execute("SELECT * FROM blocks WHERE id = ?", (block_id,))
        row = cur.fetchone()
        if row:
            return {
                "id": row[0], "text": row[1], "content": row[2],
                "source": row[3], "position": row[4], "timestamp": row[5]
            }
        return None
    
    def get_all(self) -> List[dict]:
        cur = self.conn.execute("SELECT * FROM blocks ORDER BY source, position")
        return [{
            "id": row[0], "text": row[1], "content": row[2],
            "source": row[3], "position": row[4], "timestamp": row[5]
        } for row in cur.fetchall()]
    
    def delete_by_source(self, source: str) -> int:
        cur = self.conn.execute("SELECT COUNT(*) FROM blocks WHERE source = ?", (source,))
        count = cur.fetchone()[0]
        self.conn.execute("DELETE FROM blocks WHERE source = ?", (source,))
        self.conn.commit()
        return count
    
    def get_ids_by_source(self, source: str) -> List[str]:
        cur = self.conn.execute("SELECT id FROM blocks WHERE source = ?", (source,))
        return [row[0] for row in cur.fetchall()]

# ============================================================================
# VECTOR STORE
# ============================================================================

# Storage format version - increment when changing ID format
_VECTOR_STORE_VERSION = 1


class VectorStore:
    """
    Persistent vector storage using pickle.
    
    Note: For datasets larger than 100K vectors, consider using a 
    dedicated vector database for better performance.
    """
    def __init__(self, path: Path):
        self.path = path
        self.vectors: Dict[str, List[float]] = {}
        self._version = _VECTOR_STORE_VERSION
        self._load()
    
    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, 'rb') as f:
                    data = pickle.load(f)
                
                # Check if versioned format
                if isinstance(data, dict) and "_version" in data:
                    if data["_version"] != _VECTOR_STORE_VERSION:
                        # Version mismatch - invalidate cache
                        import logging
                        logging.warning(
                            f"VectorStore version mismatch (got {data['_version']}, "
                            f"expected {_VECTOR_STORE_VERSION}). Cache invalidated."
                        )
                        self.vectors = {}
                        return
                    self.vectors = data.get("vectors", {})
                else:
                    # Legacy format (no version) - migrate
                    self.vectors = data if isinstance(data, dict) else {}
            except Exception as e:
                import logging
                logging.warning(f"Failed to load VectorStore: {e}. Starting fresh.")
                self.vectors = {}
    
    def save(self):
        data = {
            "_version": _VECTOR_STORE_VERSION,
            "vectors": self.vectors
        }
        with open(self.path, 'wb') as f:
            pickle.dump(data, f)
    
    def add(self, block_id: str, vector: List[float]):
        self.vectors[block_id] = vector
    
    def get(self, block_id: str) -> Optional[List[float]]:
        return self.vectors.get(block_id)
    
    def search(self, query_vec: List[float], top_k: int = 10) -> List[Tuple[str, float]]:
        results = []
        for block_id, vec in self.vectors.items():
            sim = cosine_similarity(query_vec, vec)
            results.append((block_id, sim))
        results.sort(key=lambda x: -x[1])
        return results[:top_k]

