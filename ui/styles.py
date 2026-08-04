from __future__ import annotations

import streamlit as st


def apply_global_styles(primary: str = "#B91C1C", secondary: str = "#111827") -> None:
    st.markdown(
        f"""
        <style>
        :root {{
          --pm-primary: {primary};
          --pm-secondary: {secondary};
          --pm-muted: #6B7280;
          --pm-surface: #FFFFFF;
          --pm-border: #E5E7EB;
        }}
        .stApp {{ background: #F7F8FA; }}
        [data-testid="stSidebar"] {{ background: #111827; }}
        [data-testid="stSidebar"] * {{ color: #F9FAFB; }}
        [data-testid="stSidebar"] .stButton button {{
          border: 1px solid rgba(255,255,255,.15);
          background: rgba(255,255,255,.06);
        }}
        .pm-brand {{
          padding: 10px 0 18px 0;
          border-bottom: 1px solid rgba(255,255,255,.15);
          margin-bottom: 14px;
        }}
        .pm-brand-title {{ font-size: 1.15rem; font-weight: 800; letter-spacing: .02em; }}
        .pm-brand-version {{ color: #D1D5DB; font-size: .78rem; }}
        .pm-page-title {{
          font-size: 2rem; font-weight: 850; color: var(--pm-secondary);
          letter-spacing: -.03em; margin: 0 0 .2rem 0;
        }}
        .pm-page-subtitle {{ color: var(--pm-muted); margin-bottom: 1.25rem; }}
        .pm-card {{
          background: var(--pm-surface); border: 1px solid var(--pm-border);
          border-radius: 14px; padding: 18px; box-shadow: 0 5px 18px rgba(17,24,39,.045);
          margin-bottom: 12px;
        }}
        .pm-kicker {{ color: var(--pm-primary); font-weight: 750; font-size: .78rem; text-transform: uppercase; letter-spacing: .08em; }}
        .pm-number {{ font-size: 1.75rem; font-weight: 850; color: var(--pm-secondary); }}
        .pm-label {{ color: var(--pm-muted); font-size: .86rem; }}
        .pm-badge {{
          display: inline-block; border-radius: 999px; padding: 4px 9px;
          background: #FEE2E2; color: #991B1B; font-size: .75rem; font-weight: 750;
        }}
        .pm-badge-muted {{ background: #E5E7EB; color: #374151; }}
        .pm-badge-good {{ background: #DCFCE7; color: #166534; }}
        .pm-player-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; }}
        .pm-player-name {{ font-weight: 800; color: var(--pm-secondary); font-size: 1.05rem; }}
        .pm-player-meta {{ color: var(--pm-muted); font-size: .82rem; }}
        .stButton > button[kind="primary"] {{
          background: var(--pm-primary); border-color: var(--pm-primary); color:white;
        }}
        div[data-testid="stMetric"] {{
          background:white; border:1px solid var(--pm-border); border-radius:12px; padding:12px;
        }}
        div[data-testid="stForm"] {{
          background:white; border:1px solid var(--pm-border); border-radius:14px; padding:16px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str | None = None) -> None:
    st.markdown(f'<div class="pm-page-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="pm-page-subtitle">{subtitle}</div>', unsafe_allow_html=True)
