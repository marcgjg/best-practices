import streamlit as st
import pandas as pd
import os
from datetime import datetime

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cost of Capital — Best Practices",
    page_icon="📊",
    layout="wide",
)

# ── Constants ─────────────────────────────────────────────────────────────────
DATA_FILE = "best_practices.csv"
COLUMNS = ["id", "category", "practice", "rationale",
           "added_by", "added_on", "last_edited_by", "last_edited_on", "edit_count"]

CATEGORIES = [
    "WACC & Capital Structure",
    "Cost of Equity (CAPM / DDM)",
    "Cost of Debt",
    "Beta Estimation",
    "Risk-Free Rate & Market Premium",
    "Emerging Markets Adjustments",
    "Project-Specific Discount Rates",
    "Other",
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def load_data() -> pd.DataFrame:
    if os.path.exists(DATA_FILE):
        df = pd.read_csv(DATA_FILE)
        # ensure all columns exist (forward-compatibility)
        for col in COLUMNS:
            if col not in df.columns:
                df[col] = ""
        # coerce string columns so NaN floats don't break .str accessor
        for col in ["last_edited_by", "last_edited_on", "added_by", "category", "practice", "rationale"]:
            df[col] = df[col].fillna("").astype(str)
        return df
    # seed with a starter example so the list is never empty
    seed = pd.DataFrame([{
        "id": 1,
        "category": "WACC & Capital Structure",
        "practice": "Use market values (not book values) for capital structure weights.",
        "rationale": "Market values reflect current investor expectations and the true "
                     "economic cost of each financing source.",
        "added_by": "Instructor",
        "added_on": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "last_edited_by": "",
        "last_edited_on": "",
        "edit_count": 0,
    }])
    seed.to_csv(DATA_FILE, index=False)
    return seed


def save_data(df: pd.DataFrame):
    df.to_csv(DATA_FILE, index=False)


def next_id(df: pd.DataFrame) -> int:
    return int(df["id"].max()) + 1 if not df.empty else 1


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def contribution_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    added = df.groupby("added_by").size().reset_index(name="Entries Added")
    edited = (
        df[df["last_edited_by"].astype(str).str.strip().isin(["", "nan"]) == False]
        .groupby("last_edited_by")
        .size()
        .reset_index(name="Entries Edited")
    )
    merged = added.merge(edited, left_on="added_by",
                         right_on="last_edited_by", how="outer")
    merged["Student"] = merged["added_by"].fillna(merged["last_edited_by"])
    merged = merged[["Student", "Entries Added", "Entries Edited"]].fillna(0)
    merged["Entries Added"] = merged["Entries Added"].astype(int)
    merged["Entries Edited"] = merged["Entries Edited"].astype(int)
    merged["Total Contributions"] = merged["Entries Added"] + merged["Entries Edited"]
    merged = merged.sort_values("Total Contributions", ascending=False).reset_index(drop=True)
    merged.index += 1
    return merged


# ── Session state ─────────────────────────────────────────────────────────────
if "student_name" not in st.session_state:
    st.session_state.student_name = ""
if "editing_id" not in st.session_state:
    st.session_state.editing_id = None

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Palette */
    :root {
        --navy:   #1a2e4a;
        --gold:   #c8952a;
        --light:  #f4f6f9;
        --card:   #ffffff;
        --border: #dde3ec;
        --muted:  #6b7a99;
        --green:  #2e7d52;
        --red:    #b94040;
    }

    /* Global */
    [data-testid="stAppViewContainer"] { background: var(--light); }
    [data-testid="stSidebar"] { background: var(--navy); }
    [data-testid="stSidebar"] * { color: #e8edf5 !important; }
    [data-testid="stSidebar"] .stTextInput input {
        background: #253d5e; border-color: #3a5278; color: white !important;
    }
    [data-testid="stSidebar"] label { color: #b0bfd4 !important; }

    /* Header banner */
    .app-header {
        background: linear-gradient(135deg, var(--navy) 0%, #253d5e 100%);
        color: white;
        padding: 1.8rem 2rem 1.4rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
    }
    .app-header h1 { margin: 0; font-size: 1.7rem; font-weight: 700; letter-spacing: .3px; }
    .app-header p  { margin: .3rem 0 0; font-size: .95rem; opacity: .8; }
    .gold-bar { width: 50px; height: 4px; background: var(--gold);
                border-radius: 2px; margin: .6rem 0 .2rem; }

    /* Section titles */
    .section-title {
        font-size: 1.05rem; font-weight: 700; color: var(--navy);
        border-left: 4px solid var(--gold); padding-left: .7rem;
        margin: 1.4rem 0 .8rem;
    }

    /* Best-practice cards */
    .bp-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-left: 5px solid var(--navy);
        border-radius: 8px;
        padding: 1rem 1.2rem;
        margin-bottom: .85rem;
        box-shadow: 0 1px 4px rgba(0,0,0,.05);
    }
    .bp-card:hover { box-shadow: 0 3px 10px rgba(0,0,0,.09); }
    .bp-category {
        display: inline-block;
        background: #e8edf5; color: var(--navy);
        font-size: .72rem; font-weight: 700; letter-spacing: .5px;
        text-transform: uppercase; border-radius: 4px;
        padding: .18rem .55rem; margin-bottom: .5rem;
    }
    .bp-practice { font-size: 1rem; font-weight: 600; color: var(--navy); margin-bottom: .3rem; }
    .bp-rationale { font-size: .88rem; color: #444; line-height: 1.55; margin-bottom: .55rem; }
    .bp-meta { font-size: .76rem; color: var(--muted); }
    .bp-meta span { margin-right: .9rem; }

    /* Contribution table */
    .contrib-table th { background: var(--navy) !important; color: white !important; }

    /* Stat pills */
    .stat-pill {
        background: var(--navy); color: white;
        border-radius: 20px; padding: .3rem .9rem;
        font-size: .82rem; font-weight: 600;
        display: inline-block; margin: .15rem .2rem;
    }

    /* Buttons */
    .stButton > button {
        border-radius: 6px !important;
        font-weight: 600 !important;
    }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — Identity
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 👤 Your Identity")
    name_input = st.text_input(
        "Enter your full name",
        value=st.session_state.student_name,
        placeholder="e.g. Jane Smith",
        key="name_field",
    )
    if name_input:
        st.session_state.student_name = name_input.strip()

    if st.session_state.student_name:
        st.success(f"Logged in as **{st.session_state.student_name}**")
    else:
        st.warning("Enter your name to add or edit entries.")

    st.markdown("---")
    st.markdown("### 📌 About this tool")
    st.markdown(
        "Collaboratively build a best-practice guide for estimating the **cost of capital**. "
        "Add new practices, refine existing ones, and track everyone's contributions."
    )
    st.markdown("---")
    st.markdown("### 🏷️ Categories")
    for c in CATEGORIES:
        st.markdown(f"• {c}")

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-header">
  <h1>📊 Cost of Capital — Best Practices</h1>
  <div class="gold-bar"></div>
  <p>Global Online MBA · Corporate Finance · Collaborative Knowledge Base</p>
</div>
""", unsafe_allow_html=True)

# Load data
df = load_data()

# ══════════════════════════════════════════════════════════════════════════════
# TOP STATS
# ══════════════════════════════════════════════════════════════════════════════
col1, col2, col3 = st.columns(3)
contributors = df["added_by"].nunique()
total = len(df)
edits = int(df["edit_count"].sum())

with col1:
    st.metric("📝 Best Practices", total)
with col2:
    st.metric("🎓 Contributors", contributors)
with col3:
    st.metric("✏️ Total Edits Made", edits)

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs(["📋 Best Practices List", "➕ Add a New Practice", "🏆 Contributions"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — VIEW & EDIT LIST
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    # Filter bar
    fcol1, fcol2 = st.columns([2, 1])
    with fcol1:
        search = st.text_input("🔍 Search practices", placeholder="keyword…")
    with fcol2:
        cat_filter = st.selectbox("Filter by category", ["All"] + CATEGORIES)

    filtered = df.copy()
    if search:
        mask = (
            filtered["practice"].str.contains(search, case=False, na=False) |
            filtered["rationale"].str.contains(search, case=False, na=False)
        )
        filtered = filtered[mask]
    if cat_filter != "All":
        filtered = filtered[filtered["category"] == cat_filter]

    st.markdown(f"<div class='section-title'>Showing {len(filtered)} practice(s)</div>",
                unsafe_allow_html=True)

    if filtered.empty:
        st.info("No practices match your filter. Try a different search term or category.")
    else:
        for _, row in filtered.iterrows():
            edited_line = ""
            if str(row.get("last_edited_by", "")).strip():
                edited_line = (f'<span>✏️ Last edited by <strong>{row["last_edited_by"]}</strong>'
                               f' on {row["last_edited_on"]} '
                               f'(edit #{int(row["edit_count"])})</span>')

            st.markdown(f"""
            <div class="bp-card">
                <div class="bp-category">{row['category']}</div>
                <div class="bp-practice">{row['practice']}</div>
                <div class="bp-rationale">{row['rationale']}</div>
                <div class="bp-meta">
                    <span>➕ Added by <strong>{row['added_by']}</strong> on {row['added_on']}</span>
                    {edited_line}
                </div>
            </div>
            """, unsafe_allow_html=True)

            # Edit button
            if st.session_state.student_name:
                if st.button(f"✏️ Edit this entry", key=f"edit_btn_{row['id']}"):
                    st.session_state.editing_id = int(row["id"])

            # Inline edit form
            if st.session_state.editing_id == int(row["id"]):
                with st.form(key=f"edit_form_{row['id']}"):
                    st.markdown(f"**Editing entry #{row['id']}**")
                    new_cat = st.selectbox("Category", CATEGORIES,
                                          index=CATEGORIES.index(row["category"])
                                          if row["category"] in CATEGORIES else 0)
                    new_practice = st.text_area("Best Practice", value=row["practice"], height=80)
                    new_rationale = st.text_area("Rationale / Explanation",
                                                 value=row["rationale"], height=100)
                    ecol1, ecol2 = st.columns(2)
                    with ecol1:
                        submitted = st.form_submit_button("💾 Save Changes", type="primary")
                    with ecol2:
                        cancelled = st.form_submit_button("Cancel")

                    if submitted:
                        if not new_practice.strip():
                            st.error("The practice field cannot be empty.")
                        else:
                            df = load_data()
                            idx = df[df["id"] == int(row["id"])].index[0]
                            df.at[idx, "category"] = new_cat
                            df.at[idx, "practice"] = new_practice.strip()
                            df.at[idx, "rationale"] = new_rationale.strip()
                            df.at[idx, "last_edited_by"] = st.session_state.student_name
                            df.at[idx, "last_edited_on"] = now_str()
                            df.at[idx, "edit_count"] = int(df.at[idx, "edit_count"]) + 1
                            save_data(df)
                            st.session_state.editing_id = None
                            st.success("✅ Entry updated successfully!")
                            st.rerun()
                    if cancelled:
                        st.session_state.editing_id = None
                        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — ADD NEW PRACTICE
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    if not st.session_state.student_name:
        st.warning("⬅️ Please enter your name in the sidebar before adding a practice.")
    else:
        st.markdown(f"<div class='section-title'>Add a Best Practice — logged as {st.session_state.student_name}</div>",
                    unsafe_allow_html=True)
        st.markdown(
            "Share a best practice for estimating the cost of capital. "
            "Be concise in the *practice* and explain the *rationale* so classmates understand the reasoning."
        )

        with st.form("add_form", clear_on_submit=True):
            new_cat = st.selectbox("Category", CATEGORIES)
            new_practice = st.text_area(
                "Best Practice *",
                placeholder="e.g. Always unlever and re-lever beta to match the target's capital structure.",
                height=90,
            )
            new_rationale = st.text_area(
                "Rationale / Explanation *",
                placeholder="Explain why this practice matters and how to apply it…",
                height=130,
            )
            submitted = st.form_submit_button("➕ Add to the List", type="primary")

            if submitted:
                if not new_practice.strip():
                    st.error("Please fill in the Best Practice field.")
                elif not new_rationale.strip():
                    st.error("Please provide a rationale so classmates understand the reasoning.")
                else:
                    df = load_data()
                    new_row = {
                        "id": next_id(df),
                        "category": new_cat,
                        "practice": new_practice.strip(),
                        "rationale": new_rationale.strip(),
                        "added_by": st.session_state.student_name,
                        "added_on": now_str(),
                        "last_edited_by": "",
                        "last_edited_on": "",
                        "edit_count": 0,
                    }
                    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                    save_data(df)
                    st.success(f"✅ Best practice added! Thank you, {st.session_state.student_name}.")
                    st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — CONTRIBUTIONS LEADERBOARD
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown("<div class='section-title'>Student Contribution Summary</div>",
                unsafe_allow_html=True)
    st.markdown(
        "The table below tallies each student's contributions: how many best practices "
        "they **added** and how many existing entries they **edited**."
    )

    contrib = contribution_summary(df)
    if contrib.empty:
        st.info("No contributions recorded yet.")
    else:
        st.dataframe(
            contrib,
            use_container_width=True,
            column_config={
                "Student":              st.column_config.TextColumn("🎓 Student"),
                "Entries Added":        st.column_config.NumberColumn("➕ Added",   format="%d"),
                "Entries Edited":       st.column_config.NumberColumn("✏️ Edited",  format="%d"),
                "Total Contributions":  st.column_config.NumberColumn("⭐ Total",   format="%d"),
            },
        )

    # Bar chart
    if not contrib.empty:
        st.markdown("<div class='section-title'>Contribution Chart</div>",
                    unsafe_allow_html=True)
        chart_df = contrib.set_index("Student")[["Entries Added", "Entries Edited"]]
        st.bar_chart(chart_df)

    # Per-student detail
    st.markdown("<div class='section-title'>View a Student's Entries</div>",
                unsafe_allow_html=True)
    all_students = sorted(df["added_by"].dropna().unique().tolist())
    if all_students:
        selected = st.selectbox("Select a student", all_students)
        student_df = df[df["added_by"] == selected][
            ["category", "practice", "added_on", "last_edited_by", "last_edited_on", "edit_count"]
        ].rename(columns={
            "category": "Category",
            "practice": "Best Practice",
            "added_on": "Added On",
            "last_edited_by": "Last Edited By",
            "last_edited_on": "Last Edited On",
            "edit_count": "# Edits",
        })
        st.dataframe(student_df, use_container_width=True)
