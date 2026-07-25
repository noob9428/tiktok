import csv
import io
import json
import os
import random
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus
import xml.etree.ElementTree as ET

import pandas as pd
import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont

APP_DIR = Path(__file__).resolve().parent
DATA_DIR = APP_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "tiktok_creator.db"

st.set_page_config(
    page_title="TikTok Trend Creator",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; padding-bottom: 4rem; max-width: 1180px;}
div[data-testid="stMetric"] {border:1px solid rgba(128,128,128,.25); padding:12px; border-radius:14px;}
.stButton button {border-radius:12px; min-height:44px;}
textarea, input {font-size:16px !important;}
.safe-card {border:1px solid rgba(128,128,128,.25); border-radius:16px; padding:16px; margin:8px 0;}
.small {opacity:.72;font-size:.9rem;}
</style>
""", unsafe_allow_html=True)

DEFAULT_NICHES = [
    "British humour",
    "Relatable everyday life",
    "Technology and AI",
    "Parenting",
    "Cars and DIY",
    "Light political satire",
]

HOOKS = [
    "Nobody warned us that {trend} would become this...",
    "POV: Britain discovers {trend}",
    "The most British response to {trend}",
    "Me pretending I understand {trend}",
    "This is why {trend} is suddenly everywhere",
    "When {trend} reaches your group chat",
]

ANGLES = [
    "Use a quick expectation-versus-reality joke.",
    "Turn it into a dry British reaction with one sharp punchline.",
    "Use a three-beat setup: normal, strange, absurd.",
    "Frame it as a mock public-service announcement.",
    "Make the viewer choose between two ridiculous options.",
    "Use a visual reveal in the final two seconds.",
]

CTAS = [
    "Be honest—would you try this?",
    "Tell me I’m not the only one.",
    "Which side are you on?",
    "Send this to the person who needs to see it.",
    "What happens next?",
]

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def initialise_db():
    with db() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS trends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trend TEXT NOT NULL,
            source TEXT NOT NULL,
            traffic TEXT,
            score REAL NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trend TEXT NOT NULL,
            niche TEXT NOT NULL,
            hook TEXT NOT NULL,
            concept TEXT NOT NULL,
            onscreen_text TEXT NOT NULL,
            caption TEXT NOT NULL,
            hashtags TEXT NOT NULL,
            shot_list TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Draft',
            created_at TEXT NOT NULL
        )
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """)

def get_setting(key, default=""):
    with db() as con:
        row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default

def set_setting(key, value):
    with db() as con:
        con.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )

def clean_text(value, limit=180):
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value[:limit]

def traffic_number(text):
    text = str(text or "").replace(",", "").strip().upper()
    match = re.search(r"([\d.]+)\s*([KMB]?)", text)
    if not match:
        return 0
    value = float(match.group(1))
    unit = match.group(2)
    return value * {"":1, "K":1_000, "M":1_000_000, "B":1_000_000_000}.get(unit, 1)

def trend_score(trend, traffic="", source="Manual"):
    base = 45
    amount = traffic_number(traffic)
    if amount:
        base += min(35, max(0, (len(str(int(amount))) - 3) * 7))
    if source == "Google Trends UK":
        base += 10
    words = len(str(trend).split())
    if 2 <= words <= 6:
        base += 5
    return float(min(100, base + random.randint(-4, 7)))

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_google_trends():
    url = "https://trends.google.com/trending/rss?geo=GB"
    response = requests.get(url, timeout=15, headers={"User-Agent":"Mozilla/5.0"})
    response.raise_for_status()
    root = ET.fromstring(response.content)
    rows = []
    ns = {"ht": "https://trends.google.com/trending/rss"}
    for item in root.findall(".//item")[:20]:
        title = item.findtext("title", default="")
        traffic = item.findtext("ht:approx_traffic", default="", namespaces=ns)
        news_title = item.findtext("ht:news_item/ht:news_item_title", default="", namespaces=ns)
        rows.append({
            "trend": clean_text(title),
            "source": "Google Trends UK",
            "traffic": clean_text(traffic, 40),
            "score": trend_score(title, traffic, "Google Trends UK"),
            "notes": clean_text(news_title),
        })
    return rows

def save_trends(rows):
    now = datetime.now(timezone.utc).isoformat()
    with db() as con:
        for row in rows:
            trend = clean_text(row.get("trend"))
            if not trend:
                continue
            con.execute(
                "INSERT INTO trends(trend,source,traffic,score,notes,created_at) VALUES(?,?,?,?,?,?)",
                (
                    trend,
                    clean_text(row.get("source", "Manual"), 60),
                    clean_text(row.get("traffic", ""), 40),
                    float(row.get("score") or trend_score(trend)),
                    clean_text(row.get("notes", ""), 300),
                    now,
                ),
            )

def load_trends(limit=100):
    with db() as con:
        rows = con.execute(
            "SELECT * FROM trends ORDER BY created_at DESC, score DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return pd.DataFrame([dict(r) for r in rows])

def fallback_post(trend, niche, tone, duration):
    hook = random.choice(HOOKS).format(trend=trend)
    angle = random.choice(ANGLES)
    cta = random.choice(CTAS)
    onscreen = f"{hook}\n\nWAIT FOR IT…"
    concept = (
        f"Create a {duration}-second {tone.lower()} post about “{trend}” for a UK audience. "
        f"{angle} Keep the joke original and understandable even without sound."
    )
    caption = f"{hook} {cta}"
    tags = [
        "#fyp", "#uktiktok", "#trending", "#britishhumour",
        "#" + re.sub(r"[^a-zA-Z0-9]", "", trend.lower())[:24]
    ]
    shot_list = (
        f"0–2s: Show the hook in large text.\n"
        f"2–{max(4, duration-3)}s: Deliver the setup using one clear visual.\n"
        f"{max(4, duration-3)}–{duration}s: Reveal the punchline and add “{cta}”"
    )
    return {
        "hook": hook,
        "concept": concept,
        "onscreen_text": onscreen,
        "caption": caption,
        "hashtags": " ".join(dict.fromkeys(tags)),
        "shot_list": shot_list,
    }

def ai_post(trend, niche, tone, duration, audience, avoid):
    api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    model = st.secrets.get("OPENAI_MODEL", "gpt-5-mini")
    if not api_key:
        return fallback_post(trend, niche, tone, duration), "Template generator used (no API key configured)."
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        prompt = f"""
Create one original TikTok post concept.
Trend: {trend}
Niche: {niche}
Tone: {tone}
Audience: {audience}
Duration: {duration} seconds
Avoid: {avoid or "misinformation, cruelty, harassment, copyrighted lyrics, impersonation, unsafe claims"}
Use British English. Keep top and bottom 20% visually clear. Do not claim that a trend fact is verified.
Return valid JSON with exactly these string keys:
hook, concept, onscreen_text, caption, hashtags, shot_list
The hashtags value must contain 4–6 hashtags. The shot list must contain timestamps.
"""
        response = client.responses.create(model=model, input=prompt)
        text = response.output_text.strip()
        text = re.sub(r"^```json\s*|\s*```$", "", text, flags=re.I | re.S)
        result = json.loads(text)
        required = ["hook","concept","onscreen_text","caption","hashtags","shot_list"]
        if not all(k in result and isinstance(result[k], str) for k in required):
            raise ValueError("Incomplete AI response")
        return result, f"AI generator used: {model}"
    except Exception as exc:
        return fallback_post(trend, niche, tone, duration), f"AI unavailable; template fallback used. ({type(exc).__name__})"

def save_post(trend, niche, post):
    now = datetime.now(timezone.utc).isoformat()
    with db() as con:
        con.execute("""
        INSERT INTO posts(trend,niche,hook,concept,onscreen_text,caption,hashtags,shot_list,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?)
        """, (
            trend, niche, post["hook"], post["concept"], post["onscreen_text"],
            post["caption"], post["hashtags"], post["shot_list"], "Draft", now
        ))

def load_posts():
    with db() as con:
        rows = con.execute("SELECT * FROM posts ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]

def update_post_status(post_id, status):
    with db() as con:
        con.execute("UPDATE posts SET status=? WHERE id=?", (status, post_id))

def delete_post(post_id):
    with db() as con:
        con.execute("DELETE FROM posts WHERE id=?", (post_id,))

def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()

def wrap(draw, text, fnt, width):
    words = text.split()
    lines, line = [], ""
    for word in words:
        trial = (line + " " + word).strip()
        if draw.textbbox((0,0), trial, font=fnt)[2] <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines

def make_preview(post):
    image = Image.new("RGB", (1080, 1920), (18, 18, 22))
    draw = ImageDraw.Draw(image)
    title_font = font(68, bold=True)
    body_font = font(38)
    small_font = font(30)
    # Keep roughly 20% top and bottom clear.
    safe_top, safe_bottom = 384, 1536
    draw.rounded_rectangle((70, safe_top, 1010, safe_bottom), radius=42, fill=(245,245,245))
    y = safe_top + 90
    for line in wrap(draw, post["hook"], title_font, 800)[:5]:
        draw.text((140, y), line, font=title_font, fill=(15,15,18))
        y += 86
    y += 35
    for line in wrap(draw, post["concept"], body_font, 800)[:9]:
        draw.text((140, y), line, font=body_font, fill=(55,55,62))
        y += 54
    draw.text((140, safe_bottom - 110), "20% TOP + BOTTOM SAFE AREA", font=small_font, fill=(100,100,108))
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()

initialise_db()

st.title("TikTok Trend Creator")
st.caption("Find ideas, generate original TikTok concepts and approve them from your phone.")

tabs = st.tabs(["📊 Dashboard", "🔎 Scan trends", "✨ Create post", "✅ Approval queue", "⚙️ Settings"])

with tabs[0]:
    trends_df = load_trends()
    posts = load_posts()
    approved = sum(1 for p in posts if p["status"] == "Approved")
    c1, c2, c3 = st.columns(3)
    c1.metric("Saved trends", len(trends_df))
    c2.metric("Post ideas", len(posts))
    c3.metric("Approved", approved)
    st.subheader("Best saved trends")
    if trends_df.empty:
        st.info("Open **Scan trends** and fetch UK trends, or paste TikTok trends manually.")
    else:
        display = trends_df[["trend","source","traffic","score"]].head(10).copy()
        display["score"] = display["score"].round(0).astype(int)
        st.dataframe(display, use_container_width=True, hide_index=True)
    st.markdown("""
    <div class="safe-card">
    <b>Recommended workflow</b><br>
    1. Fetch UK trends. 2. Add relevant TikTok Creative Center trends.
    3. Generate ideas. 4. Approve only the strongest. 5. Add the chosen TikTok sound inside TikTok.
    </div>
    """, unsafe_allow_html=True)

with tabs[1]:
    st.subheader("Live UK trend scan")
    st.write("This uses Google Trends UK as a live discovery signal. It does not scrape TikTok.")
    if st.button("Fetch current UK trends", type="primary", use_container_width=True):
        try:
            rows = fetch_google_trends()
            save_trends(rows)
            st.success(f"Saved {len(rows)} current UK trends.")
            st.rerun()
        except Exception as exc:
            st.error(f"Trend feed could not be loaded: {exc}")

    st.divider()
    st.subheader("Add TikTok trends")
    st.write("Open TikTok Creative Center, filter for the UK, then paste trend names here—one per line.")
    st.link_button(
        "Open TikTok Creative Center",
        "https://ads.tiktok.com/business/creativecenter/trends/pc/en",
        use_container_width=True,
    )
    pasted = st.text_area(
        "Trend names",
        placeholder="Example trend one\nExample trend two\n#ExampleHashtag",
        height=150,
    )
    notes = st.text_input("Optional notes", placeholder="Why these trends fit your account")
    if st.button("Save pasted trends", use_container_width=True):
        rows = []
        for line in pasted.splitlines():
            trend = clean_text(line)
            if trend:
                rows.append({
                    "trend": trend,
                    "source": "TikTok Creative Center (manual)",
                    "traffic": "",
                    "score": trend_score(trend, "", "Manual") + 8,
                    "notes": notes,
                })
        if rows:
            save_trends(rows)
            st.success(f"Saved {len(rows)} TikTok trends.")
            st.rerun()
        else:
            st.warning("Paste at least one trend.")

    uploaded = st.file_uploader("Or upload a CSV with a column named trend", type=["csv"])
    if uploaded:
        try:
            frame = pd.read_csv(uploaded)
            if "trend" not in frame.columns:
                st.error("CSV must contain a column named trend.")
            else:
                rows = []
                for _, row in frame.iterrows():
                    trend = clean_text(row.get("trend"))
                    rows.append({
                        "trend": trend,
                        "source": clean_text(row.get("source", "CSV import"), 60),
                        "traffic": clean_text(row.get("traffic", ""), 40),
                        "score": float(row.get("score", trend_score(trend))),
                        "notes": clean_text(row.get("notes", ""), 300),
                    })
                if st.button("Import CSV trends", use_container_width=True):
                    save_trends(rows)
                    st.success(f"Imported {len(rows)} trends.")
                    st.rerun()
        except Exception as exc:
            st.error(f"Could not read CSV: {exc}")

    trends_df = load_trends()
    if not trends_df.empty:
        st.subheader("Saved trend bank")
        st.dataframe(
            trends_df[["trend","source","traffic","score","notes"]].head(50),
            use_container_width=True,
            hide_index=True,
        )

with tabs[2]:
    st.subheader("Generate a post concept")
    trends_df = load_trends()
    trend_options = trends_df["trend"].drop_duplicates().tolist() if not trends_df.empty else []
    mode = st.radio("Trend input", ["Choose saved trend", "Type a trend"], horizontal=True)
    if mode == "Choose saved trend" and trend_options:
        trend = st.selectbox("Trend", trend_options)
    else:
        trend = st.text_input("Trend", placeholder="Enter a trend, topic or hashtag")

    col1, col2 = st.columns(2)
    niche_default = get_setting("niche", DEFAULT_NICHES[0])
    niche_options = list(dict.fromkeys([niche_default] + DEFAULT_NICHES))
    niche = col1.selectbox("Niche", niche_options)
    tone = col2.selectbox("Tone", ["Funny", "Dry British satire", "Curious", "Helpful", "Surprising"])
    audience = col1.text_input("Audience", get_setting("audience", "UK adults aged 25–55"))
    duration = col2.slider("Length in seconds", 6, 30, 12)
    avoid = st.text_input("Avoid", get_setting("avoid", "party-political claims, cruelty, copyrighted lyrics"))

    if st.button("Generate post", type="primary", use_container_width=True, disabled=not bool(trend.strip())):
        post, generator_note = ai_post(trend.strip(), niche, tone, duration, audience, avoid)
        st.session_state["generated_post"] = post
        st.session_state["generated_meta"] = {"trend":trend.strip(), "niche":niche, "note":generator_note}

    if "generated_post" in st.session_state:
        post = st.session_state["generated_post"]
        meta = st.session_state["generated_meta"]
        st.caption(meta["note"])
        st.text_input("Hook", value=post["hook"], key="edit_hook")
        st.text_area("Concept", value=post["concept"], key="edit_concept")
        st.text_area("On-screen text", value=post["onscreen_text"], key="edit_text")
        st.text_area("Caption", value=post["caption"], key="edit_caption")
        st.text_input("Hashtags", value=post["hashtags"], key="edit_hashtags")
        st.text_area("Shot list", value=post["shot_list"], key="edit_shots")

        edited = {
            "hook": st.session_state["edit_hook"],
            "concept": st.session_state["edit_concept"],
            "onscreen_text": st.session_state["edit_text"],
            "caption": st.session_state["edit_caption"],
            "hashtags": st.session_state["edit_hashtags"],
            "shot_list": st.session_state["edit_shots"],
        }
        preview = make_preview(edited)
        st.image(preview, caption="9:16 planning preview with safe areas", use_container_width=True)
        st.download_button(
            "Download planning preview PNG",
            data=preview,
            file_name="tiktok_post_preview.png",
            mime="image/png",
            use_container_width=True,
        )
        if st.button("Save to approval queue", use_container_width=True):
            save_post(meta["trend"], meta["niche"], edited)
            st.success("Saved to the approval queue.")

with tabs[3]:
    st.subheader("Approval queue")
    posts = load_posts()
    if not posts:
        st.info("No posts saved yet.")
    statuses = ["All", "Draft", "Approved", "Rejected", "Posted"]
    status_filter = st.selectbox("Show", statuses)
    for post in posts:
        if status_filter != "All" and post["status"] != status_filter:
            continue
        with st.expander(f'{post["status"]} · {post["trend"]} · {post["hook"][:55]}'):
            st.markdown(f"**Niche:** {post['niche']}")
            st.markdown(f"**Concept:** {post['concept']}")
            st.markdown(f"**On-screen text:**\n\n{post['onscreen_text']}")
            st.markdown(f"**Caption:** {post['caption']}")
            st.markdown(f"**Hashtags:** {post['hashtags']}")
            st.markdown(f"**Shot list:**\n\n{post['shot_list']}")
            export_text = (
                f"HOOK\n{post['hook']}\n\nCONCEPT\n{post['concept']}\n\n"
                f"ON-SCREEN TEXT\n{post['onscreen_text']}\n\nCAPTION\n{post['caption']}\n\n"
                f"HASHTAGS\n{post['hashtags']}\n\nSHOT LIST\n{post['shot_list']}\n"
            )
            st.download_button(
                "Download post plan",
                export_text,
                file_name=f"tiktok_post_{post['id']}.txt",
                key=f"dl_{post['id']}",
                use_container_width=True,
            )
            a, b, c, d = st.columns(4)
            if a.button("Approve", key=f"a_{post['id']}"):
                update_post_status(post["id"], "Approved"); st.rerun()
            if b.button("Reject", key=f"r_{post['id']}"):
                update_post_status(post["id"], "Rejected"); st.rerun()
            if c.button("Mark posted", key=f"p_{post['id']}"):
                update_post_status(post["id"], "Posted"); st.rerun()
            if d.button("Delete", key=f"d_{post['id']}"):
                delete_post(post["id"]); st.rerun()

with tabs[4]:
    st.subheader("Settings")
    saved_niche = st.text_input("Default niche", get_setting("niche", "British humour"))
    saved_audience = st.text_input("Default audience", get_setting("audience", "UK adults aged 25–55"))
    saved_avoid = st.text_input("Default avoid list", get_setting("avoid", "party-political claims, cruelty, copyrighted lyrics"))
    if st.button("Save settings", use_container_width=True):
        set_setting("niche", saved_niche)
        set_setting("audience", saved_audience)
        set_setting("avoid", saved_avoid)
        st.success("Settings saved.")

    st.divider()
    st.markdown("### Optional AI setup")
    st.code('OPENAI_API_KEY = "your-key-here"\nOPENAI_MODEL = "gpt-5-mini"', language="toml")
    st.caption("Place these values in Streamlit Community Cloud → App settings → Secrets. Never commit API keys to GitHub.")

    st.markdown("### TikTok publishing")
    st.warning(
        "Direct automatic public posting is intentionally not enabled in this starter. "
        "TikTok app registration, OAuth, Content Posting API scopes, creator controls and app review are required."
    )
