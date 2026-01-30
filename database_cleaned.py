"""
Database schema updates for cleaned/categorized data
Adds columns for content extraction and categorization
"""
import sqlite3
from contextlib import contextmanager


class CleanedDatabase:
    """Extended database with cleaning and categorization"""
    
    def __init__(self, db_path: str = "braingym.db"):
        self.db_path = db_path
        self.migrate_schema()
    
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
    
    def migrate_schema(self):
        """Add new columns for cleaning and content extraction"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Add categorization columns
            new_columns = [
                ("content_category", "TEXT DEFAULT 'uncategorized'"),
                ("needs_review", "INTEGER DEFAULT 0"),
                ("is_duplicate", "INTEGER DEFAULT 0"),
                ("content_length", "INTEGER DEFAULT 0"),
                ("has_useful_content", "INTEGER DEFAULT 0"),
                ("extracted_text", "TEXT"),
                ("extracted_metadata", "TEXT"),  # JSON string
                ("extraction_status", "TEXT DEFAULT 'pending'"),
                ("extraction_date", "TEXT"),
                ("extraction_error", "TEXT"),
                ("duplicate_of_id", "INTEGER"),  # Reference to original if duplicate
            ]
            
            for col_name, col_def in new_columns:
                try:
                    cursor.execute(f"ALTER TABLE insights ADD COLUMN {col_name} {col_def}")
                    print(f"✓ Added column: {col_name}")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e):
                        print(f"  Column {col_name} already exists")
                    else:
                        raise
            
            # Update content_length for existing entries
            cursor.execute("""
                UPDATE insights 
                SET content_length = LENGTH(content)
                WHERE content_length = 0 OR content_length IS NULL
            """)
            
            print(f"\n✅ Schema migration complete")
            conn.commit()
    
    def update_category(self, insight_id: int, category: str, 
                       has_useful_content: bool = True, needs_review: bool = False):
        """Update an insight's category"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE insights 
                SET content_category = ?,
                    has_useful_content = ?,
                    needs_review = ?
                WHERE id = ?
            """, (category, 1 if has_useful_content else 0, 1 if needs_review else 0, insight_id))
    
    def mark_duplicate(self, duplicate_id: int, original_id: int):
        """Mark an insight as duplicate"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE insights 
                SET is_duplicate = 1,
                    duplicate_of_id = ?,
                    has_useful_content = 0
                WHERE id = ?
            """, (original_id, duplicate_id))
    
    def update_extraction(self, insight_id: int, extracted_text: str, 
                         metadata: str, status: str = 'success', error: str = None):
        """Update extraction results"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            from datetime import datetime
            cursor.execute("""
                UPDATE insights 
                SET extracted_text = ?,
                    extracted_metadata = ?,
                    extraction_status = ?,
                    extraction_date = ?,
                    extraction_error = ?
                WHERE id = ?
            """, (extracted_text, metadata, status, datetime.now().isoformat(), error, insight_id))
    
    def get_insights_by_category(self, category: str):
        """Get all insights in a category"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM insights 
                WHERE content_category = ?
                ORDER BY shared_date DESC
            """, (category,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_insights_needing_extraction(self, limit: int = None):
        """Get insights that need content extraction"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT * FROM insights 
                WHERE content_category = 'external_link'
                AND extraction_status IN ('pending', 'failed')
                AND source_url IS NOT NULL
                ORDER BY shared_date DESC
            """
            if limit:
                query += f" LIMIT {limit}"
            
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_cleaning_stats(self):
        """Get comprehensive cleaning statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            stats = {}
            
            # Category breakdown
            cursor.execute("""
                SELECT content_category, COUNT(*) as count 
                FROM insights 
                GROUP BY content_category
            """)
            stats['by_category'] = {row['content_category']: row['count'] 
                                   for row in cursor.fetchall()}
            
            # Useful vs not useful
            cursor.execute("""
                SELECT has_useful_content, COUNT(*) as count 
                FROM insights 
                GROUP BY has_useful_content
            """)
            stats['by_usefulness'] = {row['has_useful_content']: row['count'] 
                                     for row in cursor.fetchall()}
            
            # Duplicates
            cursor.execute("SELECT COUNT(*) as count FROM insights WHERE is_duplicate = 1")
            stats['duplicate_count'] = cursor.fetchone()['count']
            
            # Needs review
            cursor.execute("SELECT COUNT(*) as count FROM insights WHERE needs_review = 1")
            stats['needs_review_count'] = cursor.fetchone()['count']
            
            # Extraction status
            cursor.execute("""
                SELECT extraction_status, COUNT(*) as count 
                FROM insights 
                WHERE content_category = 'external_link'
                GROUP BY extraction_status
            """)
            stats['extraction_status'] = {row['extraction_status']: row['count'] 
                                         for row in cursor.fetchall()}
            
            # Average extracted content length
            cursor.execute("""
                SELECT AVG(LENGTH(extracted_text)) as avg_length
                FROM insights 
                WHERE extraction_status = 'success' AND extracted_text IS NOT NULL
            """)
            result = cursor.fetchone()
            stats['avg_extracted_length'] = int(result['avg_length']) if result['avg_length'] else 0
            
            # Top domains
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN source_url LIKE '%linkedin.com%' THEN 'LinkedIn'
                        WHEN source_url LIKE '%twitter.com%' OR source_url LIKE '%x.com%' THEN 'Twitter'
                        WHEN source_url LIKE '%youtube.com%' OR source_url LIKE '%youtu.be%' THEN 'YouTube'
                        WHEN source_url LIKE '%medium.com%' THEN 'Medium'
                        WHEN source_url LIKE '%substack.com%' THEN 'Substack'
                        WHEN source_url LIKE '%github.com%' THEN 'GitHub'
                        WHEN source_url LIKE '%reddit.com%' THEN 'Reddit'
                        ELSE 'Other'
                    END as domain,
                    COUNT(*) as count
                FROM insights 
                WHERE source_url IS NOT NULL
                GROUP BY domain
                ORDER BY count DESC
            """)
            stats['by_domain'] = {row['domain']: row['count'] for row in cursor.fetchall()}
            
            return stats
