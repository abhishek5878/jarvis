# 🚀 Brain Gym Quick Start Guide

Get up and running in 5 minutes.

## Step 1: Export Your WhatsApp Chats

### On iPhone:
1. Open WhatsApp
2. Go to the group chat you want to export
3. Tap the group name at the top
4. Scroll down → "Export Chat"
5. Select "Without Media"
6. Save to Files or email yourself
7. Transfer the .txt file to your computer

### On Android:
1. Open WhatsApp
2. Go to the group chat
3. Tap the three dots (⋮) → More → Export chat
4. Choose "Without Media"
5. Save/share the .txt file
6. Transfer to your computer

## Step 2: Move Files to Brain Gym Folder

```bash
# Put your WhatsApp export files in the jarvis folder
mv ~/Downloads/WhatsApp\ Chat*.txt ~/jarvis/
```

## Step 3: Process Your Chats

```bash
cd ~/jarvis

# Process one file
python3 main.py "WhatsApp Chat - Group 1.txt"

# Process multiple files
python3 main.py chat1.txt chat2.txt chat3.txt

# Or process all .txt files in the folder
python3 main.py *.txt
```

That's it! The system will:
- ✅ Parse all messages
- ✅ Extract links and insights
- ✅ Auto-tag content
- ✅ Store in database
- ✅ Show you stats and first 10 insights

## Step 4: Explore Your Database

```bash
# View overall statistics
python3 main.py --stats

# Show recent 20 insights
python3 main.py --show 20

# Show recent 50 insights
python3 main.py --show 50
```

## What Gets Extracted?

**Links from:**
- Twitter/X threads
- LinkedIn posts
- YouTube videos
- Medium/Substack articles
- Any URL

**Plus:**
- Standalone quotes
- Insights (meaningful messages 30+ chars)
- Context (who shared, when, what they said)

**Filtered out:**
- System messages
- Short replies (ok, yes, lol, etc.)
- Emoji-only messages

## Understanding the Output

```
[1] ID: 445                          ← Database ID
👤 Shared by: John Smith            ← Who shared it
📅 Date: 29/01/2026, 14:23          ← When they shared it
🔖 Type: tweet                       ← Content type
🏷️  Tags: startups, tactical...     ← Auto-generated tags
💭 Content: Thread on how to...     ← The insight/message
🔗 URL: https://twitter.com/...     ← Original link
```

## Database Location

Your insights are stored in: `braingym.db`

**Important:** Back this file up! It's your entire database.

```bash
# Backup your database
cp braingym.db braingym_backup_$(date +%Y%m%d).db
```

## Common Issues

**"command not found: python"**
```bash
# Use python3 instead
python3 main.py yourfile.txt
```

**"File not found"**
```bash
# Check the file is in the jarvis folder
ls ~/jarvis/*.txt

# Or use full path
python3 main.py /full/path/to/chat.txt
```

**"No insights extracted"**
- Check your WhatsApp export format
- Look at `sample_whatsapp_export.txt` for the expected format
- WhatsApp exports vary by region/version

## Next Steps

1. **Verify quality**: Check first 10 insights to see extraction quality
2. **Process more chats**: Add all your valuable group chats
3. **Explore tags**: See what themes emerge in `--stats`
4. **Phase 2**: Once you have a good database, we'll build the daily practice system

## Tips

💡 **Multiple exports safe**: You can re-run on same files - duplicates are skipped

💡 **Incremental updates**: Export same group again later to add new messages

💡 **Tag customization**: Edit `classifier.py` to add your own themes

💡 **Backup regularly**: Your `braingym.db` is precious - back it up!

## Ready for Phase 2?

Once you have 100+ insights in your database and you're comfortable with the extraction quality, let me know and we'll build the daily Brain Gym practice system:

- 3 random insights per day
- Engaging prompts
- Response logging
- Content library building

---

Questions? Issues? Want to customize? Just ask!
