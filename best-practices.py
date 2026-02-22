import streamlit as st
import pandas as pd
from datetime import datetime
import time
import pytz
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
CLASSES        = ["GOMBA 2025 F1", "GOMBA 2025 F2"]
ADMIN_PASSWORD = st.secrets["ADMIN_PASSWORD"]

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

def fetch_row(row_id: int) -> dict | None:
    """Re-fetch a single row from the DB to detect concurrent edits."""
    res = supabase.table(TABLE).select("*").eq("id", row_id).execute()
    return res.data[0] if res.data else None

def conditional_update_row(row_id: int, expected_practice: str, updates: dict) -> bool:
    """Update the row only if practice still matches expected_practice.
    Returns True if the update was applied, False if it was blocked by a concurrent edit.
    Uses Supabase .eq() on both id AND practice — so if someone else changed
    the text in between, zero rows match and nothing is written.
    """
    res = (supabase.table(TABLE)
           .update(updates)
           .eq("id", row_id)
           .eq("practice", expected_practice)
           .execute())
    return len(res.data) > 0  # True = row was updated, False = text had changed

def delete_row(row_id: int):
    supabase.table(TABLE).delete().eq("id", row_id).execute()

def delete_class_data(class_name: str):
    """Delete all rows for a given class — used by admin reset."""
    supabase.table(TABLE).delete().eq("class_name", class_name).execute()

def now_str() -> str:
    madrid = pytz.timezone("Europe/Madrid")
    return datetime.now(madrid).strftime("%Y-%m-%d %H:%M")

def contribution_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    added  = df.groupby("added_by").size().reset_index(name="Entries Added")
    mask   = ~df["last_edited_by"].astype(str).str.strip().isin(["", "nan"])
    edited = df[mask].groupby("last_edited_by").size().reset_index(name="Entries Edited")
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
if "student_name"   not in st.session_state: st.session_state.student_name   = ""
if "student_email"  not in st.session_state: st.session_state.student_email  = ""
if "student_class"  not in st.session_state: st.session_state.student_class  = ""
if "editing_id"     not in st.session_state: st.session_state.editing_id     = None
if "adding_concept" not in st.session_state: st.session_state.adding_concept = None
if "submitting"     not in st.session_state: st.session_state.submitting     = False
if "confirm_delete"      not in st.session_state: st.session_state.confirm_delete      = None
if "admin_authenticated" not in st.session_state: st.session_state.admin_authenticated = False
if "confirm_reset"       not in st.session_state: st.session_state.confirm_reset       = None

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

def valid_ie_email(email: str) -> bool:
    return email.strip().lower().endswith(IE_DOMAIN)

with st.sidebar:
    st.markdown("## 👤 Your Identity")
    name_input  = st.text_input("Full name",
                                value=st.session_state.student_name,
                                placeholder="e.g. Jane Smith")
    email_input = st.text_input("IE University email",
                                value=st.session_state.student_email,
                                placeholder=f"e.g. jsmith{IE_DOMAIN}")
    class_options = ["— select your class —"] + CLASSES
    class_input = st.selectbox("Your class", class_options,
                               index=class_options.index(st.session_state.student_class)
                               if st.session_state.student_class in class_options else 0)
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
c1.metric("📝 Concepts covered",
          f"{df['category'].nunique()} / {len(CONCEPTS)}" if not df.empty else f"0 / {len(CONCEPTS)}")
c2.metric("🎓 Contributors",    df["added_by"].nunique() if not df.empty else 0)
c3.metric("✏️ Total Edits",     int(df["edit_count"].sum()) if not df.empty else 0)
st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# TABS — now just two
# ══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs(["📋 Best Practices List", "🏆 Contributions", "🔐 Admin"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — BEST PRACTICES LIST (add inline if empty, edit/delete if filled)
# ─────────────────────────────────────────────────────────────────────────────
with tab1:
    # ── Persistent debug panel ───────────────────────────────────────────
    if st.session_state.get("dbg_new"):
        st.error("🔍 DEBUG INFO (from last Save press — remove before go-live)")
        st.write("**new_content:**", st.session_state["dbg_new"])
        st.write("**original_text (snapshot):**", st.session_state["dbg_orig"])
        st.write("**snap_for:**", st.session_state["dbg_snap_for"],
                 "**row_id_int:**", st.session_state["dbg_row_id"])
        st.write("**same?**", st.session_state["dbg_new"] == st.session_state["dbg_orig"])
        if st.session_state.get("dbg_saved") is not None:
            st.write("**saved (conditional_update returned):**", st.session_state["dbg_saved"])
            st.write("**live text at save time:**", st.session_state.get("dbg_live_text"))
            st.write("**original_text hex:**", st.session_state.get("dbg_orig_hex"))
            st.write("**live text hex:**",     st.session_state.get("dbg_live_hex"))
        if st.button("Clear debug"):
            for k in ["dbg_new","dbg_orig","dbg_snap_for","dbg_row_id"]:
                st.session_state.pop(k, None)
            st.rerun()

    # Build a lookup: concept → row (or None)
    concept_map = {}
    for concept in CONCEPTS:
        rows = df[df["category"] == concept] if not df.empty else pd.DataFrame()
        concept_map[concept] = rows.iloc[0] if not rows.empty else None

    for concept in CONCEPTS:
        colour = CONCEPT_COLOURS[concept]
        row    = concept_map[concept]

        # ── Concept heading bar ───────────────────────────────────────────────
        st.markdown(
            f'<div style="background:{colour};color:white;font-weight:700;'
            f'font-size:.85rem;letter-spacing:.6px;text-transform:uppercase;'
            f'padding:.45rem .9rem;border-radius:6px;margin:1.1rem 0 .5rem;">'
            f'{concept}</div>',
            unsafe_allow_html=True,
        )

        if row is None:
            # ── No entry yet ─────────────────────────────────────────────────
            if not logged_in:
                st.markdown(
                    '<p style="color:#6b7a99;font-size:.88rem;margin:.2rem 0 .8rem .3rem;">'
                    'No entry yet. Log in to be the first to add one.</p>',
                    unsafe_allow_html=True,
                )
            elif st.session_state.adding_concept == concept:
                # Inline add form
                with st.form(key=f"add_form_{concept}"):
                    new_content = st.text_area("Best Practice",
                                               placeholder="Describe the best practice, including the rationale…",
                                               height=200)
                    fcol1, fcol2 = st.columns(2)
                    with fcol1:
                        add_submitted = st.form_submit_button("➕ Add to the List",
                                                              type="primary",
                                                              disabled=st.session_state.submitting)
                    with fcol2:
                        add_cancelled = st.form_submit_button("Cancel")

                    if add_submitted and not st.session_state.submitting:
                        if not new_content.strip():
                            st.error("Please fill in the Best Practice field.")
                        else:
                            st.session_state.submitting = True
                            insert_row({
                                "class_name":     active_class,
                                "category":       concept,
                                "practice":       new_content.strip(),
                                "rationale":      "",
                                "added_by":       st.session_state.student_name,
                                "added_on":       now_str(),
                                "last_edited_by": "",
                                "last_edited_on": "",
                                "edit_count":     0,
                            })
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
            # ── Entry exists: show card ───────────────────────────────────────
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
                is_author = st.session_state.student_name == row["added_by"]
                editing   = st.session_state.editing_id == int(row["id"])

                if editing:
                    # ── Snapshot via st.session_state, written ONCE and
                    # protected against overwrite by using a version counter.
                    # We store both the text AND the editing_id it belongs to,
                    # so switching rows always resets the snapshot.
                    snap_key  = "orig_text"
                    snap_for  = "orig_for_id"
                    row_id_int = int(row["id"])
                    if st.session_state.get(snap_for) != row_id_int:
                        # First render for THIS row — fetch live text from DB
                        live_now = fetch_row(row_id_int)
                        st.session_state[snap_key] = live_now["practice"] if live_now else row["practice"]
                        st.session_state[snap_for] = row_id_int
                    original_text = st.session_state[snap_key]

                    # ── Inline edit form ──────────────────────────────────────
                    with st.form(key=f"edit_form_{row['id']}"):
                        new_content  = st.text_area("Best Practice",
                                                    value=original_text, height=200)
                        ecol1, ecol2 = st.columns(2)
                        with ecol1:
                            save_btn = st.form_submit_button("💾 Save Changes", type="primary")
                        with ecol2:
                            cancel_btn = st.form_submit_button("Cancel")

                        if save_btn:
                            # DEBUG — store values in session state so they
                            # survive the rerun and stay visible on screen
                            st.session_state["dbg_new"]      = repr(new_content.strip()[:120])
                            st.session_state["dbg_orig"]     = repr(original_text.strip()[:120])
                            st.session_state["dbg_snap_for"] = st.session_state.get(snap_for)
                            st.session_state["dbg_row_id"]   = row_id_int
                            if not new_content.strip():
                                st.error("The Best Practice field cannot be empty.")
                            elif new_content.strip() == original_text.strip():
                                st.session_state.editing_id = None
                                st.session_state.pop(snap_key, None)
                                st.session_state.pop(snap_for, None)
                                st.info("No changes were made.")
                                st.rerun()
                            else:
                                # Atomic conditional write — only succeeds if DB
                                # text still matches original_text (snapshot)
                                live = fetch_row(row_id_int)
                                if live is None:
                                    st.error("This entry no longer exists. It may have been deleted.")
                                    st.session_state.editing_id = None
                                    st.session_state.pop(snap_key, None)
                                    st.session_state.pop(snap_for, None)
                                    st.rerun()
                                else:
                                    # ── DEBUG (remove before go-live) ─────
                                    with st.expander("🔍 Debug"):
                                        st.write("original_text (snapshot):", repr(original_text[:60]))
                                        st.write("live practice:", repr(live["practice"][:60]))
                                        st.write("new_content:", repr(new_content.strip()[:60]))
                                        st.write("snap_for:", st.session_state.get(snap_for))
                                        st.write("row_id_int:", row_id_int)
                                        st.write("match?", live["practice"].strip() == original_text.strip())
                                    saved = conditional_update_row(
                                        row_id_int,
                                        original_text.strip(),
                                        {
                                            "practice":       new_content.strip(),
                                            "last_edited_by": st.session_state.student_name,
                                            "last_edited_on": now_str(),
                                            "edit_count":     int(live["edit_count"]) + 1,
                                        }
                                    )
                                    st.session_state["dbg_saved"]     = saved
                                    st.session_state["dbg_live_text"] = repr(live["practice"].strip()[:120])
                                    st.session_state["dbg_orig_hex"]  = original_text.strip().encode().hex()[:80]
                                    st.session_state["dbg_live_hex"]  = live["practice"].strip().encode().hex()[:80]
                                    st.session_state.editing_id = None
                                    st.session_state.pop(snap_key, None)
                                    st.session_state.pop(snap_for, None)
                                    if saved:
                                        st.success("✅ Entry updated successfully!")
                                    else:
                                        live2  = fetch_row(row_id_int)
                                        editor = (live2.get("last_edited_by") or "a classmate") if live2 else "a classmate"
                                        current = live2["practice"] if live2 else ""
                                        st.warning(
                                            f"⚠️ This entry was edited by **{editor}** while "
                                            f"you had the form open. The latest version is "
                                            f"shown below — please re-open the form if you "
                                            f"still want to make changes."
                                        )
                                        st.markdown(f"> {current}")
                                    st.rerun()
                        if cancel_btn:
                            st.session_state.editing_id = None
                            st.session_state.pop(snap_key, None)
                            st.session_state.pop(snap_for, None)
                            st.rerun()

                elif is_author:
                    # ── Author: Edit + Delete buttons (unique keys) ───────────
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
                            if st.button("✏️ Edit my entry", key=f"author_edit_btn_{row['id']}"):
                                st.session_state.editing_id         = int(row["id"])
                                st.rerun()
                        with acol2:
                            if st.button("🗑️ Delete my entry", key=f"del_btn_{row['id']}"):
                                st.session_state.confirm_delete = int(row["id"])
                                st.rerun()

                else:
                    # ── Other students: Edit button (unique key) ──────────────
                    if st.button("✏️ Edit this entry", key=f"other_edit_btn_{row['id']}"):
                        st.session_state.editing_id = int(row["id"])
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
        import plotly.graph_objects as go
        chart_data = contrib.set_index("Student")[["Entries Added","Entries Edited"]]
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

    st.markdown("<div class='section-title'>View a Student's Entries</div>",
                unsafe_allow_html=True)
    all_students = sorted(df["added_by"].dropna().unique().tolist()) if not df.empty else []
    if all_students:
        selected   = st.selectbox("Select a student", all_students)
        student_df = df[df["added_by"] == selected][
            ["category","practice","added_on","last_edited_by","last_edited_on","edit_count"]
        ].rename(columns={
            "category":"Concept","practice":"Best Practice","added_on":"Added On",
            "last_edited_by":"Last Edited By","last_edited_on":"Last Edited On","edit_count":"# Edits"
        })
        st.dataframe(student_df, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — ADMIN
# ─────────────────────────────────────────────────────────────────────────────
with tab3:
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
                colour   = CONCEPT_COLOURS[concept]
                rows     = df_admin[df_admin["category"] == concept]
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
                                    row_id = int(rows.iloc[0]["id"])
                                    delete_row(row_id)
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
