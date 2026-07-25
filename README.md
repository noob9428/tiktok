# TikTok Trend Creator

A mobile-friendly Streamlit application that:

- fetches current UK Google Trends as a discovery signal;
- accepts trend names copied from TikTok Creative Center;
- scores and stores trends;
- generates original TikTok hooks, captions, hashtags and shot lists;
- creates a 9:16 planning preview with clear top/bottom safe areas;
- provides an approval queue;
- optionally uses the OpenAI API;
- does **not** scrape TikTok or publish without creator review.

## Important limitation

TikTok does not provide an unrestricted ordinary-account API for downloading a complete live list of every trend. This starter therefore uses a compliant hybrid workflow:

1. Live UK Google Trends.
2. Manual or CSV input from TikTok Creative Center.
3. Automatic idea generation.
4. Human approval.

TikTok Direct Post can be added later after TikTok developer registration, OAuth, relevant Content Posting API access, creator-facing controls and app review.

## Files

- `app.py` — the Streamlit app.
- `requirements.txt` — Python packages.
- `.streamlit/config.toml` — mobile-friendly Streamlit settings.
- `.streamlit/secrets.example.toml` — optional API key template.
- `data/sample_trends.csv` — sample import format.
- `data/` — SQLite database is created here automatically.

## Deploy from an iPhone using GitHub + Streamlit Community Cloud

### 1. Create a GitHub repository

Create a new private repository, for example:

`tiktok-trend-creator`

Upload every file and folder from this package. GitHub may hide `.streamlit` on some upload screens. If necessary, create the folder and files using GitHub's **Add file → Create new file** option:

`.streamlit/config.toml`

and:

`.streamlit/secrets.example.toml`

### 2. Deploy to Streamlit Community Cloud

1. Sign in to Streamlit Community Cloud using GitHub.
2. Select **Create app**.
3. Choose the repository.
4. Set the main file to `app.py`.
5. Deploy.

### 3. Optional AI generation

The app works without an API key using its built-in template generator.

For AI-generated ideas, open the Streamlit app settings and add:

```toml
OPENAI_API_KEY = "your-key-here"
OPENAI_MODEL = "gpt-5-mini"
```

Do not put a real API key in GitHub.

### 4. Use on iPhone

Open the deployed URL in Safari and choose:

**Share → Add to Home Screen**

## Daily workflow

1. Open **Scan trends**.
2. Press **Fetch current UK trends**.
3. Open TikTok Creative Center and filter to the UK.
4. Paste only trends that suit your account.
5. Open **Create post**.
6. Generate and edit a post.
7. Download the preview or save it to the queue.
8. Approve the post.
9. Create/upload the finished media and add the licensed sound inside TikTok.
10. Mark it posted.

## CSV format

```csv
trend,source,traffic,score,notes
Example trend,TikTok Creative Center,250K,85,Good match for British humour
```

Only the `trend` column is required.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

On Windows:

```powershell
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Next upgrade

A later version can include:

- TikTok OAuth;
- Content Posting API upload/draft flow;
- post-performance entry and learning;
- scheduled trend scans;
- automatic video assembly from user-owned media;
- duplicate-topic detection.
