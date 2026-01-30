"""
Content classifier for categorizing insights
Determines: external_link, my_note, personal, junk
"""
import re
from typing import Dict, Tuple
from difflib import SequenceMatcher


class ContentClassifier:
    """Classifies insights into categories"""
    
    # Keywords that indicate personal/relationship content
    PERSONAL_KEYWORDS = [
        'love', 'relationship', 'hurt', 'heart', 'boyfriend', 'girlfriend',
        'dating', 'breakup', 'miss you', 'i love you', 'vasu', 'care about you'
    ]
    
    # Very short responses that are junk
    JUNK_PHRASES = [
        'ok', 'okay', 'yes', 'no', 'thanks', 'thank you', 'lol', 'haha',
        'done', '👍', '👌', 'nice', 'good', 'great', 'cool', 'sure'
    ]
    
    # System message patterns (additional to parser's filters)
    SYSTEM_PATTERNS = [
        r'image omitted',
        r'document omitted',
        r'video omitted',
        r'audio omitted',
        r'sticker omitted',
        r'GIF omitted',
        r'created this group',
        r'changed the group',
        r'added',
        r'removed',
        r'left',
        r'Messages and calls are end-to-end encrypted'
    ]
    
    def classify(self, insight: Dict) -> Tuple[str, bool, bool]:
        """
        Classify an insight
        Returns: (category, has_useful_content, needs_review)
        """
        content = insight.get('content', '').lower()
        source_url = insight.get('source_url')
        shared_by = insight.get('shared_by', '')
        content_length = len(content)
        
        # Check for system messages (junk)
        if self._is_system_message(content):
            return ('junk', False, False)
        
        # Check for very short junk
        if self._is_junk(content, content_length):
            return ('junk', False, False)
        
        # Check for personal content
        if self._is_personal(content, shared_by):
            return ('personal', False, True)  # Needs review
        
        # Has URL - likely external link
        if source_url:
            # Check if it's a useful external link
            if self._is_useful_url(source_url, content):
                return ('external_link', True, False)
            else:
                return ('external_link', True, True)  # Needs review
        
        # No URL - check if it's a useful note
        if self._is_useful_note(content, content_length):
            return ('my_note', True, False)
        
        # Edge case - needs review
        return ('my_note', False, True)
    
    def _is_system_message(self, content: str) -> bool:
        """Check if content is a system message"""
        for pattern in self.SYSTEM_PATTERNS:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False
    
    def _is_junk(self, content: str, length: int) -> bool:
        """Check if content is junk (too short, meaningless)"""
        # Very short
        if length < 20:
            # Check against junk phrases
            content_clean = content.strip().lower()
            if content_clean in self.JUNK_PHRASES:
                return True
            # Only emojis or very short
            if len(content_clean) < 3:
                return True
        return False
    
    def _is_personal(self, content: str, shared_by: str) -> bool:
        """Check if content is personal/relationship related"""
        # From "Life I want" group - likely personal
        if shared_by == 'Life I want':
            return True
        
        # Check for personal keywords
        personal_count = sum(1 for keyword in self.PERSONAL_KEYWORDS 
                           if keyword in content)
        
        # If multiple personal keywords, it's personal
        if personal_count >= 2:
            return True
        
        # Very emotional/personal tone indicators
        emotional_indicators = ['i miss', 'i hurt', 'i feel', 'my heart', 
                               'i want you', 'i need you', 'i care']
        if any(indicator in content for indicator in emotional_indicators):
            return True
        
        return False
    
    def _is_useful_url(self, url: str, content: str) -> bool:
        """Check if URL is useful (not spam, not dead link indicator)"""
        # Known good domains
        good_domains = [
            'linkedin.com', 'twitter.com', 'x.com', 'youtube.com',
            'medium.com', 'substack.com', 'github.com', 'reddit.com',
            'arxiv.org', 'techcrunch.com', 'ycombinator.com'
        ]
        
        # Check if URL is from known good source
        if any(domain in url.lower() for domain in good_domains):
            return True
        
        # URL is very short with no context - might need review
        if len(content) < 50 and content.strip() == url.strip():
            return False  # Just a bare URL, needs review
        
        return True
    
    def _is_useful_note(self, content: str, length: int) -> bool:
        """Check if note has useful content"""
        # Too short
        if length < 100:
            return False
        
        # Too long (might be document dump)
        if length > 5000:
            return False
        
        # Check for substantive content indicators
        substantive_indicators = [
            # Questions
            'how', 'what', 'why', 'when', 'where',
            # Analysis
            'because', 'therefore', 'however', 'although',
            # Lists/structure
            '1.', '2.', '•', '-',
            # Thoughtful language
            'think', 'believe', 'consider', 'realize', 'understand'
        ]
        
        indicator_count = sum(1 for indicator in substantive_indicators 
                             if indicator in content)
        
        # Has some structure/thought
        if indicator_count >= 3:
            return True
        
        # Check for multiple sentences (structured thought)
        sentences = content.split('.')
        if len(sentences) >= 3:
            return True
        
        return False
    
    def similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (0-1)"""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    def is_duplicate(self, insight1: Dict, insight2: Dict, threshold: float = 0.8) -> bool:
        """Check if two insights are duplicates"""
        # Same URL is definitely duplicate
        url1 = insight1.get('source_url')
        url2 = insight2.get('source_url')
        
        if url1 and url2 and url1 == url2:
            return True
        
        # Very similar content
        content1 = insight1.get('content', '')
        content2 = insight2.get('content', '')
        
        if content1 and content2:
            similarity = self.similarity(content1, content2)
            if similarity >= threshold:
                return True
        
        return False


def classify_all_insights(db_path: str = "braingym.db"):
    """Classify all insights in the database"""
    from database_cleaned import CleanedDatabase
    import sqlite3
    
    db = CleanedDatabase(db_path)
    classifier = ContentClassifier()
    
    # Get all insights
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM insights ORDER BY id")
    insights = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    print(f"\n🔍 Classifying {len(insights)} insights...")
    print("=" * 60)
    
    categories_count = {
        'external_link': 0,
        'my_note': 0,
        'personal': 0,
        'junk': 0
    }
    
    for i, insight in enumerate(insights, 1):
        category, has_useful, needs_review = classifier.classify(insight)
        
        db.update_category(
            insight['id'],
            category,
            has_useful,
            needs_review
        )
        
        categories_count[category] += 1
        
        # Progress
        if i % 100 == 0:
            print(f"Progress: {i}/{len(insights)} ({i/len(insights)*100:.1f}%)")
    
    print("\n✅ Classification complete!")
    print("\n📊 Results:")
    for category, count in categories_count.items():
        print(f"   {category}: {count}")
    
    return categories_count
