from __future__ import annotations

from html import escape
from io import BytesIO

import pandas as pd
import streamlit as st


CARD_BORDER = '#dbe7ff'
CARD_BG = '#ffffff'
SECTION_TEXT = '#14213d'
CORE_CARD_BG = 'linear-gradient(180deg, #f8fbff 0%, #eef6ff 100%)'
CORE_CARD_BORDER = '#b9d5ff'
COMPARE_CARD_BG = 'linear-gradient(180deg, #ffffff 0%, #f7fbff 100%)'
COMPARE_CARD_BORDER = '#d3e4ff'
FONT_STACK = "'Segoe UI', 'Microsoft JhengHei', sans-serif"


def apply_page_style():
    st.markdown(
        f"""
        <style>
        html, body, [class*='css'] {{
            font-family: {FONT_STACK};
            background: #ffffff;
            color: #14213d;
        }}
        .stApp {{
            background: #ffffff;
        }}
        [data-testid='stAppViewContainer'] {{
            background: #ffffff;
        }}
        [data-testid='stHeader'] {{
            background: rgba(255, 255, 255, 0.92);
        }}
        .block-container {{
            padding-top: 2.75rem;
            padding-bottom: 2.25rem;
        }}
        div[data-testid='stHorizontalBlock'] {{
            gap: 0.9rem;
        }}
        div[data-testid='stMetric'] {{
            background: {CARD_BG};
            border: 1px solid #d6e4ff;
            border-radius: 16px;
            padding: 0.95rem 1rem;
            min-height: 118px;
            box-shadow: 0 4px 14px rgba(92, 61, 46, 0.05);
        }}
        div[data-testid='stMetricLabel'] {{
            font-weight: 700;
            margin-bottom: 0.4rem;
        }}
        div[data-testid='stMetricLabel'] p {{
            font-size: 0.95rem;
        }}
        div[data-testid='stMetricValue'] {{
            font-size: 2rem;
            line-height: 1.1;
        }}
        .codex-kpi-card {{
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            border-radius: 20px;
            padding: 1.05rem 1.15rem;
            min-height: 164px;
            box-shadow: 0 14px 30px rgba(29, 78, 216, 0.10);
        }}
        .codex-kpi-card.core {{
            background: {CORE_CARD_BG};
            border: 1px solid {CORE_CARD_BORDER};
            box-shadow: 0 16px 34px rgba(37, 99, 235, 0.12);
        }}
        .codex-kpi-card.compare {{
            background: {COMPARE_CARD_BG};
            border: 1px solid {COMPARE_CARD_BORDER};
            box-shadow: 0 12px 26px rgba(59, 130, 246, 0.08);
        }}
        .codex-kpi-card.compare.positive {{
            background: linear-gradient(180deg, #f4fff7 0%, #dcfce7 100%);
            border-color: #86efac;
            box-shadow: 0 14px 30px rgba(22, 163, 74, 0.14);
        }}
        .codex-kpi-card.compare.negative {{
            background: linear-gradient(180deg, #fff7f7 0%, #fee2e2 100%);
            border-color: #fca5a5;
            box-shadow: 0 14px 30px rgba(220, 38, 38, 0.14);
        }}
        .codex-kpi-card.compare.neutral {{
            background: {COMPARE_CARD_BG};
        }}
        .codex-kpi-label {{
            color: {SECTION_TEXT};
            font-size: 0.92rem;
            font-weight: 800;
            line-height: 1.45;
            min-height: 2.8em;
            margin-bottom: 0.7rem;
            word-break: keep-all;
        }}
        .codex-kpi-card.compare .codex-kpi-label {{
            color: #31507a;
        }}
        .codex-kpi-card.compare.positive .codex-kpi-label {{
            color: #166534;
        }}
        .codex-kpi-card.compare.negative .codex-kpi-label {{
            color: #b91c1c;
        }}
        .codex-kpi-value {{
            color: #0f172a;
            font-size: clamp(2.1rem, 2.4vw, 2.7rem);
            font-weight: 900;
            line-height: 1;
            letter-spacing: -0.03em;
            white-space: nowrap;
            word-break: normal;
            overflow-wrap: normal;
            font-variant-numeric: tabular-nums;
        }}
        .codex-kpi-card.compare .codex-kpi-value {{
            color: #1d4ed8;
        }}
        .codex-kpi-card.compare.positive .codex-kpi-value {{
            color: #15803d;
        }}
        .codex-kpi-card.compare.negative .codex-kpi-value {{
            color: #dc2626;
        }}
        .codex-kpi-sub {{
            margin-top: 0.7rem;
            font-size: 0.84rem;
            line-height: 1.55;
            font-weight: 700;
        }}
        .codex-kpi-sub.neutral {{ color: #475569; }}
        .codex-kpi-sub.positive {{ color: #16a34a; }}
        .codex-kpi-sub.negative {{ color: #dc2626; }}
        .codex-panel {{
            background: linear-gradient(180deg, #ffffff 0%, #f3f8ff 100%);
            border: 1px solid #c7ddff;
            border-radius: 16px;
            padding: 0.95rem 1.05rem;
            margin-bottom: 1.05rem;
            color: {SECTION_TEXT};
            font-size: 0.98rem;
            line-height: 1.45;
        }}
        .codex-alert {{
            background: linear-gradient(180deg, #fffbea 0%, #fff3c4 100%);
            border: 1px solid #f5d46b;
            border-left: 6px solid #e0a800;
            border-radius: 16px;
            padding: 1rem 1.05rem;
            margin: 0.3rem 0 1rem 0;
            color: #6b4f00;
            font-size: 0.98rem;
            line-height: 1.55;
            box-shadow: 0 10px 22px rgba(224, 168, 0, 0.10);
        }}
        .codex-section {{
            margin-top: 1.15rem;
            margin-bottom: 0.8rem;
            font-size: 1.14rem;
            font-weight: 900;
            color: #1d4ed8;
            letter-spacing: 0.02em;
        }}
        .codex-gap-sm {{ height: 0.35rem; }}
        .codex-gap-md {{ height: 0.8rem; }}
        .codex-gap-lg {{ height: 1.15rem; }}
        div[data-testid='stPlotlyChart'] {{
            background: #ffffff;
            border: 1px solid #d6e4ff;
            border-radius: 18px;
            padding: 0.45rem 0.45rem 0.15rem 0.45rem;
            margin-bottom: 0.2rem;
            box-shadow: 0 12px 28px rgba(37, 99, 235, 0.08);
        }}
        .stDataFrame {{
            border: 1px solid #d6e4ff;
            border-radius: 18px;
            overflow: hidden;
            margin-top: 0.2rem;
            box-shadow: 0 10px 24px rgba(37, 99, 235, 0.06);
        }}
        div[data-testid='stCaptionContainer'] p {{
            margin-bottom: 0.35rem;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def section_title(title: str):
    st.markdown(f'<div class="codex-section">{escape(title)}</div>', unsafe_allow_html=True)


def status_panel(text: str):
    st.markdown(f'<div class="codex-panel">{escape(text)}</div>', unsafe_allow_html=True)


def alert_panel(text: str):
    st.markdown(f'<div class="codex-alert">{escape(text)}</div>', unsafe_allow_html=True)


def content_gap(size: str = 'md'):
    size = size if size in {'sm', 'md', 'lg'} else 'md'
    st.markdown(f'<div class="codex-gap-{size}"></div>', unsafe_allow_html=True)


def render_kpi_card(label: str, value: str, subtext: str | None = None, tone: str = 'neutral', variant: str = 'core'):
    safe_label = escape(label)
    safe_value = escape(value)
    variant = variant if variant in {'core', 'compare'} else 'core'
    tone = tone if tone in {'neutral', 'positive', 'negative'} else 'neutral'
    sub_html = ''
    if subtext:
        safe_subtext = escape(subtext)
        sub_html = f'<div class="codex-kpi-sub {tone}">{safe_subtext}</div>'
    st.markdown(
        f'<div class="codex-kpi-card {variant} {tone}"><div class="codex-kpi-label">{safe_label}</div><div class="codex-kpi-value">{safe_value}</div>{sub_html}</div>',
        unsafe_allow_html=True,
    )


def change_tone(change_value: float | None, positive_is_good: bool = True) -> str:
    if change_value is None or pd.isna(change_value):
        return 'neutral'
    is_positive = change_value >= 0
    if positive_is_good:
        return 'positive' if is_positive else 'negative'
    return 'negative' if is_positive else 'positive'


def change_text(change_value: float | None, compare_label: str, target_date: str | None = None) -> str:
    date_str = f"({target_date})" if target_date else ""
    if change_value is None or pd.isna(change_value):
        return f'與{compare_label}{date_str}比：-' if compare_label else '-'
    arrow = '▲' if change_value >= 0 else '▼'
    return f'與{compare_label}{date_str}比：{arrow} {abs(change_value):.1%}'


def _normalize_export_df(df: pd.DataFrame | None) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame({'訊息': ['目前查無資料']})
    return df.copy()


def excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in sheets.items():
            export_df = _normalize_export_df(df)
            export_df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    output.seek(0)
    return output.getvalue()


def render_export_buttons(base_name: str, excel_sheets: dict[str, pd.DataFrame], csv_df: pd.DataFrame, csv_name: str = '明細'):
    # Export buttons are intentionally disabled, but we keep the shared API stable for page calls.
    return None
