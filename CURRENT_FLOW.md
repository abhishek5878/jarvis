# Current Flow – AI Content Generator

This document describes how the system works end-to-end: routes, data flow, and components.

---

## 1. System Overview

**Product:** AI Content Generator from Personal Knowledge Library

**Purpose:** Turn saved links and notes into ready-to-publish content (LinkedIn, Twitter, Blog).

**Value:** “Turn your saved links into published content. Never stare at a blank page again.”

**App:** Flask app (`content_app.py`) on **port 5001**  
**URL:** http://localhost:5001

---

## 2. The Main Loop

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  DISCOVER   │ ──► │    SAVE     │ ──► │  GENERATE   │ ──► │   PUBLISH   │
│  Content    │     │  to Library │     │  with AI    │     │  (copy out) │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
       │                    │                    │                    │
       │                    │                    │                    │
       ▼                    ▼                    ▼                    ▼
  Find articles        /save (URL or      /generate (topic)    Copy LinkedIn /
  / tweets / ideas     note)              → 3 drafts           Twitter / Blog
```

- **Discover:** User finds content (Twitter, articles, own ideas).
- **Save:** User adds it via **Save** (URL or note) so it goes into the library.
- **Generate:** User enters a topic; system searches library and calls Claude to produce 3 drafts.
- **Publish:** User copies drafts and posts elsewhere (no in-app publish).

The loop repeats: more saves → richer library → better generations.

---

## 3. Routes and User Flows

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Home: topic input, save CTA, stats, recent generations & saves |
| `/generate` | POST | Generate content for a topic (search → Claude → save generation → show results) |
| `/save` | GET | Show save form (URL + Note tabs) |
| `/save` | POST | Save URL (extract + store) or Note (store + tag) → JSON response |
| `/suggest-topics` | GET | Suggest 5 topics from library (for “random ideas”) |
| `/history` | GET | List past generations (last 50) |
| `/generation/<id>` | GET | View one past generation (same layout as fresh results) |

---

## 4. Flow 1: Generate Content

**Trigger:** User submits topic on homepage (or from “suggest topics”).

```
User enters topic (e.g. "startup mistakes")
         │
         ▼
POST /generate
         │
         ├─► init_generator()  →  ContentGenerator(ANTHROPIC_API_KEY)
         │
         ├─► search_engine.search(topic, limit=10)
         │      • Keywords from topic
         │      • Query insights (useful_for_daily=1, not junk/personal)
         │      • Score: relevance × quality
         │      • Variety (categories, domains)
         │      • Return top 10 insights
         │
         ├─► If no insights → flash message, redirect home
         │
         ├─► generator.generate(topic, insights)
         │      • Build context from insights (content/extracted_text, tags, etc.)
         │      • Build prompt (LinkedIn + Twitter + Blog instructions)
         │      • Call Anthropic API (Claude Sonnet 4), with retries/timeouts
         │      • Parse response → linkedin, twitter, blog + source IDs
         │
         ├─► save_generation(topic, result, insights)
         │      • INSERT into generations (topic, linkedin_content, twitter_content, blog_content, insights_used)
         │
         └─► render content_results.html
               • Show LinkedIn post, Twitter thread, Blog outline
               • Copy buttons, source attributions
```

**Data:** Topic + 10 insights → Claude → 3 formats + source mapping → stored in `generations` and shown on results page.

---

## 5. Flow 2: Save New Content

**Trigger:** User clicks “Save New Content” (home or nav) → `/save`.

### 2a. Save URL (tab “Save URL”)

```
User pastes URL + optional context note
         │
         ▼
POST /save  (type=url, content=URL, note=...)
         │
         ├─► save_url(url, context_note)
         │      • Require FIRECRAWL_API_KEY
         │      • FirecrawlApp().scrape(url, formats=['markdown'])
         │      • Category from URL: linkedin/twitter/x → social_reference,
         │        youtube → video, github → code, else → article
         │      • INSERT into insights (
         │          content=title, source_url, content_category,
         │          shared_by='manual_save', context_message,
         │          extracted_text=markdown, extraction_status='success',
         │          quality_score=8, useful_for_daily=1, tags
         │        )
         │
         └─► JSON: { success, message, insight_id }
```

**Data:** URL + optional note → Firecrawl → markdown + metadata → one new row in `insights` (immediately usable for search/generation).

### 2b. Save Note (tab “Save Note”)

```
User writes note (50+ chars) + optional context
         │
         ▼
POST /save  (type=text, content=note, note=...)
         │
         ├─► save_note(text, context)
         │      • Length check (min 50 chars)
         │      • Simple keyword→tag mapping (startup, business, product, …)
         │      • Quality from length (7–9)
         │      • INSERT into insights (
         │          content=text, source_type/content_category='my_note',
         │          shared_by='manual_save', context_message,
         │          quality_score, useful_for_daily=1, tags
         │        )
         │
         └─► JSON: { success, message, insight_id }
```

**Data:** Text + optional context → one new `insights` row as `my_note` (no Firecrawl).

---

## 6. Flow 3: Topic Suggestions

**Trigger:** “Generate 5 Random Ideas from My Library” on home.

```
User clicks "Generate 5 Random Ideas"
         │
         ▼
GET /suggest-topics  (from frontend fetch)
         │
         ├─► search_engine.suggest_topics(limit=5)
         │      • Analyze tags in useful insights
         │      • Clusters + combinations
         │      • Return list of { topic, angle, count, … }
         │
         └─► JSON: { topics: [...] }
```

**Data:** Library tags → suggested topics; user can pick one and submit to `/generate`.

---

## 7. Flow 4: History and View Generation

**History:**

```
GET /history
         │
         ├─► SELECT from generations (id, topic, created_at, linkedin/twitter/blog)
         │   ORDER BY created_at DESC LIMIT 50
         │
         └─► content_history.html  (list with links to /generation/<id>)
```

**View one generation:**

```
GET /generation/<id>
         │
         ├─► SELECT generation by id
         ├─► Parse linkedin_content, twitter_content (JSON), blog_content (JSON)
         ├─► Resolve insights_used → fetch insight rows from insights
         │
         └─► content_results.html  (same as after fresh /generate)
```

**Data:** Stored generations are read-only; no edit/delete in current flow.

---

## 8. Data Flow Summary

```
                    ┌──────────────────┐
                    │   braingym.db    │
                    │                  │
  /save (URL)   ──► │  insights        │  ◄── initial load (WhatsApp, etc.)
  /save (note)  ──► │  (content,       │
                    │   extracted_text,│
                    │   tags, etc.)   │
                    │                  │
  /generate     ──► │  generations     │
  (read top 10)     │  (topic,         │
                    │   linkedin/      │
  /history      ◄── │   twitter/blog, │
  /generation/<id>  │   insights_used) │
                    └──────────────────┘
```

- **insights:** All “library” items (links, notes, extracted articles). Search and topic suggestions read from here; Save writes here.
- **generations:** Each run of “Generate” creates one row; History and View read from here.

---

## 9. Components

| Component | File | Role |
|-----------|------|------|
| Web app | `content_app.py` | Routes, flash, render templates, call search/generator/save helpers |
| Search | `search_engine.py` | `ContentSearchEngine`: search(topic), suggest_topics() |
| Generation | `content_generator.py` | `ContentGenerator`: build context, call Claude, parse response, retries/timeouts |
| Save URL | `content_app.save_url()` | Firecrawl scrape, categorize, INSERT into insights |
| Save note | `content_app.save_note()` | Tag/quality, INSERT into insights |
| DB | `braingym.db` | insights, generations |

**Templates (all under `templates_content/`):**

- `content_base.html` – Nav (Generate, Save, History), flash, scripts
- `content_home.html` – Hero, topic form, “Save New Content”, “Random Ideas”, stats, recent generations/saves
- `content_save.html` – Tabs: Save URL, Save Note; forms and success/error feedback
- `content_results.html` – LinkedIn, Twitter, Blog sections + copy + sources
- `content_history.html` – List of generations with links to `/generation/<id>`

---

## 10. Environment and APIs

| Variable | Used for |
|----------|----------|
| `ANTHROPIC_API_KEY` | Claude API in `ContentGenerator.generate()` (required for /generate) |
| `FIRECRAWL_API_KEY` | URL extraction in `save_url()` (required for Save URL; Save Note works without it) |

**Port:** 5001 (set in `content_app.py`).

---

## 11. End-to-End Example

1. **Home** → User sees stats (e.g. 2,421 insights, recent saves/generations).
2. **Save** → User goes to Save, pastes article URL, adds note “pricing framework” → Extract & Save → New insight in DB.
3. **Home** → User enters topic “pricing for startups” → Generate.
4. **Backend** → Search finds ~10 relevant insights (including the new one) → Claude returns LinkedIn + Twitter + Blog → Stored in `generations` → Results page.
5. **Results** → User copies LinkedIn post (or thread/blog) and publishes elsewhere.
6. **History** → User can later open the same run via History → “View” → same results page.

This is the current flow as implemented in the codebase and described in this document.
