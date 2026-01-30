"""
Brain Gym - Daily Practice Web App
Flask application for Phase 2 - Enhanced with extracted content
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from datetime import datetime
from utils import BrainGymUtils
from classifier import InsightClassifier
import os

app = Flask(__name__)
app.secret_key = 'braingym-secret-key-change-in-production'

# Initialize utilities
utils = BrainGymUtils('braingym.db')
classifier = InsightClassifier()


@app.route('/')
def home():
    """Home page - shows today's 3 insights"""
    insights = utils.get_daily_three()
    
    # Add prompts and format content for each insight
    for insight in insights:
        insight['prompt'] = get_prompt_for_insight(insight)
        insight['display_content'] = format_insight_content(insight)
    
    # Get quick stats for header
    stats = utils.get_stats()
    
    return render_template('home.html', 
                         insights=insights,
                         stats=stats,
                         today=datetime.now().strftime('%B %d, %Y'))


@app.route('/respond', methods=['POST'])
def respond():
    """Capture response for an insight"""
    insight_id = request.form.get('insight_id', type=int)
    response_text = request.form.get('response_text', '').strip()
    
    if not insight_id or not response_text:
        flash('Please provide a response', 'error')
        return redirect(url_for('home'))
    
    if len(response_text) < 20:
        flash('Please write at least 20 characters (2-3 sentences)', 'error')
        return redirect(url_for('home'))
    
    try:
        utils.save_response(insight_id, response_text)
        flash('Response saved! 🎉 Keep building your original thinking.', 'success')
    except Exception as e:
        flash(f'Error saving response: {str(e)}', 'error')
    
    return redirect(url_for('home'))


@app.route('/skip/<int:insight_id>', methods=['POST'])
def skip(insight_id):
    """Skip an insight for now"""
    try:
        utils.skip_insight(insight_id)
        flash('Skipped for now - will show again later', 'info')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('home'))


@app.route('/archive/<int:insight_id>', methods=['POST'])
def archive(insight_id):
    """Archive an insight (not interested)"""
    try:
        utils.archive_insight(insight_id)
        flash('Archived - won\'t show this again', 'info')
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
    
    return redirect(url_for('home'))


@app.route('/search')
def search():
    """Search responses"""
    keyword = request.args.get('q', '').strip()
    tag = request.args.get('tag', '').strip()
    
    results = []
    if keyword or tag:
        results = utils.search_responses(query=keyword if keyword else None,
                                        tag=tag if tag else None,
                                        limit=50)
    
    return render_template('search.html',
                         results=results,
                         keyword=keyword,
                         tag=tag)


@app.route('/stats')
def stats():
    """Statistics dashboard"""
    stats_data = utils.get_stats()
    return render_template('stats.html', stats=stats_data)


@app.route('/add', methods=['GET', 'POST'])
def add():
    """Manually add a new insight"""
    if request.method == 'POST':
        content = request.form.get('content', '').strip()
        source_url = request.form.get('source_url', '').strip()
        
        if not content:
            flash('Please provide content', 'error')
            return redirect(url_for('add'))
        
        # Insert directly into database
        conn = utils.get_connection()
        cursor = conn.cursor()
        
        try:
            # Determine content category
            if source_url:
                if 'twitter.com' in source_url or 'x.com' in source_url:
                    category = 'social_reference'
                elif 'linkedin.com' in source_url:
                    category = 'social_reference'
                elif 'youtube.com' in source_url:
                    category = 'video'
                elif 'github.com' in source_url:
                    category = 'code'
                else:
                    category = 'article'
            else:
                category = 'my_note'
            
            # Auto-classify tags
            tags = classifier.classify(content, '')
            tags_str = ','.join(list(set(tags))) if tags else ''
            
            cursor.execute("""
                INSERT INTO insights 
                (content, source_url, content_category, tags, status, 
                 quality_score, useful_for_daily, shared_date)
                VALUES (?, ?, ?, ?, 'pending', 7, 1, ?)
            """, (content, source_url, category, tags_str, datetime.now().isoformat()))
            
            insight_id = cursor.lastrowid
            conn.commit()
            flash(f'Insight added! (ID: {insight_id})', 'success')
            return redirect(url_for('home'))
        except Exception as e:
            flash(f'Error adding insight: {str(e)}', 'error')
        finally:
            conn.close()
    
    return render_template('add.html')


@app.route('/library')
def library():
    """View all responses (content library)"""
    responses = utils.search_responses(limit=100)
    
    # Add formatted content for each response
    for response in responses:
        response['display_content'] = format_insight_content(response)
    
    return render_template('library.html', responses=responses)


@app.route('/api/stats')
def api_stats():
    """API endpoint for stats (for future use)"""
    return jsonify(utils.get_stats())


def get_prompt_for_insight(insight: dict) -> str:
    """Generate contextual prompt based on insight type"""
    content_category = insight.get('content_category', '')
    source_type = insight.get('source_type', 'quote')
    tags = insight.get('tags', '') or ''
    tags_list = [t.strip().lower() for t in tags.split(',') if t.strip()]
    
    # Prompts based on content category (Phase 1.5 enhanced categories)
    prompts = {
        'article': "What's the key takeaway for you?",
        'social_reference': "What would you add to this perspective?",
        'video': "What's the main insight you'd take away?",
        'code': "Would you use this? How would you adapt it?",
        'discussion': "What's your take on this discussion?",
        'my_note': "How has your thinking on this evolved?",
    }
    
    # Check for special tags first
    if 'cautionary' in tags_list:
        return "What's the lesson here?"
    elif 'tactical' in tags_list:
        return "Would you use this? How?"
    elif 'philosophical' in tags_list:
        return "What does this mean to you?"
    elif 'startups' in tags_list or 'business' in tags_list:
        return "How would you apply this to your work?"
    
    # Use category-based prompt
    if content_category in prompts:
        return prompts[content_category]
    
    # Fall back to source type
    if source_type == 'article':
        return "What's the key takeaway for you?"
    elif source_type in ['tweet', 'linkedin']:
        return "Agree or disagree? Why?"
    
    # Default
    return "What's your take on this?"


def format_insight_content(insight: dict) -> dict:
    """Format insight content for display"""
    content_category = insight.get('content_category', '')
    extracted_text = insight.get('extracted_text', '')
    content = insight.get('content', '')
    source_url = insight.get('source_url', '')
    extraction_status = insight.get('extraction_status', '')
    
    result = {
        'type': content_category,
        'has_full_content': False,
        'preview': '',
        'full_text': '',
        'show_url': True,
        'badge': ''
    }
    
    # Article with extracted content
    if extraction_status == 'success' and extracted_text:
        result['has_full_content'] = True
        result['full_text'] = extracted_text[:2000] + ('...' if len(extracted_text) > 2000 else '')
        result['preview'] = extracted_text[:300] + '...'
        result['badge'] = '📄 Full Article'
    
    # Social reference
    elif extraction_status == 'social_reference':
        result['preview'] = extracted_text or content or 'Social media post you saved'
        result['badge'] = '📱 Social Reference'
        result['show_url'] = True
    
    # Your note
    elif content_category == 'my_note':
        result['preview'] = content
        result['full_text'] = content
        result['has_full_content'] = True
        result['badge'] = '✍️ Your Note'
        result['show_url'] = False
    
    # Fallback
    else:
        result['preview'] = content or 'Content preview not available'
        result['badge'] = '🔗 Link'
    
    return result


if __name__ == '__main__':
    print("🧠 Brain Gym - Daily Practice")
    print("=" * 50)
    print("Starting web app on http://localhost:5001")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5001)
