#!/usr/bin/env python3
"""
Smart extraction strategy: Extract 100 best articles + prepare social references
"""
import sqlite3
import json
from datetime import datetime, timedelta
from typing import List, Dict
from firecrawl_extractor import FirecrawlExtractor


class SmartExtractor:
    """Smart extraction: Best 100 articles + social reference preparation"""
    
    def __init__(self, api_key: str, db_path: str = "braingym.db"):
        self.api_key = api_key
        self.db_path = db_path
        self.extractor = FirecrawlExtractor(api_key, db_path)
        
    def select_best_100_articles(self) -> List[Dict]:
        """
        Select 100 best articles for extraction
        Criteria: quality score, diversity, recency, variety
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get extractable URLs with quality scores
        cursor.execute("""
            SELECT *, 
                   CASE 
                       WHEN shared_date LIKE '%/26%' OR shared_date LIKE '%/25%' THEN 3
                       WHEN shared_date LIKE '%/24%' THEN 1
                       ELSE 0
                   END as recency_bonus,
                   CASE 
                       WHEN source_url LIKE '%medium.com%' OR source_url LIKE '%substack.com%' 
                            OR source_url LIKE '%github.com%' OR source_url LIKE '%fs.blog%' THEN 2
                       ELSE 0
                   END as domain_bonus
            FROM insights 
            WHERE content_category = 'external_link'
            AND extraction_status = 'pending'
            AND source_url NOT LIKE '%linkedin.com%'
            AND source_url NOT LIKE '%twitter.com%'
            AND source_url NOT LIKE '%x.com%'
            ORDER BY (quality_score + recency_bonus + domain_bonus) DESC, 
                     shared_date DESC
            LIMIT 200
        """)
        
        candidates = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Diversify by domain
        selected = []
        domain_counts = {}
        
        for insight in candidates:
            if len(selected) >= 100:
                break
            
            # Extract domain
            url = insight['source_url']
            domain = self._extract_domain(url)
            
            # Limit per domain (max 15 from same source)
            if domain_counts.get(domain, 0) < 15:
                selected.append(insight)
                domain_counts[domain] = domain_counts.get(domain, 0) + 1
        
        return selected
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL (handles invalid URLs gracefully)"""
        if not url:
            return 'unknown'
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            return domain if domain else 'unknown'
        except Exception:
            # Handle invalid URLs
            if '://' in url:
                domain = url.split('://')[1].split('/')[0]
                return domain.replace('www.', '')
            return 'unknown'
    
    def extract_best_100(self, delay: float = 1.5) -> Dict:
        """Extract content from best 100 articles"""
        print("\n🎯 Smart Extraction: Best 100 Articles")
        print("="*70)
        
        articles = self.select_best_100_articles()
        print(f"\n✅ Selected {len(articles)} best articles")
        print("\nCriteria:")
        print("  - Quality score 5+")
        print("  - Recent content prioritized")
        print("  - Diverse domains (max 15 per site)")
        print("  - High-value sources (Medium, Substack, GitHub, etc.)")
        
        # Show domain breakdown
        domains = {}
        for article in articles:
            domain = self._extract_domain(article['source_url'])
            domains[domain] = domains.get(domain, 0) + 1
        
        print(f"\n📊 Domain diversity (top 10):")
        for domain, count in sorted(domains.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   {domain}: {count}")
        
        print(f"\n🚀 Starting extraction...")
        print(f"   Delay: {delay}s between requests")
        print(f"   Estimated time: ~{int(len(articles) * delay / 60)} minutes\n")
        
        # Extract with progress and checkpointing
        stats = self.extractor.process_batch(articles, delay=delay)
        
        return stats
    
    def prepare_social_references(self):
        """Prepare LinkedIn and Twitter URLs as smart references"""
        print("\n📱 Preparing Social Media References")
        print("="*70)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get all social media URLs
        cursor.execute("""
            SELECT id, source_url, content, context_message, source_type
            FROM insights 
            WHERE (source_url LIKE '%linkedin.com%' 
                   OR source_url LIKE '%twitter.com%' 
                   OR source_url LIKE '%x.com%')
            AND extraction_status = 'pending'
        """)
        
        social_links = cursor.fetchall()
        print(f"\nFound {len(social_links)} social media links")
        
        linkedin_count = 0
        twitter_count = 0
        
        for insight_id, url, content, context, source_type in social_links:
            # Create smart reference
            platform = "LinkedIn" if "linkedin" in url else "Twitter/X"
            
            reference_text = f"""# {platform} Reference

**Original Post:** {url}

**Context (when you saved it):**
{context or content}

**Note:** This is a reference to a {platform} post. Click "View Original" to see the full content on {platform}.

---
*Social media platforms block content extraction. This reference preserves your context and provides direct access to the original.*
"""
            
            metadata = json.dumps({
                'platform': platform,
                'url': url,
                'saved_date': datetime.now().isoformat(),
                'type': 'social_reference'
            })
            
            # Update database
            cursor.execute("""
                UPDATE insights 
                SET extracted_text = ?,
                    extracted_metadata = ?,
                    extraction_status = 'social_reference',
                    extraction_date = ?,
                    content_category = 'social_reference'
                WHERE id = ?
            """, (reference_text, metadata, datetime.now().isoformat(), insight_id))
            
            if platform == "LinkedIn":
                linkedin_count += 1
            else:
                twitter_count += 1
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ Prepared {len(social_links)} social references:")
        print(f"   LinkedIn: {linkedin_count}")
        print(f"   Twitter/X: {twitter_count}")
        
        return {'linkedin': linkedin_count, 'twitter': twitter_count}
    
    def enhance_categorization(self):
        """Enhance content categories with more specific types"""
        print("\n🏷️  Enhancing Content Categorization")
        print("="*70)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Update categories based on URL patterns and content
        updates = [
            # Articles with extracted content
            ("article", "source_url IS NOT NULL AND extracted_text IS NOT NULL AND extraction_status = 'success'"),
            
            # YouTube videos
            ("video", "source_url LIKE '%youtube.com%' OR source_url LIKE '%youtu.be%'"),
            
            # GitHub code/docs
            ("code", "source_url LIKE '%github.com%'"),
            
            # Reddit discussions
            ("discussion", "source_url LIKE '%reddit.com%'"),
            
            # Social references (already handled above)
            # My notes (already categorized)
            # Personal, junk (already categorized)
        ]
        
        for category, condition in updates:
            cursor.execute(f"""
                UPDATE insights 
                SET content_category = ?
                WHERE {condition}
            """, (category,))
            print(f"   {category}: {cursor.rowcount} insights")
        
        # Add useful_for_daily flag
        cursor.execute("ALTER TABLE insights ADD COLUMN useful_for_daily INTEGER DEFAULT 1")
        
        # Mark personal and junk as not useful for daily
        cursor.execute("""
            UPDATE insights 
            SET useful_for_daily = 0 
            WHERE content_category IN ('personal', 'junk')
        """)
        
        print(f"\n   Excluded from daily: {cursor.rowcount} (personal/junk)")
        
        conn.commit()
        conn.close()
        
        print("\n✅ Categorization enhanced")
    
    def enhance_quality_scores(self):
        """Update quality scores based on extracted content"""
        print("\n⭐ Enhancing Quality Scores")
        print("="*70)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Enhance based on extracted content
        cursor.execute("""
            UPDATE insights 
            SET quality_score = quality_score + 
                CASE 
                    WHEN LENGTH(extracted_text) > 5000 THEN 1
                    WHEN LENGTH(extracted_text) > 2000 THEN 0.5
                    ELSE 0
                END
            WHERE extraction_status = 'success'
        """)
        print(f"   Enhanced {cursor.rowcount} articles (based on length)")
        
        # Enhance based on metadata presence
        cursor.execute("""
            UPDATE insights 
            SET quality_score = quality_score + 0.5
            WHERE extracted_metadata IS NOT NULL 
            AND extracted_metadata LIKE '%title%'
        """)
        print(f"   Enhanced {cursor.rowcount} with metadata")
        
        # Enhance high-quality domains
        quality_domains = ['medium.com', 'substack.com', 'fs.blog', 'github.com']
        for domain in quality_domains:
            cursor.execute(f"""
                UPDATE insights 
                SET quality_score = quality_score + 1
                WHERE source_url LIKE '%{domain}%'
                AND quality_score < 9
            """)
        
        # Enhance long personal notes
        cursor.execute("""
            UPDATE insights 
            SET quality_score = quality_score + 1
            WHERE content_category = 'my_note'
            AND content_length > 300
            AND quality_score < 9
        """)
        print(f"   Enhanced {cursor.rowcount} substantial notes")
        
        conn.commit()
        conn.close()
        
        print("\n✅ Quality scores enhanced")


def run_smart_extraction(api_key: str):
    """Run complete smart extraction process"""
    extractor = SmartExtractor(api_key)
    
    print("\n" + "="*70)
    print("🧠 BRAIN GYM: SMART EXTRACTION")
    print("="*70)
    print("\nPhase 1.5: Extract 100 best + prepare social references")
    print("="*70)
    
    # Step 1: Extract best 100 articles
    print("\n[1/5] Extracting Best 100 Articles")
    extraction_stats = extractor.extract_best_100(delay=1.5)
    
    # Step 2: Prepare social references
    print("\n[2/5] Preparing Social Media References")
    social_stats = extractor.prepare_social_references()
    
    # Step 3: Enhance categorization
    print("\n[3/5] Enhancing Categorization")
    try:
        extractor.enhance_categorization()
    except Exception as e:
        if "duplicate column" not in str(e):
            print(f"   Note: {e}")
    
    # Step 4: Enhance quality scores
    print("\n[4/5] Enhancing Quality Scores")
    extractor.enhance_quality_scores()
    
    # Step 5: Generate stats
    print("\n[5/5] Generating Statistics Report")
    from view_stats import main as view_stats
    view_stats()
    
    # Final summary
    print("\n" + "="*70)
    print("✅ SMART EXTRACTION COMPLETE")
    print("="*70)
    
    print(f"\n📊 Results:")
    print(f"   Articles extracted: {extraction_stats.get('success', 0)}/100")
    print(f"   Social references: {social_stats['linkedin'] + social_stats['twitter']}")
    print(f"   Ready for web interface!")
    
    print(f"\n🎯 Next: Build Flask web app (Phase 2)")
    
    return {
        'extraction': extraction_stats,
        'social': social_stats
    }


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python3 smart_extractor.py <FIRECRAWL_API_KEY>")
        sys.exit(1)
    
    api_key = sys.argv[1]
    run_smart_extraction(api_key)
