#!/usr/bin/env python3
"""
View cleaning and extraction statistics
"""
from database_cleaned import CleanedDatabase


def main():
    db = CleanedDatabase('braingym.db')
    stats = db.get_cleaning_stats()
    
    print("\n" + "="*70)
    print("📊 BRAIN GYM DATABASE STATISTICS")
    print("="*70)
    
    print("\n📁 CATEGORY BREAKDOWN:")
    total = sum(stats.get('by_category', {}).values())
    for category, count in sorted(stats.get('by_category', {}).items(), 
                                  key=lambda x: x[1], reverse=True):
        pct = (count / total * 100) if total > 0 else 0
        emoji = {
            'external_link': '🔗',
            'my_note': '📝',
            'personal': '❤️',
            'junk': '🗑️',
            'uncategorized': '❓'
        }.get(category, '📄')
        bar = '█' * int(pct / 2)
        print(f"   {emoji} {category:15s} {count:4d} ({pct:5.1f}%) {bar}")
    print(f"\n   TOTAL: {total}")
    
    print(f"\n✨ CONTENT QUALITY:")
    useful = stats.get('by_usefulness', {})
    useful_count = useful.get(1, 0)
    not_useful = useful.get(0, 0)
    total_checked = useful_count + not_useful
    if total_checked > 0:
        useful_pct = (useful_count / total_checked * 100)
        print(f"   Useful:     {useful_count:4d} ({useful_pct:.1f}%)")
        print(f"   Not useful: {not_useful:4d} ({100-useful_pct:.1f}%)")
    
    print(f"\n🔄 DUPLICATES:")
    dup_count = stats.get('duplicate_count', 0)
    print(f"   Found and marked: {dup_count}")
    if total > 0:
        print(f"   Percentage: {dup_count/total*100:.1f}%")
    
    print(f"\n⚠️  NEEDS REVIEW:")
    review_count = stats.get('needs_review_count', 0)
    print(f"   Flagged: {review_count}")
    
    if stats.get('extraction_status'):
        print(f"\n🌐 CONTENT EXTRACTION STATUS:")
        ext_stats = stats['extraction_status']
        total_ext = sum(ext_stats.values())
        
        for status in ['success', 'pending', 'failed', 'failed_404', 
                      'failed_timeout', 'failed_rate_limit', 'failed_paywall']:
            count = ext_stats.get(status, 0)
            if count > 0:
                pct = (count / total_ext * 100) if total_ext > 0 else 0
                emoji = {
                    'success': '✅',
                    'pending': '⏳',
                    'failed': '❌',
                    'failed_404': '🔍',
                    'failed_timeout': '⏱️',
                    'failed_rate_limit': '🚦',
                    'failed_paywall': '🔒'
                }.get(status, '❔')
                print(f"   {emoji} {status:18s} {count:4d} ({pct:5.1f}%)")
        
        if stats.get('avg_extracted_length'):
            avg_len = stats['avg_extracted_length']
            print(f"\n   📏 Average extracted: {avg_len:,} characters")
            print(f"   📚 Estimated words: {avg_len // 5:,}")
    
    if stats.get('by_domain'):
        print(f"\n🌐 TOP SOURCES:")
        for i, (domain, count) in enumerate(sorted(stats['by_domain'].items(), 
                                                   key=lambda x: x[1], reverse=True)[:15], 1):
            emoji = {
                'LinkedIn': '💼',
                'Twitter': '🐦',
                'YouTube': '📹',
                'GitHub': '💻',
                'Medium': '📝',
                'Substack': '📧',
                'Reddit': '🤖'
            }.get(domain, '🔗')
            print(f"   {i:2d}. {emoji} {domain:20s} {count:4d}")
    
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
