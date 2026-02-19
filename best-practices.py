import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client, Client

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cost of Capital — Best Practices",
    page_icon="📊",
    layout="wide",
)

# ── Categories ────────────────────────────────────────────────────────────────
CATEGORIES = [
    "Risk-Free Rate",
    "Cost of Debt",
    "Cost of Equity",
    "Cost of Capital",
]

CAT_COLOURS = {
    "Risk-Free Rate":  "#2e7d52",
    "Cost of Debt":    "#b94040",
    "Cost of Equity":  "#c8952a",
    "Cost of Capital": "#1a2e4a",
}

# ── Supabase connection ───────────────────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()
TABLE = "best_practices"

# ── DB helpers ────────────────────────────────────────────────────────────────
def load_data() -> pd.DataFrame:
    res = supabase.table(TABLE).select("*").order("id").execute()
    if not res.data:
        return pd.DataFrame(columns=[
            "id","category","practice","rationale",
            "added_by","added_on","last_edited_by","last_edited_on","edit_count"
        ])
    df = pd.DataFrame(res.data)
    for col in ["last_edited_by","last_edited_on","added_by","category","practice","rationale"]:
        df[col] = df[col].fillna("").astype(str)
    df["edit_count"] = pd.to_numeric(df["edit_count"], errors="coerce").fillna(0).astype(int)
    return df

def insert_row(row: dict):
    supabase.table(TABLE).insert(row).execute()

def update_row(row_id: int, updates: dict):
    supabase.table(TABLE).update(updates).eq("id", row_id).execute()

def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")

def contribution_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    added  = df.groupby("added_by").size().reset_index(name="Entries Added")
    mask   = ~df["last_edited_by"].astype(str).str.strip().isin(["", "nan"])
    edited = (
        df[mask].groupby("last_edited_by").size()
        .reset_index(name="Entries Edited")
    )
    merged = added.merge(edited, left_on="added_by", right_on="last_edited_by", how="outer")
    merged["Student"] = merged["added_by"].fillna(merged["last_edited_by"])
    merged = merged[["Student","Entries Added","Entries Edited"]].fillna(0)
    merged["Entries Added"]       = merged["Entries Added"].astype(int)
    merged["Entries Edited"]      = merged["Entries Edited"].astype(int)
    merged["Total Contributions"] = merged["Entries Added"] + merged["Entries Edited"]
    merged = merged.sort_values("Total Contributions", ascending=False).reset_index(drop=True)
    merged.index += 1
    return merged

# ── Session state ─────────────────────────────────────────────────────────────
if "student_name" not in st.session_state:
    st.session_state.student_name = ""
if "editing_id" not in st.session_state:
    st.session_state.editing_id = None
if "add_category" not in st.session_state:
    st.session_state.add_category = "Risk-Free Rate"
if "add_practice" not in st.session_state:
    st.session_state.add_practice = ""
if "add_rationale" not in st.session_state:
    st.session_state.add_rationale = ""

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    :root { --navy:#1a2e4a; --gold:#c8952a; --light:#f4f6f9;
            --card:#ffffff; --border:#dde3ec; --muted:#6b7a99; }
    [data-testid="stAppViewContainer"] { background:var(--light); }
    [data-testid="stSidebar"]          { background:var(--navy); }
    [data-testid="stSidebar"] *        { color:#e8edf5 !important; }
    [data-testid="stSidebar"] .stTextInput input
        { background:#253d5e; border-color:#3a5278; color:white !important; }
    [data-testid="stSidebar"] label    { color:#b0bfd4 !important; }

    .app-header { background:linear-gradient(135deg,var(--navy) 0%,#253d5e 100%);
        color:white; padding:1.8rem 2rem 1.4rem; border-radius:10px; margin-bottom:1.5rem; }
    .app-header h1 { margin:0; font-size:1.7rem; font-weight:700; }
    .app-header p  { margin:.3rem 0 0; font-size:.95rem; opacity:.8; }
    .gold-bar { width:50px; height:4px; background:var(--gold);
        border-radius:2px; margin:.6rem 0 .2rem; }

    .section-title { font-size:1.05rem; font-weight:700; color:var(--navy);
        border-left:4px solid var(--gold); padding-left:.7rem; margin:1.4rem 0 .8rem; }

    .bp-card { background:var(--card); border:1px solid var(--border);
        border-radius:8px; padding:1rem 1.2rem; margin-bottom:.85rem;
        box-shadow:0 1px 4px rgba(0,0,0,.05); }
    .bp-card:hover { box-shadow:0 3px 10px rgba(0,0,0,.09); }
    .bp-category { display:inline-block; background:#e8edf5; color:var(--navy);
        font-size:.72rem; font-weight:700; letter-spacing:.5px; text-transform:uppercase;
        border-radius:4px; padding:.18rem .55rem; margin-bottom:.5rem; }
    .bp-practice  { font-size:1rem; font-weight:600; color:var(--navy); margin-bottom:.3rem; }
    .bp-rationale { font-size:.88rem; color:#444; line-height:1.55; margin-bottom:.55rem; }
    .bp-meta      { font-size:.76rem; color:var(--muted); }
    .bp-meta span { margin-right:.9rem; }
    .stButton > button { border-radius:6px !important; font-weight:600 !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 👤 Your Identity")
    name_input = st.text_input("Enter your full name",
                               value=st.session_state.student_name,
                               placeholder="e.g. Jane Smith")
    if name_input:
        st.session_state.student_name = name_input.strip()
    if st.session_state.student_name:
        st.success(f"Logged in as **{st.session_state.student_name}**")
    else:
        st.warning("Enter your name to add or edit entries.")
    st.markdown("---")
    st.markdown("### 📌 About this tool")
    st.markdown("Collaboratively build a best-practice guide for estimating the "
                "**cost of capital**. Add new practices, refine existing ones, "
                "and track everyone's contributions.")
    st.markdown("---")
    st.markdown("### 🏷️ Categories")
    for cat, colour in CAT_COLOURS.items():
        st.markdown(
            f"<span style='display:inline-block;width:10px;height:10px;"
            f"background:{colour};border-radius:50%;margin-right:6px;'></span>{cat}",
            unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="app-header">
  <h1>📊 Cost of Capital — Best Practices</h1>
  <div class="gold-bar"></div>
  <p>Global Online MBA · Finance · Collaborative Knowledge Base</p>
</div>
""", unsafe_allow_html=True)

df = load_data()

c1, c2, c3 = st.columns(3)
c1.metric("📝 Best Practices", len(df))
c2.metric("🎓 Contributors",   df["added_by"].nunique() if not df.empty else 0)
c3.metric("✏️ Total Edits",    int(df["edit_count"].sum()) if not df.empty else 0)
st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs(["📋 Best Practices List", "➕ Add a New Practice", "🏆 Contributions"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — VIEW & EDIT
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    fcol1, fcol2 = st.columns([2,1])
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
        st.info("No practices match your filter.")
    else:
        for _, row in filtered.iterrows():
            colour      = CAT_COLOURS.get(row["category"], "#1a2e4a")
            edited_line = ""
            if str(row.get("last_edited_by","")).strip() not in ("","nan"):
                edited_line = (
                    f'<span>✏️ Last edited by <strong>{row["last_edited_by"]}</strong>'
                    f' on {row["last_edited_on"]} (edit #{int(row["edit_count"])})</span>'
                )
            st.markdown(f"""
            <div class="bp-card" style="border-left:5px solid {colour};">
                <div class="bp-category">{row['category']}</div>
                <div class="bp-practice">{row['practice']}</div>
                <div class="bp-rationale">{row['rationale']}</div>
                <div class="bp-meta">
                    <span>➕ Added by <strong>{row['added_by']}</strong> on {row['added_on']}</span>
                    {edited_line}
                </div>
            </div>
            """, unsafe_allow_html=True)

            if st.session_state.student_name:
                if st.button("✏️ Edit this entry", key=f"edit_btn_{row['id']}"):
                    st.session_state.editing_id = int(row["id"])

            if st.session_state.editing_id == int(row["id"]):
                with st.form(key=f"edit_form_{row['id']}"):
                    st.markdown(f"**Editing entry #{row['id']}**")
                    new_cat = st.selectbox("Category", CATEGORIES,
                                          index=CATEGORIES.index(row["category"])
                                          if row["category"] in CATEGORIES else 0)
                    new_practice  = st.text_area("Best Practice",           value=row["practice"],  height=80)
                    new_rationale = st.text_area("Rationale / Explanation", value=row["rationale"], height=100)
                    ecol1, ecol2  = st.columns(2)
                    with ecol1:
                        submitted = st.form_submit_button("💾 Save Changes", type="primary")
                    with ecol2:
                        cancelled = st.form_submit_button("Cancel")

                    if submitted:
                        if not new_practice.strip():
                            st.error("The practice field cannot be empty.")
                        else:
                            update_row(int(row["id"]), {
                                "category":       new_cat,
                                "practice":       new_practice.strip(),
                                "rationale":      new_rationale.strip(),
                                "last_edited_by": st.session_state.student_name,
                                "last_edited_on": now_str(),
                                "edit_count":     int(row["edit_count"]) + 1,
                            })
                            st.session_state.editing_id = None
                            st.success("✅ Entry updated successfully!")
                            st.rerun()
                    if cancelled:
                        st.session_state.editing_id = None
                        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — ADD
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
    if not st.session_state.student_name:
        st.warning("⬅️ Please enter your name in the sidebar before adding a practice.")
    else:
        st.markdown(
            f"<div class='section-title'>Add a Best Practice — logged as "
            f"{st.session_state.student_name}</div>", unsafe_allow_html=True)
        st.markdown("Share a best practice for estimating the cost of capital. "
                    "Be concise in the *practice* and explain the *rationale* so "
                    "classmates understand the reasoning.")

        with st.form("add_form"):
            new_cat = st.selectbox(
                "Category", CATEGORIES,
                index=CATEGORIES.index(st.session_state.add_category)
                if st.session_state.add_category in CATEGORIES else 0,
            )
            new_practice  = st.text_area("Best Practice *",
                value=st.session_state.add_practice,
                placeholder="e.g. Always unlever and re-lever beta to match the target's capital structure.",
                height=90)
            new_rationale = st.text_area("Rationale / Explanation *",
                value=st.session_state.add_rationale,
                placeholder="Explain why this practice matters and how to apply it…",
                height=130)
            submitted = st.form_submit_button("➕ Add to the List", type="primary")

            if submitted:
                # Persist field values in session state so they survive a rerun
                st.session_state.add_category  = new_cat
                st.session_state.add_practice  = new_practice
                st.session_state.add_rationale = new_rationale

                if not new_practice.strip():
                    st.error("Please fill in the Best Practice field.")
                elif not new_rationale.strip():
                    st.error("Please provide a rationale so classmates understand the reasoning.")
                else:
                    insert_row({
                        "category":       new_cat,
                        "practice":       new_practice.strip(),
                        "rationale":      new_rationale.strip(),
                        "added_by":       st.session_state.student_name,
                        "added_on":       now_str(),
                        "last_edited_by": "",
                        "last_edited_on": "",
                        "edit_count":     0,
                    })
                    # Clear fields only after a successful save
                    st.session_state.add_category  = "Risk-Free Rate"
                    st.session_state.add_practice  = ""
                    st.session_state.add_rationale = ""
                    st.success(f"✅ Best practice added! Thank you, {st.session_state.student_name}.")
                    st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — CONTRIBUTIONS
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown("<div class='section-title'>Student Contribution Summary</div>",
                unsafe_allow_html=True)
    st.markdown("The table below tallies each student's contributions: how many best "
                "practices they **added** and how many existing entries they **edited**.")

    contrib = contribution_summary(df)
    if contrib.empty:
        st.info("No contributions recorded yet.")
    else:
        st.dataframe(contrib, use_container_width=True,
            column_config={
                "Student":             st.column_config.TextColumn("🎓 Student"),
                "Entries Added":       st.column_config.NumberColumn("➕ Added",  format="%d"),
                "Entries Edited":      st.column_config.NumberColumn("✏️ Edited", format="%d"),
                "Total Contributions": st.column_config.NumberColumn("⭐ Total",  format="%d"),
            })
        st.markdown("<div class='section-title'>Contribution Chart</div>",
                    unsafe_allow_html=True)
        st.bar_chart(contrib.set_index("Student")[["Entries Added","Entries Edited"]])

    st.markdown("<div class='section-title'>View a Student's Entries</div>",
                unsafe_allow_html=True)
    all_students = sorted(df["added_by"].dropna().unique().tolist()) if not df.empty else []
    if all_students:
        selected   = st.selectbox("Select a student", all_students)
        student_df = df[df["added_by"] == selected][
            ["category","practice","added_on","last_edited_by","last_edited_on","edit_count"]
        ].rename(columns={
            "category":"Category","practice":"Best Practice","added_on":"Added On",
            "last_edited_by":"Last Edited By","last_edited_on":"Last Edited On","edit_count":"# Edits"
        })
        st.dataframe(student_df, use_container_width=True)
