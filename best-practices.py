import streamlit as st
import pandas as pd
from datetime import datetime
import pytz
from supabase import create_client, Client

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cost of Capital — Best Practices",
    page_icon="📊",
    layout="wide",
)

# ── Best Practice topics (renamed from "Categories") ─────────────────────────
TOPICS = [
    "Risk-Free Rate",
    "Cost of Debt",
    "Cost of Equity",
    "Cost of Capital",
]

TOPIC_COLOURS = {
    "Risk-Free Rate":  "#2e7d52",
    "Cost of Debt":    "#b94040",
    "Cost of Equity":  "#c8952a",
    "Cost of Capital": "#4a90d9",
}

# ── Supabase connection ───────────────────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = get_supabase()
TABLE    = "best_practices"
CLASSES  = ["GOMBA 2025 F1", "GOMBA 2025 F2"]

# ── DB helpers ────────────────────────────────────────────────────────────────
def load_data(class_name: str) -> pd.DataFrame:
    res = (supabase.table(TABLE).select("*")
           .eq("class_name", class_name).order("id").execute())
    if not res.data:
        return pd.DataFrame(columns=[
            "id","class_name","category","practice","rationale",
            "added_by","added_on","last_edited_by","last_edited_on","edit_count"
        ])
    df = pd.DataFrame(res.data)
    for col in ["last_edited_by","last_edited_on","added_by","category","practice","rationale","class_name"]:
        df[col] = df[col].fillna("").astype(str)
    df["edit_count"] = pd.to_numeric(df["edit_count"], errors="coerce").fillna(0).astype(int)
    return df

def insert_row(row: dict):
    supabase.table(TABLE).insert(row).execute()

def update_row(row_id: int, updates: dict):
    supabase.table(TABLE).update(updates).eq("id", row_id).execute()

def delete_row(row_id: int):
    supabase.table(TABLE).delete().eq("id", row_id).execute()

def now_str() -> str:
    madrid = pytz.timezone("Europe/Madrid")
    return datetime.now(madrid).strftime("%Y-%m-%d %H:%M")

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
if "student_name"  not in st.session_state: st.session_state.student_name  = ""
if "student_email" not in st.session_state: st.session_state.student_email = ""
if "student_class" not in st.session_state: st.session_state.student_class = CLASSES[0]
if "editing_id"    not in st.session_state: st.session_state.editing_id    = None
if "add_topic"     not in st.session_state: st.session_state.add_topic     = "Risk-Free Rate"
if "add_practice"  not in st.session_state: st.session_state.add_practice  = ""
if "add_rationale" not in st.session_state: st.session_state.add_rationale = ""
# FIX 1 — duplicate-submit guard
if "submitting"    not in st.session_state: st.session_state.submitting    = False
if "confirm_delete" not in st.session_state: st.session_state.confirm_delete = None

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

    /* FIX 2 — hide the stray /div artifact Streamlit renders below markdown blocks */
    .element-container:has(> .stMarkdown > div > p:only-child:empty) { display:none; }

    .bp-card { background:var(--card); border:1px solid var(--border);
        border-radius:8px; padding:1rem 1.2rem; margin-bottom:.3rem;
        box-shadow:0 1px 4px rgba(0,0,0,.05); }
    .bp-card:hover { box-shadow:0 3px 10px rgba(0,0,0,.09); }
    .bp-topic { display:inline-block; background:#e8edf5; color:var(--navy);
        font-size:.72rem; font-weight:700; letter-spacing:.5px; text-transform:uppercase;
        border-radius:4px; padding:.18rem .55rem; margin-bottom:.5rem; }
    .bp-practice  { font-size:1rem; font-weight:600; color:var(--navy); margin-bottom:.3rem; }
    .bp-rationale { font-size:.88rem; color:#444; line-height:1.55; margin-bottom:.55rem; }
    .bp-meta      { font-size:.76rem; color:var(--muted); }
    .bp-meta span { margin-right:.9rem; }
    .stButton > button { border-radius:6px !important; font-weight:600 !important; }

    /* Sidebar selectbox — make selected value clearly visible */
    [data-testid="stSidebar"] [data-baseweb="select"] div,
    [data-testid="stSidebar"] [data-baseweb="select"] span,
    [data-testid="stSidebar"] [data-baseweb="select"] input {
        color: white !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] > div {
        background-color: #253d5e !important;
        border-color: #3a5278 !important;
    }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
IE_DOMAIN = "@student.ie.edu"

def valid_ie_email(email: str) -> bool:
    return email.strip().lower().endswith(IE_DOMAIN)

with st.sidebar:
    st.markdown("## 👤 Your Identity")
    name_input = st.text_input("Full name",
                               value=st.session_state.student_name,
                               placeholder="e.g. Jane Smith")
    email_input = st.text_input("IE University email",
                                value=st.session_state.student_email,
                                placeholder=f"e.g. jsmith{IE_DOMAIN}")
    class_input = st.selectbox("Your class",
                               CLASSES,
                               index=CLASSES.index(st.session_state.student_class)
                               if st.session_state.student_class in CLASSES else 0)
    if name_input:
        st.session_state.student_name  = name_input.strip()
    if email_input:
        st.session_state.student_email = email_input.strip().lower()
    st.session_state.student_class = class_input

    logged_in = (
        bool(st.session_state.student_name) and
        valid_ie_email(st.session_state.student_email)
    )
    if logged_in:
        st.success(f"Logged in as **{st.session_state.student_name}** · {st.session_state.student_class}")
    elif st.session_state.student_email and not valid_ie_email(st.session_state.student_email):
        st.error(f"Please use your IE University email ({IE_DOMAIN})")
    else:
        st.warning("Enter your name and IE email to participate.")
    st.markdown("---")
    st.markdown("### 📌 About this tool")
    st.markdown("Collaboratively build a best-practice guide for estimating the "
                "**cost of capital**. Add new practices, refine existing ones, "
                "and track everyone's contributions.")
    st.markdown("---")
    st.markdown("### 🏷️ Best Practice")   # FIX 4 — renamed from "Categories"
    for topic, colour in TOPIC_COLOURS.items():
        st.markdown(
            f"<span style='display:inline-block;width:10px;height:10px;"
            f"background:{colour};border-radius:50%;margin-right:6px;'></span>{topic}",
            unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
active_class = st.session_state.student_class
st.markdown(f"""
<div class="app-header">
  <h1>📊 Cost of Capital — Best Practices</h1>
  <div class="gold-bar"></div>
  <p>Global Online MBA · Finance · {active_class} · Collaborative Knowledge Base</p>
</div>
""", unsafe_allow_html=True)

df = load_data(active_class)

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
    # Show all four topics in fixed order, each with its entries beneath
    if df.empty:
        st.info("No best practices have been added yet.")
    else:
        for topic in TOPICS:
            colour   = TOPIC_COLOURS[topic]
            topic_df = df[df["category"] == topic]

            # Coloured topic heading bar
            st.markdown(
                f'<div style="background:{colour};color:white;font-weight:700;'
                f'font-size:.85rem;letter-spacing:.6px;text-transform:uppercase;'
                f'padding:.45rem .9rem;border-radius:6px;margin:1.1rem 0 .5rem;">'
                f'{topic}</div>',
                unsafe_allow_html=True,
            )

            if topic_df.empty:
                st.markdown(
                    '<p style="color:#6b7a99;font-size:.88rem;margin:.2rem 0 .8rem .3rem;">'
                    'No entries yet — be the first to add one!</p>',
                    unsafe_allow_html=True,
                )
            else:
                for _, row in topic_df.iterrows():
                    edited_line = ""
                    if str(row.get("last_edited_by","")).strip() not in ("","nan"):
                        edited_line = (
                            f'<span>✏️ Last edited by <strong>{row["last_edited_by"]}</strong>'
                            f' on {row["last_edited_on"]} (edit #{int(row["edit_count"])})</span>'
                        )

                    st.markdown(
                        f'<div class="bp-card" style="border-left:5px solid {colour};">'
                        f'<div class="bp-practice">{row["practice"]}</div>'
                        f'<div class="bp-rationale">{row["rationale"]}</div>'
                        f'<div class="bp-meta">'
                        f'<span>➕ Added by <strong>{row["added_by"]}</strong> on {row["added_on"]}</span>'
                        f'{edited_line}'
                        f'</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    is_author = (
                        logged_in and
                        st.session_state.student_name == row["added_by"]
                    )
                    is_other_logged_in = (
                        logged_in and
                        st.session_state.student_name != row["added_by"]
                    )

                    if is_author:
                        if st.session_state.confirm_delete == int(row["id"]):
                            st.warning("Are you sure you want to delete this entry? This cannot be undone.")
                            dcol1, dcol2 = st.columns(2)
                            with dcol1:
                                if st.button("🗑️ Yes, delete it", key=f"del_confirm_{row['id']}"):
                                    delete_row(int(row["id"]))
                                    st.session_state.confirm_delete = None
                                    st.rerun()
                            with dcol2:
                                if st.button("Cancel", key=f"del_cancel_{row['id']}"):
                                    st.session_state.confirm_delete = None
                                    st.rerun()
                        else:
                            acol1, acol2 = st.columns(2)
                            with acol1:
                                if st.button("✏️ Edit my entry", key=f"edit_btn_{row['id']}"):
                                    st.session_state.editing_id = int(row["id"])
                            with acol2:
                                if st.button("🗑️ Delete my entry", key=f"del_btn_{row['id']}"):
                                    st.session_state.confirm_delete = int(row["id"])
                                    st.rerun()

                    if is_other_logged_in:
                        if st.button("✏️ Edit this entry", key=f"edit_btn_{row['id']}"):
                            st.session_state.editing_id = int(row["id"])

                    if st.session_state.editing_id == int(row["id"]):
                        with st.form(key=f"edit_form_{row['id']}"):
                            st.markdown(f"**Editing entry #{row['id']}**")
                            new_topic = st.selectbox("Best Practice", TOPICS,
                                                    index=TOPICS.index(row["category"])
                                                    if row["category"] in TOPICS else 0)
                            new_practice  = st.text_area("Practice",               value=row["practice"],  height=80)
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
                                        "category":       new_topic,
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
    if not logged_in:
        st.warning("⬅️ Please enter your name in the sidebar before adding a practice.")
    else:
        st.markdown(
            f"<div class='section-title'>Add a Best Practice — logged as "
            f"{st.session_state.student_name}</div>", unsafe_allow_html=True)
        st.markdown("Share a best practice for estimating the cost of capital. "
                    "Be concise in the *practice* and explain the *rationale* so "
                    "classmates understand the reasoning.")

        # FIX 1 — disable the button while a submission is in flight
        with st.form("add_form"):
            new_topic = st.selectbox(                          # FIX 4 — "Best Practice"
                "Best Practice",
                TOPICS,
                index=TOPICS.index(st.session_state.add_topic)
                if st.session_state.add_topic in TOPICS else 0,
            )
            new_practice  = st.text_area("Practice *",
                value=st.session_state.add_practice,
                placeholder="e.g. Always unlever and re-lever beta to match the target's capital structure.",
                height=90)
            new_rationale = st.text_area("Rationale / Explanation *",
                value=st.session_state.add_rationale,
                placeholder="Explain why this practice matters and how to apply it…",
                height=130)

            submitted = st.form_submit_button(
                "➕ Add to the List",
                type="primary",
                disabled=st.session_state.submitting,   # FIX 1 — greyed out after first click
            )

            if submitted and not st.session_state.submitting:
                # Persist field values so they survive validation reruns
                st.session_state.add_topic     = new_topic
                st.session_state.add_practice  = new_practice
                st.session_state.add_rationale = new_rationale

                if not new_practice.strip():
                    st.error("Please fill in the Practice field.")
                elif not new_rationale.strip():
                    st.error("Please provide a rationale so classmates understand the reasoning.")
                else:
                    st.session_state.submitting = True          # FIX 1 — lock button
                    insert_row({
                        "class_name":     st.session_state.student_class,
                        "category":       new_topic,
                        "practice":       new_practice.strip(),
                        "rationale":      new_rationale.strip(),
                        "added_by":       st.session_state.student_name,
                        "added_on":       now_str(),
                        "last_edited_by": "",
                        "last_edited_on": "",
                        "edit_count":     0,
                    })
                    # Reset fields and release the lock
                    st.session_state.add_topic     = "Risk-Free Rate"
                    st.session_state.add_practice  = ""
                    st.session_state.add_rationale = ""
                    st.session_state.submitting    = False      # FIX 1 — unlock for next entry
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
        import plotly.graph_objects as go
        chart_data = contrib.set_index("Student")[["Entries Added","Entries Edited"]]
        fig = go.Figure()
        fig.add_bar(name="Added",  x=chart_data.index, y=chart_data["Entries Added"],
                    marker_color="#1a2e4a")
        fig.add_bar(name="Edited", x=chart_data.index, y=chart_data["Entries Edited"],
                    marker_color="#c8952a")
        max_val = int(chart_data.values.sum())
        fig.update_layout(
            barmode="stack",
            plot_bgcolor="white",
            yaxis=dict(
                title="Contributions",
                tickmode="linear", tick0=0,
                dtick=1,
                range=[0, max(max_val, 1) + 0.5],
            ),
            xaxis_title="Student",
            legend_title="Type",
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("<div class='section-title'>View a Student's Entries</div>",
                unsafe_allow_html=True)
    all_students = sorted(df["added_by"].dropna().unique().tolist()) if not df.empty else []
    if all_students:
        selected   = st.selectbox("Select a student", all_students)
        student_df = df[df["added_by"] == selected][
            ["category","practice","added_on","last_edited_by","last_edited_on","edit_count"]
        ].rename(columns={
            "category":"Best Practice","practice":"Practice","added_on":"Added On",
            "last_edited_by":"Last Edited By","last_edited_on":"Last Edited On","edit_count":"# Edits"
        })
        st.dataframe(student_df, use_container_width=True)
