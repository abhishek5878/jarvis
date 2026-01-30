"""
Semantic search via embeddings for the knowledge library.
"""
import os
import json
import sqlite3
from typing import List, Dict, Optional

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


class EmbeddingEngine:
    """
    Generate and search embeddings for semantic search.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self.model = "text-embedding-3-small"
        self.client = None
        if HAS_OPENAI and self.api_key:
            self.client = OpenAI(api_key=self.api_key)

    def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text."""
        if not self.client:
            return None
        text = (text or "").replace("\n", " ").strip()
        if not text:
            return None
        if len(text) > 30000:
            text = text[:30000]
        try:
            response = self.client.embeddings.create(
                input=text,
                model=self.model
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            return None

    def cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Cosine similarity between two vectors."""
        if not HAS_NUMPY:
            # Fallback without numpy
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(x * x for x in b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)
        a_arr = np.array(a)
        b_arr = np.array(b)
        return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))

    def embed_all_insights(self, db_path: str = "braingym.db", batch_size: int = 50) -> None:
        """Generate embeddings for all insights that don't have them."""
        if not self.client:
            raise RuntimeError("OPENAI_API_KEY not set. Cannot generate embeddings.")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("ALTER TABLE insights ADD COLUMN embedding TEXT")
            conn.commit()
        except sqlite3.OperationalError:
            pass  # Column already exists
        cursor.execute("""
            SELECT id, content, extracted_text, source_url
            FROM insights
            WHERE useful_for_daily = 1
            AND (embedding IS NULL OR embedding = '')
            ORDER BY id
        """)
        insights = cursor.fetchall()
        total = len(insights)
        print(f"Generating embeddings for {total} insights...")
        for i, insight in enumerate(insights):
            text = (insight["extracted_text"] or insight["content"] or "").strip()
            if not text or len(text) < 20:
                continue
            embedding = self.generate_embedding(text)
            if embedding:
                cursor.execute(
                    "UPDATE insights SET embedding = ? WHERE id = ?",
                    (json.dumps(embedding), insight["id"])
                )
                if (i + 1) % 10 == 0:
                    conn.commit()
                    print(f"Progress: {i+1}/{total} ({(i+1)/total*100:.1f}%)")
        conn.commit()
        conn.close()
        print(f"✓ Embeddings generated for {total} insights")

    def semantic_search(
        self,
        query: str,
        user_id: Optional[int] = None,
        trial_key: Optional[str] = None,
        limit: int = 20,
        db_path: str = "braingym.db"
    ) -> List[Dict]:
        """
        Search insights by semantic similarity.
        user_id: filter by user (when set). trial_key: filter by trial session (when set).
        """
        if not self.client:
            return []
        query_embedding = self.generate_embedding(query)
        if not query_embedding:
            return []
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(insights)")
        cols = [row[1] for row in cursor.fetchall()]
        where_extra = ""
        params = []
        if trial_key and "trial_key" in cols:
            where_extra = " AND trial_key = ?"
            params.append(trial_key)
        elif user_id is not None and "user_id" in cols:
            where_extra = " AND (user_id = ? OR user_id IS NULL)"
            params.append(user_id)
        cursor.execute("""
            SELECT id, content, extracted_text, source_url, source_type,
                   content_category, tags, quality_score, shared_date, embedding
            FROM insights
            WHERE useful_for_daily = 1
            AND embedding IS NOT NULL AND embedding != ''
            """ + where_extra + """
            ORDER BY shared_date DESC
        """, tuple(params) if params else ())
        insights = cursor.fetchall()
        conn.close()
        results = []
        for insight in insights:
            d = dict(insight)
            try:
                emb = json.loads(d["embedding"])
            except (TypeError, ValueError):
                continue
            sim = self.cosine_similarity(query_embedding, emb)
            d["similarity_score"] = sim
            results.append(d)
        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:limit]
