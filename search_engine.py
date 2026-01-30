"""
Content Search Engine
Searches database for insights relevant to a topic
"""
import sqlite3
from typing import List, Dict, Optional
import re
from collections import Counter


class ContentSearchEngine:
    """Search and analyze insights from the database"""
    
    def __init__(self, db_path: str = "braingym.db"):
        self.db_path = db_path
    
    def get_connection(self):
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def search(self, topic: str, limit: int = 10) -> List[Dict]:
        """
        Find relevant insights for a topic
        
        Algorithm:
        1. Keyword matching in content, extracted_text, tags
        2. Score by relevance
        3. Return top N sorted by relevance * quality
        4. Ensure variety
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Extract keywords from topic
        keywords = self._extract_keywords(topic)
        
        # Search query
        query = """
            SELECT 
                id, content, source_url, source_type,
                content_category, tags, quality_score,
                extracted_text, extracted_metadata,
                context_message
            FROM insights
            WHERE useful_for_daily = 1
            AND content_category NOT IN ('junk', 'personal')
        """
        
        cursor.execute(query)
        all_insights = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Score each insight
        scored_insights = []
        for insight in all_insights:
            score = self._calculate_relevance(insight, topic, keywords)
            if score > 0:  # Only include relevant items
                insight['relevance_score'] = score
                # Parse tags if string
                if isinstance(insight['tags'], str) and insight['tags']:
                    insight['tags'] = [t.strip() for t in insight['tags'].split(',')]
                else:
                    insight['tags'] = []
                scored_insights.append(insight)
        
        # Sort by combined score (relevance * quality)
        scored_insights.sort(
            key=lambda x: x['relevance_score'] * (x['quality_score'] or 5),
            reverse=True
        )
        
        # Ensure variety
        final_results = self._ensure_variety(scored_insights, limit)
        
        return final_results
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        # Convert to lowercase, split on whitespace/punctuation
        words = re.findall(r'\w+', text.lower())
        
        # Filter out common words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 
            'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were',
            'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'should', 'could', 'may', 'might', 'must',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which',
            'who', 'when', 'where', 'why', 'how', 'about', 'this', 'that'
        }
        
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords
    
    def _calculate_relevance(self, insight: Dict, topic: str, keywords: List[str]) -> float:
        """Calculate relevance score for an insight"""
        score = 0.0
        
        # Combine all searchable text
        searchable_text = ' '.join([
            insight['content'] or '',
            insight['extracted_text'] or '',
            insight['context_message'] or '',
            ' '.join(insight.get('tags', []) if isinstance(insight.get('tags'), list) else [])
        ]).lower()
        
        # Exact phrase match (highest score)
        if topic.lower() in searchable_text:
            score += 5.0
        
        # Keyword matches
        keyword_matches = sum(1 for kw in keywords if kw in searchable_text)
        score += keyword_matches * 0.5
        
        # Tag matches (important!)
        tags_str = str(insight.get('tags', '')).lower()
        tag_matches = sum(1 for kw in keywords if kw in tags_str)
        score += tag_matches * 2.0
        
        # Bonus for articles with full content
        if insight.get('extracted_text') and len(insight['extracted_text']) > 500:
            score += 1.0
        
        # Bonus for high quality
        if insight.get('quality_score'):
            score += insight['quality_score'] / 10.0
        
        # Bonus for user's own notes (often more valuable)
        if insight.get('content_category') == 'my_note':
            score += 1.5
        
        return score
    
    def _ensure_variety(self, insights: List[Dict], limit: int) -> List[Dict]:
        """Ensure variety in selected insights"""
        if len(insights) <= limit:
            return insights
        
        selected = []
        used_categories = set()
        used_domains = set()
        
        # First pass: select diverse items
        for insight in insights:
            if len(selected) >= limit:
                break
            
            category = insight.get('content_category', '')
            domain = self._extract_domain(insight.get('source_url', ''))
            
            # Prefer items with different categories and domains
            if category not in used_categories or domain not in used_domains:
                selected.append(insight)
                used_categories.add(category)
                if domain:
                    used_domains.add(domain)
        
        # Fill remaining slots with highest scored items
        while len(selected) < limit and len(selected) < len(insights):
            for insight in insights:
                if insight not in selected:
                    selected.append(insight)
                    if len(selected) >= limit:
                        break
        
        return selected[:limit]
    
    def _extract_domain(self, url: str) -> Optional[str]:
        """Extract domain from URL"""
        if not url:
            return None
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            return domain if domain else None
        except:
            return None
    
    def suggest_topics(self, limit: int = 5) -> List[Dict]:
        """
        Analyze library and suggest content ideas
        
        Returns topic suggestions based on clusters of related content
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get all useful insights with tags
        cursor.execute("""
            SELECT id, content, tags, quality_score, content_category
            FROM insights
            WHERE useful_for_daily = 1
            AND tags IS NOT NULL AND tags != ''
            AND content_category NOT IN ('junk', 'personal')
        """)
        
        insights = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        # Analyze tag clusters
        tag_groups = {}
        for insight in insights:
            tags = insight['tags'].split(',') if insight['tags'] else []
            for tag in tags:
                tag = tag.strip().lower()
                if tag:
                    if tag not in tag_groups:
                        tag_groups[tag] = []
                    tag_groups[tag].append(insight)
        
        # Find interesting combinations
        suggestions = []
        
        # Top tags with enough content
        for tag, group in sorted(tag_groups.items(), key=lambda x: len(x[1]), reverse=True):
            if len(group) >= 3 and len(suggestions) < limit:
                avg_quality = sum(i.get('quality_score', 5) for i in group) / len(group)
                
                # Generate topic suggestion
                topic_templates = [
                    f"What I've learned about {tag}",
                    f"Why {tag} matters more than you think",
                    f"The {tag} mistakes I see everywhere",
                    f"{tag.title()}: What nobody tells you",
                    f"My contrarian take on {tag}"
                ]
                
                suggestions.append({
                    'topic': topic_templates[len(suggestions) % len(topic_templates)],
                    'angle': f'Based on your saved insights about {tag}',
                    'count': len(group),
                    'quality': round(avg_quality, 1),
                    'supporting_insights': [i['id'] for i in group[:5]],
                    'preview': [i['content'][:100] + '...' for i in group[:3]]
                })
        
        # Find interesting tag combinations
        if len(suggestions) < limit:
            tag_pairs = self._find_tag_combinations(insights, tag_groups)
            for pair, group in tag_pairs[:limit - len(suggestions)]:
                tag1, tag2 = pair
                suggestions.append({
                    'topic': f"The intersection of {tag1} and {tag2}",
                    'angle': f'Unique insights connecting these topics',
                    'count': len(group),
                    'quality': sum(i.get('quality_score', 5) for i in group) / len(group),
                    'supporting_insights': [i['id'] for i in group[:5]],
                    'preview': [i['content'][:100] + '...' for i in group[:2]]
                })
        
        return suggestions[:limit]
    
    def _find_tag_combinations(self, insights: List[Dict], tag_groups: Dict) -> List:
        """Find interesting combinations of tags"""
        combinations = {}
        
        for insight in insights:
            tags = [t.strip().lower() for t in insight['tags'].split(',') if t.strip()]
            if len(tags) >= 2:
                # Look at pairs of tags
                for i, tag1 in enumerate(tags):
                    for tag2 in tags[i+1:]:
                        pair = tuple(sorted([tag1, tag2]))
                        if pair not in combinations:
                            combinations[pair] = []
                        combinations[pair].append(insight)
        
        # Return combinations with at least 3 insights
        valid_combinations = [
            (pair, group) for pair, group in combinations.items() 
            if len(group) >= 3
        ]
        
        # Sort by number of insights
        valid_combinations.sort(key=lambda x: len(x[1]), reverse=True)
        
        return valid_combinations
    
    def find_connections(self, insights: List[Dict]) -> Dict:
        """Find interesting connections between insights"""
        connections = {
            'common_themes': [],
            'unique_angles': [],
            'examples': []
        }
        
        # Extract common themes
        all_tags = []
        for insight in insights:
            if insight.get('tags'):
                tags = [t.strip() for t in insight['tags'] if t.strip()]
                all_tags.extend(tags)
        
        tag_counts = Counter(all_tags)
        connections['common_themes'] = [
            tag for tag, count in tag_counts.most_common(5)
        ]
        
        # Find unique angles (less common tags that appear)
        unique_tags = [tag for tag, count in tag_counts.items() if count == 1]
        connections['unique_angles'] = unique_tags[:3]
        
        # Extract examples from content
        for insight in insights[:3]:
            content = insight.get('extracted_text') or insight.get('content', '')
            if content:
                # Get first substantial paragraph
                paragraphs = content.split('\n')
                for p in paragraphs:
                    if len(p) > 100:
                        connections['examples'].append(p[:200] + '...')
                        break
        
        return connections
