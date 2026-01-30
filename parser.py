"""
WhatsApp message parser for Brain Gym
Extracts links, context, and insights from WhatsApp chat exports
"""
import re
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class WhatsAppMessage:
    """Represents a parsed WhatsApp message"""
    date: str
    time: str
    sender: str
    content: str
    urls: List[str]
    
    @property
    def datetime_str(self) -> str:
        """Combined date and time string"""
        return f"{self.date} {self.time}"
    
    @property
    def full_content(self) -> str:
        """Full message content without URLs"""
        content = self.content
        for url in self.urls:
            content = content.replace(url, "").strip()
        return content


class WhatsAppParser:
    """Parser for WhatsApp chat export files"""
    
    # Common WhatsApp export patterns
    # Format: [DD/MM/YYYY, HH:MM:SS] Sender: Message
    # or: DD/MM/YYYY, HH:MM - Sender: Message
    MESSAGE_PATTERNS = [
        r'\[(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\]\s*([^:]+):\s*(.*)',
        r'(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AP]M)?)\s*-\s*([^:]+):\s*(.*)',
    ]
    
    # URL pattern
    URL_PATTERN = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    
    def __init__(self):
        self.messages: List[WhatsAppMessage] = []
    
    def parse_file(self, file_path: str) -> List[WhatsAppMessage]:
        """Parse a WhatsApp export file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return self.parse_content(content)
    
    def parse_content(self, content: str) -> List[WhatsAppMessage]:
        """Parse WhatsApp chat content"""
        messages = []
        current_message = None
        
        lines = content.split('\n')
        
        for line in lines:
            # Try to match message start pattern
            parsed = self._parse_message_line(line)
            
            if parsed:
                # Save previous message if exists
                if current_message:
                    messages.append(current_message)
                
                # Start new message
                date, time, sender, message_content = parsed
                urls = self._extract_urls(message_content)
                current_message = WhatsAppMessage(
                    date=date,
                    time=time,
                    sender=sender.strip(),
                    content=message_content,
                    urls=urls
                )
            elif current_message:
                # Continuation of previous message (multi-line)
                current_message.content += "\n" + line
                urls = self._extract_urls(line)
                current_message.urls.extend(urls)
        
        # Don't forget the last message
        if current_message:
            messages.append(current_message)
        
        self.messages = messages
        return messages
    
    def _parse_message_line(self, line: str) -> Optional[Tuple[str, str, str, str]]:
        """Try to parse a message line with different patterns"""
        for pattern in self.MESSAGE_PATTERNS:
            match = re.match(pattern, line)
            if match:
                return match.groups()
        return None
    
    def _extract_urls(self, text: str) -> List[str]:
        """Extract all URLs from text"""
        return re.findall(self.URL_PATTERN, text)
    
    def get_url_type(self, url: str) -> str:
        """Determine the type of URL"""
        url_lower = url.lower()
        
        if 'twitter.com' in url_lower or 'x.com' in url_lower:
            return 'tweet'
        elif 'linkedin.com' in url_lower:
            return 'linkedin'
        elif 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'video'
        elif any(domain in url_lower for domain in ['medium.com', 'substack.com', 'blog']):
            return 'article'
        else:
            return 'link'
    
    def extract_insights(self) -> List[Dict]:
        """Extract structured insights from parsed messages"""
        insights = []
        
        for msg in self.messages:
            # Skip system messages
            if self._is_system_message(msg):
                continue
            
            # Extract URL-based insights
            for url in msg.urls:
                insight = {
                    'content': msg.full_content or url,
                    'source_url': url,
                    'source_type': self.get_url_type(url),
                    'shared_by': msg.sender,
                    'shared_date': msg.datetime_str,
                    'context_message': msg.content
                }
                insights.append(insight)
            
            # Extract standalone insights (meaningful messages without URLs)
            if not msg.urls and self._is_meaningful_content(msg.content):
                insight = {
                    'content': msg.content,
                    'source_url': None,
                    'source_type': 'quote',
                    'shared_by': msg.sender,
                    'shared_date': msg.datetime_str,
                    'context_message': msg.content
                }
                insights.append(insight)
        
        return insights
    
    def _is_system_message(self, msg: WhatsAppMessage) -> bool:
        """Check if message is a system message"""
        system_keywords = [
            'Messages and calls are end-to-end encrypted',
            'created group',
            'changed the subject',
            'left',
            'added',
            'removed',
            'changed this group',
            'You deleted this message',
            'This message was deleted'
        ]
        return any(keyword in msg.content for keyword in system_keywords)
    
    def _is_meaningful_content(self, content: str) -> bool:
        """Check if content is meaningful enough to be an insight"""
        # Filter out very short messages, emojis only, etc.
        if len(content.strip()) < 30:
            return False
        
        # Filter out messages that are just reactions or short responses
        short_responses = ['ok', 'yes', 'no', 'thanks', 'lol', 'haha', '😂', '👍', 'nice', 'cool']
        if content.strip().lower() in short_responses:
            return False
        
        return True
    
    def get_statistics(self) -> Dict:
        """Get parsing statistics"""
        total_messages = len(self.messages)
        messages_with_urls = sum(1 for msg in self.messages if msg.urls)
        total_urls = sum(len(msg.urls) for msg in self.messages)
        
        # Count by sender
        senders = {}
        for msg in self.messages:
            senders[msg.sender] = senders.get(msg.sender, 0) + 1
        
        return {
            'total_messages': total_messages,
            'messages_with_urls': messages_with_urls,
            'total_urls': total_urls,
            'unique_senders': len(senders),
            'top_senders': dict(sorted(senders.items(), key=lambda x: x[1], reverse=True)[:10])
        }
