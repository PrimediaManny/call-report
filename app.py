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
            "f_sources": [], "f_started_from": None, "f_show": "All", "f_search": ""}


FILTER_KEYS = list(_filter_defaults())


def _reset_filters():
    defaults = _filter_defaults()
    for k, v in defaults.items():
        st.session_state[k] = v
    st.session_state["applied"] = defaults


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
    a = st.session_state["applied"]
    start, end = _date_range(a["f_preset"], a["f_dates"])
    sources = a["f_sources"] or []
    started_from = a["f_started_from"]
    direction = a["f_direction"] or "All"
    froms = a["f_from"] or []
    show = a["f_show"] or "All"
    search = a["f_search"] or ""

    df = load_calls(start, end, tuple(sorted(sources)), started_from)
    if not df.empty:
        df = apply_rep_names(df)
        df["Times Called"] = df.groupby("To")["To"].transform("count").astype(int)
        df["Leads Matched"] = pd.to_numeric(df["Leads Matched"], errors="coerce").fillna(0).astype(int)

    reps = load_contacts()["rep"].dropna().astype(str).str.strip()
    from_options = sorted(set(reps[reps != ""]) | (set(df["From"].dropna().astype(str)) if not df.empty else set()))
    st.session_state["f_from"] = [x for x in (st.session_state.get("f_from") or []) if x in from_options]

    # ---------- header ----------
    h1, h2 = st.columns([3, 1.3], vertical_alignment="bottom")
    with h1:
        st.title("Call Report")
        st.caption("Every call, matched to its MMS lead. Set filters, then **Apply filters**.")
    dl_slot = h2.container()

    # ---------- filter bar ----------
    with st.form("call_filters"):
        r1 = st.columns([2.4, 1.5, 1.8, 1.2])
        r1[0].segmented_control("Dates", DATE_PRESETS, key="f_preset")
        r1[1].date_input("Custom range", key="f_dates", format="MM/DD/YYYY",
                         help="Used when Dates is set to Custom")
        r1[2].multiselect("Rep", from_options, key="f_from", placeholder="All reps")
        r1[3].segmented_control("Direction", list(DIRECTIONS), key="f_direction")
        r2 = st.columns([2.4, 1.5, 3.0])
        r2[0].multiselect("Lead Source", load_lead_sources(), key="f_sources", placeholder="All sources",
                          help="Only match calls to MMS leads from these sources")
        r2[1].date_input("Lead started from", key="f_started_from", format="MM/DD/YYYY",
                         help="Only match calls to MMS leads started on or after this date")
        r2[2].segmented_control("Show", SHOW_OPTIONS, key="f_show")
        r3 = st.columns([4.6, 1, 1.3], vertical_alignment="bottom")
        r3[0].text_input("Search", key="f_search", placeholder="Number, company, contact, lead id",
                         icon=":material/search:")
        r3[1].form_submit_button("Reset", width="stretch", on_click=_reset_filters)
        r3[2].form_submit_button("Apply filters", type="primary", icon=":material/filter_alt:",
                                 width="stretch", on_click=_apply_filters)
    err = st.session_state.pop("apply_error", None)
    if err:
        st.warning(err)

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
    if search.strip():
        bits.append(f'Search "{search.strip()}"')
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

    view = df.copy()
    if direction != "All":
        view = view[view["Direction"].fillna("").str.lower() == DIRECTIONS[direction]]
    if froms:
        view = view[view["From"].astype(str).isin(froms)]
    needs = (view["Leads Matched"] >= 2) & (view["Lead Choice"] != "Picked")
    if show == "Matched":
        view = view[view["Lead Id"] != "Not Found"]
    elif show == "Not found":
        view = view[view["Lead Id"] == "Not Found"]
    elif show == "Needs pick":
        view = view[needs.reindex(view.index, fill_value=False)]
    if search.strip():
        s = search.strip().lower()
        s_digits = "".join(ch for ch in s if ch.isdigit())
        hay = view[["To", "From", "Ext / ID", "Company In Ad", "Contact Name (phase2)", "Lead Id"]].fillna(
            "").astype(str).apply(lambda c: c.str.lower()).agg(" ".join, axis=1)
        hit = hay.str.contains(s, regex=False)
        if len(s_digits) >= 4:
            hit |= view["To"].astype(str).str.contains(s_digits, regex=False)
        view = view[hit]

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

    left, right = st.columns([3.1, 1], gap="medium")
    with left:
        n_leads = view.loc[view["Lead Id"] != "Not Found", "Lead Id"].nunique()
        n_reps = view["From"].nunique()
        t_all, t_lead, t_rep = st.tabs([f"All calls  {len(view):,}", f"Grouped by lead  {n_leads:,}",
                                        f"Grouped by rep  {n_reps:,}"])
        with t_all:
            show_all = st.toggle("Show all columns", key="all_cols")
            call_cols = {"Date/Time": "Time", "From": "Rep", "To": "To",
                         "Duration": "Dur.", "Times Called": "Times"}
            lead_cols = {"Lead Id": "Lead", "Company In Ad": "Company", "Lead Owner": "Owner",
                         "Status": "Status", "Match": "Match"}
            if show_all:
                call_cols = {"Direction": "Direction", **call_cols, "Ext / ID": "Ext"}
                lead_cols = {**lead_cols, "Lead Started": "Lead Started", "Last Edited": "Last Edited",
                             "Lead Source": "Lead Source", "Media Market": "Market",
                             "Contact Name (phase2)": "Contact", "Phase2 Completed": "Phase2 Completed",
                             "Matched On": "Matched On", "Leads Matched": "Leads Matched"}
            table = view[list(call_cols) + list(lead_cols)].rename(columns={**call_cols, **lead_cols})
            table["To"] = table["To"].map(fmt_phone)
            lead_names = list(lead_cols.values())
            widths = {"Time": 128, "Rep": 135, "To": 105, "Dur.": 58, "Times": 56, "Direction": 80, "Ext": 70,
                      "Lead": 64, "Company": 170, "Owner": 130, "Status": 112, "Match": 108,
                      "Lead Started": 100, "Last Edited": 140, "Lead Source": 120, "Market": 110,
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
        PAGE_LEAD_SEARCH,
        st.Page(page_needs_review, title=f"Needs Review ({_review_n})" if _review_n else "Needs Review",
                icon=":material/flag:", url_path="needs-review"),
    ],
    "Manage": [
        st.Page(page_contacts, title="Contacts", icon=":material/contacts:", url_path="contacts"),
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
