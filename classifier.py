"""
Content classifier for Brain Gym
Auto-tags insights based on content analysis
"""
import re
from typing import List, Set


class InsightClassifier:
    """Classifies and tags insights based on content"""
    
    # Keyword-based classification
    THEME_KEYWORDS = {
        'startups': [
            'startup', 'founder', 'entrepreneurship', 'venture', 'funding',
            'investor', 'pitch', 'product-market fit', 'pmf', 'mvp',
            'scale', 'growth', 'revenue', 'business model'
        ],
        'productivity': [
            'productivity', 'time management', 'focus', 'deep work',
            'habit', 'routine', 'efficiency', 'workflow', 'system',
            'discipline', 'procrastination', 'todo', 'gtd'
        ],
        'writing': [
            'writing', 'writer', 'content', 'storytelling', 'narrative',
            'blog', 'article', 'essay', 'publish', 'author', 'copywriting',
            'editing', 'draft'
        ],
        'mental_models': [
            'mental model', 'framework', 'thinking', 'cognitive', 'bias',
            'decision making', 'first principles', 'systems thinking',
            'mental', 'model', 'principle'
        ],
        'philosophy': [
            'philosophy', 'stoic', 'meaning', 'purpose', 'existence',
            'ethics', 'moral', 'wisdom', 'virtue', 'life philosophy'
        ],
        'tech': [
            'technology', 'software', 'ai', 'ml', 'artificial intelligence',
            'coding', 'programming', 'developer', 'engineer', 'tech',
            'digital', 'saas', 'api', 'platform'
        ],
        'marketing': [
            'marketing', 'branding', 'brand', 'positioning', 'messaging',
            'audience', 'customer', 'distribution', 'growth marketing',
            'viral', 'seo', 'content marketing'
        ],
        'psychology': [
            'psychology', 'behavior', 'behavioral', 'motivation',
            'emotion', 'mindset', 'mindfulness', 'therapy', 'mental health'
        ],
        'learning': [
            'learning', 'education', 'teaching', 'skill', 'knowledge',
            'study', 'course', 'training', 'expertise', 'mastery'
        ],
        'creativity': [
            'creativity', 'creative', 'innovation', 'idea', 'ideation',
            'brainstorm', 'imagination', 'design', 'art', 'artistic'
        ]
    }
    
    # Type detection patterns
    TYPE_PATTERNS = {
        'tactical': [
            'how to', 'step by step', 'guide', 'tutorial', 'tip',
            'hack', 'trick', 'method', 'strategy', 'tactic'
        ],
        'philosophical': [
            'why', 'meaning', 'purpose', 'believe', 'philosophy',
            'perspective', 'view', 'think about', 'reflection'
        ],
        'cautionary': [
            'mistake', 'avoid', 'warning', 'don\'t', 'failure',
            'lesson learned', 'pitfall', 'wrong', 'error', 'regret'
        ],
        'inspirational': [
            'inspire', 'motivation', 'success', 'achieve', 'dream',
            'goal', 'ambitious', 'vision', 'possible'
        ],
        'data_driven': [
            'data', 'research', 'study', 'statistics', 'analysis',
            'survey', 'experiment', 'evidence', 'metric', 'number'
        ]
    }
    
    def classify(self, content: str, context: str = "") -> List[str]:
        """Classify content and return list of tags"""
        tags: Set[str] = set()
        
        # Combine content and context for analysis
        full_text = f"{content} {context}".lower()
        
        # Theme-based tags
        for theme, keywords in self.THEME_KEYWORDS.items():
            if any(keyword in full_text for keyword in keywords):
                tags.add(theme)
        
        # Type-based tags
        for type_name, patterns in self.TYPE_PATTERNS.items():
            if any(pattern in full_text for pattern in patterns):
                tags.add(type_name)
        
        # Source-specific tags (handled separately)
        
        return list(tags)
    
    def add_source_tags(self, tags: List[str], source_type: str, source_url: str = "") -> List[str]:
        """Add tags specific to the source type"""
        if source_type == 'tweet':
            tags.append('twitter')
            # Check if it's a thread
            if 'thread' in source_url.lower():
                tags.append('thread')
        
        elif source_type == 'linkedin':
            tags.append('linkedin')
        
        elif source_type == 'video':
            tags.append('video')
        
        elif source_type == 'article':
            tags.append('article')
            # Check for specific platforms
            if 'medium.com' in source_url.lower():
                tags.append('medium')
            elif 'substack.com' in source_url.lower():
                tags.append('substack')
        
        return tags
    
    def is_high_value(self, content: str, context: str = "") -> bool:
        """
        Determine if an insight is particularly valuable
        Based on length, depth, and certain indicators
        """
        full_text = f"{content} {context}"
        
        # Long-form content tends to be more valuable
        if len(full_text) > 200:
            return True
        
        # Check for high-value indicators
        high_value_indicators = [
            'framework', 'mental model', 'system', 'principle',
            'insight', 'breakthrough', 'counterintuitive',
            'surprising', 'discovered', 'learned', 'realized'
        ]
        
        text_lower = full_text.lower()
        indicator_count = sum(1 for indicator in high_value_indicators if indicator in text_lower)
        
        return indicator_count >= 2
    
    def enhance_tags(self, tags: List[str]) -> List[str]:
        """Add meta-tags based on existing tags"""
        enhanced = set(tags)
        
        # Add meta-category tags
        if any(tag in ['startups', 'marketing', 'tech'] for tag in tags):
            enhanced.add('business')
        
        if any(tag in ['productivity', 'learning', 'mental_models'] for tag in tags):
            enhanced.add('self_improvement')
        
        if any(tag in ['philosophy', 'psychology', 'creativity'] for tag in tags):
            enhanced.add('mindset')
        
        return list(enhanced)
