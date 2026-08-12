from __future__ import annotations

import streamlit as st


def apply_global_styles(primary: str = "#B91C1C", secondary: str = "#111827") -> None:
    st.markdown(
        f"""
        <style>
        :root {{
          --pm-primary: {primary};
          --pm-secondary: {secondary};
          --pm-muted: #596273;
          --pm-surface: #FFFFFF;
          --pm-border: #DDE2E8;
          --pm-focus: #2563EB;
        }}
        html {{ font-size: 16px; }}
        .stApp {{ background: #F7F8FA; color: var(--pm-secondary); }}
        [data-testid="stSidebar"] {{ background: #111827; }}
        [data-testid="stSidebar"] * {{ color: #F9FAFB; }}
        [data-testid="stSidebar"] .stButton button {{
          border: 1px solid rgba(255,255,255,.18);
          background: rgba(255,255,255,.06);
        }}
        .pm-brand {{
          padding: 10px 0 18px 0;
          border-bottom: 1px solid rgba(255,255,255,.18);
          margin-bottom: 14px;
        }}
        .pm-brand-title {{ font-size: 1.15rem; font-weight: 800; letter-spacing: .02em; }}
        .pm-brand-version {{ color: #D1D5DB; font-size: .82rem; }}
        .pm-page-title {{
          font-size: clamp(1.65rem, 3vw, 2rem); font-weight: 850; color: var(--pm-secondary);
          letter-spacing: -.03em; margin: 0 0 .2rem 0;
        }}
        .pm-page-subtitle {{ color: var(--pm-muted); margin-bottom: 1.1rem; max-width: 72rem; }}
        .pm-card {{
          background: var(--pm-surface); border: 1px solid var(--pm-border);
          border-radius: 14px; padding: 18px; box-shadow: 0 5px 18px rgba(17,24,39,.045);
          margin-bottom: 12px;
        }}
        .pm-kicker {{ color: var(--pm-primary); font-weight: 750; font-size: .78rem; text-transform: uppercase; letter-spacing: .08em; }}
        .pm-number {{ font-size: 1.75rem; font-weight: 850; color: var(--pm-secondary); }}
        .pm-label {{ color: var(--pm-muted); font-size: .9rem; }}
        .pm-badge {{
          display: inline-block; border-radius: 999px; padding: 4px 9px;
          background: #FEE2E2; color: #7F1D1D; font-size: .78rem; font-weight: 750;
        }}
        .pm-badge-muted {{ background: #E5E7EB; color: #374151; }}
        .pm-badge-good {{ background: #DCFCE7; color: #14532D; }}
        .pm-player-name {{ font-weight: 800; color: var(--pm-secondary); font-size: 1.05rem; }}
        .pm-player-meta {{ color: var(--pm-muted); font-size: .86rem; }}
        .pm-eval-name {{ margin: .25rem 0 .05rem 0; line-height: 1.2; color: var(--pm-secondary); }}
        .pm-eval-name strong {{ font-size: .98rem; }}
        .pm-eval-name span {{ color: var(--pm-muted); font-size: .79rem; margin-left: .35rem; }}
        .pm-eval-separator {{ height: 1px; background: #EEF1F4; margin: .18rem 0 .32rem 0; }}

        /* Large, keyboard-friendly targets. */
        .stButton > button, div[data-testid="stFormSubmitButton"] button,
        div[data-testid="stDownloadButton"] button {{ min-height: 44px; border-radius: 9px; }}
        .stButton > button[kind="primary"], div[data-testid="stFormSubmitButton"] button[kind="primary"] {{
          background: var(--pm-primary); border-color: var(--pm-primary); color:white;
        }}
        button:focus-visible, input:focus-visible, textarea:focus-visible,
        [role="radio"]:focus-visible, [role="slider"]:focus-visible, [role="checkbox"]:focus-visible {{
          outline: 3px solid var(--pm-focus) !important; outline-offset: 2px !important;
        }}
        div[data-testid="stMetric"] {{
          background:white; border:1px solid var(--pm-border); border-radius:12px; padding:12px;
        }}
        div[data-testid="stForm"] {{
          background:white; border:1px solid var(--pm-border); border-radius:14px; padding:16px;
        }}
        div[data-testid="stTextInput"] label, div[data-testid="stTextArea"] label,
        div[data-testid="stSelectbox"] label, div[data-testid="stSlider"] label {{ font-weight: 650; }}
        div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea,
        div[data-testid="stSelectbox"] input {{ font-size: 16px !important; }}
        div[data-testid="stTextInput"] input, div[data-testid="stSelectbox"] > div > div {{ min-height: 44px; }}
        div[data-testid="stCheckbox"] label {{ min-height: 40px; align-items: center; }}
        .pm-compact-player {{
          background: #FFFFFF; border: 1px solid var(--pm-border); border-radius: 11px;
          padding: 9px 12px; margin: 6px 0 2px 0;
        }}
        .pm-help {{ color: var(--pm-muted); font-size: .84rem; line-height: 1.35; }}

        /* On narrow screens, reduce decorative spacing rather than shrinking controls. */
        @media (max-width: 720px) {{
          .block-container {{ padding-left: .85rem !important; padding-right: .85rem !important; padding-top: 1rem !important; }}
          .pm-card {{ padding: 12px; border-radius: 11px; }}
          .pm-compact-player {{ padding: 7px 9px; margin-top: 4px; }}
          .pm-player-name {{ font-size: .98rem; }}
          .pm-player-meta {{ font-size: .8rem; }}
          .pm-eval-name {{ margin-top: .15rem; }}
          .pm-eval-name strong {{ font-size: .96rem; }}
          .pm-eval-name span {{ display: block; margin-left: 0; margin-top: .08rem; font-size: .76rem; }}
          div[data-testid="stSlider"] {{ margin-bottom: -.2rem; }}
          .pm-eval-separator {{ margin: .05rem 0 .22rem 0; }}
          div[data-testid="stMetric"] {{ padding: 9px; }}
          div[data-testid="stForm"] {{ padding: 11px; border-radius: 11px; }}
          div[data-testid="stTextArea"] textarea {{ min-height: 72px !important; }}
          h1, h2, h3 {{ scroll-margin-top: 1rem; }}
        }}
        @media (prefers-reduced-motion: reduce) {{
          *, *::before, *::after {{ scroll-behavior: auto !important; transition: none !important; animation: none !important; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str | None = None) -> None:
    st.markdown(f'<div class="pm-page-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="pm-page-subtitle">{subtitle}</div>', unsafe_allow_html=True)
