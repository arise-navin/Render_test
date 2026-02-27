# 🚀 Render Deployment Guide — ServiceNow AI Copilot

## What Changed: MySQL → PostgreSQL

| Area | MySQL (before) | PostgreSQL (after) |
|---|---|---|
| **Driver** | `mysql-connector-python` | `psycopg2-binary` |
| **Connection** | `mysql.connector.connect(host=…)` | `psycopg2.connect(DATABASE_URL)` |
| **Dict cursor** | `cursor(dictionary=True)` | `cursor(cursor_factory=RealDictCursor)` |
| **Table quotes** | Backticks `` `table` `` | Double quotes `"table"` |
| **Upsert** | `REPLACE INTO` | `INSERT … ON CONFLICT DO UPDATE` |
| **Dedup key** | `ON DUPLICATE KEY UPDATE` | `ON CONFLICT (col) DO UPDATE SET` |
| **Column list** | `SHOW COLUMNS FROM` | `information_schema.columns` |
| **Column type** | `LONGTEXT` | `TEXT` |
| **Charset** | `CHARACTER SET utf8mb4 …` | *(removed — Postgres defaults to UTF-8)* |
| **Connection string** | Hard-coded host/user/pass | `DATABASE_URL` environment variable |

---

## Step-by-Step Deployment

### Step 1 — Push your code to GitHub
Render deploys from Git. Push the entire project folder to a new GitHub repository.

```bash
git init
git add .
git commit -m "Initial commit — Postgres ready"
git remote add origin https://github.com/YOUR_USER/YOUR_REPO.git
git push -u origin main
```

> **Alternative (no Git):** Render also accepts a public ZIP URL. Host the zip on GitHub Releases or any public URL, then use *Deploy from URL* in the Render dashboard.

---

### Step 2 — Create a PostgreSQL Database on Render

1. Go to [render.com/dashboard](https://dashboard.render.com) → **New → PostgreSQL**
2. Fill in:
   - **Name:** `sn-copilot-db`
   - **Database Name:** `sn_health`
   - **Region:** choose closest to your users
   - **Plan:** Free *(90-day free tier, 1 GB)*
3. Click **Create Database**
4. After ~30 seconds, click into the database and copy the **Internal Database URL**
   - It looks like: `postgres://user:password@host/sn_health`
   - Keep this — you'll paste it in Step 4

---

### Step 3 — Create the Web Service

1. Render Dashboard → **New → Web Service**
2. Connect your GitHub repo (or use Deploy from URL)
3. Set the following:

   | Field | Value |
   |---|---|
   | **Name** | `servicenow-ai-copilot` |
   | **Runtime** | Python 3 |
   | **Build Command** | `pip install -r requirements.txt` |
   | **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
   | **Plan** | Free (or Starter for always-on) |

4. Click **Create Web Service** (don't start it yet)

> **Shortcut:** If you push the `render.yaml` file to your repo, Render can auto-configure both the database and web service via **New → Blueprint**.

---

### Step 4 — Set Environment Variables

In your web service → **Environment** tab, add these variables:

| Variable | Value | Notes |
|---|---|---|
| `DATABASE_URL` | `postgres://user:pass@host/sn_health` | Paste from Step 2 |
| `SN_INSTANCE` | `https://your-instance.service-now.com` | Your SN instance URL |
| `SN_USERNAME` | `admin` | ServiceNow username |
| `SN_PASSWORD` | `your-password` | ServiceNow password |
| `NVIDIA_API_KEY` | `nvapi-…` | Your NVIDIA LLM API key |

> **If using render.yaml Blueprint:** `DATABASE_URL` is wired automatically.
> You only need to set the four manual variables above.

---

### Step 5 — Deploy

1. Click **Manual Deploy → Deploy latest commit**
2. Watch the build logs. A successful build looks like:

   ```
   ==> Installing dependencies
   Successfully installed fastapi psycopg2-binary uvicorn …
   ==> Starting service
   🚀 ServiceNow AI Copilot Started
   ✓ Delta Sync started → https://your-instance.service-now.com (every 30s)
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://0.0.0.0:10000
   ```

3. Your live API endpoint will be:
   ```
   https://servicenow-ai-copilot.onrender.com
   ```

---

### Step 6 — Verify

| URL | Expected response |
|---|---|
| `/health` | `{"status": "running", "version": "2.0"}` |
| `/docs` | Interactive Swagger UI |
| `/sync/status` | Live sync progress JSON |
| `/agent/architecture` | Architecture analysis JSON |

---

## Troubleshooting

### `RuntimeError: DATABASE_URL is not set`
→ Go to Render → your web service → **Environment** and add `DATABASE_URL`

### `psycopg2.OperationalError: SSL connection required`
→ Already handled — the `get_conn()` function passes `sslmode="require"` automatically

### `relation "table_name" does not exist`
→ Normal on first run. Tables are auto-created when the first sync cycle runs. Wait ~60 seconds for the full sync to complete.

### Service sleeps after 15 minutes (free plan)
→ Upgrade to the **Starter plan ($7/mo)** for an always-on service.
   Or ping `/health` every 5 minutes via an external cron (e.g. cron-job.org)

### `401 Unauthorized` from ServiceNow
→ Check `SN_USERNAME` and `SN_PASSWORD` in Render → Environment

### Build fails: `No module named 'psycopg2'`
→ Make sure `requirements.txt` contains `psycopg2-binary` (not just `psycopg2`)

---

## Environment Variables Reference (complete list)

```
DATABASE_URL    = postgres://user:pass@host:5432/sn_health   # Render injects this
SN_INSTANCE     = https://your-instance.service-now.com
SN_USERNAME     = admin
SN_PASSWORD     = your_servicenow_password
NVIDIA_API_KEY  = nvapi-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```
