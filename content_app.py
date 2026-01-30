"""
Content Generator Flask Application
AI-powered content generator from personal knowledge library
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from content_generator import ContentGenerator
from search_engine import ContentSearchEngine
import sqlite3
import json
from datetime import datetime
import os
import anthropic
import re

app = Flask(__name__, template_folder='templates_content')
app.secret_key = 'content-generator-secret-key-change-in-production'

# Initialize
generator = None  # Will initialize when API key is available
search_engine = ContentSearchEngine('braingym.db')


def init_generator():
    """Initialize content generator with API key"""
    global generator
    if not generator:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            generator = ContentGenerator(api_key)
        else:
            print("⚠️  ANTHROPIC_API_KEY not set. Content generation will not work.")
    return generator


def init_generations_table():
    """Create generations table if it doesn't exist"""
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS generations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            linkedin_content TEXT,
            twitter_content TEXT,
            blog_content TEXT,
            insights_used TEXT
        )
    ''')
    
    conn.commit()
    conn.close()


@app.route('/')
def home():
    """Homepage with search box and library stats"""
    # Get library stats
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT COUNT(*) FROM insights WHERE useful_for_daily = 1
    """)
    total_insights = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM insights 
        WHERE useful_for_daily = 1 
        AND extraction_status = 'success'
    """)
    articles_with_content = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM insights 
        WHERE useful_for_daily = 1 
        AND content_category = 'my_note'
    """)
    your_notes = cursor.fetchone()[0]
    
    # Get recent generations
    cursor.execute("""
        SELECT id, topic, created_at
        FROM generations
        ORDER BY created_at DESC
        LIMIT 5
    """)
    recent_generations = cursor.fetchall()
    
    # Get recent manual saves
    cursor.execute('''
        SELECT content, source_url, shared_date, content_category
        FROM insights 
        WHERE shared_by = "manual_save"
        ORDER BY shared_date DESC
        LIMIT 5
    ''')
    recent_saves = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    stats = {
        'total_insights': total_insights,
        'articles_with_content': articles_with_content,
        'your_notes': your_notes
    }
    
    return render_template('content_home.html', 
                          stats=stats,
                          recent_generations=recent_generations,
                          recent_saves=recent_saves)


@app.route('/generate', methods=['POST'])
def generate():
    """Generate content for a topic"""
    gen = init_generator()
    if not gen:
        flash('⚠️  API key not configured. Set ANTHROPIC_API_KEY environment variable.', 'error')
        return redirect(url_for('home'))
    
    topic = request.form.get('topic', '').strip()
    
    if not topic:
        flash('Please enter a topic', 'error')
        return redirect(url_for('home'))
    
    try:
        # 1. Search for relevant insights
        print(f"🔍 Searching for insights about: {topic}")
        insights = search_engine.search(topic, limit=10)
        
        if not insights:
            flash(f'No relevant insights found for "{topic}". Try a different topic or add more content to your library.', 'info')
            return redirect(url_for('home'))
        
        print(f"✅ Found {len(insights)} relevant insights")
        
        # 2. Get voice profile
        voice_profile = get_active_voice_profile()
        
        # 3. Generate content
        print(f"🤖 Generating content with Claude...")
        result = gen.generate(topic, insights, voice_profile)
        
        print(f"✅ Content generated successfully")
        
        # 4. Save generation to database
        generation_id = save_generation(topic, result, insights)
        
        flash(f'✨ Generated content for "{topic}"!', 'success')
        
        # 5. Show results
        return render_template('content_results.html',
                             topic=topic,
                             generation_id=generation_id,
                             linkedin=result['linkedin'],
                             twitter=result['twitter'],
                             blog=result['blog'],
                             insights=insights)
    
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error generating content: {error_msg}")
        import traceback
        traceback.print_exc()
        
        # Show user-friendly error message
        if "Connection error" in error_msg or "Broken pipe" in error_msg:
            flash(
                '⚠️ Connection error while generating. This usually means:\n'
                '• Network issue - check your internet\n'
                '• API temporarily unavailable - try again in a minute\n'
                '• Request too large - try a simpler topic',
                'error'
            )
        elif "timeout" in error_msg.lower():
            flash(
                '⏱️ Request timed out. The prompt might be too large.\n'
                'Try with a simpler topic or wait and try again.',
                'error'
            )
        elif "Rate limit" in error_msg or "rate_limit" in error_msg:
            flash(
                '🚦 Rate limit exceeded. Please wait a few minutes before trying again.',
                'error'
            )
        elif "authentication" in error_msg.lower() or "API key" in error_msg:
            flash(
                '🔑 API authentication failed. Please check your ANTHROPIC_API_KEY.',
                'error'
            )
        else:
            # Generic error - show first line
            error_first_line = error_msg.split('\n')[0]
            flash(f'❌ Error: {error_first_line}', 'error')
        
        return redirect(url_for('home'))


@app.route('/suggest-topics')
def suggest_topics():
    """Suggest content topics from user's library"""
    try:
        suggestions = search_engine.suggest_topics(limit=5)
        return jsonify({'topics': suggestions})
    except Exception as e:
        print(f"Error suggesting topics: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/save', methods=['GET', 'POST'])
def save_content():
    """
    Save new content to library
    
    GET: Show save form
    POST: Process and save content
    """
    if request.method == 'GET':
        return render_template('content_save.html')
    
    # POST - save content
    content_type = request.form.get('type')  # 'url' or 'text'
    content = request.form.get('content', '').strip()
    note = request.form.get('note', '').strip()
    
    if not content:
        return jsonify({
            'success': False,
            'message': 'Content is required'
        })
    
    if content_type == 'url':
        # Extract content from URL using Firecrawl
        result = save_url(content, note)
    else:
        # Save as personal note
        result = save_note(content, note)
    
    return jsonify(result)


def save_url(url, context_note=''):
    """Extract and save content from URL"""
    api_key = os.environ.get('FIRECRAWL_API_KEY')
    if not api_key:
        return {
            'success': False,
            'message': 'Firecrawl API key not set. Set FIRECRAWL_API_KEY environment variable to extract URLs.'
        }
    
    try:
        from firecrawl import FirecrawlApp
        
        firecrawl = FirecrawlApp(api_key=api_key)
        
        # Extract content
        print(f"🔍 Extracting content from: {url}")
        result = firecrawl.scrape(
            url=url,
            formats=['markdown']
        )
        
        if not result or not hasattr(result, 'markdown'):
            return {
                'success': False,
                'message': 'Could not extract content from URL'
            }
        
        markdown = result.markdown or ''
        metadata_obj = getattr(result, 'metadata', None)
        
        # Get metadata
        title = ''
        if metadata_obj and hasattr(metadata_obj, 'title'):
            title = metadata_obj.title or ''
        
        if not title:
            title = url
        
        # Determine content category
        if 'linkedin.com' in url:
            category = 'social_reference'
        elif 'twitter.com' in url or 'x.com' in url:
            category = 'social_reference'
        elif 'youtube.com' in url:
            category = 'video'
        elif 'github.com' in url:
            category = 'code'
        else:
            category = 'article'
        
        # Simple tagging from URL
        tags = []
        if 'startup' in url.lower():
            tags.append('startups')
        if 'business' in url.lower():
            tags.append('business')
        
        # Save to database
        conn = sqlite3.connect('braingym.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO insights (
                content, source_url, source_type, content_category,
                shared_by, shared_date, context_message,
                extracted_text, extraction_status,
                quality_score, useful_for_daily, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            title,
            url,
            category,
            category,
            'manual_save',
            datetime.now().isoformat(),
            context_note,
            markdown,
            'success',
            8,  # Good quality for manually saved
            1,
            ','.join(tags) if tags else None
        ))
        
        insight_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ Saved! ID: {insight_id}, Extracted {len(markdown)} chars")
        
        return {
            'success': True,
            'message': f'Saved! Extracted {len(markdown):,} characters. Ready to use in generation.',
            'insight_id': insight_id
        }
        
    except Exception as e:
        print(f"❌ Error saving URL: {e}")
        import traceback
        traceback.print_exc()
        return {
            'success': False,
            'message': f'Error extracting content: {str(e)}'
        }


def save_note(text, context=''):
    """Save text as personal note"""
    if len(text.strip()) < 50:
        return {
            'success': False,
            'message': 'Note too short (minimum 50 characters)'
        }
    
    # Simple auto-tagging based on keywords
    tags = []
    text_lower = text.lower()
    
    keyword_map = {
        'startup': 'startups',
        'business': 'business',
        'product': 'product',
        'marketing': 'marketing',
        'sales': 'sales',
        'growth': 'growth',
        'team': 'teams',
        'hiring': 'hiring',
        'fund': 'fundraising',
        'investor': 'fundraising',
        'pricing': 'pricing',
        'customer': 'customers',
        'user': 'users',
        'design': 'design',
        'code': 'coding',
        'engineer': 'engineering',
        'product': 'product',
        'ai': 'ai',
        'data': 'data'
    }
    
    for keyword, tag in keyword_map.items():
        if keyword in text_lower and tag not in tags:
            tags.append(tag)
    
    # Calculate quality based on length
    quality = 7
    if len(text) > 500:
        quality = 8
    if len(text) > 1000:
        quality = 9
    
    try:
        conn = sqlite3.connect('braingym.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO insights (
                content, source_type, content_category,
                shared_by, shared_date, context_message,
                quality_score, useful_for_daily, tags
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            text,
            'my_note',
            'my_note',
            'manual_save',
            datetime.now().isoformat(),
            context,
            quality,
            1,
            ','.join(tags) if tags else None
        ))
        
        insight_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        print(f"✅ Note saved! ID: {insight_id}, Tags: {tags}")
        
        tag_msg = f' Auto-tagged: {", ".join(tags[:3])}' if tags else ''
        
        return {
            'success': True,
            'message': f'Note saved!{tag_msg} Ready to use in generation.',
            'insight_id': insight_id
        }
        
    except Exception as e:
        print(f"❌ Error saving note: {e}")
        return {
            'success': False,
            'message': f'Error saving note: {str(e)}'
        }


@app.route('/history')
def history():
    """Show past generations"""
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, topic, created_at, 
               linkedin_content, twitter_content, blog_content
        FROM generations
        ORDER BY created_at DESC
        LIMIT 50
    """)
    
    generations = []
    for row in cursor.fetchall():
        generations.append({
            'id': row[0],
            'topic': row[1],
            'created_at': row[2],
            'linkedin_preview': row[3][:200] + '...' if row[3] else '',
            'twitter_count': len(json.loads(row[4])) if row[4] else 0,
            'has_blog': bool(row[5])
        })
    
    conn.close()
    
    return render_template('content_history.html', generations=generations)


@app.route('/regenerate/<int:generation_id>', methods=['POST'])
def regenerate(generation_id):
    """Regenerate one format with feedback"""
    format_type = request.form.get('format')  # linkedin/twitter/blog
    feedback = request.form.get('feedback', '').strip()
    
    if not feedback or len(feedback) < 5:
        return jsonify({'success': False, 'message': 'Please provide specific feedback (minimum 5 characters)'})
    
    # Get original generation
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM generations WHERE id = ?', (generation_id,))
    gen_row = cursor.fetchone()
    
    if not gen_row:
        conn.close()
        return jsonify({'success': False, 'message': 'Generation not found'})
    
    generation = dict(gen_row)
    
    # Get insights used
    insights_ids = json.loads(generation['insights_used'])
    if insights_ids:
        placeholders = ','.join('?' * len(insights_ids))
        cursor.execute(f'SELECT * FROM insights WHERE id IN ({placeholders})', insights_ids)
        insights = [dict(row) for row in cursor.fetchall()]
    else:
        insights = []
    
    conn.close()
    
    # Get original content
    if format_type == 'linkedin':
        original_content = generation['linkedin_content'] or ''
    elif format_type == 'twitter':
        twitter_data = json.loads(generation['twitter_content']) if generation['twitter_content'] else []
        original_content = '\n'.join(f"{i+1}/ {t}" for i, t in enumerate(twitter_data))
    else:  # blog
        blog_data = json.loads(generation['blog_content']) if generation['blog_content'] else {}
        original_content = f"{blog_data.get('title', '')}\n\n{blog_data.get('intro', '')}\n\n{blog_data.get('outline', '')}"
    
    # Get voice profile
    voice_profile = get_active_voice_profile()
    
    # Regenerate
    try:
        generator = init_generator()
        if not generator:
            return jsonify({'success': False, 'message': 'API key not configured'})
        
        new_content = generator.regenerate(
            original_content=original_content,
            feedback=feedback,
            insights=insights,
            voice_profile=voice_profile,
            format_type=format_type
        )
        
        # Update database
        conn = sqlite3.connect('braingym.db')
        cursor = conn.cursor()
        
        if format_type == 'linkedin':
            cursor.execute('UPDATE generations SET linkedin_content = ? WHERE id = ?',
                         (new_content, generation_id))
        elif format_type == 'twitter':
            # Parse back into thread
            tweets = []
            for line in new_content.split('\n'):
                line = line.strip()
                if line:
                    # Handle "1/ tweet" or "1. tweet" format
                    match = re.match(r'^\d+[/.]\s*(.+)$', line)
                    if match:
                        tweets.append(match.group(1))
                    else:
                        tweets.append(line)
            cursor.execute('UPDATE generations SET twitter_content = ? WHERE id = ?',
                         (json.dumps(tweets), generation_id))
        else:  # blog
            # Simple parsing - could be improved
            parts = new_content.split('\n\n', 2)
            blog_data = {
                'title': parts[0].replace('Title:', '').strip() if len(parts) > 0 else '',
                'intro': parts[1].replace('Introduction:', '').strip() if len(parts) > 1 else '',
                'outline': parts[2] if len(parts) > 2 else ''
            }
            cursor.execute('UPDATE generations SET blog_content = ? WHERE id = ?',
                         (json.dumps(blog_data), generation_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'content': new_content,
            'message': 'Regenerated successfully!'
        })
        
    except Exception as e:
        print(f"❌ Error regenerating: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        })


@app.route('/save-draft', methods=['POST'])
def save_draft():
    """Save generated content as editable draft"""
    title = request.form.get('title', '').strip()
    format_type = request.form.get('format')
    content = request.form.get('content', '')
    topic = request.form.get('topic', '')
    generation_id = request.form.get('generation_id')
    
    if not title or not format_type or not content:
        return jsonify({'success': False, 'message': 'Title, format, and content are required'})
    
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            format TEXT NOT NULL,
            content TEXT NOT NULL,
            topic TEXT,
            generation_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'draft',
            scheduled_for TIMESTAMP,
            published_at TIMESTAMP,
            notes TEXT
        )
    ''')
    
    cursor.execute('''
        INSERT INTO drafts (title, format, content, topic, generation_id)
        VALUES (?, ?, ?, ?, ?)
    ''', (title, format_type, content, topic, generation_id if generation_id else None))
    
    draft_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'draft_id': draft_id,
        'message': 'Saved as draft!'
    })


@app.route('/drafts')
def drafts():
    """View all drafts"""
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            format TEXT NOT NULL,
            content TEXT NOT NULL,
            topic TEXT,
            generation_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'draft',
            scheduled_for TIMESTAMP,
            published_at TIMESTAMP,
            notes TEXT
        )
    ''')
    
    cursor.execute('''
        SELECT * FROM drafts 
        WHERE status = 'draft'
        ORDER BY updated_at DESC
    ''')
    
    drafts_list = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return render_template('content_drafts.html', drafts=drafts_list)


@app.route('/draft/<int:draft_id>', methods=['GET', 'POST'])
def edit_draft(draft_id):
    """View/edit a specific draft"""
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if request.method == 'POST':
        # Update draft
        content = request.form.get('content', '')
        notes = request.form.get('notes', '')
        
        cursor.execute('''
            UPDATE drafts 
            SET content = ?, notes = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (content, notes, draft_id))
        
        conn.commit()
        conn.close()
        
        flash('Draft updated!', 'success')
        return redirect(f'/draft/{draft_id}')
    
    # GET
    cursor.execute('SELECT * FROM drafts WHERE id = ?', (draft_id,))
    draft_row = cursor.fetchone()
    
    if not draft_row:
        flash('Draft not found', 'error')
        return redirect('/drafts')
    
    draft = dict(draft_row)
    conn.close()
    
    return render_template('content_draft_edit.html', draft=draft)


@app.route('/draft/<int:draft_id>/publish', methods=['POST'])
def publish_draft(draft_id):
    """Mark draft as published"""
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE drafts 
        SET status = 'published', published_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (draft_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Marked as published!'})


@app.route('/generation/<int:generation_id>')
def view_generation(generation_id):
    """View a specific generation"""
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT topic, created_at, linkedin_content, twitter_content, 
               blog_content, insights_used
        FROM generations
        WHERE id = ?
    """, (generation_id,))
    
    row = cursor.fetchone()
    
    if not row:
        flash('Generation not found', 'error')
        return redirect(url_for('history'))
    
    # Parse content
    linkedin = {
        'content': row[2],
        'word_count': len(row[2].split()) if row[2] else 0
    }
    
    twitter = {
        'thread': json.loads(row[3]) if row[3] else []
    }
    
    blog = json.loads(row[4]) if row[4] else {}
    
    # Get insights used
    insight_ids = json.loads(row[5]) if row[5] else []
    
    if insight_ids:
        placeholders = ','.join('?' * len(insight_ids))
        cursor.execute(f"""
            SELECT id, content, source_url, content_category
            FROM insights
            WHERE id IN ({placeholders})
        """, insight_ids)
        
        insights = [dict(zip(['id', 'content', 'source_url', 'content_category'], row))
                   for row in cursor.fetchall()]
    else:
        insights = []
    
    conn.close()
    
    return render_template('content_results.html',
                         topic=row[0],
                         generation_id=generation_id,
                         created_at=row[1],
                         linkedin=linkedin,
                         twitter=twitter,
                         blog=blog,
                         insights=insights)


def get_active_voice_profile():
    """Get current active voice profile"""
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Create table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voice_profile (
            id INTEGER PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sample_posts TEXT,
            analysis TEXT,
            tone TEXT,
            sentence_style TEXT,
            perspective TEXT,
            common_phrases TEXT,
            opening_style TEXT,
            closing_style TEXT,
            structure_preference TEXT,
            emoji_usage TEXT,
            active BOOLEAN DEFAULT 1
        )
    ''')
    
    cursor.execute('''
        SELECT * FROM voice_profile 
        WHERE active = 1 
        ORDER BY created_at DESC 
        LIMIT 1
    ''')
    
    profile = cursor.fetchone()
    conn.close()
    
    if profile:
        profile_dict = dict(profile)
        if profile_dict.get('analysis'):
            profile_dict['analysis'] = json.loads(profile_dict['analysis'])
        if profile_dict.get('common_phrases'):
            profile_dict['common_phrases'] = json.loads(profile_dict['common_phrases'])
        return profile_dict
    
    return None


def analyze_voice(sample_posts):
    """Use Claude to analyze writing style"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")
    
    client = anthropic.Anthropic(api_key=api_key)
    
    prompt = f"""Analyze the writing style of these sample posts:

{sample_posts}

Provide a detailed analysis in the following JSON format:

{{
    "tone": "conversational|professional|casual|provocative",
    "tone_description": "Brief description of tone",
    "sentence_style": "short|varied|long",
    "sentence_length_avg": "number of words",
    "perspective": "first-person|third-person",
    "common_phrases": ["phrase 1", "phrase 2", "phrase 3"],
    "opening_style": "question|statement|story|data",
    "opening_examples": ["example 1", "example 2"],
    "closing_style": "call-to-action|question|insight|summary",
    "closing_examples": ["example 1", "example 2"],
    "structure_preference": "story-driven|data-driven|framework|mixed",
    "emoji_usage": "frequent|occasional|rare|none",
    "distinctive_elements": ["element 1", "element 2"],
    "voice_summary": "2-3 sentence summary of their unique voice"
}}

Focus on what makes this voice distinctive and authentic. Be specific."""

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Parse JSON response
    analysis_text = response.content[0].text
    
    # Extract JSON (handle markdown fences)
    json_match = re.search(r'```json\s*(.*?)\s*```', analysis_text, re.DOTALL)
    if json_match:
        analysis_text = json_match.group(1)
    else:
        # Try to find JSON object directly
        json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
        if json_match:
            analysis_text = json_match.group(0)
    
    analysis = json.loads(analysis_text)
    return analysis


def save_voice_profile(sample_posts, analysis):
    """Save voice profile to database"""
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    
    # Create table if not exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS voice_profile (
            id INTEGER PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            sample_posts TEXT,
            analysis TEXT,
            tone TEXT,
            sentence_style TEXT,
            perspective TEXT,
            common_phrases TEXT,
            opening_style TEXT,
            closing_style TEXT,
            structure_preference TEXT,
            emoji_usage TEXT,
            active BOOLEAN DEFAULT 1
        )
    ''')
    
    # Deactivate old profiles
    cursor.execute('UPDATE voice_profile SET active = 0')
    
    # Insert new profile
    cursor.execute('''
        INSERT INTO voice_profile (
            sample_posts, analysis, tone, sentence_style, perspective,
            common_phrases, opening_style, closing_style, 
            structure_preference, emoji_usage
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        sample_posts,
        json.dumps(analysis),
        analysis.get('tone'),
        analysis.get('sentence_style'),
        analysis.get('perspective'),
        json.dumps(analysis.get('common_phrases', [])),
        analysis.get('opening_style'),
        analysis.get('closing_style'),
        analysis.get('structure_preference'),
        analysis.get('emoji_usage')
    ))
    
    conn.commit()
    conn.close()


@app.route('/train-voice', methods=['GET', 'POST'])
def train_voice():
    """Learn user's writing style from sample posts"""
    if request.method == 'GET':
        # Check if voice profile exists
        current_profile = get_active_voice_profile()
        
        return render_template('content_voice.html', 
                             current_profile=current_profile)
    
    # POST - analyze and save
    sample_posts = request.form.get('sample_posts', '').strip()
    
    if not sample_posts or len(sample_posts) < 200:
        flash('Please provide at least 5-10 sample posts (minimum 200 characters total)', 'error')
        return redirect('/train-voice')
    
    try:
        # Analyze voice using Claude
        print("🎯 Analyzing voice profile...")
        voice_profile = analyze_voice(sample_posts)
        
        # Save to database
        save_voice_profile(sample_posts, voice_profile)
        
        flash('✓ Voice profile learned! Your future content will match your writing style.', 'success')
        return redirect('/')
        
    except Exception as e:
        print(f"❌ Error analyzing voice: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error analyzing voice: {str(e)}', 'error')
        return redirect('/train-voice')


def save_generation(topic: str, result: dict, insights: list) -> int:
    """Save generation to database"""
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    
    insight_ids = [i['id'] for i in insights]
    
    cursor.execute('''
        INSERT INTO generations 
        (topic, linkedin_content, twitter_content, blog_content, insights_used)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        topic,
        result['linkedin']['content'],
        json.dumps(result['twitter']['thread']),
        json.dumps(result['blog']),
        json.dumps(insight_ids)
    ))
    
    generation_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return generation_id


if __name__ == '__main__':
    print("🧠 Content Generator - Turn your saved insights into published content")
    print("=" * 70)
    
    # Check for API key
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("✅ ANTHROPIC_API_KEY found")
    else:
        print("⚠️  ANTHROPIC_API_KEY not set!")
        print("   Set it with: export ANTHROPIC_API_KEY='your-key-here'")
    
    # Initialize database
    init_generations_table()
    print("✅ Database initialized")
    
    print()
    print("🚀 Starting server on http://localhost:5001")
    print("   Press Ctrl+C to stop")
    print("=" * 70)
    
    app.run(debug=True, host='0.0.0.0', port=5001)
