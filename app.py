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
from decimal import Decimal, ROUND_HALF_UP

import pandas as pd
from pathlib import Path

import streamlit as st
from supabase import create_client

FAVICON = str(Path(__file__).with_name("favicon.png"))   # Primedia "P" on brand blue
st.set_page_config(page_title="Primedia · Call Report", page_icon=FAVICON, layout="wide",
                   initial_sidebar_state="expanded")

# ---------- look & feel (Primedia blue, glass buttons) ----------
import base64 as _b64

LOGO_WHITE = _b64.b64decode("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")   # Primedia Network logo, white lettering (dark backgrounds)
LOGO_DARK = _b64.b64decode("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")     # original logo, black lettering (light backgrounds)
LOGO_WHITE_URI = "data:image/png;base64,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"
LOGO_DARK_URI = "data:image/png;base64,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"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root {
  --pm-blue: #1E4FD8; --pm-blue-2: #5B83F2; --pm-navy: #0B1F4D; --pm-light: #EEF3FF;
  --pm-bg: #F7F8FA; --pm-line: #E6E8EC; --pm-ink: #111827; --pm-mute: #6B7280;
  --pm-shadow: 0 1px 2px rgba(16,24,40,.05), 0 6px 16px rgba(16,24,40,.07), 0 16px 40px rgba(16,24,40,.06);
}
html, body, .stApp, .stApp p, .stApp label, .stApp input, .stApp textarea, .stApp h1, .stApp h2, .stApp h3,
.stApp button p, .stApp li, .kpi, .lc, .applied { font-family: 'Inter', 'Source Sans Pro', sans-serif; }

/* page background: calm neutral with one faint brand-blue glow at the top (same as PODS) */
.stApp {
  background: radial-gradient(900px 260px at 50% -120px, rgba(59,110,232,.10), transparent 75%), var(--pm-bg) !important;
  background-attachment: fixed !important;
}
[data-testid="stHeader"] { background: transparent; }
/* no Streamlit branding: hide Deploy / Share / GitHub / menu / running icon (sidebar open-close stays) */
[data-testid="stToolbarActions"], [data-testid="stAppDeployButton"], [data-testid="stMainMenu"], #MainMenu,
[data-testid="stStatusWidget"], [data-testid="stDecoration"], footer { display: none !important; }
.block-container { padding-top: 2.2rem; }
h1 { font-weight: 700 !important; letter-spacing: -.02em; color: var(--pm-ink); padding: .1rem 0 0 !important; }

/* ---- sidebar: neon blue (same look as the PODS dashboard) ---- */
[data-testid="stSidebar"] {
  border-right: 1px solid rgba(91,140,255,.35) !important;
  background:
    radial-gradient(420px 320px at 0% 0%, rgba(59,130,246,.45), transparent 70%),
    radial-gradient(380px 360px at 100% 100%, rgba(0,174,255,.28), transparent 70%),
    linear-gradient(180deg, #0c1f5c 0%, #0a1440 55%, #08102e 100%) !important;
  box-shadow: 0 0 28px rgba(59,110,232,.35); }
[data-testid="stSidebar"] > div { background: transparent !important; }
[data-testid="stSidebar"] * { color: #cbd5e1; }
[data-testid="stSidebarNav"] a { border-radius: 8px; padding: 8px 12px; margin: 1px 0; border: 0 !important; }
[data-testid="stSidebarNav"] a:hover { background: rgba(255,255,255,.06) !important; }
[data-testid="stSidebarNav"] a:hover * { color: #fff !important; }
[data-testid="stSidebarNav"] a [data-testid="stIconMaterial"] { color: #64748b !important; }
[data-testid="stSidebarNav"] a[aria-current="page"] {
  background: rgba(91,140,255,.18) !important;
  box-shadow: inset 3px 0 0 #5b8cff, 0 0 14px rgba(91,140,255,.35) !important; }
[data-testid="stSidebarNav"] a[aria-current="page"] * { color: #fff !important; font-weight: 600; }
[data-testid="stSidebarNav"] a[aria-current="page"] [data-testid="stIconMaterial"] { color: #5b8cff !important; }
[data-testid="stNavSectionHeader"], [data-testid="stNavSectionHeader"] * {
  color: #64748b !important; font-size: 11px !important; font-weight: 600 !important;
  letter-spacing: .09em; text-transform: uppercase; }
[data-testid="stSidebar"] [data-testid="stExpander"] details { border-color: rgba(255,255,255,.12); background: rgba(255,255,255,.04); }
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
  background: rgba(255,255,255,.06) !important; border-color: rgba(255,255,255,.18) !important; }
[data-testid="stSidebarCollapseButton"] { display: flex !important; visibility: visible !important; opacity: 1 !important; }
[data-testid="stSidebarCollapseButton"] button, [data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapsedControl"] button { border: 1px solid rgba(128,128,128,0.35); border-radius: 8px; }
[data-testid="stSidebarHeader"] img, [data-testid="stLogo"] { height: 30px !important; max-width: 190px; }
.sb-section { font-size: 0.72rem; font-weight: 700; letter-spacing: .07em; text-transform: uppercase;
              opacity: .55; margin: 1.1rem 0 .25rem 0; }
.sb-section:first-child { margin-top: .2rem; }
.fresh { font-size: .78rem; line-height: 1.6; background: rgba(255,255,255,.06); border-radius: 10px;
         padding: 10px 12px; margin-bottom: 8px; }
.fresh .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #34D399; margin-right: 6px; }
.fresh b { color: #fff; }
[class*="st-key-ap_find_"] button { min-height: 2rem !important; margin-top: -4px; border-style: dashed !important;
  border-color: #F5C77A !important; color: #8a4b00 !important; background: #FFFBF2 !important; }
[class*="st-key-ap_find_"] button p { font-size: .8rem !important; }
[class*="st-key-mms_hit_"] { background: #FBFCFF; border-radius: 12px !important; }
.st-key-sb_refresh { margin-bottom: 2px; }
[data-testid="stSidebar"] .st-key-sb_refresh button { background: rgba(255,255,255,.04) !important; border: 1px solid rgba(255,255,255,.12) !important;
  border-radius: 10px !important; box-shadow: none !important; justify-content: flex-start !important; padding: .45rem 1rem !important;
  min-height: 2.5rem !important; color: rgb(214,223,245) !important; }
.st-key-sb_refresh button > div, .st-key-sb_refresh button [data-testid="stMarkdownContainer"] {
  justify-content: flex-start !important; width: 100%; gap: .6rem; }
[data-testid="stSidebar"] .st-key-sb_refresh button:hover { background: rgba(255,255,255,.09) !important; border-color: rgba(255,255,255,.25) !important; }
[data-testid="stSidebar"] .st-key-sb_refresh button p { font-size: 14px !important; color: rgb(214,223,245) !important; text-align: left; }

/* ---- glass: primary buttons, selected chips / segments / pills ---- */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"],
[data-testid="stBaseButton-pillsActive"], [data-testid="stBaseButton-segmented_controlActive"],
button[data-variant="segmented_control"][data-selected="true"], button[data-variant="pills"][data-selected="true"] {
  background: linear-gradient(180deg, rgba(91,131,242,.95) 0%, rgba(30,79,216,.86) 100%) !important;
  border: 1px solid rgba(255,255,255,.55) !important; color: #fff !important;
  -webkit-backdrop-filter: blur(16px); backdrop-filter: blur(16px);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.55), 0 6px 16px -4px rgba(30,79,216,.45) !important;
}
[data-testid="stBaseButton-primary"] *, [data-testid="stBaseButton-primaryFormSubmit"] *,
[data-testid="stBaseButton-pillsActive"] *, [data-testid="stBaseButton-segmented_controlActive"] *,
button[data-variant="segmented_control"][data-selected="true"] *, button[data-variant="pills"][data-selected="true"] * { color: #fff !important; }
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
  filter: brightness(1.06); }
/* light glass: normal buttons, downloads, unselected pills */
[data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-secondaryFormSubmit"],
[data-testid="stBaseButton-pills"], button[data-variant="pills"]:not([data-selected="true"]) {
  background: linear-gradient(180deg, rgba(255,255,255,.92), rgba(230,237,255,.6)) !important;
  border: 1px solid #fff !important;
  -webkit-backdrop-filter: blur(16px); backdrop-filter: blur(16px);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.9), 0 4px 12px -3px rgba(30,79,216,.16) !important;
}
[data-testid="stBaseButton-secondary"]:hover, [data-testid="stBaseButton-pills"]:hover {
  border-color: rgba(30,79,216,.35) !important; color: var(--pm-blue) !important; }
[data-testid="stBaseButton-pills"], [data-testid="stBaseButton-pillsActive"], button[data-variant="pills"] { border-radius: 999px !important; }
/* segmented control: soft track, glass selection */
button[data-variant="segmented_control"]:not([data-selected="true"]) { background: rgba(255,255,255,.75) !important; }

/* frosted form / filter bar */
[data-testid="stForm"] {
  background: #fff; border: 1px solid var(--pm-line) !important; border-radius: 14px;
  box-shadow: var(--pm-shadow); }

/* tabs as a glass segmented switch */
[data-testid="stTabs"] [role="tablist"] { gap: 2px; background: rgba(227,233,247,.8); padding: 4px; border-radius: 12px;
  width: fit-content; border: none !important; box-shadow: none !important; }
[data-testid="stTab"] { border-radius: 9px !important; padding: 6px 16px !important; height: auto !important; border: none !important; }
[data-testid="stTab"][aria-selected="true"] {
  background: linear-gradient(180deg, rgba(91,131,242,.95), rgba(30,79,216,.86));
  box-shadow: inset 0 1px 0 rgba(255,255,255,.55), 0 6px 16px -4px rgba(30,79,216,.45); }
[data-testid="stTab"][aria-selected="true"] * { color: #fff !important; font-weight: 600; }
[data-testid="stTab"]::after { display: none !important; }

/* white cards */
[data-testid="stVerticalBlockBorderWrapper"]:has(> div > [data-testid="stVerticalBlock"]) { border-color: var(--pm-line); }
[data-testid="stDataFrame"] { background: #fff; border: 1px solid var(--pm-line); border-radius: 14px; padding: 4px;
  box-shadow: var(--pm-shadow); }
[data-testid="stMetric"] { background: #fff; border: 1px solid var(--pm-line); border-radius: 14px; padding: 12px 16px; }
[data-testid="stMetricLabel"] { opacity: .75; }

/* subtitle under page titles */
.page-sub { font-size: 1.05rem; font-weight: 600; margin: -0.4rem 0 0.2rem 0; }
/* ---- KPI cards ---- */
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 16px; margin: .4rem 0 1rem 0; }
.kpi { border: 1px solid var(--pm-line); border-radius: 14px; padding: 16px 18px; background: #fff; box-shadow: var(--pm-shadow); }
.kpi .kl { font-size: .82rem; color: var(--pm-mute); font-weight: 500; }
.kpi .kv { font-size: 1.9rem; font-weight: 700; letter-spacing: -.02em; line-height: 1.25; margin-top: 4px; color: var(--pm-navy); }
.kpi .kd { font-size: .78rem; color: var(--pm-mute); }
.kpi.alert { border-color: #F5C77A; background: #FFF6E5; }
.kpi.alert .kl, .kpi.alert .kv, .kpi.alert .kd { color: #B45309; }
.applied { margin: .2rem 0 .6rem 0; font-size: .92rem; display: flex; gap: .6rem; align-items: center; flex-wrap: wrap; color: var(--pm-mute); }
.applied b { font-weight: 600; color: var(--pm-ink); }
.sortpill { border: 1px solid var(--pm-line); background: #fff; border-radius: 20px; padding: 2px 10px; font-size: .78rem; }
/* ---- lead panel ---- */
.lc { border: 1px solid var(--pm-line); border-radius: 14px; padding: 18px; margin-bottom: .6rem; background: #fff; }
.lc.empty { border-style: dashed; background: rgba(255,255,255,.6); }
.lc-top { display: flex; justify-content: space-between; gap: 8px; align-items: flex-start; }
.lc-id { font-size: .7rem; font-weight: 700; letter-spacing: .06em; color: var(--pm-mute); }
.lc-name { font-size: 1.2rem; font-weight: 700; margin-top: 2px; line-height: 1.3; color: var(--pm-navy); }
.lc-meta { font-size: .85rem; color: var(--pm-mute); margin-top: 2px; }
.pillst { background: var(--pm-light); color: var(--pm-blue); border-radius: 6px; padding: 3px 8px; font-size: .75rem; font-weight: 600; white-space: nowrap; }
.lc-warn { margin-top: 10px; background: #FFF6E5; border: 1px solid #F5C77A; color: #8a4b00;
           border-radius: 8px; padding: 8px 10px; font-size: .82rem; }
.lc-kv { display: grid; grid-template-columns: 105px 1fr; gap: 7px 10px; margin-top: 12px; font-size: .84rem; }
.lc-kv span:nth-child(odd) { color: var(--pm-mute); }
.lc-kv span:nth-child(even) { font-weight: 600; }
.ok { color: #127a4a; font-weight: 600; }
.mini { margin-top: 14px; border-top: 1px solid var(--pm-line); padding-top: 12px; }
.mini h4 { font-size: .85rem; font-weight: 700; margin: 0 0 8px 0; padding: 0; }
.mrow { display: flex; justify-content: space-between; gap: 8px; padding: 8px 10px; font-size: .8rem;
        background: #F6F8FC; border-radius: 8px; margin-bottom: 6px; }
.mrow span:last-child { color: var(--pm-blue); font-weight: 600; }
.mrow.muted { background: none; color: var(--pm-mute); }
/* ---- management top bar ---- */
.pm-top { display: flex; align-items: center; gap: 16px; background: var(--pm-navy); margin: -1rem 0 1.6rem;
          padding: 14px 0; box-shadow: 0 0 0 100vmax var(--pm-navy); clip-path: inset(-100vmax -100vmax 0 -100vmax); }
.pm-top img { height: 30px; }
.pm-top .sp { flex: 1; }
.pm-top .ro { border: 1px solid rgba(255,255,255,.18); background: rgba(255,255,255,.08); color: #D6DFF5;
              border-radius: 999px; padding: 5px 12px; font-size: .75rem; font-weight: 500; }
.pm-top .upd { color: #9FB3E0; font-size: .75rem; }
.pm-top .upd .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #34D399; margin-right: 6px; }
/* ---- shared top bar ---- */
.st-key-pm_topbar { background: rgba(255,255,255,.78); border: 1px solid var(--pm-line); border-radius: 14px; padding: 8px 12px;
  -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px); box-shadow: var(--pm-shadow);
  margin: -.6rem 0 .9rem 0; }
.st-key-pm_topbar [data-testid="stTextInputRootElement"], .st-key-pm_topbar [data-baseweb="select"] > div {
  background: linear-gradient(180deg, rgba(255,255,255,.95), rgba(238,243,255,.75)); border-color: #fff; border-radius: 10px; }
.st-key-g_refresh button p { white-space: nowrap; }
.st-key-g_refresh button { padding: .3rem .55rem !important; gap: .3rem; }
.st-key-g_prev button, .st-key-g_next button { font-size: 1.15rem; font-weight: 700; color: var(--pm-blue) !important; padding: 0 !important; }
.st-key-pm_topbar [data-testid="stButtonGroup"] { flex-wrap: nowrap; }
.st-key-pm_topbar [data-testid="stButtonGroup"] button { padding: .3rem .42rem !important; min-height: 2.35rem; }
.st-key-pm_topbar [data-testid="stButtonGroup"] button p { font-size: .8rem !important; white-space: nowrap; }
/* week-over-week change */
.dl { display: inline-block; font-size: .72rem; font-weight: 700; border-radius: 6px; padding: 2px 7px; margin-left: 10px;
      vertical-align: middle; letter-spacing: 0; line-height: 1.5; background: #F1F1F3; color: #5F6168; }
.dl.up { background: #E3F6EA; color: #137A43; }
.dl.down { background: #FDECEA; color: #C0392B; }
/* card headers */
.card-h { font-size: 1rem; font-weight: 700; color: var(--pm-ink); margin: 0 0 6px 0; display: flex;
          justify-content: space-between; align-items: baseline; gap: 8px; }
.card-h span { font-size: .78rem; font-weight: 400; color: var(--pm-mute); }
.st-key-pm_chart, .st-key-pm_board, .st-key-nr_queue, .st-key-nr_pick { background: #fff; border-radius: 14px !important;
  border: 1px solid var(--pm-line) !important; box-shadow: var(--pm-shadow); }
/* chart and rep board: same height, bottoms line up */
[data-testid="stColumn"]:has(.st-key-pm_chart), [data-testid="stColumn"]:has(.st-key-pm_board) {
  align-self: stretch !important; height: auto !important; display: flex !important; flex-direction: column; }
[data-testid="stColumn"]:has(.st-key-pm_chart) > [data-testid="stVerticalBlock"],
[data-testid="stColumn"]:has(.st-key-pm_board) > [data-testid="stVerticalBlock"] { flex: 1 1 auto !important; height: auto !important; }
[data-testid="stLayoutWrapper"]:has(> .st-key-pm_chart), [data-testid="stLayoutWrapper"]:has(> .st-key-pm_board) {
  flex: 1 1 auto !important; height: auto !important; }
.st-key-pm_chart, .st-key-pm_board { height: 100% !important; }
/* empty states: calm centered card */
[class*="st-key-empty_"] { background: #fff; border: 1px solid var(--pm-line); border-radius: 14px; box-shadow: var(--pm-shadow);
  padding: 44px 24px 40px; align-items: center; }
.empty-card { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 6px; }
.empty-card .ec-ic { font-family: 'Material Symbols Rounded'; font-size: 30px; line-height: 1; color: #8FA0C4; background: #F1F4FA;
  border-radius: 50%; padding: 14px; margin-bottom: 6px; font-feature-settings: 'liga'; }
.empty-card .ec-t { font-size: 1.05rem; font-weight: 700; color: var(--pm-ink); }
.empty-card .ec-n { font-size: .88rem; color: var(--pm-mute); }
[class*="st-key-empty_"] .stButton { display: flex; justify-content: center; margin-top: .4rem; }
/* page title row: title and export buttons on one line, compact buttons */
.st-key-cr_export button { min-height: 2.1rem !important; padding: .2rem .8rem !important; }
.st-key-cr_export button p { font-size: .85rem !important; }
/* rep board */
.rb-row { display: grid; grid-template-columns: 34px 1fr auto 58px; gap: 12px; align-items: center; padding: 7px 0; }
.rb-av { width: 34px; height: 34px; border-radius: 50%; background: var(--pm-light); color: var(--pm-blue); font-weight: 700;
         font-size: .72rem; display: flex; align-items: center; justify-content: center; }
.rb-row.on .rb-av { background: var(--pm-blue); color: #fff; }
.rb-name { font-size: .84rem; font-weight: 600; color: var(--pm-ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rb-talk { font-weight: 400; color: var(--pm-mute); font-size: .72rem; margin-top: 3px; }
.rb-bar { height: 6px; background: var(--pm-light); border-radius: 3px; margin-top: 6px; overflow: hidden; }
.rb-bar i { display: block; height: 100%; border-radius: 3px; }
.rb-n { font-size: 1rem; font-weight: 700; color: var(--pm-navy); text-align: right; }
.rb-row .dl { margin-left: 0; }
.rb-more { font-size: .78rem; color: var(--pm-mute); padding-top: 4px; }
/* Needs Review */
.nr-sum { display: flex; gap: 28px; align-items: baseline; background: #fff; border: 1px solid var(--pm-line);
          border-radius: 14px; padding: 12px 18px; margin: .2rem 0 .9rem 0; color: var(--pm-mute); font-size: .88rem; }
.nr-sum b { font-size: 1.35rem; color: var(--pm-navy); margin-right: 4px; }
.nr-sum .sp { flex: 1; }
.nr-title { font-size: 1.3rem; font-weight: 700; color: var(--pm-navy); margin-bottom: -4px; }
.st-key-nr_queue [data-testid="stRadioGroup"] { gap: 2px; width: 100%; }
.st-key-nr_queue [data-testid="stRadioGroup"] > div { width: 100%; }
.st-key-nr_queue [data-testid="stRadioOption"] { width: 100%; padding: 9px 12px; border-radius: 10px; margin: 0; cursor: pointer; }
.st-key-nr_queue [data-testid="stRadioOption"] > div > div:first-child { display: none; }
.st-key-nr_queue [data-testid="stRadioOption"]:hover { background: #F6F8FC; }
.st-key-nr_queue [data-testid="stRadioOption"][data-selected="true"] {
  background: linear-gradient(90deg, rgba(220,230,255,.95), rgba(238,243,255,.6)); box-shadow: inset 3px 0 0 var(--pm-blue); }
.st-key-nr_queue [data-testid="stRadioOption"] p { font-size: .8rem; color: var(--pm-mute); line-height: 1.5; margin: 0; }
.st-key-nr_queue [data-testid="stRadioOption"] p strong { color: var(--pm-ink); font-size: .93rem; font-weight: 600; }
[class*="st-key-nr_c"] { background: #fff; border-radius: 14px !important; }
[class*="st-key-nr_c_sug"] { border: 1.5px solid #5B83F2 !important; box-shadow: 0 10px 24px -8px rgba(30,79,216,.28); }
.nr-card .lc-name { font-size: 1.05rem; margin: 2px 0 6px 0; }
.bds { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 8px; }
.bd { font-size: .7rem; font-weight: 700; border-radius: 6px; padding: 2px 7px; }
.bd.sug { background: var(--pm-blue); color: #fff; }
.bd.own { background: #E3F6EA; color: #137A43; }
.bd.new { background: var(--pm-light); color: var(--pm-blue); }
.bd.old { background: #F1F1F3; color: #5F6168; }
.nr-kv { display: grid; gap: 7px; margin: 12px 0 4px 0; }
.nr-kv div { display: flex; flex-direction: column; }
.nr-kv span { font-size: .7rem; color: var(--pm-mute); }
.nr-kv b { font-size: .84rem; font-weight: 600; color: var(--pm-ink); }
/* ---- Appointments calendar ---- */
.cal-legend { display: flex; flex-wrap: wrap; gap: 16px; font-size: .8rem; color: #374151; margin: .2rem 0 .6rem 2px; }
.cal-legend i { display: inline-block; width: 11px; height: 11px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; }
.cal-legend .sp { flex: 1; } .cal-legend span:last-child { color: var(--pm-mute); }
.cal { background: #fff; border: 1px solid var(--pm-line); border-radius: 18px; display: grid; overflow: hidden;
       box-shadow: 0 8px 24px rgba(30,79,216,.06); margin-bottom: .8rem; }
.cal-gut { position: relative; border-right: 1px solid var(--pm-line); margin-top: 58px; }
.cal-hr { position: absolute; left: 0; right: 0; } .cal-hr span { position: absolute; right: 8px; top: -2px; font-size: .8rem; color: var(--pm-ink); font-weight: 800; white-space: nowrap; }
.cal-col { border-right: 1px solid #EEF1F7; min-width: 0; } .cal-col:last-child { border-right: none; }
.cal-dh { height: 58px; border-bottom: 1px solid var(--pm-line); padding: 10px 12px; display: flex; align-items: baseline; gap: 7px; background: #FAFBFE; }
.cal-dh b { font-size: .9rem; } .cal-dh span { font-size: 1.25rem; font-weight: 700; color: var(--pm-navy); white-space: nowrap; }
.cal-dh em { margin-left: auto; font-style: normal; font-size: .7rem; color: var(--pm-mute); background: var(--pm-light); border-radius: 999px; padding: 2px 8px; white-space: nowrap; }
.cal-col.today .cal-dh { background: var(--pm-light); } .cal-col.today .cal-dh span { color: var(--pm-blue); }
.cal-body { position: relative; background: repeating-linear-gradient(#fff 0, #fff 51px, #F5F7FB 51px, #F5F7FB 52px, #fff 52px, #fff 103px, #C9D3E6 103px, #C9D3E6 104px); }
.cal-ev { position: absolute; height: 49px; background: var(--bg); border-left: 4px solid var(--c); border-radius: 9px;
          padding: 6px 9px; box-shadow: 0 2px 6px rgba(11,31,77,.08); overflow: hidden; }
.cal-ev.unas { border: 1.5px dashed #E8A33C; border-left: 4px solid #E8A33C; background: #FFF7EA; }
.cal-ev.cxl { opacity: .55; }
.cal-t { display: flex; justify-content: space-between; align-items: center; gap: 4px; font-size: .72rem; }
.cal-t b { color: var(--c); white-space: nowrap; }
.cal-r { display: flex; justify-content: space-between; gap: 6px; margin-top: 3px; align-items: baseline; }
.cal-c { font-size: .8rem; font-weight: 700; color: var(--pm-ink); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cal-w { font-size: .72rem; font-weight: 600; color: #4B5563; flex: none; max-width: 45%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cal-ok, .cal-no, .cal-up, .cal-un { font-size: .66rem; font-weight: 700; border-radius: 5px; padding: 1px 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cal-ok { background: #fff; color: #137A43; } .cal-no { background: #FDECEA; color: #C0392B; }
.cal-up { background: #fff; color: var(--pm-mute); } .cal-un { background: #fff; color: #B45309; }
/* Commissions */
.kpis { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
.st-key-pm_email { background: linear-gradient(180deg, rgba(255,255,255,.95), rgba(233,239,255,.9)); border-radius: 14px !important;
                   border-color: #A9C1FF !important; margin-top: .4rem; }
.em-h { font-size: .82rem; color: var(--pm-blue); font-weight: 600; }
.em-t { font-size: 1rem; color: var(--pm-navy); font-weight: 700; margin-bottom: 2px; }
.pp-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin: .3rem 0 1rem 0; }
.pp { background: #fff; border: 1px solid var(--pm-line); border-radius: 14px; padding: 14px 16px; }
.pp-top { display: flex; justify-content: space-between; align-items: center; gap: 6px; }
.pp-name { font-weight: 700; color: var(--pm-navy); font-size: .92rem; }
.pp-cnt { font-size: .7rem; font-weight: 700; background: var(--pm-light); color: var(--pm-blue); border-radius: 6px; padding: 2px 7px; }
.pp-amt { font-size: 1.45rem; font-weight: 700; color: var(--pm-ink); margin-top: 6px; letter-spacing: -.01em; }
.pp-sub { font-size: .76rem; color: var(--pm-mute); }
.pp-lines { border-top: 1px solid var(--pm-line); margin-top: 10px; padding-top: 8px; display: grid; gap: 4px; font-size: .8rem; }
.pp-lines div { display: flex; justify-content: space-between; color: var(--pm-mute); }
.pp-lines b { color: var(--pm-ink); }
.pp-lines .tot b { color: #137A43; font-size: .92rem; }
.pp-lines .warn { color: #B45309; }
/* ---- lead drawer: details box + call timeline ---- */
.dname { font-size: 1.45rem; font-weight: 700; color: var(--pm-navy); line-height: 1.25; margin: 2px 0 8px; }
.dkv { display: grid; grid-template-columns: 125px 1fr; gap: 9px 12px; background: #F7F9FD; border: 1px solid var(--pm-line);
       border-radius: 12px; padding: 14px 16px; margin: 14px 0 4px; font-size: .86rem; }
.dkv span:nth-child(odd) { color: var(--pm-mute); }
.dkv span:nth-child(even) { font-weight: 600; color: var(--pm-ink); text-align: right; overflow-wrap: anywhere; }
.dsec { font-size: 1rem; font-weight: 700; color: var(--pm-ink); margin: 18px 0 10px; }
.tl-row { display: grid; grid-template-columns: 16px 1fr auto; gap: 12px; position: relative; padding-bottom: 16px; }
.tl-rail { position: relative; }
.tl-rail i { position: absolute; left: 3px; top: 4px; width: 10px; height: 10px; border-radius: 50%;
             background: var(--pm-blue); box-shadow: 0 0 0 3px var(--pm-light); }
.tl-row:not(:last-child) .tl-rail::after { content: ""; position: absolute; left: 7px; top: 18px; bottom: -2px;
             width: 2px; background: #D9E1F2; border-radius: 1px; }
.tl-body b { display: block; font-size: .86rem; font-weight: 600; color: var(--pm-ink); line-height: 1.3; }
.tl-body span { font-size: .78rem; color: var(--pm-mute); }
.tl-len { font-size: .86rem; font-weight: 600; color: var(--pm-blue); }
.tl-more { font-size: .78rem; color: var(--pm-mute); padding-left: 28px; }
.rchips { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0 0; }
.rchips span { background: var(--pm-light); color: var(--pm-ink); border-radius: 8px; padding: 4px 10px; font-size: .8rem; }
.rchips b { color: var(--pm-blue); margin-right: 3px; }
/* ---- Appointments ---- */
.ap-colh { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.ap-colh .av { width: 34px; height: 34px; border-radius: 50%; background: var(--pm-light); color: var(--pm-blue);
               font-weight: 700; font-size: .72rem; display: flex; align-items: center; justify-content: center; flex: none; }
.ap-colh b { font-size: .92rem; color: var(--pm-ink); display: block; }
.ap-colh span { font-size: .75rem; color: var(--pm-mute); }
.ap-day { font-size: .68rem; font-weight: 700; letter-spacing: .07em; color: var(--pm-mute); margin: 8px 0 -6px; text-transform: uppercase; }
.ap { border: 1px solid var(--pm-line); border-left: 3px solid var(--pm-blue); border-radius: 10px; padding: 9px 11px;
      background: #FBFCFF; margin-bottom: -10px; }
.ap.done { border-left-color: #137A43; } .ap.noshow { border-left-color: #C0392B; } .ap.cxl { border-left-color: #9CA3AF; opacity: .7; }
.ap-t { display: flex; justify-content: space-between; gap: 6px; font-size: .74rem; color: var(--pm-mute); }
.ap-t b { color: var(--pm-blue); font-weight: 700; }
.ap-c { font-size: .86rem; font-weight: 700; color: var(--pm-ink); margin-top: 2px; line-height: 1.3; }
.ap-p { font-size: .75rem; color: var(--pm-mute); }
.st { display: inline-block; font-size: .7rem; font-weight: 700; border-radius: 6px; padding: 2px 7px; }
.st.showed, .st.sold { background: #E3F6EA; color: #137A43; } .st.no_show { background: #FDECEA; color: #C0392B; }
.st.canceled { background: #F1F1F3; color: #5F6168; } .st.rescheduled { background: #FFF4E0; color: #9A5B00; }
.bd.warn { background: #FDECEA; color: #C0392B; }
.bd.rfp { background: #E3F6EA; color: #0B7A55; }
.cal-rfp { background: #fff; color: #0B7A55; }
.cal-rfp { font-size: .66rem; font-weight: 700; border-radius: 5px; padding: 1px 6px; white-space: nowrap; }
.un { background: #FFF7EA; border: 1px solid #F5C77A; border-radius: 14px; padding: 12px 14px; }
.un-c { font-weight: 700; color: var(--pm-ink); font-size: .92rem; margin-top: 2px; }
.un-m { font-size: .78rem; color: #8a4b00; }
.sug { font-size: .74rem; color: #137A43; font-weight: 600; margin-top: 4px; }
[class*="st-key-ap_col_"] { background: #fff; border-radius: 16px !important; }
[class*="st-key-ap_open_"] button { padding: 0 !important; min-height: 1.6rem !important; font-size: .78rem !important;
                                   color: var(--pm-blue) !important; justify-content: flex-end; width: 100%; }
[class*="st-key-ap_open_"] button p { font-size: .78rem !important; }
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
# VIEWER_PASSWORD -> management: Call Log (read-only) and Appointments (full, same as admin) (role "viewer")
# SETTER_PASSWORD -> appointment setter: Appointments, lead appointments only (role "setter")
def is_viewer() -> bool:
    return st.session_state.get("role", "admin") == "viewer"


def is_setter() -> bool:
    return st.session_state.get("role", "admin") == "setter"


def password_ok() -> bool:
    try:
        admin_pw = st.secrets.get("APP_PASSWORD")
        viewer_pw = st.secrets.get("VIEWER_PASSWORD")
        setter_pw = st.secrets.get("SETTER_PASSWORD")
    except Exception:
        admin_pw = viewer_pw = setter_pw = None
    if st.session_state.get("authed"):
        return True
    if not admin_pw:
        st.session_state["role"] = "admin"
        return True
    st.markdown(f'<img src="{LOGO_DARK_URI}" style="height:44px;margin:1.5rem 0 1rem">',
                unsafe_allow_html=True)
    st.title("Call Report")
    pw = st.text_input("Password", type="password")
    if pw:
        if hmac.compare_digest(pw, str(admin_pw)):
            st.session_state.update(authed=True, role="admin")
            st.rerun()
        if viewer_pw and hmac.compare_digest(pw, str(viewer_pw)):
            st.session_state.update(authed=True, role="viewer")
            st.rerun()
        if setter_pw and hmac.compare_digest(pw, str(setter_pw)):
            st.session_state.update(authed=True, role="setter", ap_kind="Lead appts")
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


def lead_card(r, df: pd.DataFrame, inline: bool = False):
    """Lead details for the selected call (shown in the side drawer)."""
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
    calls = df[df["To"] == r["To"]].sort_values("Date/Time", ascending=False)
    confirmed = ('<span class="bd own">✓ Lead confirmed</span>'
                 if n_leads <= 1 or r["Lead Choice"] == "Picked" else "")
    src = (rec.get("Lead Source") or "").upper()
    kv = "".join(f"<span>{k}</span><span>{v}</span>" for k, v in
                 [("Contact", esc(rec.get("Contact Name (phase2)"))), ("Market", esc(rec.get("Media Market")))] if v) + kv
    dkv = f'<div class="dkv">{kv}</div>' if kv else ""
    st.markdown(
        f'<div class="lc-id">LEAD {esc(lead_id)}{" · " + esc(src) if src else ""}</div>'
        f'<div class="dname">{esc(rec.get("Company In Ad") or rec.get("Company (phase2)") or "")}</div>'
        f'<div class="bds">{_status_pill(rec.get("Status"))}{confirmed}</div>{warn}{dkv}'
        f'<div class="dsec">Calls to this number · {len(calls)}</div>{timeline_html(calls, 12)}',
        unsafe_allow_html=True)
    b1, b2 = st.columns(2)
    if b1.button("Open full lead", width="stretch", key=f"open_{lead_id}"):
        st.session_state["ls_q"] = lead_id
        st.switch_page(PAGE_LEAD_SEARCH)
    if b2.button("Change lead", width="stretch", key=f"chg_{r['call_id']}", disabled=n_leads < 2,
                 help=None if n_leads >= 2 else "This number only matches one lead"):
        if inline:
            st.session_state["chg_open"] = None if st.session_state.get("chg_open") == r["call_id"] else r["call_id"]
        else:
            pick_lead_dialog(number, lead_id, str(r["Lead Choice"]))
    if inline and st.session_state.get("chg_open") == r["call_id"]:
        st.markdown(f"**{fmt_phone(number)}** matches {n_leads} leads. Click the right one, then **Use lead** — "
                    "it applies to every call to this number.")
        render_pick(number, lead_id, str(r["Lead Choice"]), "drw")


REP_COLORS = ["#1E4FD8", "#5B83F2", "#A9C1FF", "#0B1F4D", "#7C93C9", "#3B5BA9", "#C9D6F5", "#94A3B8",
              "#64748B", "#CBD5E1", "#1E3A8A", "#93C5FD"]


def prev_range(start: date, end: date) -> tuple:
    """The period to compare against: same days last week (up to a week), same days of last month
    (month to date), otherwise the same number of days just before."""
    n = (end - start).days + 1
    if start.day == 1 and n > 7:
        pe = start - timedelta(days=1)
        ps = pe.replace(day=1)
        return ps, min(ps + timedelta(days=n - 1), pe), "last month"
    if n <= 7:
        return start - timedelta(days=7), end - timedelta(days=7), ("same day last week" if n == 1 else "last week")
    return start - timedelta(days=n), start - timedelta(days=1), "the previous period"


def delta_html(cur: float, prev: float) -> str:
    if not prev:
        return ""
    pct = round((cur - prev) / prev * 100)
    cls, arrow = ("up", "▲") if pct > 0 else ("down", "▼") if pct < 0 else ("flat", "•")
    return f'<span class="dl {cls}">{arrow} {abs(pct)}%</span>'


def _cr_prep(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = apply_rep_names(df)
    df["Times Called"] = df.groupby("To")["To"].transform("count").astype(int)
    df["Leads Matched"] = pd.to_numeric(df["Leads Matched"], errors="coerce").fillna(0).astype(int)
    return df


def _cr_filter(df: pd.DataFrame, direction: str, show: str, reps=None) -> pd.DataFrame:
    if df.empty:
        return df
    v = df
    if reps is not None:
        v = v[v["From"].astype(str).isin(reps)]
    if direction != "All":
        v = v[v["Direction"].fillna("").str.lower() == DIRECTIONS[direction]]
    needs = (v["Leads Matched"] >= 2) & (v["Lead Choice"] != "Picked")
    if show == "Matched":
        v = v[v["Lead Id"] != "Not Found"]
    elif show == "Not found":
        v = v[v["Lead Id"] == "Not Found"]
    elif show == "Needs pick":
        v = v[needs]
    return v


def rep_order(v: pd.DataFrame) -> list:
    return list(v["From"].fillna("Unknown").astype(str).value_counts().index) if not v.empty else []


def calls_chart(v: pd.DataFrame, start: date, end: date, order: list, title: str = "Calls by day", height: int = 230):
    """Stacked bars of calls per day (per hour for a single day), one color per rep.
    Every day gets a faint track bar, so quiet days don't leave a gap."""
    import altair as alt
    import json
    single = start == end
    head = "Calls by hour" if single else title
    st.markdown(f'<div class="card-h">{head}<span>{plural(len(v), "call")}</span></div>', unsafe_allow_html=True)
    if v.empty:
        st.caption("No calls in this range.")
        return
    d = v.assign(_rep=v["From"].fillna("Unknown").astype(str))
    if single:
        d["_k"] = d["Date/Time"].dt.hour
        keys = list(range(min(8, int(d["_k"].min())), max(18, int(d["_k"].max())) + 1))
        label = {h: f"{(h % 12) or 12} {'AM' if h < 12 else 'PM'}" for h in keys}
    else:
        d["_k"] = d["Date/Time"].dt.date
        days = (end - start).days + 1
        keys = [start + timedelta(days=i) for i in range(days)] if days <= 62 else sorted(d["_k"].unique())
        label = {k: (f"{k:%a} {k.month}/{k.day}" if days <= 14 else f"{k.month}/{k.day}") for k in keys}
    agg = d.groupby(["_k", "_rep"]).size().reset_index(name="Calls")
    agg["Day"] = agg["_k"].map(label)
    tot = agg.groupby("Day", as_index=False)["Calls"].sum()
    tot = pd.concat([tot, pd.DataFrame({"Day": [label[k] for k in keys if label[k] not in set(tot["Day"])],
                                        "Calls": 0})], ignore_index=True)
    xorder = [label[k] for k in keys]
    reps = [r for r in order if r in set(agg["_rep"])]
    colors = (REP_COLORS * 3)[:len(reps)]
    x = alt.X("Day:N", sort=xorder, title=None, axis=alt.Axis(labelAngle=0, labelColor="#6B7280", labelFont="Inter",
                                                              labelFontSize=11, domain=False, ticks=False))
    size = min(56, max(10, 560 // max(len(keys), 1)))
    top = max(int(tot["Calls"].max()), 1)
    yscale = alt.Scale(domain=[0, top * 1.12])
    track = alt.Chart(pd.DataFrame({"Day": xorder, "Calls": top * 1.12})).mark_bar(
        cornerRadius=4, size=size, color="#F1F3F8").encode(x=x, y=alt.Y("Calls:Q", axis=None, scale=yscale))
    bars = alt.Chart(agg).mark_bar(cornerRadius=4, size=size).encode(
        x=x, y=alt.Y("Calls:Q", stack="zero", scale=yscale,
                     axis=alt.Axis(title=None, labels=False, ticks=False, domain=False, tickCount=4,
                                   grid=True, gridColor="#EEF0F4", gridDash=[3, 3])),
        color=alt.Color("_rep:N", sort=reps, scale=alt.Scale(domain=reps, range=colors),
                        legend=alt.Legend(orient="top", title=None, labelFont="Inter", labelColor="#6B7280",
                                          symbolType="square", columns=min(4, max(len(reps), 1)),
                                          labelLimit=0, columnPadding=18, rowPadding=6)),
        order=alt.Order("rank:Q"),
        tooltip=[alt.Tooltip("Day:N", title="Day"), alt.Tooltip("_rep:N", title="Rep"), "Calls:Q"]
    ).transform_calculate(rank=f"indexof({json.dumps(reps)}, datum._rep)")
    labels = alt.Chart(tot).mark_text(dy=-8, font="Inter", fontWeight=600, fontSize=11, color="#111827").encode(
        x=alt.X("Day:N", sort=xorder), y=alt.Y("Calls:Q", axis=None, scale=yscale), text=alt.Text("Calls:Q"))
    chart = (track + bars + labels).properties(height=height).configure_view(stroke=None).configure_axisX(grid=False)
    st.altair_chart(chart, width="stretch", theme=None)


def rep_board(v: pd.DataFrame, pv: pd.DataFrame, order: list, picked: str, cmp_label: str):
    """Rep leaderboard: calls, talk time and change vs the comparison period."""
    st.markdown(f'<div class="card-h">Reps<span>calls · vs {esc(cmp_label)}</span></div>', unsafe_allow_html=True)
    if v.empty:
        st.caption("No calls in this range.")
        return
    reps = v["From"].fillna("Unknown").astype(str)
    g = pd.DataFrame({"n": reps.value_counts()})
    g["secs"] = v.assign(_r=reps, _s=v["Duration"].map(dur_seconds)).groupby("_r")["_s"].sum()
    prev = (pv["From"].fillna("Unknown").astype(str).value_counts() if not pv.empty else pd.Series(dtype=int))
    top = int(g["n"].max())
    rows = []
    for i, (name, r) in enumerate(g.head(8).iterrows()):
        color = (REP_COLORS * 3)[order.index(name)] if name in order else REP_COLORS[0]
        ini = "".join(w[0] for w in name.split()[:2]).upper() or "?"
        p = int(prev.get(name, 0))
        rows.append(
            f'<div class="rb-row{" on" if name == picked else ""}"><div class="rb-av">{esc(ini)}</div>'
            f'<div style="min-width:0"><div class="rb-name">{esc(name)}</div>'
            f'<div class="rb-bar"><i style="width:{max(3, round(100 * r["n"] / top))}%;background:{color}"></i></div>'
            f'<div class="rb-talk">{fmt_total(int(r["secs"]))} talk time</div></div>'
            f'<div class="rb-n">{int(r["n"]):,}</div><div>{delta_html(r["n"], p) or "<span class=dl>new</span>"}</div></div>')
    more = f'<div class="rb-more">+ {len(g) - 8} more reps</div>' if len(g) > 8 else ""
    st.markdown("".join(rows) + more, unsafe_allow_html=True)


@st.dialog("Lead", width="medium", position="right")
def lead_drawer(r, df: pd.DataFrame):
    st.markdown('<div class="pm-drawer"></div>', unsafe_allow_html=True)
    lead_card(r, df, inline=True)


def drawer_trigger(tag: str, ident) -> bool:
    """True once each time a different row is selected, so the drawer opens on a click
    and stays closed after the person closes it."""
    k = f"_drawer_{tag}"
    if ident is None:
        st.session_state[k] = None
        return False
    if st.session_state.get(k) != ident:
        st.session_state[k] = ident
        return True
    return False


def _g_this_week():
    st.session_state["g_preset"] = "This week"
    _g_preset_changed()


def empty_state(key: str, title: str, note: str = "", icon: str = "event_busy", action=None):
    """Calm, centered 'nothing to show' card (instead of a yellow warning bar).
    action = (button label, on_click callback) for a one-click way forward."""
    with st.container(key=f"empty_{key}"):
        st.markdown(f'<div class="empty-card"><span class="ec-ic">{icon}</span><div class="ec-t">{esc(title)}</div>'
                    f'<div class="ec-n">{esc(note)}</div></div>', unsafe_allow_html=True)
        if action:
            st.button(action[0], key=f"{key}_empty_action", on_click=action[1], type="primary")


def page_call_report():
    for k, v in _filter_defaults().items():  # first visit: start every filter at its default
        st.session_state.setdefault(k, v)
    st.session_state.setdefault("applied", _filter_defaults())
    a = {**_filter_defaults(), **st.session_state["applied"]}
    start, end = g_range()
    sources = a["f_sources"] or []
    started_from = a["f_started_from"]
    direction = a["f_direction"] or "All"
    show = a["f_show"] or "All"
    team_reps = g_team_reps()

    df = _cr_prep(load_calls(start, end, tuple(sorted(sources)), started_from))
    ps, pe, cmp_label = prev_range(start, end)
    pdf = _cr_prep(load_calls(ps, pe, tuple(sorted(sources)), started_from))

    try:
        source_options = load_range_sources(start, end, started_from)
    except Exception:
        source_options = load_lead_sources()
    st.session_state["f_sources"] = [x for x in (st.session_state.get("f_sources") or []) if x in source_options]

    # ---------- header: title with the export buttons on the same line, subtitle under it ----------
    h1, h2 = st.columns([4, 1.35], vertical_alignment="center")
    h1.title("Call Report")
    dl_slot = h2.container(key="cr_export")
    st.caption(f"Every call for **{esc(g_when())}**, matched to its MMS lead")

    # ---------- lead filters (dates and team are in the bar at the top) ----------
    with st.form("call_filters"):
        r = st.columns([2.5, 1.45, 1.35, 2.6, .9, 1.25], vertical_alignment="bottom")
        r[0].multiselect("Lead Source", source_options, key="f_sources", placeholder="All sources",
                         help="Only match calls to MMS leads from these sources")
        r[1].date_input("Lead started from", key="f_started_from", format="MM/DD/YYYY",
                        help="Only match calls to MMS leads started on or after this date")
        r[2].segmented_control("Direction", list(DIRECTIONS), key="f_direction")
        r[3].segmented_control("Show", SHOW_OPTIONS, key="f_show")
        r[4].form_submit_button("Reset", width="stretch", on_click=_reset_filters)
        r[5].form_submit_button("Apply", type="primary", icon=":material/filter_alt:", width="stretch",
                                on_click=_apply_filters)
    err = st.session_state.pop("apply_error", None)
    if err:
        st.warning(err)

    if df.empty:
        lead_filter = " and ".join(x for x in [
            f"from {', '.join(sources)}" if sources else "",
            f"started on or after {started_from:%m/%d/%Y}" if started_from else ""] if x)
        on_week = st.session_state.get("g_preset") == "This week"
        empty_state("cr", "No calls yet" if st.session_state.get("g_preset") == "Today" else "No calls in this date range",
                    (f"No calls match a lead {lead_filter}." if lead_filter else
                     "Calls show up here as soon as they come in."),
                    icon="call", action=None if on_week else ("View this week", _g_this_week))
        return

    pre = _cr_filter(df, direction, show, team_reps)
    ppre = _cr_filter(pdf, direction, show, team_reps)
    order = rep_order(pre)

    rep_counts = pre["From"].dropna().astype(str).value_counts() if not pre.empty else pd.Series(dtype=int)
    rep_options = [ALL_REPS] + sorted(rep_counts.index, key=str.lower)
    if st.session_state.get("rep_pick") not in rep_options:
        st.session_state["rep_pick"] = ALL_REPS
    rep_pick = st.session_state.get("rep_pick") or ALL_REPS
    froms = [] if rep_pick == ALL_REPS else [rep_pick]
    view = pre[pre["From"].astype(str).isin(froms)] if froms else pre
    pview = ppre[ppre["From"].astype(str).isin(froms)] if froms else ppre

    # ---------- summary cards, each compared with the previous period ----------
    secs = view["Duration"].map(dur_seconds)
    psecs = pview["Duration"].map(dur_seconds) if not pview.empty else pd.Series(dtype=float)
    out_n = int(view["Direction"].fillna("").str.lower().eq("outbound").sum())
    in_n = len(view) - out_n
    matched = int((view["Lead Id"] != "Not Found").sum())
    needs_n = view.loc[(view["Leads Matched"] >= 2) & (view["Lead Choice"] != "Picked"), "To"].nunique()
    avg = secs.mean() if len(view) else 0
    pavg = psecs.mean() if len(pview) else 0
    kpi_cards([
        {"label": "Calls", "value": f"{len(view):,}{delta_html(len(view), len(pview))}",
         "note": f"vs {len(pview):,} {cmp_label} · {out_n:,} out · {in_n:,} in"},
        {"label": "Talk time", "value": f"{fmt_total(secs.sum())}{delta_html(secs.sum(), psecs.sum())}",
         "note": f"avg {fmt_short(avg)} per call (was {fmt_short(pavg)})" if len(view) else ""},
        {"label": "Matched to a lead", "value": f"{matched / len(view):.0%}" if len(view) else "—",
         "note": f"{matched:,} calls · {len(view) - matched:,} not in MMS"},
        {"label": "⚑ Needs a lead picked", "value": f"{needs_n:,}", "note": "numbers match 2+ leads — see Needs Review",
         "alert": needs_n > 0},
    ])

    # ---------- chart + rep board ----------
    c1, c2 = st.columns([1.75, 1], gap="medium")
    board_rows = min(8, int(pre["From"].nunique())) if not pre.empty else 0
    with c1, st.container(border=True, key="pm_chart"):
        # chart grows with the rep board next to it, so the two cards end at the same line
        calls_chart(view, start, end, order, height=max(230, min(440, 57 * board_rows + 10)))
    with c2, st.container(border=True, key="pm_board"):
        rep_board(pre, ppre, order, rep_pick, cmp_label)

    if view.empty:
        empty_state("cr_filtered", "No calls match these filters",
                    "Try a different lead source, direction or rep.", icon="filter_alt_off")
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
            d2.download_button("Excel", xlsx, file_name=f"call_report_{start}_{end}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               icon=":material/table_view:", type="primary", width="stretch")

    # ---------- rep filter + table ----------
    st.pills("Rep", rep_options, key="rep_pick", selection_mode="single", label_visibility="collapsed",
             format_func=lambda r: f"{r}  ·  {len(pre):,}" if r == ALL_REPS else f"{r}  ·  {int(rep_counts[r]):,}")
    n_leads = view.loc[view["Lead Id"] != "Not Found", "Lead Id"].nunique()
    n_reps = view["From"].nunique()
    t_all, t_lead, t_rep = st.tabs([f"All calls  {len(view):,}", f"By lead  {n_leads:,}", f"By rep  {n_reps:,}"])
    with t_all:
        tl, tr = st.columns([3, 1.4], vertical_alignment="center")
        tl.markdown('<div class="applied"><span class="sortpill">Sorted by Rep → Market → Source → Lead → Time'
                    '</span><span>Click a call to open its lead</span></div>', unsafe_allow_html=True)
        show_all = tr.toggle("Show all columns", key="all_cols")
        call_cols = {"Date/Time": "Time", "From": "Rep", "To": "Number", "Duration": "Dur.", "Times Called": "Dialed"}
        lead_cols = {"Lead Id": "Lead", "Lead Source": "Lead Source", "Company In Ad": "Company",
                     "Lead Owner": "Owner", "Status": "Status", "Match": "Match"}
        if show_all:
            call_cols = {"Direction": "Direction", **call_cols, "Ext / ID": "Ext"}
            lead_cols = {**lead_cols, "Lead Started": "Lead Started", "Last Edited": "Last Edited",
                         "Media Market": "Market", "Contact Name (phase2)": "Contact",
                         "Phase2 Completed": "Phase2 Completed", "Matched On": "Matched On",
                         "Leads Matched": "Leads Matched"}
        table = view[list(call_cols) + list(lead_cols)].rename(columns={**call_cols, **lead_cols})
        table["Number"] = table["Number"].map(fmt_phone)

        def _cells(frame):
            css = pd.DataFrame("", index=frame.index, columns=frame.columns)
            css["Company"] = "font-weight: 600"
            for i, v in frame["Status"].items():
                k = _status_kind(v)
                if k:
                    bg, fg = STATUS_COLORS[k]
                    css.at[i, "Status"] = f"background-color: {bg}; color: {fg}; font-weight: 600"
            for i, v in frame["Dialed"].items():
                if v >= 3:
                    css.at[i, "Dialed"] = "background-color: #FDECEA; color: #C0392B; font-weight: 700"
            for i, v in frame["Match"].items():
                s = str(v)
                css.at[i, "Match"] = ("background-color: #FFF4E0; color: #9a5b00; font-weight: 700" if s.startswith("⚑")
                                      else "color: #137a43; font-weight: 600" if s.startswith("✓")
                                      else "color: #8a92a3; font-style: italic")
            return css
        styled = table.style.apply(_cells, axis=None) if len(table) <= 10000 else table
        event = st.dataframe(
            styled, key=f"calls_table_{start}_{end}_{rep_pick}_{show_all}", width="stretch", hide_index=True,
            height=min(40 + 35 * len(table), 640), on_select="rerun", selection_mode="single-row",
            column_config={
                "Time": st.column_config.DatetimeColumn(format="M/D/YY h:mm A", width=125),
                "Dialed": st.column_config.NumberColumn(width=64, help="Times this number was called in the range"),
                "Dur.": st.column_config.TextColumn(width=64),
                "Lead": st.column_config.TextColumn(width=80),
                "Match": st.column_config.TextColumn(
                    width=110, help="✓ = lead confirmed · ⚑ Pick = number matches several leads; "
                                    "open the call, then Change lead")})
        st.caption(f"{len(view):,} calls")
        sel = event.selection.rows if event and event.selection else []
        ident = f"{start}{end}{rep_pick}{show_all}-{view.iloc[sel[0]]['call_id']}" if sel and sel[0] < len(view) else None
        if drawer_trigger("cr", ident):
            lead_drawer(view.iloc[sel[0]], df)
    with t_lead:
        g = view[view["Lead Id"] != "Not Found"].groupby("Lead Id").agg(
            Company=("Company In Ad", "first"), Owner=("Lead Owner", "first"), Status=("Status", "first"),
            Source=("Lead Source", "first"), Calls=("To", "size"), Numbers=("To", "nunique"),
            Reps=("From", lambda s: ", ".join(sorted(set(s.dropna().astype(str))))),
            Last_call=("Date/Time", "max")).reset_index().sort_values("Calls", ascending=False)
        g = g.rename(columns={"Lead Id": "Lead", "Last_call": "Last call"})
        st.dataframe(styled_log(g), hide_index=True, width="stretch", height=560,
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


# =====================================================================================
# NEEDS REVIEW
# =====================================================================================
def _nr_use(phone: str, lead_id: str, nxt):
    sb.table("lead_picks").upsert({"phone10": str(phone)[-10:], "lead_id": str(lead_id),
                                   "picked_at": pd.Timestamp.now("UTC").isoformat()}, on_conflict="phone10").execute()
    _after_pick()
    st.session_state["nr_done"] = f"{fmt_phone(phone)} now uses lead {lead_id} for every call."
    if nxt:
        st.session_state["nr_sel"] = nxt


def _nr_go(phone):
    if phone:
        st.session_state["nr_sel"] = phone


@st.cache_data(ttl=300, show_spinner=False)
def calls_to_number(phone: str) -> pd.DataFrame:
    """Most recent calls to one phone number (newest first)."""
    try:
        data = sb.table("calls").select("*").eq("To", int(str(phone)[-10:])).order("ID", desc=True).limit(25) \
                 .execute().data
    except Exception:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if df.empty or "Date/Time" not in df.columns:
        return pd.DataFrame()
    df["Date/Time"] = pd.to_datetime(df["Date/Time"], format="%m/%d/%y %I:%M %p", errors="coerce")
    return apply_rep_names(df).sort_values("Date/Time", ascending=False)


def _short_date(v) -> str:
    try:
        x = pd.to_datetime(v)
        return f"{x:%b} {x.day}, {x.year}" if v else ""
    except Exception:
        return str(v or "")


def page_needs_review():
    h1, h2 = st.columns([4, 1.6], vertical_alignment="bottom")
    with h1:
        st.title("Needs Review")
        st.caption("Numbers that match 2 or more MMS leads. Pick the right lead once — every call to that "
                   "number uses it from then on.")
    span = h2.segmented_control("Called in the last", ["7 days", "30 days", "90 days"], default="30 days",
                                key="nr_days", label_visibility="collapsed") or "30 days"
    days = int(span.split()[0])
    data = load_needs_review(days)
    done = st.session_state.pop("nr_done", None)
    if done:
        st.toast(done, icon=":material/check_circle:")
    if data.empty:
        st.success("All caught up — every multi-lead number called in this period has a lead picked.")
        return
    c = load_contacts()
    c = c[c["rep"].fillna("").str.strip() != ""].sort_values("effective_from")
    names = c.groupby("from_value")["rep"].last().to_dict()
    data = data.copy()
    data["phone10"] = data["phone10"].astype(str)
    data["callers_n"] = data["callers"].map(lambda xs: sorted({names.get(x, x) for x in (xs or [])}))
    data["last_call"] = pd.to_datetime(data["last_call"])
    data = data.sort_values(["calls", "last_call"], ascending=[False, False]).reset_index(drop=True)
    phones = data["phone10"].tolist()
    if st.session_state.get("nr_sel") not in phones:
        st.session_state["nr_sel"] = phones[0]
    info = data.set_index("phone10")

    st.markdown(f'<div class="nr-sum"><span><b>{len(data):,}</b> numbers to review</span>'
                f'<span><b>{int(data["calls"].sum()):,}</b> calls affected</span>'
                f'<span class="sp"></span><span>Most-called numbers first</span></div>', unsafe_allow_html=True)

    def _label(p):
        r = info.loc[p]
        who = ", ".join(n.split()[0] for n in r["callers_n"]) or "unknown"
        return f"**{fmt_phone(p)}** · {int(r['leads_matched'])} leads  \n{plural(int(r['calls']), 'call')} · {who}"

    left, right = st.columns([1, 2.4], gap="medium")
    sel = st.session_state["nr_sel"]
    i = phones.index(sel)
    with left, st.container(border=True, key="nr_queue", height=640):
        st.markdown(f'<div class="card-h">Queue<span>{i + 1} of {len(phones)}</span></div>', unsafe_allow_html=True)
        st.radio("Queue", phones, key="nr_sel", format_func=_label, label_visibility="collapsed")

    row = info.loc[sel]
    nxt = phones[i + 1] if i + 1 < len(phones) else (phones[i - 1] if i > 0 else None)
    callers = set(row["callers_n"])
    with right, st.container(border=True, key="nr_pick"):
        st.markdown(f'<div class="nr-title">{fmt_phone(sel)} — which lead is this?</div>', unsafe_allow_html=True)
        st.caption(f"{plural(int(row['calls']), 'call')} · last call {us_time(row['last_call'])} · called by "
                   f"{', '.join(sorted(callers)) or 'unknown'}")
        leads = pd.DataFrame(sb.rpc("leads_for_number", {"p_phone": sel}).execute().data)
        if leads.empty:
            st.info("No matching leads found for this number.")
        else:
            leads["_edited"] = pd.to_datetime(leads["last_edited"], errors="coerce")
            own = leads[leads["lead_owner"].isin(callers)]
            pool = own if not own.empty else leads
            sug = pool.sort_values("_edited", ascending=False).index[0]
            newest = leads["_edited"].idxmax() if leads["_edited"].notna().any() else None
            per_row = 3 if len(leads) != 4 else 2
            for start_i in range(0, len(leads), per_row):
                cols = st.columns(per_row, gap="small")
                for col, (ix, l) in zip(cols, list(leads.iterrows())[start_i:start_i + per_row]):
                    rec = get_lead(str(l["lead_id"])) or {}
                    badges = []
                    if ix == sug:
                        badges.append('<span class="bd sug">★ Suggested</span>')
                    if l["lead_owner"] in callers:
                        badges.append('<span class="bd own">Caller owns it</span>')
                    if ix == newest:
                        badges.append('<span class="bd new">Most recently edited</span>')
                    if not badges:
                        badges.append('<span class="bd old">Older lead</span>')
                    src = str(rec.get("Lead Source") or "").upper()
                    kv = [("Contact", rec.get("Contact Name (phase2)")), ("Owner", l["lead_owner"]),
                          ("Market", l["media_market"]), ("Lead started", _short_date(rec.get("Lead Started"))),
                          ("Last edited", _short_date(l["last_edited"])), ("Number found in", l.get("matched_on"))]
                    kvh = "".join(f"<div><span>{k}</span><b>{esc(v) if v else '—'}</b></div>" for k, v in kv)
                    with col, st.container(border=True, key=f"nr_c{'_sug' if ix == sug else ''}_{start_i}_{ix}"):
                        st.markdown(f'<div class="nr-card"><div class="bds">{"".join(badges)}</div>'
                                    f'<div class="lc-id">LEAD {esc(l["lead_id"])}{" · " + esc(src) if src else ""}</div>'
                                    f'<div class="lc-name">{esc(l["company_in_ad"] or rec.get("Company (phase2)") or "")}</div>'
                                    f'{_status_pill(l["status"])}<div class="nr-kv">{kvh}</div></div>',
                                    unsafe_allow_html=True)
                        st.button("Use this lead", key=f"nr_use_{sel}_{l['lead_id']}", width="stretch",
                                  type="primary" if ix == sug else "secondary", on_click=_nr_use,
                                  args=(sel, str(l["lead_id"]), nxt))
        hist = calls_to_number(sel)
        if not hist.empty:
            lines = "".join(f'<div class="mrow"><span>{us_time(h["Date/Time"])} · {esc(h["From"])}</span>'
                            f'<span>{esc(_short_len(h["Duration"]))}</span></div>' for _, h in hist.head(6).iterrows())
            st.markdown(f'<div class="mini"><h4>Latest calls to this number</h4>{lines}</div>', unsafe_allow_html=True)
        b = st.columns([3, 1.1, 1.1], vertical_alignment="center")
        b[0].caption("Suggested = the calling rep's own lead, otherwise the most recently edited one.")
        b[1].button("Previous", icon=":material/arrow_back:", width="stretch", disabled=i == 0,
                    on_click=_nr_go, args=(phones[i - 1] if i else None,), key="nr_prev")
        b[2].button("Skip", icon=":material/arrow_forward:", width="stretch", disabled=i + 1 >= len(phones),
                    on_click=_nr_go, args=(phones[i + 1] if i + 1 < len(phones) else None,), key="nr_next")


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


@st.cache_data(ttl=300, show_spinner=False)
def load_rep_emails() -> dict:
    """{rep name: email} from the rep_emails table (where appointment notices go)."""
    try:
        return {r["rep"]: r["email"] for r in sb.table("rep_emails").select("rep, email").execute().data if r.get("email")}
    except Exception:
        return {}


def rep_email_editor():
    """Admin: each Sales Team rep's email, for 'you've been assigned an appointment' notices."""
    emails = load_rep_emails()
    reps = sorted(set(load_rep_teams().get("Sales Team", set())) | set(emails), key=str.lower)
    missing = [r for r in reps if not emails.get(r)]
    with st.expander(f"Rep emails · {len(reps) - len(missing)} of {len(reps)} set", icon=":material/mail:"):
        st.caption("When a rep is assigned an appointment, they get an email with a calendar invite at this address. "
                   "Reps on the Sales Team are listed; leave a box empty to skip that rep.")
        shown = pd.DataFrame({"Rep": reps, "Email": [emails.get(r, "") for r in reps]})
        ed = st.data_editor(shown, hide_index=True, width="stretch", num_rows="fixed", key="rep_emails_editor",
                            disabled=["Rep"],
                            column_config={"Email": st.column_config.TextColumn(validate=r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$")})
        changed = ed[ed["Email"].fillna("").str.strip() != shown["Email"]]
        if st.button(f"Save {plural(len(changed), 'email')}", type="primary", disabled=changed.empty, key="rep_emails_save"):
            for _, r in changed.iterrows():
                e = str(r["Email"] or "").strip()
                if e:
                    sb.table("rep_emails").upsert({"rep": r["Rep"], "email": e}).execute()
                else:
                    sb.table("rep_emails").delete().eq("rep", r["Rep"]).execute()
            load_rep_emails.clear()
            st.rerun()


def page_contacts():
    st.title("Contacts")
    st.markdown('<div class="page-sub">Who each extension belongs to</div>', unsafe_allow_html=True)
    st.caption("Edit a name and press Enter to rename it. Use Assign New when an extension changes hands. "
               "MMS Owner Name is only needed when the person's name is spelled differently in MMS.")
    contacts = load_contacts()
    team_editor(contacts)
    rep_email_editor()
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

    raw = pd.read_csv(up, dtype=str, keep_default_na=False, low_memory=False, encoding="utf-8-sig")
    raw.columns = [str(c).replace("\ufeff", "").strip() for c in raw.columns]
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
    start, end = g_range()

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


STATUS_COLORS = {"green": ("#e3f6ea", "#137a43"), "amber": ("#fff4e0", "#9a5b00"),
                 "gray": ("#f1f1f3", "#5f6168"), "blue": ("#e8f0fe", "#1a56c4")}


def _status_kind(s) -> str:
    s = str(s or "")
    if not s:
        return ""
    if s.startswith(("09", "10")):
        return "green"
    if s.startswith(("07", "08", "14", "16")):
        return "amber"
    if s.startswith(("03", "05", "15", "Phase")):
        return "gray"
    return "blue"


def styled_log(df: pd.DataFrame, bold=("Company",), status_col="Status", extra=None):
    """Call Log look: bold company, colored status cells."""
    def _cells(frame):
        css = pd.DataFrame("", index=frame.index, columns=frame.columns)
        for c in bold:
            if c in css.columns:
                css[c] = "font-weight: 700"
        if status_col in frame.columns:
            for i, v in frame[status_col].items():
                k = _status_kind(v)
                if k:
                    bg, fg = STATUS_COLORS[k]
                    css.at[i, status_col] = f"background-color: {bg}; color: {fg}; font-weight: 600"
        if extra:
            extra(frame, css)
        return css
    return df.style.apply(_cells, axis=None)


def _short_len(d) -> str:
    secs = dur_seconds(d)
    h, rem = divmod(secs, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"


def _tl_when(t) -> str:
    try:
        t = pd.to_datetime(t)
        yr = f", {t.year}" if t.year != date.today().year else ""
        return f"{t:%a %b} {t.day}{yr} · {(t.hour % 12) or 12}:{t:%M} {'AM' if t.hour < 12 else 'PM'}"
    except Exception:
        return str(t or "")


def timeline_html(calls: pd.DataFrame, limit: int = 40) -> str:
    """Calls as a timeline: blue dot + line, date and rep on the left, call length on the right."""
    if calls is None or calls.empty:
        return '<div class="tl-more" style="padding-left:0">No calls.</div>'
    rows = "".join(
        f'<div class="tl-row"><div class="tl-rail"><i></i></div><div class="tl-body"><b>{esc(_tl_when(h["Date/Time"]))}</b>'
        f'<span>{esc(h["From"])}</span></div><div class="tl-len">{esc(_short_len(h["Duration"]))}</div></div>'
        for _, h in calls.head(limit).iterrows())
    more = f'<div class="tl-more">+ {len(calls) - limit} more</div>' if len(calls) > limit else ""
    return f'<div class="tl">{rows}</div>{more}'


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


def _toggle(key: str):
    st.session_state[key] = not st.session_state.get(key, False)


def full_lead_button(lead_id: str, tag: str):
    """'Open full lead' under the call timeline: shows every MMS field for the lead, grouped."""
    k = f"full_{tag}_{lead_id}"
    shown = st.session_state.get(k, False)
    st.button("Hide full lead" if shown else "Open full lead", key=f"btn_{k}", width="stretch",
              type="secondary" if shown else "primary",
              icon=":material/expand_less:" if shown else ":material/description:", on_click=_toggle, args=(k,))
    if not shown:
        return
    rec = get_lead(str(lead_id)) or {}
    if not rec:
        st.caption("This lead isn't in MMS any more.")
        return
    parts = []
    for title, fields in DETAIL_GROUPS.items():
        def _val(f, v):
            if "Phone" in f:
                return fmt_phone(v)
            if any(w in f for w in ("Started", "Edited", "Completed")) and f != "Started By":
                return _short_date(v)
            return v
        rows = "".join(f"<span>{esc(f.replace(' (phase2)', '').replace(' (phase3)', ''))}</span>"
                       f"<span>{esc(_val(f, rec.get(f)))}</span>" for f in fields if rec.get(f) not in (None, ""))
        if rows:
            parts.append(f"<div class='dsec'>{title}</div><div class='dkv'>{rows}</div>")
    if rec.get("Phase2 Comments"):
        parts.append(f"<div class='dsec'>Comments</div><div class='dkv' style='display:block;font-weight:400'>"
                     f"{esc(rec.get('Phase2 Comments'))}</div>")
    st.markdown("".join(parts) or "<span class='tl-more'>Nothing recorded</span>", unsafe_allow_html=True)


def _cl_lead_panel(r, calls: pd.DataFrame):
    call_day = r["Date/Time"].date() if pd.notna(r["Date/Time"]) else date.today()
    month_start = call_day.replace(day=1)
    with st.container():
        if r["Lead Id"] == "Not Found":
            st.markdown(f"<div class='lc-id'>NOT IN MMS</div><div class='dname'>{esc(fmt_phone(r['To']))}</div>",
                        unsafe_allow_html=True)
            st.caption("This number isn't on any MMS lead.")
            same = calls[calls["To"] == r["To"]]
            hist = same[(same["Date/Time"].dt.date >= month_start)].sort_values("Date/Time", ascending=False)
            title = f"Calls to this number in {month_start:%B}"
        else:
            rec = get_lead(str(r["Lead Id"])) or {}
            name = rec.get("Company In Ad") or rec.get("Company (phase2)") or r.get("Company In Ad") or ""
            src = rec.get("Lead Source") or ""
            st.markdown(f"<div class='lc-id'>LEAD {esc(r['Lead Id'])}{' · ' + esc(src.upper()) if src else ''}</div>"
                        f"<div class='dname'>{esc(name)}</div><div class='bds'>{_status_pill(rec.get('Status'))}</div>",
                        unsafe_allow_html=True)

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
            if kv:
                st.markdown(f"<div class='dkv'>{kv}</div>", unsafe_allow_html=True)
            hist = calls_to_lead_in_month(str(r["Lead Id"]), month_start)
            title = f"Calls to this lead in {month_start:%B}"
        st.markdown(f"<div class='dsec'>{title} · {len(hist)}</div>{timeline_html(hist, 40)}",
                    unsafe_allow_html=True)
    if r["Lead Id"] != "Not Found":
        full_lead_button(str(r["Lead Id"]), "cl")


@st.cache_data(ttl=300, show_spinner=False)
def load_rep_teams() -> dict:
    """{team name: set of rep names} from the rep_teams table."""
    teams = {}
    for r in sb.table("rep_teams").select("team, rep").execute().data:
        teams.setdefault(r["team"], set()).add(r["rep"])
    return teams


EVERYONE = "Everyone"


def page_call_log():
    st.markdown("<h1 style='margin-bottom:0'>Call Log</h1>", unsafe_allow_html=True)
    st.caption("Every rep call, matched to its MMS lead. Click a row to see the lead.")
    t_calls, t_leads = st.tabs(["Calls", "Leads"])
    with t_calls:
        _calls_tab()
    with t_leads:
        _leads_tab()


def _calls_tab():
    st.session_state.setdefault("cl_preset", "Yesterday")
    st.session_state.setdefault("cl_week", None)
    st.session_state.setdefault("cl_sources", [])
    if st.session_state.get("cl_week") not in [None] + att_week_options():
        st.session_state["cl_week"] = None

    teams = load_rep_teams()
    f2 = st.columns([2.4, 5.4])
    start, end = g_range()

    calls = load_calls(start, end)
    if not calls.empty:
        calls = apply_rep_names(calls)
    src_opts = sorted(x for x in calls.get("Lead Source", pd.Series(dtype=str)).dropna().unique() if x) \
        if not calls.empty else []
    st.session_state["cl_sources"] = [x for x in st.session_state.get("cl_sources", []) if x in src_opts]
    f2[0].multiselect("Lead source", src_opts, key="cl_sources", placeholder="All lead sources")
    when = g_when()
    if calls.empty:
        st.info(f"No calls for {when}.")
        return

    # how many times each number was dialed in the picked dates (all reps)
    calls = calls.copy()
    calls["Times Dialed"] = calls.groupby("To")["To"].transform("count").astype(int)
    view = calls
    team = st.session_state.get("g_team") or EVERYONE
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
             format_func=lambda r: (f"{team if team != EVERYONE else ALL_REPS_CL}  {len(view):,}" if r == ALL_REPS_CL
                                    else f"{r}  {int(counts[r]):,}"))
    rep = st.session_state.get("cl_rep") or ALL_REPS_CL
    if rep != ALL_REPS_CL:
        view = view[view["From"].astype(str) == rep]

    secs = view["Duration"].map(dur_seconds)
    leads = view.loc[view["Lead Id"] != "Not Found", "Lead Id"].nunique()
    is_admin = st.session_state.get("role", "admin") == "admin"
    cards = [{"label": "Calls", "value": f"{len(view):,}", "note": when},
             {"label": "Leads reached", "value": f"{leads:,}", "note": ""},
             {"label": "Talk time", "value": fmt_total(secs.sum()), "note": ""}]
    if is_admin:
        dirs = view["Direction"].fillna("").str.lower()
        cards[1:1] = [{"label": "Outbound", "value": f"{int((dirs == 'outbound').sum()):,}", "note": ""},
                      {"label": "Inbound", "value": f"{int((dirs == 'inbound').sum()):,}", "note": ""}]
    kpi_cards(cards)
    if view.empty:
        st.info("No calls match these filters.")
        return

    # default order: Rep, Media Market, Lead Source, Lead ID (A-Z / low-high), then oldest call first
    def _key(col: pd.Series) -> pd.Series:
        if col.name == "Lead Id":
            return pd.to_numeric(col, errors="coerce")          # "Not Found" goes last
        if col.name == "Date/Time":
            return col
        return col.fillna("").astype(str).str.strip().str.lower().replace("", "\uffff")  # blanks last
    view = view.sort_values(["From", "Media Market", "Lead Source", "Lead Id", "Date/Time"], key=_key,
                            na_position="last", kind="stable").reset_index(drop=True)
    found = view["Lead Id"] != "Not Found"
    table = pd.DataFrame({
        "Date": pd.to_datetime(view["Date/Time"]),
        "Number": view["To"].map(fmt_phone),
        "Rep": view["From"],
        "Duration": view["Duration"].map(_short_len),
        "Lead ID": view["Lead Id"].where(found, "Not in MMS"),
        "Lead Source": view["Lead Source"].where(found, "").fillna(""),
        "Media Market": view["Media Market"].where(found, "").fillna(""),
        "Company": view["Company In Ad"].where(found, "").fillna(""),
        "Status": view["Status"].where(found, "").fillna(""),
        "Times Dialed": view["Times Dialed"],
    })
    if is_admin:
        table.insert(0, "Direction", view["Direction"].fillna("").str.capitalize())

    ev = st.dataframe(styled_log(table), hide_index=True, width="stretch",
                      height=min(38 + 35 * len(table), 700),
                      on_select="rerun", selection_mode="single-row",
                      key=f"cl_table_{start}_{end}_{rep}_{team}_{len(table)}",
                      column_config={"Date": st.column_config.DatetimeColumn(format="M/D/YY h:mm A", width=135),
                                     "Number": st.column_config.TextColumn(width=110),
                                         "Duration": st.column_config.TextColumn(width="small"),
                                     "Lead ID": st.column_config.TextColumn(width="small"),
                                     "Times Dialed": st.column_config.NumberColumn(
                                         format="%d", width="small",
                                         help="Times this number was dialed in the picked dates (all reps)")})
    sel = ev.selection.rows if ev and ev.selection else []
    ident = f"{start}{end}{rep}{team}-{sel[0]}" if sel else None
    st.caption("Click a call to open its lead")
    if drawer_trigger("cl", ident):
        cl_drawer(view.iloc[sel[0]], calls)


@st.dialog("Lead", width="medium", position="right")
def cl_drawer(r, calls: pd.DataFrame):
    st.markdown('<div class="pm-drawer"></div>', unsafe_allow_html=True)
    _cl_lead_panel(r, calls)


# ---------- Leads tab: leads created in a period, and who dialed them ----------
LD_PRESETS = ["Yesterday", "This week", "Last week", "This month", "Custom"]
LD_SHOW = ["All leads", "Called", "Not called"]


@st.cache_data(ttl=600, show_spinner="Loading leads...")
def load_leads_with_calls(start: date, end: date) -> pd.DataFrame:
    data = sb.rpc("leads_with_calls", {"p_start": str(start), "p_end": str(end)}).execute().data
    return pd.DataFrame(data, columns=["lead_id", "lead_started", "lead_source", "company", "contact", "owner",
                                       "status", "market", "calls"])


def _ld_preset_changed():
    st.session_state["ld_week"] = None


def _ld_week_changed():
    if st.session_state.get("ld_week"):
        st.session_state["ld_preset"] = None


def _ld_range() -> tuple:
    today = date.today()
    week = st.session_state.get("ld_week")
    if week:
        return week, min(week + timedelta(days=6), today)
    p = st.session_state.get("ld_preset") or "This week"
    if p == "Yesterday":
        y = today - timedelta(days=1)
        return y, y
    if p == "Last week":
        m = bweek_monday(today) - timedelta(days=7)
        return m, m + timedelta(days=6)
    if p == "This month":
        return today.replace(day=1), today
    if p == "Custom":
        c = st.session_state.get("ld_custom")
        if isinstance(c, (list, tuple)) and len(c) == 2:
            return c[0], c[1]
        if isinstance(c, (list, tuple)) and len(c) == 1:
            return c[0], c[0]
    return bweek_monday(today), today


def _leads_tab():
    st.session_state.setdefault("ld_preset", "This week")
    st.session_state.setdefault("ld_week", None)
    st.session_state.setdefault("ld_sources", [])
    st.session_state.setdefault("ld_show", "All leads")
    if st.session_state.get("ld_week") not in [None] + att_week_options():
        st.session_state["ld_week"] = None

    f2 = st.columns([2.4, 2.4, 3.0])
    start, end = g_range()

    leads = load_leads_with_calls(start, end)
    src_opts = sorted(x for x in leads["lead_source"].dropna().unique() if x)
    st.session_state["ld_sources"] = [x for x in st.session_state.get("ld_sources", []) if x in src_opts]
    f2[0].multiselect("Lead source", src_opts, key="ld_sources", placeholder="All lead sources")
    f2[1].segmented_control("Show", LD_SHOW, key="ld_show")

    when = g_when()
    if leads.empty:
        st.info(f"No leads were created {when}.")
        return

    if st.session_state["ld_sources"]:
        leads = leads[leads["lead_source"].isin(st.session_state["ld_sources"])]

    # one row per call, with rep names as of the call date
    rows = [{"lead_id": r.lead_id, **c} for r in leads.itertuples() for c in (r.calls or [])]
    calls = pd.DataFrame(rows, columns=["lead_id", "from_value", "call_time", "duration", "direction"])
    if not calls.empty:
        calls = calls.rename(columns={"from_value": "From", "call_time": "Date/Time", "duration": "Duration"})
        calls["Date/Time"] = pd.to_datetime(calls["Date/Time"])
        calls = apply_rep_names(calls)
    per = (calls.groupby("lead_id").agg(n=("lead_id", "size"), last=("Date/Time", "max"),
                                        reps=("From", lambda s: ", ".join(s.value_counts().index)))
           if not calls.empty else pd.DataFrame(columns=["n", "last", "reps"]))
    leads = leads.join(per, on="lead_id")
    leads["n"] = leads["n"].fillna(0).astype(int)

    n_all = len(leads)
    n_called = int((leads["n"] > 0).sum())
    kpi_cards([
        {"label": "Leads created", "value": f"{n_all:,}", "note": when},
        {"label": "Leads called", "value": f"{n_called:,}",
         "note": f"{n_called / n_all:.0%} of new leads" if n_all else ""},
        {"label": "Not called yet", "value": f"{n_all - n_called:,}", "note": "no call since created",
         "alert": n_all - n_called > 0},
        {"label": "Times dialed", "value": f"{int(leads['n'].sum()):,}", "note": "calls to these leads"},
    ])

    show = st.session_state.get("ld_show") or "All leads"
    if show == "Called":
        leads = leads[leads["n"] > 0]
    elif show == "Not called":
        leads = leads[leads["n"] == 0]
    if leads.empty:
        st.info("No leads match these filters.")
        return

    leads = leads.assign(_sd=pd.to_datetime(leads["lead_started"].str[:10], errors="coerce"))
    leads = leads.sort_values(["n", "last", "_sd"], ascending=[False, False, False],
                              na_position="last").reset_index(drop=True)
    table = pd.DataFrame({
        "Created": leads["_sd"].map(lambda d: f"{d.month}/{d.day}/{d:%y}" if pd.notna(d) else ""),
        "Lead ID": leads["lead_id"],
        "Company": leads["company"].fillna(""),
        "Lead Source": leads["lead_source"].fillna(""),
        "Owner": leads["owner"].fillna(""),
        "Status": leads["status"].fillna(""),
        "Times Dialed": leads["n"].map(lambda n: str(n) if n else "Not called"),
        "Dialed By": leads["reps"].fillna(""),
        "Last Call": leads["last"].map(lambda t: us_time(t) if pd.notna(t) else ""),
    })

    def _not_called(frame, css):
        for i, v in frame["Times Dialed"].items():
            css.at[i, "Times Dialed"] = ("color: #c0392b; font-weight: 600" if v == "Not called"
                                         else "font-weight: 700")

    ev = st.dataframe(styled_log(table, extra=_not_called), hide_index=True, width="stretch",
                      height=min(38 + 35 * len(table), 640), on_select="rerun", selection_mode="single-row",
                      key=f"ld_table_{start}_{end}_{show}_{len(table)}",
                      column_config={"Created": st.column_config.TextColumn(width="small"),
                                     "Lead ID": st.column_config.TextColumn(width="small"),
                                     "Times Dialed": st.column_config.TextColumn(
                                         help="Calls to this lead from the day it was created to today")})
    sel = ev.selection.rows if ev and ev.selection else []
    st.caption("Click a lead to see who dialed it and every call since it was created")
    ident = f"{start}{end}{show}-{leads.iloc[sel[0]]['lead_id']}" if sel else None
    if drawer_trigger("ld", ident):
        r = leads.iloc[sel[0]]
        lc = calls[calls["lead_id"] == r["lead_id"]].sort_values("Date/Time", ascending=False) \
            if not calls.empty else calls
        ld_drawer(r, lc)


@st.dialog("Lead", width="medium", position="right")
def ld_drawer(r, lc: pd.DataFrame):
    st.markdown('<div class="pm-drawer"></div>', unsafe_allow_html=True)
    created = f" · CREATED {r['_sd'].month}/{r['_sd'].day}/{r['_sd']:%y}" if pd.notna(r["_sd"]) else ""
    src = str(r["lead_source"] or "").upper()
    st.markdown(f"<div class='lc-id'>LEAD {esc(r['lead_id'])}{' · ' + esc(src) if src else ''}{created}</div>"
                f"<div class='dname'>{esc(r['company'] or '')}</div><div class='bds'>{_status_pill(r['status'])}</div>",
                unsafe_allow_html=True)
    kv = "".join(f"<span>{k}</span><span>{esc(v)}</span>" for k, v in
                 [("Contact", r["contact"]), ("Owner", r["owner"]), ("Market", r["market"])]
                 if v and not (isinstance(v, float) and pd.isna(v)))
    if kv:
        st.markdown(f"<div class='dkv'>{kv}</div>", unsafe_allow_html=True)
    if not lc.empty:
        chips = "".join(f"<span><b>{n}</b>{esc(rep)}</span>" for rep, n in lc["From"].value_counts().items())
        st.markdown(f"<div class='rchips'>{chips}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='dsec'>Every call since it was created · {len(lc)}</div>"
                f"{timeline_html(lc, 60) if not lc.empty else '<div class=tl-more style=padding-left:0>No calls yet.</div>'}",
                unsafe_allow_html=True)
    full_lead_button(str(r["lead_id"]), "ld")


# =====================================================================================
# COMMISSIONS (admin only) - deposits synced from NEW DEPOSIT REPORT, rates per rep
# =====================================================================================
COMM_FIRST_WEEK = date(2026, 10, 12)       # Week 42 of 2026, first week synced
COMM_PRESETS = ["This week", "Last week", "This month"]


@st.cache_data(ttl=60, show_spinner=False)
def load_deposits(start: date, end: date) -> pd.DataFrame:
    data = (sb.table("deposits").select("*").gte("deposit_date", str(start)).lte("deposit_date", str(end))
            .order("deposit_date").execute().data)
    df = pd.DataFrame(data, columns=["row_id", "deposit_date", "week", "salesperson", "company", "lead_id",
                                     "lead_source", "deposit_status", "purchase_type", "total_sale", "discount",
                                     "deposit_amount", "commissionable_amount", "synced_at"])
    df["deposit_date"] = pd.to_datetime(df["deposit_date"]).dt.date
    for c in ("deposit_amount", "commissionable_amount", "total_sale", "discount"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_commission_rates() -> pd.DataFrame:
    data = sb.table("commission_rates").select("*").execute().data
    df = pd.DataFrame(data, columns=["id", "salesperson", "rate", "effective_from"])
    df["effective_from"] = pd.to_datetime(df["effective_from"]).dt.date
    df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
    return df


@st.cache_data(ttl=300, show_spinner=False)
def load_commission_managers() -> pd.DataFrame:
    data = sb.table("commission_managers").select("*").execute().data
    df = pd.DataFrame(data, columns=["id", "manager", "rate", "excludes", "effective_from"])
    df["effective_from"] = pd.to_datetime(df["effective_from"]).dt.date
    df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
    return df


def manager_overrides(deps: pd.DataFrame, managers: pd.DataFrame) -> pd.DataFrame:
    """Matching: each manager earns their % of the commissionable amount on every deposit passed in
    (the ones ticked Matching), except their own sales. Uses the manager's rate in effect that day."""
    rows = []
    if deps.empty or managers.empty:
        return pd.DataFrame(columns=["row_id", "deposit_date", "salesperson", "company", "base", "manager",
                                     "rate", "override"])
    for mgr, rules in managers.sort_values("effective_from").groupby("manager"):
        for d in deps.itertuples():
            r = rules[rules["effective_from"] <= d.deposit_date]
            if r.empty:
                continue
            r = r.iloc[-1]
            excl = {mgr.upper()}          # a manager never earns matching on their own sale
            if str(d.salesperson or "").upper() in excl:
                continue
            base = 0.0 if pd.isna(d.base) else float(d.base)
            rows.append({"row_id": d.row_id, "deposit_date": d.deposit_date, "salesperson": d.salesperson,
                         "company": d.company, "base": base, "manager": mgr, "rate": float(r["rate"]),
                         "override": pay(base, float(r["rate"]) / 100)})
    return pd.DataFrame(rows, columns=["row_id", "deposit_date", "salesperson", "company", "base", "manager",
                                       "rate", "override"])


@st.cache_data(ttl=300, show_spinner=False)
def load_commission_overrides() -> dict:
    return {int(r["row_id"]): float(r["rate"]) for r in
            sb.table("commission_overrides").select("row_id, rate").execute().data}


@st.cache_data(ttl=60, show_spinner=False)
def load_deposit_sync_time():
    data = sb.table("att_file_log").select("loaded_at").eq("file_name", "DEPOSIT REPORT").execute().data
    return pd.to_datetime(data[0]["loaded_at"]) if data else None


def _rep_rate(rates: pd.DataFrame, rep: str, day: date):
    r = rates[(rates["salesperson"] == rep) & (rates["effective_from"] <= day)].sort_values("effective_from")
    return float(r.iloc[-1]["rate"]) if not r.empty else None


def _comm_range() -> tuple:
    today = date.today()
    week = st.session_state.get("cm_week")
    if week:
        return week, week + timedelta(days=6)
    p = st.session_state.get("cm_preset") or "Last week"
    if p == "This week":
        return bweek_monday(today), today
    if p == "This month":
        return max(today.replace(day=1), COMM_FIRST_WEEK), today
    m = bweek_monday(today) - timedelta(days=7)
    return m, m + timedelta(days=6)


def comm_week_options() -> list:
    return [w for w in att_week_options() if w >= COMM_FIRST_WEEK]


def _money(x) -> str:
    return "" if x is None or pd.isna(x) else f"${x:,.2f}"


def commission_excel(table: pd.DataFrame, summary: pd.DataFrame, title: str, overrides: pd.DataFrame = None):
    try:
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    except ImportError:
        return None
    buf = io.BytesIO()
    yellow = PatternFill("solid", fgColor="FFF36B")
    red = Font(color="D11A1A", bold=True)
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        table.to_excel(w, index=False, sheet_name="Commissions", startrow=1)
        ws = w.sheets["Commissions"]
        ws["A1"] = title
        ws["A1"].font = Font(bold=True, size=13)
        for c in ws[2]:
            c.fill, c.font = yellow, Font(bold=True)
            c.alignment = Alignment(horizontal="center", wrap_text=True)
        last = ws.max_row
        for c in ws[last]:
            c.fill, c.font = yellow, Font(bold=True)
            c.border = Border(top=Side(style="medium"))
        for row in ws.iter_rows(min_row=3, max_row=last - 1):
            row[2].font = red
        cols = list(table.columns)
        for name in ("Deposit", "Commissionable", "Commission"):
            if name in cols:
                for cell in ws[chr(65 + cols.index(name))][2:]:
                    cell.number_format = '"$"#,##0.00'
        widths = {"Date": 10, "Week": 9, "Sales": 11, "Company": 34, "Lead Source": 20, "Deposit Status": 20,
                  "Deposit": 13, "Commissionable": 15, "Commission %": 13, "Commission": 13}
        for i, cname in enumerate(cols):
            ws.column_dimensions[chr(65 + i)].width = widths.get(cname, 14)
        start = last + 2
        if overrides is not None and not overrides.empty:
            ws.cell(row=start + 1, column=1, value="MANAGER OVERRIDES").font = Font(bold=True)
            overrides.to_excel(w, index=False, sheet_name="Commissions", startrow=start + 1)
            for c in ws[start + 2]:
                c.fill, c.font = yellow, Font(bold=True)
            for row in ws.iter_rows(min_row=start + 3, max_row=ws.max_row):
                row[1].font = red
                for i in (4, 6):
                    row[i].number_format = '"$"#,##0.00'
            start = ws.max_row + 2
        summary.to_excel(w, index=False, sheet_name="Commissions", startrow=start)
        for c in ws[start + 1]:
            c.fill, c.font = yellow, Font(bold=True)
        for row in ws.iter_rows(min_row=start + 2, max_row=ws.max_row):
            row[0].font = red
            for cell in row[2:]:
                cell.number_format = '"$"#,##0.00'
    return buf.getvalue()


def money2(x) -> float:
    """Round to cents the way Excel does (half up): 20.825 -> 20.83."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return 0.0
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def pay(base, rate) -> float:
    """base x rate (rate as a fraction, e.g. 0.05), rounded half up to cents."""
    if base is None or rate is None or pd.isna(base) or pd.isna(rate):
        return 0.0
    return money2(Decimal(str(float(base))) * Decimal(str(float(rate))))


REPORT_TO = "Tony@primedianetwork.com"
REPORT_FILE = "PRIMEDIA-SALES_AND_COMMISSION_REPORT_SALESREP.xlsx"
PRIMEDIA_LOGO = "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"


def breakdown_excel(deps: pd.DataFrame, managers: pd.DataFrame, group_mult: float, week_no: int, year: int):
    """The 'Week NN Breakdown' sheet, laid out and formatted like the one sent to Tony each week."""
    import base64
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.worksheet.properties import PageSetupProperties

    acct = '_("$"* #,##0.00_);_("$"* \\(#,##0.00\\);_("$"* "-"??_);_(@_)'
    thin = Side(style="thin")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    open_r = Border(left=thin, top=thin, bottom=thin)
    yellow = PatternFill("solid", fgColor="FFFF00")
    black_fill = PatternFill("solid", fgColor="000000")
    f_black = Font(name="Aptos Narrow", size=11, bold=True, color="000000")
    f_red = Font(name="Aptos Narrow", size=11, bold=True, color="FF0000")
    f_yel = Font(name="Aptos Narrow", size=11, bold=True, color="FFFF00")
    left = Alignment(horizontal="left", vertical="center")
    center = Alignment(horizontal="center", vertical="center")
    center_wrap = Alignment(horizontal="center", vertical="center", wrap_text=True)

    wb = Workbook()
    ws = wb.active
    ws.title = f"Week {week_no} Breakdown"
    ws.sheet_properties.tabColor = "FF0000"
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)
    ws.sheet_view.zoomScale = 115
    ws.freeze_panes = "A5"
    ws.page_margins.left = ws.page_margins.right = ws.page_margins.top = ws.page_margins.bottom = 0
    ws.page_setup.orientation = "portrait"
    ws.page_setup.scale = 66
    for col, w in zip("ABCDEFGHIJ", (11.43, 14.43, 27.14, 38.14, 22, 22, 13.43, 13.14, 14.57, 11.43)):
        ws.column_dimensions[col].width = w
    ws.column_dimensions["J"].hidden = True
    cached = {}          # formula cell -> value, so previews (phone, Outlook) show numbers before Excel recalcs

    def put(ref, value, font=f_black, align=left, border=box, fmt=None, fill=None, calc=None):
        c = ws[ref]
        c.value, c.font, c.alignment = value, font, align
        if border is not None:
            c.border = border
        if fmt:
            c.number_format = fmt
        if fill is not None:
            c.fill = fill
        if calc is not None:
            cached[ref] = calc
        return c

    try:
        img = XLImage(io.BytesIO(base64.b64decode(PRIMEDIA_LOGO)))
        img.width, img.height = 313, 59
        ws.add_image(img, "A1")
    except Exception:
        pass
    put("D3", f"SALES COMMISSIONS {year}", align=center, border=None)

    mgr_rate = float(managers["rate"].iloc[0]) / 100 if not managers.empty else 0.03
    heads = ["DATE ", "Week", "Sales", "Company", "Lead Source", "DEPOSIT STATUS", "TOTAL",
             "COMMISSION PERCENTAGE", "TOTAL COMMISSIONS & PAYOUTS"]
    ws.row_dimensions[4].height = 43.5
    for i, h in enumerate(heads):
        put(f"{'ABCDEFGHI'[i]}4", h, fill=yellow, align=left if i < 4 else (center if i == 4 else center_wrap))
    put("J4", mgr_rate, font=Font(name="Aptos Narrow", size=11, bold=True, color="808080"), align=center,
        border=None, fmt="0%")

    rows = deps.sort_values(["salesperson", "deposit_date", "row_id"]).reset_index(drop=True)
    r = 5
    match_amt = {}
    for d in rows.itertuples():
        base = 0.0 if pd.isna(d.base) else float(d.base)
        rate = None if pd.isna(d.pct) else float(d.pct) / 100
        ws.row_dimensions[r].height = 16.5
        put(f"A{r}", d.deposit_date, fmt="d-mmm")
        put(f"B{r}", bweek_number(d.deposit_date), align=center)
        put(f"C{r}", d.salesperson or "", font=f_red, fmt="d-mmm")
        put(f"D{r}", d.company or "", font=f_red)
        put(f"E{r}", d.lead_source or "", font=f_red, border=open_r)
        put(f"F{r}", d.deposit_status or "", font=f_red, align=center, border=open_r, fmt=acct)
        put(f"G{r}", base, font=f_red, align=center, border=open_r, fmt=acct)
        put(f"H{r}", rate, font=f_red, align=center, fmt="0.0%")
        put(f"I{r}", f"=ROUND(G{r}*H{r},2)", align=center, border=open_r, fmt=acct, calc=pay(base, rate or 0))
        if d.matching:
            put(f"J{r}", f"=ROUND(G{r}*$J$4,2)", border=None, fmt=acct, calc=pay(base, mgr_rate))
            match_amt[r] = (str(d.salesperson or "").upper(), pay(base, mgr_rate))
        r += 1
    last_dep = r - 1
    grp = rows[rows["group"]]
    if not grp.empty:
        gbase = float(grp["base"].fillna(0).sum())
        ws.row_dimensions[r].height = 16.5
        put(f"A{r}", grp["deposit_date"].max(), fmt="d-mmm")
        put(f"B{r}", bweek_number(grp["deposit_date"].max()), align=center)
        put(f"C{r}", GROUP_PAYEE, font=f_red, fmt="d-mmm")
        put(f"D{r}", "", font=f_red)
        put(f"E{r}", "", font=f_red, border=open_r)
        put(f"F{r}", "", font=f_red, align=center, border=open_r, fmt=acct)
        put(f"G{r}", gbase, font=f_red, align=center, border=open_r, fmt=acct)
        put(f"H{r}", group_mult, font=f_red, align=center)
        put(f"I{r}", f"=ROUND(G{r}*H{r},2)", align=center, border=open_r, fmt=acct, calc=pay(gbase, group_mult))
        r += 1
    last = r - 1

    # people in the summary: everyone with a payout row, plus the matching managers
    mgr_names = sorted(managers["manager"].str.upper().unique()) if not managers.empty else []
    people = sorted(set(str(x).upper() for x in rows["salesperson"].dropna()) | set(mgr_names)
                    | ({GROUP_PAYEE} if not grp.empty else set()))
    tot = r
    for col in "ABCDEFGHI":
        put(f"{col}{tot}", None, fill=yellow, align=center if col in "FGHI" else left,
            border=open_r if col in "EFGI" else box, fmt=acct if col in "FGI" else None)
    for col, name in zip("CD", mgr_names[:2] if mgr_names else []):
        put(f"{col}{tot}", name, font=f_yel, fill=yellow)
    put(f"G{tot}", f"=SUM(G5:G{last_dep})", fill=yellow, align=center, border=open_r, fmt=acct,
        calc=money2(rows["base"].fillna(0).sum()))
    put(f"H{tot}", mgr_rate, fill=yellow, align=center, fmt="0.0%")
    s_first = tot + 3
    s_last = s_first + len(people) - 1
    ws.row_dimensions[tot + 1].height = 8.25
    for col in "ABCDEFGHI":
        ws[f"{col}{tot + 1}"].fill = black_fill
    put(f"A{tot + 2}", "Sales", fill=yellow)
    put(f"B{tot + 2}", "TOTAL", fill=yellow)

    own = {}
    for rr in range(5, last + 1):
        nm = str(ws[f"C{rr}"].value or "").upper()
        own[nm] = own.get(nm, 0.0) + cached[f"I{rr}"]
    grand = 0.0
    for i, p in enumerate(people):
        rr = s_first + i
        put(f"A{rr}", p, font=f_red, fmt="d-mmm")
        f = f"=ROUND(SUMIF($C$5:$C${last},A{rr},$I$5:$I${last}),2)"
        val = money2(own.get(p, 0.0))
        if p in mgr_names:
            f += f'+SUMIFS($J$5:$J${max(last_dep, 5)},$C$5:$C${max(last_dep, 5)},"<>"&A{rr})'
            val = money2(val + sum(a for who, a in match_amt.values() if who != p))
        put(f"B{rr}", f, align=center, fmt=acct, calc=val)
        grand += val
    put(f"I{tot}", f"=SUM(B{s_first}:B{s_last})", fill=yellow, align=center, border=open_r, fmt=acct,
        calc=money2(grand))
    ws.auto_filter.ref = f"A4:I{tot}"

    buf = io.BytesIO()
    wb.save(buf)
    return _fill_cached(buf.getvalue(), cached)


def _fill_cached(xlsx: bytes, cached: dict) -> bytes:
    """Write each formula's result next to it in the file, so the numbers show even before a recalc."""
    import zipfile
    src = zipfile.ZipFile(io.BytesIO(xlsx))
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "xl/worksheets/sheet1.xml":
                s = data.decode("utf-8")
                for ref, v in cached.items():
                    s = re.sub(rf'(<c r="{ref}"[^>]*>)(<f>.*?</f>)(<v\s*/>|<v></v>)?',
                               lambda m, v=v: f"{m.group(1)}{m.group(2)}<v>{v!r}</v>", s, count=1)
                data = s.encode("utf-8")
            z.writestr(item, data)
    return out.getvalue()


def report_email(xlsx: bytes, week_no: int, start: date, end: date) -> bytes:
    """A ready-to-send email (opens as a new message in Outlook) to Tony with the breakdown attached."""
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["To"] = REPORT_TO
    msg["Subject"] = f"Week {week_no} Sales & Commission Breakdown"
    msg["X-Unsent"] = "1"
    msg.set_content(f"Hi Tony,\n\nAttached is the Week {week_no} sales and commission breakdown "
                    f"({start:%m/%d/%Y} - {end:%m/%d/%Y}).\n\nThanks,\nJustin\n")
    msg.add_attachment(xlsx, maintype="application", subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       filename=REPORT_FILE)
    return msg.as_bytes()


@st.dialog("Assign commission rate")
def assign_rate_dialog(reps: list, rates: pd.DataFrame):
    pick = st.selectbox("Salesperson", reps + ["+ Someone else…"], index=None, placeholder="Pick a salesperson")
    rep = st.text_input("Name (as it appears in the deposit report)").strip().upper() \
        if pick == "+ Someone else…" else (pick or "")
    rate = st.number_input("Commission %", min_value=0.0, max_value=100.0, step=0.5, format="%.2f")
    start_day = st.date_input("Starting", value=COMM_FIRST_WEEK, format="MM/DD/YYYY",
                              help="Deposits on or after this date use this rate")
    if rep:
        cur = _rep_rate(rates, rep, start_day)
        if cur is not None:
            st.caption(f"{rep} is at {cur:g}% now. Deposits from {start_day:%m/%d/%Y} on will use the new rate; "
                       "earlier deposits keep theirs.")
    if st.button("Save", type="primary"):
        if not rep:
            st.error("Pick a salesperson.")
            return
        clash = rates[(rates["salesperson"] == rep) & (rates["effective_from"] == start_day)]
        if not clash.empty:
            sb.table("commission_rates").update({"rate": rate}).eq("id", int(clash.iloc[0]["id"])).execute()
        else:
            sb.table("commission_rates").insert({"salesperson": rep, "rate": rate,
                                                 "effective_from": str(start_day)}).execute()
        st.cache_data.clear()
        st.rerun()


@st.cache_data(ttl=300, show_spinner=False)
def load_commission_group() -> set:
    return {int(r["row_id"]) for r in sb.table("commission_group").select("row_id").execute().data}


@st.cache_data(ttl=300, show_spinner=False)
def load_group_multiplier() -> float:
    r = sb.table("commission_settings").select("value").eq("name", "group_multiplier").execute().data
    return float(r[0]["value"]) if r else 0.001666


GROUP_PAYEE = "GROUP"


@st.cache_data(ttl=300, show_spinner=False)
def load_commission_matching() -> set:
    return {int(r["row_id"]) for r in sb.table("commission_matching").select("row_id").execute().data}


def _sync_state():
    r = sb.table("sync_requests").select("*").eq("name", "deposits").execute().data
    if not r:
        return None, None
    ts = lambda v: pd.to_datetime(v) if v else None  # noqa: E731
    return ts(r[0].get("requested_at")), ts(r[0].get("done_at"))


@st.fragment(run_every=5)
def _sync_waiter():
    """While a Refresh is pending, check every few seconds whether the PC has finished the sync."""
    if not st.session_state.get("dep_sync_pending"):
        return
    asked, done = _sync_state()
    if done is not None and asked is not None and done >= asked:
        st.session_state["dep_sync_pending"] = False
        st.cache_data.clear()
        st.rerun(scope="app")
    waited = (pd.Timestamp.now(tz="UTC") - asked).total_seconds() if asked is not None else 0
    if waited > 150:
        st.warning("Your PC hasn't picked up the refresh yet. Make sure it's on with the 'Sync Deposits' task set "
                   "up, or double-click **Sync Deposits Now** in your Call Files folder.")
    else:
        st.info("Getting the latest from the deposit report on your PC… this usually takes under a minute.",
                icon=":material/sync:")


def _prep_deps(deps, rates, overrides, matching, grouped) -> pd.DataFrame:
    """Add base, rate, commission (rounded half up) and the Matching / Group ticks to each deposit."""
    deps = deps.sort_values(["salesperson", "deposit_date", "row_id"]).reset_index(drop=True)
    base = deps["commissionable_amount"].where(deps["commissionable_amount"].notna(), deps["deposit_amount"])
    rep_rates = [_rep_rate(rates, r, d) for r, d in zip(deps["salesperson"], deps["deposit_date"])]
    pct = [overrides.get(int(rid), rr) for rid, rr in zip(deps["row_id"], rep_rates)]
    deps = deps.assign(base=base, pct=pct, rep_rate=rep_rates,
                       overridden=[int(rid) in overrides for rid in deps["row_id"]],
                       matching=[int(rid) in matching for rid in deps["row_id"]],
                       group=[int(rid) in grouped for rid in deps["row_id"]])
    deps["commission"] = [pay(b, (p or 0) / 100) if p is not None and not pd.isna(p) else 0.0
                          for b, p in zip(deps["base"].fillna(0), deps["pct"])]
    return deps


def _email_button(where, deps: pd.DataFrame, managers: pd.DataFrame, group_mult: float, start: date, end: date,
                  week_view: bool):
    """Below Refresh: download a ready-to-send email to Tony with the Week NN Breakdown attached."""
    wk = bweek_number(start)
    if not week_view:
        where.button("Email Tony", icon=":material/mail:", width="stretch", disabled=True,
                     help="Pick a single week (This week, Last week or a broadcast week) to email its breakdown")
        return
    # rows that pay someone: reps with a rate, plus anything ticked Matching or Group
    pays = deps[deps["pct"].notna() | deps["matching"] | deps["group"]]
    try:
        xlsx = breakdown_excel(pays, managers, group_mult, wk, start.year)
        eml = report_email(xlsx, wk, start, end)
    except Exception as e:
        where.button("Email Tony", icon=":material/mail:", width="stretch", disabled=True, help=f"Couldn't build: {e}")
        return
    where.download_button(f"Email Week {wk}", eml, file_name=f"Week {wk} Breakdown - email to Tony.eml",
                          mime="message/rfc822", icon=":material/mail:", width="stretch",
                          help=f"Downloads a new email to {REPORT_TO} with the Week {wk} Breakdown attached. "
                               "Open the download and it opens in Outlook ready to send.")
    where.download_button(f"Week {wk} file only", xlsx, file_name=REPORT_FILE, type="tertiary",
                          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                          icon=":material/download:", width="stretch")


def person_cards(deps: pd.DataFrame, summary: pd.DataFrame, rates: pd.DataFrame, end: date):
    """One card per salesperson: what they sold and what they're paid."""
    ppl = summary[(summary["Sales"] != "TOTAL") & ((summary["Deposits"] > 0) | (summary["Total Payout"] > 0))]
    if ppl.empty:
        return
    base = deps.groupby("salesperson")["base"].sum()
    cards = []
    for r in ppl.sort_values(["Total", "Total Payout"], ascending=False).itertuples():
        n = int(r.Deposits)
        lines = []
        if n:
            rate = _rep_rate(rates, r.Sales, end)
            lines.append(f'<div><span>Commission{f" · {rate:g}%" if rate is not None else ""}</span>'
                         f'<b>${r.Commission:,.2f}</b></div>' if rate is not None or r.Commission else
                         '<div class="warn"><span>No rate set</span><span>Assign Commissions</span></div>')
        if r.Matching:
            lines.append(f'<div><span>Matching</span><b>${r.Matching:,.2f}</b></div>')
        if r.Group:
            lines.append(f'<div><span>Group</span><b>${r.Group:,.2f}</b></div>')
        lines.append(f'<div class="tot"><span>Total payout</span><b>${r._7:,.2f}</b></div>')
        cards.append(
            f'<div class="pp"><div class="pp-top"><span class="pp-name">{esc(r.Sales)}</span>'
            f'<span class="pp-cnt">{plural(n, "deposit") if n else "matching / group"}</span></div>'
            f'<div class="pp-amt">${(r.Total if n else r._7):,.{0 if n else 2}f}</div><div class="pp-sub">'
            f'{f"${float(base.get(r.Sales, 0) or 0):,.0f} commissionable" if n else "paid on others&#39; sales"}</div>'
            f'<div class="pp-lines">{"".join(lines)}</div></div>')
    st.markdown('<div class="card-h" style="margin-top:.2rem">By salesperson<span>details for anyone: click their name '
                'in the Week summary below</span></div><div class="pp-grid">' + "".join(cards) + "</div>",
                unsafe_allow_html=True)


def page_commissions():
    h1, h2 = st.columns([4, 1], vertical_alignment="bottom")
    h1.title("Commissions")
    if h2.button("Refresh", icon=":material/refresh:", width="stretch",
                 help="Pull the latest saved changes from the NEW DEPOSIT REPORT on your PC"):
        sb.table("sync_requests").upsert({"name": "deposits",
                                          "requested_at": pd.Timestamp.now(tz="UTC").isoformat()}).execute()
        st.session_state["dep_sync_pending"] = True
    _sync_waiter()
    synced = load_deposit_sync_time()
    st.caption("Deposits from the NEW DEPOSIT REPORT, by broadcast week. Rates are set on **Manage → Assign "
               "Commissions**. " + (f"Last synced from the file {us_time(synced.tz_convert('America/Chicago'))}."
                                     if synced is not None else ""))

    f = st.columns([2.4, 5.6])
    start, end = g_range()
    deps = load_deposits(start, end)
    rates = load_commission_rates()
    overrides = load_commission_overrides()
    matching = load_commission_matching()
    grouped = load_commission_group()
    group_mult = load_group_multiplier()
    managers = load_commission_managers()
    rep_pick = f[0].multiselect("Salesperson", sorted(deps["salesperson"].dropna().unique()),
                                placeholder="All salespeople", key="cm_reps")

    when = g_when()
    week_view = g_is_week()
    all_deps = _prep_deps(deps, rates, overrides, matching, grouped)
    deps = all_deps
    if rep_pick:
        deps = deps[deps["salesperson"].isin(rep_pick)].reset_index(drop=True)
    if deps.empty:
        st.info(f"No deposits for {when}.")
        return

    mgr_ov = manager_overrides(deps[deps["matching"]], managers)
    grp = deps[deps["group"]].copy()
    grp["group_pay"] = [pay(b, group_mult) for b in grp["base"].fillna(0)]
    total_grp = pay(float(grp["base"].fillna(0).sum()), group_mult) if not grp.empty else 0.0

    total_dep = float(deps["deposit_amount"].sum())
    total_base = float(deps["base"].fillna(0).sum())
    total_comm = float(deps["commission"].sum())
    total_mgr = float(mgr_ov["override"].sum()) if not mgr_ov.empty else 0.0
    k1, k2 = st.columns([3.1, 1], gap="medium")
    with k2, st.container(border=True, key="pm_email"):
        wk = bweek_number(start)
        st.markdown(f'<div class="em-h">Week {wk} breakdown</div><div class="em-t">Ready to send to Tony</div>'
                    if week_view else '<div class="em-h">Weekly breakdown</div>'
                                      '<div class="em-t">Pick one week to email Tony</div>', unsafe_allow_html=True)
        _email_button(st, all_deps, managers, group_mult, start, end, week_view)
    with k1:
        kpi_cards([
        {"label": "Deposits", "value": f"{len(deps):,}", "note": when},
        {"label": "Total deposited", "value": f"${total_dep:,.0f}", "note": ""},
        {"label": "Commissionable", "value": f"${total_base:,.0f}", "note": ""},
        {"label": "Total payouts", "value": f"${total_comm + total_mgr + total_grp:,.2f}",
         "note": f"${total_comm:,.2f} commissions + ${total_mgr:,.2f} matching"
                 + (f" + ${total_grp:,.2f} group" if total_grp else ""), "alert": True},
    ])
    own = deps.groupby("salesperson").agg(Deposits=("row_id", "size"), Total=("deposit_amount", "sum"),
                                          Commission=("commission", "sum"))
    ovs = mgr_ov.groupby("manager")["override"].sum() if not mgr_ov.empty else pd.Series(dtype=float)
    people = sorted(set(own.index) | set(ovs.index) | set(managers["manager"]) | ({GROUP_PAYEE} if total_grp else set()))
    summary = pd.DataFrame({
        "Sales": people,
        "Deposits": [int(own["Deposits"].get(p, 0)) for p in people],
        "Total": [float(own["Total"].get(p, 0.0)) for p in people],
        "Commission": [round(float(own["Commission"].get(p, 0.0)), 2) for p in people],
        "Matching": [round(float(ovs.get(p, 0.0)), 2) for p in people],
        "Group": [round(total_grp, 2) if p == GROUP_PAYEE else 0.0 for p in people],
    })
    summary["Total Payout"] = (summary["Commission"] + summary["Matching"] + summary["Group"]).round(2)
    summary = pd.concat([summary, pd.DataFrame([{
        "Sales": "TOTAL", "Deposits": len(deps), "Total": total_dep, "Commission": round(total_comm, 2),
        "Matching": round(total_mgr, 2), "Group": round(total_grp, 2),
        "Total Payout": round(total_comm + total_mgr + total_grp, 2)}])], ignore_index=True)

    person_cards(deps, summary, rates, end)
    missing = sorted(deps.loc[deps["pct"].isna(), "salesperson"].dropna().unique())
    if missing:
        st.warning("No commission rate set for: " + ", ".join(missing)
                   + " — set it on **Manage → Assign Commissions**. Until then their commission shows $0.")

    # ---------- deposits ----------
    mgr_names = ", ".join(sorted(managers["manager"].unique())) or "the managers"
    mgr_rates = sorted({f"{r:g}%" for r in managers["rate"]}) or ["3%"]
    table = pd.DataFrame({
        "row_id": deps["row_id"],
        "Date": deps["deposit_date"].map(lambda d: f"{d.month}/{d.day}/{d:%y}"),
        "Week": deps["week"].fillna(""),
        "Sales": deps["salesperson"].fillna(""),
        "Company": deps["company"].fillna(""),
        "Lead Source": deps["lead_source"].fillna("").str.title(),
        "Deposit Status": deps["deposit_status"].fillna(""),
        "Deposit": deps["deposit_amount"],
        "Commissionable": deps["base"],
        "Commission %": deps["pct"],
        "Commission": deps["commission"],
        "Matching": deps["matching"],
        "Group": deps["group"],
    })
    st.caption(f"Tick **Matching** to pay {mgr_names} {' / '.join(mgr_rates)} of that deposit's commissionable "
               f"amount (a manager never earns matching on their own sale). Tick **Group** to pay GROUP the "
               f"commissionable amount × {group_mult:g}. Change a **Commission %** to override "
               "it for one deposit; clear it to go back to the rep's rate.")
    ed = st.data_editor(
        table, hide_index=True, width="stretch", height=min(38 + 35 * len(table), 620),
        key=f"comm_tbl_{start}_{end}_{'-'.join(rep_pick)}_{st.session_state.get('ov_v', 0)}",
        column_order=[c for c in table.columns if c != "row_id"],
        disabled=[c for c in table.columns if c not in ("Commission %", "Matching", "Group")],
        column_config={
            "Sales": st.column_config.TextColumn(width="small"),
            "Company": st.column_config.TextColumn(width="medium"),
            "Week": st.column_config.TextColumn(width="small"),
            "Deposit": st.column_config.NumberColumn(format="dollar"),
            "Commissionable": st.column_config.NumberColumn(
                format="dollar", help="From the deposit report's Commissionable Amount (deposit if blank)"),
            "Commission %": st.column_config.NumberColumn(format="%.2f%%", min_value=0, max_value=100, step=0.25,
                                                          help="Rep's rate, or this deposit's override"),
            "Commission": st.column_config.NumberColumn(format="dollar"),
            "Matching": st.column_config.CheckboxColumn(
                width="small", help=f"Pays {mgr_names} their matching % on this deposit"),
            "Group": st.column_config.CheckboxColumn(
                width="small", help=f"Pays GROUP this deposit's commissionable amount × {group_mult:g}"),
        })
    changed = False
    old, new = table["Commission %"], ed["Commission %"]
    for _, r in ed[~((old == new) | (old.isna() & new.isna()))].iterrows():
        rid = int(r["row_id"])
        val = r["Commission %"]
        rep_rate = deps.loc[deps["row_id"] == rid, "rep_rate"].iloc[0]
        if val is None or pd.isna(val) or (rep_rate is not None and float(val) == rep_rate):
            sb.table("commission_overrides").delete().eq("row_id", rid).execute()
        else:
            sb.table("commission_overrides").upsert({"row_id": rid, "rate": float(val)}).execute()
        changed = True
    for _, r in ed[ed["Matching"] != table["Matching"]].iterrows():
        rid = int(r["row_id"])
        if bool(r["Matching"]):
            sb.table("commission_matching").upsert({"row_id": rid}).execute()
        else:
            sb.table("commission_matching").delete().eq("row_id", rid).execute()
        changed = True
    for _, r in ed[ed["Group"] != table["Group"]].iterrows():
        rid = int(r["row_id"])
        if bool(r["Group"]):
            sb.table("commission_group").upsert({"row_id": rid}).execute()
        else:
            sb.table("commission_group").delete().eq("row_id", rid).execute()
        changed = True
    if changed:
        st.cache_data.clear()
        st.session_state["ov_v"] = st.session_state.get("ov_v", 0) + 1
        st.rerun()
    if deps["overridden"].any():
        st.caption("Commission % overridden: " + ", ".join(
            f"{r.company} ({r.deposit_date.month}/{r.deposit_date.day}) {r.pct:g}%"
            for r in deps[deps["overridden"]].itertuples()))

    # ---------- week summary + person detail ----------
    st.markdown("**Week summary**")
    sl, sr = st.columns([1.5, 1], gap="large")

    def _sum_style(frame):
        css = pd.DataFrame("", index=frame.index, columns=frame.columns)
        css["Sales"] = "color: #d11a1a; font-weight: 700"
        css.iloc[-1] = "background-color: #fff36b; font-weight: 700"
        return css
    with sl:
        ev = st.dataframe(summary.style.apply(_sum_style, axis=None).format(
            {"Total": "${:,.2f}", "Commission": "${:,.2f}", "Matching": "${:,.2f}", "Group": "${:,.2f}",
             "Total Payout": "${:,.2f}"}),
            hide_index=True, width="stretch", on_select="rerun", selection_mode="single-row",
            key=f"comm_sum_{start}_{end}_{'-'.join(rep_pick)}")
        st.caption("Click a name to see what they're being paid for.")
    sel = ev.selection.rows if ev and ev.selection else []
    with sr:
        person = summary.iloc[sel[0]]["Sales"] if sel else None
        with st.container(border=True):
            if not person:
                st.caption("Click a name in the Week summary to see each deposit they're paid on.")
            else:
                _payout_box(person, deps, mgr_ov, summary, when, grp, group_mult)

    # ---------- export ----------
    export = table.drop(columns=["row_id"]).copy()
    export["Matching"] = export["Matching"].map(lambda m: "Yes" if m else "")
    export["Group"] = export["Group"].map(lambda m: "Yes" if m else "")
    export = pd.concat([export, pd.DataFrame([{
        "Date": "TOTALS", "Deposit": total_dep, "Commissionable": total_base,
        "Commission %": round(total_comm / total_base * 100, 2) if total_base else None,
        "Commission": round(total_comm, 2)}])], ignore_index=True)
    mo_export = None
    if not mgr_ov.empty:
        mo_export = pd.DataFrame({
            "Date": mgr_ov["deposit_date"].map(lambda d: f"{d.month}/{d.day}/{d:%y}"),
            "Manager": mgr_ov["manager"], "Sale by": mgr_ov["salesperson"], "Company": mgr_ov["company"],
            "Commissionable": mgr_ov["base"], "Matching %": mgr_ov["rate"], "Matching $": mgr_ov["override"],
        }).sort_values(["Manager", "Date"])
    if not grp.empty:
        g_rows = pd.DataFrame({
            "Date": grp["deposit_date"].map(lambda d: f"{d.month}/{d.day}/{d:%y}"), "Manager": GROUP_PAYEE,
            "Sale by": grp["salesperson"], "Company": grp["company"], "Commissionable": grp["base"],
            "Matching %": group_mult * 100, "Matching $": grp["group_pay"]})
        mo_export = g_rows if mo_export is None else pd.concat([mo_export, g_rows], ignore_index=True)
    xlsx = commission_excel(export, summary, f"SALES COMMISSIONS · {when}", mo_export)
    if xlsx:
        sl.download_button("Download Excel", xlsx, file_name=f"commissions_{start}_{end}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                           icon=":material/table_view:")


def _payout_box(person: str, deps: pd.DataFrame, mgr_ov: pd.DataFrame, summary: pd.DataFrame, when: str,
                grp: pd.DataFrame = None, group_mult: float = 0.0):
    row = summary[summary["Sales"] == person].iloc[0]
    st.markdown(f"<div style='opacity:.6;font-size:.75rem;letter-spacing:.04em'>{esc(when.upper())}</div>"
                f"<div style='font-size:1.35rem;font-weight:700;color:#d11a1a'>{esc(person)}</div>"
                f"<div style='font-size:1.6rem;font-weight:700;margin:2px 0 8px'>${row['Total Payout']:,.2f}"
                f"<span style='font-size:.85rem;font-weight:400;opacity:.65'> total payout</span></div>",
                unsafe_allow_html=True)
    line = ("display:grid;grid-template-columns:62px 1fr 92px 58px 78px;gap:6px;padding:5px 0;font-size:.84rem;"
            "border-bottom:1px dashed rgba(128,128,128,.25)")
    head = line + ";opacity:.6;font-size:.75rem;border-bottom:1px solid rgba(128,128,128,.3)"

    def _block(title, rows, total):
        st.markdown(f"<div style='font-weight:700;margin:10px 0 2px'>{title} · ${total:,.2f}</div>",
                    unsafe_allow_html=True)
        if not rows:
            st.caption("None this period.")
            return
        st.markdown(f"<div style='{head}'><span>Date</span><span>Company</span><span style='text-align:right'>"
                    f"Commissionable</span><span style='text-align:right'>%</span><span style='text-align:right'>"
                    f"Paid</span></div>" + "".join(rows), unsafe_allow_html=True)

    if person == "TOTAL":
        st.caption("Click a person's name to see their details.")
        return
    if person == GROUP_PAYEE:
        rows = [f"<div style='{line}'><span>{g.deposit_date.month}/{g.deposit_date.day}</span><span>{esc(g.company)}"
                f" <span style='opacity:.6'>({esc(g.salesperson)})</span></span><span style='text-align:right'>"
                f"${(0 if pd.isna(g.base) else g.base):,.2f}</span><span style='text-align:right'>×{group_mult:g}</span>"
                f"<span style='text-align:right'><b>${g.group_pay:,.2f}</b></span></div>"
                for g in (grp.itertuples() if grp is not None else [])]
        _block("Group", rows, float(row["Group"]))
        return
    mine = deps[deps["salesperson"] == person]
    rows = [f"<div style='{line}'><span>{d.deposit_date.month}/{d.deposit_date.day}</span><span>{esc(d.company)}"
            f"</span><span style='text-align:right'>${(0 if pd.isna(d.base) else d.base):,.2f}</span>"
            f"<span style='text-align:right'>{'' if pd.isna(d.pct) else f'{d.pct:g}%'}</span>"
            f"<span style='text-align:right'><b>${d.commission:,.2f}</b></span></div>" for d in mine.itertuples()]
    _block("Own sales", rows, float(row["Commission"]))
    mo = mgr_ov[mgr_ov["manager"] == person] if not mgr_ov.empty else mgr_ov
    if not mo.empty or float(row["Matching"]):
        rows = [f"<div style='{line}'><span>{m.deposit_date.month}/{m.deposit_date.day}</span><span>{esc(m.company)}"
                f" <span style='opacity:.6'>({esc(m.salesperson)})</span></span><span style='text-align:right'>"
                f"${m.base:,.2f}</span><span style='text-align:right'>{m.rate:g}%</span><span style='text-align:right'>"
                f"<b>${m.override:,.2f}</b></span></div>" for m in mo.itertuples()]
        _block("Matching", rows, float(row["Matching"]))


def page_assign_commissions():
    st.title("Assign Commissions")
    st.markdown('<div class="page-sub">Commission rates and matching managers</div>', unsafe_allow_html=True)
    rates = load_commission_rates()
    deps_all = load_deposits(COMM_FIRST_WEEK, date.today())
    all_reps = sorted(set(deps_all["salesperson"].dropna()) | set(rates["salesperson"].dropna()))
    c1, c2 = st.columns([1.3, 1], gap="large")

    with c1:
        st.markdown("**Commission rates**")
        st.caption("Each rep's % of the commissionable amount. A rate applies from its Starting date on; use "
                   "**Assign rate** with a later date when a rep's rate changes, so earlier deposits keep theirs.")
        if st.button("Assign rate", icon=":material/percent:", type="primary"):
            assign_rate_dialog(all_reps, rates)
        if rates.empty:
            st.info("No rates yet. Use **Assign rate** to set each rep's %.")
        else:
            rshow = rates.sort_values(["salesperson", "effective_from"]).reset_index(drop=True)
            rv = pd.DataFrame({"id": rshow["id"], "Sales": rshow["salesperson"], "Rate %": rshow["rate"],
                               "Starting": rshow["effective_from"].map(
                                   lambda d: "Beginning" if d == BASE_DATE else f"{d:%m/%d/%Y}"),
                               "Remove": False})
            ed = st.data_editor(rv, hide_index=True, width="stretch",
                                key=f"rates_{st.session_state.get('rates_v', 0)}",
                                column_order=["Sales", "Rate %", "Starting", "Remove"], disabled=["Sales", "Starting"],
                                column_config={"Rate %": st.column_config.NumberColumn(format="%.2f%%", min_value=0,
                                                                                       max_value=100, step=0.25),
                                               "Remove": st.column_config.CheckboxColumn(width="small")})
            ch, rm = ed[ed["Rate %"] != rv["Rate %"]], ed[ed["Remove"]]
            if not ch.empty or not rm.empty:
                for _, r in ch.iterrows():
                    sb.table("commission_rates").update({"rate": float(r["Rate %"] or 0)}).eq("id", int(r["id"])).execute()
                for _, r in rm.iterrows():
                    sb.table("commission_rates").delete().eq("id", int(r["id"])).execute()
                st.cache_data.clear()
                st.session_state["rates_v"] = st.session_state.get("rates_v", 0) + 1
                st.rerun()
        no_rate = [p for p in sorted(deps_all["salesperson"].dropna().unique()) if p not in set(rates["salesperson"])]
        if no_rate:
            st.caption("Salespeople with deposits but no rate yet: " + ", ".join(no_rate))

    with c2:
        st.markdown("**Matching managers**")
        st.caption("When a deposit's **Matching** box is ticked on the Commissions page, each manager here earns "
                   "their % of its commissionable amount, except on their own sales.")
        mgrs = load_commission_managers().sort_values(["manager", "effective_from"]).reset_index(drop=True)
        mv = pd.DataFrame({"id": mgrs["id"], "Manager": mgrs["manager"], "Matching %": mgrs["rate"],
                           "Starting": mgrs["effective_from"].map(lambda d: f"{d:%m/%d/%Y}"), "Remove": False})
        med = st.data_editor(mv, hide_index=True, width="stretch", key=f"mgrs_{st.session_state.get('mgr_v', 0)}",
                             column_order=["Manager", "Matching %", "Starting", "Remove"],
                             disabled=["Manager", "Starting"],
                             column_config={"Matching %": st.column_config.NumberColumn(format="%.2f%%", min_value=0,
                                                                                        max_value=100, step=0.25),
                                            "Remove": st.column_config.CheckboxColumn(width="small")})
        mch, mrm = med[med["Matching %"] != mv["Matching %"]], med[med["Remove"]]
        if not mch.empty or not mrm.empty:
            for _, r in mch.iterrows():
                sb.table("commission_managers").update({"rate": float(r["Matching %"] or 0)}).eq("id", int(r["id"])).execute()
            for _, r in mrm.iterrows():
                sb.table("commission_managers").delete().eq("id", int(r["id"])).execute()
            st.cache_data.clear()
            st.session_state["mgr_v"] = st.session_state.get("mgr_v", 0) + 1
            st.rerun()
        st.markdown("**Group**")
        cur_mult = load_group_multiplier()
        g1, g2 = st.columns([2, 1], vertical_alignment="bottom")
        new_mult = g1.number_input("Group multiplier", value=cur_mult, min_value=0.0, step=0.0001, format="%.6f",
                                   help="A deposit ticked Group pays GROUP its commissionable amount × this number")
        if g2.button("Save", key="save_group_mult", disabled=new_mult == cur_mult):
            sb.table("commission_settings").upsert({"name": "group_multiplier", "value": new_mult}).execute()
            st.cache_data.clear()
            st.rerun()
        with st.expander("Add a manager"):
            a1, a2 = st.columns(2)
            new_m = a1.text_input("Name (as in the deposit report)", key="new_mgr").strip().upper()
            new_r = a2.number_input("Matching %", min_value=0.0, max_value=100.0, value=3.0, step=0.25,
                                    key="new_mgr_rate")
            new_d = st.date_input("Starting", value=date.today(), format="MM/DD/YYYY", key="new_mgr_d")
            if st.button("Add manager", disabled=not new_m):
                sb.table("commission_managers").insert({"manager": new_m, "rate": new_r, "excludes": "",
                                                        "effective_from": str(new_d)}).execute()
                st.cache_data.clear()
                st.rerun()


# =====================================================================================
# SHARED TOP BAR: one search box, one team and one date range for every tab
# =====================================================================================
G_PRESETS = ["Today", "Tomorrow", "This week", "Last week", "This month", "Custom"]


def _g_init():
    t = date.today()
    for k, v in {"g_preset": "Today", "g_week": None, "g_custom": (t, t)}.items():
        st.session_state.setdefault(k, v)
    if st.session_state.get("g_week") not in [None] + att_week_options():
        st.session_state["g_week"] = None


def g_range() -> tuple:
    """The date range picked in the top bar (shared by every tab)."""
    _g_init()
    ss, today = st.session_state, date.today()
    p = ss.get("g_preset")
    if p == "Tomorrow":
        t = today + timedelta(days=1)
        return t, t
    if p == "This week":
        return bweek_monday(today), today
    if p == "Last week":
        m = bweek_monday(today) - timedelta(days=7)
        return m, m + timedelta(days=6)
    if p == "This month":
        return today.replace(day=1), today
    if p == "Custom":
        c = ss.get("g_custom")
        if isinstance(c, (list, tuple)) and len(c) == 2:
            return c[0], c[1]
        if isinstance(c, (list, tuple)) and len(c) == 1:
            return c[0], c[0]
    w = ss.get("g_week")
    if p is None and w:
        return w, min(w + timedelta(days=6), today)
    return today, today


def g_is_week() -> bool:
    p = st.session_state.get("g_preset")
    return p in ("This week", "Last week") or (p is None and bool(st.session_state.get("g_week")))


def g_when() -> str:
    s, e = g_range()
    txt = f"{s:%m/%d/%Y}" if s == e else f"{s:%m/%d/%Y} – {e:%m/%d/%Y}"
    return f"Week {bweek_number(s)} · {txt}" if g_is_week() else txt


def _g_preset_changed():
    ss = st.session_state
    p = ss.get("g_preset")
    if p in ("This week", "Last week"):
        ss["g_week"] = g_range()[0]
    elif p is not None:
        ss["g_week"] = None
    elif not ss.get("g_week"):
        ss["g_preset"] = "Today"


def _g_week_label(m: date) -> str:
    return f"Week {bweek_number(m)}"


def _g_week_changed():
    st.session_state["g_preset"] = None if st.session_state.get("g_week") else "Today"


def _g_step(n: int):
    ss, this = st.session_state, bweek_monday(date.today())
    m = bweek_monday(g_range()[0]) + timedelta(days=7 * n)
    m = max(min(m, this), ATT_FIRST_WEEK)
    ss["g_week"] = m
    ss["g_preset"] = "This week" if m == this else "Last week" if m == this - timedelta(days=7) else None


def g_team_reps():
    """Reps in the team picked in the top bar, or None for Everyone."""
    team = st.session_state.get("g_team") or EVERYONE
    return None if team == EVERYONE else load_rep_teams().get(team, set())


def _g_refresh():
    """Re-read appointments / calls from the database (in case a new booking is lagging behind)."""
    for fn in ("load_appointments", "load_calls", "load_freshness", "load_needs_review", "calls_to_lead_in_month",
               "load_leads_with_calls"):
        f = globals().get(fn)
        if f is not None and hasattr(f, "clear"):
            f.clear()
    st.session_state["_g_refreshed"] = True


def _g_search():
    q = (st.session_state.get("g_search") or "").strip()
    if q:
        st.session_state["ls_q"] = q
        st.session_state["_go_search"] = True
    st.session_state["g_search"] = ""


def top_bar(dates: bool = True, team: bool = False, search: bool = True, future: bool = False):
    _g_init()
    presets = G_PRESETS if future else [p for p in G_PRESETS if p != "Tomorrow"]   # Tomorrow: Appointments only
    if st.session_state.get("g_preset") not in presets + [None]:
        st.session_state["g_preset"] = "Today"
    if team:
        teams = load_rep_teams()
        team_opts = [EVERYONE] + sorted(teams)
        if st.session_state.get("g_team") not in team_opts:
            st.session_state["g_team"] = "Sales Team" if "Sales Team" in teams else EVERYONE
    tight = search and team and dates          # Call Report / Call Log: search shrinks to an icon-sized box
    spec = ([("search", .62 if tight else 1.05)] if search else []) + ([("team", 1.6)] if team else []) + \
        ([("preset", 5.45 if future else 4.6), ("gap", 1.1), ("prev", .3), ("week", 1.5), ("next", .3)] if dates else [])
    if not spec:
        return
    if not dates:
        spec = [("search", 3.2), ("gap", 6.8)] if search else spec
    with st.container(key="pm_topbar"):
        cols = st.columns([w for _, w in spec], vertical_alignment="center", gap="small")
        for (name, _), c in zip(spec, cols):
            if name == "search":
                c.text_input("Search", key="g_search", on_change=_g_search, label_visibility="collapsed",
                             icon=":material/search:", placeholder="" if tight else "Search",
                             help="Search MMS for a phone number, company, name or lead ID")
            elif name == "team":
                c.selectbox("Team", team_opts, key="g_team", label_visibility="collapsed",
                            help="Team")
            elif name == "preset":
                c.segmented_control("Dates", presets, key="g_preset", on_change=_g_preset_changed,
                                    label_visibility="collapsed")
            elif name == "prev":
                c.button("‹", key="g_prev", on_click=_g_step, args=(-1,), help="Previous broadcast week",
                         width="stretch")
            elif name == "week":
                c.selectbox("Broadcast week", att_week_options(), key="g_week", index=None, format_func=_g_week_label,
                            placeholder="Week", on_change=_g_week_changed,
                            label_visibility="collapsed")
            elif name == "next":
                c.button("›", key="g_next", on_click=_g_step, args=(1,), help="Next broadcast week", width="stretch",
                         disabled=bweek_monday(g_range()[0]) >= bweek_monday(date.today()))
        if dates and st.session_state.get("g_preset") == "Custom":
            cc = st.columns([2.4, 7.6], vertical_alignment="center")
            cc[0].date_input("Custom dates", key="g_custom", format="MM/DD/YYYY", label_visibility="collapsed")
            cc[1].caption("Pick a start and an end date")
    if st.session_state.pop("_g_refreshed", False):
        st.toast("Refreshed — showing the latest from the database", icon=":material/refresh:")
    if st.session_state.pop("_go_search", False):
        st.switch_page(PAGE_LEAD_SEARCH)


def with_bar(fn, **kw):
    """Run a page with the shared top bar above it."""
    def run():
        top_bar(**kw)
        fn()
    run.__name__ = fn.__name__
    return run


# =====================================================================================
# FIND IN MMS: on request only, search the MMS lead report by company and by contact name
# (used for bookings with no lead match in Supabase). The CSV upload stays the main sync.
# Secrets needed: MMS_USER, MMS_PASSWORD   (optional: MMS_URL)
# =====================================================================================
import requests as _rq
from bs4 import BeautifulSoup as _BS
from urllib.parse import urljoin as _urljoin, urlparse as _urlparse
import ssl as _ssl
import tempfile as _tempfile

MMS_REPORT = "https://mms.primedianetwork.com/marketing/lead_developer_report.php"
MMS_REPORT_COLS = ["lead_id", "created", "last_edited", "lead_source", "media_market", "name_company_ad", "person_phone",
            "person_email", "lead_rating", "partner_rep", "status"]
# report header -> MMS table column in Supabase
MMS_MAP = {"ID#": "Lead Id", "Created": "Lead Started", "Last Edited": "Last Edited", "Source": "Lead Source",
           "Market": "Media Market", "Company": "Company In Ad", "Contact Phone": "Contact Phone (phase2)",
           "Contact Email": "Contact Email (phase2)", "Rating": "Lead Rating", "Lead Owner": "Lead Owner",
           "Status": "Status"}


class MMSError(Exception):
    pass


def _mms_url() -> str:
    try:
        return st.secrets.get("MMS_URL") or MMS_REPORT
    except Exception:
        return MMS_REPORT


def _mms_params(company: str = "", name: str = "") -> list:
    p = [("filter_startdate_callback", ""), ("filter_enddate_callback", ""), ("filter_id", ""),
         ("filter_startdate", ""), ("filter_enddate", ""), ("filter_modified_start", ""), ("filter_modified_end", ""),
         ("filter_company", company), ("filter_phone", ""), ("filter_name", name), ("filter_url", ""),
         ("bulk_select", ""), ("bulk_select_status", ""), ("startpage", ""), ("pageno", "1"), ("grpperpage", "25"),
         ("sortcol", "last_edited"), ("sortdir", "DESC")]
    return p + [("show_columns[]", c) for c in MMS_REPORT_COLS]


def _login_form(html: str):
    soup = _BS(html, "html.parser")
    pw = soup.find("input", {"type": "password"})
    if not pw:
        return None
    return pw.find_parent("form") or soup


def _auto_form(html: str):
    """MMS answers a logged-out request with a blank page that auto-submits a form to /login
    (<form ...><script>document.form.submit();</script>). Browsers run that script; the app does it here."""
    soup = _BS(html, "html.parser")
    if soup.find("input", {"type": "password"}):
        return None
    if soup.find("table") is not None:          # a real page (like the lead report) is never a jump page
        return None
    js = " ".join(t.get_text() for t in soup.find_all("script"))
    for form in soup.find_all("form"):
        inputs = form.find_all(["input", "select", "textarea"])
        only_hidden = all(i.name == "input" and (i.get("type") or "").lower() == "hidden" for i in inputs)
        if only_hidden and ".submit()" in js:
            return form
    return None


def _submit_form(s: _rq.Session, page: _rq.Response, form) -> _rq.Response:
    data = {i.get("name"): i.get("value", "") for i in form.find_all("input")
            if i.get("name") and (i.get("type") or "text").lower() not in ("button", "image", "reset", "file", "checkbox", "radio")}
    action = _urljoin(page.url, form.get("action") or page.url)
    if (form.get("method") or "get").lower() == "post":
        return s.post(action, data=data, timeout=25, verify=s.verify)
    return s.get(action, params=data, timeout=25, verify=s.verify)


def _redirect_target(html: str):
    """A page whose only job is to send the browser elsewhere (meta refresh or a location= script)."""
    import re as _re
    soup = _BS(html, "html.parser")
    if soup.find("table") is not None or soup.find("input", {"type": "password"}):
        return None
    m = soup.find("meta", attrs={"http-equiv": _re.compile("^refresh$", _re.I)})
    if m and "url=" in (m.get("content") or "").lower():
        return m["content"].split("=", 1)[1].strip(" '\"")
    js = " ".join(t.get_text() for t in soup.find_all("script"))
    m2 = _re.search(r"location(?:\.href)?\s*=\s*['\"]([^'\"]+)['\"]|location\.replace\(\s*['\"]([^'\"]+)['\"]", js)
    if m2 and len(soup.get_text(strip=True)) < 400:
        return m2.group(1) or m2.group(2)
    return None


def _follow_jumps(s: _rq.Session, r: _rq.Response) -> _rq.Response:
    for _ in range(4):
        form = _auto_form(r.text)
        if form is not None:
            r = _submit_form(s, r, form)
            continue
        target = _redirect_target(r.text)
        if target:
            r = s.get(_urljoin(r.url, target), timeout=25, verify=s.verify)
            continue
        break
    return r


def _page_hint(r: _rq.Response) -> str:
    """Short, password-free description of a page, for error messages."""
    soup = _BS(r.text, "html.parser")
    msg = ""
    for el in soup.select('[class*="error"], [class*="alert"], [class*="warn"], [id*="error"], [class*="message"]'):
        t = " ".join(el.get_text(" ", strip=True).split())
        if t:
            msg = t[:160]
            break
    if not msg:
        body = soup.body or soup
        msg = " ".join(body.get_text(" ", strip=True).split())[:160]
    return f"HTTP {r.status_code} at {_urlparse(r.url).path or '/'}: \"{msg}\""


def _mms_login(s: _rq.Session, page: _rq.Response) -> _rq.Response:
    try:
        user, pwd = st.secrets.get("MMS_USER"), st.secrets.get("MMS_PASSWORD")
    except Exception:
        user = pwd = None
    user = str(user).strip() if user else user          # stray spaces/newlines from pasting into Secrets
    pwd = str(pwd).strip("\r\n") if pwd else pwd
    if not user or not pwd:
        raise MMSError("The MMS login isn't set up yet. Add MMS_USER and MMS_PASSWORD to the app's Secrets in Streamlit.")
    form = _login_form(page.text)
    data, user_set = {}, False
    for inp in form.find_all("input"):
        n, t = inp.get("name"), (inp.get("type") or "text").lower()
        if not n:
            continue
        if t == "password":
            data[n] = pwd
        elif t in ("text", "email") and not user_set:
            data[n], user_set = user, True
        elif t in ("checkbox", "radio"):
            if inp.has_attr("checked"):
                data[n] = inp.get("value", "on")
        elif t not in ("button", "image", "reset", "file"):
            data[n] = inp.get("value", "")
    btn = form.find(["button", "input"], {"type": "submit"})
    if btn is not None and btn.get("name"):
        data[btn["name"]] = btn.get("value", "")
    action = _urljoin(page.url, form.get("action") or page.url) if getattr(form, "name", "") == "form" else page.url
    method = (form.get("method") or "post").lower() if getattr(form, "name", "") == "form" else "post"
    pu = _urlparse(page.url)
    hdrs = {"Referer": page.url, "Origin": f"{pu.scheme}://{pu.netloc}"}   # what a browser sends with the form
    r = (s.get(action, params=data, headers=hdrs, timeout=25, verify=s.verify) if method == "get"
         else s.post(action, data=data, headers=hdrs, timeout=25, verify=s.verify))
    return r


def _ssl_reason(e: Exception) -> str:
    t = str(e)
    for k in ("unable to get local issuer certificate", "certificate has expired", "self-signed certificate",
              "self signed certificate", "Hostname mismatch", "doesn't match", "unable to verify the first certificate",
              "wrong version number", "handshake failure", "unsupported protocol"):
        if k.lower() in t.lower():
            return k
    return t[-160:]


@st.cache_resource(show_spinner=False)
def _mms_ca_bundle(host: str, port: int = 443) -> str:
    """MMS's server doesn't send its full certificate chain (browsers fill the gap, Python doesn't).
    Fetch the missing intermediate certificate(s) named in the site's own certificate and add them to the
    normal trusted list, so the connection is still fully verified."""
    import certifi
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import Encoding
    from cryptography.x509.oid import AuthorityInformationAccessOID, ExtensionOID
    import datetime as _dt
    cert = x509.load_pem_x509_certificate(_ssl.get_server_certificate((host, port)).encode())
    now = _dt.datetime.now(_dt.timezone.utc)
    end = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after.replace(tzinfo=_dt.timezone.utc)
    if end < now:
        raise MMSError(f"MMS's security certificate expired on {end:%m/%d/%Y}. IT needs to renew it on "
                       f"{host} before the app can connect.")
    if cert.issuer == cert.subject:
        raise MMSError(f"MMS uses a self-signed security certificate, which outside apps can't trust. IT would "
                       f"need to install a standard certificate (for example a free Let's Encrypt one) on {host}.")
    def load_any(url: str):
        """CA 'issuer' files come as DER, PEM, or a PKCS#7 bundle (.p7c / .p7b) - accept all of them."""
        from cryptography.hazmat.primitives.serialization import pkcs7
        resp = _rq.get(url, timeout=20)
        raw = resp.content
        for fn in (lambda r: [x509.load_der_x509_certificate(r)], x509.load_pem_x509_certificates,
                   pkcs7.load_der_pkcs7_certificates, pkcs7.load_pem_pkcs7_certificates):
            try:
                certs = fn(raw)
                if certs:
                    return certs
            except Exception:
                pass
        head = raw[:24]
        raise MMSError(f"MMS's security certificate is missing its middle link. The app tried to fetch it from "
                       f"{url} but got something it couldn't read (HTTP {resp.status_code}, "
                       f"{resp.headers.get('Content-Type', 'no type')}, starts with {head!r}). "
                       f"IT should install the full certificate chain on {host}.")

    def cn(c) -> str:
        v = c.issuer.get_attributes_for_oid(x509.oid.NameOID.COMMON_NAME)
        return v[0].value if v else c.issuer.rfc4514_string()

    extra, last_err = [], None
    for _ in range(4):                                   # walk up the chain until a trusted root
        try:
            aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
        except x509.ExtensionNotFound:
            break
        urls = [d.access_location.value for d in aia if d.access_method == AuthorityInformationAccessOID.CA_ISSUERS]
        urls = [u for u in urls if u.lower().startswith("http")]
        got = None
        for u in urls:
            try:
                got = load_any(u)
                break
            except MMSError as e:
                last_err = e
            except Exception as e:
                last_err = MMSError(f"Couldn't download the certificate's middle link from {u} ({type(e).__name__}).")
        if not got:
            break
        parent = next((c for c in got if c.subject == cert.issuer), got[0])
        for c in got:
            pem = c.public_bytes(Encoding.PEM).decode()
            if pem not in extra:
                extra.append(pem)
        cert = parent
        if cert.issuer == cert.subject:
            break
    if not extra and last_err:
        raise last_err
    if not extra:
        raise MMSError(f"MMS's security certificate (issued by {cn(cert)}) is missing its middle link and "
                       f"doesn't say where to find it. IT should install the full certificate chain on {host}.")
    f = _tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
    f.write(open(certifi.where()).read() + "\n" + "\n".join(extra))
    f.close()
    return f.name


MMS_LOGOFF_HOUR = 18          # the shared MMS login is dropped at 6:00 PM Central


@st.cache_resource(show_spinner=False)
def _mms_holder() -> dict:
    """One MMS login shared by everyone using the app (not one per browser tab)."""
    import threading
    return {"s": None, "until": None, "lock": threading.Lock(), "logins": 0, "timer": None}


def _mms_logoff(h: dict):
    s = h.get("s")
    h["s"], h["until"] = None, None
    if s is not None:
        try:
            s.close()
        except Exception:
            pass


def _mms_session() -> _rq.Session:
    """The day's MMS connection: opened on the first Find in MMS click, reused for every search,
    dropped at 6 PM Central (a click after 6 PM opens a short 30-minute one)."""
    import threading
    h = _mms_holder()
    now = pd.Timestamp.now(tz=CENTRAL)
    if h["s"] is not None and now < h["until"]:
        return h["s"]
    _mms_logoff(h)
    s = _rq.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/130.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    })
    six = now.normalize() + pd.Timedelta(hours=MMS_LOGOFF_HOUR)
    h["s"], h["until"] = s, (six if now < six else now + pd.Timedelta(minutes=30))
    if h.get("timer"):
        h["timer"].cancel()
    t = threading.Timer(max(1.0, (h["until"] - now).total_seconds()), _mms_logoff, args=(h,))
    t.daemon = True
    t.start()
    h["timer"] = t
    return s


def _mms_get(params: list) -> str:
    """Open the report page with the day's shared MMS connection, logging in only if MMS asks."""
    h = _mms_holder()
    with h["lock"]:                     # one search at a time, so two clicks never cause two logins
        return _mms_get_locked(_mms_session(), h, params)


def _mms_get_locked(s: _rq.Session, h: dict, params: list) -> str:
    url = _mms_url()
    try:
        try:
            r = s.get(url, params=params, timeout=25, verify=s.verify)
        except _rq.exceptions.SSLError as e:
            host = _urlparse(url).hostname
            try:
                s.verify = _mms_ca_bundle(host, _urlparse(url).port or 443)
            except MMSError:
                raise
            except Exception as e2:
                raise MMSError(f"MMS's security certificate couldn't be verified ({_ssl_reason(e)}), and the app "
                               f"couldn't repair it automatically ({type(e2).__name__}: {str(e2)[:120]}). IT should check the "
                               f"certificate on {host}.")
            try:
                r = s.get(url, params=params, timeout=25, verify=s.verify)
            except _rq.exceptions.SSLError as e3:
                _mms_ca_bundle.clear()
                raise MMSError(f"MMS's security certificate still couldn't be verified ({_ssl_reason(e3)}). "
                               f"IT should check the certificate on {host}.")
        r = _follow_jumps(s, r)                  # logged out: MMS's blank page jumps to /login
        if _login_form(r.text) is not None:
            login_r = _mms_login(s, r)
            after = _follow_jumps(s, login_r)
            h["logins"] += 1
            r = _follow_jumps(s, s.get(url, params=params, timeout=25, verify=s.verify))
            if _login_form(r.text) is not None:
                cookies = ", ".join(sorted({c.name for c in s.cookies})) or "none"
                hops = " → ".join(f"{x.status_code} {_urlparse(x.url).path or '/'}" for x in login_r.history + [login_r])
                _mms_logoff(h)
                raise MMSError("MMS didn't accept the login. Check MMS_USER and MMS_PASSWORD in the app's Secrets. "
                               f"Details for troubleshooting — login reply: {hops}; after login: {_page_hint(after)}; "
                               f"cookies MMS set: {cookies}.")
    except _rq.exceptions.SSLError as e:
        raise MMSError(f"MMS's security certificate couldn't be verified ({_ssl_reason(e)}).")
    except _rq.exceptions.ConnectionError as e:
        raise MMSError(f"Couldn't reach MMS from the app's server ({type(e).__name__}). MMS may only allow "
                       "connections from the office network.")
    except _rq.RequestException as e:
        raise MMSError(f"The request to MMS failed ({type(e).__name__}: {str(e)[-140:]}).")
    if r.status_code >= 400:
        raise MMSError(f"MMS answered with an error (HTTP {r.status_code}).")
    return r.text


def _cell_text(td) -> str:
    t = td.get_text(" ", strip=True)
    if not t:
        for tag in td.find_all(["input", "button"]):
            t = (tag.get("value") or tag.get_text(" ", strip=True) or "").strip()
            if t:
                break
    return " ".join(t.split())


def parse_mms_report(html: str) -> list:
    soup = _BS(html, "html.parser")
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for hi, tr in enumerate(rows[:6]):
            heads = [_cell_text(c).rstrip(" ▼▲").strip() for c in tr.find_all(["th", "td"], recursive=False)]
            heads = [h.lstrip("▼▲ ").strip() for h in heads]
            if "ID#" in heads and "Company" in heads:
                out = []
                for r in rows[hi + 1:]:
                    cells = r.find_all(["td", "th"], recursive=False)
                    if len(cells) != len(heads):
                        continue
                    rec = {h: _cell_text(c) for h, c in zip(heads, cells) if h in MMS_MAP}
                    lid = "".join(ch for ch in rec.get("ID#", "") if ch.isdigit())
                    if lid:
                        rec["ID#"] = lid
                        out.append(rec)
                return out
    title = soup.title.get_text(strip=True) if soup.title else "no title"
    text = " ".join(soup.get_text(" ", strip=True).split())[:160]
    raise MMSError(f"MMS opened, but the lead table wasn't on the page (page: {title} · it said: \"{text}\").")


@st.cache_data(ttl=600, show_spinner=False)
def mms_search(company: str = "", name: str = "") -> list:
    return parse_mms_report(_mms_get(_mms_params(company.strip(), name.strip())))


def _mms_date(v: str, with_time: bool) -> str:
    p = pd.to_datetime(v, errors="coerce", format="mixed")
    if pd.isna(p):
        return v or None
    return p.strftime("%Y-%m-%d %H:%M:%S" if with_time else "%Y-%m-%d")


def _owner_to_rep(owner: str) -> str:
    try:
        c = load_contacts()
        hit = c[(c["rep"] == owner) | (c["mms_owner"] == owner)]
        if not hit.empty:
            return str(hit.sort_values("rep", key=lambda s: s != owner).iloc[0]["rep"])
    except Exception:
        pass
    return owner


def use_mms_lead(a, rec: dict):
    """Save the MMS lead to Supabase and link it (and its owner) to the appointment."""
    row = {MMS_MAP[k]: (v or None) for k, v in rec.items() if k in MMS_MAP}
    row["Lead Started"] = _mms_date(rec.get("Created", ""), False)
    row["Last Edited"] = _mms_date(rec.get("Last Edited", ""), True)
    sb.table("mms").upsert([row], on_conflict="Lead Id").execute()
    try:
        sb.rpc("refresh_lead_phones", {"p_ids": [row["Lead Id"]]}).execute()
    except Exception:
        pass
    owner = rec.get("Lead Owner") or ""
    rep = _owner_to_rep(owner) if owner else None
    now = pd.Timestamp.now("UTC").isoformat()
    upd = {"lead_id": row["Lead Id"], "suggested_rep": rep, "updated_at": now}
    if rep and not a["assigned_rep"] and rep in _rep_options():
        upd.update({"assigned_rep": rep, "assigned_at": now})
    if not a["invitee_phone"] and rec.get("Contact Phone"):
        upd["invitee_phone"] = rec["Contact Phone"]
    sb.table("appointments").update(upd).eq("id", int(a["id"])).execute()
    for fn in ("load_appointments", "load_needs_review", "load_leads_with_calls"):
        f = globals().get(fn)
        if f is not None and hasattr(f, "clear"):
            f.clear()
    st.session_state.pop(f"mms_res_{a['id']}", None)
    sent = notify_rep(int(a["id"]), upd["assigned_rep"]) if upd.get("assigned_rep") else ""
    st.session_state["ap_toast"] = f"Linked to MMS lead {row['Lead Id']}" + (f" · assigned to {upd['assigned_rep']}{sent}"
                                                                           if upd.get("assigned_rep") else "")


def mms_find_panel(a, auto: bool = False):
    """'Find in MMS' for a booking with no lead match: two separate searches, company and contact name."""
    key = f"mms_res_{a['id']}"
    company, name = (a["company"] or "").strip(), (a["invitee_name"] or "").strip()
    st.markdown("<div class='dsec'>Find in MMS</div>", unsafe_allow_html=True)
    st.caption(f"No lead in the database matches this booking yet. Searches MMS for the company "
               f"**{esc(company or '—')}** and, separately, the contact **{esc(name or '—')}**.")
    go = st.button("Find in MMS", key=f"mms_go_{a['id']}", icon=":material/travel_explore:", width="stretch")
    if go or (auto and key not in st.session_state):
        res = {}
        with st.spinner("Searching MMS..."):
            for label, kw in (("Company", {"company": company}), ("Contact name", {"name": name})):
                if not list(kw.values())[0]:
                    continue
                try:
                    res[label] = mms_search(**kw)
                except MMSError as e:
                    res = {"error": str(e)}
                    break
        st.session_state[key] = res
    res = st.session_state.get(key)
    if res is None:
        return
    if "error" in res:
        st.error(res["error"], icon=":material/error:")
        return
    seen = {}
    for label, rows in res.items():
        for r in rows:
            seen.setdefault(r["ID#"], {**r, "_by": []})["_by"].append(label.lower())
    if not seen:
        st.info("MMS has no lead for this company or contact name.", icon=":material/search_off:")
        return
    st.caption(f"{plural(len(seen), 'lead')} found · pick the right one")
    for lid, r in list(seen.items())[:10]:
        with st.container(border=True, key=f"mms_hit_{a['id']}_{lid}"):
            st.markdown(f"<div class='ap-t'><b>Lead {esc(lid)}</b><span>matched by {esc(' + '.join(r['_by']))}</span></div>"
                        f"<div class='ap-c'>{esc(r.get('Company', ''))}</div>"
                        f"<div class='ap-p'>{esc(r.get('Contact Phone', ''))}{' · ' + esc(r.get('Contact Email')) if r.get('Contact Email') else ''}</div>"
                        f"<div class='ap-p'>Owner <b>{esc(r.get('Lead Owner') or '—')}</b> · {esc(r.get('Status', ''))}"
                        f" · {esc(r.get('Source', ''))} · edited {esc(r.get('Last Edited', ''))}</div>",
                        unsafe_allow_html=True)
            if st.button("Use this lead", key=f"mms_use_{a['id']}_{lid}", type="primary", width="stretch"):
                use_mms_lead(a, r)
                st.rerun()



# =====================================================================================
# APPOINTMENTS (admin only for now) - Calendly bookings, assigned to reps, linked to the call log
# =====================================================================================
APPT_STATUS = {"scheduled": "Scheduled", "showed": "Showed", "no_show": "No-show", "rescheduled": "Rescheduled",
               "canceled": "Canceled", "sold": "Sold"}
CENTRAL = "America/Chicago"


def _digits10(v) -> str:
    d = "".join(ch for ch in str(v or "") if ch.isdigit())
    return d[-10:] if len(d) >= 10 else ""


@st.cache_data(ttl=120, show_spinner="Loading appointments...")
def load_appointments(start: date, end: date) -> pd.DataFrame:
    lo = pd.Timestamp(start).tz_localize(CENTRAL).tz_convert("UTC").isoformat()
    hi = (pd.Timestamp(end) + pd.Timedelta(days=1)).tz_localize(CENTRAL).tz_convert("UTC").isoformat()
    data = (sb.table("appointments").select("*").gte("start_time", lo).lt("start_time", hi)
            .order("start_time").execute().data)
    df = pd.DataFrame(data, columns=["id", "invitee_uri", "event_type", "start_time", "end_time", "invitee_name",
                                     "invitee_email", "invitee_phone", "company", "answers", "status", "lead_id",
                                     "suggested_rep", "assigned_rep", "notes", "booked_at", "notified_rep", "notified_at",
                                     "meeting_kind", "requested_by", "request_source", "sold_amount"])
    if df.empty:
        return df
    df = df.astype(object).where(df.notna(), None)
    df["meeting_kind"] = df["meeting_kind"].fillna("lead_appt")
    df["start"] = pd.to_datetime(df["start_time"], utc=True).dt.tz_convert(CENTRAL).dt.tz_localize(None)
    df["phone10"] = df["invitee_phone"].map(_digits10)
    # the lead's MMS owner (for bookings imported without one) and its MMS status
    ids = sorted({str(x) for x in df["lead_id"].dropna()})
    try:
        recs = {str(r["Lead Id"]): r for r in
                sb.table("mms").select('"Lead Id", "Lead Owner", "Status"').in_("Lead Id", ids).execute().data} if ids else {}
    except Exception:
        recs = {}
    df["mms_status"] = [recs.get(str(x), {}).get("Status") if x else None for x in df["lead_id"]]
    need = df["lead_id"].notna() & df["suggested_rep"].isna()
    if need.any():
        owners = {k: r["Lead Owner"] for k, r in recs.items() if r.get("Lead Owner")}
        df.loc[need, "suggested_rep"] = [(_owner_to_rep(owners[str(x)]) if str(x) in owners else None)
                                         for x in df.loc[need, "lead_id"]]
    return df


@st.cache_data(ttl=120, show_spinner=False)
def lead_appt_dates(lead_ids: tuple) -> dict:
    """{lead_id: [start times]} of the leads' Calendly lead appointments (any date), to link an RFP to how it began."""
    out = {}
    if not lead_ids:
        return out
    rows = (sb.table("appointments").select("lead_id, start_time").eq("meeting_kind", "lead_appt")
            .in_("lead_id", list(lead_ids)).neq("status", "canceled").order("start_time").execute().data)
    for r in rows:
        t = pd.to_datetime(r["start_time"], utc=True).tz_convert(CENTRAL).tz_localize(None)
        out.setdefault(str(r["lead_id"]), []).append(t)
    return out


def _is_presented(a) -> bool:
    return a["status"] in ("showed", "sold") or str(a.get("mms_status") or "")[:2] in ("08", "10")


def _is_sold(a) -> bool:
    return a["status"] == "sold" or str(a.get("mms_status") or "")[:2] == "10"


def link_calls(appts: pd.DataFrame, calls: pd.DataFrame) -> pd.DataFrame:
    """For each appointment, find the rep's call to that lead / number on the appointment day
    (from 30 minutes before to 3 hours after). Adds: call_status, call_at, call_by, call_len."""
    appts = appts.copy()
    appts["call_status"], appts["call_at"], appts["call_by"], appts["call_len"] = "", pd.NaT, "", ""
    now = pd.Timestamp.now(tz=CENTRAL).tz_localize(None)
    c = calls.copy() if calls is not None and not calls.empty else pd.DataFrame(columns=["Date/Time", "To", "From", "Duration", "Lead Id"])
    if not c.empty:
        c["_p"] = c["To"].map(_digits10)
        c["_t"] = pd.to_datetime(c["Date/Time"])
    for i, a in appts.iterrows():
        if a["meeting_kind"] == "rfp":           # Zoom proposal meetings: no phone call to check
            appts.at[i, "call_status"] = ("canceled" if a["status"] == "canceled" else
                                          "upcoming" if a["start"] > now else "rfp_past")
            continue
        hit = pd.DataFrame()
        if not c.empty:
            same = (c["Lead Id"].astype(str) == str(a["lead_id"])) if a["lead_id"] else False
            if a["phone10"]:
                same = same | (c["_p"] == a["phone10"])
            win = (c["_t"] >= a["start"] - pd.Timedelta(minutes=30)) & (c["_t"] <= a["start"] + pd.Timedelta(hours=3))
            hit = c[same & win] if not isinstance(same, bool) else pd.DataFrame()
            if not hit.empty and a["assigned_rep"]:
                mine = hit[hit["From"].astype(str) == str(a["assigned_rep"])]
                hit = mine if not mine.empty else hit
        if not hit.empty:
            h = hit.sort_values("_t").iloc[0]
            appts.at[i, "call_status"] = "called"
            appts.at[i, "call_at"], appts.at[i, "call_by"] = h["_t"], str(h["From"])
            appts.at[i, "call_len"] = _short_len(h["Duration"])
        elif a["status"] == "canceled":
            appts.at[i, "call_status"] = "canceled"
        elif a["start"] > now:
            appts.at[i, "call_status"] = "upcoming"
        else:
            appts.at[i, "call_status"] = "not_called"
    return appts


def _appt_badges(a) -> str:
    cs = a["call_status"]
    call = {"called": f'<span class="bd own">📞 Called {us_time(a["call_at"], False)} · {esc(a["call_len"])}</span>',
            "not_called": '<span class="bd warn">Not called</span>',
            "upcoming": '<span class="bd new">Upcoming</span>',
            "canceled": ""}.get(cs, "")
    stt = a["status"] or "scheduled"
    out = f'<span class="st {stt}">{APPT_STATUS.get(stt, stt)}</span>' if stt != "scheduled" else ""
    rfp = '<span class="bd rfp">RFP</span>' if a["meeting_kind"] == "rfp" else ""
    return rfp + call + out


def _rep_options() -> list:
    return sorted(load_rep_teams().get("Sales Team", set()))


# ---------- rep notices: an email + calendar invite when a rep is assigned ----------
# Secrets needed: SMTP_USER, SMTP_PASSWORD   (optional: SMTP_HOST, SMTP_PORT; default Microsoft 365)
def _smtp_conf():
    try:
        s = st.secrets
        user, pwd = s.get("SMTP_USER"), s.get("SMTP_PASSWORD")
        return (str(s.get("SMTP_HOST") or "smtp.office365.com"), int(s.get("SMTP_PORT") or 587), user, pwd) \
            if user and pwd else None
    except Exception:
        return None


def _ics_text(v) -> str:
    return (str(v or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
            .replace("\r\n", "\\n").replace("\n", "\\n"))


def _ics_fold(line: str) -> str:
    out, cur = [], ""
    for ch in line:                           # lines over 75 bytes continue on the next line after a space
        if len((cur + ch).encode()) > 74:
            out.append(cur)
            cur = " "
        cur += ch
    return "\r\n".join(out + [cur])


def _appt_ics(a: dict, organizer: str, to: str, cancel: bool) -> str:
    utc = lambda t: pd.Timestamp(t).tz_convert("UTC").strftime("%Y%m%dT%H%M%SZ")
    start = pd.to_datetime(a["start_time"], utc=True)
    end = pd.to_datetime(a["end_time"], utc=True) if a.get("end_time") else start + pd.Timedelta(minutes=30)
    now = pd.Timestamp.now("UTC")
    lines = ["BEGIN:VCALENDAR", "PRODID:-//Primedia Network//Call Report//EN", "VERSION:2.0",
             f"METHOD:{'CANCEL' if cancel else 'REQUEST'}", "BEGIN:VEVENT",
             f"UID:appt-{a['id']}@primedianetwork.com", f"SEQUENCE:{int(now.timestamp())}",
             f"DTSTAMP:{utc(now)}", f"DTSTART:{utc(start)}", f"DTEND:{utc(end)}",
             f"SUMMARY:{_ics_text(_appt_title(a))}", f"DESCRIPTION:{_ics_text(_appt_details(a))}",
             f"ORGANIZER:mailto:{organizer}", f"ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=FALSE:mailto:{to}",
             f"STATUS:{'CANCELLED' if cancel else 'CONFIRMED'}", "TRANSP:OPAQUE"]
    if not cancel:
        lines += ["BEGIN:VALARM", "ACTION:DISPLAY", "DESCRIPTION:Appointment", "TRIGGER:-PT15M", "END:VALARM"]
    lines += ["END:VEVENT", "END:VCALENDAR"]
    return "\r\n".join(_ics_fold(x) for x in lines) + "\r\n"


def _appt_title(a: dict) -> str:
    return f"Appointment: {a.get('company') or a.get('invitee_name') or 'Calendly booking'}"


def _appt_details(a: dict) -> str:
    start = pd.to_datetime(a["start_time"], utc=True).tz_convert(CENTRAL).tz_localize(None)
    rows = [("When", f"{start:%A %b} {start.day} · {us_time(start, False)} Central"), ("Meeting", a.get("event_type")),
            ("Company", a.get("company")), ("Contact", a.get("invitee_name")),
            ("Phone", fmt_phone(a["invitee_phone"]) if a.get("invitee_phone") else ""), ("Email", a.get("invitee_email")),
            ("MMS lead", a.get("lead_id"))]
    txt = "\n".join(f"{k}: {v}" for k, v in rows if v)
    if a.get("answers"):
        txt += f"\n\nWhat they told Calendly:\n{a['answers']}"
    if a.get("notes"):
        txt += f"\n\nNotes from management:\n{a['notes']}"
    return txt


def _send_appt_email(a: dict, rep: str, to: str, cancel: bool = False):
    import smtplib
    from email.message import EmailMessage
    host, port, user, pwd = _smtp_conf()
    first = rep.split()[0] if rep else ""
    msg = EmailMessage()
    msg["From"], msg["To"] = user, to
    msg["Subject"] = ("Canceled — " if cancel else "") + _appt_title(a)
    intro = ("This appointment is no longer assigned to you and has been taken off your calendar."
             if cancel else "You've been assigned this appointment. It's on your calendar; please call them on time.")
    msg.set_content(f"Hi {first},\n\n{intro}\n\n{_appt_details(a)}\n")
    msg.add_alternative(_appt_ics(a, user, to, cancel), subtype="calendar",
                        params={"method": "CANCEL" if cancel else "REQUEST"})
    with smtplib.SMTP(host, port, timeout=20) as s:
        s.starttls()
        s.login(user, pwd)
        s.send_message(msg)


def notify_rep(appt_id: int, rep, resend: bool = False) -> str:
    """Email the newly assigned rep an invite, and the previously emailed rep a cancellation.
    Returns a short note for the toast (empty when there was nothing to send)."""
    try:
        a = sb.table("appointments").select("*").eq("id", int(appt_id)).execute().data[0]
    except Exception:
        return ""
    old = a.get("notified_rep")
    if (rep == old and not resend) or (not rep and not old):
        return ""
    if _smtp_conf() is None:
        st.session_state["ap_warn"] = "Rep wasn't emailed: add SMTP_USER and SMTP_PASSWORD to the app's Secrets."
        return ""
    emails, sent, problems = load_rep_emails(), [], []
    try:
        if old and old != rep and emails.get(old):
            _send_appt_email(a, old, emails[old], cancel=True)
        if rep:
            if emails.get(rep):
                _send_appt_email(a, rep, emails[rep])
                sent.append(rep.split()[0])
            else:
                problems.append(f"no email saved for {rep} (Manage → Contacts → Rep emails)")
    except Exception as e:
        problems.append(f"sending failed ({str(e)[:140]})")
    if sent or not rep:
        try:
            sb.table("appointments").update({"notified_rep": rep if sent else None,
                                             "notified_at": pd.Timestamp.now("UTC").isoformat()}).eq("id", int(appt_id)).execute()
        except Exception:
            pass
    if problems:
        st.session_state["ap_warn"] = "Rep wasn't emailed: " + "; ".join(problems)
    return f" · emailed {sent[0]}" if sent else ""


def _assign(appt_id: int, key: str):
    rep = st.session_state.get(key)
    if rep:
        sb.table("appointments").update({"assigned_rep": rep, "assigned_at": pd.Timestamp.now("UTC").isoformat(),
                                         "updated_at": pd.Timestamp.now("UTC").isoformat()}).eq("id", appt_id).execute()
        load_appointments.clear()
        st.session_state["ap_toast"] = f"Assigned to {rep}" + notify_rep(appt_id, rep)


@st.dialog("Appointment", width="medium", position="right")
def appt_drawer(a, calls: pd.DataFrame, find: bool = False):
    st.markdown('<div class="pm-drawer"></div>', unsafe_allow_html=True)
    day = a["start"]
    st.markdown(f'<div class="lc-id">{esc(str(a["event_type"] or "").upper())}</div>'
                f'<div class="dname">{esc(a["company"] or a["invitee_name"] or "")}</div>'
                f'<div class="bds"><span class="bd new">{day:%a %b} {day.day} · {us_time(day, False)}</span>'
                f'{_appt_badges(a)}{f"<span class=bd>Lead {esc(a.lead_id)}</span>" if a["lead_id"] else ""}</div>',
                unsafe_allow_html=True)
    rfp = a["meeting_kind"] == "rfp"
    firsts = lead_appt_dates((str(a["lead_id"]),)).get(str(a["lead_id"]), []) if rfp and a["lead_id"] else []
    firsts = [t for t in firsts if t < day]
    kv = [("Contact", a["invitee_name"]), ("Phone", fmt_phone(a["invitee_phone"]) if a["invitee_phone"] else ""),
          ("Email", a["invitee_email"]), ("Lead owner", a["suggested_rep"]),
          ("Requested by", a["requested_by"] if rfp else ""),
          ("Lead appt", ", ".join(f"{t:%a %b} {t.day} · {us_time(t, False)}" for t in firsts) if rfp else ""),
          ("MMS status", a["mms_status"]),
          ("Sold amount", f"${float(a['sold_amount']):,.0f}" if a["sold_amount"] is not None else ""),
          ("Rep emailed", f"{a['notified_rep']} · {us_time(pd.to_datetime(a['notified_at'], utc=True).tz_convert(CENTRAL).tz_localize(None))}"
           if a["notified_rep"] and a["notified_at"] else ""),
          ("Called", f"{us_time(a['call_at'])} by {a['call_by']} · {a['call_len']}" if a["call_status"] == "called" else "")]
    rows = "".join(f"<span>{k}</span><span>{esc(v)}</span>" for k, v in kv if v)
    if rows:
        st.markdown(f"<div class='dkv'>{rows}</div>", unsafe_allow_html=True)
    if a["answers"]:
        st.markdown(f"<div class='dsec'>What they told Calendly</div><div class='dkv' style='display:block;font-weight:400'>"
                    f"{esc(a['answers'])}</div>", unsafe_allow_html=True)
    reps = _rep_options()
    if a["assigned_rep"] and a["assigned_rep"] not in reps:
        reps = reps + [a["assigned_rep"]]
    stt = list(APPT_STATUS)
    with st.form(f"ap_form_{a['id']}", border=False):
        c1, c2 = st.columns(2)
        rep = c1.selectbox("Assigned rep", reps, index=reps.index(a["assigned_rep"]) if a["assigned_rep"] in reps else None,
                           placeholder="Unassigned")
        out = c2.selectbox("Show / no-show", stt, index=stt.index(a["status"]) if a["status"] in stt else 0,
                           format_func=lambda s: APPT_STATUS[s])
        amount = st.number_input("Sold amount ($)", min_value=0.0, step=100.0, format="%.0f",
                                 value=float(a["sold_amount"]) if a["sold_amount"] is not None else None,
                                 placeholder="Only for a sale") if rfp else None
        notes = st.text_area("Notes", value=a["notes"] or "", placeholder="Anything management should know…", height=80)
        if st.form_submit_button("Save", type="primary", width="stretch"):
            upd = {"status": out, "notes": notes or None, "updated_at": pd.Timestamp.now("UTC").isoformat()}
            if rfp:
                upd["sold_amount"] = amount
            moved = rep and rep != a["assigned_rep"]
            if moved:
                upd.update({"assigned_rep": rep, "assigned_at": pd.Timestamp.now("UTC").isoformat()})
            sb.table("appointments").update(upd).eq("id", int(a["id"])).execute()
            load_appointments.clear()
            # email only when the rep changes or the meeting is canceled (not for notes / show marks)
            sent = notify_rep(int(a["id"]), None if out == "canceled" else rep) \
                if moved or (out == "canceled" and a["status"] != "canceled") else ""
            st.session_state["ap_toast"] = "Appointment saved" + sent
            st.rerun()
    if a["assigned_rep"] and a["status"] != "canceled" and \
            st.button(f"Email {a['assigned_rep'].split()[0]} the invite again", key=f"ap_resend_{a['id']}",
                      icon=":material/forward_to_inbox:", type="tertiary"):
        sent = notify_rep(int(a["id"]), a["assigned_rep"], resend=True)
        load_appointments.clear()
        st.session_state["ap_toast"] = ("Invite" + sent) if sent else "Invite not sent"
        st.rerun()
    if a["lead_id"]:
        hist = calls_to_lead_in_month(str(a["lead_id"]), day.date().replace(day=1))
        st.markdown(f"<div class='dsec'>Calls to this lead in {day:%B} · {len(hist)}</div>{timeline_html(hist, 30)}",
                    unsafe_allow_html=True)
        full_lead_button(str(a["lead_id"]), "ap")
    else:
        mms_find_panel(a, auto=find)


CAL_PX = 104          # pixels per hour (each half hour fits one appointment)


def _tint(hex_color: str, k: float = .88) -> str:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % tuple(round(v + (255 - v) * k) for v in (r, g, b))


KIND_COLORS = {"lead_appt": "#1E4FD8", "rfp": "#0E9F6E"}


def calendar_html(appts: pd.DataFrame, week_start: date) -> str:
    """One week as a calendar: days across, hours down, one colored card per appointment."""
    days = [week_start + timedelta(days=i) for i in range(7)]
    wk = appts[(appts["start"].dt.date >= days[0]) & (appts["start"].dt.date <= days[-1])]
    show = days[:5] + [d for d in days[5:] if (wk["start"].dt.date == d).any()]   # weekends only when booked
    if len(wk):   # start at the hour of the first appointment, end after the last one (no dead space)
        h0 = min(int(t.hour) for t in wk["start"])
        h1 = max(-(-(t.hour * 60 + t.minute + 30) // 60) for t in wk["start"])   # room for a card starting late in the hour
    else:
        h0, h1 = 8, 12
    height = (h1 - h0) * CAL_PX
    today = pd.Timestamp.now(tz=CENTRAL).date()
    hours = "".join(f'<div class="cal-hr" style="top:{(h - h0) * CAL_PX}px"><span>{(h % 12) or 12} {"AM" if h < 12 else "PM"}</span></div>'
                    for h in range(h0, h1))
    cols = []
    for d in show:
        mine = wk[wk["start"].dt.date == d].sort_values("start")
        slot = (mine["start"].dt.hour * 2 + (mine["start"].dt.minute >= 30)).tolist()
        cards = []
        for j, (_, a) in enumerate(mine.iterrows()):
            same = [i for i, x in enumerate(slot) if x == slot[j]]     # appointments sharing this half hour
            n, k = len(same), same.index(j)                            # ... sit side by side
            top = ((a["start"].hour - h0) * 60 + a["start"].minute) / 60 * CAL_PX
            rep = a["assigned_rep"] or ""
            c = KIND_COLORS[a["meeting_kind"]] if rep else "#B45309"     # blue = lead appt, green = RFP
            cs, stt = a["call_status"], a["status"] or "scheduled"
            badge = {"called": f'<span class="cal-ok">📞 {us_time(a["call_at"], False)} · {esc(a["call_len"])}</span>',
                     "not_called": '<span class="cal-no">Not called</span>',
                     "upcoming": '<span class="cal-up">Upcoming</span>' if rep else '<span class="cal-un">Needs a rep</span>',
                     "canceled": '<span class="cal-up">Canceled</span>'}.get(cs, "")
            if not rep and cs != "canceled":
                badge = '<span class="cal-un">Needs a rep</span>'
            elif a["meeting_kind"] == "rfp":
                badge = '<span class="cal-rfp">RFP</span>'
            who = rep.split()[0] if rep else ""
            mark = {"showed": "✓", "sold": "★", "no_show": "✗", "rescheduled": "↻"}.get(stt, "")
            if mark:
                who = f"{who} {mark}".strip()
            cls = "cal-ev" + (" unas" if not rep else "") + (" cxl" if stt == "canceled" else "")
            left, width = f"calc({k} * (100% - 8px) / {n} + 4px)", f"calc((100% - 8px) / {n} - 4px)"
            cards.append(f'<div class="{cls}" style="top:{top:.0f}px;left:{left};width:{width};--c:{c};--bg:{_tint(c)}">'
                         f'<div class="cal-t"><b>{us_time(a["start"], False)}</b>{badge}</div>'
                         f'<div class="cal-r"><span class="cal-c">{esc(a["company"] or a["invitee_name"] or "")}</span>'
                         f'<span class="cal-w">{esc(who)}</span></div></div>')
        cols.append(f'<div class="cal-col{" today" if d == today else ""}"><div class="cal-dh"><b>{d:%a}</b>'
                    f'<span>{d:%b} {d.day}</span><em>{plural(len(mine), "appt")}</em></div>'
                    f'<div class="cal-body" style="height:{height}px">{"".join(cards)}</div></div>')
    return (f'<div class="cal" style="grid-template-columns:62px repeat({len(show)},1fr)">'
            f'<div class="cal-gut" style="height:{height}px">{hours}</div>{"".join(cols)}</div>')


def _ap_pick():
    v = st.session_state.get("ap_pick")
    if v:
        st.session_state["ap_open"] = int(v)
    st.session_state["ap_pick"] = None


def appt_range() -> tuple:
    """Like the top bar's range, but appointments are booked ahead: a week runs through Sunday and
    This month runs to the end of the month (calls stop at today, appointments don't)."""
    start, end = g_range()
    p = st.session_state.get("g_preset")
    if g_is_week():
        end = start + timedelta(days=6)
    elif p == "This month":
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    return start, end


AP_KINDS = {"Lead appts": "lead appointments", "RFP proposals": "RFP proposal meetings", "All": "appointments"}


def _of_kind(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    if df.empty or kind == "All":
        return df
    return df[(df["meeting_kind"] == "rfp") == (kind == "RFP proposals")]


def page_appointments():
    start, end = appt_range()
    toast = st.session_state.pop("ap_toast", None)
    if toast:
        st.toast(toast, icon=":material/check_circle:")
    warn = st.session_state.pop("ap_warn", None)
    if warn:
        st.warning(warn, icon=":material/mail:")
    h1, h2 = st.columns([3, 1.3], vertical_alignment="bottom")
    with h1:
        st.title("Appointments")
        if is_setter():                         # the appointment setter only works lead appointments
            kind = "Lead appts"
        else:
            kind = st.segmented_control("Meetings", list(AP_KINDS), default="Lead appts", key="ap_kind",
                                        label_visibility="collapsed") or "Lead appts"
        when = (f"Week {bweek_number(start)} · " if g_is_week() else "") + \
            (f"{start:%m/%d/%Y}" if start == end else f"{start:%m/%d/%Y} – {end:%m/%d/%Y}")
        st.caption({"Lead appts": f"Calendly lead appointments (salesteam@) for **{esc(when)}**, assigned to a rep and "
                                  "checked against the call log. New bookings arrive on their own.",
                    "RFP proposals": f"Final proposal meetings (mediarfpzoom@) for **{esc(when)}**. Presented and sold "
                                     "come from the MMS lead status or what's marked here.",
                    "All": f"Lead appointments and RFP proposal meetings for **{esc(when)}**."}[kind])
    view_mode = h2.segmented_control("View", ["Calendar", "By rep", "List"], default="Calendar", key="ap_view",
                                     label_visibility="collapsed") or "Calendar"
    appts = _of_kind(load_appointments(start, end), kind)
    if appts.empty:
        st.info(f"No {AP_KINDS[kind]} for {when}.")
        return
    calls = load_calls(start, end)
    if not calls.empty:
        calls = apply_rep_names(calls)
    appts = link_calls(appts, calls)
    ps, pe, cmp_label = prev_range(start, end)
    prev_n = len(_of_kind(load_appointments(ps, pe), kind).query("status != 'canceled'"))

    live = appts[appts["status"] != "canceled"]
    unassigned = appts[appts["assigned_rep"].isna() | (appts["assigned_rep"] == "")]
    booked = {"label": "Booked", "value": f"{len(live):,}{delta_html(len(live), prev_n)}",
              "note": f"vs {prev_n:,} {cmp_label}" + (f" · {int((appts['status'] == 'canceled').sum())} canceled"
                                                        if (appts["status"] == "canceled").any() else "")}
    if kind == "RFP proposals":
        past = live[live["start"] <= pd.Timestamp.now(tz=CENTRAL).tz_localize(None)]
        presented = int(past.apply(_is_presented, axis=1).sum()) if len(past) else 0
        sold = int(live.apply(_is_sold, axis=1).sum()) if len(live) else 0
        firsts = lead_appt_dates(tuple(sorted({str(x) for x in live["lead_id"].dropna()})))
        from_appt = int(sum(any(t < a["start"] for t in firsts.get(str(a["lead_id"]), [])) for _, a in live.iterrows()))
        kpi_cards([
            booked | {"label": "Proposals booked"},
            {"label": "Presented", "value": f"{presented:,}" + (f"<span class='dl'>{presented / len(past):.0%}</span>" if len(past) else ""),
             "note": f"of {len(past):,} past proposal meetings"},
            {"label": "★ Sold", "value": f"{sold:,}" + (f"<span class='dl up'>{sold / presented:.0%}</span>" if presented else ""),
             "note": "close rate = sold ÷ presented"},
            {"label": "From a lead appt", "value": f"{from_appt:,}",
             "note": f"of {len(live):,} had a Calendly lead appointment first"},
        ])
    else:
        done = live[(live["start"] <= pd.Timestamp.now(tz=CENTRAL).tz_localize(None)) & (live["meeting_kind"] != "rfp")]
        called = int((done["call_status"] == "called").sum())
        showed = int((appts["status"].isin(["showed", "sold"])).sum())
        marked = int((appts["status"].isin(["showed", "sold", "no_show"])).sum())
        kpi_cards([
            booked,
            {"label": "📞 Called on time", "value": f"{called:,}" + (f"<span class='dl'>{called / len(done):.0%}</span>" if len(done) else ""),
             "note": f"of {len(done):,} past lead appointments · {len(done) - called:,} not called"},
            {"label": "Showed", "value": f"{showed:,}", "note": f"{marked:,} marked show / no-show so far"},
            {"label": "⚑ Unassigned", "value": f"{len(unassigned):,}", "note": "assign them below" if len(unassigned) else "every appointment has a rep",
             "alert": len(unassigned) > 0},
        ])

    reps = _rep_options()
    if not unassigned.empty:
        st.markdown('<div class="card-h">Unassigned<span>pick a rep, then Assign · suggested = owner of the MMS lead</span></div>',
                    unsafe_allow_html=True)
        per = 3
        items = list(unassigned.iterrows())
        for k in range(0, len(items), per):
            cols = st.columns(per, gap="small")
            for col, (_, a) in zip(cols, items[k:k + per]):
                d = a["start"]
                sug = a["suggested_rep"]
                if a["lead_id"] and sug:
                    note = (f'<div class="sug">Lead {esc(a.lead_id)} · owner {esc(sug)}'
                            f'{"" if sug in reps else " (not on the Sales Team)"}</div>')
                elif a["lead_id"]:
                    note = f'<div class="sug">Lead {esc(a.lead_id)} · no owner found for this lead</div>'
                else:
                    note = '<div class="sug" style="color:#B45309">No MMS lead found for this booking</div>'
                with col:
                    st.markdown(f'<div class="un"><div class="ap-t"><span>{d:%a %b} {d.day} · {us_time(d, False)}</span>'
                                f'<b>{esc(a["event_type"] or "")}</b></div><div class="un-c">{esc(a["company"] or a["invitee_name"])}</div>'
                                f'<div class="un-m">{esc(a["invitee_name"] or "")}{" · " + fmt_phone(a["invitee_phone"]) if a["invitee_phone"] else ""}</div>'
                                f'{note}</div>', unsafe_allow_html=True)
                    x, y = st.columns([2.2, 1], vertical_alignment="bottom")
                    key = f"ap_rep_{a['id']}"
                    x.selectbox("Rep", reps, index=None, placeholder="Pick a rep…", key=key, label_visibility="collapsed")
                    y.button("Assign", type="primary", key=f"ap_as_{a['id']}", width="stretch", on_click=_assign,
                             args=(int(a["id"]), key))
                    if not a["lead_id"]:
                        st.button("Find in MMS", key=f"ap_find_{a['id']}", icon=":material/travel_explore:",
                                  width="stretch", on_click=lambda i=int(a["id"]): st.session_state.update(ap_find=i))
        st.write("")

    assigned = appts[~appts.index.isin(unassigned.index)]
    if st.session_state.get("ap_find"):          # "Find in MMS" on a card: open it and search right away
        pick = appts[appts["id"] == st.session_state.pop("ap_find")]
        st.session_state.pop("ap_open", None)
        if not pick.empty:
            appt_drawer(pick.iloc[0], calls, find=True)
    if view_mode == "Calendar":
        legend = "".join(f'<span><i style="background:{KIND_COLORS[k]}"></i>{label}</span>'
                         for k, label in (("lead_appt", "Lead appt"), ("rfp", "RFP proposal"))
                         if (appts["meeting_kind"] == k).any())
        if not unassigned.empty:
            legend += '<span><i style="background:#E8A33C"></i>Unassigned</span>'
        opts = appts.sort_values("start")
        labels = {int(a["id"]): f"{a['start']:%a %m/%d} {us_time(a['start'], False)} · {a['company'] or a['invitee_name']}"
                                f" · {a['assigned_rep'] or 'Unassigned'}" for _, a in opts.iterrows()}
        c1, c2 = st.columns([2.2, 3], vertical_alignment="center")
        c1.selectbox("Open an appointment", list(labels), index=None, format_func=lambda i: labels[i],
                     placeholder="🔎 Open an appointment…", key="ap_pick", on_change=_ap_pick,
                     label_visibility="collapsed")
        key_txt = ("RFP = final proposal meeting · " if (appts["meeting_kind"] == "rfp").any() else "") + \
            ("📞 rep called within 3 hrs · " if (appts["meeting_kind"] != "rfp").any() else "") + "✓ showed · ✗ no-show · ★ sold"
        c2.markdown(f'<div class="cal-legend" style="margin:0">{legend}<span class="sp"></span>'
                    f'<span>{key_txt}</span></div>', unsafe_allow_html=True)
        w = bweek_monday(start)
        while w <= end:
            if len(appts[(appts["start"].dt.date >= w) & (appts["start"].dt.date <= w + timedelta(days=6))]) or g_is_week():
                if not g_is_week():
                    st.markdown(f'<div class="card-h" style="margin-top:.6rem">{_g_week_label(w)} · '
                                f'{w:%b} {w.day} – {(w + timedelta(days=6)):%b} {(w + timedelta(days=6)).day}</div>',
                                unsafe_allow_html=True)
                st.markdown(calendar_html(appts, w), unsafe_allow_html=True)
            w += timedelta(days=7)
        if st.session_state.get("ap_open"):
            pick = appts[appts["id"] == st.session_state.pop("ap_open")]
            if not pick.empty:
                appt_drawer(pick.iloc[0], calls)
        return
    if view_mode == "List":
        table = pd.DataFrame({
            "When": appts["start"], "Company": appts["company"].fillna(""), "Contact": appts["invitee_name"].fillna(""),
            "Number": appts["invitee_phone"].map(lambda v: fmt_phone(v) if v else ""),
            "Rep": appts["assigned_rep"].fillna("Unassigned"), "Lead ID": appts["lead_id"].fillna(""),
            "Call": appts.apply(lambda a: {"called": f"Called {a['call_len']}", "not_called": "Not called",
                                           "upcoming": "Upcoming", "canceled": "—", "rfp_past": "Zoom"}.get(a["call_status"], ""),
                                axis=1),
            "Show / no-show": appts["status"].map(lambda s: APPT_STATUS.get(s, s)),
        })
        if (appts["meeting_kind"] == "rfp").any():
            table.insert(1, "Type", appts["meeting_kind"].map({"rfp": "RFP"}).fillna("Lead appt"))
            table["MMS status"] = appts["mms_status"].fillna("")

        def _css(frame):
            css = pd.DataFrame("", index=frame.index, columns=frame.columns)
            css["Company"] = "font-weight: 600"
            for i, v in frame["Call"].items():
                css.at[i, "Call"] = ("background-color:#E3F6EA;color:#137A43;font-weight:600" if v.startswith("Called") else
                                     "background-color:#FDECEA;color:#C0392B;font-weight:600" if v == "Not called" else "")
            for i, v in frame["Rep"].items():
                if v == "Unassigned":
                    css.at[i, "Rep"] = "background-color:#FFF4E0;color:#9a5b00;font-weight:600"
            return css
        ev = st.dataframe(table.style.apply(_css, axis=None), hide_index=True, width="stretch",
                          height=min(40 + 35 * len(table), 680), on_select="rerun", selection_mode="single-row",
                          key=f"ap_tbl_{start}_{end}_{len(table)}",
                          column_config={"When": st.column_config.DatetimeColumn(format="ddd M/D h:mm A", width=135)})
        st.caption("Click an appointment to open it")
        sel = ev.selection.rows if ev and ev.selection else []
        if drawer_trigger("ap", f"{start}{end}-{appts.iloc[sel[0]]['id']}" if sel else None):
            appt_drawer(appts.iloc[sel[0]], calls)
        return

    st.markdown('<div class="card-h">By rep<span>📞 = the rep called the lead within 3 hours of the appointment time · '
                'Open an appointment to mark show / no-show</span></div>', unsafe_allow_html=True)
    team = [r for r in reps if (assigned["assigned_rep"] == r).any()] + \
           sorted(set(assigned["assigned_rep"].dropna()) - set(reps))
    if not team:
        st.caption("No assigned appointments in this range.")
        return
    for k in range(0, len(team), 4):
        cols = st.columns(4, gap="small")
        for j, (col, rep) in enumerate(zip(cols, team[k:k + 4])):
            mine = assigned[assigned["assigned_rep"] == rep].sort_values("start")
            ini = "".join(w[0] for w in rep.split()[:2]).upper()
            n_called = int((mine["call_status"] == "called").sum())
            n_past = int(mine["call_status"].isin(["called", "not_called"]).sum())
            rfps = mine[mine["meeting_kind"] == "rfp"]
            n_rfp, n_sold = len(rfps), int(rfps.apply(_is_sold, axis=1).sum()) if len(rfps) else 0
            sub = ([f"called {n_called}/{n_past}"] if len(mine) > n_rfp else []) + \
                  ([f"{n_rfp} RFP · {n_sold} sold"] if n_rfp else [])
            with col, st.container(border=True, key=f"ap_col_{k + j}"):
                st.markdown(f'<div class="ap-colh"><div class="av">{ini}</div><div><b>{esc(rep)}</b>'
                            f'<span>{plural(len(mine), "meeting" if n_rfp else "appointment")} · {" · ".join(sub)}</span></div></div>',
                            unsafe_allow_html=True)
                last = None
                for _, a in mine.iterrows():
                    d = a["start"]
                    if d.date() != last:
                        st.markdown(f'<div class="ap-day">{d:%A} · {d:%b} {d.day}</div>', unsafe_allow_html=True)
                        last = d.date()
                    cls = {"called": "done", "not_called": "noshow", "canceled": "cxl"}.get(a["call_status"], "")
                    st.markdown(f'<div class="ap {cls}"><div class="ap-t"><b>{us_time(d, False)}</b>'
                                f'<span>{esc(fmt_phone(a["invitee_phone"]) if a["invitee_phone"] else "")}</span></div>'
                                f'<div class="ap-c">{esc(a["company"] or a["invitee_name"] or "")}</div>'
                                f'<div class="ap-p">{esc(a["invitee_name"] or "")}{" · lead " + esc(a["lead_id"]) if a["lead_id"] else ""}</div>'
                                f'<div class="bds" style="margin:6px 0 0">{_appt_badges(a)}</div></div>', unsafe_allow_html=True)
                    if st.button("Open", key=f"ap_open_{a['id']}", type="tertiary", icon=":material/open_in_new:"):
                        st.session_state["ap_open"] = int(a["id"])
    if st.session_state.get("ap_open"):
        pick = appts[appts["id"] == st.session_state.pop("ap_open")]
        if not pick.empty:
            appt_drawer(pick.iloc[0], calls)


# =====================================================================================
# NAVIGATION
# =====================================================================================
PAGE_CALL_LOG = st.Page(with_bar(page_call_log, team=True), title="Call Log", icon=":material/list_alt:", url_path="call-log")

if is_viewer() or is_setter():
    # management: Call Log and Appointments, no sidebar; Appointments works the same as for admin
    # setter: Appointments only, lead appointments only (assign reps, set status)
    st.markdown("<style>[data-testid='stSidebar'],[data-testid='stSidebarCollapsedControl'],"
                "[data-testid='stExpandSidebarButton'],[data-testid='stSidebarCollapseButton']"
                "{display:none !important}</style>", unsafe_allow_html=True)
    try:
        _fr = load_freshness()
        _lc = pd.to_datetime(_fr.get("last_call")) if _fr.get("last_call") else None
        _upd = f"Calls through {us_time(_lc)}" if _lc is not None else ""
    except Exception:
        _upd = ""
    # management sees a clean navy bar: no Streamlit toolbar above it
    st.markdown("<style>[data-testid='stHeader']{display:none !important}"
                ".block-container{padding-top:0 !important}.pm-top{margin-top:-1.4rem !important}</style>",
                unsafe_allow_html=True)
    st.markdown(f'''<div class="pm-top"><img src="{LOGO_WHITE_URI}" alt="Primedia Network"><div class="sp"></div>
<span class="ro">{"Appointment setter" if is_setter() else "Management view"}</span>
{f'<span class="upd"><span class="dot"></span>{esc(_upd)}</span>' if _upd else ""}</div>''', unsafe_allow_html=True)
    _ap_page = st.Page(with_bar(page_appointments, search=False, future=True), title="Appointments",
                       icon=":material/event:", url_path="appointments", default=is_setter())
    _vpages = [_ap_page] if is_setter() else \
        [st.Page(with_bar(page_call_log, team=True, search=False), title="Call Log",
                 icon=":material/list_alt:", url_path="call-log", default=True), _ap_page]
    _vnav = st.navigation(_vpages, position="hidden")
    if len(_vpages) > 1:
        with st.container(key="pm_vnav", horizontal=True):
            for _p in _vpages:
                st.page_link(_p, label=_p.title, icon=_p.icon, width="content")
    _vnav.run()
    st.stop()

st.logo(LOGO_WHITE, size="large")   # admin sidebar logo (management view has its own top bar)
PAGE_LEAD_SEARCH = st.Page(page_lead_search, title="Lead Search", icon=":material/person_search:",
                           url_path="lead-search")
try:
    _review_n = len(load_needs_review(30))
except Exception:
    _review_n = 0
try:   # appointments still waiting for a rep (shows as a count in the menu)
    _appt_n = len(sb.table("appointments").select("id").is_("assigned_rep", "null").neq("status", "canceled")
                  .execute().data)
except Exception:
    _appt_n = 0
nav = st.navigation({
    "Reports": [
        st.Page(with_bar(page_call_report, team=True), title="Call Report", icon=":material/call:", url_path="call-report",
                default=True),
        PAGE_CALL_LOG,
        st.Page(with_bar(page_appointments, future=True), title=f"Appointments ({_appt_n})" if _appt_n else "Appointments",
                icon=":material/event:", url_path="appointments"),
        st.Page(with_bar(page_commissions), title="Commissions", icon=":material/payments:", url_path="commissions"),
        st.Page(with_bar(page_att_calls), title="ATT Calls", icon=":material/phone_in_talk:", url_path="att-calls"),
    ],
    "Lookup": [
        PAGE_LEAD_SEARCH,
        st.Page(with_bar(page_needs_review, dates=False), title=f"Needs Review ({_review_n})" if _review_n else "Needs Review",
                icon=":material/flag:", url_path="needs-review"),
    ],
    "Manage": [
        st.Page(with_bar(page_contacts, dates=False), title="Contacts", icon=":material/contacts:", url_path="contacts"),
        st.Page(with_bar(page_toll_routing, dates=False), title="Toll Routing", icon=":material/alt_route:", url_path="toll-routing"),
        st.Page(with_bar(page_toll_sources, dates=False), title="Toll Sources", icon=":material/sell:", url_path="toll-sources"),
        st.Page(with_bar(page_assign_commissions, dates=False), title="Assign Commissions", icon=":material/percent:",
                url_path="assign-commissions"),
        st.Page(with_bar(page_upload_calls, dates=False), title="Upload Calls", icon=":material/upload_file:", url_path="upload-calls"),
        st.Page(with_bar(page_upload_leads, dates=False), title="Upload Leads", icon=":material/group_add:", url_path="upload-leads"),
    ],
})

# Sidebar footer (all pages): how fresh the data is + rarely needed tools
with st.sidebar:
    st.button("Refresh", key="sb_refresh", icon=":material/refresh:", width="stretch", on_click=_g_refresh,
              help="Fetch the latest appointments, calls and leads from the database")
    try:
        fr = load_freshness()
        last_call = pd.to_datetime(fr.get("last_call")) if fr.get("last_call") else None
        last_edit = pd.to_datetime(fr.get("last_lead_edit")) if fr.get("last_lead_edit") else None
        st.markdown(f'''<div class="fresh"><b><span class="dot"></span>Data up to date</b><br>
Calls through <b>{us_time(last_call) or "—"}</b><br>
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
