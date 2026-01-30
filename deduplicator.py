"""
Deduplication script for insights
Finds and marks duplicate entries
"""
import sqlite3
from typing import List, Dict
from difflib import SequenceMatcher


class Deduplicator:
    """Find and mark duplicate insights"""
    
    def __init__(self, db_path: str = "braingym.db"):
        self.db_path = db_path
    
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def find_url_duplicates(self) -> List[Dict]:
        """Find insights with duplicate URLs"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Find URLs that appear more than once
        cursor.execute("""
            SELECT source_url, COUNT(*) as count, MIN(id) as original_id
            FROM insights
            WHERE source_url IS NOT NULL
            AND source_url != ''
            GROUP BY source_url
            HAVING count > 1
        """)
        
        duplicates = []
        for row in cursor.fetchall():
            url = row['source_url']
            original_id = row['original_id']
            
            # Get all insights with this URL
            cursor.execute("""
                SELECT id FROM insights 
                WHERE source_url = ? AND id != ?
                ORDER BY id
            """, (url, original_id))
            
            duplicate_ids = [r['id'] for r in cursor.fetchall()]
            
            duplicates.append({
                'type': 'url',
                'original_id': original_id,
                'duplicate_ids': duplicate_ids,
                'url': url
            })
        
        conn.close()
        return duplicates
    
    def find_content_duplicates(self, threshold: float = 0.85) -> List[Dict]:
        """Find insights with very similar content"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get all non-junk insights without URLs (to check content similarity)
        cursor.execute("""
            SELECT id, content, content_length
            FROM insights
            WHERE content_category != 'junk'
            AND (source_url IS NULL OR source_url = '')
            AND content_length > 100
            ORDER BY id
        """)
        
        insights = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        duplicates = []
        checked = set()
        
        print(f"\n🔍 Checking {len(insights)} insights for content similarity...")
        
        for i, insight1 in enumerate(insights):
            if insight1['id'] in checked:
                continue
            
            duplicate_ids = []
            
            # Compare with later insights
            for insight2 in insights[i+1:]:
                if insight2['id'] in checked:
                    continue
                
                similarity = self._similarity(
                    insight1['content'],
                    insight2['content']
                )
                
                if similarity >= threshold:
                    duplicate_ids.append(insight2['id'])
                    checked.add(insight2['id'])
            
            if duplicate_ids:
                duplicates.append({
                    'type': 'content',
                    'original_id': insight1['id'],
                    'duplicate_ids': duplicate_ids
                })
            
            if (i + 1) % 50 == 0:
                print(f"   Checked {i+1}/{len(insights)}...")
        
        return duplicates
    
    def _similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity ratio between two texts"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def mark_duplicates(self, duplicates: List[Dict]):
        """Mark duplicates in the database"""
        from database_cleaned import CleanedDatabase
        
        db = CleanedDatabase(self.db_path)
        
        total_marked = 0
        for dup_group in duplicates:
            original_id = dup_group['original_id']
            for dup_id in dup_group['duplicate_ids']:
                db.mark_duplicate(dup_id, original_id)
                total_marked += 1
        
        print(f"\n✅ Marked {total_marked} duplicates")
        return total_marked


def run_deduplication(db_path: str = "braingym.db"):
    """Run complete deduplication process"""
    dedup = Deduplicator(db_path)
    
    print("\n🔍 Finding duplicates...")
    print("=" * 60)
    
    # Find URL duplicates
    print("\n1. Checking for duplicate URLs...")
    url_dups = dedup.find_url_duplicates()
    print(f"   Found {len(url_dups)} groups of URL duplicates")
    
    # Find content duplicates
    print("\n2. Checking for similar content...")
    content_dups = dedup.find_content_duplicates(threshold=0.85)
    print(f"   Found {len(content_dups)} groups of content duplicates")
    
    # Mark all duplicates
    all_duplicates = url_dups + content_dups
    if all_duplicates:
        print("\n3. Marking duplicates in database...")
        dedup.mark_duplicates(all_duplicates)
    else:
        print("\n✅ No duplicates found!")
    
    return len(all_duplicates)
