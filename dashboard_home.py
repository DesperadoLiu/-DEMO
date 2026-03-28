from __future__ import annotations

from html import escape

import streamlit as st

from src.filters import render_sidebar_filters
from src.session_manager import get_session_limit_status, touch_current_page


# No st.set_page_config here, it's in demo_app.py

touch_current_page('dashboard_home')
# Mock summary for demo
summary = {
    'alert_level': 'healthy',
    'status_label': '系統運作正常 (展示版本)',
    'active_count': 1,
    'max_users': 100,
    'available_slots': 99
}
alert_class = f"usage-{summary['alert_level']}"
status_badge = summary['status_label']

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background: #ffffff !important;
    }
    [data-testid="stMain"] {
        background: #ffffff !important;
    }
    .block-container {
        background: #ffffff !important;
    }
    .home-summary-wrap {
        display: grid;
        grid-template-columns: 1.7fr 1fr 1fr;
        gap: 14px;
        margin: 0.6rem 0 1.5rem 0;
    }
    .home-summary-card {
        border-radius: 22px;
        padding: 20px 22px;
        border: 1px solid rgba(90, 67, 53, 0.10);
        box-shadow: 0 12px 28px rgba(70, 49, 38, 0.08);
        background: linear-gradient(180deg, #fffaf5 0%, #ffffff 100%);
    }
    .home-summary-card.usage-healthy {
        border: 1px solid rgba(27, 94, 32, 0.18);
        background: linear-gradient(180deg, #effaf2 0%, #ffffff 100%);
        box-shadow: 0 14px 30px rgba(46, 125, 50, 0.10);
    }
    .home-summary-card.usage-warning {
        border: 1px solid rgba(245, 124, 0, 0.24);
        background: linear-gradient(180deg, #fff7e8 0%, #ffffff 100%);
        box-shadow: 0 14px 30px rgba(245, 124, 0, 0.12);
    }
    .home-summary-card.usage-critical {
        border: 1px solid rgba(198, 40, 40, 0.28);
        background: linear-gradient(180deg, #fff0f0 0%, #ffffff 100%);
        box-shadow: 0 16px 34px rgba(198, 40, 40, 0.16);
    }
    .home-summary-card.usage-critical .home-summary-value,
    .home-summary-card.usage-critical .home-summary-label {
        color: #b71c1c;
    }
    .home-summary-card.usage-warning .home-summary-value,
    .home-summary-card.usage-warning .home-summary-label {
        color: #bf6d00;
    }
    .home-summary-label {
        font-size: 0.82rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        color: #9a6a48;
        margin-bottom: 8px;
    }
    .home-summary-value {
        font-size: 2.25rem;
        font-weight: 900;
        color: #2d241f;
        line-height: 1.05;
    }
    .home-summary-note {
        font-size: 0.98rem;
        line-height: 1.6;
        color: #6a584d;
        margin-top: 8px;
    }
    .home-summary-pill {
        display: inline-block;
        margin-top: 12px;
        padding: 6px 12px;
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 800;
        letter-spacing: 0.03em;
        background: rgba(255, 255, 255, 0.84);
        border: 1px solid rgba(90, 67, 53, 0.10);
        color: #4b3425;
    }
    .home-section-title {
        font-size: 2.1rem;
        font-weight: 800;
        color: #2b211b;
        margin: 2.2rem 0 1.2rem 0;
    }
    .home-card {
        border-radius: 20px;
        padding: 20px 20px 18px 20px;
        border: 1px solid rgba(90, 67, 53, 0.10);
        box-shadow: 0 12px 28px rgba(70, 49, 38, 0.08);
        min-height: 360px;
        position: relative;
        overflow: hidden;
        margin-bottom: 0.85rem;
    }
    .home-card::before {
        content: "";
        position: absolute;
        inset: 0 auto auto 0;
        width: 100%;
        height: 6px;
        background: var(--accent);
    }
    .home-card-badge {
        display: inline-block;
        font-size: 0.8rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        color: var(--accent-deep);
        background: rgba(255, 255, 255, 0.82);
        border: 1px solid rgba(255, 255, 255, 0.9);
        border-radius: 999px;
        padding: 6px 10px;
        margin-bottom: 14px;
    }
    .home-card-title {
        font-size: 1.35rem;
        font-weight: 800;
        color: #2d241f;
        margin-bottom: 10px;
        line-height: 1.3;
    }
    .home-card-body {
        font-size: 1rem;
        line-height: 1.75;
        color: #5e5046;
    }
    .home-card-flag {
        position: absolute;
        top: 16px;
        right: 16px;
        font-size: 0.76rem;
        font-weight: 800;
        letter-spacing: 0.03em;
        border-radius: 999px;
        padding: 6px 10px;
        color: #8a5a00;
        background: rgba(255, 245, 194, 0.96);
        border: 1px solid rgba(240, 193, 49, 0.75);
        box-shadow: 0 8px 16px rgba(224, 168, 0, 0.14);
    }
    .card-overview {
        --accent: linear-gradient(90deg, #3b82f6, #60a5fa);
        --accent-deep: #1d4ed8;
        background: linear-gradient(180deg, #eef6ff 0%, #ffffff 100%);
    }
    .card-supervisor {
        --accent: linear-gradient(90deg, #f59e0b, #fbbf24);
        --accent-deep: #b45309;
        background: linear-gradient(180deg, #fff8eb 0%, #ffffff 100%);
    }
    .card-product {
        --accent: linear-gradient(90deg, #10b981, #34d399);
        --accent-deep: #047857;
        background: linear-gradient(180deg, #effcf6 0%, #ffffff 100%);
    }
    .card-behavior {
        --accent: linear-gradient(90deg, #ec4899, #f472b6);
        --accent-deep: #be185d;
        background: linear-gradient(180deg, #fff4f9 0%, #ffffff 100%);
    }
    .card-admin {
        --accent: linear-gradient(90deg, #6b7280, #9ca3af);
        --accent-deep: #374151;
        background: linear-gradient(180deg, #f6f7f8 0%, #ffffff 100%);
    }
    .card-filter {
        --accent: linear-gradient(90deg, #8b5cf6, #a78bfa);
        --accent-deep: #6d28d9;
        background: linear-gradient(180deg, #f7f4ff 0%, #ffffff 100%);
    }
    .home-nav {
        margin-top: -0.2rem;
        margin-bottom: 1.15rem;
    }
    .home-nav button {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        min-height: 54px;
        padding: 0.9rem 1.1rem;
        border-radius: 18px;
        font-weight: 800;
        box-shadow: 0 12px 24px rgba(121, 85, 61, 0.12);
        transition: all 0.18s ease;
    }
    .home-nav button:hover {
        transform: translateY(-1px);
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title('行銷大數據儀表板')
st.caption('提供整體營運、轄區、商品與消費行為分析，也可從首頁直接查看目前系統使用人數。')

st.markdown(
    f"""
    <div class="home-summary-wrap">
        <div class="home-summary-card {alert_class}">
            <div class="home-summary-label">即時使用狀態</div>
            <div class="home-summary-value">{summary['active_count']} / {summary['max_users']} 人</div>
            <div class="home-summary-note">目前剩餘可用名額 {summary['available_slots']} 個。展示版本已預設永久放行。</div>
            <div class="home-summary-pill">{status_badge}</div>
        </div>
        <div class="home-summary-card">
            <div class="home-summary-label">管理入口</div>
            <div class="home-summary-value">系統管理</div>
            <div class="home-summary-note">展示版本僅提供介面體驗，無實際踢人功能。</div>
        </div>
        <div class="home-summary-card">
            <div class="home-summary-label">服務模式</div>
            <div class="home-summary-value">靜態展示</div>
            <div class="home-summary-note">由 GitHub Pages 託管，無需後端資料庫連線。</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

render_sidebar_filters()


def render_feature_card(
    *,
    column,
    badge: str,
    title: str,
    body: str,
    card_class: str,
    nav_key: str | None = None,
    page_path: str | None = None,
    slow_notice: bool = False,
):
    flag_html = '<div class="home-card-flag">較耗時頁面</div>' if slow_notice else ''
    card_html = (
        f'<div class="home-card {card_class}">'
        f'{flag_html}'
        f'<div class="home-card-badge">{escape(badge)}</div>'
        f'<div class="home-card-title">{escape(title)}</div>'
        f'<div class="home-card-body">{escape(body)}</div>'
        f'</div>'
    )
    with column:
        st.markdown(card_html, unsafe_allow_html=True)
        if page_path and nav_key:
            st.markdown('<div class="home-nav">', unsafe_allow_html=True)
            if st.button(f'前往 {title}', key=nav_key, icon=':material/arrow_forward:', use_container_width=True):
                st.switch_page(page_path)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="home-card-spacer"></div>', unsafe_allow_html=True)


st.markdown('<div class="home-section-title">核心分析模組</div>', unsafe_allow_html=True)

top_cols = st.columns(3)
render_feature_card(
    column=top_cols[0],
    badge='Overview',
    title='整體營運分析',
    body='查看整體營收、來客、客單與趨勢變化，快速掌握目前營運脈動與重要觀察指標。',
    card_class='card-overview',
    nav_key='nav_overview',
    page_path='pages/1_整體營運分析.py',
)
render_feature_card(
    column=top_cols[1],
    badge='Supervisor',
    title='轄區營運分析',
    body='從區域與轄區角度看門市表現，協助主管定位需要追蹤的區域與異常門市。',
    card_class='card-supervisor',
    nav_key='nav_supervisor',
    page_path='pages/2_轄區營運分析.py',
)
render_feature_card(
    column=top_cols[2],
    badge='Product',
    title='商品表現分析',
    body='查看商品營收、銷量、組合與結構，幫助判斷主力商品、弱勢商品與調整方向。',
    card_class='card-product',
    nav_key='nav_product',
    page_path='pages/3_商品表現分析.py',
    slow_notice=True,
)

bottom_cols = st.columns(3)
render_feature_card(
    column=bottom_cols[0],
    badge='Behavior',
    title='消費行為分析',
    body='從交易型態、支付方式與消費行為切入，理解顧客購買模式與支付偏好。',
    card_class='card-behavior',
    nav_key='nav_behavior',
    page_path='pages/4_消費行為分析.py',
    slow_notice=True,
)
render_feature_card(
    column=bottom_cols[1],
    badge='Admin',
    title='系統管理',
    body='查看目前活躍與閒置名額、最後活動時間，必要時可手動踢出名額或清空閒置名額。',
    card_class='card-admin',
    nav_key='nav_admin',
    page_path='pages/5_系統管理.py',
)
render_feature_card(
    column=bottom_cols[2],
    badge='Filters',
    title='共用篩選條件',
    body='所有分析頁皆可透過左側篩選條件控制期間、區域、門市與交易維度。',
    card_class='card-filter',
)
