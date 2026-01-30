# 🧠 Brain Gym Phase 2 - Daily Practice Web App

## What's New in Phase 2

You now have a beautiful web interface for your daily practice!

### Features

✅ **Daily Practice Interface**
- Shows 3 curated insights each day
- Smart selection algorithm (quality, variety, freshness)
- Contextual prompts for each insight
- Clean, mobile-friendly design

✅ **Response System**
- Capture your 2-3 sentence reactions
- Link responses to original insights
- Track engagement over time

✅ **Search Your Thinking**
- Search by keyword across all responses
- Filter by tag
- See original insight + your response side-by-side

✅ **Stats Dashboard**
- Current streak (days in a row)
- Response rate
- Top themes you engage with
- Activity timeline

✅ **Manual Add**
- Add insights on the fly
- Auto-classification and tagging
- Paste URLs or text directly

✅ **Response Library**
- All your responses in one place
- Your content library for future use
- Copy and share capabilities

## Quick Start

### 1. Install Flask

```bash
cd ~/jarvis
pip3 install Flask
```

### 2. Launch the App

```bash
python3 app.py
```

You'll see:
```
🧠 Brain Gym - Daily Practice
==================================================
Starting web app on http://localhost:5000
Press Ctrl+C to stop
==================================================
```

### 3. Open in Browser

Visit: **http://localhost:5000**

Or from your phone (if on same network):
**http://your-computer-ip:5000**

## How It Works

### Daily Practice Flow

1. **Visit Home** - See today's 3 insights
2. **Read & Think** - Each has a contextual prompt
3. **Respond** - Write 2-3 sentences (your take)
4. **Submit** - Response saved, insight marked complete
5. **Repeat** - Come back tomorrow for 3 new ones

### Smart Selection Algorithm

The app picks insights based on:
- **Quality**: High-value content first
- **Variety**: Different tags and types
- **Freshness**: Not shown recently
- **Engagement**: Lower priority for repeatedly skipped
- **Status**: Only unresponded, non-archived

### Database Schema (Phase 2 Additions)

**New Tables:**
```sql
responses
├─ id
├─ insight_id (foreign key)
├─ response_text
├─ response_tags
└─ created_at

user_actions
├─ id
├─ insight_id
├─ action_type (responded/skipped/archived)
└─ action_date

daily_sessions
├─ id
├─ session_date
├─ insights_shown (comma-separated IDs)
└─ completed
```

**Extended insights table:**
```sql
insights
├─ ... (existing columns)
├─ last_shown_date (track when displayed)
├─ times_skipped (count skips)
├─ archived (boolean - not interested)
└─ quality_score (1-10, defaults to 5, high_value = 8)
```

## Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Home - daily 3 insights |
| `/respond` | POST | Submit response |
| `/skip/<id>` | POST | Skip insight for now |
| `/archive/<id>` | POST | Archive insight (not interested) |
| `/search?q=keyword&tag=tag` | GET | Search responses |
| `/stats` | GET | Statistics dashboard |
| `/add` | GET/POST | Manually add insight |
| `/library` | GET | View all responses |
| `/api/stats` | GET | JSON stats (for future use) |

## Usage Examples

### Daily Practice

1. Open http://localhost:5000
2. See your 3 insights for today
3. For each one:
   - Read the content
   - Think about the prompt
   - Write your response (2-3 sentences)
   - Hit "Submit Response"
4. Come back tomorrow for 3 new insights!

### Searching Your Responses

**By keyword:**
```
http://localhost:5000/search?q=startup
http://localhost:5000/search?q=mental+model
```

**By tag:**
```
http://localhost:5000/search?tag=startups
http://localhost:5000/search?tag=productivity
```

**Combined:**
```
http://localhost:5000/search?q=framework&tag=mental_models
```

### Manual Add

1. Go to "Add Insight" (+ button in nav)
2. Paste the content
3. Add source URL (optional)
4. Add context notes (optional)
5. Submit - auto-tagged and added to queue

## Mobile Usage

The interface is fully mobile-friendly!

**Find your computer's IP:**
```bash
# macOS/Linux
ifconfig | grep "inet "

# Look for something like: 192.168.1.XXX
```

**Access from phone:**
```
http://192.168.1.XXX:5000
```

Pro tip: Bookmark it on your phone's home screen for quick access!

## Tips for Building the Habit

### Morning Routine (Recommended)

```
☕ Coffee + Brain Gym
├─ Open http://localhost:5000
├─ Read insight 1, respond
├─ Read insight 2, respond
├─ Read insight 3, respond
└─ 10 minutes total
```

### Quality Over Speed

- Don't rush your responses
- 2-3 sentences is perfect
- Your genuine reaction > trying to sound smart
- These become your content library

### Use Your Responses

1. **Writing**: Search for a topic, review your takes
2. **Tweets**: Copy your responses → edit → post
3. **Articles**: Multiple responses on same theme → essay outline
4. **Conversations**: Reference your thinking on topics

## Architecture

```
~/jarvis/
├── app.py                    # Flask web application
├── database_v2.py            # Extended database with Phase 2 features
├── database.py               # Original database (still used by CLI)
├── classifier.py             # Auto-tagging (used by both)
├── parser.py                 # WhatsApp parser (Phase 1)
├── templates/                # HTML templates
│   ├── base.html            # Base layout with nav
│   ├── home.html            # Daily practice page
│   ├── search.html          # Search interface
│   ├── stats.html           # Dashboard
│   ├── add.html             # Manual add form
│   └── library.html         # Response library
├── braingym.db              # SQLite database (shared)
└── requirements_phase2.txt  # Phase 2 dependencies
```

## Customization

### Change Daily Count

Edit `app.py`:
```python
insights = db.get_daily_insights(count=5)  # Show 5 instead of 3
```

### Modify Selection Algorithm

Edit `database_v2.py` → `get_daily_insights()`:
- Adjust quality score weights
- Change variety logic
- Modify time spacing rules

### Customize Prompts

Edit `app.py` → `get_prompt_for_insight()`:
- Add new prompt types
- Customize by tag or source
- Make prompts more specific

### Change Theme/Styling

Templates use Tailwind CSS (CDN). To customize:
- Edit `templates/base.html` for colors
- Modify individual template styles
- Add custom CSS in `<style>` blocks

## Troubleshooting

### "Address already in use"

```bash
# Find and kill process on port 5000
lsof -ti:5000 | xargs kill -9

# Or use different port
python3 app.py --port 5001
```

### "Module not found: Flask"

```bash
pip3 install Flask
```

### Database Errors

```bash
# Backup first
cp braingym.db braingym_backup.db

# Check database
sqlite3 braingym.db "SELECT COUNT(*) FROM insights;"

# Rebuild Phase 2 tables
python3 -c "from database_v2 import BrainGymDBV2; BrainGymDBV2()"
```

### No Insights Showing

```bash
# Check pending count
python3 main.py --stats

# If all responded, check
sqlite3 braingym.db "SELECT status, COUNT(*) FROM insights GROUP BY status;"

# Reset some to pending if needed (optional)
sqlite3 braingym.db "UPDATE insights SET status='pending' WHERE id IN (SELECT id FROM insights WHERE status='responded' ORDER BY RANDOM() LIMIT 10);"
```

## Production Deployment (Optional)

### Run with Gunicorn

```bash
pip3 install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### Background Process

```bash
# Using nohup
nohup python3 app.py > brain_gym.log 2>&1 &

# Using screen
screen -S braingym
python3 app.py
# Press Ctrl+A then D to detach
```

### Nginx Reverse Proxy (Advanced)

```nginx
server {
    listen 80;
    server_name braingym.local;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## What's Next?

### Phase 3 Ideas

- **Export Features**: Export responses as tweets, LinkedIn posts, blog drafts
- **AI Enhancements**: GPT-powered prompt generation, insight summarization
- **Social**: Share responses, discuss with others
- **Analytics**: Deeper insights into your thinking patterns
- **Mobile App**: Native iOS/Android app
- **API**: Public API for integrations
- **Reminders**: Daily notification to complete practice
- **Themes**: Dark mode, custom themes

Want any of these? Just ask!

## Support

### Check Logs

```bash
# If running in terminal, logs show in real-time
# If background process:
tail -f brain_gym.log
```

### Database Stats

```bash
# Via web
http://localhost:5000/stats

# Via CLI
python3 main.py --stats
```

### Backup

```bash
# Quick backup
./backup.sh

# Backup before updates
cp braingym.db braingym_before_phase2.db
```

---

**You're ready to start your daily practice!** Open http://localhost:5000 and begin building your content library.
