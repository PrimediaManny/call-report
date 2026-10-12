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

st.set_page_config(page_title="Call Report", layout="wide")

CALL_COLS = ["Direction", "To", "From", "Ext / ID", "Date/Time", "Duration", "Times Called"]
LEAD_COLS = ["Lead Id", "Lead Started", "Lead Source", "Media Market", "Company In Ad",
             "Contact Name (phase2)", "Lead Owner", "Status", "Phase2 Completed",
             "Matched On", "Leads Matched"]
RENAME = {
    "direction": "Direction", "to_number": "To", "from_value": "From", "call_time": "Date/Time",
    "duration": "Duration", "lead_id": "Lead Id", "lead_started": "Lead Started",
    "lead_source": "Lead Source", "media_market": "Media Market", "company_in_ad": "Company In Ad",
    "contact_name": "Contact Name (phase2)", "lead_owner": "Lead Owner", "status": "Status",
    "phase2_completed": "Phase2 Completed", "matched_on": "Matched On", "leads_matched": "Leads Matched",
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
        res = sb.rpc("call_report", {"p_start": str(start), "p_end": str(end),
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
    return df


BASE_DATE = date(1900, 1, 1)  # "from the beginning"


@st.cache_data(ttl=600, show_spinner=False)
def load_contacts() -> pd.DataFrame:
    res = (sb.table("contacts").select("id, from_value, rep, effective_from")
           .order("from_value").order("effective_from").execute())
    out = pd.DataFrame(res.data, columns=["id", "from_value", "rep", "effective_from"])
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
                                     "effective_from": str(start_day)}).execute()
        st.cache_data.clear()
        _reset_editor()
        st.rerun()


@st.dialog("Rename contact")
def rename_dialog(row_id: int, old: str, new: str):
    st.write(f'Would you like to rename **"{old or "(unassigned)"}"** to **"{new or "(unassigned)"}"**?')
    yes, no = st.columns(2)
    if yes.button("Yes", type="primary", width="stretch"):
        sb.table("contacts").update({"rep": new or None}).eq("id", row_id).execute()
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
page = st.sidebar.radio("Page", ["Call Report", "Contacts"], label_visibility="collapsed")
st.sidebar.divider()

if page == "Contacts":
    st.title("Contacts")
    st.caption("Who each extension, phone number, or username in the From column belongs to. "
               "Edit a name and press Enter to rename it. Use Assign New when an extension changes hands.")
    contacts = load_contacts()
    if st.button("➕ Assign New", type="primary"):
        assign_new_dialog(contacts)

    shown = pd.DataFrame({
        "id": contacts["id"],
        "Ext / Phone / ID": contacts["from_value"],
        "Name": contacts["rep"].fillna(""),
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
        column_order=["Ext / Phone / ID", "Name", "Starting", "Remove"],
        disabled=["Ext / Phone / ID", "Starting"],
        column_config={
            "Name": st.column_config.TextColumn(help="Edit and press Enter to rename"),
            "Starting": st.column_config.TextColumn(help="Calls on or after this date use this name"),
            "Remove": st.column_config.CheckboxColumn(width="small"),
        },
    )
    unassigned = (shown["Name"].str.strip() == "").sum()
    st.caption(f"{len(shown)} assignments · {unassigned} unassigned")

    # A name was changed -> confirm
    changed = edited[edited["Name"].str.strip() != shown["Name"].str.strip()]
    if not changed.empty:
        r = changed.iloc[0]
        rename_dialog(int(r["id"]), shown.loc[r.name, "Name"].strip(), str(r["Name"]).strip())

    to_remove = edited[edited["Remove"]]
    if not to_remove.empty and st.button(f"Remove {len(to_remove)} selected"):
        remove_dialog(to_remove)
    st.stop()


# ---------- sidebar ----------
st.sidebar.header("Filters")
today = date.today()
picked = st.sidebar.date_input("Date range", value=(today - timedelta(days=7), today))
if not isinstance(picked, (list, tuple)) or len(picked) != 2:
    st.info("Pick an end date to finish the date range.")
    st.stop()
start, end = picked

df = load_calls(start, end)

st.title("Call Report")
st.caption(f"{start:%m/%d/%Y} to {end:%m/%d/%Y}  ·  Times Called counts calls to that number within this date range")

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

directions = st.sidebar.multiselect("Direction", sorted(df["Direction"].dropna().unique()))
froms = st.sidebar.multiselect("From", sorted(df["From"].dropna().astype(str).unique()))
found = st.sidebar.radio("Lead match", ["All", "Found", "Not Found"], horizontal=True)
min_times = st.sidebar.number_input("Times Called at least", min_value=1, value=1, step=1)
search = st.sidebar.text_input("Search (number, company, contact, lead id)")

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
k1, k2, k3, k4 = st.columns(4)
k1.metric("Calls", f"{len(view):,}")
k2.metric("Unique numbers", f"{view['To'].nunique():,}")
k3.metric("Calls matched to a lead", f"{matched:,}",
          f"{matched / len(view):.0%}" if len(view) else None, delta_color="off")
k4.metric("Not Found", f"{len(view) - matched:,}")

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

STYLE_LIMIT = 10000  # colouring very large tables makes the page slow
if len(table) <= STYLE_LIMIT:
    shown = (table.style
             .set_properties(subset=LEAD_COLS, **{"background-color": "rgba(255, 230, 0, 0.12)"})
             .map(lambda v: "background-color: rgba(255, 99, 132, 0.25)" if v >= 3 else "",
                  subset=["Times Called"]))
else:
    shown = table

st.markdown("**Call log** (left)  →  **MMS lead** (right, shaded)")
event = st.dataframe(
    shown,
    width="stretch",
    hide_index=True,
    height=600,
    on_select="rerun",
    selection_mode="single-row",
    column_config={
        "Date/Time": st.column_config.DatetimeColumn(format="M/D/YY h:mm A"),
        "Times Called": st.column_config.NumberColumn(width="small"),
        "Leads Matched": st.column_config.NumberColumn(width="small",
                                                       help="How many MMS leads contain this number"),
    },
)

st.download_button("Download as CSV", table.to_csv(index=False).encode("utf-8"),
                   file_name=f"call_report_{start}_{end}.csv", mime="text/csv")

# ---------- detail for a selected row ----------
sel = event.selection.rows if event and event.selection else []
if sel:
    number = table.iloc[sel[0]]["To"]
    st.subheader(f"All calls to {number} in this date range")
    st.dataframe(df[df["To"] == number][CALL_COLS + ["Lead Id", "Company In Ad", "Status"]],
                 hide_index=True, width="stretch",
                 column_config={"Date/Time": st.column_config.DatetimeColumn(format="M/D/YY h:mm A")})
else:
    st.caption("Tip: click a row to see every call to that number in the date range.")
