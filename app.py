"""
Call Report dashboard
Left side: the call log.  Right side: the matching MMS lead.

A call's "To" number is searched (any format: 1-xxx, (xxx) xxx-xxxx, xxx.xxx.xxxx, etc.)
in these MMS columns only:
  Phone Number In Ad, Contact Name (phase2), Contact Phone (phase2), Contact Email (phase2),
  Company (phase2), Company Phone (phase2), Company (phase3), Company Phone (phase3),
  Contact Phone (phase3), Phase2 Comments
The matching itself runs inside Supabase (function: call_report).
"""
import hmac
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Call Report", layout="wide", initial_sidebar_state="expanded")

# Keep the sidebar hide/show arrow visible at all times (Streamlit normally shows it only on hover)
st.markdown("""
<style>
[data-testid="stSidebarCollapseButton"] { display: flex !important; visibility: visible !important; opacity: 1 !important; }
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapsedControl"] button {
    border: 1px solid rgba(128,128,128,0.35); border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

CALL_COLS = ["Direction", "To", "From", "Ext / ID", "Date/Time", "Duration", "Times Called"]
LEAD_COLS = ["Lead Id", "Lead Started", "Last Edited", "Lead Source",
             "Media Market", "Company In Ad", "Contact Name (phase2)", "Lead Owner", "Status",
             "Phase2 Completed", "Matched On", "Leads Matched"]
RENAME = {
    "direction": "Direction", "to_number": "To", "from_value": "From", "call_time": "Date/Time",
    "duration": "Duration", "lead_id": "Lead Id", "lead_started": "Lead Started",
    "lead_source": "Lead Source", "media_market": "Media Market", "company_in_ad": "Company In Ad",
    "contact_name": "Contact Name (phase2)", "lead_owner": "Lead Owner", "status": "Status",
    "phase2_completed": "Phase2 Completed", "matched_on": "Matched On", "leads_matched": "Leads Matched",
    "last_edited": "Last Edited",
}


# ---------- password gate (only active when APP_PASSWORD is set in secrets) ----------
def password_ok() -> bool:
    try:
        required = st.secrets.get("APP_PASSWORD")
    except Exception:
        required = None
    if not required or st.session_state.get("authed"):
        return True
    st.title("Call Report")
    pw = st.text_input("Password", type="password")
    if pw:
        if hmac.compare_digest(pw, str(required)):
            st.session_state["authed"] = True
            st.rerun()
        st.error("Incorrect password")
    return False


if not password_ok():
    st.stop()


# ---------- connection ----------
@st.cache_resource
def get_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SECRET_KEY"])


try:
    sb = get_client()
except Exception:
    st.error(
        "Supabase connection details are missing. Add SUPABASE_URL and "
        "SUPABASE_SECRET_KEY to this app's secrets."
    )
    st.stop()


# ---------- data ----------
@st.cache_data(ttl=600, show_spinner="Loading calls...")
def load_calls(start: date, end: date) -> pd.DataFrame:
    rows, offset, page = [], 0, 1000
    while True:
        res = sb.rpc("call_report_v2", {"p_start": str(start), "p_end": str(end),
                                     "p_limit": page, "p_offset": offset}).execute()
        rows.extend(res.data)
        if len(res.data) < page:
            break
        offset += page
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df.rename(columns=RENAME)
    df["Date/Time"] = pd.to_datetime(df["Date/Time"])
    df["Lead Id"] = df["Lead Id"].fillna("Not Found")
    # Why this lead was chosen when a number matches several leads
    df["Lead Choice"] = ""
    multi = df["Leads Matched"] >= 2
    df.loc[multi, "Lead Choice"] = "Most recent edit"
    df.loc[multi & df["reps_lead"].astype(bool), "Lead Choice"] = "Rep's lead"
    df.loc[multi & df["picked"].astype(bool), "Lead Choice"] = "Picked"
    df = df.drop(columns=["picked", "reps_lead"])
    return df


BASE_DATE = date(1900, 1, 1)  # "from the beginning"


@st.cache_data(ttl=600, show_spinner=False)
def load_contacts() -> pd.DataFrame:
    res = (sb.table("contacts").select("id, from_value, rep, effective_from, mms_owner")
           .order("from_value").order("effective_from").execute())
    out = pd.DataFrame(res.data, columns=["id", "from_value", "rep", "effective_from", "mms_owner"])
    out["effective_from"] = pd.to_datetime(out["effective_from"]).dt.date
    return out


def current_owner_labels(contacts: pd.DataFrame) -> dict:
    """3-digit extensions only -> '418 — Devin Klein' (latest assignment)."""
    ext = contacts[contacts["from_value"].astype(str).str.fullmatch(r"\d{3}")]
    latest = ext.sort_values("effective_from").groupby("from_value").tail(1)
    labels = {}
    for _, r in latest.sort_values("from_value").iterrows():
        name = r["rep"] if isinstance(r["rep"], str) and r["rep"].strip() else "(unassigned)"
        labels[r["from_value"]] = f'{r["from_value"]} — {name}'
    return labels


def _reset_editor():
    st.session_state["editor_v"] = st.session_state.get("editor_v", 0) + 1


@st.dialog("Assign New")
def assign_new_dialog(contacts: pd.DataFrame):
    labels = current_owner_labels(contacts)
    ext = st.selectbox("Extension", list(labels), format_func=lambda k: labels[k])
    name = st.text_input("Contact")
    owner = st.text_input("MMS Owner Name (optional)",
                          help="Only needed if this person's name is spelled differently in MMS Lead Owner")
    start_day = st.date_input("Starting", value=date.today(), format="MM/DD/YYYY")
    st.caption(f"Calls from {ext} on or after {start_day:%m/%d/%Y} will show this contact. "
               "Earlier calls keep their current name.")
    if st.button("Save", type="primary"):
        if not name.strip():
            st.error("Enter a contact name.")
            return
        clash = contacts[(contacts["from_value"] == ext) & (contacts["effective_from"] == start_day)]
        if not clash.empty:
            st.error(f"{ext} already has an assignment starting {start_day:%m/%d/%Y}. "
                     "Rename it in the table instead.")
            return
        sb.table("contacts").insert({"from_value": ext, "rep": name.strip(),
                                     "mms_owner": owner.strip() or None,
                                     "effective_from": str(start_day)}).execute()
        st.cache_data.clear()
        _reset_editor()
        st.rerun()


@st.dialog("Rename contact")
def rename_dialog(row_id: int, old: str, new: str, field: str = "rep"):
    if field == "rep":
        st.write(f'Would you like to rename **"{old or "(unassigned)"}"** to **"{new or "(unassigned)"}"**?')
    else:
        st.write(f'Would you like to change the MMS Owner Name from **"{old or "(blank)"}"** '
                 f'to **"{new or "(blank)"}"**?')
    yes, no = st.columns(2)
    if yes.button("Yes", type="primary", width="stretch"):
        sb.table("contacts").update({field: new or None}).eq("id", row_id).execute()
        st.cache_data.clear()
        _reset_editor()
        st.rerun()
    if no.button("Cancel", width="stretch"):
        _reset_editor()
        st.rerun()


@st.dialog("Remove assignments")
def remove_dialog(rows: pd.DataFrame):
    st.write("Remove these assignments? Their calls go back to the previous owner.")
    st.dataframe(rows[["Ext / Phone / ID", "Name", "Starting"]], hide_index=True, width="stretch")
    yes, no = st.columns(2)
    if yes.button("Remove", type="primary", width="stretch"):
        for row_id in rows["id"]:
            sb.table("contacts").delete().eq("id", int(row_id)).execute()
        st.cache_data.clear()
        _reset_editor()
        st.rerun()
    if no.button("Cancel", width="stretch"):
        _reset_editor()
        st.rerun()


# ---------- page picker ----------
page = st.sidebar.radio("Page", ["Call Report", "Contacts", "Upload Calls"], label_visibility="collapsed")
st.sidebar.divider()

if page == "Upload Calls":
    st.title("Upload Calls")
    st.caption("Add new calls from a CSV export. Columns needed: Direction, To, From, Date/Time, Duration "
               "(same format as the call log). Calls already in the database are skipped, "
               "so it's safe to upload a file that overlaps an earlier one.")
    up = st.file_uploader("Call log CSV", type=["csv"])
    if up is None:
        st.stop()

    raw = pd.read_csv(up, dtype=str, keep_default_na=False)
    raw.columns = [str(c).strip() for c in raw.columns]
    needed = ["Direction", "To", "From", "Date/Time", "Duration"]
    missing = [c for c in needed if c not in raw.columns]
    if missing:
        st.error(f"This file is missing these columns: {', '.join(missing)}. "
                 f"Columns found: {', '.join(raw.columns)}")
        st.stop()

    f = raw[needed].copy()
    for c in needed:
        f[c] = f[c].astype(str).str.strip()
    # To: digits only
    f["To"] = f["To"].str.replace(r"\.0$", "", regex=True).str.replace(r"\D", "", regex=True)
    # From: blank -> empty; 433.0 -> 433
    f["From"] = f["From"].str.replace(r"^(\d+)\.0$", r"\1", regex=True)
    # Date/Time: store exactly like the existing rows, e.g. 10/9/26 4:40 PM
    ts = pd.to_datetime(f["Date/Time"], format="%m/%d/%y %I:%M %p", errors="coerce")
    retry = ts.isna() & (f["Date/Time"] != "")
    if retry.any():
        ts[retry] = pd.to_datetime(f.loc[retry, "Date/Time"], errors="coerce")
    def _fmt(t):
        h = t.hour % 12 or 12
        return f"{t.month}/{t.day}/{t:%y} {h}:{t:%M} {'AM' if t.hour < 12 else 'PM'}"
    f["Date/Time"] = [(_fmt(t) if pd.notna(t) else "") for t in ts]
    # Duration: H:MM:SS like 0:00:57
    td = pd.to_timedelta(f["Duration"], errors="coerce")
    def _dur(orig, d):
        if pd.isna(d):
            return orig
        s = int(d.total_seconds())
        return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    f["Duration"] = [_dur(o, d) for o, d in zip(f["Duration"], td)]

    bad = (f["To"] == "") | (f["Date/Time"] == "") | (f["Direction"] == "")
    good = f[~bad]
    if bad.any():
        with st.expander(f"⚠️ {int(bad.sum())} row{'s' if int(bad.sum()) != 1 else ''} can't be read (missing To, Date/Time or Direction) "
                         "and will be skipped"):
            st.dataframe(raw[bad.values], hide_index=True, width="stretch")
    if good.empty:
        st.error("No usable rows in this file.")
        st.stop()

    payload = good.replace({"From": {"": None}}).to_dict(orient="records")
    file_key = f"{up.name}-{up.size}-{len(payload)}"
    if st.session_state.get("upload_key") != file_key:
        with st.spinner("Checking which calls are already in the database..."):
            res = sb.rpc("calls_upload", {"p_rows": payload, "p_commit": False}).execute().data[0]
        st.session_state["upload_key"] = file_key
        st.session_state["upload_preview"] = res
    res = st.session_state["upload_preview"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Rows in file", f"{len(f):,}")
    c2.metric("Already in database", f"{res['already_there']:,}")
    c3.metric("New calls to add", f"{res['to_add']:,}")
    c4.metric("Skipped (unreadable)", f"{int(bad.sum()):,}")
    if res["to_add"]:
        st.caption(f"New calls run from {res['first_call']} to {res['last_call']}.")
    with st.expander("Preview the file (first 50 rows)"):
        st.dataframe(good.head(50), hide_index=True, width="stretch")

    @st.dialog("Confirm upload")
    def confirm_upload(n: int):
        st.write(f"Upload **{n:,}** new call{'s' if n != 1 else ''} to the database?")
        yes, no = st.columns(2)
        if yes.button("Yes, upload", type="primary", width="stretch"):
            with st.spinner("Uploading..."):
                out = sb.rpc("calls_upload", {"p_rows": payload, "p_commit": True}).execute().data[0]
            load_calls.clear()
            st.session_state["upload_key"] = None
            st.session_state["upload_done"] = out["to_add"]
            st.rerun()
        if no.button("Cancel", width="stretch"):
            st.rerun()

    if st.session_state.get("upload_done") is not None:
        n_done = st.session_state.pop("upload_done")
        st.success(f"Added {n_done:,} call{'s' if n_done != 1 else ''}. They now show on the Call Report.")
    elif res["to_add"] == 0:
        st.info("Every call in this file is already in the database. Nothing to upload.")
    else:
        if st.button(f"Confirm: upload {res['to_add']:,} call{'s' if res['to_add'] != 1 else ''}", type="primary"):
            confirm_upload(res["to_add"])
    st.stop()



if page == "Contacts":
    st.title("Contacts")
    st.caption("Who each extension, phone number, or username in the From column belongs to. "
               "Edit a name and press Enter to rename it. Use Assign New when an extension changes hands. "
               "MMS Owner Name is only needed when the person's name is spelled differently in MMS.")
    contacts = load_contacts()
    if st.button("➕ Assign New", type="primary"):
        assign_new_dialog(contacts)

    shown = pd.DataFrame({
        "id": contacts["id"],
        "Ext / Phone / ID": contacts["from_value"],
        "Name": contacts["rep"].fillna(""),
        "MMS Owner Name": contacts["mms_owner"].fillna(""),
        "Starting": contacts["effective_from"].map(
            lambda d: "Beginning" if d == BASE_DATE else f"{d:%m/%d/%Y}"),
        "Remove": False,
    })
    find = st.text_input("Find", placeholder="Type an extension or name")
    if find.strip():
        f = find.strip().lower()
        shown = shown[shown["Ext / Phone / ID"].str.lower().str.contains(f, regex=False)
                      | shown["Name"].str.lower().str.contains(f, regex=False)]

    edited = st.data_editor(
        shown, hide_index=True, width="stretch", height=600, num_rows="fixed",
        key=f"contacts_editor_{st.session_state.get('editor_v', 0)}",
        column_order=["Ext / Phone / ID", "Name", "MMS Owner Name", "Starting", "Remove"],
        disabled=["Ext / Phone / ID", "Starting"],
        column_config={
            "Name": st.column_config.TextColumn(help="Edit and press Enter to rename"),
            "MMS Owner Name": st.column_config.TextColumn(
                help="How this person's name appears in MMS Lead Owner, if different "
                     "(e.g. Becky Kirchwehm -> Rebecca Kirchwehm). Used to find the rep's own lead."),
            "Starting": st.column_config.TextColumn(help="Calls on or after this date use this name"),
            "Remove": st.column_config.CheckboxColumn(width="small"),
        },
    )
    unassigned = (shown["Name"].str.strip() == "").sum()
    st.caption(f"{len(shown)} assignments · {unassigned} unassigned")

    # A name was changed -> confirm
    changed = edited[edited["Name"].str.strip() != shown["Name"].str.strip()]
    changed_owner = edited[edited["MMS Owner Name"].fillna("").str.strip()
                           != shown["MMS Owner Name"].fillna("").str.strip()]
    if not changed.empty:
        r = changed.iloc[0]
        rename_dialog(int(r["id"]), shown.loc[r.name, "Name"].strip(), str(r["Name"]).strip())
    elif not changed_owner.empty:
        r = changed_owner.iloc[0]
        rename_dialog(int(r["id"]), shown.loc[r.name, "MMS Owner Name"].strip(),
                      str(r["MMS Owner Name"] or "").strip(), field="mms_owner")

    to_remove = edited[edited["Remove"]]
    if not to_remove.empty and st.button(f"Remove {len(to_remove)} selected"):
        remove_dialog(to_remove)
    st.stop()


# ---------- sidebar ----------
st.sidebar.header("Filters")
today = date.today()
picked = st.sidebar.date_input("Date range", value=(today - timedelta(days=7), today), key="f_dates")
if not isinstance(picked, (list, tuple)) or len(picked) != 2:
    st.info("Pick an end date to finish the date range.")
    st.stop()
start, end = picked

df = load_calls(start, end)

st.title("Call Report")
header_slot = st.empty()  # filled in once the From filter is known

if df.empty:
    st.warning("No calls in this date range.")
    st.stop()

# Swap From (extension / username) for the rep's name, using the assignment
# that was in effect on the day of the call (see Contacts > Assign New)
_c = load_contacts()
_c = _c[_c["rep"].fillna("").str.strip() != ""].copy()
_c["eff"] = pd.to_datetime(_c["effective_from"]).astype("datetime64[ns]")
_c = _c.rename(columns={"from_value": "_key"})[["_key", "eff", "rep"]].sort_values("eff")
df["Ext / ID"] = df["From"]
df["_key"] = df["From"].fillna("").astype(str)
df["Date/Time"] = df["Date/Time"].astype("datetime64[ns]")
df = df.sort_values("Date/Time")
df = pd.merge_asof(df, _c, left_on="Date/Time", right_on="eff", by="_key", direction="backward")
df["From"] = df["rep"].str.strip().fillna(df["Ext / ID"])
df = df.drop(columns=["_key", "eff", "rep"])

# Times Called = number of calls to that number inside the selected date range
df["Times Called"] = df.groupby("To")["To"].transform("count")

directions = st.sidebar.multiselect("Direction", sorted(df["Direction"].dropna().unique()), key="f_direction")
froms = st.sidebar.multiselect("From", sorted(df["From"].dropna().astype(str).unique()), key="f_from")

# Header label: who is being viewed + date range, e.g. "Amanda Watson · 10/05/2026 to 10/12/2026"
who = ", ".join(froms) if froms else "All reps"
with header_slot.container():
    st.markdown(f"#### {who}  ·  {start:%m/%d/%Y} to {end:%m/%d/%Y}")
    st.caption("Times Called counts calls to that number within this date range")
found = st.sidebar.radio("Lead match", ["All", "Found", "Not Found"], horizontal=True, key="f_match")
min_times = st.sidebar.number_input("Times Called at least", min_value=1, value=1, step=1, key="f_min_times")
search = st.sidebar.text_input("Search (number, company, contact, lead id)", key="f_search")

view = df.copy()
if directions:
    view = view[view["Direction"].isin(directions)]
if froms:
    view = view[view["From"].astype(str).isin(froms)]
if found == "Found":
    view = view[view["Lead Id"] != "Not Found"]
elif found == "Not Found":
    view = view[view["Lead Id"] == "Not Found"]
view = view[view["Times Called"] >= min_times]
if search.strip():
    s = search.strip().lower()
    hay = view[["To", "From", "Ext / ID", "Company In Ad", "Contact Name (phase2)", "Lead Id"]].fillna("").astype(str).apply(
        lambda c: c.str.lower()).agg(" ".join, axis=1)
    view = view[hay.str.contains(s, regex=False)]

st.sidebar.divider()
if st.sidebar.button("Refresh lead matching", help="Run this after uploading new MMS data"):
    with st.spinner("Rebuilding phone lookup from MMS..."):
        sb.rpc("refresh_mms_phone_lookup", {}).execute()
    st.cache_data.clear()
    st.rerun()
if st.sidebar.button("Reload calls"):
    st.cache_data.clear()
    st.rerun()

# ---------- summary ----------
matched = (view["Lead Id"] != "Not Found").sum()
is_out = view["Direction"].fillna("").str.lower().eq("outbound")
is_in = view["Direction"].fillna("").str.lower().eq("inbound")
k1, k2, k3, k4, k5, k6 = st.columns(6)
k1.metric("Total Calls", f"{len(view):,}")
k2.metric("Outbound", f"{int(is_out.sum()):,}")
k3.metric("Inbound", f"{int(is_in.sum()):,}")
k4.metric("Unique numbers", f"{view['To'].nunique():,}")
k5.metric("Calls matched to a lead", f"{matched:,}",
          f"{matched / len(view):.0%}" if len(view) else None, delta_color="off")
k6.metric("Not Found", f"{len(view) - matched:,}")

# ---------- table: calls on the left, MMS lead on the right ----------
# Default sort (same as the Excel report):
# From A-Z, Media Market A-Z, Lead Source A-Z, Lead Id smallest-largest, Date/Time oldest-newest
def _sort_key(col: pd.Series) -> pd.Series:
    if col.name == "Lead Id":
        return pd.to_numeric(col, errors="coerce")  # "Not Found" goes to the bottom of each group
    if col.name == "Date/Time":
        return col
    return col.astype("string").str.lower()  # A-Z ignoring upper/lower case, blanks last


SORT_COLS = ["From", "Media Market", "Lead Source", "Lead Id", "Date/Time"]
view = view.sort_values(SORT_COLS, key=_sort_key, na_position="last", kind="stable")
table = view[CALL_COLS + LEAD_COLS].reset_index(drop=True)

# Orange = several matching leads and nobody has picked/confirmed one yet
needs_pick = ((view["Leads Matched"] >= 2) & (view["Lead Choice"] != "Picked")).to_numpy()

STYLE_LIMIT = 10000  # colouring very large tables makes the page slow
if len(table) <= STYLE_LIMIT:
    shown = (table.style
             .set_properties(subset=LEAD_COLS, **{"background-color": "rgba(255, 230, 0, 0.12)"})
             .map(lambda v: "background-color: rgba(255, 99, 132, 0.25)" if v >= 3 else "",
                  subset=["Times Called"])
             .apply(lambda col: ["background-color: rgba(255, 140, 0, 0.35); font-weight: 600"
                                 if flag else "" for flag in needs_pick],
                    subset=["Leads Matched"], axis=0))
else:
    shown = table

st.markdown("**Call log** (left)  →  **MMS lead** (right, shaded)  ·  "
            "Click a row with **Leads Matched** of 2 or more (orange) to pick which lead it belongs to.")
event = st.dataframe(
    shown,
    key=f"calls_table_{st.session_state.get('table_v', 0)}",
    width="stretch",
    hide_index=True,
    height=600,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "Date/Time": st.column_config.DatetimeColumn(format="M/D/YY h:mm A"),
        "Times Called": st.column_config.NumberColumn(width="small"),
        "Leads Matched": st.column_config.NumberColumn(width="small",
                                                       help="How many MMS leads contain this number. "
                                                            "Click the row to pick one."),
    },
)

st.download_button("Download as CSV", table.to_csv(index=False).encode("utf-8"),
                   file_name=f"call_report_{start}_{end}.csv", mime="text/csv")

# ---------- pick a lead for numbers with several matches ----------
def _reset_table():
    # Don't rebuild the table (that would reset its sorting/search); just remember this
    # selection was handled so the box doesn't pop up again until another row is clicked.
    st.session_state["pick_handled"] = st.session_state.get("pick_current")
    st.session_state["suppress_pick"] = True  # rows may shift after a pick; don't auto-open on the next load


@st.dialog("Pick a lead", width="large")
def pick_lead_dialog(number: str, current_lead: str, choice: str):
    leads = pd.DataFrame(sb.rpc("leads_for_number", {"p_phone": number}).execute().data)
    if leads.empty:
        st.info("No matching leads found.")
        return
    leads = leads.rename(columns={
        "lead_id": "Lead Id", "created": "Created", "last_edited": "Last Edited", "lead_source": "Source",
        "media_market": "Market", "company_in_ad": "Company", "contact_name": "Contact",
        "contact_phone": "Contact Phone", "contact_email": "Contact Email", "lead_owner": "Lead Owner",
        "status": "Status", "phase2_completed": "Phase2 Completed", "matched_on": "Matched On"})
    leads = leads.rename(columns={"Company": "Company In Ad"})
    leads = leads[["Lead Id", "Market", "Company In Ad", "Lead Owner", "Status", "Last Edited", "Matched On"]]
    st.write(f"**{number}** matches **{len(leads)} leads**. Currently showing **{current_lead}** "
             f"({choice.lower() or 'only match'}). Click a lead, then **Use this lead**. "
             "The choice applies to every call to this number.")
    picked = st.dataframe(leads, hide_index=True, width="stretch", on_select="rerun",
                          selection_mode="single-row", key=f"pick_{number}")
    rows = picked.selection.rows if picked and picked.selection else []
    c1, c2, c3 = st.columns(3)
    if rows:
        lead = leads.iloc[rows[0]]["Lead Id"]
        label = f"Confirm lead {lead}" if lead == current_lead else f"Use lead {lead}"
        if c1.button(label, type="primary", width="stretch"):
            sb.table("lead_picks").upsert({"phone10": str(number)[-10:], "lead_id": str(lead),
                                           "picked_at": pd.Timestamp.utcnow().isoformat()},
                                          on_conflict="phone10").execute()
            load_calls.clear()
            _reset_table()
            st.rerun()
    else:
        c1.button("Use this lead", disabled=True, width="stretch")
    if choice == "Picked" and c2.button("Undo pick (go back to automatic)", width="stretch"):
        sb.table("lead_picks").delete().eq("phone10", str(number)[-10:]).execute()
        load_calls.clear()
        _reset_table()
        st.rerun()
    if c3.button("Close", width="stretch"):
        _reset_table()
        st.rerun()


# ---------- detail for a selected row ----------
sel = event.selection.rows if event and event.selection else []
st.session_state["pick_current"] = view.iloc[sel[0]]["call_id"] if sel else None
if not sel:
    st.session_state["pick_handled"] = None
if st.session_state.pop("suppress_pick", False):
    st.session_state["pick_handled"] = st.session_state["pick_current"]
if (sel and table.iloc[sel[0]]["Leads Matched"] >= 2
        and st.session_state.get("pick_handled") != st.session_state["pick_current"]):
    r = table.iloc[sel[0]]
    pick_lead_dialog(str(r["To"]), str(r["Lead Id"]), str(view.iloc[sel[0]]["Lead Choice"]))
if sel:
    number = table.iloc[sel[0]]["To"]
    st.subheader(f"All calls to {number} in this date range")
    st.dataframe(df[df["To"] == number][CALL_COLS + ["Lead Id", "Company In Ad", "Status"]],
                 hide_index=True, width="stretch",
                 column_config={"Date/Time": st.column_config.DatetimeColumn(format="M/D/YY h:mm A")})
else:
    st.caption("Tip: click a row to see every call to that number in the date range.")
