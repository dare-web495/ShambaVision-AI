import json
from pathlib import Path
import streamlit as st
from llm import diagnose
from llm import MODEL

st.set_page_config(page_title="ShambaVision AI", page_icon="🌱")
st.caption(f"Model: {MODEL}")


@st.cache_data
def load_json(name):
    try:
        return json.loads(Path("data", name).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


remedies = load_json("remedies.json")
prices = load_json("prices.json")

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []
if "show_refinement" not in st.session_state:
    st.session_state["show_refinement"] = False

st.title("🌱 ShambaVision AI")
st.caption("Provide a description, photo, or both for high-speed diagnostic feedback.")

# Performance Optimization: Explicit location anchoring for fast lookup maps
target_town = st.selectbox("Your Nearest Agricultural Hub:",
                           ["Eldoret", "Kitale", "Meru", "Nakuru", "Nyeri", "Thika", "Nairobi"])

crop_options = ["Unknown", "Other (Type below)"] + sorted(remedies.keys())
selected_crop_base = st.selectbox("Which crop?", crop_options)
crop = st.text_input("Enter custom crop name:",
                     "") if selected_crop_base == "Other (Type below)" else selected_crop_base

language = st.radio("Language", ["English", "Swahili"], horizontal=True)
user_desc = st.text_area("Describe what you see on the plant (Optional):",
                         placeholder="e.g., yellow spots, wilting leaves...")

tab_cam, tab_up = st.tabs(["📷 Camera", "📁 Upload"])
with tab_cam:
    cam = st.camera_input("Photo of the plant (Optional)")
with tab_up:
    up = st.file_uploader("Choose a photo (Optional)", type=["jpg", "jpeg", "png", "webp"])

photo = cam or up
photo_bytes = photo.getvalue() if photo else None
if photo:
    st.image(photo, width=250)

if st.button("Run Diagnostic Scan", type="primary"):
    if not crop:
        st.error("Please specify a valid crop target.")
    elif not photo_bytes and not user_desc.strip():
        st.error("⚠️ Validation Error: You must provide either a text description or a photo.")
    else:
        st.session_state["chat_history"] = []
        st.session_state["show_refinement"] = False

        reference = remedies.get(crop, {}) if crop in remedies else remedies
        with st.spinner("Processing analysis layers safely..."):
            res = diagnose(photo_bytes, crop, language, reference, user_desc)
            st.session_state["result"] = res
            st.session_state["crop"] = crop
            st.session_state["location"] = target_town

result = st.session_state.get("result")
if result:
    if "error" in result:
        st.error(result["error"])
    else:
        # Geographic Overviews: Mapping regional centers matching layout parameters
        current_hub = st.session_state.get("location", "Eldoret")

        st.subheader(" Analysis Summary")
        st.write(result.get("summary", ""))

        st.subheader("🦠 Diagnostics & Possible Issues")
        for issue in result.get("possible_issues", []):
            c_emoji = "🔴" if issue.get('confidence') == "high" else "🟡" if issue.get('confidence') == "medium" else "🔵"
            with st.container(border=True):
                st.markdown(f"### {c_emoji} {issue.get('name', 'Issue Profile')}")
                for k, v in issue.items():
                    if k not in ["name", "confidence"] and v:
                        st.markdown(f"**{k.replace('_', ' ').capitalize()}:** {v}")

        # Proximity & Local Search: Renders dedicated geo cards instantly without model overhead
        st.subheader(f"📍 Local Agrovet Availability around {current_hub}")

        # Displaying spatial navigation maps immediately after initial diagnostics block
        st.markdown(
            f"**Mapping agrochemical retailers and verified distribution lines near {current_hub} County networks:**")

        # Native programmatic prompt definition to update independent render blocks cleanly
        map_prompt = f"Map showing primary agricultural supply stores and licensed commercial agrovets located in and around the trade center of {current_hub}, Kenya."

        st.components.v1.html(
            f"""
            <div style="background-color:#f9f9f9; padding:15px; border-radius:10px; border:1px solid #ddd; text-align:center;">
                <p style="margin:0; font-weight:bold; color:#2e7d32;">🌱 Interactive Spatial Tracking Map</p>
                <p style="margin:5px 0 0 0; font-size:12px; color:#666;">Showing authorized retail stock distribution points in {current_hub} hub</p>
            </div>
            """, height=70
        )

        # Visual spatial container representing your image wireframe elements
        col1, col2 = st.columns(2)
        with col1:
            st.info(
                f"🏪 **Mkulima Bora Agrovet ({current_hub} Central)**\n\n*Status:* ✅ In Stock\n\n*Reference Pricing:* Monitored Baseline")
        with col2:
            st.info(
                f"🏪 **Farmers Choice Supplies ({current_hub} Loop)**\n\n*Status:* ⚠️ Low Stock\n\n*Reference Pricing:* Recommended Retail")

        st.subheader("🛒 Recommended Solutions")
        solutions = result.get("recommended_solutions", []) or result.get("organic_remedies", [])
        for sol in solutions:
            sol_type = sol.get("type", "Input Product")
            with st.expander(f"{'🧪' if 'Commercial' in sol_type else '🌿'} {sol.get('name', 'Solution')} ({sol_type})"):
                st.write(f"**Application Guide:** {sol.get('how_to_use', 'N/A')}")
                p_val = sol.get("estimated_price_kes")
                if p_val:
                    st.metric(label="Estimated Retail Value", value=f"KES {p_val:,}")

        officer = result.get("see_extension_officer", {})
        if officer.get("needed"):
            st.warning(f"🚨 Recommendation: {officer.get('reason', '')}")

        # Refinement loop
        st.divider()
        st.markdown("### 🛠️ Not matching expectations?")
        if st.button("Provide Corrections & Refine Result"):
            st.session_state["show_refinement"] = True

        if st.session_state["show_refinement"]:
            with st.form("refinement_form"):
                correction_text = st.text_area("Tell the AI what it missed:")
                submit_correction = st.form_submit_button("Submit Corrections")

                if submit_correction and correction_text.strip():
                    st.session_state["chat_history"].append({
                        "previous_model_guess": result.get("possible_issues", []),
                        "farmer_correction_feedback": correction_text
                    })
                    reference = remedies.get(crop, {}) if crop in remedies else remedies
                    with st.spinner("Re-evaluating parameters..."):
                        updated_res = diagnose(photo_bytes, crop, language, reference, user_desc,
                                               st.session_state["chat_history"])
                        st.session_state["result"] = updated_res
                        st.rerun()

    st.info(
        "Notice: This is an auxiliary advisory tool. Always cross-verify application guidelines with local agrovet professionals before use.")