import json
from pathlib import Path

import streamlit as st

from llm import diagnose

st.set_page_config(page_title="ShambaVision AI", page_icon="🌱")


@st.cache_data
def load_json(name):
    return json.loads(Path("data", name).read_text(encoding="utf-8"))


remedies = load_json("remedies.json")
prices = load_json("prices.json")

st.title("🌱 ShambaVision AI")
st.caption("Take or upload a photo of your crop to get possible causes and organic remedies.")

crop = st.selectbox("Which crop?", ["Unknown"] + sorted(remedies.keys()))
language = st.radio("Language", ["English", "Swahili"], horizontal=True)

tab_cam, tab_up = st.tabs(["📷 Camera", "📁 Upload"])
with tab_cam:
    cam = st.camera_input("Photo of the affected leaf or plant")
with tab_up:
    up = st.file_uploader("Choose a photo", type=["jpg", "jpeg", "png", "webp"])

photo = cam or up
if photo:
    st.image(photo, width=300)

if photo and st.button("Diagnose", type="primary"):
    reference = remedies.get(crop, remedies)  # unknown crop: send everything
    with st.spinner("Looking at your crop..."):
        st.session_state["result"] = diagnose(photo.getvalue(), crop, language, reference)
        st.session_state["crop"] = crop

result = st.session_state.get("result")
if result:
    if "error" in result:
        st.error(result["error"])
    else:
        st.subheader("What I see")
        st.write(result.get("summary", ""))

        st.subheader("Possible issues")
        for issue in result.get("possible_issues", []):
            st.markdown(f"**{issue.get('name')}**: confidence {issue.get('confidence')}")
            st.caption(issue.get("symptoms_seen", ""))

        st.subheader("Organic remedies")
        for r in result.get("organic_remedies", []):
            with st.expander(r.get("name", "Remedy")):
                st.write(f"**How to use:** {r.get('how_to_use', '')}")
                st.write(f"**Where to find:** {r.get('where_to_find', '')}")

        questions = result.get("follow_up_questions", [])
        if questions:
            st.subheader("Questions to check")
            for q in questions:
                st.write(f"- {q}")

        officer = result.get("see_extension_officer", {})
        if officer.get("needed"):
            st.warning(f"Please see an extension officer: {officer.get('reason', '')}")

        # Prices come from our own data file, never from the model
        price_key = st.session_state.get("crop", "Unknown")
        if price_key not in prices:
            price_key = str(result.get("crop_guess", "")).title()
        if price_key in prices:
            p = prices[price_key]
            st.subheader("Market price (sample data)")
            st.write(f"{price_key}: KES {p['low_kes']} to {p['high_kes']} per {p['unit']}")

    st.info("This is a guide, not a final diagnosis. Confirm serious problems with your local extension officer.")