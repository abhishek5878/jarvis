"""
Content Generator using Claude API
Generates LinkedIn posts, Twitter threads, and blog outlines
"""
import anthropic
import os
import re
from typing import List, Dict, Optional
import json
import time
from anthropic import APIError, APIConnectionError, APITimeoutError


class ContentGenerator:
    """Generate content using Claude API and user's saved insights"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        
        self.client = anthropic.Anthropic(api_key=self.api_key)
    
    def generate(self, topic: str, insights: List[Dict], user_voice: Optional[Dict] = None) -> Dict:
        """
        Generate 3 content formats from insights
        
        Returns:
            {
                'linkedin': {...},
                'twitter': {...},
                'blog': {...}
            }
        """
        context = self._build_context(insights)
        voice_instructions = self._get_voice_instructions(user_voice)
        
        prompt = f"""You are helping a content creator write about "{topic}".

They have saved these materials in their personal library:

{context}

Generate 3 pieces of content:

1. LINKEDIN POST (300-400 words):
   - Start with a hook (compelling first line that stops the scroll)
   - Tell a story or share a specific insight
   - Include practical takeaway or framework
   - Conversational, authentic tone (like talking to a friend)
   - Use short paragraphs (1-2 sentences each)
   - End with a question or call-to-action
   {voice_instructions}

2. TWITTER THREAD (5-7 tweets):
   - Tweet 1: Hook that makes people want to read more (contrarian, surprising, or intriguing)
   - Each tweet: Standalone value, builds on previous
   - Use numbers, frameworks, specific examples
   - Last tweet: Summary + engagement ask ("What do you think?" or similar)
   - Each tweet MUST be under 280 characters
   - Natural, conversational flow

3. BLOG POST OUTLINE:
   - Compelling, specific title (not generic)
   - Introduction (2-3 paragraphs that set up the problem/opportunity)
   - 3-4 main sections with:
     * Clear section title
     * Key points to cover
     * Specific examples or stories to include
     * Actionable takeaways
   - Conclusion with practical next steps
   
CRITICAL QUALITY RULES:
- NO generic advice ("Here are 5 tips..." "In today's world...")
- NO obvious statements that add no value
- Start with something surprising, contrarian, or specific
- Use concrete examples, not abstract concepts
- Write like you're texting a smart friend, not writing a press release
- Cut ruthlessly - every sentence must earn its place
- End with something memorable, not a generic summary

EXAMPLES OF BAD VS GOOD:

BAD: "Communication is important in startups."
GOOD: "I've watched 3 startups die because the CEO assumed everyone knew the plan. They didn't."

BAD: "Here are 5 tips for better pricing..."
GOOD: "When we 10x'd our price, conversion rate went up 40%. Here's what we learned..."

BAD: "In conclusion, focus on your customers."
GOOD: "The best product feedback I ever got was from a customer who threatened to cancel."

IMPORTANT GUIDELINES:
- Synthesize ideas from MULTIPLE sources (don't just summarize one)
- Find unique angles by connecting different insights
- Use specific examples and data from the materials
- Write in an authentic, human voice (not corporate or AI-sounding)
- Make it personal and opinionated where appropriate
- Focus on insight and original thinking, not just information
- Be concrete and specific (avoid generic advice)

Your content should be:
- Specific, not generic
- Surprising, not obvious
- Personal, not corporate
- Valuable, not filler

For each piece, indicate which source materials you used by their number.

Format your response EXACTLY like this:

### LINKEDIN POST
[Write the full post here]

Sources used: 1, 3, 5

### TWITTER THREAD
1/ [First tweet - the hook]

2/ [Second tweet]

3/ [Third tweet]

4/ [Fourth tweet]

5/ [Fifth tweet]

6/ [Sixth tweet if needed]

7/ [Final tweet with engagement ask]

Sources used: 1, 2, 4

### BLOG POST
Title: [Compelling, specific title]

Introduction:
[2-3 introduction paragraphs]

I. [Section 1 Title]
- Key point 1
- Key point 2
- Example: [specific example]

II. [Section 2 Title]
- Key point 1
- Key point 2
- Example: [specific example]

III. [Section 3 Title]
- Key point 1
- Key point 2
- Example: [specific example]

Conclusion:
[Conclusion paragraph with actionable takeaways]

Sources used: 1, 2, 3, 4, 5"""

        # Retry logic with exponential backoff
        max_retries = 3
        retry_delay = 2  # Start with 2 seconds
        
        for attempt in range(max_retries):
            try:
                print(f"🤖 Calling Claude API (attempt {attempt + 1}/{max_retries})...")
                
                # Check prompt size (Anthropic has limits)
                prompt_size = len(prompt)
                if prompt_size > 200000:  # ~200k chars is safe limit
                    print(f"⚠️  Prompt is large ({prompt_size:,} chars), truncating context...")
                    context = self._build_context(insights[:5])  # Use fewer insights
                    prompt = f"""You are helping a content creator write about "{topic}".

They have saved these materials in their personal library:

{context}

Generate 3 pieces of content:

1. LINKEDIN POST (300-400 words):
   - Start with a hook (compelling first line that stops the scroll)
   - Tell a story or share a specific insight
   - Include practical takeaway or framework
   - Conversational, authentic tone (like talking to a friend)
   - Use short paragraphs (1-2 sentences each)
   - End with a question or call-to-action
   {voice_instructions}

2. TWITTER THREAD (5-7 tweets):
   - Tweet 1: Hook that makes people want to read more (contrarian, surprising, or intriguing)
   - Each tweet: Standalone value, builds on previous
   - Use numbers, frameworks, specific examples
   - Last tweet: Summary + engagement ask ("What do you think?" or similar)
   - Each tweet MUST be under 280 characters
   - Natural, conversational flow

3. BLOG POST OUTLINE:
   - Compelling, specific title (not generic)
   - Introduction (2-3 paragraphs that set up the problem/opportunity)
   - 3-4 main sections with:
     * Clear section title
     * Key points to cover
     * Specific examples or stories to include
     * Actionable takeaways
   - Conclusion with practical next steps
   
CRITICAL QUALITY RULES:
- NO generic advice ("Here are 5 tips..." "In today's world...")
- NO obvious statements that add no value
- Start with something surprising, contrarian, or specific
- Use concrete examples, not abstract concepts
- Write like you're texting a smart friend, not writing a press release
- Cut ruthlessly - every sentence must earn its place
- End with something memorable, not a generic summary

EXAMPLES OF BAD VS GOOD:

BAD: "Communication is important in startups."
GOOD: "I've watched 3 startups die because the CEO assumed everyone knew the plan. They didn't."

BAD: "Here are 5 tips for better pricing..."
GOOD: "When we 10x'd our price, conversion rate went up 40%. Here's what we learned..."

BAD: "In conclusion, focus on your customers."
GOOD: "The best product feedback I ever got was from a customer who threatened to cancel."

IMPORTANT GUIDELINES:
- Synthesize ideas from MULTIPLE sources (don't just summarize one)
- Find unique angles by connecting different insights
- Use specific examples and data from the materials
- Write in an authentic, human voice (not corporate or AI-sounding)
- Make it personal and opinionated where appropriate
- Focus on insight and original thinking, not just information
- Be concrete and specific (avoid generic advice)

Your content should be:
- Specific, not generic
- Surprising, not obvious
- Personal, not corporate
- Valuable, not filler

For each piece, indicate which source materials you used by their number.

Format your response EXACTLY like this:

### LINKEDIN POST
[Write the full post here]

Sources used: 1, 3, 5

### TWITTER THREAD
1/ [First tweet - the hook]

2/ [Second tweet]

3/ [Third tweet]

4/ [Fourth tweet]

5/ [Fifth tweet]

6/ [Sixth tweet if needed]

7/ [Final tweet with engagement ask]

Sources used: 1, 2, 4

### BLOG POST
Title: [Compelling, specific title]

Introduction:
[2-3 introduction paragraphs]

I. [Section 1 Title]
- Key point 1
- Key point 2
- Example: [specific example]

II. [Section 2 Title]
- Key point 1
- Key point 2
- Example: [specific example]

III. [Section 3 Title]
- Key point 1
- Key point 2
- Example: [specific example]

Conclusion:
[Conclusion paragraph with actionable takeaways]

Sources used: 1, 2, 3, 4, 5"""
                
                response = self.client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4000,
                    messages=[{"role": "user", "content": prompt}],
                    timeout=120.0  # 2 minute timeout
                )
                
                response_text = response.content[0].text
                print(f"✅ Claude API response received ({len(response_text):,} chars)")
                return self._parse_response(response_text, insights)
            
            except (APIConnectionError, BrokenPipeError, ConnectionError, OSError) as e:
                # Network/connection errors - retry with backoff
                error_msg = str(e)
                if "Broken pipe" in error_msg or "Connection" in error_msg:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        print(f"⚠️  Connection error (attempt {attempt + 1}/{max_retries}): {error_msg}")
                        print(f"   Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(
                            f"Connection error after {max_retries} attempts. "
                            f"This usually means:\n"
                            f"1. Network connectivity issue - check your internet\n"
                            f"2. Anthropic API is temporarily unavailable\n"
                            f"3. Request timeout - try with fewer insights\n\n"
                            f"Original error: {error_msg}"
                        )
                else:
                    raise
            
            except APITimeoutError as e:
                # Timeout errors - retry
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"⚠️  Request timeout (attempt {attempt + 1}/{max_retries})")
                    print(f"   Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(
                        f"Request timed out after {max_retries} attempts. "
                        f"The prompt might be too large or the API is slow. "
                        f"Try with a simpler topic or fewer insights."
                    )
            
            except APIError as e:
                # API errors (rate limits, invalid key, etc.) - don't retry
                error_msg = str(e)
                if "rate_limit" in error_msg.lower() or "429" in error_msg:
                    raise Exception(
                        "Rate limit exceeded. Please wait a few minutes and try again. "
                        "Anthropic API has usage limits."
                    )
                elif "authentication" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
                    raise Exception(
                        "API authentication failed. Please check your ANTHROPIC_API_KEY. "
                        "Make sure it's valid and has sufficient credits."
                    )
                else:
                    raise Exception(
                        f"API error: {error_msg}\n\n"
                        f"If this persists, check:\n"
                        f"1. Your API key is valid\n"
                        f"2. You have API credits\n"
                        f"3. Anthropic service status"
                    )
            
            except Exception as e:
                # Other errors - log and raise
                error_type = type(e).__name__
                error_msg = str(e)
                print(f"❌ Unexpected error ({error_type}): {error_msg}")
                
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)
                    print(f"   Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise Exception(
                        f"Content generation failed after {max_retries} attempts.\n\n"
                        f"Error: {error_type}: {error_msg}\n\n"
                        f"Please try:\n"
                        f"1. Check your internet connection\n"
                        f"2. Verify ANTHROPIC_API_KEY is set correctly\n"
                        f"3. Try a simpler topic\n"
                        f"4. Check Anthropic API status"
                    )
        
        # Should never reach here, but just in case
        raise Exception("Content generation failed after all retry attempts.")
    
    def _build_context(self, insights: List[Dict]) -> str:
        """Build context string from insights"""
        context_parts = []
        
        for i, insight in enumerate(insights, 1):
            part = f"\n--- Source {i} ---\n"
            part += f"Type: {insight.get('content_category', 'unknown')}\n"
            
            if insight.get('source_url'):
                part += f"URL: {insight['source_url']}\n"
            
            tags = insight.get('tags', [])
            if tags:
                if isinstance(tags, str):
                    part += f"Tags: {tags}\n"
                else:
                    part += f"Tags: {', '.join(tags)}\n"
            
            part += "\n"
            
            # Use extracted text if available, otherwise content
            text = insight.get('extracted_text') or insight.get('content', '')
            
            # Truncate if too long (keep first 1500 chars for better context)
            if len(text) > 1500:
                text = text[:1500] + "..."
            
            part += text
            
            # Add user's context if available
            if insight.get('context_message'):
                part += f"\n\nUser's note when saving: {insight['context_message']}"
            
            context_parts.append(part)
        
        return "\n\n".join(context_parts)
    
    def _get_voice_instructions(self, user_voice: Optional[Dict]) -> str:
        """Generate voice instructions if user_voice provided"""
        if not user_voice:
            return ""
        
        analysis = user_voice.get('analysis', {})
        if isinstance(analysis, str):
            try:
                analysis = json.loads(analysis)
            except:
                analysis = {}
        
        instructions = f"""
MATCH THIS WRITING STYLE (CRITICAL):

Voice Profile:
- Tone: {analysis.get('tone', 'conversational')} - {analysis.get('tone_description', '')}
- Sentence style: {analysis.get('sentence_style', 'varied')} (avg {analysis.get('sentence_length_avg', '15')} words)
- Perspective: {analysis.get('perspective', 'first-person')}
- Structure: {analysis.get('structure_preference', 'mixed')}
- Emoji usage: {analysis.get('emoji_usage', 'occasional')}

Common phrases the user uses:
{chr(10).join('- "' + p + '"' for p in analysis.get('common_phrases', [])[:5])}

Opening style: {analysis.get('opening_style', 'varied')}
Examples:
{chr(10).join('- ' + ex for ex in analysis.get('opening_examples', [])[:2])}

Closing style: {analysis.get('closing_style', 'question')}
Examples:
{chr(10).join('- ' + ex for ex in analysis.get('closing_examples', [])[:2])}

Distinctive elements:
{chr(10).join('- ' + el for el in analysis.get('distinctive_elements', []))}

Voice summary: {analysis.get('voice_summary', '')}

IMPORTANT: Match this style exactly. Use similar:
- Sentence structures
- Phrase patterns  
- Opening/closing techniques
- Tone and personality
- Level of formality

The content should sound like it was written by the same person who wrote the sample posts.
"""
        
        return instructions
    
    def _parse_response(self, response_text: str, insights: List[Dict]) -> Dict:
        """Parse Claude's response into structured format"""
        result = {
            'linkedin': {'content': '', 'word_count': 0, 'sources': []},
            'twitter': {'thread': [], 'sources': []},
            'blog': {'title': '', 'outline': '', 'intro': '', 'sources': []}
        }
        
        try:
            # Split by main sections
            sections = response_text.split('###')
            
            for section in sections:
                section = section.strip()
                
                if section.startswith('LINKEDIN POST'):
                    linkedin_content = self._extract_linkedin(section)
                    result['linkedin'] = linkedin_content
                
                elif section.startswith('TWITTER THREAD'):
                    twitter_content = self._extract_twitter(section)
                    result['twitter'] = twitter_content
                
                elif section.startswith('BLOG POST'):
                    blog_content = self._extract_blog(section)
                    result['blog'] = blog_content
            
            # Map source numbers to insight IDs
            result['linkedin']['sources'] = self._map_sources(
                result['linkedin']['sources'], insights
            )
            result['twitter']['sources'] = self._map_sources(
                result['twitter']['sources'], insights
            )
            result['blog']['sources'] = self._map_sources(
                result['blog']['sources'], insights
            )
        
        except Exception as e:
            print(f"Error parsing response: {e}")
            # Return raw content as fallback
            result['linkedin']['content'] = response_text
        
        return result
    
    def regenerate(self, original_content: str, feedback: str, insights: List[Dict], 
                   voice_profile: Optional[Dict] = None, format_type: str = 'linkedin') -> str:
        """
        Regenerate content with specific feedback
        
        Args:
            original_content: The content to improve
            feedback: User's improvement request (e.g., "make it shorter", "more casual")
            insights: Original source insights
            voice_profile: Voice profile
            format_type: 'linkedin', 'twitter', or 'blog'
        """
        context = self._build_context(insights)
        voice_instructions = self._build_voice_instructions(voice_profile)
        
        format_instructions = {
            'linkedin': "LinkedIn post (300-400 words)",
            'twitter': "Twitter thread (5-7 tweets, under 280 chars each)",
            'blog': "Blog post outline with title and sections"
        }
        
        prompt = f"""Here is content that was generated:

{original_content}

The user wants you to regenerate it with this feedback:
"{feedback}"

Source materials:
{context}

{voice_instructions}

Regenerate the {format_instructions[format_type]} incorporating the feedback.
Keep what works, improve based on the specific feedback.

IMPORTANT:
- Address the specific feedback directly
- Maintain the user's voice and style
- Keep using the source materials
- Make substantial improvements, not minor tweaks

Return only the regenerated content, no explanation."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=3000,
                messages=[{"role": "user", "content": prompt}],
                timeout=120.0
            )
            
            return response.content[0].text.strip()
        
        except Exception as e:
            print(f"Error regenerating content: {e}")
            raise
    
    def _build_voice_instructions(self, voice_profile: Optional[Dict]) -> str:
        """Build voice instructions from profile (alias for _get_voice_instructions)"""
        return self._get_voice_instructions(voice_profile)
    
    def _extract_linkedin(self, section: str) -> Dict:
        """Extract LinkedIn post content"""
        lines = section.split('\n')
        content_lines = []
        sources = []
        
        in_content = False
        for line in lines:
            if 'LINKEDIN POST' in line:
                in_content = True
                continue
            
            if line.startswith('Sources used:'):
                sources = self._parse_sources(line)
                break
            
            if in_content and line.strip():
                content_lines.append(line.strip())
        
        content = '\n\n'.join(content_lines)
        
        return {
            'content': content,
            'word_count': len(content.split()),
            'sources': sources
        }
    
    def _extract_twitter(self, section: str) -> Dict:
        """Extract Twitter thread"""
        lines = section.split('\n')
        tweets = []
        sources = []
        
        for line in lines:
            line = line.strip()
            
            if line.startswith('Sources used:'):
                sources = self._parse_sources(line)
                break
            
            # Match tweet format: "1/ content" or "1. content"
            match = re.match(r'^(\d+)[/.]\s*(.+)$', line)
            if match:
                tweet_content = match.group(2).strip()
                tweets.append(tweet_content)
        
        return {
            'thread': tweets,
            'sources': sources
        }
    
    def _extract_blog(self, section: str) -> Dict:
        """Extract blog post outline"""
        lines = section.split('\n')
        title = ''
        intro = ''
        outline_lines = []
        sources = []
        
        in_intro = False
        in_outline = False
        
        for line in lines:
            line_stripped = line.strip()
            
            if line_stripped.startswith('Title:'):
                title = line_stripped.replace('Title:', '').strip()
                continue
            
            if line_stripped.startswith('Introduction:'):
                in_intro = True
                in_outline = False
                continue
            
            if line_stripped.startswith('Sources used:'):
                sources = self._parse_sources(line_stripped)
                break
            
            # Detect outline start
            if re.match(r'^(I\.|1\.|\d+\.)', line_stripped):
                in_intro = False
                in_outline = True
            
            if in_intro and line_stripped:
                intro += line_stripped + '\n\n'
            
            if in_outline and line_stripped:
                outline_lines.append(line_stripped)
        
        return {
            'title': title,
            'intro': intro.strip(),
            'outline': '\n'.join(outline_lines),
            'sources': sources
        }
    
    def _parse_sources(self, line: str) -> List[int]:
        """Parse source numbers from 'Sources used: 1, 2, 3' format"""
        try:
            numbers_part = line.split(':', 1)[1]
            numbers = re.findall(r'\d+', numbers_part)
            return [int(n) for n in numbers]
        except:
            return []
    
    def _map_sources(self, source_numbers: List[int], insights: List[Dict]) -> List[int]:
        """Map source numbers (1-indexed) to insight IDs"""
        mapped = []
        for num in source_numbers:
            if 1 <= num <= len(insights):
                mapped.append(insights[num - 1]['id'])
        return mapped
