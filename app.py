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


@st.cache_data(ttl=600, show_spinner=False)
def load_contacts() -> pd.DataFrame:
    res = sb.table("contacts").select("from_value, rep").order("from_value").execute()
    return pd.DataFrame(res.data, columns=["from_value", "rep"])


# ---------- page picker ----------
page = st.sidebar.radio("Page", ["Call Report", "Contacts"], label_visibility="collapsed")
st.sidebar.divider()

if page == "Contacts":
    st.title("Contacts")
    st.caption("Who each extension, phone number, or username in the call log's From column belongs to. "
               "Edit a name, add a row at the bottom, or select rows and press Delete, then click Save.")
    contacts = load_contacts().rename(columns={"from_value": "Ext / Phone / ID", "rep": "Name"})
    edited = st.data_editor(
        contacts, num_rows="dynamic", hide_index=True, width="stretch", height=650,
        column_config={
            "Ext / Phone / ID": st.column_config.TextColumn(required=True),
            "Name": st.column_config.TextColumn(help="Leave blank if unassigned"),
        },
    )
    unassigned = contacts["Name"].isna() | (contacts["Name"].astype(str).str.strip() == "")
    st.caption(f"{len(contacts)} contacts · {int(unassigned.sum())} unassigned")
    if st.button("Save changes", type="primary"):
        new = edited.dropna(subset=["Ext / Phone / ID"]).copy()
        new["Ext / Phone / ID"] = new["Ext / Phone / ID"].astype(str).str.strip()
        new = new[new["Ext / Phone / ID"] != ""].drop_duplicates("Ext / Phone / ID", keep="last")
        removed = set(contacts["Ext / Phone / ID"]) - set(new["Ext / Phone / ID"])
        for key in removed:
            sb.table("contacts").delete().eq("from_value", key).execute()
        rows = [{"from_value": r["Ext / Phone / ID"],
                 "rep": (str(r["Name"]).strip() or None) if pd.notna(r["Name"]) else None}
                for _, r in new.iterrows()]
        if rows:
            sb.table("contacts").upsert(rows, on_conflict="from_value").execute()
        st.cache_data.clear()
        st.success("Saved.")
        st.rerun()
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

# Swap From (extension / username) for the rep's name from the Contacts list
contact_map = (load_contacts().dropna(subset=["rep"])
               .assign(rep=lambda d: d["rep"].str.strip())
               .query("rep != ''").set_index("from_value")["rep"].to_dict())
df["Ext / ID"] = df["From"]
df["From"] = df["From"].map(contact_map).fillna(df["From"])

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
    hay = view[["To", "From", "Ext / ID", "Company In Ad", "Contact Name (phase2)", "Lead Id"]].astype(str).apply(
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
