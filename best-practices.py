import streamlit as st
import pandas as pd
from datetime import datetime
import time
import pytz
import plotly.graph_objects as go
from supabase import create_client, Client

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cost of Capital — Best Practices",
    page_icon="📊",
    layout="wide",
)

CONCEPTS = [
    "Risk-Free Rate",
    "Cost of Debt",
    "Cost of Equity",
    "Cost of Capital",
]

CONCEPT_COLOURS = {
    "Risk-Free Rate":  "#2e7d52",
    "Cost of Debt":    "#b94040",
    "Cost of Equity":  "#c8952a",
    "Cost of Capital": "#4a90d9",
}

# ── Supabase ──────────────────────────────────────────────────────────────────
@st.cache_resource
def get_supabase() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase       = get_supabase()
TABLE          = "best_practices"
HISTORY_TABLE  = "edit_history"
CLASSES        = ["GOMBA 2025 F1", "GOMBA 2025 F2"]
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]

# ── Helpers ───────────────────────────────────────────────────────────────────
def now_str() -> str:
    madrid = pytz.timezone("Europe/Madrid")
    return datetime.now(madrid).strftime("%Y-%m-%d %H:%M")

def valid_ie_email(email: str) -> bool:
    return email.strip().lower().endswith("@student.ie.edu")

# ── DB helpers — best_practices ───────────────────────────────────────────────
def load_data(class_name: str) -> pd.DataFrame:
    res = (supabase.table(TABLE).select("*")
           .eq("class_name", class_name).order("id").execute())
    if not res.data:
        return pd.DataFrame(columns=[
            "id", "class_name", "category", "practice", "rationale",
            "added_by", "added_on", "last_edited_by", "last_edited_on", "edit_count"
        ])
    df = pd.DataFrame(res.data)
    for col in ["last_edited_by", "last_edited_on", "added_by",
                "category", "practice", "rationale", "class_name"]:
        df[col] = df[col].fillna("").astype(str)
    df["edit_count"] = pd.to_numeric(df["edit_count"], errors="coerce").fillna(0).astype(int)
    return df

def insert_row(row: dict):
    supabase.table(TABLE).insert(row).execute()

def fetch_row(row_id: int) -> dict | None:
    res = supabase.table(TABLE).select("*").eq("id", row_id).execute()
    return res.data[0] if res.data else None

def conditional_update_row(row_id: int, expected_practice: str, updates: dict) -> bool:
    """Update only if practice still matches expected_practice (optimistic lock)."""
    res = (supabase.table(TABLE)
           .update(updates)
           .eq("id", row_id)
           .eq("practice", expected_practice)
           .execute())
    return len(res.data) > 0

def delete_row(row_id: int):
    supabase.table(TABLE).delete().eq("id", row_id).execute()

def delete_class_data(class_name: str):
    supabase.table(TABLE).delete().eq("class_name", class_name).execute()

# ── DB helpers — edit_history ─────────────────────────────────────────────────
def log_history(entry_id: int, class_name: str, category: str,
                practice: str, edited_by: str, edited_on: str):
    """Append a revision record. Wrapped in try/except so it never crashes the app."""
    try:
        supabase.table(HISTORY_TABLE).insert({
            "entry_id":   entry_id,
            "class_name": class_name,
            "category":   category,
            "practice":   practice,
            "edited_by":  edited_by,
            "edited_on":  edited_on,
        }).execute()
    except Exception:
        pass

def load_history(class_name: str, category: str | None = None) -> pd.DataFrame:
    """Load revision history. Returns empty DataFrame on any error."""
    try:
        q = (supabase.table(HISTORY_TABLE).select("*")
             .eq("class_name", class_name)
             .order("id", desc=True))
        if category:
            q = q.eq("category", category)
        res = q.execute()
        if not res.data:
            return pd.DataFrame(columns=[
                "id", "entry_id", "class_name", "category",
                "practice", "edited_by", "edited_on"
            ])
        return pd.DataFrame(res.data)
    except Exception:
        return pd.DataFrame(columns=[
            "id", "entry_id", "class_name", "category",
            "practice", "edited_by", "edited_on"
        ])

# ── Contribution summary ──────────────────────────────────────────────────────
def contribution_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    added  = df.groupby("added_by").size().reset_index(name="Entries Added")
    mask   = ~df["last_edited_by"].astype(str).str.strip().isin(["", "nan"])
    edited = df[mask].groupby("last_edited_by").size().reset_index(name="Entries Edited")
    merged = added.merge(edited, left_on="added_by", right_on="last_edited_by", how="outer")
    merged["Student"] = merged["added_by"].fillna(merged["last_edited_by"])
    merged = merged[["Student", "Entries Added", "Entries Edited"]].fillna(0)
    merged["Entries Added"]       = merged["Entries Added"].astype(int)
    merged["Entries Edited"]      = merged["Entries Edited"].astype(int)
    merged["Total Contributions"] = merged["Entries Added"] + merged["Entries Edited"]
    merged = merged.sort_values("Total Contributions", ascending=False).reset_index(drop=True)
    merged.index += 1
    return merged

# ── Session state ─────────────────────────────────────────────────────────────
if "student_name"        not in st.session_state: st.session_state.student_name        = ""
if "student_email"       not in st.session_state: st.session_state.student_email       = ""
if "student_class"       not in st.session_state: st.session_state.student_class       = ""
if "editing_id"          not in st.session_state: st.session_state.editing_id          = None
if "adding_concept"      not in st.session_state: st.session_state.adding_concept      = None
if "submitting"          not in st.session_state: st.session_state.submitting          = False
if "confirm_delete"      not in st.session_state: st.session_state.confirm_delete      = None
if "confirm_reset"       not in st.session_state: st.session_state.confirm_reset       = None
if "admin_authenticated" not in st.session_state: st.session_state.admin_authenticated = False
if "conflict_warning"    not in st.session_state: st.session_state["conflict_warning"] = None

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
    [data-testid="stSidebar"] label { color:#b0bfd4 !important; }

    .app-header { background:linear-gradient(135deg,var(--navy) 0%,#253d5e 100%);
        color:white; padding:1.8rem 2rem 1.4rem; border-radius:10px; margin-bottom:1.5rem; }
    .app-header h1 { margin:0; font-size:1.7rem; font-weight:700; }
    .app-header p  { margin:.3rem 0 0; font-size:.95rem; opacity:.8; }
    .gold-bar { width:50px; height:4px; background:var(--gold);
        border-radius:2px; margin:.6rem 0 .2rem; }

    .section-title { font-size:1.05rem; font-weight:700; color:var(--navy);
        border-left:4px solid var(--gold); padding-left:.7rem; margin:1.4rem 0 .8rem; }

    .bp-card { background:var(--card); border:1px solid var(--border);
        border-radius:8px; padding:1rem 1.2rem; margin-bottom:.3rem;
        box-shadow:0 1px 4px rgba(0,0,0,.05); }
    .bp-card:hover { box-shadow:0 3px 10px rgba(0,0,0,.09); }
    .bp-practice { font-size:1rem; color:#222; line-height:1.6; margin-bottom:.55rem; }
    .bp-meta     { font-size:.76rem; color:var(--muted); }
    .bp-meta span { margin-right:.9rem; }
    .stButton > button { border-radius:6px !important; font-weight:600 !important; }

    [data-testid="stSidebar"] [data-baseweb="select"] div,
    [data-testid="stSidebar"] [data-baseweb="select"] span,
    [data-testid="stSidebar"] [data-baseweb="select"] input { color:white !important; }
    [data-testid="stSidebar"] [data-baseweb="select"] > div
        { background-color:#253d5e !important; border-color:#3a5278 !important; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
IE_DOMAIN = "@student.ie.edu"

with st.sidebar:
    st.markdown("## 👤 Your Identity")
    name_input  = st.text_input("Full name",
                                value=st.session_state.student_name,
                                placeholder="e.g. Jane Smith")
    email_input = st.text_input("IE University email",
                                value=st.session_state.student_email,
                                placeholder=f"e.g. jsmith{IE_DOMAIN}")
    class_options = ["— select your class —"] + CLASSES
    class_input   = st.selectbox(
        "Your class", class_options,
        index=class_options.index(st.session_state.student_class)
        if st.session_state.student_class in class_options else 0
    )
    if name_input:
        st.session_state.student_name  = name_input.strip()
    if email_input:
        st.session_state.student_email = email_input.strip().lower()
    if class_input != "— select your class —":
        st.session_state.student_class = class_input

    logged_in = (
        bool(st.session_state.student_name) and
        valid_ie_email(st.session_state.student_email) and
        st.session_state.student_class in CLASSES
    )
    if logged_in:
        st.success(f"Logged in as **{st.session_state.student_name}** · {st.session_state.student_class}")
    elif st.session_state.student_email and not valid_ie_email(st.session_state.student_email):
        st.error(f"Please use your IE University email ({IE_DOMAIN})")
    else:
        st.warning("Enter your name, IE email and class to participate.")

    st.markdown("---")
    st.markdown("### 📌 About this tool")
    st.markdown("Collaboratively build a best-practice guide for estimating the "
                "**cost of capital**. Each concept has one shared post that all "
                "students can contribute to and edit.")
    st.markdown("---")
    st.markdown("### 🏷️ Concept")
    for concept, colour in CONCEPT_COLOURS.items():
        st.markdown(
            f"<span style='display:inline-block;width:10px;height:10px;"
            f"background:{colour};border-radius:50%;margin-right:6px;'></span>{concept}",
            unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# HEADER & METRICS
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
c1.metric("📝 Concepts covered",
          f"{df['category'].nunique()} / {len(CONCEPTS)}" if not df.empty else f"0 / {len(CONCEPTS)}")
c2.metric("🎓 Contributors",  df["added_by"].nunique() if not df.empty else 0)
c3.metric("✏️ Total Edits",   int(df["edit_count"].sum()) if not df.empty else 0)
st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3, tab4 = st.tabs([
    "📋 Best Practices List",
    "🏆 Contributions",
    "📜 History",
    "🔐 Admin",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — BEST PRACTICES LIST
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    concept_map = {}
    for concept in CONCEPTS:
        rows = df[df["category"] == concept] if not df.empty else pd.DataFrame()
        concept_map[concept] = rows.iloc[0] if not rows.empty else None

    for concept in CONCEPTS:
        colour = CONCEPT_COLOURS[concept]
        row    = concept_map[concept]

        # Concept heading bar
        st.markdown(
            f'<div style="background:{colour};color:white;font-weight:700;'
            f'font-size:.85rem;letter-spacing:.6px;text-transform:uppercase;'
            f'padding:.45rem .9rem;border-radius:6px;margin:1.1rem 0 .5rem;">'
            f'{concept}</div>',
            unsafe_allow_html=True,
        )

        if row is None:
            # No entry yet
            if not logged_in:
                st.markdown(
                    '<p style="color:#6b7a99;font-size:.88rem;margin:.2rem 0 .8rem .3rem;">'
                    'No entry yet. Log in to be the first to add one.</p>',
                    unsafe_allow_html=True,
                )
            elif st.session_state.adding_concept == concept:
                with st.form(key=f"add_form_{concept}"):
                    new_content  = st.text_area(
                        "Best Practice",
                        placeholder="Describe the best practice, including the rationale…",
                        height=200,
                    )
                    fcol1, fcol2 = st.columns(2)
                    with fcol1:
                        add_submitted = st.form_submit_button(
                            "➕ Add to the List", type="primary",
                            disabled=st.session_state.submitting,
                        )
                    with fcol2:
                        add_cancelled = st.form_submit_button("Cancel")

                    if add_submitted and not st.session_state.submitting:
                        if not new_content.strip():
                            st.error("Please fill in the Best Practice field.")
                        else:
                            st.session_state.submitting = True
                            ts = now_str()
                            insert_row({
                                "class_name":     active_class,
                                "category":       concept,
                                "practice":       new_content.strip(),
                                "rationale":      "",
                                "added_by":       st.session_state.student_name,
                                "added_on":       ts,
                                "last_edited_by": "",
                                "last_edited_on": "",
                                "edit_count":     0,
                            })
                            # Fetch new row id for history log
                            new_row = (supabase.table(TABLE).select("id")
                                       .eq("class_name", active_class)
                                       .eq("category", concept)
                                       .execute())
                            if new_row.data:
                                log_history(
                                    entry_id   = new_row.data[0]["id"],
                                    class_name = active_class,
                                    category   = concept,
                                    practice   = new_content.strip(),
                                    edited_by  = st.session_state.student_name,
                                    edited_on  = ts,
                                )
                            st.session_state.adding_concept = None
                            st.session_state.submitting     = False
                            st.success(f"✅ Best practice added! Thank you, {st.session_state.student_name}.")
                            time.sleep(2.5)
                            st.rerun()
                    if add_cancelled:
                        st.session_state.adding_concept = None
                        st.rerun()
            else:
                st.markdown(
                    '<p style="color:#6b7a99;font-size:.88rem;margin:.2rem 0 .4rem .3rem;">'
                    'No entry yet — be the first to add one!</p>',
                    unsafe_allow_html=True,
                )
                if st.button("➕ Add best practice", key=f"add_btn_{concept}"):
                    st.session_state.adding_concept = concept
                    st.rerun()

        else:
            # Entry exists — show card
            edited_line = ""
            if str(row.get("last_edited_by", "")).strip() not in ("", "nan"):
                edited_line = (
                    f'<span>✏️ Last edited by <strong>{row["last_edited_by"]}</strong>'
                    f' on {row["last_edited_on"]} (edit #{int(row["edit_count"])})</span>'
                )
            st.markdown(
                f'<div class="bp-card" style="border-left:5px solid {colour};">'
                f'<div class="bp-practice">{row["practice"]}</div>'
                f'<div class="bp-meta">'
                f'<span>➕ Added by <strong>{row["added_by"]}</strong> on {row["added_on"]}</span>'
                f'{edited_line}'
                f'</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            if logged_in:
                is_author  = st.session_state.student_name == row["added_by"]
                editing    = st.session_state.editing_id == int(row["id"])
                row_id_int = int(row["id"])

                # Conflict warning — rendered at card level so it survives the rerun
                # that follows a blocked save (editing_id is already None by then)
                if st.session_state.get("conflict_warning") == row_id_int:
                    live_w  = fetch_row(row_id_int)
                    editor  = (live_w.get("last_edited_by") or "a classmate") if live_w else "a classmate"
                    st.warning(
                        f"⚠️ This entry was edited by **{editor}** while you had the "
                        f"form open. The latest version is shown above — please "
                        f"re-open the form if you still want to make changes."
                    )
                    st.session_state["conflict_warning"] = None

                if editing:
                    snap_key = "orig_text"
                    snap_for = "orig_for_id"
                    # Snapshot set once per form open (identified by row id)
                    if st.session_state.get(snap_for) != row_id_int:
                        live_now = fetch_row(row_id_int)
                        st.session_state[snap_key] = live_now["practice"] if live_now else row["practice"]
                        st.session_state[snap_for] = row_id_int
                    original_text = st.session_state[snap_key]

                    with st.form(key=f"edit_form_{row['id']}"):
                        new_content  = st.text_area("Best Practice",
                                                    value=original_text, height=200)
                        ecol1, ecol2 = st.columns(2)
                        with ecol1:
                            save_btn = st.form_submit_button("💾 Save Changes", type="primary")
                        with ecol2:
                            cancel_btn = st.form_submit_button("Cancel")

                        if save_btn:
                            if not new_content.strip():
                                st.error("The Best Practice field cannot be empty.")
                            elif new_content.strip() == original_text.strip():
                                st.session_state.editing_id = None
                                st.session_state.pop(snap_key, None)
                                st.session_state.pop(snap_for, None)
                                st.info("No changes were made.")
                                st.rerun()
                            else:
                                live = fetch_row(row_id_int)
                                if live is None:
                                    st.error("This entry no longer exists — it may have been deleted.")
                                    st.session_state.editing_id = None
                                    st.session_state.pop(snap_key, None)
                                    st.session_state.pop(snap_for, None)
                                    st.rerun()
                                else:
                                    ts    = now_str()
                                    saved = conditional_update_row(
                                        row_id_int,
                                        original_text.strip(),
                                        {
                                            "practice":       new_content.strip(),
                                            "last_edited_by": st.session_state.student_name,
                                            "last_edited_on": ts,
                                            "edit_count":     int(live["edit_count"]) + 1,
                                        }
                                    )
                                    if saved:
                                        log_history(
                                            entry_id   = row_id_int,
                                            class_name = active_class,
                                            category   = row["category"],
                                            practice   = new_content.strip(),
                                            edited_by  = st.session_state.student_name,
                                            edited_on  = ts,
                                        )
                                        st.session_state.editing_id = None
                                        st.session_state.pop(snap_key, None)
                                        st.session_state.pop(snap_for, None)
                                        st.rerun()
                                    else:
                                        # Concurrent edit detected — flag for warning outside form
                                        st.session_state["conflict_warning"] = row_id_int
                                        st.session_state.editing_id = None
                                        st.session_state.pop(snap_key, None)
                                        st.session_state.pop(snap_for, None)
                                        st.rerun()
                        if cancel_btn:
                            st.session_state.editing_id = None
                            st.session_state.pop(snap_key, None)
                            st.session_state.pop(snap_for, None)
                            st.rerun()

                elif is_author:
                    if st.session_state.confirm_delete == row_id_int:
                        st.warning("Are you sure you want to delete this entry? This cannot be undone.")
                        dcol1, dcol2 = st.columns(2)
                        with dcol1:
                            if st.button("🗑️ Yes, delete it", key=f"del_confirm_{row['id']}"):
                                delete_row(row_id_int)
                                st.session_state.confirm_delete = None
                                st.rerun()
                        with dcol2:
                            if st.button("Cancel", key=f"del_cancel_{row['id']}"):
                                st.session_state.confirm_delete = None
                                st.rerun()
                    else:
                        acol1, acol2 = st.columns(2)
                        with acol1:
                            if st.button("✏️ Edit my entry", key=f"author_edit_btn_{row['id']}"):
                                st.session_state.editing_id = row_id_int
                                st.rerun()
                        with acol2:
                            if st.button("🗑️ Delete my entry", key=f"del_btn_{row['id']}"):
                                st.session_state.confirm_delete = row_id_int
                                st.rerun()
                else:
                    if st.button("✏️ Edit this entry", key=f"other_edit_btn_{row['id']}"):
                        st.session_state.editing_id = row_id_int
                        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — CONTRIBUTIONS
# ─────────────────────────────────────────────────────────────────────────────
with tab2:
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
        chart_data = contrib.set_index("Student")[["Entries Added", "Entries Edited"]]
        fig = go.Figure()
        fig.add_bar(name="Added",  x=chart_data.index, y=chart_data["Entries Added"],
                    marker_color="#1a2e4a")
        fig.add_bar(name="Edited", x=chart_data.index, y=chart_data["Entries Edited"],
                    marker_color="#c8952a")
        max_val = int(chart_data.values.sum())
        fig.update_layout(
            barmode="stack", plot_bgcolor="white",
            yaxis=dict(title="Contributions", tickmode="linear",
                       tick0=0, dtick=1, range=[0, max(max_val, 1) + 0.5]),
            xaxis_title="Student", legend_title="Type",
            margin=dict(t=20, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)



# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — HISTORY
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
    st.markdown("<div class='section-title'>Revision History</div>", unsafe_allow_html=True)
    st.markdown(
        "Every version of each entry is recorded here. "
        "Select a concept to browse its full edit history, newest revision first."
    )

    hist_concept     = st.selectbox("Concept",
                                    ["— all concepts —"] + CONCEPTS,
                                    key="hist_concept_select")
    selected_concept = None if hist_concept == "— all concepts —" else hist_concept

    hist_df = load_history(active_class, selected_concept)

    if hist_df.empty:
        st.info("No history recorded yet for this selection.")
    else:
        for _, hrow in hist_df.iterrows():
            colour = CONCEPT_COLOURS.get(hrow["category"], "#4a90d9")
            with st.expander(
                f"**{hrow['category']}** · {hrow['edited_on']} · {hrow['edited_by']}",
                expanded=False,
            ):
                st.markdown(
                    f'<div class="bp-card" style="border-left:5px solid {colour};">'
                    f'<div class="bp-practice">{hrow["practice"]}</div>'
                    f'<div class="bp-meta">'
                    f'<span>✏️ <strong>{hrow["edited_by"]}</strong> · {hrow["edited_on"]}</span>'
                    f'</div></div>',
                    unsafe_allow_html=True,
                )

# ─────────────────────────────────────────────────────────────────────────────
# TAB 4 — ADMIN
# ─────────────────────────────────────────────────────────────────────────────
with tab4:
    st.markdown("<div class='section-title'>Admin Panel</div>", unsafe_allow_html=True)

    if not st.session_state.admin_authenticated:
        st.markdown("Enter the admin password to access reset controls.")
        pwd = st.text_input("Password", type="password", key="admin_pwd_input")
        if st.button("🔓 Log in", key="admin_login_btn"):
            if pwd == ADMIN_PASSWORD:
                st.session_state.admin_authenticated = True
                st.rerun()
            else:
                st.error("Incorrect password.")
    else:
        st.success("✅ Logged in as admin.")
        if st.button("🔒 Log out", key="admin_logout_btn"):
            st.session_state.admin_authenticated = False
            st.rerun()

        st.markdown("---")
        st.markdown("### 🗑️ Reset Concept Boxes")
        st.markdown(
            "Select a class and choose which concepts to clear. "
            "This permanently deletes the entry for that concept and cannot be undone."
        )

        reset_class = st.selectbox("Class to reset", CLASSES, key="admin_class_select")
        df_admin    = load_data(reset_class)

        if df_admin.empty:
            st.info(f"No entries found for {reset_class}.")
        else:
            for concept in CONCEPTS:
                colour    = CONCEPT_COLOURS[concept]
                rows      = df_admin[df_admin["category"] == concept]
                has_entry = not rows.empty

                col_label, col_btn = st.columns([3, 1])
                with col_label:
                    status = (f"<span style='color:{colour};font-weight:700;'>{concept}</span> — "
                              f"{'✅ has entry' if has_entry else '⬜ empty'}")
                    st.markdown(status, unsafe_allow_html=True)
                with col_btn:
                    if has_entry:
                        if st.session_state.confirm_reset == (reset_class, concept):
                            st.warning(f"Delete the entry for **{concept}** in {reset_class}?")
                            dcol1, dcol2 = st.columns(2)
                            with dcol1:
                                if st.button("Yes, delete", key=f"admin_del_yes_{concept}"):
                                    delete_row(int(rows.iloc[0]["id"]))
                                    st.session_state.confirm_reset = None
                                    st.success(f"✅ '{concept}' cleared for {reset_class}.")
                                    st.rerun()
                            with dcol2:
                                if st.button("Cancel", key=f"admin_del_no_{concept}"):
                                    st.session_state.confirm_reset = None
                                    st.rerun()
                        else:
                            if st.button("🗑️ Reset", key=f"admin_reset_{concept}"):
                                st.session_state.confirm_reset = (reset_class, concept)
                                st.rerun()

        st.markdown("---")
        st.markdown("### 🔴 Reset Entire Class")
        st.markdown("This deletes **all four** concept entries for the selected class at once.")
        if st.session_state.confirm_reset == (reset_class, "ALL"):
            st.error(f"This will delete all entries for **{reset_class}**. Are you sure?")
            rcol1, rcol2 = st.columns(2)
            with rcol1:
                if st.button("Yes, reset all", key="admin_reset_all_yes"):
                    delete_class_data(reset_class)
                    st.session_state.confirm_reset = None
                    st.success(f"✅ All entries cleared for {reset_class}.")
                    st.rerun()
            with rcol2:
                if st.button("Cancel", key="admin_reset_all_no"):
                    st.session_state.confirm_reset = None
                    st.rerun()
        else:
            if st.button(f"🔴 Reset all entries for {reset_class}", key="admin_reset_all_btn"):
                st.session_state.confirm_reset = (reset_class, "ALL")
                st.rerun()
