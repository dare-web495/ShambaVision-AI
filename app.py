import base64
import html
import io
import json
import re
import secrets
import time
from datetime import datetime
from pathlib import Path

import streamlit as st
from PIL import Image

from llm import diagnose

st.set_page_config(page_title="ShambaVision AI", page_icon="🌱", layout="centered")

# ---------- persistence ----------
STATE_DIR = Path("state")
STATE_DIR.mkdir(exist_ok=True)
PREF_KEYS = ["pref_dark", "pref_language", "pref_town"]
RESULT_KEYS = ["result", "thumb", "scanned_at", "scan_crop", "scan_town"]
LANGUAGES = ["English", "Swahili"]


def get_sid():
    """Session ID kept in the URL so it survives a refresh."""
    sid = st.query_params.get("s", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,32}", sid or ""):
        sid = secrets.token_urlsafe(9)
        st.query_params["s"] = sid
    return sid


def cleanup_old(days=7):
    cutoff = time.time() - days * 86400
    for p in STATE_DIR.glob("*.json"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
        except OSError:
            pass


def load_state(sid):
    if st.session_state.get("_loaded"):
        return
    st.session_state["_loaded"] = True
    cleanup_old()
    path = STATE_DIR / f"{sid}.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return
        for key in PREF_KEYS + RESULT_KEYS:
            if key in data:
                st.session_state[key] = data[key]


def save_state(sid):
    data = {k: st.session_state[k] for k in PREF_KEYS + RESULT_KEYS if k in st.session_state}
    if "error" in (data.get("result") or {}):  # don't keep failed diagnoses
        for key in RESULT_KEYS:
            data.pop(key, None)
    try:
        (STATE_DIR / f"{sid}.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


# ---------- theme (CSS lives in the styles/ folder) ----------
def read_css(name):
    text = Path("styles", name).read_text(encoding="utf-8")
    return " ".join(line.strip() for line in text.splitlines() if line.strip())


def inject_theme(dark):
    theme_file = "dark.css" if dark else "light.css"
    st.markdown(
        f"<style>{read_css('base.css')} {read_css(theme_file)}</style>",
        unsafe_allow_html=True,
    )


# ---------- data + helpers ----------
@st.cache_data
def load_json(name):
    return json.loads(Path("data", name).read_text(encoding="utf-8"))


remedies = load_json("remedies.json")
prices = load_json("prices.json")
st.session_state.setdefault("scan_id", 0)


def esc(value):
    """Escape model output before putting it into HTML."""
    return html.escape(str(value or ""))


def render(markup):
    """Render HTML; strip indentation so Markdown doesn't treat it as code."""
    flat = " ".join(line.strip() for line in markup.splitlines())
    st.markdown(flat, unsafe_allow_html=True)


def make_thumb(image_bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img.thumbnail((200, 200))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return base64.b64encode(buf.getvalue()).decode()


def reset():
    for key in RESULT_KEYS:
        st.session_state.pop(key, None)
    st.session_state["scan_id"] += 1  # new widget keys = fresh camera/uploader


# ---------- views ----------
def input_view():
    sid_ = st.session_state["scan_id"]
    render('<div class="page-title">Scan your crop</div>')

    crop = st.selectbox("Which crop?", ["Unknown"] + sorted(remedies.keys()), key=f"crop_{sid_}")
    saved_lang = st.session_state.get("pref_language")
    language = st.radio(
        "Language", LANGUAGES, horizontal=True,
        index=LANGUAGES.index(saved_lang) if saved_lang in LANGUAGES else 0,
        key="language_widget",
    )
    st.session_state["pref_language"] = language

    tab_cam, tab_up = st.tabs(["📷 Camera", "📁 Upload"])
    with tab_cam:
        cam = st.camera_input("Photo of the affected leaf or plant", key=f"cam_{sid_}")
    with tab_up:
        up = st.file_uploader("Choose a photo", type=["jpg", "jpeg", "png", "webp"], key=f"up_{sid_}")

    photo = cam or up
    if photo:
        st.image(photo, width=240)

    if photo and st.button("Diagnose", type="primary", use_container_width=True):
        data = photo.getvalue()
        reference = remedies.get(crop, remedies)
        with st.spinner("Looking at your crop..."):
            result = diagnose(data, crop, language, reference)
        st.session_state["result"] = result
        st.session_state["thumb"] = make_thumb(data)
        st.session_state["scanned_at"] = datetime.now().strftime("%d %b %Y, %H:%M")
        st.session_state["scan_crop"] = crop
        st.rerun()


def results_view():
    result = st.session_state["result"]
    st.button("← Back", on_click=reset)

    if "error" in result:
        st.error(result["error"])
        return

    crop = st.session_state.get("scan_crop", "Unknown")
    crop_label = crop if crop != "Unknown" else (result.get("crop_guess") or "Unknown")
    town = st.session_state.get("scan_town", "")
    where = f" · {esc(town)}" if town else ""

    render(f"""
    <div class="card scan">
      <img src="data:image/jpeg;base64,{st.session_state.get('thumb', '')}">
      <div>
        <div class="scan-title">Field Scan</div>
        <div class="muted">Crop: {esc(crop_label)}{where}<br>{esc(st.session_state.get('scanned_at'))}</div>
      </div>
    </div>
    """)

    render('<div class="page-title">AI DIAGNOSIS RESULTS</div>')

    issues = result.get("possible_issues") or []
    follow_ups = result.get("follow_up_questions") or []
    if issues:
        top = issues[0]
        conf = str(top.get("confidence", "")).lower()
        conf = conf if conf in ("high", "medium", "low") else "low"
        render(f"""
        <div class="card">
          <div class="label">DISEASE / PROBLEM</div>
          <div class="disease">{esc(top.get('name'))}</div>
          <span class="pill {conf}">{conf.title()} confidence</span>
          <div class="label" style="margin-top:10px">CAUSE</div>
          <div>{esc(top.get('cause') or 'Not sure')}</div>
          <div class="muted" style="margin-top:8px">{esc(result.get('summary'))}</div>
        </div>
        """)
        with st.expander("Learn more"):
            st.write(f"**Signs seen in your photo:** {top.get('symptoms_seen', '')}")
            if follow_ups:
                st.write("**Questions to check:**")
                for q in follow_ups:
                    st.write(f"- {q}")

        if len(issues) > 1:
            others = "".join(
                f'<div class="sol"><span class="sol-name">{esc(i.get("name"))}</span> '
                f'<span class="muted">({esc(i.get("confidence"))})</span></div>'
                for i in issues[1:]
            )
            render(f'<div class="card"><div class="section">Other possibilities</div>{others}</div>')
    else:
        render(f'<div class="card">{esc(result.get("summary"))}</div>')

    solutions = result.get("organic_remedies") or []
    if solutions:
        items = "".join(
            f'<div class="sol"><div class="sol-name">{n}. {esc(r.get("name"))}</div>'
            f'<div class="muted">{esc(r.get("how_to_use"))}</div></div>'
            for n, r in enumerate(solutions, 1)
        )
        render(f'<div class="card"><div class="section">Recommended organic remedies</div>{items}</div>')

        where_items = "".join(
            f'<div class="sol"><div class="sol-name">{esc(r.get("name"))}</div>'
            f'<div class="muted">{esc(r.get("where_to_find"))}</div></div>'
            for r in solutions
        )
        price_key = crop if crop in prices else str(result.get("crop_guess", "")).title()
        price_html = ""
        if price_key in prices:
            p = prices[price_key]
            price_html = (
                f'<div class="sol"><div class="sol-name">Market price for {esc(price_key)} (sample data)</div>'
                f'<div class="muted">KES {p["low_kes"]} to {p["high_kes"]} per {esc(p["unit"])}</div></div>'
            )
        render(f"""
        <div class="card">
          <div class="section">Local availability</div>
          {where_items}{price_html}
          <div class="muted" style="margin-top:8px">Stock and shop prices vary. Ask your local agrovet.</div>
        </div>
        """)

    officer = result.get("see_extension_officer") or {}
    if officer.get("needed"):
        render(f"""
        <div class="card warn">
          <div class="label">PLEASE SEE AN EXTENSION OFFICER</div>
          <div>{esc(officer.get('reason'))}</div>
        </div>
        """)

    render('<div class="muted">This is a guide, not a final diagnosis. Confirm serious problems with your local extension officer.</div>')
    st.write("")
    st.button("Scan another crop", type="primary", use_container_width=True, on_click=reset, key="again")


# ---------- main ----------
sid = get_sid()
load_state(sid)

# the toggle's value is already in session_state at the start of a rerun
dark = st.session_state.get("dark_widget", st.session_state.get("pref_dark", False))
inject_theme(dark)

render('<div class="app-bar">🌱 SHAMBAVISION AI ASSISTANT</div>')
dark_now = st.toggle("🌙 Dark mode", value=dark, key="dark_widget")
st.session_state["pref_dark"] = dark_now

if "result" in st.session_state:
    results_view()
else:
    input_view()

save_state(sid)