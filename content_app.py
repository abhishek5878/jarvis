"""
Content Generator Flask Application
AI-powered content generator from personal knowledge library
PLG Phase 1: Auth, freemium, watermark, public voice, share, referral
"""
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from content_generator import ContentGenerator
from search_engine import ContentSearchEngine
import sqlite3

try:
    from query_engine import QueryEngine
    query_engine = QueryEngine()
except Exception as e:
    query_engine = None
    print(f"Query engine not available: {e}")
import json
from datetime import datetime
import os
import anthropic
import re
import secrets
import hashlib
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='templates_content')
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

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


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def optional_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = None
        if 'user_id' in session:
            user = get_user(session['user_id'])
        return f(user=user, *args, **kwargs)
    return decorated_function


def get_user(user_id):
    """Get user by ID"""
    if user_id is None:
        return None
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None


@app.context_processor
def inject_current_user():
    """Make current_user available in all templates for nav."""
    user = None
    if 'user_id' in session:
        user = get_user(session['user_id'])
    return dict(current_user=user)


def track_usage(user_id, action, metadata=None):
    """Track user action"""
    if user_id is None:
        return
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO usage_log (user_id, action, metadata)
        VALUES (?, ?, ?)
    ''', (user_id, action, json.dumps(metadata) if metadata else None))
    conn.commit()
    conn.close()


def check_generation_limit(user):
    """Check if user can generate. Returns (can_generate: bool, reason: str or None)."""
    if user is None:
        return True, None  # Trial user
    if user.get('tier') not in ('free', None):
        return True, None  # Paid users unlimited
    used = user.get('generations_this_month') or 0
    limit = user.get('generations_limit') or 10
    if used >= limit:
        return False, f"You've used all {limit} free generations this month. Upgrade for unlimited."
    return True, None


def increment_generation_count(user_id):
    """Increment user's generation count"""
    if user_id is None:
        return
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET generations_this_month = generations_this_month + 1
        WHERE id = ?
    ''', (user_id,))
    conn.commit()
    conn.close()


# ---------- Trial mode (try before signup) ----------
def is_trial_user():
    """True if user is not logged in (trial mode)."""
    return 'user_id' not in session


def get_trial_key():
    """Session key for trial (by IP)."""
    return f"trial_{request.remote_addr}"


def get_trial_limits():
    """Trial usage limits for current session."""
    key = get_trial_key()
    return {
        'queries_used': session.get(f'{key}_queries', 0),
        'queries_limit': 3,
        'items_saved': session.get(f'{key}_items', 0),
        'items_limit': 10,
    }


def increment_trial_usage(action='query'):
    """Increment trial usage counter."""
    key = get_trial_key()
    if action == 'query':
        session[f'{key}_queries'] = session.get(f'{key}_queries', 0) + 1
    elif action == 'save':
        session[f'{key}_items'] = session.get(f'{key}_items', 0) + 1


def check_trial_limit(action='query'):
    """Return (can_proceed, error_message)."""
    limits = get_trial_limits()
    if action == 'query':
        if limits['queries_used'] >= limits['queries_limit']:
            return False, f"You've used all {limits['queries_limit']} free queries. Sign up for 20 more free per month!"
    elif action == 'save':
        if limits['items_saved'] >= limits['items_limit']:
            return False, f"You've saved {limits['items_limit']} items. Sign up to save unlimited!"
    return True, None


def migrate_trial_to_user(user_id):
    """Move trial insights (trial_key) into the new user account."""
    key = get_trial_key()
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(insights)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'trial_key' in cols and 'user_id' in cols:
        cursor.execute(
            'UPDATE insights SET user_id = ?, trial_key = NULL WHERE trial_key = ?',
            (user_id, key)
        )
        conn.commit()
    conn.close()


def generate_share_hash(generation_id):
    """Create unique hash for sharing"""
    secret = os.environ.get('SHARE_SECRET', 'content-forge-share-secret')
    return hashlib.sha256(f"{generation_id}{secret}".encode()).hexdigest()[:16]


def check_and_award_referral_bonus(referee_id):
    """Award referrer bonus when referee completes onboarding"""
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT referrer_id, converted, reward_granted FROM referrals WHERE referee_id = ?
    ''', (referee_id,))
    row = cursor.fetchone()
    if not row or row[1] or row[2]:
        conn.close()
        return
    referrer_id = row[0]
    cursor.execute('''
        UPDATE referrals SET converted = 1, reward_granted = 1 WHERE referee_id = ?
    ''', (referee_id,))
    cursor.execute('UPDATE users SET generations_limit = generations_limit + 5 WHERE id = ?', (referrer_id,))
    conn.commit()
    conn.close()
    track_usage(referrer_id, 'referral_bonus', {'referee_id': referee_id, 'bonus': 5})


def init_generations_table():
    """Create generations table if it doesn't exist; run PLG migration"""
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
    
    # PLG: add user_id and share_hash if missing
    try:
        from plg_migrate import run_migration
        run_migration()
    except Exception as e:
        print(f"PLG migration note: {e}")


@app.route('/')
@optional_login
def home(user):
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
    
    topic_prefill = request.args.get('topic', '')
    return render_template('content_home.html',
                          stats=stats,
                          recent_generations=recent_generations,
                          recent_saves=recent_saves,
                          user=user,
                          topic_prefill=topic_prefill)


# ---------- PLG: Auth ----------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """User registration"""
    if request.method == 'GET':
        referral_code = request.args.get('ref', '')
        next_url = request.args.get('next', '/')
        return render_template('signup.html', referral_code=referral_code, next_url=next_url)
    
    email = request.form.get('email', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    referral_code = request.form.get('referral_code', '').strip()
    next_url = request.form.get('next', '/')
    
    if not email or not username or not password:
        flash('All fields required', 'error')
        return redirect(url_for('signup'))
    
    if len(password) < 8:
        flash('Password must be at least 8 characters', 'error')
        return redirect(url_for('signup'))
    
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    
    cursor.execute('SELECT id FROM users WHERE email = ? OR username = ?', (email, username))
    if cursor.fetchone():
        flash('Email or username already exists', 'error')
        conn.close()
        return redirect(url_for('signup'))
    
    referred_by = None
    bonus_generations = 0
    if referral_code:
        cursor.execute('SELECT id FROM users WHERE referral_code = ?', (referral_code,))
        ref_row = cursor.fetchone()
        if ref_row:
            referred_by = ref_row[0]
            bonus_generations = 5
    
    password_hash = generate_password_hash(password)
    user_referral_code = secrets.token_urlsafe(8)
    
    cursor.execute('''
        INSERT INTO users (email, username, password_hash, referral_code, referred_by, generations_limit)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (email, username, password_hash, user_referral_code, referred_by, 10 + bonus_generations))
    
    user_id = cursor.lastrowid
    
    if referred_by:
        cursor.execute('INSERT INTO referrals (referrer_id, referee_id) VALUES (?, ?)', (referred_by, user_id))
    
    conn.commit()
    conn.close()
    
    session['user_id'] = user_id
    migrate_trial_to_user(user_id)
    track_usage(user_id, 'signup', {'referred_by': referred_by})
    flash(f'Welcome! You have {10 + bonus_generations} free generations this month.', 'success')
    return redirect(next_url or url_for('home'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'GET':
        return render_template('login.html', next_url=request.args.get('next', '/'))
    
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    next_url = request.form.get('next', '/')
    
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    user = cursor.fetchone()
    conn.close()
    
    if not user or not check_password_hash(user['password_hash'], password):
        flash('Invalid email or password', 'error')
        return redirect(url_for('login'))
    
    session['user_id'] = user['id']
    return redirect(next_url or url_for('home'))


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully', 'success')
    return redirect(url_for('home'))


@app.route('/upgrade')
@login_required
def upgrade_page():
    """Upgrade / pricing page"""
    user = get_user(session['user_id'])
    return render_template('upgrade.html',
        current_tier=user.get('tier', 'free'),
        generations_used=user.get('generations_this_month') or 0,
        generations_limit=user.get('generations_limit') or 10,
        user=user)


@app.route('/generate', methods=['POST'])
def generate():
    """Generate content for a topic (trial for anonymous, limits for free tier)"""
    gen = init_generator()
    if not gen:
        flash('⚠️  API key not configured. Set ANTHROPIC_API_KEY environment variable.', 'error')
        return redirect(url_for('home'))
    
    topic = request.form.get('topic', '').strip()
    if not topic:
        flash('Please enter a topic', 'error')
        return redirect(url_for('home'))
    
    # Resolve user (optional login)
    user = None
    if 'user_id' in session:
        user = get_user(session['user_id'])
    
    # Anonymous trial: allow 1 free generation per session
    if user is None:
        trial_key = 'trial_generations'
        trial_count = session.get(trial_key, 0)
        if trial_count >= 1:
            flash('Sign up free to get 10 generations per month.', 'info')
            return redirect(url_for('signup', next=url_for('home')))
        session[trial_key] = trial_count + 1
        user_tier = 'free'  # watermark
    else:
        can_generate, reason = check_generation_limit(user)
        if not can_generate:
            flash(reason, 'error')
            return redirect(url_for('upgrade_page'))
        user_tier = user.get('tier') or 'free'
    
    try:
        # 1. Search for relevant insights
        print(f"🔍 Searching for insights about: {topic}")
        insights = search_engine.search(topic, limit=10)
        
        if not insights:
            flash(f'No relevant insights found for "{topic}". Try a different topic or add more content to your library.', 'info')
            return redirect(url_for('home'))
        
        print(f"✅ Found {len(insights)} relevant insights")
        
        # 2. Get voice profile (user's if logged in)
        voice_profile = get_active_voice_profile(user['id'] if user else None)
        
        # 3. Generate content (with watermark for free tier)
        print(f"🤖 Generating content with Claude...")
        result = gen.generate(topic, insights, voice_profile, user_tier=user_tier)
        
        print(f"✅ Content generated successfully")
        
        # 4. Save generation (user_id, share_hash)
        generation_id = save_generation(topic, result, insights, user_id=user['id'] if user else None)
        
        # 5. Increment count for logged-in free user
        if user:
            increment_generation_count(user['id'])
            track_usage(user['id'], 'generate', {'topic': topic})
        
        flash(f'✨ Generated content for "{topic}"!', 'success')
        
        # 6. Show results (share_hash stored in save_generation)
        conn = sqlite3.connect('braingym.db')
        cursor = conn.cursor()
        cursor.execute('SELECT share_hash FROM generations WHERE id = ?', (generation_id,))
        row = cursor.fetchone()
        share_hash = row[0] if row and row[0] else None
        conn.close()
        
        return render_template('content_results.html',
                             topic=topic,
                             generation_id=generation_id,
                             linkedin=result['linkedin'],
                             twitter=result['twitter'],
                             blog=result['blog'],
                             insights=insights,
                             user=user,
                             user_tier=user_tier,
                             share_hash=share_hash)
    
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


# ---------- Query interface (external context window) ----------
def save_query(query_text, result, user_id=None):
    """Save query to database for history."""
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            query_text TEXT NOT NULL,
            query_type TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            results_count INTEGER,
            useful BOOLEAN,
            response_text TEXT,
            insights_used TEXT
        )
    ''')
    insights = result.get('insights') or []
    insight_ids = [i['id'] for i in insights]
    cursor.execute('''
        INSERT INTO queries (user_id, query_text, query_type, results_count, response_text, insights_used)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        user_id,
        query_text,
        result.get('type', 'recall'),
        len(insight_ids),
        result.get('response', '')[:50000],
        json.dumps(insight_ids)
    ))
    conn.commit()
    conn.close()


def get_recent_queries(limit=5, user_id=None):
    """Get recent queries for display."""
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT query_text, query_type, timestamp
            FROM queries
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        return [dict(r) for r in rows]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


@app.route('/query', methods=['GET', 'POST'])
@optional_login
def query_interface(user):
    """Main query interface - works for trial users (3 free queries) or logged-in."""
    if request.method == 'GET':
        recent_queries = get_recent_queries(limit=5)
        if query_engine:
            stats = query_engine._get_library_stats()
        else:
            conn = sqlite3.connect('braingym.db')
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM insights WHERE useful_for_daily = 1')
            total = cursor.fetchone()[0]
            conn.close()
            stats = {'total': total, 'articles': 0, 'notes': 0, 'top_topics': []}
        trial_limits = get_trial_limits() if is_trial_user() else None
        return render_template('query_interface.html',
            recent_queries=recent_queries,
            stats=stats,
            user=user,
            trial_limits=trial_limits)
    query_text = (request.form.get('query') or '').strip()
    if len(query_text) < 3:
        flash('Please enter a question (at least 3 characters)', 'error')
        return redirect(url_for('query_interface'))
    if not query_engine:
        flash('Query engine not available. Set OPENAI_API_KEY and ANTHROPIC_API_KEY.', 'error')
        return redirect(url_for('query_interface'))
    if is_trial_user():
        can_query, limit_msg = check_trial_limit('query')
        if not can_query:
            flash(limit_msg, 'info')
            return redirect(url_for('signup', reason='trial_limit'))
        increment_trial_usage('query')
    try:
        user_id = session.get('user_id') if session else None
        if user:
            user_id = user.get('id')
        trial_key = get_trial_key() if is_trial_user() else None
        result = query_engine.route_query(query_text, user_id=user_id, trial_key=trial_key)
        save_query(query_text, result, user_id=user_id)
        if result.get('type') == 'generate':
            from urllib.parse import quote
            topic = result.get('topic') or query_text
            return redirect(url_for('home', topic=quote(str(topic)[:200])))
        if result.get('type') == 'explore' and not result.get('insights'):
            result['insights'] = result.get('sample') or []
        return render_template('query_result.html',
            query=query_text,
            result=result,
            user=user)
    except Exception as e:
        print(f"Query error: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error processing query: {str(e)}', 'error')
        return redirect(url_for('query_interface'))


@app.route('/synthesis/<int:synthesis_id>')
def view_synthesis(synthesis_id):
    """View saved synthesis."""
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM syntheses WHERE id = ?', (synthesis_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        flash('Synthesis not found', 'error')
        return redirect(url_for('query_interface'))
    synthesis = dict(row)
    insight_ids = []
    if synthesis.get('source_insights'):
        try:
            insight_ids = json.loads(synthesis['source_insights'])
        except Exception:
            pass
    insights = []
    if insight_ids:
        conn = sqlite3.connect('braingym.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(insight_ids))
        cursor.execute(f'SELECT * FROM insights WHERE id IN ({placeholders})', insight_ids)
        insights = [dict(r) for r in cursor.fetchall()]
        conn.close()
    return render_template('synthesis_view.html', synthesis=synthesis, insights=insights)


@app.route('/my-syntheses')
@optional_login
def my_syntheses(user):
    """List user's syntheses."""
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id, query, synthesis_text, created_at
            FROM syntheses
            ORDER BY created_at DESC
            LIMIT 50
        ''')
        syntheses = [dict(r) for r in cursor.fetchall()]
    except sqlite3.OperationalError:
        syntheses = []
    finally:
        conn.close()
    return render_template('syntheses_list.html', syntheses=syntheses, user=user)


# ---------- Conversion engine: waste, onboarding, impact, testimonial, library ----------
@app.route('/waste-analysis')
@optional_login
def waste_analysis(user):
    """Show bookmark waste analysis (trial: estimate; logged-in: actual)."""
    if is_trial_user():
        estimated_bookmarks = 500
        return render_template('waste_analysis.html',
            bookmarks_count=estimated_bookmarks,
            hours_wasted=(estimated_bookmarks * 5) / 60,
            money_wasted=int((estimated_bookmarks * 5) / 60 * 100),
            is_estimate=True,
            user=user)
    u = get_user(session['user_id'])
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(insights)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'user_id' in cols:
        cursor.execute('SELECT COUNT(*) FROM insights WHERE user_id = ? AND useful_for_daily = 1', (u['id'],))
    else:
        cursor.execute('SELECT COUNT(*) FROM insights WHERE useful_for_daily = 1')
    count = cursor.fetchone()[0]
    queries_made = 0
    try:
        cursor.execute('SELECT COUNT(*) FROM queries WHERE user_id = ?', (u['id'],))
        queries_made = cursor.fetchone()[0]
    except Exception:
        pass
    conn.close()
    usage_rate = (queries_made / count * 100) if count > 0 else 0
    return render_template('waste_analysis.html',
        bookmarks_count=count,
        queries_made=queries_made,
        usage_rate=usage_rate,
        hours_wasted=(count * 5) / 60,
        money_wasted=int((count * 5) / 60 * 100),
        hours_saved_potential=count * 5 / 60,
        hours_saved_actual=queries_made * 0.5,
        is_estimate=False,
        user=user)


@app.route('/onboarding')
@login_required
def onboarding():
    """Post-signup onboarding to drive aha moment."""
    user = get_user(session['user_id'])
    if user.get('onboarding_completed'):
        return redirect(url_for('home'))
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(insights)")
    cols = [row[1] for row in cursor.fetchall()]
    items_saved = 0
    if 'user_id' in cols:
        cursor.execute('SELECT COUNT(*) as c FROM insights WHERE user_id = ?', (user['id'],))
        items_saved = cursor.fetchone()['c']
    else:
        cursor.execute('SELECT COUNT(*) as c FROM insights WHERE useful_for_daily = 1')
        items_saved = cursor.fetchone()['c']
    try:
        cursor.execute('SELECT COUNT(*) as c FROM queries WHERE user_id = ?', (user['id'],))
        queries_made = cursor.fetchone()['c']
    except Exception:
        queries_made = 0
    conn.close()
    steps = [
        {'id': 1, 'title': 'Import your bookmarks', 'description': 'Connect Twitter or upload browser bookmarks', 'completed': items_saved >= 10, 'action_url': '/import/twitter', 'action_text': 'Import Now'},
        {'id': 2, 'title': 'Ask your first question', 'description': 'Query your knowledge library', 'completed': queries_made >= 1, 'action_url': '/query', 'action_text': 'Try Query'},
        {'id': 3, 'title': 'Get your aha moment', 'description': 'See synthesis across all your saved content', 'completed': queries_made >= 3, 'action_url': '/query', 'action_text': 'Ask Another'},
    ]
    return render_template('onboarding.html', steps=steps, items_saved=items_saved, queries_made=queries_made, user=user)


@app.route('/onboarding/complete', methods=['POST'])
@login_required
def complete_onboarding_post():
    """Mark onboarding complete."""
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'onboarding_completed' in cols:
        cursor.execute('UPDATE users SET onboarding_completed = 1 WHERE id = ?', (session['user_id'],))
    conn.commit()
    conn.close()
    check_and_award_referral_bonus(session['user_id'])
    flash("Welcome! You're all set.", 'success')
    return redirect(url_for('home'))


@app.route('/impact')
@login_required
def impact_dashboard():
    """Show value/ROI from Cortex."""
    user = get_user(session['user_id'])
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(*) as total_queries, COUNT(DISTINCT DATE(timestamp)) as active_days FROM queries WHERE user_id = ?', (user['id'],))
        query_stats = dict(cursor.fetchone())
    except Exception:
        query_stats = {'total_queries': 0, 'active_days': 0}
    cursor.execute("PRAGMA table_info(insights)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'user_id' in cols:
        cursor.execute('SELECT COUNT(*) as c FROM insights WHERE user_id = ? AND useful_for_daily = 1', (user['id'],))
    else:
        cursor.execute('SELECT COUNT(*) as c FROM insights WHERE useful_for_daily = 1')
    library_size = cursor.fetchone()[0]
    try:
        cursor.execute('SELECT COUNT(*) as c FROM syntheses WHERE user_id = ?', (user['id'],))
        syntheses_count = cursor.fetchone()[0]
    except Exception:
        syntheses_count = 0
    try:
        cursor.execute('SELECT COUNT(*) as c FROM generations WHERE user_id = ?', (user['id'],))
        generations_count = cursor.fetchone()[0]
    except Exception:
        generations_count = 0
    conn.close()
    time_saved_hours = query_stats.get('total_queries', 0) * 0.5 + generations_count * 2
    money_value = int(time_saved_hours * 100)
    cost_per_month = 49 if user.get('tier') == 'pro' else 0
    roi = int(money_value / 49) if cost_per_month else 0
    return render_template('impact_dashboard.html',
        queries=query_stats.get('total_queries', 0),
        active_days=query_stats.get('active_days', 0),
        library_size=library_size,
        syntheses=syntheses_count,
        generations=generations_count,
        time_saved_hours=int(time_saved_hours),
        money_value=money_value,
        cost_per_month=cost_per_month,
        roi=roi,
        user=user)


def get_user_stats(user_id):
    """Stats for testimonial context."""
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    try:
        cursor.execute('SELECT COUNT(*) as c FROM queries WHERE user_id = ?', (user_id,))
        queries = cursor.fetchone()[0]
    except Exception:
        queries = 0
    cursor.execute("PRAGMA table_info(insights)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'user_id' in cols:
        cursor.execute('SELECT COUNT(*) as c FROM insights WHERE user_id = ? AND useful_for_daily = 1', (user_id,))
    else:
        cursor.execute('SELECT COUNT(*) as c FROM insights WHERE useful_for_daily = 1')
    library_size = cursor.fetchone()[0]
    conn.close()
    return {'queries': queries, 'library_size': library_size, 'time_saved': int(queries * 0.5), 'active_days': min(queries, 30)}


@app.route('/testimonial', methods=['GET', 'POST'])
@login_required
def submit_testimonial():
    """Testimonial submission."""
    if request.method == 'GET':
        user = get_user(session['user_id'])
        stats = get_user_stats(user['id'])
        return render_template('testimonial.html', stats=stats, user=user)
    testimonial_text = request.form.get('testimonial', '').strip()
    rating = request.form.get('rating')
    allow_public = request.form.get('allow_public') == 'on'
    twitter_handle = request.form.get('twitter_handle', '').strip()
    if not testimonial_text:
        flash('Please enter your testimonial', 'error')
        return redirect(url_for('submit_testimonial'))
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS testimonials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            text TEXT NOT NULL,
            rating INTEGER,
            allow_public INTEGER DEFAULT 0,
            twitter_handle TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            featured INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('INSERT INTO testimonials (user_id, text, rating, allow_public, twitter_handle) VALUES (?, ?, ?, ?, ?)',
        (session['user_id'], testimonial_text, rating, 1 if allow_public else 0, twitter_handle))
    cursor.execute("PRAGMA table_info(users)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'generations_limit' in cols:
        cursor.execute('UPDATE users SET generations_limit = generations_limit + 10 WHERE id = ?', (session['user_id'],))
    conn.commit()
    conn.close()
    flash('Thank you! Added 10 bonus generations to your account.', 'success')
    return redirect(url_for('impact_dashboard'))


@app.route('/library')
@login_required
def library():
    """View user's library with stats."""
    user = get_user(session['user_id'])
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(insights)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'user_id' in cols:
        cursor.execute('''
            SELECT COUNT(*) as total,
                SUM(CASE WHEN content_category = "article" THEN 1 ELSE 0 END) as articles,
                SUM(CASE WHEN content_category = "my_note" THEN 1 ELSE 0 END) as notes,
                SUM(CASE WHEN content_category = "social_reference" THEN 1 ELSE 0 END) as social
            FROM insights WHERE user_id = ? AND useful_for_daily = 1
        ''', (user['id'],))
    else:
        cursor.execute('''
            SELECT COUNT(*) as total,
                SUM(CASE WHEN content_category = "article" THEN 1 ELSE 0 END) as articles,
                SUM(CASE WHEN content_category = "my_note" THEN 1 ELSE 0 END) as notes,
                SUM(CASE WHEN content_category = "social_reference" THEN 1 ELSE 0 END) as social
            FROM insights WHERE useful_for_daily = 1
        ''')
    row = cursor.fetchone()
    stats = dict(row) if row else {'total': 0, 'articles': 0, 'notes': 0, 'social': 0}
    if 'user_id' in cols:
        cursor.execute('SELECT * FROM insights WHERE user_id = ? AND useful_for_daily = 1 ORDER BY shared_date DESC LIMIT 50', (user['id'],))
    else:
        cursor.execute('SELECT * FROM insights WHERE useful_for_daily = 1 ORDER BY shared_date DESC LIMIT 50')
    recent_items = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return render_template('library.html', stats=stats, recent_items=recent_items, user=user)


@app.route('/import/twitter')
@login_required
def import_twitter():
    """Twitter import page (OAuth stub)."""
    return render_template('import_twitter.html', user=get_user(session['user_id']))


@app.route('/import/bookmarks', methods=['GET', 'POST'])
@login_required
def import_bookmarks():
    """Browser bookmarks import (file upload)."""
    if request.method == 'GET':
        return render_template('import_bookmarks.html', user=get_user(session['user_id']))
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('import_bookmarks'))
    file = request.files.get('file')
    if not file or not file.filename:
        flash('No file selected', 'error')
        return redirect(url_for('import_bookmarks'))
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name
    try:
        with open(tmp_path, 'r', encoding='utf-8', errors='ignore') as f:
            raw = f.read()
        bookmarks = []
        if raw.strip().startswith('{'):
            data = json.loads(raw)
            def extract(node):
                if node.get('type') == 'url':
                    bookmarks.append({'title': node.get('name'), 'url': node.get('url'), 'date_added': node.get('date_added')})
                for child in node.get('children', []):
                    extract(child)
            for root_name in ['bookmark_bar', 'other', 'synced']:
                if data.get('roots', {}).get(root_name):
                    extract(data['roots'][root_name])
        else:
            import re
            for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>', raw, re.I):
                url, title = m.group(1).strip(), (m.group(2) or '').strip()
                if url.startswith('http') and len(url) < 2048:
                    bookmarks.append({'title': title[:500] or url, 'url': url, 'date_added': None})
        imported = 0
        conn = sqlite3.connect('braingym.db')
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(insights)")
        cols = [row[1] for row in cursor.fetchall()]
        user_id = session['user_id']
        for b in bookmarks[:100]:
            url = b.get('url') or ''
            if not url or not url.startswith('http'):
                continue
            if 'user_id' in cols:
                cursor.execute('SELECT id FROM insights WHERE user_id = ? AND source_url = ?', (user_id, url))
            else:
                cursor.execute('SELECT id FROM insights WHERE source_url = ?', (url,))
            if cursor.fetchone():
                continue
            title = (b.get('title') or url)[:500]
            cursor.execute("PRAGMA table_info(insights)")
            c2 = [row[1] for row in cursor.fetchall()]
            if 'user_id' in c2 and 'trial_key' in c2:
                cursor.execute('''
                    INSERT INTO insights (content, source_url, source_type, content_category, shared_by, shared_date, quality_score, useful_for_daily, user_id, trial_key)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (title, url, 'article', 'article', 'bookmark_import', datetime.now().isoformat(), 7, 1, user_id, None))
            else:
                cursor.execute('''
                    INSERT INTO insights (content, source_url, source_type, content_category, shared_by, shared_date, quality_score, useful_for_daily)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (title, url, 'article', 'article', 'bookmark_import', datetime.now().isoformat(), 7, 1))
            imported += 1
        conn.commit()
        conn.close()
        flash(f'Imported {imported} bookmarks!', 'success')
    except Exception as e:
        flash(f'Error importing: {str(e)}', 'error')
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
    return redirect(url_for('library'))


# ---------- PLG: Public voice, share, referral ----------
@app.route('/voice/<username>')
def public_voice_profile(username):
    """Public voice profile page - shareable"""
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
    profile_user = cursor.fetchone()
    
    if not profile_user:
        flash('User not found', 'error')
        conn.close()
        return redirect(url_for('home'))
    
    cursor.execute("PRAGMA table_info(voice_profile)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'user_id' in cols:
        cursor.execute('''
            SELECT * FROM voice_profile 
            WHERE user_id = ? AND active = 1 ORDER BY created_at DESC LIMIT 1
        ''', (profile_user['id'],))
    else:
        cursor.execute('SELECT * FROM voice_profile WHERE active = 1 ORDER BY created_at DESC LIMIT 1')
    
    voice = cursor.fetchone()
    conn.close()
    
    if not voice:
        flash("This user hasn't created a voice profile yet", 'error')
        return redirect(url_for('home'))
    
    voice_dict = dict(voice)
    if voice_dict.get('analysis'):
        voice_dict['analysis'] = json.loads(voice_dict['analysis']) if isinstance(voice_dict['analysis'], str) else voice_dict['analysis']
    else:
        voice_dict['analysis'] = {}
    
    current_user = get_user(session['user_id']) if 'user_id' in session else None
    
    return render_template('public_voice.html',
        profile_user=dict(profile_user),
        voice=voice_dict,
        current_user=current_user)


@app.route('/generate-with-voice/<username>', methods=['POST'])
def generate_with_voice(username):
    """Generate content in someone else's voice (trial or logged-in)"""
    topic = request.form.get('topic', '').strip()
    if not topic:
        flash('Please enter a topic', 'error')
        return redirect(url_for('public_voice_profile', username=username))
    
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    profile_user = cursor.fetchone()
    if not profile_user:
        conn.close()
        flash('User not found', 'error')
        return redirect(url_for('home'))
    
    cursor.execute("PRAGMA table_info(voice_profile)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'user_id' in cols:
        cursor.execute('SELECT * FROM voice_profile WHERE user_id = ? AND active = 1 LIMIT 1', (profile_user['id'],))
    else:
        cursor.execute('SELECT * FROM voice_profile WHERE active = 1 LIMIT 1')
    voice_row = cursor.fetchone()
    conn.close()
    
    if not voice_row:
        flash('Voice profile not found', 'error')
        return redirect(url_for('public_voice_profile', username=username))
    
    voice_profile = dict(voice_row)
    if voice_profile.get('analysis'):
        voice_profile['analysis'] = json.loads(voice_profile['analysis']) if isinstance(voice_profile['analysis'], str) else voice_profile['analysis']
    
    user = get_user(session['user_id']) if 'user_id' in session else None
    if user is None:
        trial_key = f'trial_voice_{username}'
        trial_count = session.get(trial_key, 0)
        if trial_count >= 1:
            flash('Sign up free to continue generating in this voice', 'info')
            return redirect(url_for('signup', next=url_for('public_voice_profile', username=username)))
        session[trial_key] = trial_count + 1
    
    gen = init_generator()
    if not gen:
        flash('API key not configured', 'error')
        return redirect(url_for('home'))
    
    insights = search_engine.search(topic, limit=10)
    if not insights:
        flash(f'No relevant insights for "{topic}". Try a different topic.', 'info')
        return redirect(url_for('public_voice_profile', username=username))
    
    try:
        result = gen.generate(topic, insights, voice_profile, user_tier='free')
        generation_id = save_generation(topic, result, insights, user_id=user['id'] if user else None)
        if user:
            increment_generation_count(user['id'])
            track_usage(user['id'], 'generate_with_voice', {'topic': topic, 'voice_username': username})
        
        share_hash = None
        conn = sqlite3.connect('braingym.db')
        cursor = conn.cursor()
        cursor.execute('SELECT share_hash FROM generations WHERE id = ?', (generation_id,))
        row = cursor.fetchone()
        if row and row[0]:
            share_hash = row[0]
        conn.close()
        
        return render_template('content_results.html',
            topic=topic,
            generation_id=generation_id,
            linkedin=result['linkedin'],
            twitter=result['twitter'],
            blog=result['blog'],
            insights=insights,
            user=user,
            user_tier='free',
            share_hash=share_hash,
            voice_owner=username)
    except Exception as e:
        flash(f'Error: {str(e)}', 'error')
        return redirect(url_for('public_voice_profile', username=username))


@app.route('/my-voice')
@login_required
def my_voice():
    """User's own voice profile with share link"""
    user = get_user(session['user_id'])
    voice = get_active_voice_profile(user['id'])
    share_link = f"{request.host_url.rstrip('/')}/voice/{user['username']}"
    return render_template('my_voice.html', voice=voice, share_link=share_link, user=user)


@app.route('/share/<share_hash>')
def view_shared_generation(share_hash):
    """Public view of a shared generation"""
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(generations)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'share_hash' not in cols:
        conn.close()
        flash('Share not found', 'error')
        return redirect(url_for('home'))
    
    cursor.execute('SELECT * FROM generations WHERE share_hash = ?', (share_hash,))
    generation = cursor.fetchone()
    
    if not generation:
        conn.close()
        flash('Generation not found', 'error')
        return redirect(url_for('home'))
    
    gen_dict = dict(generation)
    gen_dict['twitter_content'] = json.loads(gen_dict['twitter_content']) if gen_dict.get('twitter_content') else []
    gen_dict['blog_content'] = json.loads(gen_dict['blog_content']) if gen_dict.get('blog_content') else {}
    
    insight_ids = json.loads(gen_dict['insights_used']) if gen_dict.get('insights_used') else []
    if insight_ids:
        placeholders = ','.join('?' * len(insight_ids))
        cursor.execute(f'SELECT id, content, source_url, content_category FROM insights WHERE id IN ({placeholders})', insight_ids)
        insights = [dict(zip(['id', 'content', 'source_url', 'content_category'], row)) for row in cursor.fetchall()]
    else:
        insights = []
    conn.close()
    
    linkedin = {'content': gen_dict['linkedin_content'], 'word_count': len((gen_dict['linkedin_content'] or '').split())}
    twitter = {'thread': gen_dict['twitter_content']}
    blog = gen_dict['blog_content'] if isinstance(gen_dict['blog_content'], dict) else {'title': '', 'intro': '', 'outline': ''}
    
    current_user = get_user(session['user_id']) if 'user_id' in session else None
    
    return render_template('shared_generation.html',
        generation=gen_dict,
        topic=gen_dict['topic'],
        linkedin=linkedin,
        twitter=twitter,
        blog=blog,
        insights=insights,
        current_user=current_user)


@app.route('/refer')
@login_required
def referral_page():
    """Referral dashboard"""
    user = get_user(session['user_id'])
    conn = sqlite3.connect('braingym.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT COUNT(*) as total,
               SUM(CASE WHEN converted = 1 THEN 1 ELSE 0 END) as converted
        FROM referrals WHERE referrer_id = ?
    ''', (user['id'],))
    row = cursor.fetchone()
    stats = {'total': row[0] or 0, 'converted': row[1] or 0}
    
    cursor.execute('''
        SELECT u.username, u.email, r.signup_date, r.converted
        FROM referrals r
        JOIN users u ON r.referee_id = u.id
        WHERE r.referrer_id = ?
        ORDER BY r.signup_date DESC LIMIT 10
    ''', (user['id'],))
    recent = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    referral_link = f"{request.host_url.rstrip('/')}/signup?ref={user['referral_code']}"
    bonus_generations = stats['converted'] * 5
    
    return render_template('referral.html',
        referral_link=referral_link,
        stats=stats,
        recent=recent,
        bonus_generations=bonus_generations,
        user=user)


@app.route('/onboarding-complete', methods=['POST'])
@login_required
def onboarding_complete():
    """Mark onboarding complete, award referral bonus"""
    check_and_award_referral_bonus(session['user_id'])
    flash('Onboarding complete! Start generating content.', 'success')
    return redirect(url_for('home'))


@app.route('/save', methods=['GET', 'POST'])
def save_content():
    """
    Save new content to library. Works for trial users (session limits) or logged-in users.
    """
    if request.method == 'GET':
        return render_template('content_save.html')
    content_type = request.form.get('type')  # 'url' or 'text'
    content = request.form.get('content', '').strip()
    note = request.form.get('note', '').strip()
    if not content:
        return jsonify({'success': False, 'message': 'Content is required'})
    user_id = session.get('user_id') if session else None
    trial_key = get_trial_key() if is_trial_user() else None
    if is_trial_user():
        can_save, limit_msg = check_trial_limit('save')
        if not can_save:
            return jsonify({'success': False, 'message': limit_msg, 'action': 'signup'})
        increment_trial_usage('save')
    if content_type == 'url':
        result = save_url(content, note, user_id=user_id, trial_key=trial_key)
    else:
        result = save_note(content, note, user_id=user_id, trial_key=trial_key)
    return jsonify(result)


def save_url(url, context_note='', user_id=None, trial_key=None):
    """Extract and save content from URL. Optional user_id and trial_key for ownership."""
    api_key = os.environ.get('FIRECRAWL_API_KEY')
    if not api_key:
        return {
            'success': False,
            'message': 'Firecrawl API key not set. Set FIRECRAWL_API_KEY environment variable to extract URLs.'
        }
    try:
        from firecrawl import FirecrawlApp
        firecrawl = FirecrawlApp(api_key=api_key)
        print(f"🔍 Extracting content from: {url}")
        result = firecrawl.scrape(url=url, formats=['markdown'])
        if not result or not hasattr(result, 'markdown'):
            return {'success': False, 'message': 'Could not extract content from URL'}
        markdown = result.markdown or ''
        metadata_obj = getattr(result, 'metadata', None)
        title = getattr(metadata_obj, 'title', None) if metadata_obj else None
        if not title:
            title = url
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
        tags = []
        if 'startup' in url.lower():
            tags.append('startups')
        if 'business' in url.lower():
            tags.append('business')
        conn = sqlite3.connect('braingym.db')
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(insights)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'user_id' in cols and 'trial_key' in cols:
            cursor.execute('''
                INSERT INTO insights (
                    content, source_url, source_type, content_category,
                    shared_by, shared_date, context_message,
                    extracted_text, extraction_status,
                    quality_score, useful_for_daily, tags, user_id, trial_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                title, url, category, category, 'manual_save',
                datetime.now().isoformat(), context_note, markdown, 'success',
                8, 1, ','.join(tags) if tags else None, user_id, trial_key
            ))
        else:
            cursor.execute('''
                INSERT INTO insights (
                    content, source_url, source_type, content_category,
                    shared_by, shared_date, context_message,
                    extracted_text, extraction_status,
                    quality_score, useful_for_daily, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                title, url, category, category, 'manual_save',
                datetime.now().isoformat(), context_note, markdown, 'success',
                8, 1, ','.join(tags) if tags else None
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
        return {'success': False, 'message': f'Error extracting content: {str(e)}'}


def save_note(text, context='', user_id=None, trial_key=None):
    """Save text as personal note. Optional user_id and trial_key for ownership."""
    if len(text.strip()) < 50:
        return {'success': False, 'message': 'Note too short (minimum 50 characters)'}
    tags = []
    text_lower = text.lower()
    keyword_map = {
        'startup': 'startups', 'business': 'business', 'product': 'product',
        'marketing': 'marketing', 'sales': 'sales', 'growth': 'growth',
        'team': 'teams', 'hiring': 'hiring', 'fund': 'fundraising',
        'investor': 'fundraising', 'pricing': 'pricing', 'customer': 'customers',
        'user': 'users', 'design': 'design', 'code': 'coding', 'engineer': 'engineering',
        'ai': 'ai', 'data': 'data'
    }
    for keyword, tag in keyword_map.items():
        if keyword in text_lower and tag not in tags:
            tags.append(tag)
    quality = 7
    if len(text) > 500:
        quality = 8
    if len(text) > 1000:
        quality = 9
    try:
        conn = sqlite3.connect('braingym.db')
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(insights)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'user_id' in cols and 'trial_key' in cols:
            cursor.execute('''
                INSERT INTO insights (
                    content, source_type, content_category,
                    shared_by, shared_date, context_message,
                    quality_score, useful_for_daily, tags, user_id, trial_key
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                text, 'my_note', 'my_note', 'manual_save', datetime.now().isoformat(),
                context, quality, 1, ','.join(tags) if tags else None, user_id, trial_key
            ))
        else:
            cursor.execute('''
                INSERT INTO insights (
                    content, source_type, content_category,
                    shared_by, shared_date, context_message,
                    quality_score, useful_for_daily, tags
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                text, 'my_note', 'my_note', 'manual_save', datetime.now().isoformat(),
                context, quality, 1, ','.join(tags) if tags else None
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
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("PRAGMA table_info(generations)")
    cols = [r[1] for r in cursor.fetchall()]
    if 'share_hash' in cols and 'user_id' in cols:
        cursor.execute("SELECT * FROM generations WHERE id = ?", (generation_id,))
    else:
        cursor.execute("""
            SELECT id, topic, created_at, linkedin_content, twitter_content, blog_content, insights_used
            FROM generations WHERE id = ?
        """, (generation_id,))
    
    row = cursor.fetchone()
    
    if not row:
        flash('Generation not found', 'error')
        conn.close()
        return redirect(url_for('history'))
    
    row_dict = dict(row) if hasattr(row, 'keys') else None
    share_hash = row_dict.get('share_hash') if row_dict else None
    
    # Parse content (by name for Row, by index for tuple)
    linkedin_content = row_dict.get('linkedin_content') if row_dict else row[2]
    twitter_content = row_dict.get('twitter_content') if row_dict else row[3]
    blog_content = row_dict.get('blog_content') if row_dict else row[4]
    insights_used = row_dict.get('insights_used') if row_dict else row[5]
    
    linkedin = {'content': linkedin_content, 'word_count': len((linkedin_content or '').split())}
    twitter = {'thread': json.loads(twitter_content) if twitter_content else []}
    blog = json.loads(blog_content) if blog_content else {}
    insight_ids = json.loads(insights_used) if insights_used else []
    
    if insight_ids:
        placeholders = ','.join('?' * len(insight_ids))
        cursor.execute(f"""
            SELECT id, content, source_url, content_category
            FROM insights
            WHERE id IN ({placeholders})
        """, insight_ids)
        
        insights = [dict(zip(['id', 'content', 'source_url', 'content_category'], r))
                   for r in cursor.fetchall()]
    else:
        insights = []
    
    conn.close()
    
    user = get_user(session['user_id']) if 'user_id' in session else None
    user_tier = (user.get('tier') or 'free') if user else 'free'
    topic = row_dict.get('topic') if row_dict else row[0]
    created_at = row_dict.get('created_at') if row_dict else row[1]
    
    return render_template('content_results.html',
                         topic=topic,
                         generation_id=generation_id,
                         created_at=created_at,
                         linkedin=linkedin,
                         twitter=twitter,
                         blog=blog,
                         insights=insights,
                         user=user,
                         user_tier=user_tier,
                         share_hash=share_hash)


def get_active_voice_profile(user_id=None):
    """Get current active voice profile (optionally for a specific user)"""
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
    
    if user_id is not None:
        # Check if user_id column exists
        cursor.execute("PRAGMA table_info(voice_profile)")
        cols = [row[1] for row in cursor.fetchall()]
        if 'user_id' in cols:
            cursor.execute('''
                SELECT * FROM voice_profile 
                WHERE active = 1 AND user_id = ?
                ORDER BY created_at DESC LIMIT 1
            ''', (user_id,))
        else:
            cursor.execute('''
                SELECT * FROM voice_profile 
                WHERE active = 1 
                ORDER BY created_at DESC LIMIT 1
            ''')
    else:
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


def save_voice_profile(sample_posts, analysis, user_id=None):
    """Save voice profile to database (optionally linked to user)"""
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
    
    # Deactivate old profiles for this user (or all if no user_id column)
    cursor.execute("PRAGMA table_info(voice_profile)")
    cols = [row[1] for row in cursor.fetchall()]
    if 'user_id' in cols and user_id is not None:
        cursor.execute('UPDATE voice_profile SET active = 0 WHERE user_id = ?', (user_id,))
    else:
        cursor.execute('UPDATE voice_profile SET active = 0')
    
    # Insert new profile
    if 'user_id' in cols:
        cursor.execute('''
            INSERT INTO voice_profile (
                sample_posts, analysis, tone, sentence_style, perspective,
                common_phrases, opening_style, closing_style,
                structure_preference, emoji_usage, user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            analysis.get('emoji_usage'),
            user_id
        ))
    else:
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
        
        # Save to database (with user_id if logged in)
        user_id = session.get('user_id')
        save_voice_profile(sample_posts, voice_profile, user_id=user_id)
        
        flash('✓ Voice profile learned! Your future content will match your writing style.', 'success')
        return redirect('/')
        
    except Exception as e:
        print(f"❌ Error analyzing voice: {e}")
        import traceback
        traceback.print_exc()
        flash(f'Error analyzing voice: {str(e)}', 'error')
        return redirect('/train-voice')


def save_generation(topic: str, result: dict, insights: list, user_id: int = None) -> int:
    """Save generation to database with user_id and share_hash"""
    conn = sqlite3.connect('braingym.db')
    cursor = conn.cursor()
    
    insight_ids = [i['id'] for i in insights]
    
    # Check if user_id and share_hash columns exist
    cursor.execute("PRAGMA table_info(generations)")
    cols = [row[1] for row in cursor.fetchall()]
    has_user_id = 'user_id' in cols
    has_share_hash = 'share_hash' in cols
    
    if has_user_id and has_share_hash:
        share_hash = generate_share_hash(0)  # temp, update after insert
        cursor.execute('''
            INSERT INTO generations 
            (topic, linkedin_content, twitter_content, blog_content, insights_used, user_id, share_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            topic,
            result['linkedin']['content'],
            json.dumps(result['twitter']['thread']),
            json.dumps(result['blog']),
            json.dumps(insight_ids),
            user_id,
            ''
        ))
    else:
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
    share_hash = generate_share_hash(generation_id)
    if has_share_hash:
        cursor.execute('UPDATE generations SET share_hash = ? WHERE id = ?', (share_hash, generation_id))
    if has_user_id and user_id is not None:
        cursor.execute('UPDATE generations SET user_id = ? WHERE id = ?', (user_id, generation_id))
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
