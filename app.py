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
import html
import re
import io
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
/* ---- Call Report ---- */
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin: .4rem 0 1rem 0; }
.kpi { border: 1px solid rgba(128,128,128,0.22); border-radius: 12px; padding: 12px 16px; background: rgba(128,128,128,0.04); }
.kpi .kl { font-size: .82rem; opacity: .75; font-weight: 500; }
.kpi .kv { font-size: 1.85rem; font-weight: 700; letter-spacing: -.02em; line-height: 1.25; margin-top: 4px; }
.kpi .kd { font-size: .78rem; opacity: .6; }
.kpi.alert { border-color: rgba(245,158,11,.55); background: rgba(245,158,11,.10); }
.kpi.alert .kv { color: #b45309; }
.applied { margin: .2rem 0 .6rem 0; font-size: .92rem; display: flex; gap: .6rem; align-items: center; flex-wrap: wrap; }
.applied b { font-weight: 600; }
.sortpill { border: 1px solid rgba(128,128,128,0.25); border-radius: 20px; padding: 2px 10px; font-size: .78rem; opacity: .75; }
.halves { display: flex; gap: 0; margin: .2rem 0 0 0; overflow: hidden; font-size: .7rem; font-weight: 700; letter-spacing: .09em; }
.halves .h-call { padding: 4px 10px; opacity: .65; flex: none; }
.halves .h-lead { padding: 4px 10px; background: rgba(255,230,0,.18); color: #8a6400; border-radius: 6px 6px 0 0; flex: none; }
.lc { border: 1px solid rgba(128,128,128,0.22); border-radius: 12px; padding: 16px; margin-bottom: .6rem; }
.lc.empty { opacity: .8; border-style: dashed; }
.lc-top { display: flex; justify-content: space-between; gap: 8px; align-items: flex-start; }
.lc-id { font-size: .7rem; font-weight: 700; letter-spacing: .05em; opacity: .55; }
.lc-name { font-size: 1.15rem; font-weight: 700; margin-top: 2px; line-height: 1.3; }
.lc-meta { font-size: .85rem; opacity: .7; margin-top: 2px; }
.pillst { background: rgba(31,79,216,.10); color: #1f4fd8; border-radius: 6px; padding: 3px 8px; font-size: .75rem; font-weight: 600; white-space: nowrap; }
.lc-warn { margin-top: 10px; background: rgba(245,158,11,.12); border: 1px solid rgba(245,158,11,.45); color: #8a4b00;
           border-radius: 8px; padding: 8px 10px; font-size: .82rem; }
.lc-kv { display: grid; grid-template-columns: 105px 1fr; gap: 6px 10px; margin-top: 12px; font-size: .84rem; }
.lc-kv span:nth-child(odd) { opacity: .55; }
.ok { color: #127a4a; font-weight: 600; }
.mini { margin-top: 12px; border-top: 1px solid rgba(128,128,128,0.2); padding-top: 10px; }
.mini h4 { font-size: .82rem; font-weight: 700; margin: 0 0 6px 0; padding: 0; }
.mrow { display: flex; justify-content: space-between; gap: 8px; padding: 4px 0; font-size: .8rem;
        border-bottom: 1px dashed rgba(128,128,128,0.2); }
.mrow span:last-child, .mrow.muted { opacity: .6; }
.fresh { font-size: .78rem; line-height: 1.6; opacity: .75; }
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
# APP_PASSWORD    -> full app (role "admin")
# VIEWER_PASSWORD -> management: read-only Call Log only (role "viewer")
def password_ok() -> bool:
    try:
        admin_pw = st.secrets.get("APP_PASSWORD")
        viewer_pw = st.secrets.get("VIEWER_PASSWORD")
    except Exception:
        admin_pw = viewer_pw = None
    if st.session_state.get("authed"):
        return True
    if not admin_pw:
        st.session_state["role"] = "admin"
        return True
    st.title("Call Report")
    pw = st.text_input("Password", type="password")
    if pw:
        if hmac.compare_digest(pw, str(admin_pw)):
            st.session_state.update(authed=True, role="admin")
            st.rerun()
        if viewer_pw and hmac.compare_digest(pw, str(viewer_pw)):
            st.session_state.update(authed=True, role="viewer")
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


@st.cache_data(ttl=600, show_spinner=False)
def load_range_sources(start: date, end: date, started_from=None) -> list:
    """Lead Sources of the MMS leads that match at least one call in this date range."""
    return [r["lead_source"] for r in sb.rpc("call_lead_sources", {
        "p_start": str(start), "p_end": str(end),
        "p_started_from": str(started_from) if started_from else None}).execute().data]


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


def to_excel(df: pd.DataFrame, sheet: str = "Call Report"):
    """Excel file with Date/Time as real dates shown as 09/30/2026 02:58 PM.
    Returns None if openpyxl isn't installed."""
    try:
        import openpyxl  # noqa: F401
        from openpyxl.utils import get_column_letter
    except ImportError:
        return None
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl", datetime_format="mm/dd/yyyy hh:mm AM/PM") as w:
        df.to_excel(w, index=False, sheet_name=sheet)
        ws = w.sheets[sheet]
        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions
        for i, col in enumerate(df.columns, start=1):
            width = max([len(str(col))] + [len(str(v)) for v in df[col].head(500)]) + 2
            ws.column_dimensions[get_column_letter(i)].width = min(max(width, 10), 45)
        if "Date/Time" in df.columns:
            letter = get_column_letter(list(df.columns).index("Date/Time") + 1)
            ws.column_dimensions[letter].width = 22
            for cell in ws[letter][1:]:  # every row under the header
                cell.number_format = "mm/dd/yyyy hh:mm AM/PM"
    return buf.getvalue()


def plural(n: int, word: str) -> str:
    return f"{n:,} {word}{'' if n == 1 else 's'}"


# =====================================================================================
# CALL REPORT
# =====================================================================================
def fmt_phone(v) -> str:
    d = "".join(ch for ch in str(v) if ch.isdigit())
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    return f"{d[:3]}-{d[3:6]}-{d[6:]}" if len(d) == 10 else str(v)


def dur_seconds(s) -> int:
    try:
        parts = [int(x) for x in str(s).strip().split(":")]
    except ValueError:
        return 0
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, sec = parts[-3:]
    return h * 3600 + m * 60 + sec


def fmt_total(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m {s:02d}s"


def fmt_short(seconds: float) -> str:
    m, s = divmod(int(round(seconds)), 60)
    return f"{m}:{s:02d}"


def us_time(t, with_date=True) -> str:  # 9/30/26 2:58 PM (works on Windows too)
    if t is None or pd.isna(t):
        return ""
    clock = f"{t.hour % 12 or 12}:{t:%M} {'AM' if t.hour < 12 else 'PM'}"
    return f"{t.month}/{t.day}/{t:%y} {clock}" if with_date else clock


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


@st.cache_data(ttl=600, show_spinner=False)
def load_needs_review(days: int) -> pd.DataFrame:
    return pd.DataFrame(sb.rpc("needs_review", {"p_days": days}).execute().data,
                        columns=["phone10", "calls", "last_call", "callers", "leads_matched"])


@st.cache_data(ttl=300, show_spinner=False)
def load_freshness() -> dict:
    data = sb.rpc("data_freshness", {}).execute().data
    return data[0] if data else {}


@st.cache_data(ttl=120, show_spinner=False)
def get_lead(lead_id: str) -> dict:
    data = sb.table("mms").select("*").eq("Lead Id", lead_id).execute().data
    return data[0] if data else {}


def _after_pick():
    load_calls.clear()
    load_needs_review.clear()


def render_pick(number: str, current_lead: str, choice: str, key: str):
    """Lead chooser for a phone number that matches several MMS leads."""
    leads = pd.DataFrame(sb.rpc("leads_for_number", {"p_phone": number}).execute().data)
    if leads.empty:
        st.info("No matching leads found.")
        return
    leads = leads.rename(columns={
        "lead_id": "Lead Id", "last_edited": "Last Edited", "media_market": "Market",
        "company_in_ad": "Company In Ad", "lead_owner": "Lead Owner", "status": "Status",
        "matched_on": "Matched On"})
    leads = leads[["Lead Id", "Market", "Company In Ad", "Lead Owner", "Status", "Last Edited", "Matched On"]]
    picked = st.dataframe(leads, hide_index=True, width="stretch", on_select="rerun",
                          selection_mode="single-row", key=f"{key}_{number}")
    rows = picked.selection.rows if picked and picked.selection else []
    c1, c2 = st.columns(2)
    if rows:
        lead = str(leads.iloc[rows[0]]["Lead Id"])
        label = f"Confirm lead {lead}" if lead == current_lead else f"Use lead {lead}"
        if c1.button(label, type="primary", width="stretch", key=f"{key}_use_{number}"):
            sb.table("lead_picks").upsert({"phone10": str(number)[-10:], "lead_id": lead,
                                           "picked_at": pd.Timestamp.now("UTC").isoformat()},
                                          on_conflict="phone10").execute()
            _after_pick()
            st.rerun()
    else:
        c1.button("Click a lead above first", disabled=True, width="stretch", key=f"{key}_dis_{number}")
    if choice == "Picked" and c2.button("Undo pick (back to automatic)", width="stretch",
                                        key=f"{key}_undo_{number}"):
        sb.table("lead_picks").delete().eq("phone10", str(number)[-10:]).execute()
        _after_pick()
        st.rerun()


@st.dialog("Change lead", width="large")
def pick_lead_dialog(number: str, current_lead: str, choice: str):
    st.write(f"**{fmt_phone(number)}** matches several MMS leads. Currently showing **{current_lead}** "
             f"({(choice or 'only match').lower()}). Click a lead, then **Use lead**. "
             "The choice applies to every call to this number.")
    render_pick(number, current_lead, choice, "dlg")


# ---------- filters (only take effect when Apply is pressed) ----------
DATE_PRESETS = ["Yesterday", "Last 7 days", "This month", "Custom"]
DIRECTIONS = {"All": "All", "Out": "outbound", "In": "inbound"}
SHOW_OPTIONS = ["All", "Matched", "Not found", "Needs pick"]


def _date_range(preset: str, custom):
    today = date.today()
    if preset == "Last 7 days":
        return today - timedelta(days=6), today
    if preset == "This month":
        return today.replace(day=1), today
    if preset == "Custom" and isinstance(custom, (list, tuple)) and len(custom) == 2:
        return custom[0], custom[1]
    y = today - timedelta(days=1)
    return y, y


def _filter_defaults() -> dict:
    y = date.today() - timedelta(days=1)
    return {"f_preset": "Yesterday", "f_dates": (y, y), "f_from": [], "f_direction": "All",
            "f_sources": [], "f_started_from": None, "f_show": "All"}


FILTER_KEYS = list(_filter_defaults())
ALL_REPS = "All reps"


def _reset_filters():
    defaults = _filter_defaults()
    for k, v in defaults.items():
        st.session_state[k] = v
    st.session_state["applied"] = defaults
    st.session_state["rep_pick"] = ALL_REPS


def _apply_filters():
    if st.session_state.get("f_preset") == "Custom":
        custom = st.session_state.get("f_dates")
        if not isinstance(custom, (list, tuple)) or len(custom) != 2:
            st.session_state["apply_error"] = "Pick both a start and an end date for the custom range."
            return
    st.session_state["applied"] = {k: st.session_state.get(k) for k in FILTER_KEYS}


def match_label(row) -> str:
    if row["Lead Id"] == "Not Found":
        return "— Not found"
    n = int(row["Leads Matched"] or 0)
    if row["Lead Choice"] == "Picked":
        return "✓ Picked"
    if n >= 2:
        return f"⚑ Pick 1 of {n}"
    return "✓ 1 lead"


def kpi_cards(cards: list):
    html_cards = "".join(
        f'<div class="kpi{" alert" if c.get("alert") else ""}"><div class="kl">{c["label"]}</div>'
        f'<div class="kv">{c["value"]}</div><div class="kd">{c.get("note", "")}</div></div>' for c in cards)
    st.markdown(f'<div class="kpis">{html_cards}</div>', unsafe_allow_html=True)


def lead_card(r, df: pd.DataFrame):
    """Right-hand panel for the selected call."""
    number = str(r["To"])
    if r["Lead Id"] == "Not Found":
        st.markdown(f'<div class="lc"><div class="lc-id">NO MMS LEAD FOUND</div>'
                    f'<div class="lc-name">{fmt_phone(number)}</div>'
                    f'<div class="lc-meta">This number isn\'t in any of the searched MMS columns.</div></div>',
                    unsafe_allow_html=True)
        if st.button("Search MMS for this number", icon=":material/person_search:", width="stretch"):
            st.session_state["ls_q"] = number
            st.switch_page(PAGE_LEAD_SEARCH)
        return
    lead_id = str(r["Lead Id"])
    rec = get_lead(lead_id)
    n_leads = int(r["Leads Matched"] or 0)
    owner_note = ' <span class="ok">· matches caller</span>' if r["Lead Choice"] == "Rep's lead" else ""
    rows = [("Owner", esc(rec.get("Lead Owner")) + owner_note),
            ("Lead started", esc(rec.get("Lead Started"))),
            ("Last edited", esc(rec.get("Last Edited"))),
            ("Phone in ad", esc(fmt_phone(rec.get("Phone Number In Ad") or "")) if rec.get("Phone Number In Ad") else ""),
            ("Contact phone", esc(rec.get("Contact Phone (phase2)"))),
            ("Found in", esc(r["Matched On"]))]
    kv = "".join(f"<span>{k}</span><span>{v}</span>" for k, v in rows if v)
    warn = ""
    if n_leads >= 2 and r["Lead Choice"] != "Picked":
        how = "the caller's own lead" if r["Lead Choice"] == "Rep's lead" else "the most recently edited lead"
        warn = (f'<div class="lc-warn">⚑ This number matches <b>{n_leads} leads</b>. Showing {how} — '
                f'use <b>Change lead</b> to pick the right one.</div>')
    status = f'<span class="pillst">{esc(rec.get("Status"))}</span>' if rec.get("Status") else ""
    calls = df[df["To"] == r["To"]].sort_values("Date/Time", ascending=False)
    call_rows = "".join(
        f'<div class="mrow"><span>{us_time(c["Date/Time"])} · {esc(c["From"])}</span><span>{esc(c["Duration"])}</span></div>'
        for _, c in calls.head(8).iterrows())
    more = f'<div class="mrow muted">+ {len(calls) - 8} more</div>' if len(calls) > 8 else ""
    st.markdown(
        f'<div class="lc"><div class="lc-top"><div><div class="lc-id">LEAD {esc(lead_id)} · '
        f'{esc((rec.get("Lead Source") or "").upper())}</div>'
        f'<div class="lc-name">{esc(rec.get("Company In Ad") or rec.get("Company (phase2)") or "")}</div>'
        f'<div class="lc-meta">{esc(" · ".join(x for x in [rec.get("Contact Name (phase2)"), rec.get("Media Market")] if x))}</div>'
        f'</div>{status}</div>{warn}<div class="lc-kv">{kv}</div>'
        f'<div class="mini"><h4>Calls to this number in this range ({len(calls)})</h4>{call_rows}{more}</div></div>',
        unsafe_allow_html=True)
    b1, b2 = st.columns(2)
    if b1.button("Open full lead", width="stretch", key=f"open_{lead_id}"):
        st.session_state["ls_q"] = lead_id
        st.switch_page(PAGE_LEAD_SEARCH)
    if b2.button("Change lead", width="stretch", key=f"chg_{r['call_id']}", disabled=n_leads < 2,
                 help=None if n_leads >= 2 else "This number only matches one lead"):
        pick_lead_dialog(number, lead_id, str(r["Lead Choice"]))


def page_call_report():
    for k, v in _filter_defaults().items():  # first visit: start every filter at its default
        st.session_state.setdefault(k, v)
    st.session_state.setdefault("applied", _filter_defaults())
    a = {**_filter_defaults(), **st.session_state["applied"]}
    start, end = _date_range(a["f_preset"], a["f_dates"])
    sources = a["f_sources"] or []
    started_from = a["f_started_from"]
    direction = a["f_direction"] or "All"
    show = a["f_show"] or "All"

    df = load_calls(start, end, tuple(sorted(sources)), started_from)
    if not df.empty:
        df = apply_rep_names(df)
        df["Times Called"] = df.groupby("To")["To"].transform("count").astype(int)
        df["Leads Matched"] = pd.to_numeric(df["Leads Matched"], errors="coerce").fillna(0).astype(int)

    # Lead Source dropdown only lists sources of leads matched to calls in the applied date range.
    try:
        source_options = load_range_sources(start, end, started_from)
    except Exception:
        source_options = load_lead_sources()
    st.session_state["f_sources"] = [x for x in (st.session_state.get("f_sources") or []) if x in source_options]

    # ---------- header ----------
    h1, h2 = st.columns([3, 1.3], vertical_alignment="bottom")
    with h1:
        st.title("Call Report")
        st.caption("Every call, matched to its MMS lead. Set filters, then **Apply filters**.")
    dl_slot = h2.container()

    # ---------- filter bar ----------
    with st.form("call_filters"):
        r1 = st.columns([2.4, 1.5, 1.2])
        r1[0].segmented_control("Dates", DATE_PRESETS, key="f_preset")
        r1[1].date_input("Custom range", key="f_dates", format="MM/DD/YYYY",
                         help="Used when Dates is set to Custom")
        r1[2].segmented_control("Direction", list(DIRECTIONS), key="f_direction")
        r2 = st.columns([2.4, 1.5, 3.0])
        r2[0].multiselect("Lead Source", source_options, key="f_sources", placeholder="All sources",
                          help="Only match calls to MMS leads from these sources. Lists the sources "
                               "found for the applied date range.")
        r2[1].date_input("Lead started from", key="f_started_from", format="MM/DD/YYYY",
                         help="Only match calls to MMS leads started on or after this date")
        r2[2].segmented_control("Show", SHOW_OPTIONS, key="f_show")
        r3 = st.columns([4.6, 1, 1.3], vertical_alignment="bottom")
        r3[1].form_submit_button("Reset", width="stretch", on_click=_reset_filters)
        r3[2].form_submit_button("Apply filters", type="primary", icon=":material/filter_alt:",
                                 width="stretch", on_click=_apply_filters)
    err = st.session_state.pop("apply_error", None)
    if err:
        st.warning(err)

    # ---------- calls for the applied filters (before picking a rep) ----------
    pre = df.copy()
    if not pre.empty:
        if direction != "All":
            pre = pre[pre["Direction"].fillna("").str.lower() == DIRECTIONS[direction]]
        needs_pre = (pre["Leads Matched"] >= 2) & (pre["Lead Choice"] != "Picked")
        if show == "Matched":
            pre = pre[pre["Lead Id"] != "Not Found"]
        elif show == "Not found":
            pre = pre[pre["Lead Id"] == "Not Found"]
        elif show == "Needs pick":
            pre = pre[needs_pre.reindex(pre.index, fill_value=False)]

    # ---------- rep buttons: only reps with calls under the applied filters ----------
    rep_counts = (pre["From"].dropna().astype(str).value_counts() if not pre.empty
                  else pd.Series(dtype=int))
    rep_options = [ALL_REPS] + sorted(rep_counts.index, key=str.lower)
    if st.session_state.get("rep_pick") not in rep_options:
        st.session_state["rep_pick"] = ALL_REPS
    if len(rep_options) > 1:
        st.pills("Rep", rep_options, key="rep_pick", selection_mode="single",
                 format_func=lambda r: f"{r}  ·  {len(pre):,}" if r == ALL_REPS
                 else f"{r}  ·  {int(rep_counts[r]):,}",
                 help="Reps with calls under the current filters. Click one to show only their calls.")
    rep_pick = st.session_state.get("rep_pick") or ALL_REPS
    froms = [] if rep_pick == ALL_REPS else [rep_pick]

    # ---------- what's applied ----------
    bits = [", ".join(froms) if froms else "All reps"]
    if direction != "All":
        bits.append("Outbound only" if direction == "Out" else "Inbound only")
    if sources:
        bits.append(", ".join(sources))
    if started_from:
        bits.append(f"Leads started from {started_from:%m/%d/%Y}")
    if show != "All":
        bits.append(show)
    when = f"{start:%m/%d/%Y}" if start == end else f"{start:%m/%d/%Y} – {end:%m/%d/%Y}"
    bits.append(when)
    st.markdown(f'<div class="applied">Showing <b>{esc(" · ".join(bits))}</b>'
                f'<span class="sortpill">Sorted by Rep → Market → Source → Lead Id → Time</span></div>',
                unsafe_allow_html=True)

    if df.empty:
        lead_filter = " and ".join(x for x in [
            f"from {', '.join(sources)}" if sources else "",
            f"started on or after {started_from:%m/%d/%Y}" if started_from else ""] if x)
        st.warning("No calls in this date range" + (f" match a lead {lead_filter}." if lead_filter else "."))
        return

    view = pre[pre["From"].astype(str).isin(froms)] if froms else pre

    # ---------- counters ----------
    secs = view["Duration"].map(dur_seconds)
    out_n = int(view["Direction"].fillna("").str.lower().eq("outbound").sum())
    in_n = int(view["Direction"].fillna("").str.lower().eq("inbound").sum())
    uniq = view["To"].nunique()
    matched = int((view["Lead Id"] != "Not Found").sum())
    needs_n = view.loc[(view["Leads Matched"] >= 2) & (view["Lead Choice"] != "Picked"), "To"].nunique()
    called3 = view.loc[view["Times Called"] >= 3, "To"].nunique()
    kpi_cards([
        {"label": "Total calls", "value": f"{len(view):,}", "note": f"{out_n:,} outbound · {in_n:,} inbound"},
        {"label": "Unique numbers", "value": f"{uniq:,}",
         "note": f"{len(view) / uniq:.1f} calls per number" if uniq else ""},
        {"label": "Matched to a lead", "value": f"{matched:,}",
         "note": f"{matched / len(view):.0%} of calls · {len(view) - matched:,} not found" if len(view) else ""},
        {"label": "Talk time", "value": fmt_total(secs.sum()),
         "note": f"avg {fmt_short(secs.mean())} per call" if len(view) else ""},
        {"label": "Called 3+ times", "value": f"{called3:,}", "note": "numbers in this range"},
        {"label": "⚠ Needs a lead picked", "value": f"{needs_n:,}", "note": "numbers match 2+ leads",
         "alert": needs_n > 0},
    ])

    if view.empty:
        st.info("No calls match these filters.")
        return

    # ---------- table data ----------
    def _sort_key(col: pd.Series) -> pd.Series:
        if col.name == "Lead Id":
            return pd.to_numeric(col, errors="coerce")  # "Not Found" goes to the bottom of each group
        if col.name == "Date/Time":
            return col
        return col.astype("string").str.lower()

    view = view.sort_values(["From", "Media Market", "Lead Source", "Lead Id", "Date/Time"],
                            key=_sort_key, na_position="last", kind="stable").reset_index(drop=True)
    view["Match"] = view.apply(match_label, axis=1)

    # downloads (full detail) in the header
    full = view[CALL_COLS + LEAD_COLS].copy()
    export = full.copy()
    export["Date/Time"] = export["Date/Time"].map(us_time)
    with dl_slot:
        d1, d2 = st.columns(2)
        d1.download_button("CSV", export.to_csv(index=False).encode("utf-8"),
                           file_name=f"call_report_{start}_{end}.csv", mime="text/csv",
                           icon=":material/download:", width="stretch")
        xlsx = to_excel(full)
        if xlsx:
            d2.download_button("Download Excel", xlsx, file_name=f"call_report_{start}_{end}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               icon=":material/table_view:", type="primary", width="stretch")

    left, right = st.columns([3.3, 1], gap="medium")
    with left:
        n_leads = view.loc[view["Lead Id"] != "Not Found", "Lead Id"].nunique()
        n_reps = view["From"].nunique()
        t_all, t_lead, t_rep = st.tabs([f"All calls  {len(view):,}", f"Grouped by lead  {n_leads:,}",
                                        f"Grouped by rep  {n_reps:,}"])
        with t_all:
            show_all = st.toggle("Show all columns", key="all_cols")
            call_cols = {"Date/Time": "Time", "From": "Rep", "To": "To",
                         "Duration": "Dur.", "Times Called": "Times"}
            lead_cols = {"Lead Id": "Lead", "Lead Source": "Lead Source", "Company In Ad": "Company", "Lead Owner": "Owner",
                         "Status": "Status", "Match": "Match"}
            if show_all:
                call_cols = {"Direction": "Direction", **call_cols, "Ext / ID": "Ext"}
                lead_cols = {**lead_cols, "Lead Started": "Lead Started", "Last Edited": "Last Edited",
                             "Media Market": "Market",
                             "Contact Name (phase2)": "Contact", "Phase2 Completed": "Phase2 Completed",
                             "Matched On": "Matched On", "Leads Matched": "Leads Matched"}
            table = view[list(call_cols) + list(lead_cols)].rename(columns={**call_cols, **lead_cols})
            table["To"] = table["To"].map(fmt_phone)
            lead_names = list(lead_cols.values())
            widths = {"Time": 114, "Rep": 122, "To": 100, "Dur.": 56, "Times": 54, "Direction": 80, "Ext": 70,
                      "Lead": 72, "Company": 132, "Owner": 120, "Status": 100, "Match": 104,
                      "Lead Started": 100, "Last Edited": 140, "Lead Source": 102, "Market": 110,
                      "Contact": 130, "Phase2 Completed": 140, "Matched On": 170, "Leads Matched": 100}
            call_w = sum(widths[c] for c in call_cols.values()) + 33  # + row checkbox column
            lead_w = sum(widths[c] for c in lead_cols.values())
            st.markdown(f'<div class="halves"><div class="h-call" style="width:{call_w}px">THE CALL</div>'
                        f'<div class="h-lead" style="width:{lead_w}px">MATCHED MMS LEAD</div></div>',
                        unsafe_allow_html=True)
            if len(table) <= 10000:
                styled = (table.style
                          .set_properties(subset=lead_names, **{"background-color": "rgba(255, 230, 0, 0.12)"})
                          .map(lambda v: "background-color: rgba(220, 38, 38, 0.14); color: #b42318; font-weight: 700"
                               if v >= 3 else "", subset=["Times"])
                          .map(lambda v: ("background-color: rgba(245, 158, 11, 0.22); color: #8a4b00; font-weight: 700"
                                          if str(v).startswith("⚑") else
                                          "color: #127a4a; font-weight: 600" if str(v).startswith("✓") else
                                          "color: #8a92a3; font-style: italic"), subset=["Match"]))
                if "Leads Matched" in table.columns:
                    styled = styled.format({"Leads Matched": "{:d}", "Times": "{:d}"})
                else:
                    styled = styled.format({"Times": "{:d}"})
            else:
                styled = table
            event = st.dataframe(
                styled, key="calls_table", width="stretch", hide_index=True,
                height=min(40 + 35 * len(table), 600),
                on_select="rerun", selection_mode="single-row",
                column_config={
                    **{c: st.column_config.Column(width=widths[c]) for c in table.columns if c in widths},
                    "Time": st.column_config.DatetimeColumn(format="M/D/YY h:mm A", width=widths["Time"]),
                    "Times": st.column_config.NumberColumn(width=widths["Times"]),
                    "Match": st.column_config.TextColumn(
                        width=widths["Match"],
                        help="✓ = lead confirmed · ⚑ Pick = number matches several leads; "
                             "click the row, then Change lead")})
            st.caption(f"{len(view):,} calls · click a row to see its lead on the right")
        with t_lead:
            g = view[view["Lead Id"] != "Not Found"].groupby("Lead Id").agg(
                Company=("Company In Ad", "first"), Owner=("Lead Owner", "first"), Status=("Status", "first"),
                Source=("Lead Source", "first"), Calls=("To", "size"), Numbers=("To", "nunique"),
                Reps=("From", lambda s: ", ".join(sorted(set(s.dropna().astype(str))))),
                Last_call=("Date/Time", "max")).reset_index().sort_values("Calls", ascending=False)
            g = g.rename(columns={"Lead Id": "Lead", "Last_call": "Last call"})
            st.dataframe(g, hide_index=True, width="stretch", height=560,
                         column_config={"Last call": DT_FMT})
        with t_rep:
            v2 = view.assign(_secs=view["Duration"].map(dur_seconds),
                             _out=view["Direction"].fillna("").str.lower().eq("outbound"),
                             _in=view["Direction"].fillna("").str.lower().eq("inbound"),
                             _match=view["Lead Id"] != "Not Found",
                             _needs=(view["Leads Matched"] >= 2) & (view["Lead Choice"] != "Picked"))
            g = v2.groupby("From").agg(Calls=("To", "size"), Outbound=("_out", "sum"), Inbound=("_in", "sum"),
                                       Numbers=("To", "nunique"), Matched=("_match", "mean"),
                                       Talk=("_secs", "sum"), Needs_pick=("_needs", "sum")).reset_index()
            g["Matched"] = (g["Matched"] * 100).round(0).astype(int).astype(str) + "%"
            g["Talk"] = g["Talk"].map(fmt_total)
            g = g.rename(columns={"From": "Rep", "Talk": "Talk time", "Needs_pick": "Needs pick"}) \
                 .sort_values("Calls", ascending=False)
            st.dataframe(g, hide_index=True, width="stretch")

    with right:
        sel = event.selection.rows if event and event.selection else []
        if sel and sel[0] < len(view):
            lead_card(view.iloc[sel[0]], df)
        else:
            st.markdown('<div class="lc empty"><div class="lc-name">Click a call</div>'
                        '<div class="lc-meta">Select any row in the table to see its MMS lead here, '
                        'every call to that number, and to change the lead if it matches several.</div></div>',
                        unsafe_allow_html=True)


# =====================================================================================
# NEEDS REVIEW
# =====================================================================================
def page_needs_review():
    st.title("Needs Review")
    st.caption("Numbers that match 2 or more MMS leads and still need the right lead picked. "
               "Once you pick one it drops off this list and every call to that number uses it.")
    span = st.segmented_control("Called in the last", ["7 days", "30 days", "90 days"], default="30 days",
                                key="nr_days") or "30 days"
    days = int(span.split()[0])
    data = load_needs_review(days)
    if data.empty:
        st.success("All caught up — every multi-lead number called in this period has a lead picked.")
        return
    # caller names (latest name for each extension / username)
    c = load_contacts()
    c = c[c["rep"].fillna("").str.strip() != ""].sort_values("effective_from")
    names = c.groupby("from_value")["rep"].last().to_dict()
    data = data.copy()
    data["Number"] = data["phone10"].map(fmt_phone)
    data["Called by"] = data["callers"].map(
        lambda xs: ", ".join(sorted({names.get(x, x) for x in (xs or [])})))
    data["Last call"] = pd.to_datetime(data["last_call"])
    table = data[["Number", "calls", "Last call", "Called by", "leads_matched"]].rename(
        columns={"calls": "Calls", "leads_matched": "Leads matched"})

    kpi_cards([
        {"label": "Numbers to review", "value": f"{len(data):,}", "note": f"called in the last {days} days",
         "alert": True},
        {"label": "Calls affected", "value": f"{int(data['calls'].sum()):,}", "note": "calls to these numbers"},
        {"label": "Most leads on one number", "value": f"{int(data['leads_matched'].max()):,}",
         "note": "matching MMS leads"},
    ])
    left, right = st.columns([1.7, 2], gap="medium")
    with left:
        ev = st.dataframe(table, hide_index=True, width="stretch", height=min(40 + 35 * len(table), 600),
                          on_select="rerun", selection_mode="single-row", key=f"nr_table_{days}",
                          column_config={"Last call": st.column_config.DatetimeColumn(format="M/D/YY h:mm A", width=125),
                                         "Number": st.column_config.Column(width=105),
                                         "Calls": st.column_config.NumberColumn(width=55),
                                         "Leads matched": st.column_config.NumberColumn("Leads", width=55)})
        st.caption("Sorted by most calls first · click a number to pick its lead")
    with right:
        sel = ev.selection.rows if ev and ev.selection else []
        if not sel:
            st.markdown('<div class="lc empty"><div class="lc-name">Pick a number</div>'
                        '<div class="lc-meta">Click a number on the left to see every MMS lead it matches, '
                        'then choose the right one.</div></div>', unsafe_allow_html=True)
            return
        row = data.iloc[sel[0]]
        st.subheader(f"{row['Number']} · {plural(int(row['leads_matched']), 'matching lead')}")
        st.caption(f"{plural(int(row['calls']), 'call')} · called by {row['Called by'] or 'unknown'}. "
                   "Click the right lead, then **Use lead**.")
        render_pick(str(row["phone10"]), "", "", "nr")


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


@st.cache_data(ttl=300, show_spinner="Searching MMS...")
def search_mms(q: str):
    """Every MMS lead with the search text in ANY column (phone numbers match in any format).
    Returns (leads table, {lead id: [matched columns]}, total found)."""
    data = sb.rpc("search_mms", {"p_q": q, "p_limit": 1000}).execute().data
    if not data:
        return pd.DataFrame(columns=MMS_COLS), {}, 0
    recs = pd.DataFrame([d["rec"] for d in data])
    for c in MMS_COLS:
        if c not in recs.columns:
            recs[c] = None
    recs = recs[MMS_COLS]
    matched = {str(d["lead_id"]): list(d["matched_cols"] or []) for d in data}
    recs.insert(1, "Matched In", [", ".join(matched.get(str(i), [])) for i in recs["Lead Id"]])
    return recs, matched, int(data[0].get("total_found") or len(data))


def _edits(a: str, b: str) -> int:
    """Number of single-letter changes to turn a into b (Levenshtein)."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _word_ok(typed: str, word: str, last: bool) -> bool:
    """A typed word matches a word in the cell: exact, or 1 typo if 4+ letters.
    The last typed word may be the start of a longer word (net -> network)."""
    allowed = 0 if len(typed) < 4 else 1
    if typed == word or (last and word.startswith(typed)):
        return True
    if allowed and _edits(typed, word) <= allowed:
        return True
    if last and allowed and len(word) > len(typed):
        return min(_edits(typed, word[:n]) for n in (len(typed) - 1, len(typed), len(typed) + 1)) <= allowed
    return False


def close_phrase_match(query: str, text) -> bool:
    """True if the typed words appear in the cell next to each other, in the same order,
    allowing a small typo per word (e.g. 'Advanced Net' -> 'Merchant Advance Network')."""
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return False
    q = re.findall(r"[a-z0-9@.]+", query.lower())
    w = re.findall(r"[a-z0-9@.]+", str(text).lower())
    if not q or len(w) < len(q):
        return False
    for start in range(len(w) - len(q) + 1):
        if all(_word_ok(q[k], w[start + k], k == len(q) - 1) for k in range(len(q))):
            return True
    return False


@st.cache_data(ttl=300, show_spinner="Looking for close matches...")
def search_mms_close(q: str):
    """Spelling-tolerant fallback: same words, same order, small typos allowed."""
    data = sb.rpc("search_mms_close", {"p_q": q, "p_limit": 1000}).execute().data or []
    kept = []
    for d in data:
        rec = d["rec"] or {}
        cols = [c for c in MMS_COLS if c in rec and close_phrase_match(q, rec[c])]
        if cols:
            kept.append({**d, "matched_cols": cols})
    data = kept
    if not data:
        return pd.DataFrame(columns=MMS_COLS), {}, 0
    recs = pd.DataFrame([d["rec"] for d in data])
    for c in MMS_COLS:
        if c not in recs.columns:
            recs[c] = None
    recs = recs[MMS_COLS]
    matched = {str(d["lead_id"]): list(d["matched_cols"] or []) for d in data}
    recs.insert(1, "Matched In", [", ".join(matched.get(str(i), [])) for i in recs["Lead Id"]])
    return recs, matched, len(data)


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


def _field_block(title: str, rec: dict, fields: list, hits=()):
    with st.container(border=True):
        st.markdown(f"**{title}**")
        hl = "background:#e53935;color:#fff;border-radius:4px;padding:1px 5px"
        lines = [f"<span style='opacity:.6'>{f.replace(' (phase2)', '').replace(' (phase3)', '')}</span>"
                 f"<br><span style='{hl if f in hits else ''}'>{esc(rec.get(f))}</span>"
                 for f in fields if rec.get(f) not in (None, "")]
        st.markdown("".join(f"<div style='margin-bottom:.55rem;line-height:1.35'>{l}</div>" for l in lines) or
                    "<span style='opacity:.5'>Nothing recorded</span>", unsafe_allow_html=True)


def page_lead_search():
    st.title("Lead Search")
    st.markdown('<div class="page-sub">Search the MMS lead table</div>', unsafe_allow_html=True)
    st.caption("Type anything: a Lead Id, a phone number in any format, a name, company, email, market, "
               "status... Every MMS column is searched and every matching lead is listed. "
               "Matching cells are highlighted in red.")
    q = st.text_input("Search MMS", key="ls_q", label_visibility="collapsed", icon=":material/search:",
                      placeholder="e.g. 171876  ·  (702) 727-7777  ·  Merchant Advance  ·  name@company.com")
    if not q.strip():
        return
    if len(q.strip()) < 2:
        st.info("Type at least 2 characters.")
        return

    results, matched, total = search_mms(q.strip())
    close = False
    if results.empty and any(ch.isalpha() for ch in q):
        results, matched, total = search_mms_close(q.strip())
        close = not results.empty
    if results.empty:
        st.warning(f"No leads in MMS match **{q.strip()}**, and nothing is spelled close to it.")
        return
    if close:
        st.info(f"No exact match for **{q.strip()}**. Showing close spellings instead: the same words in the "
                "same order, with a small typo allowed in each word.", icon=":material/spellcheck:")

    # which columns matched, and how often
    col_counts = pd.Series([c for cols in matched.values() for c in cols]).value_counts()
    chips = "".join(f"<span class='mchip'>{esc(c)} <b>{n:,}</b></span>" for c, n in col_counts.items())
    st.markdown("<style>.mchip{display:inline-block;background:rgba(229,57,53,.12);border:1px solid "
                "rgba(229,57,53,.45);border-radius:14px;padding:2px 10px;margin:0 6px 6px 0;font-size:.82rem}"
                "</style>"
                f"<div style='margin:.2rem 0 .4rem 0'><span style='opacity:.7;margin-right:6px'>Found in:</span>"
                f"{chips}</div>", unsafe_allow_html=True)

    t1, t2 = st.columns([3, 1.2], vertical_alignment="center")
    note = (f" Showing the {len(results):,} most recently edited. Type more to narrow it down."
            if total > len(results) else "")
    t1.caption(f"**{plural(total, 'lead')}** found.{note} Click a lead to see the full record and its calls.")
    only_hit_cols = t2.toggle("Only columns with matches", value=False)

    # matched columns come right after "Matched In" so the red cells are visible without scrolling
    hit_cols = [c for c in MMS_COLS if c in col_counts.index and c != "Lead Id"]
    keep = ["Lead Id", "Matched In"] + hit_cols
    if only_hit_cols:
        keep += [c for c in ["Company In Ad", "Lead Owner", "Status"] if c not in keep]
    else:
        keep += [c for c in MMS_COLS if c not in keep]
    show = results[keep].fillna("")

    hit_css = "background-color: #e53935; color: white; font-weight: 600"

    def _highlight(frame: pd.DataFrame) -> pd.DataFrame:
        css = pd.DataFrame("", index=frame.index, columns=frame.columns)
        for i in frame.index:
            for c in matched.get(str(frame.at[i, "Lead Id"]), []):
                if c in css.columns:
                    css.at[i, c] = hit_css
        return css

    styled = show.reset_index(drop=True).style.apply(_highlight, axis=None)
    event = st.dataframe(styled, hide_index=True, width="stretch", on_select="rerun",
                         selection_mode="single-row", key=f"ls_table_{q.strip()}_{only_hit_cols}",
                         height=min(38 + 35 * len(show), 520),
                         column_config={"Matched In": st.column_config.TextColumn(width="medium",
                                        help="The columns where your search was found")})
    try:
        buf = io.BytesIO()
        results.fillna("").reset_index(drop=True).style.apply(_highlight, axis=None).to_excel(
            buf, index=False, sheet_name="Lead Search", engine="openpyxl")
        st.download_button("Download results (Excel, highlighted)", buf.getvalue(),
                           file_name=f"lead_search_{re.sub(r'[^A-Za-z0-9]+', '_', q.strip())[:40]}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           icon=":material/table_view:")
    except Exception:
        pass

    sel = event.selection.rows if event and event.selection else []
    if not sel and len(results) == 1:
        sel = [0]
    if not sel:
        return
    results = show.reset_index(drop=True)

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
                _field_block(title, rec, fields, matched.get(lead_id, []))
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


def team_editor(contacts: pd.DataFrame):
    """Admin: choose which reps belong to each team (used by the Call Log's Team filter)."""
    teams = load_rep_teams()
    names = sorted({str(x).strip() for x in contacts["rep"].dropna() if str(x).strip()} |
                   {r for members in teams.values() for r in members}, key=str.lower)
    with st.expander(f"Teams · {', '.join(f'{t} ({len(m)})' for t, m in sorted(teams.items())) or 'none yet'}",
                     icon=":material/groups:"):
        st.caption("Teams appear as filters on the Call Log. Add or remove reps here; new reps show up in the "
                   "list once they're added above.")
        for t in sorted(teams):
            c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
            picked = c1.multiselect(t, names, default=sorted(teams[t], key=str.lower), key=f"team_{t}")
            if c2.button("Save", key=f"team_save_{t}", type="primary", width="stretch",
                         disabled=set(picked) == teams[t]):
                for r in teams[t] - set(picked):
                    sb.table("rep_teams").delete().eq("team", t).eq("rep", r).execute()
                new = [{"team": t, "rep": r} for r in set(picked) - teams[t]]
                if new:
                    sb.table("rep_teams").insert(new).execute()
                st.cache_data.clear()
                st.rerun()
        c1, c2 = st.columns([4, 1], vertical_alignment="bottom")
        new_team = c1.text_input("New team name", placeholder="e.g. Political Team")
        if c2.button("Create", width="stretch", disabled=not new_team.strip()):
            st.session_state["new_team_pending"] = new_team.strip()
        pending = st.session_state.get("new_team_pending")
        if pending:
            members = st.multiselect(f"Reps in {pending}", names, key="new_team_members")
            if st.button(f"Save {pending}", type="primary", disabled=not members):
                sb.table("rep_teams").insert([{"team": pending, "rep": r} for r in members]).execute()
                st.session_state.pop("new_team_pending", None)
                st.cache_data.clear()
                st.rerun()


def page_contacts():
    st.title("Contacts")
    st.markdown('<div class="page-sub">Who each extension belongs to</div>', unsafe_allow_html=True)
    st.caption("Edit a name and press Enter to rename it. Use Assign New when an extension changes hands. "
               "MMS Owner Name is only needed when the person's name is spelled differently in MMS.")
    contacts = load_contacts()
    team_editor(contacts)
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
# ATT CALLS + TOLL ROUTING MASTER
# =====================================================================================
ATT_COLS = ["ID", "Week", "Connect Date", "Connect Time", "Number", "Toll Dialed", "Routing Number",
            "Time", "Time(Secs)", "ATT", "State", "Source", "Point To", "Transfer", "Caller"]
ATT_PHONE_COLS = ["Number", "Toll Dialed", "Routing Number", "Point To"]
ATT_SHOW = ["All", "Matches master", "Differs", "Not in master"]
OTHER_STATES = "(Any other state)"
US_STATES = ["AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI", "IA", "ID", "IL", "IN",
             "KS", "KY", "LA", "MA", "MD", "ME", "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ",
             "NM", "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VT", "WA",
             "WI", "WV", "WY", "PR", "VI", "GU", "ON", "QC"]


def digits10(v) -> str:
    """Any phone format -> last 10 digits ('' if not a phone)."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    d = re.sub(r"\D", "", re.sub(r"\.0$", "", str(v)))
    return d[-10:] if len(d) >= 10 else ""


@st.cache_data(ttl=600, show_spinner="Loading ATT calls...")
def load_att(start: date = None, end: date = None) -> pd.DataFrame:
    """ATT calls between start and end (inclusive). Connect Date is stored as text (10/9/2026),
    so the dates in the range are listed and fetched in chunks."""
    end = end or date.today()
    start = start or (end - timedelta(days=89))
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    rows = []
    for i in range(0, len(days), 31):
        chunk = [f"{d.month}/{d.day}/{d.year}" for d in days[i:i + 31]]
        offset = 0
        while True:
            data = (sb.table("ATT").select("*").in_("Connect Date", chunk).order("ID")
                    .range(offset, offset + 999).execute().data)
            rows.extend(data)
            if len(data) < 1000:
                break
            offset += 1000
    df = pd.DataFrame(rows, columns=ATT_COLS)
    df["_date"] = pd.to_datetime(df["Connect Date"], format="%m/%d/%Y", errors="coerce").dt.date
    df["_time"] = pd.to_datetime(df["Connect Time"], format="%H:%M:%S", errors="coerce").dt.time
    df["_toll"] = df["Toll Dialed"].map(digits10)
    df["_state"] = df["State"].fillna("").astype(str).str.strip().str.upper()
    df["_pt"] = df["Point To"].map(digits10)
    df["_num"] = df["Number"].map(digits10)
    df["Source"] = df["Source"].fillna("").astype(str).str.strip()
    return df


@st.cache_data(ttl=600, show_spinner=False)
def load_routing() -> pd.DataFrame:
    data = sb.table("toll_routing").select("id, toll, state, point_to, effective_from").execute().data
    out = pd.DataFrame(data, columns=["id", "toll", "state", "point_to", "effective_from"])
    out["effective_from"] = pd.to_datetime(out["effective_from"]).dt.date
    out["state"] = out["state"].fillna("")
    return out


@st.cache_data(ttl=600, show_spinner=False)
def load_toll_sources() -> pd.DataFrame:
    data = sb.table("toll_sources").select("id, toll, source, group_name, effective_from").execute().data
    out = pd.DataFrame(data, columns=["id", "toll", "source", "group_name", "effective_from"])
    out["effective_from"] = pd.to_datetime(out["effective_from"]).dt.date
    return out


@st.cache_data(ttl=120, show_spinner=False)
def load_att_file_log() -> pd.DataFrame:
    data = (sb.table("att_file_log").select("*").order("loaded_at", desc=True).limit(500).execute().data)
    return pd.DataFrame(data, columns=["file_name", "file_size", "call_date", "status", "rows_in_file",
                                       "rows_added", "rows_already_there", "message", "loaded_at"])


NO_GROUP = "Not in a group"


def apply_groups(df: pd.DataFrame, srcs: pd.DataFrame) -> pd.DataFrame:
    """Adds 'Group' (e.g. USA Vein) to each call from the Toll Sources master, as of the call date."""
    rules = {}
    for r in srcs.sort_values("effective_from").itertuples():
        rules.setdefault(r.toll, []).append((r.effective_from, r.group_name or ""))

    def lookup(toll, day):
        hits = [g for eff, g in rules.get(toll, []) if day is None or pd.isna(day) or eff <= day]
        return hits[-1] if hits else ""

    df = df.copy()
    df["Group"] = [lookup(t, d) or NO_GROUP for t, d in zip(df["_toll"], df["_date"])]
    return df


def apply_master(df: pd.DataFrame, routing: pd.DataFrame) -> pd.DataFrame:
    """Adds 'Master Point To' + 'Routing' to each ATT call, using the master rule for its toll + state
    that was in effect on the call date (falls back to the toll's 'any other state' rule)."""
    rules = {}
    for r in routing.sort_values("effective_from").itertuples():
        rules.setdefault((r.toll, r.state), []).append((r.effective_from, r.point_to))

    def lookup(toll, state, day):
        for key in ((toll, state), (toll, "")):
            hits = [pt for eff, pt in rules.get(key, []) if day is None or pd.isna(day) or eff <= day]
            if hits:
                return hits[-1]
        return ""

    df = df.copy()
    df["_master"] = [lookup(t, s, d) for t, s, d in zip(df["_toll"], df["_state"], df["_date"])]
    df["Master Point To"] = df["_master"].map(lambda v: fmt_phone(v) if v else "")
    df["Routing"] = "Not in master"
    has = df["_master"] != ""
    df.loc[has & (df["_master"] == df["_pt"]), "Routing"] = "Matches master"
    df.loc[has & (df["_master"] != df["_pt"]), "Routing"] = "Differs"
    return df


ATT_DATE_PRESETS = ["Yesterday", "This week", "Last week", "Last 7 days", "This month", "Broadcast week", "Custom"]
ATT_FIRST_WEEK = date(2025, 12, 29)   # broadcast week 1 of 2026 (first day loaded from AT&T)


def bweek_monday(d: date) -> date:
    return d - timedelta(days=d.weekday())


def bweek_number(d: date) -> int:
    """Broadcast calendar: weeks run Monday-Sunday; week 1 is the week containing Jan 1."""
    nxt = bweek_monday(date(d.year + 1, 1, 1))
    start = nxt if d >= nxt else bweek_monday(date(d.year, 1, 1))
    return (d - start).days // 7 + 1


def bweek_label(monday: date) -> str:
    sun = monday + timedelta(days=6)
    first = f"{monday:%m/%d/%Y}" if monday.year != sun.year else f"{monday:%m/%d}"
    return f"Week {bweek_number(monday)} · {first} – {sun:%m/%d/%Y}"


def att_week_options() -> list:
    """Every broadcast week from week 1 of 2026 to this week, newest first."""
    this = bweek_monday(date.today())
    weeks, w = [], this
    while w >= ATT_FIRST_WEEK:
        weeks.append(w)
        w -= timedelta(days=7)
    return weeks


def _att_date_range(preset: str, custom, week) -> tuple:
    today = date.today()
    if preset == "This week":
        return bweek_monday(today), today
    if preset == "Last week":
        m = bweek_monday(today) - timedelta(days=7)
        return m, m + timedelta(days=6)
    if preset == "Broadcast week" and week:
        m = week if isinstance(week, date) else date.fromisoformat(str(week))
        return m, min(m + timedelta(days=6), today)
    return _date_range(preset, custom)


def _att_defaults() -> dict:
    y = date.today() - timedelta(days=1)
    return {"a_preset": "Yesterday", "a_dates": (y, y), "a_week": bweek_monday(date.today()),
            "a_sources": [], "a_tolls": [], "a_states": [],
            "a_points": [], "a_show": "All", "a_group": "All tolls"}


def _att_reset():
    for k, v in _att_defaults().items():
        st.session_state[k] = v
    st.session_state["att_applied"] = _att_defaults()


def _att_apply():
    # picking a different week in the Broadcast week box switches Dates to that week
    prev_week = (st.session_state.get("att_applied") or {}).get("a_week")
    if st.session_state.get("a_week") != prev_week and st.session_state.get("a_preset") != "Custom":
        st.session_state["a_preset"] = "Broadcast week"
    if st.session_state.get("a_preset") == "Custom":
        custom = st.session_state.get("a_dates")
        if not isinstance(custom, (list, tuple)) or len(custom) != 2:
            st.session_state["att_error"] = "Pick both a start and an end date for the custom range."
            return
    st.session_state["att_applied"] = {k: st.session_state.get(k) for k in _att_defaults()}


def page_att_calls():
    for k, v in _att_defaults().items():
        st.session_state.setdefault(k, v)
    st.session_state.setdefault("att_applied", _att_defaults())
    a = {**_att_defaults(), **st.session_state["att_applied"]}
    if st.session_state.get("a_week") not in att_week_options():
        st.session_state["a_week"] = bweek_monday(date.today())
    start, end = _att_date_range(a["a_preset"], a["a_dates"], a["a_week"])

    att = load_att(start, end)
    in_range = att[(att["_date"] >= start) & (att["_date"] <= end)]
    in_range = apply_master(in_range, load_routing())
    srcs = load_toll_sources()
    in_range = apply_groups(in_range, srcs)
    group_opts = ["All tolls"] + sorted(g for g in srcs["group_name"].dropna().unique() if g) + [NO_GROUP]
    if st.session_state.get("a_group") not in group_opts:
        st.session_state["a_group"] = "All tolls"

    src_opts = sorted(x for x in in_range["Source"].unique() if x)
    toll_opts = sorted(x for x in in_range["_toll"].unique() if x)
    state_opts = sorted(x for x in in_range["_state"].unique() if x)
    pt_opts = sorted(x for x in in_range["_pt"].unique() if x)
    for key, opts in (("a_sources", src_opts), ("a_tolls", toll_opts), ("a_states", state_opts),
                      ("a_points", pt_opts)):
        st.session_state[key] = [x for x in (st.session_state.get(key) or []) if x in opts]

    h1, h2 = st.columns([3, 1.3], vertical_alignment="bottom")
    with h1:
        st.title("ATT Calls")
        st.caption("Every call from the ATT table. Set filters, then **Apply filters**.")
    dl_slot = h2.container()

    with st.form("att_filters"):
        r1 = st.columns([3.6, 1.7, 1.5])
        r1[0].segmented_control("Dates", ATT_DATE_PRESETS, key="a_preset",
                                help="Weeks are broadcast weeks (Monday – Sunday)")
        r1[1].selectbox("Broadcast week", att_week_options(), key="a_week", format_func=bweek_label,
                        help="Used when Dates is set to Broadcast week")
        r1[2].date_input("Custom range", key="a_dates", format="MM/DD/YYYY",
                         help="Used when Dates is set to Custom")
        r2 = st.columns([1.9, 1.6, 1.6, 1.2, 1.7])
        r2[0].segmented_control("Tolls", group_opts, key="a_group",
                                help="USA Vein = every toll in the Toll Sources master's USA Vein group")
        r2[1].multiselect("Source", src_opts, key="a_sources", placeholder="All sources")
        r2[2].multiselect("Toll Dialed", toll_opts, key="a_tolls", placeholder="All tolls", format_func=fmt_phone)
        r2[3].multiselect("State", state_opts, key="a_states", placeholder="All states")
        r2[4].multiselect("Point To", pt_opts, key="a_points", placeholder="All Point To numbers",
                          format_func=fmt_phone)
        r3 = st.columns([3.4, 2.0, 1, 1.3], vertical_alignment="bottom")
        r3[0].segmented_control("Show", ATT_SHOW, key="a_show",
                                help="Compare each call's Point To with the Toll Routing master")
        r3[2].form_submit_button("Reset", width="stretch", on_click=_att_reset)
        r3[3].form_submit_button("Apply filters", type="primary", icon=":material/filter_alt:",
                                 width="stretch", on_click=_att_apply)
    err = st.session_state.pop("att_error", None)
    if err:
        st.warning(err)

    view = in_range
    if (a["a_group"] or "All tolls") != "All tolls":
        view = view[view["Group"] == a["a_group"]]
    if a["a_sources"]:
        view = view[view["Source"].isin(a["a_sources"])]
    if a["a_tolls"]:
        view = view[view["_toll"].isin(a["a_tolls"])]
    if a["a_states"]:
        view = view[view["_state"].isin(a["a_states"])]
    if a["a_points"]:
        view = view[view["_pt"].isin(a["a_points"])]
    if (a["a_show"] or "All") != "All":
        view = view[view["Routing"] == a["a_show"]]

    bits = [a["a_group"] or "All tolls",
            ", ".join(a["a_sources"]) if a["a_sources"] else "All sources",
            ", ".join(fmt_phone(x) for x in a["a_tolls"]) if a["a_tolls"] else "All toll numbers",
            ", ".join(a["a_states"]) if a["a_states"] else "All states"]
    if a["a_points"]:
        bits.append("Point To " + ", ".join(fmt_phone(x) for x in a["a_points"]))
    if (a["a_show"] or "All") != "All":
        bits.append(a["a_show"])
    when = f"{start:%m/%d/%Y}" if start == end else f"{start:%m/%d/%Y} – {end:%m/%d/%Y}"
    if a["a_preset"] in ("This week", "Last week", "Broadcast week"):
        when = f"Week {bweek_number(start)} ({when})"
    bits.append(when)
    st.markdown(f'<div class="applied">Showing <b>{esc(" · ".join(bits))}</b></div>', unsafe_allow_html=True)

    secs = pd.to_numeric(view["Time(Secs)"], errors="coerce").fillna(0)
    uniq = view.loc[view["_num"] != "", "_num"].nunique()
    per_num = view.loc[view["_num"] != "", "_num"].value_counts()
    differs = int((view["Routing"] == "Differs").sum())
    no_rule = int((view["Routing"] == "Not in master").sum())
    kpi_cards([
        {"label": "Total calls", "value": f"{len(view):,}", "note": "in the applied filters"},
        {"label": "Unique numbers", "value": f"{uniq:,}",
         "note": f"{len(view) / uniq:.1f} calls per number" if uniq else ""},
        {"label": "Talk time", "value": fmt_total(secs.sum()),
         "note": f"avg {fmt_short(secs.mean())} per call" if len(view) else ""},
        {"label": "Tolls dialed", "value": f"{view['_toll'].nunique():,}",
         "note": f"{view.loc[view['_pt'] != '', '_pt'].nunique():,} Point To numbers used"},
        {"label": "Called 3+ times", "value": f"{int((per_num >= 3).sum()):,}", "note": "numbers in this range"},
        {"label": "⚠ Routing differs", "value": f"{differs:,}",
         "note": f"{no_rule:,} calls on tolls/states not in the master", "alert": differs > 0},
    ])

    if view.empty:
        st.info("No ATT calls match these filters." if not in_range.empty
                else "No ATT calls in this date range.")
        return

    view = view.sort_values(["_date", "_time"], ascending=False, na_position="last")
    out = view[ATT_COLS + ["Group", "Master Point To", "Routing"]].copy()
    for c in ATT_PHONE_COLS:
        out[c] = out[c].map(lambda v: fmt_phone(v) if digits10(v) else ("" if v is None or pd.isna(v) else v))

    with dl_slot:
        d1, d2 = st.columns(2)
        d1.download_button("CSV", out.to_csv(index=False).encode("utf-8"),
                           file_name=f"att_calls_{start}_{end}.csv", mime="text/csv",
                           icon=":material/download:", width="stretch")
        xlsx = to_excel(out, sheet="ATT Calls")
        if xlsx:
            d2.download_button("Download Excel", xlsx, file_name=f"att_calls_{start}_{end}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               icon=":material/table_view:", type="primary", width="stretch")

    def _routing_style(col):
        colors = {"Matches master": "color: #2e9e6a", "Differs": "color: #d97706; font-weight: 600",
                  "Not in master": "opacity: .55"}
        return [colors.get(v, "") for v in col]

    n_tolls = view.loc[view["_toll"] != "", "_toll"].nunique()
    tab_calls, tab_tolls = st.tabs([f":material/list: Calls  {len(out):,}",
                                    f":material/analytics: Toll analysis  {n_tolls:,}"])
    with tab_tolls:
        toll_analysis(view, start, end)
    with tab_calls:
        _att_calls_table(out, _routing_style)
    att_file_log_panel()


def _att_calls_table(out: pd.DataFrame, _routing_style):
    st.dataframe(out.style.apply(_routing_style, subset=["Routing"]), hide_index=True, width="stretch",
                 height=620,
                 column_config={
                     "ID": st.column_config.NumberColumn(format="%d", width="small"),
                     "Week": st.column_config.NumberColumn(format="%d", width="small"),
                     "Time(Secs)": st.column_config.NumberColumn(format="%d"),
                     "ATT": st.column_config.NumberColumn(format="%d", width="small"),
                     "Master Point To": st.column_config.TextColumn(
                         help="Where the Toll Routing master says this toll + state should go"),
                     "Routing": st.column_config.TextColumn(
                         help="Matches master · Differs (actual Point To is different) · Not in master"),
                 })
    st.caption(f"{plural(len(out), 'call')} · newest first · Point To rules are on the **Toll Routing** page, "
               "Source and group on the **Toll Sources** page")


def toll_report_table(view: pd.DataFrame) -> pd.DataFrame:
    """One row per toll per broadcast week: Total Calls and Unique Calls (different caller numbers)."""
    v = view[view["_toll"] != ""].copy()
    if v.empty:
        return pd.DataFrame(columns=["Toll", "Week", "Week Of", "Total Calls", "Unique Calls"])
    v["_mon"] = v["_date"].map(bweek_monday)
    g = (v.groupby(["_toll", "_mon"])
         .agg(total=("ID", "size"), uniq=("_num", lambda s: s[s != ""].nunique())).reset_index()
         .sort_values(["_toll", "_mon"]))
    rep = pd.DataFrame({
        "Toll": g["_toll"].map(lambda t: f"({t[:3]}) {t[3:6]}-{t[6:]}"),
        "Week": g["_mon"].map(lambda m: f"{(m + timedelta(days=6)).year}-{bweek_number(m):02d}"),
        "Week Of": g["_mon"].map(lambda m: f"{m:%Y-%m-%d}"),
        "Total Calls": g["total"].astype(int),
        "Unique Calls": g["uniq"].astype(int),
    })
    totals = pd.DataFrame([{"Toll": "TOTALS:", "Week": "", "Week Of": "",
                            "Total Calls": int(rep["Total Calls"].sum()),
                            "Unique Calls": int(rep["Unique Calls"].sum())}])
    return pd.concat([rep, totals], ignore_index=True)


def toll_report_excel(rep: pd.DataFrame, title: str):
    try:
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    except ImportError:
        return None
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        rep.to_excel(w, index=False, sheet_name="Toll Analysis")
        ws = w.sheets["Toll Analysis"]
        head = PatternFill("solid", fgColor="BDD7EE")
        for c in ws[1]:
            c.font = Font(bold=True)
            c.fill = head
            c.alignment = Alignment(horizontal="center")
        last = ws.max_row
        thin = Side(style="thin")
        for c in ws[last]:
            c.font = Font(bold=True)
            c.border = Border(top=thin, bottom=Side(style="double"))
        for col, width in zip("ABCDE", (17, 10, 12, 12, 13)):
            ws.column_dimensions[col].width = width
        ws.freeze_panes = "A2"
    return buf.getvalue()


def toll_analysis(view: pd.DataFrame, start: date, end: date):
    rep = toll_report_table(view)
    if len(rep) <= 1:
        st.info("No calls to report for these filters.")
        return
    weeks = rep["Week"].iloc[:-1].nunique()
    c1, c2 = st.columns([3, 1.2], vertical_alignment="center")
    c1.caption(f"Calls per toll per broadcast week for the applied filters "
               f"({start:%m/%d/%Y} – {end:%m/%d/%Y}, {plural(weeks, 'week')}). "
               "**Unique Calls** = different caller numbers. The TOTALS row adds up each column.")
    xlsx = toll_report_excel(rep, "Toll Analysis")
    if xlsx:
        c2.download_button("Download Excel", xlsx, file_name=f"toll_analysis_{start}_{end}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           icon=":material/table_view:", width="stretch")

    def _bold_total(row):
        return ["font-weight: 700; border-top: 2px solid #888" if row["Toll"] == "TOTALS:" else ""] * len(row)

    st.dataframe(rep.style.apply(_bold_total, axis=1), hide_index=True, width="content",
                 height=min(38 + 35 * len(rep), 760),
                 column_config={"Toll": st.column_config.TextColumn(width="medium"),
                                "Week": st.column_config.TextColumn(help="Broadcast year-week"),
                                "Week Of": st.column_config.TextColumn(help="Monday that starts the broadcast week"),
                                "Total Calls": st.column_config.NumberColumn(format="%d"),
                                "Unique Calls": st.column_config.NumberColumn(
                                    format="%d", help="Different caller numbers to this toll that week")})


def att_file_log_panel():
    flog = load_att_file_log()
    with st.expander("AT&T files loaded automatically", icon=":material/folder_open:"):
        if flog.empty:
            st.info("No AT&T files have been loaded yet. The loader on your PC adds new files from the "
                    "AT&T Exports folder and records each one here, so a file is never loaded twice.")
            return
        loaded = flog[flog["status"] == "loaded"]
        errors = flog[flog["status"] == "error"]
        last = pd.to_datetime(flog["loaded_at"]).max()
        st.caption(f"{len(loaded):,} files loaded · {int(loaded['rows_added'].fillna(0).sum()):,} calls added · "
                   f"last run {us_time(last.tz_convert('America/Chicago')) if last is not pd.NaT else '—'}"
                   + (f" · ⚠ {len(errors)} file(s) had errors" if len(errors) else ""))
        show = flog[flog["status"].isin(["loaded", "error"])].copy()
        show["Call date"] = pd.to_datetime(show["call_date"]).dt.strftime("%m/%d/%Y")
        show["Loaded"] = pd.to_datetime(show["loaded_at"]).dt.tz_convert("America/Chicago").map(us_time)
        show = show.rename(columns={"file_name": "File", "status": "Status", "rows_in_file": "Calls in file",
                                    "rows_added": "Added", "rows_already_there": "Already there",
                                    "message": "Error"})
        st.dataframe(show[["Call date", "File", "Status", "Calls in file", "Added", "Already there", "Loaded",
                           "Error"]].head(60), hide_index=True, width="stretch")


# ---------- Toll Routing (master) ----------
def _rule_label(state: str) -> str:
    return state if state else OTHER_STATES


@st.dialog("Assign Point To")
def assign_route_dialog(routing: pd.DataFrame, toll: str):
    toll_in = st.text_input("Toll Dialed", value=fmt_phone(toll) if toll else "",
                            help="Pick a toll on the left, or type a new one")
    states = st.multiselect("States", [OTHER_STATES] + US_STATES, placeholder="Pick one or more states")
    point_raw = st.text_input("Point To", placeholder="e.g. 847-579-2429")
    start_day = st.date_input("Starting", value=date.today(), format="MM/DD/YYYY",
                              help="Calls on or after this date use this Point To")
    toll10, point10 = digits10(toll_in), digits10(point_raw)
    keys = ["" if s == OTHER_STATES else s for s in states]
    if toll10 and keys:
        cur = routing[routing["toll"] == toll10]
        notes = []
        for s in keys:
            prior = cur[(cur["state"] == s) & (cur["effective_from"] <= start_day)].sort_values("effective_from")
            if not prior.empty and prior.iloc[-1]["point_to"] != point10:
                notes.append(f"{_rule_label(s)} now goes to {fmt_phone(prior.iloc[-1]['point_to'])}")
        if notes:
            st.info("Handover: " + "; ".join(notes) + f". From {start_day:%m/%d/%Y} on, these will go to the "
                    "new Point To. Earlier calls keep the old one.")
    if st.button("Save", type="primary"):
        if not toll10:
            st.error("Enter a 10-digit toll number.")
            return
        if not keys:
            st.error("Pick at least one state.")
            return
        if not point10:
            st.error("Enter a 10-digit Point To number.")
            return
        cur = routing[(routing["toll"] == toll10) & (routing["effective_from"] == start_day)]
        clash = cur[cur["state"].isin(keys)]
        if not clash.empty:
            lst = ", ".join(f"{_rule_label(r.state)} → {fmt_phone(r.point_to)}" for r in clash.itertuples())
            st.error(f"These states already have a Point To on this toll starting {start_day:%m/%d/%Y}: {lst}. "
                     "A state can only go to one Point To at a time. Remove that rule first, "
                     "or pick a different Starting date.")
            return
        sb.table("toll_routing").insert([{"toll": toll10, "state": s or None, "point_to": point10,
                                          "effective_from": str(start_day)} for s in keys]).execute()
        st.session_state["route_toll"] = toll10
        st.cache_data.clear()
        st.rerun()


@st.dialog("Remove routing rules")
def remove_route_dialog(rows: pd.DataFrame):
    st.write("Remove these rules from the master? Calls fall back to an earlier rule or "
             f"the toll's {OTHER_STATES} rule, if there is one.")
    st.dataframe(rows[["State", "Point To", "Starting"]], hide_index=True, width="stretch")
    yes, no = st.columns(2)
    if yes.button("Remove", type="primary", width="stretch"):
        for row_id in rows["id"]:
            sb.table("toll_routing").delete().eq("id", int(row_id)).execute()
        st.cache_data.clear()
        st.session_state["route_v"] = st.session_state.get("route_v", 0) + 1
        st.rerun()
    if no.button("Cancel", width="stretch"):
        st.session_state["route_v"] = st.session_state.get("route_v", 0) + 1
        st.rerun()


def page_toll_routing():
    st.title("Toll Routing")
    st.markdown('<div class="page-sub">Master: which Point To each toll should ring, by state</div>',
                unsafe_allow_html=True)
    st.caption("A state can only go to one Point To per toll at a time. Use **Assign Point To** with a later "
               "Starting date when routing changes; earlier calls keep the old Point To. "
               f"{OTHER_STATES} covers any state not listed for that toll (and calls with no state).")
    routing = load_routing()
    att = apply_master(load_att(), routing)   # last 90 days

    # ---------- toll list ----------
    calls_per_toll = att.groupby("_toll").size()
    differs_per_toll = att[att["Routing"] == "Differs"].groupby("_toll").size()
    tolls = sorted(set(routing["toll"]) | set(t for t in calls_per_toll.index if t))
    tl = pd.DataFrame({
        "toll": tolls,
        "Toll": [fmt_phone(t) for t in tolls],
        "Point Tos": [routing.loc[routing["toll"] == t, "point_to"].nunique() or None for t in tolls],
        "States": [int((routing["toll"] == t).sum()) or None for t in tolls],
        "Calls": [int(calls_per_toll.get(t, 0)) for t in tolls],
        "Differs": [int(differs_per_toll.get(t, 0)) or None for t in tolls],
    })

    left, right = st.columns([1.25, 2.6], gap="large")
    with left:
        st.markdown("**Tolls**")
        find = st.text_input("Find a toll", placeholder="Type part of a toll number", label_visibility="collapsed",
                             icon=":material/search:")
        if find.strip():
            tl = tl[tl["toll"].str.contains(re.sub(r"\D", "", find), regex=False)]
        tl = tl.reset_index(drop=True)
        ev = st.dataframe(tl, hide_index=True, width="stretch", height=560, on_select="rerun",
                          selection_mode="single-row", key=f"toll_list_{find}",
                          column_order=["Toll", "Point Tos", "States", "Calls", "Differs"],
                          column_config={"Point Tos": st.column_config.NumberColumn(help="Point To numbers in the master"),
                                         "States": st.column_config.NumberColumn(help="State rules in the master (blank = none yet)"),
                                         "Calls": st.column_config.NumberColumn(help="ATT calls to this toll in the last 90 days"),
                                         "Differs": st.column_config.NumberColumn(help="Calls whose Point To doesn't match the master")})
        sel = ev.selection.rows if ev and ev.selection else []
        if sel:
            st.session_state["route_toll"] = tl.iloc[sel[0]]["toll"]
        st.caption(f"{len(routing):,} rules · {routing['toll'].nunique()} tolls in the master")

    toll = st.session_state.get("route_toll") or (tl.iloc[0]["toll"] if not tl.empty else "")
    with right:
        top = st.columns([3, 1.3], vertical_alignment="center")
        tcalls = att[att["_toll"] == toll]
        srcs = ", ".join(sorted(x for x in tcalls["Source"].unique() if x))
        top[0].markdown(f"### {fmt_phone(toll) if toll else 'Pick a toll'}"
                        + (f"  \n<span style='opacity:.6'>{esc(srcs)} · {len(tcalls):,} calls</span>" if toll else ""),
                        unsafe_allow_html=True)
        if top[1].button("Assign Point To", icon=":material/alt_route:", type="primary", width="stretch"):
            assign_route_dialog(routing, toll)
        if not toll:
            return

        rules = routing[routing["toll"] == toll].copy()
        if rules.empty:
            st.info("This toll isn't in the master yet. Use **Assign Point To** to add its states.")
        else:
            # summary: one line per Point To + Starting date
            covered = tcalls.groupby("_master").size()
            grp = (rules.assign(lbl=rules["state"].map(_rule_label))
                   .groupby(["point_to", "effective_from"])["lbl"]
                   .apply(lambda s: sorted(s, key=lambda x: (x == OTHER_STATES, x))).reset_index())
            summary = pd.DataFrame({
                "States": grp["lbl"].map(lambda xs: "  ".join(xs)),
                "Point To": grp["point_to"].map(fmt_phone),
                "Starting": grp["effective_from"].map(lambda d: "Beginning" if d == BASE_DATE else f"{d:%m/%d/%Y}"),
                "# States": grp["lbl"].map(len),
                "Calls routed": grp["point_to"].map(lambda p: int(covered.get(p, 0))),
            }).sort_values(["Point To", "Starting"])
            st.markdown("**Routing by Point To**")
            st.dataframe(summary, hide_index=True, width="stretch",
                         column_config={"States": st.column_config.TextColumn(width="large"),
                                        "Calls routed": st.column_config.NumberColumn(
                                            help="ATT calls on this toll the master sends to this Point To")})

            st.markdown("**Rules by state**")
            detail = pd.DataFrame({
                "id": rules["id"],
                "State": rules["state"].map(_rule_label),
                "Point To": rules["point_to"].map(fmt_phone),
                "Starting": rules["effective_from"].map(lambda d: "Beginning" if d == BASE_DATE else f"{d:%m/%d/%Y}"),
                "_s": rules["state"].replace("", "~"), "_e": rules["effective_from"],
                "Remove": False,
            }).sort_values(["_s", "_e"]).drop(columns=["_s", "_e"])
            edited = st.data_editor(detail, hide_index=True, width="stretch", height=320, num_rows="fixed",
                                    key=f"route_editor_{toll}_{st.session_state.get('route_v', 0)}",
                                    column_order=["State", "Point To", "Starting", "Remove"],
                                    disabled=["State", "Point To", "Starting"],
                                    column_config={"Remove": st.column_config.CheckboxColumn(width="small")})
            to_remove = edited[edited["Remove"]]
            if not to_remove.empty and st.button(f"Remove {len(to_remove)} selected", icon=":material/delete:"):
                remove_route_dialog(to_remove)

        # calls on this toll whose state has no rule and no catch-all
        missing = tcalls[tcalls["Routing"] == "Not in master"]
        if not missing.empty:
            st.warning("Calls on this toll from states with no rule: "
                       + ", ".join(f"{s or '(blank)'} ({n})" for s, n in
                                   missing["_state"].value_counts().items()))


# ---------- Toll Sources (master: which Source + group each toll belongs to) ----------
def _starting_label(d) -> str:
    return "Beginning" if d == BASE_DATE else f"{d:%m/%d/%Y}"


def _refresh_sources(toll: str):
    """Rewrite the stored Source on this toll's ATT calls from the master."""
    try:
        sb.rpc("refresh_att_source", {"p_toll": toll}).execute()
    except Exception as e:
        st.warning(f"Saved, but updating existing ATT calls for {fmt_phone(toll)} failed: {e}")


@st.dialog("Assign New")
def assign_source_dialog(srcs: pd.DataFrame):
    existing = sorted(srcs["toll"].unique())
    mode = st.radio("Toll", ["Existing toll", "New toll"], horizontal=True, label_visibility="collapsed")
    if mode == "Existing toll" and existing:
        cur = srcs.sort_values("effective_from").groupby("toll").tail(1).set_index("toll")
        toll = st.selectbox("Toll", existing, format_func=lambda t: f"{fmt_phone(t)} — {cur.at[t, 'source'] or '(no source)'}"
                                                                 f" · {cur.at[t, 'group_name'] or NO_GROUP}")
    else:
        toll = digits10(st.text_input("Toll", placeholder="e.g. 800-905-6880"))
    src_opts = sorted(x for x in srcs["source"].dropna().unique() if x)
    pick = st.selectbox("Source", src_opts + ["+ New source…"], index=None, placeholder="Pick a source")
    source = st.text_input("New source name").strip() if pick == "+ New source…" else (pick or "")
    grp_opts = sorted(x for x in srcs["group_name"].dropna().unique() if x)
    gpick = st.selectbox("Group", grp_opts + [NO_GROUP, "+ New group…"],
                         index=grp_opts.index("USA Vein") if "USA Vein" in grp_opts else 0)
    group = st.text_input("New group name").strip() if gpick == "+ New group…" else (
        "" if gpick == NO_GROUP else gpick)
    start_day = st.date_input("Starting", value=date.today(), format="MM/DD/YYYY",
                              help="Calls on or after this date use this Source and group")
    if toll:
        st.caption(f"Calls to {fmt_phone(toll)} on or after {start_day:%m/%d/%Y} will show this Source and group. "
                   "Earlier calls keep their current values.")
    if st.button("Save", type="primary"):
        if len(toll) != 10:
            st.error("Enter a 10-digit toll number.")
            return
        if not source and not group:
            st.error("Pick a Source or a group.")
            return
        clash = srcs[(srcs["toll"] == toll) & (srcs["effective_from"] == start_day)]
        if not clash.empty:
            st.error(f"{fmt_phone(toll)} already has an assignment starting {start_day:%m/%d/%Y}. "
                     "Edit it in the table instead, or pick another date.")
            return
        sb.table("toll_sources").insert({"toll": toll, "source": source or None, "group_name": group or None,
                                         "effective_from": str(start_day)}).execute()
        _refresh_sources(toll)
        st.cache_data.clear()
        st.session_state["src_v"] = st.session_state.get("src_v", 0) + 1
        st.rerun()


@st.dialog("Confirm change")
def edit_source_dialog(row_id: int, toll: str, field: str, old: str, new: str):
    label = "Source" if field == "source" else "group"
    st.write(f'Change the {label} of **{fmt_phone(toll)}** from **"{old or "(blank)"}"** to **"{new or "(blank)"}"**?')
    st.caption("This updates that assignment, including calls already loaded for its dates.")
    yes, no = st.columns(2)
    if yes.button("Yes", type="primary", width="stretch"):
        sb.table("toll_sources").update({field: new or None}).eq("id", row_id).execute()
        if field == "source":
            _refresh_sources(toll)
        st.cache_data.clear()
        st.session_state["src_v"] = st.session_state.get("src_v", 0) + 1
        st.rerun()
    if no.button("Cancel", width="stretch"):
        st.session_state["src_v"] = st.session_state.get("src_v", 0) + 1
        st.rerun()


@st.dialog("Remove assignments")
def remove_source_dialog(rows: pd.DataFrame):
    st.write("Remove these assignments? Their calls go back to the toll's previous assignment, "
             "or to a blank Source if there isn't one.")
    st.dataframe(rows[["Toll", "Source", "Group", "Starting"]], hide_index=True, width="stretch")
    yes, no = st.columns(2)
    if yes.button("Remove", type="primary", width="stretch"):
        for r in rows.itertuples():
            sb.table("toll_sources").delete().eq("id", int(r.id)).execute()
        for toll in rows["toll"].unique():
            _refresh_sources(toll)
        st.cache_data.clear()
        st.session_state["src_v"] = st.session_state.get("src_v", 0) + 1
        st.rerun()
    if no.button("Cancel", width="stretch"):
        st.session_state["src_v"] = st.session_state.get("src_v", 0) + 1
        st.rerun()


def page_toll_sources():
    st.title("Toll Sources")
    st.markdown('<div class="page-sub">Which Source and group each toll belongs to</div>', unsafe_allow_html=True)
    st.caption("Edit a Source or group and press Enter to change it. Use **Assign New** when a toll moves to a "
               "different Source or group: calls from the Starting date on use the new values, earlier calls "
               "keep the old ones. Tolls in the **USA Vein** group make up the USA Vein filter on ATT Calls.")
    srcs = load_toll_sources()
    c1, c2, c3 = st.columns([1, 2.2, 1.4])
    if c1.button("Assign New", icon=":material/add_link:", type="primary", width="stretch"):
        assign_source_dialog(srcs)
    find = c2.text_input("Find", placeholder="Type a toll, source or group", label_visibility="collapsed",
                         icon=":material/search:")
    grp_opts = ["All groups"] + sorted(x for x in srcs["group_name"].dropna().unique() if x) + [NO_GROUP]
    grp = c3.selectbox("Group", grp_opts, label_visibility="collapsed")

    shown = pd.DataFrame({
        "id": srcs["id"], "toll": srcs["toll"],
        "Toll": srcs["toll"].map(fmt_phone),
        "Source": srcs["source"].fillna(""),
        "Group": srcs["group_name"].fillna(""),
        "Starting": srcs["effective_from"].map(_starting_label),
        "_e": srcs["effective_from"],
        "Remove": False,
    }).sort_values(["Group", "Source", "toll", "_e"]).drop(columns="_e").reset_index(drop=True)
    if grp == NO_GROUP:
        shown = shown[shown["Group"] == ""]
    elif grp != "All groups":
        shown = shown[shown["Group"] == grp]
    if find.strip():
        f = find.strip().lower()
        fd = re.sub(r"\D", "", f)
        hit = shown["Source"].str.lower().str.contains(f, regex=False) | shown["Group"].str.lower().str.contains(f, regex=False)
        if fd:
            hit |= shown["toll"].str.contains(fd, regex=False)
        shown = shown[hit]

    edited = st.data_editor(
        shown, hide_index=True, width="stretch", height=560, num_rows="fixed",
        key=f"src_editor_{st.session_state.get('src_v', 0)}_{grp}_{find}",
        column_order=["Toll", "Source", "Group", "Starting", "Remove"],
        disabled=["Toll", "Starting"],
        column_config={"Source": st.column_config.TextColumn(help="Edit and press Enter"),
                       "Group": st.column_config.TextColumn(help="e.g. USA Vein. Edit and press Enter"),
                       "Starting": st.column_config.TextColumn(help="Calls on or after this date use this row"),
                       "Remove": st.column_config.CheckboxColumn(width="small")})
    n_tolls = srcs["toll"].nunique()
    n_vein = srcs.loc[srcs["group_name"] == "USA Vein", "toll"].nunique()
    st.caption(f"{len(srcs)} assignments · {n_tolls} tolls · {n_vein} in USA Vein")

    for field, col in (("source", "Source"), ("group_name", "Group")):
        changed = edited[edited[col].fillna("").str.strip() != shown[col].fillna("").str.strip()]
        if not changed.empty:
            r = changed.iloc[0]
            edit_source_dialog(int(r["id"]), r["toll"], field, shown.loc[r.name, col].strip(), str(r[col] or "").strip())
            break
    to_remove = edited[edited["Remove"]]
    if not to_remove.empty and st.button(f"Remove {len(to_remove)} selected", icon=":material/delete:"):
        remove_source_dialog(to_remove)

    # tolls getting calls that aren't in the master yet
    recent = load_att()
    if not recent.empty:
        missing = recent[~recent["_toll"].isin(set(srcs["toll"])) & (recent["_toll"] != "")]
        if not missing.empty:
            with st.expander(f"Tolls receiving calls that aren't in this master ({missing['_toll'].nunique()})",
                             icon=":material/help:"):
                st.caption("Last 90 days. Their calls are loaded with a blank Source and aren't in any group. "
                           "Use Assign New → New toll to add one.")
                t = (missing.groupby("_toll").agg(Calls=("ID", "size"), Last=("_date", "max")).reset_index()
                     .sort_values("Calls", ascending=False))
                t["Toll"] = t["_toll"].map(fmt_phone)
                t["Last call"] = t["Last"].map(lambda d: f"{d:%m/%d/%Y}" if pd.notna(d) else "")
                st.dataframe(t[["Toll", "Calls", "Last call"]], hide_index=True, width="stretch")


# =====================================================================================
# CALL LOG (simple, read-only view for management)
# =====================================================================================
CL_PRESETS = ["Yesterday", "This week", "Last week", "This month", "Custom"]
ALL_REPS_CL = "All reps"


def _status_pill(st_text) -> str:
    if not st_text or (isinstance(st_text, float) and pd.isna(st_text)):
        return ""
    s = str(st_text)
    if s.startswith(("09", "10")):
        bg, fg = "rgba(19,122,67,.12)", "#137a43"
    elif s.startswith(("07", "08", "14", "16")):
        bg, fg = "rgba(217,119,6,.13)", "#a35c00"
    elif s.startswith(("03", "05", "15")):
        bg, fg = "rgba(128,128,128,.15)", "inherit"
    else:
        bg, fg = "rgba(26,86,196,.12)", "#1a56c4"
    return (f"<span style='background:{bg};color:{fg};border-radius:6px;padding:2px 8px;font-size:.8rem;"
            f"font-weight:600'>{esc(s)}</span>")


def _short_len(d) -> str:
    secs = dur_seconds(d)
    h, rem = divmod(secs, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _cl_preset_changed():
    st.session_state["cl_week"] = None


def _cl_week_changed():
    if st.session_state.get("cl_week"):
        st.session_state["cl_preset"] = None


def _cl_range() -> tuple:
    today = date.today()
    week = st.session_state.get("cl_week")
    if week:
        return week, min(week + timedelta(days=6), today)
    p = st.session_state.get("cl_preset") or "Yesterday"
    if p == "This week":
        return bweek_monday(today), today
    if p == "Last week":
        m = bweek_monday(today) - timedelta(days=7)
        return m, m + timedelta(days=6)
    if p == "This month":
        return today.replace(day=1), today
    if p == "Custom":
        c = st.session_state.get("cl_custom")
        if isinstance(c, (list, tuple)) and len(c) == 2:
            return c[0], c[1]
        if isinstance(c, (list, tuple)) and len(c) == 1:
            return c[0], c[0]
    y = today - timedelta(days=1)
    return y, y


@st.cache_data(ttl=600, show_spinner=False)
def calls_to_lead_in_month(lead_id: str, month_start: date) -> pd.DataFrame:
    data = sb.rpc("calls_for_lead", {"p_lead_id": lead_id}).execute().data
    df = pd.DataFrame(data, columns=["direction", "to_number", "from_value", "call_time", "duration", "matched_on"])
    if df.empty:
        return df
    df = df.rename(columns={"direction": "Direction", "to_number": "To", "from_value": "From",
                            "call_time": "Date/Time", "duration": "Duration"})
    df["Date/Time"] = pd.to_datetime(df["Date/Time"])
    nxt = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
    df = df[(df["Date/Time"].dt.date >= month_start) & (df["Date/Time"].dt.date < nxt)]
    return apply_rep_names(df).sort_values("Date/Time", ascending=False) if not df.empty else df


def _cl_lead_panel(r, calls: pd.DataFrame):
    call_day = r["Date/Time"].date() if pd.notna(r["Date/Time"]) else date.today()
    month_start = call_day.replace(day=1)
    with st.container(border=True):
        if r["Lead Id"] == "Not Found":
            st.markdown(f"<div style='opacity:.6;font-size:.8rem'>NOT IN MMS</div>"
                        f"<div style='font-size:1.3rem;font-weight:700'>{esc(fmt_phone(r['To']))}</div>",
                        unsafe_allow_html=True)
            st.caption("This number isn't on any MMS lead.")
            same = calls[calls["To"] == r["To"]]
            hist = same[(same["Date/Time"].dt.date >= month_start)].sort_values("Date/Time", ascending=False)
            title = f"Calls to this number in {month_start:%B}"
        else:
            rec = get_lead(str(r["Lead Id"])) or {}
            name = rec.get("Company In Ad") or rec.get("Company (phase2)") or r.get("Company In Ad") or ""
            src = rec.get("Lead Source") or ""
            st.markdown(f"<div style='opacity:.6;font-size:.78rem;letter-spacing:.04em'>LEAD {esc(r['Lead Id'])}"
                        f"{' · ' + esc(src.upper()) if src else ''}</div>"
                        f"<div style='font-size:1.35rem;font-weight:700;line-height:1.25;margin:2px 0 6px'>"
                        f"{esc(name)}</div>{_status_pill(rec.get('Status'))}", unsafe_allow_html=True)

            def _d(v):
                try:
                    x = pd.to_datetime(v)
                    return f"{x:%b} {x.day}, {x.year}" if v else ""
                except Exception:
                    return str(v or "")
            rows = [("Contact", rec.get("Contact Name (phase2)")),
                    ("Phone", fmt_phone(rec.get("Contact Phone (phase2)") or rec.get("Phone Number In Ad") or "")),
                    ("Email", rec.get("Contact Email (phase2)")),
                    ("Owner", rec.get("Lead Owner")),
                    ("Market", rec.get("Media Market")),
                    ("Lead started", _d(rec.get("Lead Started"))),
                    ("Last edited", _d(rec.get("Last Edited")))]
            kv = "".join(f"<span>{k}</span><span>{esc(v)}</span>" for k, v in rows if v)
            st.markdown(f"<style>.clkv span:nth-child(odd){{opacity:.6}}</style><div class='clkv' style='display:grid;"
                        f"grid-template-columns:105px 1fr;gap:6px 10px;margin:12px 0 4px;font-size:.9rem'>{kv}</div>",
                        unsafe_allow_html=True)
            hist = calls_to_lead_in_month(str(r["Lead Id"]), month_start)
            title = f"Calls to this lead in {month_start:%B}"
        st.markdown(f"<div style='font-weight:700;margin:12px 0 4px;border-top:1px solid rgba(128,128,128,.2);"
                    f"padding-top:10px'>{title} · {len(hist)}</div>", unsafe_allow_html=True)
        if hist.empty:
            st.caption("No calls.")
        else:
            lines = "".join(
                f"<div style='display:grid;grid-template-columns:1.35fr 1fr .45fr;padding:5px 0;font-size:.85rem;"
                f"border-bottom:1px dashed rgba(128,128,128,.25)'><span>{us_time(h['Date/Time'])}</span>"
                f"<span>{esc(h['From'])}</span><span style='opacity:.6;text-align:right'>"
                f"{esc(_short_len(h['Duration']))}</span></div>"
                for _, h in hist.head(40).iterrows())
            st.markdown(lines, unsafe_allow_html=True)


@st.cache_data(ttl=300, show_spinner=False)
def load_rep_teams() -> dict:
    """{team name: set of rep names} from the rep_teams table."""
    teams = {}
    for r in sb.table("rep_teams").select("team, rep").execute().data:
        teams.setdefault(r["team"], set()).add(r["rep"])
    return teams


EVERYONE = "Everyone"


def page_call_log():
    st.session_state.setdefault("cl_preset", "Yesterday")
    st.session_state.setdefault("cl_week", None)
    st.session_state.setdefault("cl_sources", [])
    if st.session_state.get("cl_week") not in [None] + att_week_options():
        st.session_state["cl_week"] = None

    st.markdown("<h1 style='margin-bottom:0'>Call Log</h1>", unsafe_allow_html=True)
    st.caption("Every rep call, matched to its MMS lead. Click a call to see the lead.")

    teams = load_rep_teams()
    team_opts = [EVERYONE] + sorted(teams)
    if st.session_state.get("cl_team") not in team_opts:
        st.session_state["cl_team"] = EVERYONE
    f = st.columns([3.0, 1.7, 2.0, 1.9])
    f[0].segmented_control("Dates", CL_PRESETS, key="cl_preset", on_change=_cl_preset_changed)
    f[1].selectbox("Broadcast week", att_week_options(), key="cl_week", index=None, placeholder="Pick a week…",
                   format_func=bweek_label, on_change=_cl_week_changed)
    if st.session_state.get("cl_preset") == "Custom" and not st.session_state.get("cl_week"):
        y = date.today() - timedelta(days=1)
        st.session_state.setdefault("cl_custom", (y, y))
        f[0].date_input("Custom dates", key="cl_custom", format="MM/DD/YYYY")
    start, end = _cl_range()

    calls = load_calls(start, end)
    if not calls.empty:
        calls = apply_rep_names(calls)
    src_opts = sorted(x for x in calls.get("Lead Source", pd.Series(dtype=str)).dropna().unique() if x) \
        if not calls.empty else []
    st.session_state["cl_sources"] = [x for x in st.session_state.get("cl_sources", []) if x in src_opts]
    f[2].multiselect("Lead source", src_opts, key="cl_sources", placeholder="All lead sources")
    f[3].segmented_control("Team", team_opts, key="cl_team")

    when = f"{start:%m/%d/%Y}" if start == end else f"{start:%m/%d/%Y} – {end:%m/%d/%Y}"
    if st.session_state.get("cl_week") or st.session_state.get("cl_preset") in ("This week", "Last week"):
        when = f"Week {bweek_number(start)} · {when}"
    if calls.empty:
        st.info(f"No calls for {when}.")
        return

    # how many times each number was dialed in the picked dates (all reps)
    calls = calls.copy()
    calls["Times Dialed"] = calls.groupby("To")["To"].transform("count").astype(int)
    view = calls
    team = st.session_state.get("cl_team") or EVERYONE
    if team != EVERYONE:
        view = view[view["From"].astype(str).isin(teams.get(team, set()))]
    if st.session_state["cl_sources"]:
        view = view[view["Lead Source"].isin(st.session_state["cl_sources"])]

    # rep buttons: only reps with calls in the picked dates / sources
    counts = view["From"].fillna("").astype(str).value_counts()
    counts = counts[counts.index != ""]
    reps = [ALL_REPS_CL] + sorted(counts.index, key=str.lower)
    if st.session_state.get("cl_rep") not in reps:
        st.session_state["cl_rep"] = ALL_REPS_CL
    st.pills("Rep", reps, key="cl_rep", selection_mode="single", label_visibility="collapsed",
             format_func=lambda r: f"{r}  {len(view):,}" if r == ALL_REPS_CL else f"{r}  {int(counts[r]):,}")
    rep = st.session_state.get("cl_rep") or ALL_REPS_CL
    if rep != ALL_REPS_CL:
        view = view[view["From"].astype(str) == rep]

    secs = view["Duration"].map(dur_seconds)
    leads = view.loc[view["Lead Id"] != "Not Found", "Lead Id"].nunique()
    kpi_cards([{"label": "Calls", "value": f"{len(view):,}", "note": when},
               {"label": "Leads reached", "value": f"{leads:,}", "note": ""},
               {"label": "Talk time", "value": fmt_total(secs.sum()), "note": ""}])
    if view.empty:
        st.info("No calls match these filters.")
        return

    view = view.sort_values("Date/Time", ascending=False).reset_index(drop=True)
    found = view["Lead Id"] != "Not Found"
    table = pd.DataFrame({
        "Date": view["Date/Time"].map(us_time),
        "Rep": view["From"],
        "Lead ID": view["Lead Id"].where(found, "Not in MMS"),
        "Lead Source": view["Lead Source"].where(found, "").fillna(""),
        "Media Market": view["Media Market"].where(found, "").fillna(""),
        "Company": view["Company In Ad"].where(found, "").fillna(""),
        "Status": view["Status"].where(found, "").fillna(""),
        "Times Dialed": view["Times Dialed"],
    })

    left, right = st.columns([2.6, 1], gap="medium")
    with left:
        ev = st.dataframe(table, hide_index=True, width="stretch", height=min(38 + 35 * len(table), 640),
                          on_select="rerun", selection_mode="single-row",
                          key=f"cl_table_{start}_{end}_{rep}_{team}_{len(table)}",
                          column_config={"Date": st.column_config.TextColumn(width="small"),
                                         "Lead ID": st.column_config.TextColumn(width="small"),
                                         "Times Dialed": st.column_config.NumberColumn(
                                             format="%d", width="small",
                                             help="Times this number was dialed in the picked dates (all reps)")})
    sel = ev.selection.rows if ev and ev.selection else []
    with right:
        if sel:
            _cl_lead_panel(view.iloc[sel[0]], calls)
        else:
            with st.container(border=True):
                st.caption("Click a call to see the lead's details and every call to it that month.")


# =====================================================================================
# NAVIGATION
# =====================================================================================
PAGE_CALL_LOG = st.Page(page_call_log, title="Call Log", icon=":material/list_alt:", url_path="call-log")

if st.session_state.get("role", "admin") == "viewer":
    # management: only the Call Log, no sidebar, nothing that changes data
    st.markdown("<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl'],"
                "[data-testid='stExpandSidebarButton'],[data-testid='stSidebarCollapseButton']"
                "{display:none !important}</style>", unsafe_allow_html=True)
    st.navigation([st.Page(page_call_log, title="Call Log", icon=":material/list_alt:", url_path="call-log",
                           default=True)], position="hidden").run()
    st.stop()

PAGE_LEAD_SEARCH = st.Page(page_lead_search, title="Lead Search", icon=":material/person_search:",
                           url_path="lead-search")
try:
    _review_n = len(load_needs_review(30))
except Exception:
    _review_n = 0
nav = st.navigation({
    "Reports": [
        st.Page(page_call_report, title="Call Report", icon=":material/call:", url_path="call-report",
                default=True),
        PAGE_CALL_LOG,
        st.Page(page_att_calls, title="ATT Calls", icon=":material/phone_in_talk:", url_path="att-calls"),
        PAGE_LEAD_SEARCH,
        st.Page(page_needs_review, title=f"Needs Review ({_review_n})" if _review_n else "Needs Review",
                icon=":material/flag:", url_path="needs-review"),
    ],
    "Manage": [
        st.Page(page_contacts, title="Contacts", icon=":material/contacts:", url_path="contacts"),
        st.Page(page_toll_routing, title="Toll Routing", icon=":material/alt_route:", url_path="toll-routing"),
        st.Page(page_toll_sources, title="Toll Sources", icon=":material/sell:", url_path="toll-sources"),
        st.Page(page_upload_calls, title="Upload Calls", icon=":material/upload_file:", url_path="upload-calls"),
        st.Page(page_upload_leads, title="Upload Leads", icon=":material/group_add:", url_path="upload-leads"),
    ],
})

# Sidebar footer (all pages): how fresh the data is + rarely needed tools
with st.sidebar:
    try:
        fr = load_freshness()
        last_call = pd.to_datetime(fr.get("last_call")) if fr.get("last_call") else None
        last_edit = pd.to_datetime(fr.get("last_lead_edit")) if fr.get("last_lead_edit") else None
        st.markdown(f'''<div class="fresh">Calls through <b>{us_time(last_call) or "—"}</b><br>
Latest MMS edit <b>{us_time(last_edit) or "—"}</b><br>
{int(fr.get("total_calls") or 0):,} calls · {int(fr.get("total_leads") or 0):,} leads</div>''',
                    unsafe_allow_html=True)
    except Exception:
        pass
    with st.expander("Maintenance", icon=":material/build:"):
        if st.button("Reload data", width="stretch", help="Fetch the latest calls and leads from the database"):
            st.cache_data.clear()
            st.rerun()
        if st.button("Refresh lead matching", width="stretch",
                     help="Rebuild the phone lookup from all of MMS. Only needed if MMS was changed outside this app."):
            with st.spinner("Rebuilding phone lookup from MMS..."):
                sb.rpc("refresh_mms_phone_lookup", {}).execute()
            st.cache_data.clear()
            st.rerun()

nav.run()
