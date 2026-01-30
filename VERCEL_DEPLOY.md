# Deploy Content Generator to Vercel

## What’s configured

- **Entry point:** `index.py` (imports `app` from `content_app`)
- **Dependencies:** `requirements-vercel.txt` (Flask, anthropic, firecrawl-py)
- **Config:** `vercel.json` (Flask framework, install command)
- **Ignore:** `.vercelignore` (excludes WhatsApp exports, backups, etc.)
- **Optional:** `pyproject.toml` with `[project.scripts] app = "content_app:app"`

## Before you push

### 1. Database

- **Include `braingym.db`** in the repo so Vercel can deploy it (it’s not in `.vercelignore`).
- If the file is in `.gitignore`, either:
  - Remove `braingym.db` from `.gitignore` and commit it, or  
  - Use an external DB (e.g. Vercel Postgres) and change the app to use it.

### 2. Environment variables (Vercel project)

In **Vercel Dashboard → Your Project → Settings → Environment Variables**, add:

| Name                 | Value        | Notes                    |
|----------------------|-------------|--------------------------|
| `ANTHROPIC_API_KEY`  | `sk-ant-…`  | Required for generation  |
| `FIRECRAWL_API_KEY`  | `fc-…`      | Optional, for URL save   |
| `SECRET_KEY`         | (random)    | Optional, for Flask sessions |

Use the same values you use locally.

---

## Push to your Vercel project

### Option A: Git (recommended)

1. **Connect repo to Vercel**
   - [vercel.com/new](https://vercel.com/new)
   - Import the Git repo that contains this project (e.g. `jarvis`).
   - Root directory: leave default (project root).

2. **Configure project**
   - Framework Preset: **Flask** (or leave as detected).
   - Build Command: leave empty (or as set in `vercel.json`).
   - Install Command: leave empty so Vercel uses `vercel.json` (`pip install -r requirements-vercel.txt`).
   - Add the environment variables above.

3. **Deploy**
   - Click **Deploy**.
   - Every push to the connected branch will trigger a new deployment.

### Option B: Vercel CLI

1. **Install and log in**
   ```bash
   npm i -g vercel
   vercel login
   ```

2. **From project root**
   ```bash
   cd /Users/abhishekvyas/jarvis
   vercel
   ```
   - Link to an existing Vercel project or create a new one.
   - Add env vars when prompted or in the dashboard.

3. **Production**
   ```bash
   vercel --prod
   ```

---

## After deploy

- Open the project’s **Vercel URL** (e.g. `https://your-project.vercel.app`).
- You should see the Content Generator home page.
- Test: Generate, Save, Voice, Drafts, History.

If something fails, check **Vercel Dashboard → Deployments → [latest] → Logs / Functions**.

---

## Limits and behavior

- **SQLite:** `braingym.db` is read from the deployment. Writes work on Vercel’s runtime; for heavy or persistent usage, consider a hosted DB.
- **Size:** Total deployment (code + `braingym.db` + deps) must stay under Vercel’s limit (e.g. 250 MB for the bundle). Use `.vercelignore` to keep the repo lean.
- **Secrets:** Never commit API keys; use only Vercel environment variables.

---

## Quick checklist

- [ ] `braingym.db` is in the repo (or app points to an external DB)
- [ ] `ANTHROPIC_API_KEY` set in Vercel
- [ ] `FIRECRAWL_API_KEY` set in Vercel (if you use URL save)
- [ ] Repo connected to Vercel (or `vercel` run from `jarvis`)
- [ ] Deploy and open the Vercel URL to confirm
