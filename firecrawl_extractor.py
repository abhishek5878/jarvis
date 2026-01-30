"""
Firecrawl content extraction for external links
Fetches actual content from URLs and stores in database
"""
import os
import json
import time
from typing import Dict, Optional, List
from datetime import datetime
import sqlite3


class FirecrawlExtractor:
    """Extract content from URLs using Firecrawl API"""
    
    def __init__(self, api_key: str, db_path: str = "braingym.db"):
        self.api_key = api_key
        self.db_path = db_path
        
        # Import firecrawl
        try:
            from firecrawl import FirecrawlApp
            self.firecrawl = FirecrawlApp(api_key=api_key)
            print("✅ Firecrawl initialized")
        except ImportError:
            print("❌ Firecrawl not installed. Run: pip3 install firecrawl-py")
            raise
    
    def extract_from_url(self, url: str, timeout: int = 30) -> Dict:
        """
        Extract content from a single URL using Firecrawl
        Returns: dict with content, metadata, status, error
        """
        try:
            # Use Firecrawl's scrape endpoint (correct method name and params)
            result = self.firecrawl.scrape(
                url=url,
                formats=['markdown'],
                only_main_content=True
            )
            
            if result and hasattr(result, 'markdown') and result.markdown:
                # Extract metadata from Document object
                metadata_obj = getattr(result, 'metadata', {}) or {}
                metadata = {
                    'title': getattr(metadata_obj, 'title', '') if hasattr(metadata_obj, 'title') else '',
                    'description': getattr(metadata_obj, 'description', '') if hasattr(metadata_obj, 'description') else '',
                    'domain': self._extract_domain(url),
                    'extracted_at': datetime.now().isoformat(),
                    'word_count': len(result.markdown.split()),
                    'char_count': len(result.markdown),
                }
                
                return {
                    'content': result.markdown,
                    'metadata': json.dumps(metadata),
                    'status': 'success',
                    'error': None
                }
            else:
                return {
                    'content': None,
                    'metadata': None,
                    'status': 'failed',
                    'error': 'No content extracted'
                }
        
        except Exception as e:
            error_msg = str(e)
            
            # Categorize errors
            if '404' in error_msg or 'not found' in error_msg.lower():
                status = 'failed_404'
            elif 'timeout' in error_msg.lower():
                status = 'failed_timeout'
            elif 'rate limit' in error_msg.lower():
                status = 'failed_rate_limit'
            elif 'paywall' in error_msg.lower() or 'forbidden' in error_msg.lower():
                status = 'failed_paywall'
            else:
                status = 'failed'
            
            return {
                'content': None,
                'metadata': None,
                'status': status,
                'error': error_msg[:500]  # Limit error message length
            }
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc
    
    def process_batch(self, insights: List[Dict], batch_size: int = 50, 
                     delay: float = 1.0) -> Dict:
        """
        Process a batch of insights
        Returns: stats dict with counts
        """
        from database_cleaned import CleanedDatabase
        
        db = CleanedDatabase(self.db_path)
        
        stats = {
            'total': len(insights),
            'success': 0,
            'failed': 0,
            'failed_404': 0,
            'failed_timeout': 0,
            'failed_rate_limit': 0,
            'failed_paywall': 0,
            'skipped': 0,
            'total_chars_extracted': 0,
            'by_domain': {}
        }
        
        for i, insight in enumerate(insights, 1):
            insight_id = insight['id']
            url = insight['source_url']
            
            # Skip if already successfully extracted
            if insight.get('extraction_status') == 'success':
                stats['skipped'] += 1
                print(f"  [{i}/{len(insights)}] Skipped (already extracted): {url[:60]}...")
                continue
            
            print(f"\n  [{i}/{len(insights)}] Extracting: {url[:60]}...")
            
            # Extract content
            result = self.extract_from_url(url)
            
            # Update database
            db.update_extraction(
                insight_id=insight_id,
                extracted_text=result['content'],
                metadata=result['metadata'],
                status=result['status'],
                error=result['error']
            )
            
            # Update stats
            if result['status'] == 'success':
                stats['success'] += 1
                if result['content']:
                    stats['total_chars_extracted'] += len(result['content'])
                
                # Track by domain
                if result['metadata']:
                    metadata = json.loads(result['metadata'])
                    domain = metadata.get('domain', 'unknown')
                    stats['by_domain'][domain] = stats['by_domain'].get(domain, 0) + 1
                
                print(f"    ✓ Success ({len(result['content'])} chars)")
            else:
                stats['failed'] += 1
                if result['status'] in stats:
                    stats[result['status']] += 1
                print(f"    ✗ {result['status']}: {result['error'][:100]}")
            
            # Rate limiting delay
            if i < len(insights):
                time.sleep(delay)
        
        return stats
    
    def process_all(self, batch_size: int = 100, delay: float = 1.0, 
                   max_items: int = None) -> Dict:
        """
        Process all insights needing extraction
        """
        from database_cleaned import CleanedDatabase
        
        db = CleanedDatabase(self.db_path)
        
        print("\n🚀 Starting Firecrawl Content Extraction")
        print("=" * 70)
        
        # Get insights needing extraction
        insights = db.get_insights_needing_extraction(limit=max_items)
        
        if not insights:
            print("✅ No insights need extraction!")
            return {}
        
        print(f"\nFound {len(insights)} insights to extract")
        print(f"Batch size: {batch_size}, Delay: {delay}s between requests")
        print("\nStarting extraction...\n")
        
        # Process in batches
        all_stats = {
            'total': len(insights),
            'success': 0,
            'failed': 0,
            'failed_404': 0,
            'failed_timeout': 0,
            'failed_rate_limit': 0,
            'failed_paywall': 0,
            'skipped': 0,
            'total_chars_extracted': 0,
            'by_domain': {},
            'started_at': datetime.now().isoformat(),
        }
        
        for batch_start in range(0, len(insights), batch_size):
            batch_end = min(batch_start + batch_size, len(insights))
            batch = insights[batch_start:batch_end]
            
            print(f"\n{'='*70}")
            print(f"BATCH {batch_start//batch_size + 1}: Items {batch_start+1}-{batch_end}")
            print(f"{'='*70}")
            
            batch_stats = self.process_batch(batch, batch_size, delay)
            
            # Aggregate stats
            for key in ['success', 'failed', 'failed_404', 'failed_timeout', 
                       'failed_rate_limit', 'failed_paywall', 'skipped', 'total_chars_extracted']:
                all_stats[key] += batch_stats.get(key, 0)
            
            # Merge domain stats
            for domain, count in batch_stats.get('by_domain', {}).items():
                all_stats['by_domain'][domain] = all_stats['by_domain'].get(domain, 0) + count
            
            # Show progress
            completed = batch_end
            print(f"\n📊 Progress: {completed}/{len(insights)} ({completed/len(insights)*100:.1f}%)")
            print(f"   Success: {all_stats['success']}, Failed: {all_stats['failed']}, Skipped: {all_stats['skipped']}")
        
        all_stats['completed_at'] = datetime.now().isoformat()
        
        # Save stats to file
        stats_file = f"extraction_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(stats_file, 'w') as f:
            json.dump(all_stats, f, indent=2)
        
        print(f"\n✅ Extraction complete! Stats saved to: {stats_file}")
        
        return all_stats


def print_extraction_summary(stats: Dict):
    """Print a nice summary of extraction results"""
    print("\n" + "="*70)
    print("📊 EXTRACTION SUMMARY")
    print("="*70)
    
    total = stats['total']
    success = stats['success']
    failed = stats['failed']
    skipped = stats['skipped']
    
    print(f"\n✅ Total processed: {total}")
    print(f"   Success: {success} ({success/total*100:.1f}%)")
    print(f"   Failed: {failed} ({failed/total*100:.1f}%)")
    print(f"   Skipped: {skipped} ({skipped/total*100:.1f}%)")
    
    print(f"\n📝 Content extracted:")
    print(f"   Total characters: {stats['total_chars_extracted']:,}")
    print(f"   Average per item: {stats['total_chars_extracted']//success:,}" if success > 0 else "   N/A")
    
    if stats.get('failed_404') or stats.get('failed_timeout') or stats.get('failed_paywall'):
        print(f"\n❌ Failure breakdown:")
        if stats.get('failed_404'):
            print(f"   404 Not Found: {stats['failed_404']}")
        if stats.get('failed_timeout'):
            print(f"   Timeout: {stats['failed_timeout']}")
        if stats.get('failed_rate_limit'):
            print(f"   Rate Limited: {stats['failed_rate_limit']}")
        if stats.get('failed_paywall'):
            print(f"   Paywall/Forbidden: {stats['failed_paywall']}")
        other_failed = failed - sum([stats.get('failed_404', 0), stats.get('failed_timeout', 0), 
                                     stats.get('failed_rate_limit', 0), stats.get('failed_paywall', 0)])
        if other_failed > 0:
            print(f"   Other errors: {other_failed}")
    
    if stats.get('by_domain'):
        print(f"\n🌐 By domain:")
        for domain, count in sorted(stats['by_domain'].items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   {domain}: {count}")


if __name__ == "__main__":
    # Check for API key
    api_key = os.getenv('FIRECRAWL_API_KEY')
    
    if not api_key:
        print("❌ Error: FIRECRAWL_API_KEY environment variable not set")
        print("\nUsage:")
        print("  export FIRECRAWL_API_KEY='your-api-key'")
        print("  python3 firecrawl_extractor.py")
        exit(1)
    
    # Run extraction
    extractor = FirecrawlExtractor(api_key)
    
    # Process all (or specify max_items for testing)
    # For testing: stats = extractor.process_all(batch_size=10, max_items=20)
    stats = extractor.process_all(batch_size=50, delay=1.0)
    
    # Print summary
    print_extraction_summary(stats)
