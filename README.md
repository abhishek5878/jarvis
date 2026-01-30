# 🧠 Brain Gym

> Ferment ideas into original thinking

A system to extract insights from WhatsApp group exports, build a structured knowledge database, and develop a daily practice of engaging with ideas to create original content.

## What It Does

Brain Gym helps you:
1. **Extract** insights, links, and quotes from WhatsApp group chats
2. **Organize** them in a structured database with auto-tagging
3. **Engage** with 3 random ideas daily to develop your thinking
4. **Build** a personal content library from your reactions

## Features (Phase 1 - COMPLETE ✅)

### WhatsApp Parser
- Parses WhatsApp .txt export files (both bracket and dash formats)
- Extracts all URLs (Twitter/X, LinkedIn, YouTube, articles)
- Captures context around each link (who shared, what they said)
- Extracts standalone quotes/insights even without links
- Handles multi-line messages properly
- Preserves timestamp and sender metadata

### Content Classifier
- Auto-tags by theme (startups, productivity, writing, mental models, etc.)
- Detects content type (tactical, philosophical, cautionary, inspirational)
- Flags high-value insights
- Supports 10+ categories and growing

### Database
- SQLite-based (simple, local, no setup)
- Deduplication (won't store same insight twice)
- Tracks status (pending/responded/archived)
- Stores your responses for future content creation

## Installation

```bash
# Clone or download the project
cd jarvis

# No dependencies to install! Uses Python standard library only.
# Optional: Install enhanced dependencies
pip install -r requirements.txt
```

## Usage

### 1. Export Your WhatsApp Chats

On WhatsApp:
1. Open the group chat
2. Tap the group name → More → Export chat
3. Choose "Without Media"
4. Save the .txt file

### 2. Process the Files

```bash
# Process one or multiple files
python main.py chat1.txt chat2.txt chat3.txt

# This will:
# - Parse all messages
# - Extract insights and links
# - Auto-tag and classify
# - Store in database
# - Show stats and first 10 insights
```

### 3. View Statistics

```bash
# Show database stats
python main.py --stats

# Show recent insights
python main.py --show 20
```

## Database Schema

```sql
insights table:
├─ id (primary key)
├─ content (TEXT) - The insight/quote
├─ source_url (TEXT) - Original URL if any
├─ source_type (TEXT) - tweet/article/quote/video/linkedin
├─ shared_by (TEXT) - WhatsApp sender
├─ shared_date (TEXT) - When shared
├─ context_message (TEXT) - Full message context
├─ tags (TEXT) - Comma-separated tags
├─ my_response (TEXT) - Your reaction (null initially)
├─ response_date (TEXT) - When you responded
└─ status (TEXT) - pending/responded/archived
```

## Auto-Tagging System

**Themes:**
- startups, productivity, writing, mental_models
- philosophy, tech, marketing, psychology
- learning, creativity

**Types:**
- tactical (how-to, guides)
- philosophical (meaning, purpose)
- cautionary (mistakes, warnings)
- inspirational (motivation, success)
- data_driven (research, statistics)

**Meta-tags:**
- business, self_improvement, mindset
- high_value (algorithmic flag)

## Phase 2 (Coming Next)

- Daily selector: Pick 3 unresponded insights
- Response prompts: "Agree/disagree?", "What's missing?", "Your version?"
- CLI/Web interface for daily practice
- Export responses as content drafts

## File Structure

```
jarvis/
├── main.py          # CLI entry point
├── parser.py        # WhatsApp message parser
├── database.py      # SQLite database layer
├── classifier.py    # Content classification & tagging
├── requirements.txt # Dependencies (optional)
├── README.md        # This file
└── braingym.db      # SQLite database (created on first run)
```

## Example Output

```
📱 Processing WhatsApp export: chat1.txt
✓ Parsed 1,234 messages
✓ Extracted 456 insights
✓ Stored 445 new insights
⚠ Skipped 11 duplicates

📊 BRAIN GYM STATISTICS
═══════════════════════════════════════════════════════════
📚 Total Insights: 445

🔗 By Type:
   Tweet: 187
   Article: 98
   Quote: 76
   Video: 45
   Linkedin: 39

👥 Top Sharers:
   1. John Smith: 124 insights
   2. Jane Doe: 98 insights
   3. Bob Wilson: 87 insights

🧠 RECENT INSIGHTS (showing 10)
═══════════════════════════════════════════════════════════
[1] ID: 445
👤 Shared by: John Smith
📅 Date: 29/01/2026, 14:23
🔖 Type: tweet
🏷️  Tags: startups, tactical, business, high_value
💭 Content: Thread on how to validate startup ideas in 48 hours...
🔗 URL: https://twitter.com/founder/status/123456
```

## Tips

1. **Multiple exports**: Process all your group chats at once
2. **Re-running**: Safe to re-run on same files - deduplication prevents duplicates
3. **Backup**: The `braingym.db` file is your database - back it up!
4. **Tags**: Check the classifier.py file to customize tag categories

## Architecture

- **Zero dependencies** for core functionality (uses Python stdlib)
- **SQLite** for persistence (single file, no server needed)
- **Modular design** (parser, classifier, database are independent)
- **Extensible** (easy to add new classifiers, sources, etc.)

## Why This Works

1. **Capture**: You're already in great WhatsApp groups - this extracts the gold
2. **Context**: Keeps who shared what, when, and why they shared it
3. **Process**: Auto-tagging helps you see patterns and themes
4. **Practice**: Daily engagement turns consumption into creation
5. **Library**: Your responses become your content library

## Next Steps

1. **Run it**: Process your WhatsApp exports
2. **Review**: Check the first 10 insights to verify extraction quality
3. **Adjust**: Tweak classifier tags if needed for your use case
4. **Phase 2**: Once comfortable, we'll build the daily practice system

---

Built with ☕ and curiosity. Let's ferment some ideas.
