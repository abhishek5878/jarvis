#!/usr/bin/env python3
"""
Brain Gym Explorer - Interactive database exploration
"""
import sqlite3
import argparse
from collections import Counter
from typing import List, Dict


class BrainGymExplorer:
    """Explore and analyze your Brain Gym database"""
    
    def __init__(self, db_path: str = "braingym.db"):
        self.db_path = db_path
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def search_by_keyword(self, keyword: str, limit: int = 20):
        """Search insights by keyword"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT * FROM insights 
            WHERE content LIKE ? OR context_message LIKE ?
            ORDER BY shared_date DESC
            LIMIT ?
        """
        
        search_term = f"%{keyword}%"
        cursor.execute(query, (search_term, search_term, limit))
        results = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in results]
    
    def get_by_tag(self, tag: str, limit: int = 20):
        """Get insights by specific tag"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT * FROM insights 
            WHERE tags LIKE ?
            ORDER BY shared_date DESC
            LIMIT ?
        """
        
        tag_pattern = f"%{tag}%"
        cursor.execute(query, (tag_pattern, limit))
        results = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in results]
    
    def get_by_type(self, source_type: str, limit: int = 20):
        """Get insights by source type"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT * FROM insights 
            WHERE source_type = ?
            ORDER BY shared_date DESC
            LIMIT ?
        """
        
        cursor.execute(query, (source_type, limit))
        results = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in results]
    
    def get_high_value(self, limit: int = 20):
        """Get high-value insights"""
        return self.get_by_tag('high_value', limit)
    
    def analyze_tags(self):
        """Analyze tag distribution"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT tags FROM insights WHERE tags IS NOT NULL")
        all_tags = []
        
        for row in cursor.fetchall():
            if row['tags']:
                tags = row['tags'].split(',')
                all_tags.extend([tag.strip() for tag in tags])
        
        conn.close()
        
        return Counter(all_tags)
    
    def random_insights(self, count: int = 3):
        """Get random insights for daily practice"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Prefer unresponded, but include all if not enough
        query = """
            SELECT * FROM insights 
            WHERE status = 'pending'
            ORDER BY RANDOM()
            LIMIT ?
        """
        
        cursor.execute(query, (count,))
        results = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in results]
    
    def display_insights(self, insights: List[Dict], title: str):
        """Display insights in a nice format"""
        print("\n" + "="*70)
        print(f"🧠 {title}")
        print("="*70)
        print(f"Found {len(insights)} insights\n")
        
        for i, insight in enumerate(insights, 1):
            print(f"[{i}] ID: {insight['id']}")
            print(f"👤 {insight['shared_by']} | 📅 {insight['shared_date']}")
            print(f"🔖 {insight['source_type']}")
            
            if insight['tags']:
                tags = insight['tags'].split(',')
                print(f"🏷️  {', '.join(tags[:5])}")
            
            content = insight['content']
            if len(content) > 200:
                content = content[:200] + "..."
            print(f"💭 {content}")
            
            if insight['source_url']:
                url = insight['source_url']
                if len(url) > 80:
                    url = url[:80] + "..."
                print(f"🔗 {url}")
            
            print("-" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="Brain Gym Explorer - Explore your insights database"
    )
    
    parser.add_argument('--db', default='braingym.db', help='Database path')
    parser.add_argument('--search', help='Search by keyword')
    parser.add_argument('--tag', help='Filter by tag')
    parser.add_argument('--type', help='Filter by type (tweet/article/quote/etc)')
    parser.add_argument('--high-value', action='store_true', help='Show high-value insights')
    parser.add_argument('--random', type=int, metavar='N', help='Show N random insights')
    parser.add_argument('--tags-analysis', action='store_true', help='Analyze tag distribution')
    parser.add_argument('--limit', type=int, default=20, help='Limit results (default: 20)')
    
    args = parser.parse_args()
    
    explorer = BrainGymExplorer(args.db)
    
    if args.search:
        insights = explorer.search_by_keyword(args.search, args.limit)
        explorer.display_insights(insights, f"Search results for '{args.search}'")
    
    elif args.tag:
        insights = explorer.get_by_tag(args.tag, args.limit)
        explorer.display_insights(insights, f"Insights tagged with '{args.tag}'")
    
    elif args.type:
        insights = explorer.get_by_type(args.type, args.limit)
        explorer.display_insights(insights, f"Insights of type '{args.type}'")
    
    elif args.high_value:
        insights = explorer.get_high_value(args.limit)
        explorer.display_insights(insights, "High-Value Insights")
    
    elif args.random:
        insights = explorer.random_insights(args.random)
        explorer.display_insights(insights, f"{args.random} Random Insights")
    
    elif args.tags_analysis:
        print("\n" + "="*70)
        print("🏷️  TAG ANALYSIS")
        print("="*70)
        
        tag_counts = explorer.analyze_tags()
        
        print(f"\nTotal unique tags: {len(tag_counts)}")
        print(f"\nTop 30 tags:")
        
        for i, (tag, count) in enumerate(tag_counts.most_common(30), 1):
            bar = "█" * (count // 20)
            print(f"{i:2d}. {tag:20s} {count:4d} {bar}")
    
    else:
        parser.print_help()
        print("\n💡 Example usage:")
        print("  python3 explore.py --search 'startup'")
        print("  python3 explore.py --tag startups --limit 30")
        print("  python3 explore.py --type tweet")
        print("  python3 explore.py --high-value")
        print("  python3 explore.py --random 3")
        print("  python3 explore.py --tags-analysis")


if __name__ == "__main__":
    main()
