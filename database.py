"""
Database module for Brain Gym - handles SQLite schema and operations
"""
import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager


class BrainGymDB:
    """Manages the Brain Gym SQLite database"""
    
    def __init__(self, db_path: str = "braingym.db"):
        self.db_path = db_path
        self.init_database()
    
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
    
    def init_database(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Main insights table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS insights (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    source_url TEXT,
                    source_type TEXT,
                    shared_by TEXT,
                    shared_date TEXT,
                    context_message TEXT,
                    tags TEXT,
                    my_response TEXT,
                    response_date TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(content, source_url, shared_by, shared_date)
                )
            """)
            
            # Stats table for tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    total_insights INTEGER,
                    total_responded INTEGER,
                    last_updated TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
    
    def insert_insight(
        self,
        content: str,
        source_url: Optional[str] = None,
        source_type: Optional[str] = None,
        shared_by: Optional[str] = None,
        shared_date: Optional[str] = None,
        context_message: Optional[str] = None,
        tags: Optional[List[str]] = None,
        status: str = "pending"
    ) -> Optional[int]:
        """Insert a new insight into the database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            tags_str = ",".join(tags) if tags else None
            
            try:
                cursor.execute("""
                    INSERT INTO insights (
                        content, source_url, source_type, shared_by,
                        shared_date, context_message, tags, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    content, source_url, source_type, shared_by,
                    shared_date, context_message, tags_str, status
                ))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                # Duplicate entry, skip
                return None
    
    def get_insights(
        self,
        limit: Optional[int] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve insights from database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            query = "SELECT * FROM insights"
            params = []
            
            if status:
                query += " WHERE status = ?"
                params.append(status)
            
            query += " ORDER BY shared_date DESC"
            
            if limit:
                query += " LIMIT ?"
                params.append(limit)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about insights"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Total insights
            cursor.execute("SELECT COUNT(*) as count FROM insights")
            stats['total_insights'] = cursor.fetchone()['count']
            
            # Breakdown by status
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM insights 
                GROUP BY status
            """)
            stats['by_status'] = {row['status']: row['count'] for row in cursor.fetchall()}
            
            # Breakdown by source type
            cursor.execute("""
                SELECT source_type, COUNT(*) as count 
                FROM insights 
                WHERE source_type IS NOT NULL
                GROUP BY source_type
                ORDER BY count DESC
            """)
            stats['by_type'] = {row['source_type']: row['count'] for row in cursor.fetchall()}
            
            # Top sharers
            cursor.execute("""
                SELECT shared_by, COUNT(*) as count 
                FROM insights 
                WHERE shared_by IS NOT NULL
                GROUP BY shared_by
                ORDER BY count DESC
                LIMIT 10
            """)
            stats['top_sharers'] = {row['shared_by']: row['count'] for row in cursor.fetchall()}
            
            return stats
    
    def update_response(self, insight_id: int, response: str):
        """Update an insight with user's response"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE insights 
                SET my_response = ?, 
                    response_date = ?,
                    status = 'responded'
                WHERE id = ?
            """, (response, datetime.now().isoformat(), insight_id))
