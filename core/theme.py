"""
The app's stylesheet, built from core/brand.py. Streamlit-free so it can be
rendered outside the app (tests, static previews).

Two halves:
  * Streamlit overrides -- reskin Streamlit's own widgets via their
    data-testid / baseweb attributes. These are internal, not a public API,
    and can drift between Streamlit versions; if a widget stops picking up
    the brand after an upgrade, look here first. Each override degrades to
    Streamlit's default look, never to something broken.
  * nyl-* component classes -- styling for the HTML that core/components.py
    emits. Fully under our control.

Brand rules honored throughout: Dark Blue / Blue / Green with White and Grey
as the only backgrounds, Georgia headlines + Arial body, no gradients, no
drop shadows, square corners. Motion is opt-out: every animation is disabled
under prefers-reduced-motion.

One deliberate deviation from the brand spec: numerals (KPI values, step
and phase numbers) are set in Arial, not Georgia. Georgia only has old-style
figures, where "0" is an x-height circle -- "$0.00" renders as "$o.oo",
which is unacceptable for the one number this tool exists to show.

Nothing in here may contain a "<" character -- the stylesheet is injected
through st.markdown, where a stray "<" would end the <style> block early.
"""

from __future__ import annotations

from .brand import BLUE, BODY_FONT, DARK_BLUE, GREEN, GREY, HEADLINE_FONT, INK_MUTED, INK_ON_DARK, WHITE

_TOKENS = f"""
:root {{
  --nyl-dark: {DARK_BLUE};
  --nyl-blue: {BLUE};
  --nyl-green: {GREEN};
  --nyl-grey: {GREY};
  --nyl-white: {WHITE};
  --nyl-ink-muted: {INK_MUTED};
  --nyl-ink-on-dark: {INK_ON_DARK};
  --nyl-serif: {HEADLINE_FONT};
  --nyl-sans: {BODY_FONT};
  --nyl-mono: Consolas, 'Courier New', monospace;
}}
"""

_STREAMLIT_OVERRIDES = """
html, body, .stApp, [class*="css"] { font-family: var(--nyl-sans); }
.stApp { background: var(--nyl-white); }
h1, h2, h3, h4 { font-family: var(--nyl-serif) !important; color: var(--nyl-dark); }
[data-testid="stDecoration"] { display: none; }
.block-container, [data-testid="stAppViewBlockContainer"], [data-testid="stMainBlockContainer"] {
  padding-top: 4rem; padding-bottom: 2rem; max-width: 1440px;
}
.stApp button { border-radius: 0 !important; box-shadow: none !important; }

[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child { background: var(--nyl-dark); }
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] summary,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: var(--nyl-white) !important; }
[data-testid="stSidebar"] label p { font-weight: 700; letter-spacing: .12em; text-transform: uppercase; font-size: 11px !important; color: var(--nyl-ink-on-dark) !important; }
[data-testid="stSidebar"] [data-baseweb="select"] > div { border-radius: 0 !important; border: 0 !important; }
[data-testid="stSidebarNav"] * { color: var(--nyl-white) !important; font-family: var(--nyl-sans); }
[data-testid="stSidebarNav"] a { border-radius: 0 !important; border-left: 3px solid transparent; transition: background-color .15s ease, border-color .15s ease; }
[data-testid="stSidebarNav"] a:hover { background: rgba(255, 255, 255, .08) !important; border-left-color: rgba(255, 255, 255, .4); }
[data-testid="stSidebarNav"] a[aria-current="page"] { background: rgba(255, 255, 255, .12) !important; border-left-color: var(--nyl-blue); }
[data-testid="stNavSectionHeader"], [data-testid="stNavSectionHeader"] * {
  color: var(--nyl-ink-on-dark) !important; text-transform: uppercase; letter-spacing: .16em; font-size: 11px !important; font-weight: 700;
}
[data-testid="stSidebarNavSeparator"] { border-color: rgba(255, 255, 255, .15) !important; }

[data-testid="stExpander"] details { border-radius: 0 !important; border-color: var(--nyl-grey) !important; }
[data-testid="stExpander"] summary { font-weight: 700; color: var(--nyl-dark); }
[data-testid="stExpander"] summary:hover { color: var(--nyl-blue); }

.stButton button[kind="primary"], [data-testid="stBaseButton-primary"], [data-testid="baseButton-primary"] {
  background: var(--nyl-dark) !important; color: var(--nyl-white) !important; border: 2px solid var(--nyl-dark) !important;
  padding: .85rem 2.2rem !important; transition: background-color .18s ease, border-color .18s ease, transform .18s ease;
}
.stButton button[kind="primary"]:hover:not(:disabled), [data-testid="stBaseButton-primary"]:hover:not(:disabled), [data-testid="baseButton-primary"]:hover:not(:disabled) {
  background: var(--nyl-blue) !important; border-color: var(--nyl-blue) !important; transform: translateY(-1px);
}
.stButton button[kind="primary"]:disabled, [data-testid="stBaseButton-primary"]:disabled, [data-testid="baseButton-primary"]:disabled {
  background: var(--nyl-grey) !important; border-color: var(--nyl-grey) !important; color: var(--nyl-ink-muted) !important; cursor: not-allowed;
}
.stButton button p, .stDownloadButton button p, [data-testid="stDownloadButton"] button p {
  font-family: var(--nyl-sans) !important; font-weight: 700 !important; letter-spacing: .1em; text-transform: uppercase; font-size: 13px !important; color: inherit !important;
}
.stButton button[kind="secondary"], [data-testid="stBaseButton-secondary"], [data-testid="baseButton-secondary"] {
  background: var(--nyl-white) !important; color: var(--nyl-dark) !important; border: 1px solid var(--nyl-dark) !important;
}
.stButton button[kind="secondary"]:hover, [data-testid="stBaseButton-secondary"]:hover, [data-testid="baseButton-secondary"]:hover {
  color: var(--nyl-blue) !important; border-color: var(--nyl-blue) !important;
}
.stDownloadButton button, [data-testid="stDownloadButton"] button {
  background: var(--nyl-white) !important; color: var(--nyl-blue) !important; border: 2px solid var(--nyl-blue) !important;
  padding: .85rem 2.2rem !important; transition: background-color .18s ease, color .18s ease;
}
.stDownloadButton button:hover, [data-testid="stDownloadButton"] button:hover { background: var(--nyl-blue) !important; color: var(--nyl-white) !important; }

[data-testid="stFileUploaderDropzone"], [data-testid="stFileUploader"] section {
  border-radius: 0 !important; background: var(--nyl-grey) !important; border: 0 !important; border-left: 4px solid var(--nyl-blue) !important;
  transition: outline-color .15s ease;
}
[data-testid="stFileUploaderDropzone"]:hover, [data-testid="stFileUploader"] section:hover { outline: 2px solid var(--nyl-blue); }
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="base-input"] { border-radius: 0 !important; }

.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 2px solid var(--nyl-grey); }
.stTabs [data-baseweb="tab"] { height: auto; padding: 12px 18px; background: transparent; }
.stTabs [data-baseweb="tab"] p { font-family: var(--nyl-sans); font-weight: 700; font-size: 12px; letter-spacing: .12em; text-transform: uppercase; color: var(--nyl-ink-muted); }
.stTabs [aria-selected="true"] p { color: var(--nyl-dark); }
.stTabs [data-baseweb="tab-highlight"] { background-color: var(--nyl-blue) !important; height: 3px; }
.stTabs [data-baseweb="tab-border"] { display: none; }

[data-testid="stPageLink-NavLink"] {
  border: 2px solid var(--nyl-dark); border-radius: 0 !important; padding: .55rem 1rem; background: var(--nyl-white);
  transition: background-color .18s ease;
}
[data-testid="stPageLink-NavLink"] p, [data-testid="stPageLink-NavLink"] span {
  font-weight: 700; text-transform: uppercase; letter-spacing: .1em; font-size: 12px !important; color: var(--nyl-dark) !important;
}
[data-testid="stPageLink-NavLink"]:hover { background: var(--nyl-dark); }
[data-testid="stPageLink-NavLink"]:hover p, [data-testid="stPageLink-NavLink"]:hover span { color: var(--nyl-white) !important; }

[data-testid="stToast"] { border-radius: 0 !important; background: var(--nyl-dark) !important; border-left: 6px solid var(--nyl-green); }
[data-testid="stToast"] * { color: var(--nyl-white) !important; }
[data-testid="stDataFrame"] { border: 1px solid var(--nyl-grey); }
"""

_COMPONENTS = """
.nyl-eyebrow {
  display: flex; align-items: center; gap: 10px;
  font: 700 12px/1 var(--nyl-sans); letter-spacing: .18em; text-transform: uppercase; color: var(--nyl-ink-muted);
}
.nyl-eyebrow::before { content: ""; flex: 0 0 10px; height: 10px; background: var(--nyl-blue); }

.nyl-logo {
  display: inline-flex; flex-direction: column; align-items: center; justify-content: center; flex-shrink: 0;
  background: var(--nyl-blue); color: var(--nyl-white); font-family: var(--nyl-sans); font-weight: 700;
  text-transform: uppercase; line-height: 1.02; letter-spacing: .02em; text-align: center;
}

.nyl-hero {
  position: relative; overflow: hidden; background: var(--nyl-dark); color: var(--nyl-white);
  padding: 34px 52px 46px; min-height: 250px;
}
.nyl-hero__rule, .nyl-hero__slab { position: absolute; top: 0; right: 0; bottom: 0; width: 44%; }
.nyl-hero__rule { background: var(--nyl-white); clip-path: polygon(30% 0, 100% 0, 100% 100%, 16% 100%); animation: nyl-slide .8s cubic-bezier(.2, .7, .2, 1) both; }
.nyl-hero__slab { background: var(--nyl-blue); clip-path: polygon(calc(30% + 14px) 0, 100% 0, 100% 100%, calc(16% + 14px) 100%); animation: nyl-slide .8s .08s cubic-bezier(.2, .7, .2, 1) both; }
.nyl-hero__grid {
  position: absolute; right: 48px; top: 50%; transform: translateY(-50%);
  display: grid; grid-template-columns: repeat(7, 14px); gap: 9px;
}
.nyl-hero__grid span { width: 14px; height: 14px; background: var(--nyl-white); opacity: .12; animation: nyl-glimmer 5.2s ease-in-out infinite both; }
.nyl-hero__content { position: relative; max-width: 62%; }
.nyl-lockup { display: flex; align-items: center; gap: 14px; margin-bottom: 30px; }
.nyl-lockup__divider { width: 1px; height: 30px; background: rgba(255, 255, 255, .3); }
.nyl-lockup__name { font: 700 12px/1.3 var(--nyl-sans); letter-spacing: .16em; text-transform: uppercase; color: var(--nyl-white); }
.nyl-lockup__sub { display: block; font-weight: 400; letter-spacing: .08em; color: var(--nyl-ink-on-dark); text-transform: none; }
.nyl-hero .nyl-eyebrow { color: var(--nyl-ink-on-dark); }
.nyl-hero__title { font: 400 44px/1.08 var(--nyl-serif); color: var(--nyl-white); margin-top: 14px; animation: nyl-rise .6s .1s ease both; }
.nyl-hero__lede { font: 17px/1.5 var(--nyl-sans); color: var(--nyl-ink-on-dark); margin-top: 14px; max-width: 640px; animation: nyl-rise .6s .18s ease both; }
.nyl-hero__meta { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 22px; animation: nyl-rise .6s .26s ease both; }
.nyl-hero__meta span { font: 700 11px/1 var(--nyl-sans); letter-spacing: .12em; text-transform: uppercase; color: var(--nyl-white); border: 1px solid rgba(255, 255, 255, .32); padding: 8px 10px; }
.nyl-hero__sweep { position: absolute; left: 0; bottom: 0; height: 5px; width: 100%; background: var(--nyl-blue); transform-origin: left center; animation: nyl-sweep 1.2s .2s cubic-bezier(.2, .7, .2, 1) both; }

.nyl-chips { display: flex; flex-wrap: wrap; gap: 10px; }
.nyl-chip { background: var(--nyl-grey); padding: 11px 16px 12px; border-left: 4px solid var(--nyl-blue); animation: nyl-rise .45s ease both; }
.nyl-chip__k { font: 700 10px/1 var(--nyl-sans); letter-spacing: .16em; text-transform: uppercase; color: var(--nyl-ink-muted); }
.nyl-chip__v { font: 700 14px/1.3 var(--nyl-sans); color: var(--nyl-dark); margin-top: 6px; }
.nyl-hint { font: 12px var(--nyl-sans); color: var(--nyl-ink-muted); margin-top: 8px; }
.nyl-hint code { font-family: var(--nyl-mono); color: var(--nyl-dark); background: transparent; padding: 0; }

.nyl-step { display: flex; align-items: flex-start; gap: 16px; margin-top: 26px; padding-top: 22px; border-top: 1px solid var(--nyl-grey); }
.nyl-step__num {
  flex: 0 0 auto; min-width: 44px; height: 44px; padding: 0 8px; background: var(--nyl-dark); color: var(--nyl-white);
  font: 700 16px/1 var(--nyl-sans); letter-spacing: .04em; display: flex; align-items: center; justify-content: center;
}
.nyl-step__title { font: 400 26px/1.15 var(--nyl-serif); color: var(--nyl-dark); }
.nyl-step__hint { font: 14px/1.45 var(--nyl-sans); color: var(--nyl-ink-muted); margin-top: 5px; }

.nyl-source { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.nyl-source__badge {
  flex: 0 0 30px; height: 30px; background: var(--nyl-blue); color: var(--nyl-white);
  font: 700 14px/1 var(--nyl-sans); display: flex; align-items: center; justify-content: center;
}
.nyl-source__title { font: 400 21px/1.2 var(--nyl-serif); color: var(--nyl-dark); }
.nyl-source__hint { font: 13px/1.4 var(--nyl-sans); color: var(--nyl-ink-muted); }

.nyl-loaded {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; padding: 11px 14px; background: var(--nyl-white);
  border: 1px solid var(--nyl-grey); border-left: 4px solid var(--nyl-green); font: 13px var(--nyl-sans); color: var(--nyl-dark);
  animation: nyl-rise .35s ease both;
}
.nyl-loaded__icon { width: 20px; height: 20px; background: var(--nyl-green); color: var(--nyl-white); font: 700 12px/20px var(--nyl-sans); text-align: center; }
.nyl-loaded b { font-weight: 700; }
.nyl-loaded__dot { color: var(--nyl-ink-muted); }

.nyl-callout {
  display: flex; align-items: flex-start; gap: 12px; padding: 14px 16px; background: var(--nyl-grey);
  border-left: 4px solid var(--nyl-blue); font: 14px/1.45 var(--nyl-sans); color: var(--nyl-dark); animation: nyl-rise .35s ease both;
}
.nyl-callout__icon { flex: 0 0 22px; height: 22px; background: var(--nyl-blue); color: var(--nyl-white); font: 700 12px/22px var(--nyl-sans); text-align: center; }
.nyl-callout.is-ok { border-left-color: var(--nyl-green); }
.nyl-callout.is-ok .nyl-callout__icon { background: var(--nyl-green); }
.nyl-callout.is-alert { border-left-color: var(--nyl-dark); font-weight: 700; }
.nyl-callout.is-alert .nyl-callout__icon { background: var(--nyl-dark); }

.nyl-verdict {
  position: relative; overflow: hidden; display: flex; align-items: center; gap: 24px; margin-top: 8px;
  padding: 26px 30px; background: var(--nyl-white); border: 1px solid var(--nyl-grey); border-left: 10px solid var(--nyl-dark);
  animation: nyl-rise .5s ease both;
}
.nyl-verdict.is-ok { border-left-color: var(--nyl-green); }
.nyl-verdict.is-info { border-left-color: var(--nyl-blue); }
.nyl-verdict__mark {
  position: relative; flex: 0 0 68px; height: 68px; background: var(--nyl-dark); color: var(--nyl-white);
  display: flex; align-items: center; justify-content: center; font: 700 32px/1 var(--nyl-sans);
}
.nyl-verdict.is-ok .nyl-verdict__mark { background: var(--nyl-green); }
.nyl-verdict.is-info .nyl-verdict__mark { background: var(--nyl-blue); }
.nyl-verdict__title { font: 400 30px/1.18 var(--nyl-serif); color: var(--nyl-dark); margin-top: 10px; }
.nyl-verdict__detail { font: 14px/1.45 var(--nyl-sans); color: var(--nyl-ink-muted); margin-top: 8px; }
.nyl-burst { position: absolute; left: 34px; top: 34px; width: 0; height: 0; pointer-events: none; }
.nyl-burst span { position: absolute; width: 9px; height: 9px; background: var(--nyl-green); left: -4px; top: -4px; opacity: 0; animation: nyl-burst 1s .35s cubic-bezier(.15, .7, .3, 1) both; }
.nyl-burst span:nth-child(odd) { background: var(--nyl-blue); width: 7px; height: 7px; }
.nyl-burst span:nth-child(1) { --a: 0deg; } .nyl-burst span:nth-child(2) { --a: 45deg; }
.nyl-burst span:nth-child(3) { --a: 90deg; } .nyl-burst span:nth-child(4) { --a: 135deg; }
.nyl-burst span:nth-child(5) { --a: 180deg; } .nyl-burst span:nth-child(6) { --a: 225deg; }
.nyl-burst span:nth-child(7) { --a: 270deg; } .nyl-burst span:nth-child(8) { --a: 315deg; }

.nyl-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin-top: 16px; }
.nyl-kpi { background: var(--nyl-white); border: 1px solid var(--nyl-grey); border-top: 5px solid var(--nyl-dark); padding: 18px 20px 18px; animation: nyl-rise .5s ease both; }
.nyl-kpi.is-ok { border-top-color: var(--nyl-green); }
.nyl-kpi.is-manual { border-top-color: var(--nyl-blue); }
.nyl-kpi.is-neutral { border-top-color: var(--nyl-grey); }
.nyl-kpi__label { font: 700 13px/1.3 var(--nyl-sans); color: var(--nyl-ink-muted); }
.nyl-kpi__value { font: 700 34px/1.05 var(--nyl-sans); letter-spacing: -.01em; color: var(--nyl-dark); margin-top: 12px; white-space: nowrap; }
.nyl-kpi__value small { font-size: 18px; font-weight: 400; letter-spacing: 0; color: var(--nyl-ink-muted); margin-left: 2px; }
.nyl-kpi__sub { font: 13px/1.4 var(--nyl-sans); color: var(--nyl-ink-muted); margin-top: 8px; }

.nyl-panel { background: var(--nyl-white); border: 1px solid var(--nyl-grey); padding: 22px 24px 24px; margin-top: 16px; animation: nyl-rise .5s ease both; }
.nyl-panel__head { display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; flex-wrap: wrap; margin-bottom: 18px; }
.nyl-panel__title { font: 400 22px/1.2 var(--nyl-serif); color: var(--nyl-dark); margin-top: 8px; }
.nyl-legend { display: flex; gap: 16px; flex-wrap: wrap; font: 12px var(--nyl-sans); color: var(--nyl-ink-muted); }
.nyl-legend > span { display: inline-flex; align-items: center; gap: 7px; }

.nyl-sq {
  display: inline-flex; align-items: center; justify-content: center; width: 30px; height: 30px; flex-shrink: 0;
  background: var(--nyl-grey); color: var(--nyl-white); font: 700 13px/1 var(--nyl-sans); transition: transform .15s ease;
}
.nyl-sq.is-ok { background: var(--nyl-green); }
.nyl-sq.is-bad { background: var(--nyl-dark); }
.nyl-sq.is-manual { background: var(--nyl-blue); }
.nyl-sq.is-empty { background: transparent; box-sizing: border-box; border: 1px solid var(--nyl-grey); }
.nyl-legend .nyl-sq { width: 16px; height: 16px; font-size: 10px; }

.nyl-beat__months { display: flex; flex-wrap: wrap; gap: 18px 28px; }
.nyl-beat__mlabel { font: 700 11px/1 var(--nyl-sans); letter-spacing: .16em; text-transform: uppercase; color: var(--nyl-ink-muted); margin-bottom: 10px; }
.nyl-beat { display: flex; flex-wrap: wrap; gap: 6px; }
.nyl-beat__day { display: flex; flex-direction: column; align-items: center; gap: 5px; min-width: 34px; animation: nyl-pop .4s ease both; }
.nyl-beat__day:hover .nyl-sq { transform: scale(1.14); }
.nyl-beat__d { font: 700 12px/1 var(--nyl-sans); color: var(--nyl-dark); }
.nyl-beat__w { font: 10px/1 var(--nyl-sans); color: var(--nyl-ink-muted); text-transform: uppercase; letter-spacing: .06em; }

.nyl-matrix-wrap { overflow-x: auto; padding-bottom: 4px; }
.nyl-matrix { display: grid; gap: 5px; align-items: center; }
.nyl-matrix__corner { font: 700 10px/1 var(--nyl-sans); letter-spacing: .16em; text-transform: uppercase; color: var(--nyl-ink-muted); }
.nyl-matrix__col { font: 700 11px/1.15 var(--nyl-sans); color: var(--nyl-dark); text-align: center; }
.nyl-matrix__col small { display: block; font-weight: 400; color: var(--nyl-ink-muted); font-size: 9px; letter-spacing: .06em; text-transform: uppercase; }
.nyl-matrix__row { padding-right: 12px; white-space: nowrap; }
.nyl-matrix__code { font: 700 14px/1 var(--nyl-mono); color: var(--nyl-dark); }
.nyl-matrix__note { display: block; font: 11px/1.2 var(--nyl-sans); color: var(--nyl-ink-muted); margin-top: 3px; }
.nyl-matrix .nyl-sq { width: 28px; height: 28px; font-size: 12px; animation: nyl-pop .4s ease both; }
.nyl-matrix .nyl-sq:hover { transform: scale(1.14); }

.nyl-facts { display: grid; grid-template-columns: minmax(170px, 260px) 1fr; border-top: 1px solid var(--nyl-grey); }
.nyl-facts > div { padding: 11px 0; border-bottom: 1px solid var(--nyl-grey); font: 14px/1.4 var(--nyl-sans); }
.nyl-facts__k { color: var(--nyl-ink-muted); font-weight: 700; padding-right: 16px !important; }
.nyl-facts__v { color: var(--nyl-dark); font-family: var(--nyl-mono) !important; }

.nyl-export { display: flex; flex-wrap: wrap; align-items: center; gap: 22px; padding: 20px 22px; margin-top: 12px; background: var(--nyl-grey); }
.nyl-export__stack { display: grid; grid-template-columns: repeat(3, 12px); gap: 4px; }
.nyl-export__stack span { width: 12px; height: 12px; background: var(--nyl-dark); }
.nyl-export__stack span:first-child { background: var(--nyl-green); }
.nyl-export__title { font: 400 20px/1.2 var(--nyl-serif); color: var(--nyl-dark); }
.nyl-export__tabs { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.nyl-export__tabs span { font: 700 11px/1 var(--nyl-sans); letter-spacing: .06em; color: var(--nyl-dark); background: var(--nyl-white); padding: 7px 9px; }
.nyl-export__file { font: 12px var(--nyl-mono); color: var(--nyl-ink-muted); margin-top: 8px; }

.nyl-phase { position: relative; background: var(--nyl-white); border: 1px solid var(--nyl-grey); padding: 24px 24px 22px; min-height: 252px; transition: border-color .2s ease, transform .2s ease; animation: nyl-rise .5s ease both; }
.nyl-phase:hover { border-color: var(--nyl-blue); transform: translateY(-3px); }
.nyl-phase__num { font: 400 50px/1 var(--nyl-sans); letter-spacing: -.03em; color: var(--nyl-dark); }
.nyl-phase__num::after { content: ""; display: block; width: 36px; height: 5px; background: var(--nyl-blue); margin-top: 14px; }
.nyl-phase__title { font: 400 23px/1.2 var(--nyl-serif); color: var(--nyl-dark); margin-top: 16px; }
.nyl-phase__desc { font: 14px/1.5 var(--nyl-sans); color: var(--nyl-ink-muted); margin-top: 8px; }
.nyl-phase__status { display: flex; align-items: center; gap: 9px; margin-top: 18px; font: 700 12px/1.3 var(--nyl-sans); letter-spacing: .06em; text-transform: uppercase; color: var(--nyl-dark); }
.nyl-phase__status .nyl-sq { width: 20px; height: 20px; font-size: 11px; }

.nyl-legacy { background: var(--nyl-white); border: 1px solid var(--nyl-grey); border-top: 5px solid var(--nyl-dark); padding: 22px 24px; animation: nyl-rise .5s ease both; }
.nyl-legacy__acct { font: 700 11px/1 var(--nyl-sans); letter-spacing: .16em; text-transform: uppercase; color: var(--nyl-ink-muted); }
.nyl-legacy__link { display: flex; align-items: center; gap: 12px; margin-top: 14px; }
.nyl-legacy__link .nyl-matrix__code { font-size: 22px; }
.nyl-legacy__arrow { font: 700 20px/1 var(--nyl-sans); color: var(--nyl-blue); }

.nyl-road { margin-top: 14px; }
.nyl-road__item { display: flex; align-items: flex-start; gap: 16px; padding: 14px 0; border-bottom: 1px solid var(--nyl-grey); animation: nyl-rise .45s ease both; }
.nyl-road__item:last-child { border-bottom: 0; }
.nyl-road__t { font: 400 19px/1.25 var(--nyl-serif); color: var(--nyl-dark); }
.nyl-road__d { font: 14px/1.45 var(--nyl-sans); color: var(--nyl-ink-muted); margin-top: 3px; }

.nyl-flow { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 0; margin-top: 4px; border: 1px solid var(--nyl-grey); }
.nyl-flow__step { position: relative; padding: 24px 26px; border-right: 1px solid var(--nyl-grey); animation: nyl-rise .5s ease both; }
.nyl-flow__step:last-child { border-right: 0; }
.nyl-flow__n { width: 36px; height: 36px; background: var(--nyl-blue); color: var(--nyl-white); font: 700 16px/36px var(--nyl-sans); text-align: center; }
.nyl-flow__t { font: 400 20px/1.25 var(--nyl-serif); color: var(--nyl-dark); margin-top: 14px; }
.nyl-flow__d { font: 14px/1.5 var(--nyl-sans); color: var(--nyl-ink-muted); margin-top: 6px; }

.nyl-credit { display: flex; flex-wrap: wrap; align-items: center; gap: 22px; padding: 26px 28px; margin-top: 16px; background: var(--nyl-dark); color: var(--nyl-white); position: relative; overflow: hidden; }
.nyl-credit::after { content: ""; position: absolute; top: 0; right: 0; bottom: 0; width: 160px; background: var(--nyl-blue); clip-path: polygon(40% 0, 100% 0, 100% 100%, 0 100%); }
.nyl-credit__body { position: relative; z-index: 1; }
.nyl-credit .nyl-eyebrow { color: var(--nyl-ink-on-dark); }
.nyl-credit__name { font: 400 26px/1.2 var(--nyl-serif); color: var(--nyl-white); margin-top: 10px; }
.nyl-credit__team { font: 14px/1.45 var(--nyl-sans); color: var(--nyl-ink-on-dark); margin-top: 4px; }

.nyl-avatar { flex: 0 0 auto; width: 56px; height: 56px; background: var(--nyl-blue); color: var(--nyl-white); font: 400 22px/56px var(--nyl-serif); text-align: center; position: relative; z-index: 1; }
.nyl-coda {
  display: inline-flex; align-items: center; gap: 8px; margin-top: 12px; padding: 7px 11px; border: 1px solid rgba(255, 255, 255, .38);
  font: 700 11px/1 var(--nyl-sans); letter-spacing: .2em; text-transform: uppercase; color: var(--nyl-white);
}
.nyl-coda::before { content: ""; width: 8px; height: 8px; background: var(--nyl-green); }

.nyl-profile { margin-top: 22px; padding-top: 20px; border-top: 1px solid rgba(255, 255, 255, .18); }
.nyl-profile .nyl-eyebrow { color: var(--nyl-ink-on-dark); font-size: 10px; }
.nyl-profile__row { display: flex; align-items: center; gap: 12px; margin-top: 14px; }
.nyl-profile .nyl-avatar { width: 42px; height: 42px; font-size: 17px; line-height: 42px; }
.nyl-profile__name { font: 400 17px/1.2 var(--nyl-serif); color: var(--nyl-white); }
.nyl-profile__team { font: 12px/1.35 var(--nyl-sans); color: var(--nyl-ink-on-dark); margin-top: 2px; }

.nyl-footer {
  display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 28px; margin-top: 56px;
  padding: 26px 30px; background: var(--nyl-grey); border-top: 5px solid var(--nyl-dark);
}
.nyl-footer__brand { display: flex; align-items: center; gap: 14px; }
.nyl-footer__company { font: 400 17px/1.25 var(--nyl-serif); color: var(--nyl-dark); }
.nyl-footer__small { font: 12px/1.45 var(--nyl-sans); color: var(--nyl-ink-muted); }
.nyl-footer__credit { font: 13px/1.5 var(--nyl-sans); color: var(--nyl-dark); }
.nyl-footer__credit b { font-weight: 700; }
.nyl-footer__contact { font: 700 12px/1.4 var(--nyl-sans); letter-spacing: .08em; text-transform: uppercase; color: var(--nyl-dark); text-align: right; }

@media (max-width: 900px) {
  .nyl-hero { padding: 28px 26px 40px; }
  .nyl-hero__content { max-width: 100%; }
  .nyl-hero__rule, .nyl-hero__slab, .nyl-hero__grid { display: none; }
  .nyl-hero__title { font-size: 34px; }
  .nyl-footer { grid-template-columns: 1fr; }
  .nyl-footer__contact { text-align: left; }
  .nyl-flow__step { border-right: 0; border-bottom: 1px solid var(--nyl-grey); }
}

@keyframes nyl-rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
@keyframes nyl-pop { from { opacity: 0; transform: scale(.55); } to { opacity: 1; transform: none; } }
@keyframes nyl-slide { from { opacity: 0; transform: translateX(60px); } to { opacity: 1; transform: none; } }
@keyframes nyl-sweep { from { transform: scaleX(0); } to { transform: scaleX(1); } }
@keyframes nyl-glimmer { 0%, 100% { opacity: .1; } 50% { opacity: .92; } }
@keyframes nyl-burst {
  0% { opacity: 0; transform: rotate(var(--a)) translateX(0) scale(.4); }
  15% { opacity: 1; }
  100% { opacity: 0; transform: rotate(var(--a)) translateX(64px) scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  [class*="nyl-"], [class*="nyl-"] * { animation: none !important; transition: none !important; }
}
"""


def brand_css() -> str:
    """The full stylesheet (no surrounding <style> tag)."""
    return _TOKENS + _STREAMLIT_OVERRIDES + _COMPONENTS
