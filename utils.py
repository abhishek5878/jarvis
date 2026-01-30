"""
Utility functions for Brain Gym web interface
Helper functions for daily selection, search, stats, etc.
"""
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import random


class BrainGymUtils:
    """Utility functions for Brain Gym web interface"""
    
    def __init__(self, db_path: str = "braingym.db"):
        self.db_path = db_path
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_daily_three(self) -> List[Dict]:
        """
        Get 3 insights for daily practice
        Algorithm: quality + variety + not shown recently + unresponded
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().date().isoformat()
        yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
        
        # Get candidates: unresponded, useful, not shown today
        query = """
            SELECT * FROM insights
            WHERE status = 'pending'
            AND useful_for_daily = 1
            AND is_duplicate = 0
            AND (last_shown_date IS NULL OR last_shown_date < ?)
            ORDER BY quality_score DESC, RANDOM()
            LIMIT 50
        """
        
        cursor.execute(query, (today,))
        candidates = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        if len(candidates) <= 3:
            return candidates
        
        # Select 3 with variety
        selected = self._ensure_variety(candidates, 3)
        
        # Mark as shown
        for insight in selected:
            self.mark_shown(insight['id'])
        
        return selected
    
    def _ensure_variety(self, candidates: List[Dict], count: int) -> List[Dict]:
        """Ensure variety in selected insights"""
        if len(candidates) <= count:
            return candidates
        
        selected = []
        used_categories = set()
        used_domains = set()
        
        # First pass: pick diverse items
        for insight in candidates:
            if len(selected) >= count:
                break
            
            category = insight.get('content_category', '')
            source_url = insight.get('source_url', '')
            domain = self._extract_domain(source_url) if source_url else 'none'
            
            # Prefer items with different categories and domains
            if category not in used_categories or domain not in used_domains:
                selected.append(insight)
                if category:
                    used_categories.add(category)
                if domain:
                    used_domains.add(domain)
        
        # Fill remaining slots if needed
        while len(selected) < count and len(selected) < len(candidates):
            for insight in candidates:
                if insight not in selected:
                    selected.append(insight)
                    if len(selected) >= count:
                        break
        
        return selected[:count]
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.replace('www.', '')
    
    def mark_shown(self, insight_id: int):
        """Mark insight as shown today"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().date().isoformat()
        
        cursor.execute("""
            UPDATE insights 
            SET last_shown_date = ?
            WHERE id = ?
        """, (today, insight_id))
        
        conn.commit()
        conn.close()
    
    def save_response(self, insight_id: int, response_text: str) -> int:
        """Save user's response to an insight"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Insert response
        cursor.execute("""
            INSERT INTO responses (insight_id, response_text, created_at)
            VALUES (?, ?, ?)
        """, (insight_id, response_text, datetime.now().isoformat()))
        
        response_id = cursor.lastrowid
        
        # Update insight status
        cursor.execute("""
            UPDATE insights 
            SET my_response = ?,
                response_date = ?,
                status = 'responded'
            WHERE id = ?
        """, (response_text, datetime.now().isoformat(), insight_id))
        
        conn.commit()
        conn.close()
        
        return response_id
    
    def search_responses(self, query: str = None, tag: str = None, 
                        limit: int = 50) -> List[Dict]:
        """Search through user's responses"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        sql = """
            SELECT 
                i.*,
                r.response_text,
                r.created_at as response_created_at
            FROM insights i
            INNER JOIN responses r ON i.id = r.insight_id
            WHERE 1=1
        """
        params = []
        
        if query:
            sql += " AND (r.response_text LIKE ? OR i.content LIKE ? OR i.extracted_text LIKE ?)"
            search_term = f"%{query}%"
            params.extend([search_term, search_term, search_term])
        
        if tag:
            sql += " AND i.tags LIKE ?"
            params.append(f"%{tag}%")
        
        sql += " ORDER BY r.created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(sql, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return results
    
    def get_stats(self) -> Dict:
        """Get comprehensive statistics"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        stats = {}
        
        # Total insights
        cursor.execute("SELECT COUNT(*) as count FROM insights WHERE useful_for_daily = 1")
        stats['total_useful'] = cursor.fetchone()['count']
        
        # Responses
        cursor.execute("SELECT COUNT(*) as count FROM responses")
        stats['total_responses'] = cursor.fetchone()['count']
        
        # Pending
        cursor.execute("""
            SELECT COUNT(*) as count FROM insights 
            WHERE status = 'pending' AND useful_for_daily = 1
        """)
        stats['pending'] = cursor.fetchone()['count']
        
        # By category
        cursor.execute("""
            SELECT content_category, COUNT(*) as count 
            FROM insights 
            WHERE useful_for_daily = 1
            GROUP BY content_category
        """)
        stats['by_category'] = {row['content_category']: row['count'] 
                               for row in cursor.fetchall()}
        
        # Current streak
        stats['current_streak'] = self._calculate_streak(cursor)
        
        # Response rate
        if stats['total_useful'] > 0:
            stats['response_rate'] = round((stats['total_responses'] / stats['total_useful']) * 100, 1)
        else:
            stats['response_rate'] = 0
        
        # Top themes
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
            if row['tags']:
                tags = row['tags'].split(',')
                for tag in tags:
                    tag = tag.strip()
                    theme_counts[tag] = theme_counts.get(tag, 0) + row['count']
        
        stats['top_themes'] = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        
        conn.close()
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
    
    def get_insight(self, insight_id: int) -> Optional[Dict]:
        """Get a single insight by ID"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM insights WHERE id = ?", (insight_id,))
        row = cursor.fetchone()
        conn.close()
        
        return dict(row) if row else None
    
    def skip_insight(self, insight_id: int):
        """Mark insight as skipped"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE insights 
            SET times_skipped = COALESCE(times_skipped, 0) + 1
            WHERE id = ?
        """, (insight_id,))
        
        conn.commit()
        conn.close()
    
    def archive_insight(self, insight_id: int):
        """Archive an insight"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE insights 
            SET archived = 1, 
                status = 'archived',
                useful_for_daily = 0
            WHERE id = ?
        """, (insight_id,))
        
        conn.commit()
        conn.close()
