# 🔧 Troubleshooting Guide - Brain Gym

## ✅ System Status

**App is running on:** http://localhost:5001  
**Backend:** ✅ Working  
**Database:** ✅ Working (2,421 insights ready)  
**Content formatter:** ✅ Working  

---

## 🤔 What's Not Working?

Please tell me specifically what issue you're seeing:

### **Common Issues:**

1. **❌ Page won't load / Connection refused**
   - Symptom: Browser shows "Can't connect" or "Refused to connect"
   - Fix: App is running! Try http://127.0.0.1:5001 instead

2. **❌ Page loads but looks broken / No styling**
   - Symptom: Plain text, no colors, broken layout
   - Fix: Clear browser cache (Cmd+Shift+R) or try incognito mode

3. **❌ Content not displaying properly**
   - Symptom: Empty cards, missing text, garbled content
   - Fix: Check browser console for errors (Cmd+Option+J)

4. **❌ Can't submit responses**
   - Symptom: Form doesn't work, button does nothing
   - Fix: Check if JavaScript is enabled

5. **❌ "Read full article" button not working**
   - Symptom: Click does nothing
   - Fix: Check browser console for errors

6. **❌ Very slow / Takes long to load**
   - Symptom: Page takes >10 seconds to load
   - Fix: Database might be large, this is normal for first load

---

## 🧪 Quick Tests

### **Test 1: Check if app is accessible**
```bash
curl http://localhost:5001
```
Expected: Should return HTML

### **Test 2: Check for backend errors**
```bash
cd ~/jarvis
python3 -c "from utils import BrainGymUtils; print(BrainGymUtils().get_daily_three())"
```
Expected: Should show 3 insights

### **Test 3: Check database**
```bash
cd ~/jarvis
sqlite3 braingym.db "SELECT COUNT(*) FROM insights WHERE useful_for_daily = 1"
```
Expected: Should show ~2421

---

## 🔍 Debug Steps

### **Step 1: Check Browser Console**
1. Open http://localhost:5001
2. Press `Cmd + Option + J` (Mac) or `F12` (Windows/Linux)
3. Look for red errors
4. Share the error message

### **Step 2: Check Flask Logs**
```bash
# View recent Flask logs
tail -50 /Users/abhishekvyas/.cursor/projects/Users-abhishekvyas-jarvis/terminals/348845.txt
```

### **Step 3: Test a Simple Page Load**
```bash
# This should work instantly
curl -s http://localhost:5001 | grep "Today's Insights"
```

### **Step 4: Force Restart**
```bash
# Kill and restart Flask
pkill -9 -f "python3 app.py"
cd ~/jarvis
python3 app.py
```

---

## 🎯 What Should You See?

When working correctly, you should see:

### **Home Page (`/`):**
- ✅ Large heading "Today's Insights"
- ✅ Your streak badge (if you have one)
- ✅ 3 insight cards with:
  - Gradient header with badge
  - Tags you can click
  - Full article content (readable text)
  - "Read full article" button for long content
  - Prompt section ("💭 What's your take?")
  - Large textarea for response
  - Submit and Skip buttons
- ✅ Stats footer at bottom

### **Styling:**
- ✅ Modern, spacious design
- ✅ Blue and purple gradient accents
- ✅ Large, readable text (18px)
- ✅ Shadow effects on cards
- ✅ Rounded corners everywhere

---

## 🚨 Specific Issues & Fixes

### **Issue: "Page is too cramped / hard to read"**
**Status:** Should be fixed now!
- New design has 48px spacing between cards
- 32px padding inside cards
- 18px base font size
- 1.8 line height

### **Issue: "Content is cut off"**
**Expected behavior:** Long articles show preview + "Read full article" button
- Click button to expand
- Button changes to "Show less"
- This is intentional to avoid overwhelming you

### **Issue: "No insights showing"**
**Possible causes:**
1. All insights already responded to today
2. Database issue
3. Date filter too aggressive

**Fix:**
```python
# Check if you have pending insights
cd ~/jarvis
python3 -c "
from utils import BrainGymUtils
u = BrainGymUtils()
stats = u.get_stats()
print(f'Pending: {stats[\"pending\"]}')
print(f'Responses: {stats[\"total_responses\"]}')
"
```

### **Issue: "JavaScript not working"**
**Check:**
1. Browser has JavaScript enabled
2. No browser extensions blocking scripts
3. Check browser console for errors

---

## 📋 System Info

**Current Status:**
```
✅ Flask app: Running on port 5001
✅ Database: ~/jarvis/braingym.db
✅ Insights ready: 2,421
✅ Backend: Working
✅ Content extraction: Working
✅ Formatters: Working
```

**Files:**
```
~/jarvis/
├── app.py              ← Flask app (running)
├── utils.py            ← Backend logic
├── braingym.db         ← Database
└── templates/
    ├── base.html       ← Layout
    └── home.html       ← Daily page
```

---

## 💡 Most Likely Issues

Based on your "not working properly" comment, here are the most common issues:

### **1. Browser Cache** (Most Common!)
**Symptom:** Old styling, broken layout
**Fix:**
```
Hard refresh: Cmd + Shift + R (Mac) or Ctrl + Shift + R (Windows)
Or: Open in Incognito/Private mode
```

### **2. JavaScript Not Loading**
**Symptom:** "Read full article" doesn't work, form doesn't submit
**Fix:** Check browser console for errors

### **3. Content Display Issue**
**Symptom:** Text is garbled or missing
**Fix:** The content should now be formatted properly with the new UI

---

## 🆘 Still Not Working?

If it's still not working after trying the above:

1. **Take a screenshot** of what you're seeing
2. **Open browser console** (Cmd+Option+J) and screenshot any errors
3. **Share:** "The issue is: [specific description]"
4. **Tell me:** What happens when you:
   - Load the page?
   - Click "Read full article"?
   - Try to submit a response?

---

## ✅ Expected Working State

The app should:
- ✅ Load in < 2 seconds
- ✅ Show 3 insights with full content
- ✅ Have large, readable text
- ✅ Allow expanding long articles
- ✅ Let you submit responses
- ✅ Show stats at the bottom

**If any of these are not working, let me know which one!**

---

*App is running and backend is healthy. Just need to identify the specific UI issue you're experiencing.*
