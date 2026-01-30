# 🧠 Brain Gym - Command Reference

Quick reference for all Brain Gym commands.

## Processing WhatsApp Exports

```bash
# Process single file
python3 main.py "WhatsApp Chat - Group Name/_chat.txt"

# Process multiple files
python3 main.py chat1.txt chat2.txt chat3.txt

# Process all your current groups
python3 main.py "WhatsApp Chat - Heimdall/_chat.txt" \
                "WhatsApp Chat - Life I want/_chat.txt" \
                "WhatsApp Chat - The PLAN/_chat.txt"

# View statistics
python3 main.py --stats

# Show recent insights
python3 main.py --show 20
```

## Exploring Your Database

### Search by Keyword

```bash
# Search for any keyword in content
python3 explore.py --search 'startup'
python3 explore.py --search 'mental model'
python3 explore.py --search 'productivity'
python3 explore.py --search 'ai'

# Increase results
python3 explore.py --search 'founder' --limit 50
```

### Filter by Tags

```bash
# Available tags (top ones):
python3 explore.py --tag high_value
python3 explore.py --tag startups
python3 explore.py --tag business
python3 explore.py --tag tech
python3 explore.py --tag mindset
python3 explore.py --tag creativity
python3 explore.py --tag self_improvement
python3 explore.py --tag data_driven
python3 explore.py --tag tactical
python3 explore.py --tag mental_models
python3 explore.py --tag productivity
python3 explore.py --tag learning
python3 explore.py --tag philosophical
python3 explore.py --tag marketing
python3 explore.py --tag inspirational
python3 explore.py --tag writing
python3 explore.py --tag cautionary
python3 explore.py --tag psychology

# Combine with limit
python3 explore.py --tag startups --limit 30
```

### Filter by Content Type

```bash
# By source type
python3 explore.py --type tweet       # Twitter/X posts
python3 explore.py --type linkedin    # LinkedIn posts
python3 explore.py --type article     # Medium, Substack, blogs
python3 explore.py --type video       # YouTube videos
python3 explore.py --type quote       # Standalone insights
python3 explore.py --type link        # General URLs
```

### Special Filters

```bash
# Only high-value insights
python3 explore.py --high-value --limit 50

# Random selection (for daily practice)
python3 explore.py --random 3
python3 explore.py --random 5

# Analyze all tags
python3 explore.py --tags-analysis
```

## Backup

```bash
# Create backup
./backup.sh

# Manual backup
cp braingym.db "braingym_backup_$(date +%Y%m%d).db"

# Backup to Dropbox/Drive (if mounted)
cp braingym.db ~/Dropbox/braingym_backup.db
```

## Database Operations

### Direct SQL Access

```bash
# Open database
sqlite3 braingym.db

# Example queries:
sqlite> SELECT COUNT(*) FROM insights;
sqlite> SELECT DISTINCT source_type FROM insights;
sqlite> SELECT * FROM insights WHERE tags LIKE '%startups%' LIMIT 5;
sqlite> SELECT shared_by, COUNT(*) FROM insights GROUP BY shared_by;
sqlite> .quit
```

### Export Insights

```bash
# Export to text file
python3 explore.py --tag startups --limit 100 > startups_export.txt
python3 explore.py --high-value > high_value_insights.txt

# Export specific search
python3 explore.py --search 'framework' > frameworks.txt
```

## Workflow Examples

### Morning Routine

```bash
# Get 3 random insights to think about
python3 explore.py --random 3
```

### Content Creation

```bash
# Looking for startup content ideas
python3 explore.py --tag startups --limit 20

# Need frameworks for an article
python3 explore.py --search 'framework' --limit 15

# Want tactical advice to share
python3 explore.py --tag tactical --limit 10
```

### Deep Dive on a Topic

```bash
# Everything about mental models
python3 explore.py --tag mental_models --limit 100 > mental_models.txt

# All productivity insights
python3 explore.py --tag productivity --limit 50
```

### Quality Review

```bash
# Check high-value insights
python3 explore.py --high-value --limit 50

# Review recent additions
python3 main.py --show 30

# See what you have by type
python3 explore.py --type tweet --limit 20
python3 explore.py --type article --limit 20
```

## Testing

```bash
# Run test suite
python3 test_parser.py

# Test with sample data
python3 main.py sample_whatsapp_export.txt
```

## Maintenance

### Clean Up Test Data

```bash
# Remove test database
rm test_braingym.db

# Start fresh (CAREFUL - deletes everything!)
rm braingym.db
python3 main.py "WhatsApp Chat - Heimdall/_chat.txt"
```

### Update Exports

```bash
# Re-export WhatsApp groups (to get new messages)
# Then re-run (duplicates are skipped automatically)
python3 main.py "WhatsApp Chat - Heimdall/_chat.txt"
```

### Check Database Size

```bash
# Database size
ls -lh braingym.db

# Detailed stats
python3 main.py --stats
```

## Tips & Tricks

### Save Common Commands as Aliases

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
# Brain Gym shortcuts
alias bg='cd ~/jarvis'
alias bgs='python3 ~/jarvis/main.py --stats'
alias bgr='python3 ~/jarvis/explore.py --random 3'
alias bghv='python3 ~/jarvis/explore.py --high-value --limit 20'
alias bgb='cd ~/jarvis && ./backup.sh'
```

Then use:
```bash
bg      # Go to Brain Gym folder
bgs     # Show stats
bgr     # Get 3 random insights
bghv    # Show high-value insights
bgb     # Create backup
```

### Combine with Other Tools

```bash
# Open random insight URL in browser (macOS)
python3 explore.py --random 1 | grep '🔗' | awk '{print $2}' | xargs open

# Count insights by tag
python3 explore.py --tags-analysis | grep 'startups'

# Export to clipboard (macOS)
python3 explore.py --tag startups --limit 5 | pbcopy
```

### Regular Maintenance

```bash
# Weekly routine
./backup.sh                          # Backup database
python3 main.py --stats              # Check growth
python3 explore.py --high-value -limit 10  # Review quality
```

## Getting Help

```bash
# Show help for main script
python3 main.py --help

# Show help for explorer
python3 explore.py --help

# Read documentation
cat README.md
cat QUICKSTART.md
cat YOUR_RESULTS.md
```

## Common Patterns

### Find Something Specific

```bash
# "I remember reading about X"
python3 explore.py --search 'topic you remember'

# "What did I save about Y?"
python3 explore.py --tag relevant_tag --limit 50
```

### Content Ideas

```bash
# Need tweet ideas
python3 explore.py --type tweet --limit 20

# Need article topics
python3 explore.py --tag writing --limit 15
```

### Learning

```bash
# Study mental models
python3 explore.py --tag mental_models

# Learn from mistakes
python3 explore.py --tag cautionary
```

---

**Pro tip**: Bookmark this file. It's your command reference for everything Brain Gym can do.
