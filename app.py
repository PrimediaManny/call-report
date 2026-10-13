"""
Call Report dashboard (Primedia Network)

Pages
  Reports:  Call Report  - call log (left) matched to the MMS lead (right)
            Lead Search  - search the MMS lead table directly
  Manage:   Contacts, Upload Calls, Upload Leads

A call's "To" number is matched (any format: 1-xxx, (xxx) xxx-xxxx, xxx.xxx.xxxx, ...) against the
phone numbers found in these MMS columns: Phone Number In Ad, Contact Name (phase2), Contact Phone (phase2),
Contact Email (phase2), Company (phase2), Company Phone (phase2), Company (phase3), Company Phone (phase3),
Contact Phone (phase3), Phase2 Comments. The matching runs inside Supabase (call_report_v4).
"""
import hmac
from datetime import date, timedelta

import pandas as pd
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Call Report", page_icon=":material/call:", layout="wide",
                   initial_sidebar_state="expanded")

# ---------- look & feel ----------
st.markdown("""
<style>
/* sidebar hide/show arrow always visible */
[data-testid="stSidebarCollapseButton"] { display: flex !important; visibility: visible !important; opacity: 1 !important; }
[data-testid="stSidebarCollapseButton"] button, [data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapsedControl"] button { border: 1px solid rgba(128,128,128,0.35); border-radius: 8px; }
/* tighter page top */
.block-container { padding-top: 2.2rem; }
/* sidebar section labels */
.sb-section { font-size: 0.72rem; font-weight: 700; letter-spacing: .07em; text-transform: uppercase;
              opacity: .55; margin: 1.1rem 0 .25rem 0; }
.sb-section:first-child { margin-top: .2rem; }
/* metric cards */
[data-testid="stMetric"] { background: rgba(128,128,128,0.06); border: 1px solid rgba(128,128,128,0.18);
                           border-radius: 12px; padding: 10px 14px; }
[data-testid="stMetricLabel"] { opacity: .75; }
/* subtitle under page titles */
.page-sub { font-size: 1.05rem; font-weight: 600; margin: -0.4rem 0 0.2rem 0; }
</style>
""", unsafe_allow_html=True)


def sidebar_section(label: str):
    st.markdown(f'<div class="sb-section">{label}</div>', unsafe_allow_html=True)


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
MMS_COLS = [
    "Lead Id", "Old Lead Id", "Lead Started", "Last Edited", "Lead Source", "Vertical", "Name of Media",
    "Media Market", "Media Format", "Company In Ad", "Lead Rating", "Phone Number In Ad",
    "Contact Name (phase2)", "Contact Phone (phase2)", "Contact Email (phase2)", "Company (phase2)",
    "Company Phone (phase2)", "Address (phase2)", "Suite (phase2)", "City (phase2)", "State (phase2)",
    "Zip (phase2)", "Company (phase3)", "State (phase3)", "Company Phone (phase3)",
    "Company Website (phase3)", "Contact 1 (phase3)", "Contact 1 Title (phase3)", "Contact 2 (phase3)",
    "Contact 2 Title (phase3)", "Contact Phone (phase3)", "Contact Email (phase3)", "Started By",
    "Lead Owner", "Status", "Phase1 Completed", "Mmr Completed", "Phase2 Completed", "Phase3 Completed",
    "Ddr Completed", "Phase2 Comments",
]
DT_FMT = st.column_config.DatetimeColumn(format="M/D/YY h:mm A")


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
    st.error("Supabase connection details are missing. Add SUPABASE_URL and "
             "SUPABASE_SECRET_KEY to this app's secrets.")
    st.stop()


# ---------- data ----------
@st.cache_data(ttl=3600, show_spinner=False)
def load_lead_sources() -> list:
    return [r["lead_source"] for r in sb.rpc("lead_source_list", {}).execute().data]


@st.cache_data(ttl=600, show_spinner="Loading calls...")
def load_calls(start: date, end: date, sources: tuple = (), started_from=None) -> pd.DataFrame:
    """sources / started_from: only match calls to MMS leads with these Lead Sources and/or
    a Lead Started date on or after started_from (both empty = all leads)."""
    rows, offset, page = [], 0, 1000
    while True:
        res = sb.rpc("call_report_v4", {"p_start": str(start), "p_end": str(end),
                                        "p_limit": page, "p_offset": offset,
                                        "p_sources": list(sources) if sources else None,
                                        "p_started_from": str(started_from) if started_from else None}).execute()
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


def apply_rep_names(df: pd.DataFrame) -> pd.DataFrame:
    """Swap From (extension / username) for the rep's name, using the assignment that was in effect
    on the day of the call (Contacts > Assign New). Keeps the raw value in 'Ext / ID'."""
    c = load_contacts()
    c = c[c["rep"].fillna("").str.strip() != ""].copy()
    c["eff"] = pd.to_datetime(c["effective_from"]).astype("datetime64[ns]")
    c = c.rename(columns={"from_value": "_key"})[["_key", "eff", "rep"]].sort_values("eff")
    df = df.copy()
    df["Ext / ID"] = df["From"]
    df["_key"] = df["From"].fillna("").astype(str)
    df["Date/Time"] = pd.to_datetime(df["Date/Time"]).astype("datetime64[ns]")
    df = df.sort_values("Date/Time")
    df = pd.merge_asof(df, c, left_on="Date/Time", right_on="eff", by="_key", direction="backward")
    df["From"] = df["rep"].str.strip().fillna(df["Ext / ID"])
    return df.drop(columns=["_key", "eff", "rep"])


def plural(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


# =====================================================================================
# CALL REPORT
# =====================================================================================
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
        "lead_id": "Lead Id", "last_edited": "Last Edited", "media_market": "Market",
        "company_in_ad": "Company In Ad", "lead_owner": "Lead Owner", "status": "Status",
        "matched_on": "Matched On"})
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
                                           "picked_at": pd.Timestamp.now("UTC").isoformat()},
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


def _filter_defaults() -> dict:
    today = date.today()
    return {"f_dates": (today - timedelta(days=7), today), "f_sources": [], "f_started_from": None,
            "f_direction": "All", "f_from": [], "f_match": "All", "f_min_times": 1, "f_search": ""}


def _reset_filters():
    for k, v in _filter_defaults().items():
        st.session_state[k] = v


def page_call_report():
    for k, v in _filter_defaults().items():  # first visit: start every filter at its default
        st.session_state.setdefault(k, v)

    # Sidebar sections are created up front so they stay in order while being filled later
    sec_calls, sec_leads, sec_narrow, sec_tools = (st.sidebar.container() for _ in range(4))

    with sec_calls:
        sidebar_section("Calls")
        picked = st.date_input("Date range", key="f_dates", format="MM/DD/YYYY")
    with sec_leads:
        sidebar_section("MMS leads to match")
        sources = st.multiselect(
            "Lead Source", load_lead_sources(), key="f_sources", placeholder="All sources",
            help="Only match calls to MMS leads with these Lead Sources. Calls without a lead from "
                 "these sources are hidden.")
        started_from = st.date_input(
            "Lead Started from", key="f_started_from", format="MM/DD/YYYY",
            help="Only match calls to MMS leads started on or after this date. Leave empty for any date.")
    with sec_tools:
        st.divider()
        st.button("Reset filters", icon=":material/restart_alt:", on_click=_reset_filters, width="stretch")
        with st.expander("Maintenance", icon=":material/build:"):
            if st.button("Reload calls", width="stretch", help="Fetch the latest calls from the database"):
                st.cache_data.clear()
                st.rerun()
            if st.button("Refresh lead matching", width="stretch",
                         help="Rebuild the phone lookup from all of MMS. Only needed if MMS was "
                              "changed outside this app."):
                with st.spinner("Rebuilding phone lookup from MMS..."):
                    sb.rpc("refresh_mms_phone_lookup", {}).execute()
                st.cache_data.clear()
                st.rerun()

    st.title("Call Report")
    if not isinstance(picked, (list, tuple)) or len(picked) != 2:
        st.info("Pick an end date to finish the date range.")
        return
    start, end = picked

    df = load_calls(start, end, tuple(sorted(sources)), started_from)
    header_slot = st.empty()  # filled in once the From filter is known

    if df.empty:
        lead_filter = " and ".join(x for x in [
            f"from {', '.join(sources)}" if sources else "",
            f"started on or after {started_from:%m/%d/%Y}" if started_from else ""] if x)
        st.warning("No calls in this date range" + (f" match a lead {lead_filter}." if lead_filter else "."))
        return

    df = apply_rep_names(df)
    # Times Called = number of calls to that number inside the selected date range
    df["Times Called"] = df.groupby("To")["To"].transform("count").astype(int)

    with sec_calls:
        direction = st.segmented_control("Direction", ["All", "Outbound", "Inbound"], key="f_direction")
        from_options = sorted(df["From"].dropna().astype(str).unique())
        # keep only reps that still exist in this date range
        st.session_state["f_from"] = [x for x in st.session_state.get("f_from", []) if x in from_options]
        froms = st.multiselect("From", from_options, key="f_from", placeholder="All reps")
        search = st.text_input("Search calls", key="f_search", placeholder="Number, company, contact, lead id",
                               icon=":material/search:")
    with sec_narrow:
        sidebar_section("Narrow results")
        found = st.segmented_control("Lead match", ["All", "Found", "Not Found"], key="f_match")
        min_times = st.number_input("Times Called at least", min_value=1, step=1, key="f_min_times")

    # Header label: who + lead filters + date range
    who = ", ".join(froms) if froms else "All reps"
    with header_slot.container():
        src = f"  ·  {', '.join(sources)}" if sources else ""
        if started_from:
            src += f"  ·  Leads started from {started_from:%m/%d/%Y}"
        st.markdown(f'<div class="page-sub">{who}{src}  ·  {start:%m/%d/%Y} to {end:%m/%d/%Y}</div>',
                    unsafe_allow_html=True)
        st.caption("Times Called counts calls to that number within this date range")

    view = df.copy()
    if direction and direction != "All":
        view = view[view["Direction"].fillna("").str.lower() == direction.lower()]
    if froms:
        view = view[view["From"].astype(str).isin(froms)]
    if found == "Found":
        view = view[view["Lead Id"] != "Not Found"]
    elif found == "Not Found":
        view = view[view["Lead Id"] == "Not Found"]
    view = view[view["Times Called"] >= min_times]
    if search.strip():
        s = search.strip().lower()
        hay = view[["To", "From", "Ext / ID", "Company In Ad", "Contact Name (phase2)", "Lead Id"]].fillna(
            "").astype(str).apply(lambda c: c.str.lower()).agg(" ".join, axis=1)
        view = view[hay.str.contains(s, regex=False)]

    # ---------- summary ----------
    matched = int((view["Lead Id"] != "Not Found").sum())
    is_out = view["Direction"].fillna("").str.lower().eq("outbound")
    is_in = view["Direction"].fillna("").str.lower().eq("inbound")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Total Calls", f"{len(view):,}")
    k2.metric("Outbound", f"{int(is_out.sum()):,}")
    k3.metric("Inbound", f"{int(is_in.sum()):,}")
    k4.metric("Unique numbers", f"{view['To'].nunique():,}")
    k5.metric("Matched to a lead", f"{matched:,}",
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

    view = view.sort_values(["From", "Media Market", "Lead Source", "Lead Id", "Date/Time"],
                            key=_sort_key, na_position="last", kind="stable")
    table = view[CALL_COLS + LEAD_COLS].reset_index(drop=True)
    for col in ["Times Called", "Leads Matched"]:  # whole numbers, never 86.000000
        table[col] = pd.to_numeric(table[col], errors="coerce").fillna(0).astype(int)

    # Orange = several matching leads and nobody has picked/confirmed one yet
    needs_pick = ((view["Leads Matched"] >= 2) & (view["Lead Choice"] != "Picked")).to_numpy()

    if len(table) <= 10000:  # colouring very large tables makes the page slow
        shown = (table.style
                 .format({"Times Called": "{:d}", "Leads Matched": "{:d}"})
                 .set_properties(subset=LEAD_COLS, **{"background-color": "rgba(255, 230, 0, 0.12)"})
                 .map(lambda v: "background-color: rgba(255, 99, 132, 0.25)" if v >= 3 else "",
                      subset=["Times Called"])
                 .apply(lambda col: ["background-color: rgba(255, 140, 0, 0.35); font-weight: 600"
                                     if flag else "" for flag in needs_pick],
                        subset=["Leads Matched"], axis=0))
    else:
        shown = table

    st.caption("**Call log** (left) → **MMS lead** (right, shaded). Click a row with **Leads Matched** "
               "shaded orange to pick which lead it belongs to.")
    event = st.dataframe(
        shown, key="calls_table", width="stretch", hide_index=True, height=600,
        on_select="rerun", selection_mode="single-row",
        column_config={
            "Date/Time": DT_FMT,
            "Times Called": st.column_config.NumberColumn(width="small"),
            "Leads Matched": st.column_config.NumberColumn(
                width="small", help="How many MMS leads contain this number. Click the row to pick one."),
        },
    )
    def _us_time(t):  # 9/30/26 2:58 PM, same as the table (works on Windows too)
        if pd.isna(t):
            return ""
        return f"{t.month}/{t.day}/{t:%y} {t.hour % 12 or 12}:{t:%M} {'AM' if t.hour < 12 else 'PM'}"
    export = table.copy()
    export["Date/Time"] = export["Date/Time"].map(_us_time)
    st.download_button("Download as CSV", export.to_csv(index=False).encode("utf-8"),
                       file_name=f"call_report_{start}_{end}.csv", mime="text/csv",
                       icon=":material/download:")

    # ---------- selected row: pick a lead / all calls to that number ----------
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
                     hide_index=True, width="stretch", column_config={"Date/Time": DT_FMT})
    else:
        st.caption("Tip: click a row to see every call to that number in the date range.")


# =====================================================================================
# LEAD SEARCH
# =====================================================================================
@st.cache_data(ttl=120, show_spinner="Searching MMS...")
def search_leads(q: str) -> pd.DataFrame:
    data = sb.rpc("search_leads", {"p_q": q, "p_limit": 300}).execute().data
    return pd.DataFrame(data).rename(columns={
        "lead_id": "Lead Id", "found_by": "Found By", "lead_started": "Lead Started",
        "last_edited": "Last Edited", "lead_source": "Lead Source", "media_market": "Media Market",
        "company_in_ad": "Company In Ad", "contact_name": "Contact Name", "contact_phone": "Contact Phone",
        "contact_email": "Contact Email", "phone_in_ad": "Phone Number In Ad", "lead_owner": "Lead Owner",
        "status": "Status"})


DETAIL_GROUPS = {
    "Lead": ["Lead Id", "Old Lead Id", "Lead Source", "Lead Rating", "Lead Owner", "Status", "Started By",
             "Lead Started", "Last Edited"],
    "Ad": ["Company In Ad", "Phone Number In Ad", "Media Market", "Media Format", "Name of Media", "Vertical"],
    "Phase 2 contact": ["Contact Name (phase2)", "Contact Phone (phase2)", "Contact Email (phase2)",
                        "Company (phase2)", "Company Phone (phase2)", "Address (phase2)", "Suite (phase2)",
                        "City (phase2)", "State (phase2)", "Zip (phase2)"],
    "Phase 3": ["Company (phase3)", "State (phase3)", "Company Phone (phase3)", "Company Website (phase3)",
                "Contact 1 (phase3)", "Contact 1 Title (phase3)", "Contact 2 (phase3)",
                "Contact 2 Title (phase3)", "Contact Phone (phase3)", "Contact Email (phase3)"],
    "Milestones": ["Phase1 Completed", "Mmr Completed", "Phase2 Completed", "Phase3 Completed",
                   "Ddr Completed"],
}


def _field_block(title: str, rec: dict, fields: list):
    with st.container(border=True):
        st.markdown(f"**{title}**")
        lines = [f"<span style='opacity:.6'>{f.replace(' (phase2)', '').replace(' (phase3)', '')}</span>"
                 f"<br>{rec.get(f)}" for f in fields if rec.get(f) not in (None, "")]
        st.markdown("".join(f"<div style='margin-bottom:.55rem;line-height:1.35'>{l}</div>" for l in lines) or
                    "<span style='opacity:.5'>Nothing recorded</span>", unsafe_allow_html=True)


def page_lead_search():
    st.title("Lead Search")
    st.markdown('<div class="page-sub">Search the MMS lead table</div>', unsafe_allow_html=True)
    st.caption("Look up a Lead Id, a phone number in any format (full or at least 7 digits), "
               "or part of a company name, contact name or email.")
    q = st.text_input("Search MMS", key="ls_q", label_visibility="collapsed", icon=":material/search:",
                      placeholder="e.g. 171876  ·  (702) 727-7777  ·  Athari  ·  name@company.com")
    if not q.strip():
        return
    digits = "".join(ch for ch in q if ch.isdigit())
    has_text = any(ch.isalpha() or ch == "@" for ch in q)
    if not has_text and 0 < len(digits) < 7 and not q.strip().isdigit():
        st.info("Enter at least 7 digits to search by phone number.")
        return
    if has_text and len(q.strip()) < 2:
        st.info("Type at least 2 characters.")
        return

    results = search_leads(q.strip())
    if results.empty:
        st.warning(f"No leads in MMS match **{q.strip()}**.")
        return
    note = " (showing the first 300 — refine your search to narrow it down)" if len(results) >= 300 else ""
    st.caption(f"{plural(len(results), 'lead')} found{note}. Click a lead to see the full record and its calls.")
    event = st.dataframe(results, hide_index=True, width="stretch", on_select="rerun",
                         selection_mode="single-row", key=f"ls_table_{q.strip()}",
                         height=min(38 + 35 * len(results), 420))
    sel = event.selection.rows if event and event.selection else []
    if not sel and len(results) == 1:
        sel = [0]
    if not sel:
        return

    lead_id = str(results.iloc[sel[0]]["Lead Id"])
    rec = sb.table("mms").select("*").eq("Lead Id", lead_id).execute().data
    if not rec:
        st.warning("That lead is no longer in MMS.")
        return
    rec = rec[0]
    st.divider()
    st.subheader(f"Lead {lead_id} · {rec.get('Company In Ad') or rec.get('Company (phase2)') or ''}")
    st.caption(" · ".join(x for x in [rec.get("Lead Owner"), rec.get("Status"), rec.get("Lead Source"),
                                       rec.get("Media Market")] if x))

    tab_details, tab_calls = st.tabs([":material/description: Details", ":material/call: Calls to this lead"])
    with tab_details:
        cols = st.columns(3)
        for i, (title, fields) in enumerate(DETAIL_GROUPS.items()):
            with cols[i % 3]:
                _field_block(title, rec, fields)
        if rec.get("Phase2 Comments"):
            with st.container(border=True):
                st.markdown("**Phase 2 comments**")
                st.text(rec["Phase2 Comments"])
    with tab_calls:
        calls = pd.DataFrame(sb.rpc("calls_for_lead", {"p_lead_id": lead_id}).execute().data)
        if calls.empty:
            st.info("No calls in the call log to any phone number on this lead.")
        else:
            calls = calls.rename(columns={"direction": "Direction", "to_number": "To", "from_value": "From",
                                          "call_time": "Date/Time", "duration": "Duration",
                                          "matched_on": "Number found in"})
            calls = apply_rep_names(calls).sort_values("Date/Time", ascending=False)
            st.caption(f"{plural(len(calls), 'call')} to {plural(calls['To'].nunique(), 'number')} on this lead")
            st.dataframe(calls[["Date/Time", "Direction", "To", "From", "Ext / ID", "Duration", "Number found in"]],
                         hide_index=True, width="stretch", column_config={"Date/Time": DT_FMT})


# =====================================================================================
# CONTACTS
# =====================================================================================
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


def page_contacts():
    st.title("Contacts")
    st.markdown('<div class="page-sub">Who each extension belongs to</div>', unsafe_allow_html=True)
    st.caption("Edit a name and press Enter to rename it. Use Assign New when an extension changes hands. "
               "MMS Owner Name is only needed when the person's name is spelled differently in MMS.")
    contacts = load_contacts()
    c1, c2 = st.columns([1, 3])
    if c1.button("Assign New", icon=":material/person_add:", type="primary", width="stretch"):
        assign_new_dialog(contacts)
    find = c2.text_input("Find", placeholder="Type an extension or name", label_visibility="collapsed",
                         icon=":material/search:")

    shown = pd.DataFrame({
        "id": contacts["id"],
        "Ext / Phone / ID": contacts["from_value"],
        "Name": contacts["rep"].fillna(""),
        "MMS Owner Name": contacts["mms_owner"].fillna(""),
        "Starting": contacts["effective_from"].map(lambda d: "Beginning" if d == BASE_DATE else f"{d:%m/%d/%Y}"),
        "Remove": False,
    })
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
    if not to_remove.empty and st.button(f"Remove {len(to_remove)} selected", icon=":material/delete:"):
        remove_dialog(to_remove)


# =====================================================================================
# UPLOAD CALLS
# =====================================================================================
def page_upload_calls():
    st.title("Upload Calls")
    st.markdown('<div class="page-sub">Add new calls from a CSV export</div>', unsafe_allow_html=True)
    st.caption("Columns needed: Direction, To, From, Date/Time, Duration (same format as the call log). "
               "Calls already in the database are skipped, so it's safe to upload a file that overlaps an "
               "earlier one. New calls get the next ID automatically.")
    up = st.file_uploader("Call log CSV", type=["csv"])
    if up is None:
        return

    raw = pd.read_csv(up, dtype=str, keep_default_na=False)
    raw.columns = [str(c).strip() for c in raw.columns]
    needed = ["Direction", "To", "From", "Date/Time", "Duration"]
    missing = [c for c in needed if c not in raw.columns]
    if missing:
        st.error(f"This file is missing these columns: {', '.join(missing)}. "
                 f"Columns found: {', '.join(raw.columns)}")
        return

    f = raw[needed].copy()
    for c in needed:
        f[c] = f[c].astype(str).str.strip()
    f["To"] = f["To"].str.replace(r"\.0$", "", regex=True).str.replace(r"\D", "", regex=True)
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
        with st.expander(f"⚠️ {plural(int(bad.sum()), 'row')} can't be read (missing To, Date/Time or "
                         "Direction) and will be skipped"):
            st.dataframe(raw[bad.values], hide_index=True, width="stretch")
    if good.empty:
        st.error("No usable rows in this file.")
        return

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
        st.write(f"Upload **{plural(n, 'new call')}** to the database?")
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
        st.success(f"Added {plural(n_done, 'call')}. They now show on the Call Report.")
    elif res["to_add"] == 0:
        st.info("Every call in this file is already in the database. Nothing to upload.")
    elif st.button(f"Confirm: upload {plural(res['to_add'], 'call')}", type="primary",
                   icon=":material/cloud_upload:"):
        confirm_upload(res["to_add"])


# =====================================================================================
# UPLOAD LEADS
# =====================================================================================
def page_upload_leads():
    st.title("Upload Leads")
    st.markdown('<div class="page-sub">Update MMS from a lead export</div>', unsafe_allow_html=True)
    st.caption("Rows are matched on Lead Id only: a Lead Id already in MMS is overwritten with the file's "
               "version, a new Lead Id is added. Only the columns in the file are updated, and blank cells in "
               "those columns overwrite with blank. Phone matching for the call log updates automatically.")
    up = st.file_uploader("Lead export CSV", type=["csv"], key="leads_file")
    if up is None:
        return

    raw = pd.read_csv(up, dtype=str, keep_default_na=False, low_memory=False)
    raw.columns = [str(c).strip() for c in raw.columns]
    if "Lead Id" not in raw.columns:
        st.error("This file has no **Lead Id** column, so it can't be matched to MMS. "
                 f"Columns found: {', '.join(raw.columns)}")
        return
    use_cols = [c for c in raw.columns if c in MMS_COLS]
    ignored = [c for c in raw.columns if c not in MMS_COLS]

    f = raw[use_cols].copy()
    for c in use_cols:
        f[c] = f[c].astype(str).str.strip()
    f["Lead Id"] = f["Lead Id"].str.replace(r"\.0+$", "", regex=True)  # "235486.0" -> "235486"
    # Dates: store them like the rest of MMS (Excel saves 10/1/2026 or 10/12/2026 16:21 instead)
    date_only = ["Lead Started", "Mmr Completed"]
    date_time = ["Last Edited", "Phase1 Completed", "Phase2 Completed", "Phase3 Completed", "Ddr Completed"]
    for col in [c for c in date_only + date_time if c in f.columns]:
        parsed = pd.to_datetime(f[col], errors="coerce", format="mixed")
        fmt = "%Y-%m-%d" if col in date_only else "%Y-%m-%d %H:%M:%S"
        f[col] = [p.strftime(fmt) if pd.notna(p) else orig for p, orig in zip(parsed, f[col])]
    bad = ~f["Lead Id"].str.fullmatch(r"\d+")
    dupes = int(f[~bad].duplicated("Lead Id", keep="last").sum())
    good = f[~bad].drop_duplicates("Lead Id", keep="last")

    if ignored:
        st.info(f"These columns aren't in MMS and will be ignored: {', '.join(ignored)}")
    if bad.any():
        with st.expander(f"⚠️ {plural(int(bad.sum()), 'row')} without a valid Lead Id will be skipped"):
            st.dataframe(raw[bad.values], hide_index=True, width="stretch")
    if good.empty:
        st.error("No rows with a valid Lead Id in this file.")
        return

    ids = good["Lead Id"].tolist()
    file_key = f"{up.name}-{up.size}-{len(ids)}"
    if st.session_state.get("leads_key") != file_key:
        with st.spinner("Checking which leads are already in MMS..."):
            existing = 0
            for i in range(0, len(ids), 5000):
                existing += sb.rpc("count_existing_leads", {"p_ids": ids[i:i + 5000]}).execute().data
        st.session_state["leads_key"] = file_key
        st.session_state["leads_existing"] = existing
    existing = st.session_state["leads_existing"]
    new = len(ids) - existing

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Leads in file", f"{len(ids):,}")
    c2.metric("Will overwrite", f"{existing:,}")
    c3.metric("New leads to add", f"{new:,}")
    c4.metric("Skipped", f"{int(bad.sum()) + dupes:,}",
              help="Rows without a valid Lead Id, plus repeated Lead Ids (the last copy in the file is used)")
    st.caption(f"Columns that will be updated ({len(use_cols)}): {', '.join(use_cols)}")
    with st.expander("Preview the file (first 50 rows)"):
        st.dataframe(good.head(50), hide_index=True, width="stretch")

    @st.dialog("Confirm lead upload")
    def confirm_leads(n_over: int, n_new: int):
        st.write(f"Overwrite **{plural(n_over, 'existing lead')}** and add **{plural(n_new, 'new lead')}** in MMS?")
        yes, no = st.columns(2)
        if yes.button("Yes, upload", type="primary", width="stretch"):
            rows = good.replace({"": None}).to_dict(orient="records")
            bar = st.progress(0.0, text="Uploading leads...")
            for i in range(0, len(rows), 500):
                sb.table("mms").upsert(rows[i:i + 500], on_conflict="Lead Id").execute()
                bar.progress(min(1.0, (i + 500) / len(rows)), text="Uploading leads...")
            bar.progress(1.0, text="Updating phone matching for these leads...")
            for i in range(0, len(ids), 1000):
                sb.rpc("refresh_lead_phones", {"p_ids": ids[i:i + 1000]}).execute()
            st.cache_data.clear()
            st.session_state["leads_key"] = None
            st.session_state["leads_done"] = (n_over, n_new)
            st.rerun()
        if no.button("Cancel", width="stretch"):
            st.rerun()

    if st.session_state.get("leads_done") is not None:
        n_over, n_new = st.session_state.pop("leads_done")
        st.success(f"Done: {plural(n_over, 'lead')} overwritten and {n_new:,} added. "
                   "The call log now uses the updated leads.")
    elif st.button(f"Confirm: upload {plural(len(ids), 'lead')}", type="primary", icon=":material/cloud_upload:"):
        confirm_leads(existing, new)


# =====================================================================================
# NAVIGATION
# =====================================================================================
nav = st.navigation({
    "Reports": [
        st.Page(page_call_report, title="Call Report", icon=":material/call:", url_path="call-report",
                default=True),
        st.Page(page_lead_search, title="Lead Search", icon=":material/person_search:", url_path="lead-search"),
    ],
    "Manage": [
        st.Page(page_contacts, title="Contacts", icon=":material/contacts:", url_path="contacts"),
        st.Page(page_upload_calls, title="Upload Calls", icon=":material/upload_file:", url_path="upload-calls"),
        st.Page(page_upload_leads, title="Upload Leads", icon=":material/group_add:", url_path="upload-leads"),
    ],
})
nav.run()
