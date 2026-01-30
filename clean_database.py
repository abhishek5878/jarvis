#!/usr/bin/env python3
"""
Master script for cleaning and categorizing the Brain Gym database
Runs all cleaning operations in sequence
"""
import sys
import os


def main():
    print("\n" + "="*70)
    print("🧹 BRAIN GYM DATABASE CLEANING")
    print("="*70)
    
    print("\nThis script will:")
    print("  1. Update database schema (add new columns)")
    print("  2. Classify all insights into categories")
    print("  3. Find and mark duplicates")
    print("  4. Generate cleaning statistics")
    print("  5. Export review file")
    print("\nNote: Firecrawl extraction is run separately")
    
    proceed = input("\nProceed? (y/n): ").strip().lower()
    if proceed != 'y':
        print("Aborted.")
        return
    
    # Step 1: Schema migration
    print("\n" + "="*70)
    print("STEP 1: Database Schema Migration")
    print("="*70)
    
    from database_cleaned import CleanedDatabase
    db = CleanedDatabase('braingym.db')
    print("✅ Schema updated")
    
    # Step 2: Classification
    print("\n" + "="*70)
    print("STEP 2: Content Classification")
    print("="*70)
    
    from classifier_clean import classify_all_insights
    classify_all_insights('braingym.db')
    
    # Step 3: Deduplication
    print("\n" + "="*70)
    print("STEP 3: Deduplication")
    print("="*70)
    
    from deduplicator import run_deduplication
    run_deduplication('braingym.db')
    
    # Step 4: Generate stats
    print("\n" + "="*70)
    print("STEP 4: Cleaning Statistics")
    print("="*70)
    
    stats = db.get_cleaning_stats()
    print_cleaning_stats(stats)
    
    # Step 5: Export review file
    print("\n" + "="*70)
    print("STEP 5: Export Review File")
    print("="*70)
    
    export_review_file(db)
    
    print("\n" + "="*70)
    print("✅ CLEANING COMPLETE!")
    print("="*70)
    print("\nNext steps:")
    print("  1. Review 'needs_review.csv' and decide what to keep/remove")
    print("  2. Run Firecrawl extraction:")
    print("     export FIRECRAWL_API_KEY='your-key'")
    print("     python3 firecrawl_extractor.py")
    print("  3. Check extraction results and build web app with clean data")


def print_cleaning_stats(stats: dict):
    """Print cleaning statistics"""
    print("\n📊 CATEGORY BREAKDOWN:")
    for category, count in stats.get('by_category', {}).items():
        emoji = {
            'external_link': '🔗',
            'my_note': '📝',
            'personal': '❤️',
            'junk': '🗑️',
            'uncategorized': '❓'
        }.get(category, '📄')
        print(f"   {emoji} {category}: {count}")
    
    print(f"\n📈 USEFUL CONTENT:")
    useful = stats.get('by_usefulness', {})
    print(f"   Useful: {useful.get(1, 0)}")
    print(f"   Not useful: {useful.get(0, 0)}")
    
    print(f"\n🔄 DUPLICATES:")
    print(f"   Found: {stats.get('duplicate_count', 0)}")
    
    print(f"\n⚠️  NEEDS REVIEW:")
    print(f"   Flagged: {stats.get('needs_review_count', 0)}")
    
    if stats.get('extraction_status'):
        print(f"\n🌐 EXTRACTION STATUS:")
        for status, count in stats['extraction_status'].items():
            emoji = {
                'success': '✅',
                'pending': '⏳',
                'failed': '❌',
                'failed_404': '🔍',
                'failed_timeout': '⏱️',
                'failed_paywall': '🔒'
            }.get(status, '❔')
            print(f"   {emoji} {status}: {count}")
        
        if stats.get('avg_extracted_length'):
            print(f"\n   Average extracted length: {stats['avg_extracted_length']:,} chars")
    
    if stats.get('by_domain'):
        print(f"\n🌐 TOP DOMAINS:")
        for domain, count in sorted(stats['by_domain'].items(), 
                                    key=lambda x: x[1], reverse=True)[:10]:
            print(f"   {domain}: {count}")


def export_review_file(db):
    """Export items needing review to CSV"""
    import sqlite3
    import csv
    
    conn = sqlite3.connect(db.db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT 
            id,
            content_category,
            source_url,
            content,
            extraction_status,
            extraction_error,
            shared_by,
            shared_date
        FROM insights
        WHERE needs_review = 1
        ORDER BY content_category, id
    """)
    
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        print("✅ No items need review!")
        return
    
    filename = 'needs_review.csv'
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'ID', 'Category', 'URL', 'Content Preview', 
            'Extraction Status', 'Error', 'Shared By', 'Date'
        ])
        
        for row in rows:
            content_preview = row['content'][:200] + '...' if len(row['content']) > 200 else row['content']
            writer.writerow([
                row['id'],
                row['content_category'],
                row['source_url'] or 'N/A',
                content_preview,
                row['extraction_status'] or 'N/A',
                row['extraction_error'][:100] if row['extraction_error'] else 'N/A',
                row['shared_by'],
                row['shared_date']
            ])
    
    print(f"✅ Exported {len(rows)} items to: {filename}")
    print(f"   Review this file and decide what to keep/remove")


if __name__ == "__main__":
    main()
