"""
Extended database module for Brain Gym Phase 2
Adds response tracking, user actions, and analytics
"""
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import contextmanager


class BrainGymDBV2:
    """Enhanced database for Phase 2 with response tracking"""
    
    def __init__(self, db_path: str = "braingym.db"):
        self.db_path = db_path
        self.migrate_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def migrate_database(self):
        """Add Phase 2 tables and columns"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Add new columns to insights table if they don't exist
            try:
                cursor.execute("ALTER TABLE insights ADD COLUMN last_shown_date TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute("ALTER TABLE insights ADD COLUMN times_skipped INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE insights ADD COLUMN archived INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE insights ADD COLUMN quality_score INTEGER DEFAULT 5")
            except sqlite3.OperationalError:
                pass
            
            # Update quality scores for existing insights
            cursor.execute("""
                UPDATE insights 
                SET quality_score = CASE 
                    WHEN tags LIKE '%high_value%' THEN 8
                    ELSE 5
                END
                WHERE quality_score = 5 OR quality_score IS NULL
            """)
            
            # Create responses table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS responses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    insight_id INTEGER NOT NULL,
                    response_text TEXT NOT NULL,
                    response_tags TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (insight_id) REFERENCES insights (id)
                )
            """)
            
            # Create user actions table (for tracking skips, views, etc.)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    insight_id INTEGER NOT NULL,
                    action_type TEXT NOT NULL,
                    action_date TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (insight_id) REFERENCES insights (id)
                )
            """)
            
            # Create daily sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_date TEXT NOT NULL UNIQUE,
                    insights_shown TEXT,
                    completed INTEGER DEFAULT 0,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def get_daily_insights(self, count: int = 3) -> List[Dict[str, Any]]:
        """
        Smart selector for daily insights
        Picks based on quality, variety, and engagement history
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get today's date
            today = datetime.now().date().isoformat()
            
            # Check if we already selected insights for today
            cursor.execute("""
                SELECT insights_shown FROM daily_sessions 
                WHERE session_date = ?
            """, (today,))
            
            existing = cursor.fetchone()
            if existing and existing['insights_shown']:
                # Return today's already-selected insights
                insight_ids = existing['insights_shown'].split(',')
                placeholders = ','.join('?' * len(insight_ids))
                cursor.execute(f"""
                    SELECT * FROM insights 
                    WHERE id IN ({placeholders})
                """, insight_ids)
                return [dict(row) for row in cursor.fetchall()]
            
            # Select new insights for today
            query = """
                SELECT * FROM insights
                WHERE 
                    archived = 0
                    AND status = 'pending'
                    AND (last_shown_date IS NULL OR last_shown_date != ?)
                ORDER BY
                    quality_score DESC,
                    times_skipped ASC,
                    RANDOM()
                LIMIT ?
            """
            
            cursor.execute(query, (today, count * 3))  # Get more than needed for variety
            candidates = [dict(row) for row in cursor.fetchall()]
            
            # Ensure variety in tags and types
            selected = self._ensure_variety(candidates, count)
            
            # Record the selection
            insight_ids = ','.join(str(i['id']) for i in selected)
            cursor.execute("""
                INSERT OR REPLACE INTO daily_sessions (session_date, insights_shown)
                VALUES (?, ?)
            """, (today, insight_ids))
            
            # Update last_shown_date
            for insight in selected:
                cursor.execute("""
                    UPDATE insights 
                    SET last_shown_date = ?
                    WHERE id = ?
                """, (today, insight['id']))
            
            conn.commit()
            return selected
    
    def _ensure_variety(self, candidates: List[Dict], count: int) -> List[Dict]:
        """Ensure variety in selected insights"""
        if len(candidates) <= count:
            return candidates
        
        selected = []
        used_types = set()
        used_primary_tags = set()
        
        # First pass: pick diverse items
        for insight in candidates:
            if len(selected) >= count:
                break
            
            source_type = insight.get('source_type')
            tags = insight.get('tags', '').split(',')
            primary_tag = tags[0] if tags else None
            
            # Prefer items with different types and primary tags
            if source_type not in used_types or primary_tag not in used_primary_tags:
                selected.append(insight)
                if source_type:
                    used_types.add(source_type)
                if primary_tag:
                    used_primary_tags.add(primary_tag)
        
        # Fill remaining slots if needed
        while len(selected) < count and len(selected) < len(candidates):
            for insight in candidates:
                if insight not in selected:
                    selected.append(insight)
                    break
        
        return selected[:count]
    
    def add_response(self, insight_id: int, response_text: str) -> int:
        """Add a response to an insight"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert response
            cursor.execute("""
                INSERT INTO responses (insight_id, response_text)
                VALUES (?, ?)
            """, (insight_id, response_text))
            
            response_id = cursor.lastrowid
            
            # Update insight status
            cursor.execute("""
                UPDATE insights 
                SET my_response = ?,
                    response_date = ?,
                    status = 'responded'
                WHERE id = ?
            """, (response_text, datetime.now().isoformat(), insight_id))
            
            # Log action
            cursor.execute("""
                INSERT INTO user_actions (insight_id, action_type)
                VALUES (?, 'responded')
            """, (insight_id,))
            
            conn.commit()
            return response_id
    
    def skip_insight(self, insight_id: int):
        """Mark insight as skipped"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE insights 
                SET times_skipped = times_skipped + 1
                WHERE id = ?
            """, (insight_id,))
            
            cursor.execute("""
                INSERT INTO user_actions (insight_id, action_type)
                VALUES (?, 'skipped')
            """, (insight_id,))
            
            conn.commit()
    
    def archive_insight(self, insight_id: int):
        """Archive an insight (not interested)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE insights 
                SET archived = 1, status = 'archived'
                WHERE id = ?
            """, (insight_id,))
            
            cursor.execute("""
                INSERT INTO user_actions (insight_id, action_type)
                VALUES (?, 'archived')
            """, (insight_id,))
            
            conn.commit()
    
    def search_responses(self, keyword: str = None, tag: str = None, 
                        limit: int = 50) -> List[Dict[str, Any]]:
        """Search through responses"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = """
                SELECT 
                    i.*,
                    r.response_text,
                    r.created_at as response_created_at
                FROM insights i
                INNER JOIN responses r ON i.id = r.insight_id
                WHERE 1=1
            """
            params = []
            
            if keyword:
                query += " AND (r.response_text LIKE ? OR i.content LIKE ?)"
                params.extend([f"%{keyword}%", f"%{keyword}%"])
            
            if tag:
                query += " AND i.tags LIKE ?"
                params.append(f"%{tag}%")
            
            query += " ORDER BY r.created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive stats for dashboard"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Total insights and responses
            cursor.execute("SELECT COUNT(*) as count FROM insights WHERE archived = 0")
            stats['total_insights'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM responses")
            stats['total_responses'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM insights WHERE status = 'pending' AND archived = 0")
            stats['pending'] = cursor.fetchone()['count']
            
            # Current streak
            stats['current_streak'] = self._calculate_streak(cursor)
            
            # Response rate
            if stats['total_insights'] > 0:
                stats['response_rate'] = round((stats['total_responses'] / stats['total_insights']) * 100, 1)
            else:
                stats['response_rate'] = 0
            
            # Top themes engaged with
            cursor.execute("""
                SELECT i.tags, COUNT(*) as count
                FROM insights i
                INNER JOIN responses r ON i.id = r.insight_id
                WHERE i.tags IS NOT NULL
                GROUP BY i.tags
                ORDER BY count DESC
                LIMIT 10
            """)
            
            theme_counts = {}
            for row in cursor.fetchall():
                tags = row['tags'].split(',')
                for tag in tags:
                    tag = tag.strip()
                    theme_counts[tag] = theme_counts.get(tag, 0) + row['count']
            
            stats['top_themes'] = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            
            # Responses over time (last 30 days)
            cursor.execute("""
                SELECT DATE(created_at) as date, COUNT(*) as count
                FROM responses
                WHERE created_at >= date('now', '-30 days')
                GROUP BY DATE(created_at)
                ORDER BY date
            """)
            stats['responses_by_date'] = [dict(row) for row in cursor.fetchall()]
            
            return stats
    
    def _calculate_streak(self, cursor) -> int:
        """Calculate current response streak"""
        cursor.execute("""
            SELECT DISTINCT DATE(created_at) as date
            FROM responses
            ORDER BY date DESC
            LIMIT 30
        """)
        
        dates = [row['date'] for row in cursor.fetchall()]
        if not dates:
            return 0
        
        streak = 0
        current_date = datetime.now().date()
        
        for i in range(30):
            check_date = (current_date - timedelta(days=i)).isoformat()
            if check_date in dates:
                streak += 1
            else:
                break
        
        return streak
    
    def add_manual_insight(self, content: str, source_url: str = None,
                          context: str = None, tags: List[str] = None) -> int:
        """Manually add an insight"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Determine source type from URL
            source_type = 'quote'
            if source_url:
                if 'twitter.com' in source_url or 'x.com' in source_url:
                    source_type = 'tweet'
                elif 'linkedin.com' in source_url:
                    source_type = 'linkedin'
                elif 'youtube.com' in source_url or 'youtu.be' in source_url:
                    source_type = 'video'
                elif any(d in source_url for d in ['medium.com', 'substack.com', 'blog']):
                    source_type = 'article'
                else:
                    source_type = 'link'
            
            tags_str = ','.join(tags) if tags else None
            quality_score = 8 if tags and 'high_value' in tags else 5
            
            cursor.execute("""
                INSERT INTO insights (
                    content, source_url, source_type, shared_by,
                    shared_date, context_message, tags, quality_score, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            """, (
                content, source_url, source_type, 'Manual',
                datetime.now().isoformat(), context, tags_str, quality_score
            ))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_insight(self, insight_id: int) -> Optional[Dict[str, Any]]:
        """Get a single insight by ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM insights WHERE id = ?", (insight_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def mark_session_complete(self, session_date: str = None):
        """Mark today's session as complete"""
        if not session_date:
            session_date = datetime.now().date().isoformat()
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE daily_sessions 
                SET completed = 1 
                WHERE session_date = ?
            """, (session_date,))
            conn.commit()
