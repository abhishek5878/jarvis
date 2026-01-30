"""
Query engine: classify and route queries to recall, synthesis, pattern, decision, generate, explore.
"""
import json
import re
import sqlite3
from typing import List, Dict, Optional
from collections import Counter

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

from embeddings import EmbeddingEngine


class QueryEngine:
    """
    Classify and route queries to appropriate handlers.
    """
    def __init__(self, anthropic_key: Optional[str] = None, openai_key: Optional[str] = None):
        self.anthropic_key = anthropic_key or __import__("os").environ.get("ANTHROPIC_API_KEY")
        self.client = None
        if HAS_ANTHROPIC and self.anthropic_key:
            self.client = anthropic.Anthropic(api_key=self.anthropic_key)
        self.embedding_engine = EmbeddingEngine(api_key=openai_key or __import__("os").environ.get("OPENAI_API_KEY"))
        self.db_path = "braingym.db"

    def classify_query(self, query: str) -> Dict:
        """
        Classify query type and extract intent.
        Types: recall, synthesis, pattern, decision, generate, explore.
        """
        if not self.client:
            return {
                "type": "recall",
                "intent": query,
                "key_concepts": [],
                "timeframe": "all_time",
                "output_format": "text"
            }
        prompt = f"""Classify this query and extract the intent:

Query: "{query}"

Classify as ONE of these types:
1. recall - User wants to find/remember specific information
2. synthesis - User wants to connect ideas or synthesize knowledge
3. pattern - User wants to identify patterns or themes
4. decision - User is making a decision and needs relevant context
5. generate - User wants to create content (post, article, etc.)
6. explore - User wants to browse/discover what they know

Return JSON only, no other text:
{{
    "type": "recall|synthesis|pattern|decision|generate|explore",
    "intent": "brief description of what user wants",
    "key_concepts": ["concept1", "concept2"],
    "timeframe": "recent|all_time|specific_date",
    "output_format": "text|list|framework|content"
}}
"""
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            text = response.content[0].text
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"Query classification error: {e}")
        return {
            "type": "recall",
            "intent": query,
            "key_concepts": [],
            "timeframe": "all_time",
            "output_format": "text"
        }

    def route_query(
        self,
        query: str,
        user_id: Optional[int] = None,
        trial_key: Optional[str] = None
    ) -> Dict:
        """Main query router."""
        classification = self.classify_query(query)
        query_type = classification.get("type", "recall")
        relevant_insights = self.embedding_engine.semantic_search(
            query,
            user_id=user_id,
            trial_key=trial_key,
            limit=20,
            db_path=self.db_path
        )
        if query_type == "recall":
            return self.handle_recall(query, relevant_insights, classification)
        if query_type == "synthesis":
            return self.handle_synthesis(query, relevant_insights, classification, user_id)
        if query_type == "pattern":
            return self.handle_pattern(query, relevant_insights, classification)
        if query_type == "decision":
            return self.handle_decision(query, relevant_insights, classification)
        if query_type == "generate":
            return self.handle_generate(query, relevant_insights, classification)
        if query_type == "explore":
            return self.handle_explore(query, relevant_insights, classification)
        return self.handle_recall(query, relevant_insights, classification)

    def handle_recall(self, query: str, insights: List[Dict], classification: Dict) -> Dict:
        """Help user recall specific information."""
        top_insights = insights[:5]
        context = self._build_context(top_insights)
        if not self.client:
            return {
                "type": "recall",
                "response": "No AI configured. Here are relevant items from your library.\n\n" + context[:2000],
                "insights": top_insights,
                "query": query
            }
        prompt = f"""The user is trying to recall information from their knowledge library.

Query: "{query}"

Here's what they have saved that's relevant:

{context}

Help them recall by:
1. Directly answering their question if possible
2. Showing the most relevant saved items
3. Providing context (when they saved it, any notes they added)
4. Suggesting related items they might also want

Be conversational and helpful. Reference specific items by their source or content preview.
"""
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        return {
            "type": "recall",
            "response": response.content[0].text,
            "insights": top_insights,
            "query": query
        }

    def handle_synthesis(
        self,
        query: str,
        insights: List[Dict],
        classification: Dict,
        user_id: Optional[int] = None
    ) -> Dict:
        """Synthesize knowledge across multiple sources."""
        top_insights = insights[:15]
        context = self._build_context(top_insights)
        if not self.client:
            synthesis_text = "AI not configured. Your relevant items:\n\n" + context[:3000]
            synthesis_id = self._save_synthesis(query, synthesis_text, [i["id"] for i in top_insights], user_id)
            return {
                "type": "synthesis",
                "response": synthesis_text,
                "insights": top_insights,
                "synthesis_id": synthesis_id,
                "query": query
            }
        prompt = f"""The user wants to synthesize knowledge from their library.

Query: "{query}"

Their saved knowledge on this topic:

{context}

Create a comprehensive synthesis that:
1. Identifies key themes and patterns
2. Connects ideas across sources
3. Highlights unique insights or contradictions
4. Shows how their thinking has evolved (if temporal patterns exist)
5. Suggests new connections or implications

This should be THEIR knowledge synthesized, not generic information.
Reference specific sources (by number or title).
"""
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )
        synthesis_text = response.content[0].text
        synthesis_id = self._save_synthesis(
            query, synthesis_text, [i["id"] for i in top_insights], user_id
        )
        return {
            "type": "synthesis",
            "response": synthesis_text,
            "insights": top_insights,
            "synthesis_id": synthesis_id,
            "query": query
        }

    def handle_pattern(self, query: str, insights: List[Dict], classification: Dict) -> Dict:
        """Identify patterns across user's knowledge."""
        top_insights = insights[:20]
        context = self._build_context(top_insights)
        if not self.client:
            return {
                "type": "pattern",
                "response": "AI not configured. Review the " + str(len(top_insights)) + " relevant items above for patterns.",
                "insights": top_insights,
                "query": query
            }
        prompt = f"""The user wants to identify patterns in their knowledge.

Query: "{query}"

Their relevant saved content:

{context}

Analyze for patterns:
1. Recurring themes or topics
2. Common frameworks or mental models
3. Evolution of thinking over time
4. Contradictions or tensions
5. Gaps in knowledge
6. Unique combinations of ideas

Present patterns clearly with specific examples from their saved content.
"""
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )
        return {
            "type": "pattern",
            "response": response.content[0].text,
            "insights": top_insights,
            "query": query
        }

    def handle_decision(self, query: str, insights: List[Dict], classification: Dict) -> Dict:
        """Provide context for decision-making."""
        top_insights = insights[:15]
        context = self._build_context(top_insights)
        if not self.client:
            return {
                "type": "decision",
                "response": "AI not configured. Here are relevant items from your library for this decision.",
                "insights": top_insights,
                "query": query
            }
        prompt = f"""The user is making a decision and needs context from their knowledge.

Query: "{query}"

Relevant knowledge from their library:

{context}

Help them decide by:
1. Presenting relevant frameworks or mental models they've saved
2. Showing lessons from similar situations they've noted
3. Highlighting both supporting and contradicting viewpoints
4. Identifying what they DON'T know (gaps)
5. Suggesting what additional information might help

Frame this as decision support, not making the decision for them.
"""
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2500,
            messages=[{"role": "user", "content": prompt}]
        )
        return {
            "type": "decision",
            "response": response.content[0].text,
            "insights": top_insights,
            "query": query
        }

    def handle_generate(self, query: str, insights: List[Dict], classification: Dict) -> Dict:
        """Redirect to content generation."""
        topic = classification.get("intent", query)
        if isinstance(topic, list):
            topic = query
        return {
            "type": "generate",
            "redirect": "/",
            "topic": topic[:200] if topic else query,
            "insights": insights[:10]
        }

    def handle_explore(self, query: str, insights: List[Dict], classification: Dict) -> Dict:
        """Help user explore their knowledge library."""
        stats = self._get_library_stats()
        sample = self._get_diverse_sample(insights, n=10)
        context = self._build_context(sample)
        if not self.client:
            return {
                "type": "explore",
                "response": f"Your library has {stats['total']} items. Top topics: {', '.join(stats.get('top_topics', [])[:5])}.",
                "stats": stats,
                "sample": sample,
                "query": query
            }
        prompt = f"""The user wants to explore their knowledge library.

Query: "{query}"

Library statistics:
- Total items: {stats['total']}
- Articles: {stats.get('articles', 0)}
- Notes: {stats.get('notes', 0)}
- Top topics: {', '.join(stats.get('top_topics', [])[:5])}

Sample of their saved content:
{context}

Help them explore by:
1. Highlighting interesting patterns or clusters
2. Suggesting topics they might want to dive into
3. Pointing out unique combinations
4. Showing their learning journey (temporal patterns)
5. Identifying gaps or opportunities

Be enthusiastic and help them rediscover their own knowledge.
"""
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        return {
            "type": "explore",
            "response": response.content[0].text,
            "stats": stats,
            "sample": sample,
            "query": query
        }

    def _build_context(self, insights: List[Dict]) -> str:
        """Build context string from insights."""
        parts = []
        for i, insight in enumerate(insights, 1):
            part = f"\n--- Item {i} ---\n"
            part += f"Type: {insight.get('content_category', 'unknown')}\n"
            shared = insight.get("shared_date") or ""
            if isinstance(shared, str) and len(shared) >= 10:
                part += f"Saved: {shared[:10]}\n"
            if insight.get("source_url"):
                part += f"Source: {insight['source_url']}\n"
            tags = insight.get("tags")
            if tags:
                if isinstance(tags, str):
                    try:
                        tags = json.loads(tags) if tags.strip().startswith("[") else [t.strip() for t in tags.split(",")]
                    except Exception:
                        tags = [t.strip() for t in tags.split(",")]
                if tags:
                    part += f"Tags: {', '.join(str(t) for t in (tags[:5] if isinstance(tags, list) else []))}\n"
            part += "\nContent:\n"
            text = insight.get("extracted_text") or insight.get("content") or ""
            if len(text) > 1500:
                text = text[:1500] + "..."
            part += text
            parts.append(part)
        return "\n".join(parts)

    def _save_synthesis(
        self,
        query: str,
        synthesis_text: str,
        insights: List[int],
        user_id: Optional[int] = None
    ) -> int:
        """Save synthesis to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS syntheses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                query TEXT NOT NULL,
                synthesis_text TEXT NOT NULL,
                source_insights TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                edited_text TEXT
            )
        """)
        cursor.execute(
            """
            INSERT INTO syntheses (user_id, query, synthesis_text, source_insights)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, query, synthesis_text, json.dumps(insights))
        )
        sid = cursor.lastrowid
        conn.commit()
        conn.close()
        return sid

    def _get_library_stats(self) -> Dict:
        """Get statistics about the library."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as total FROM insights WHERE useful_for_daily = 1")
        total = cursor.fetchone()["total"]
        cursor.execute("""
            SELECT content_category, COUNT(*) as count
            FROM insights WHERE useful_for_daily = 1
            GROUP BY content_category
        """)
        categories = {row["content_category"]: row["count"] for row in cursor.fetchall()}
        cursor.execute("""
            SELECT tags FROM insights
            WHERE useful_for_daily = 1 AND tags IS NOT NULL AND tags != ''
        """)
        all_tags = []
        for row in cursor.fetchall():
            t = row["tags"]
            try:
                if isinstance(t, str) and t.strip().startswith("["):
                    all_tags.extend(json.loads(t))
                else:
                    all_tags.extend([x.strip() for x in str(t).split(",") if x.strip()])
            except Exception:
                all_tags.extend([x.strip() for x in str(t).split(",") if x.strip()])
        tag_counts = Counter(all_tags)
        top_topics = [tag for tag, _ in tag_counts.most_common(10)]
        conn.close()
        return {
            "total": total,
            "articles": categories.get("article", 0),
            "notes": categories.get("my_note", 0),
            "videos": categories.get("video", 0),
            "social": categories.get("social_reference", 0),
            "top_topics": top_topics
        }

    def _get_diverse_sample(self, insights: List[Dict], n: int = 10) -> List[Dict]:
        """Get diverse sample by category."""
        by_category = {}
        for insight in insights:
            cat = insight.get("content_category") or "other"
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(insight)
        sample = []
        for cat, items in by_category.items():
            sample.extend(items[:2])
            if len(sample) >= n:
                break
        return sample[:n]
