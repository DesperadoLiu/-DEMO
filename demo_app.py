from __future__ import annotations

import uuid
import datetime

import streamlit as st

st.set_page_config(
    page_title="鬍鬚張|行企部|大數據儀表板虛擬展示",
    page_icon=':bar_chart:',
    layout='wide',
)


# Demo mode - Always granted
session_state = {
    "granted": True,
    "active_count": 1,
    "max_users": 100
}

def render_sidebar_header():
    from src.weather import get_weather_data
    
    weather = get_weather_data("Taipei")
    
    if weather:
        temp = weather["temp"]
        rain = weather["rain"]
        uv_val = weather["uv"]
    else:
        temp = "26°C"
        rain = "20%"
        uv_val = "1"
    
    now = datetime.datetime.now()
    date_str = now.strftime("%m月%d日")
    days = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday_str = days[now.weekday()]

    import streamlit.components.v1 as components
    with st.sidebar:
        components.html(f"""
        <style>
            .sidebar-card {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: rgba(255, 255, 255, 0.15);
                border-radius: 18px;
                padding: 18px 12px;
                border: 1px solid rgba(255,255,255,0.3);
                text-align: center;
                color: #3f332b;
                box-shadow: 0 4px 15px rgba(31, 38, 135, 0.05);
                backdrop-filter: blur(8px);
                -webkit-backdrop-filter: blur(8px);
                margin: 0;
            }}
            #sidebar-clock {{
                margin: 0;
                font-size: 38px;
                font-weight: 850;
                letter-spacing: -1.5px;
                line-height: 1;
            }}
            .sidebar-date {{
                font-size: 14px;
                font-weight: 500;
                opacity: 0.85;
                margin-top: 6px;
            }}
            .sidebar-weather {{
                display: flex;
                justify-content: space-around;
                align-items: center;
                font-size: 13px;
                font-weight: 700;
                margin-top: 15px;
            }}
            @media (max-width: 320px) {{
                #sidebar-clock {{ font-size: 30px; }}
                .sidebar-date {{ font-size: 12px; }}
                .sidebar-weather {{ font-size: 11px; }}
            }}
        </style>
        <div class="sidebar-card">
            <h1 id="sidebar-clock">00:00:00</h1>
            <div class="sidebar-date">{date_str} {weekday_str}</div>
            <div class="sidebar-weather">
                <div title="現在溫度">溫 {temp}</div>
                <div title="降雨機率">雨 {rain}</div>
                <div title="紫外線指數">紫 {uv_val}</div>
            </div>
        </div>
        <script>
            function updateSidebarClock() {{
                const now = new Date();
                const timeString = now.getHours().toString().padStart(2, '0') + ':' + 
                                 now.getMinutes().toString().padStart(2, '0') + ':' + 
                                 now.getSeconds().toString().padStart(2, '0');
                const el = document.getElementById('sidebar-clock');
                if (el) el.innerText = timeString;
            }}
            setInterval(updateSidebarClock, 1000);
            updateSidebarClock();
        </script>
        """, height=165)

st.markdown(
    """
    <style>
    [data-testid="stAppViewContainer"] {
        background: #ffffff !important;
    }
    [data-testid="stMain"] {
        background: #ffffff !important;
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #e3ddd7 0%, #d6cec6 100%) !important;
        border-right: 1px solid rgba(63, 51, 43, 0.16);
    }
    [data-testid="stSidebarContent"] {
        background: transparent !important;
    }
    [data-testid="stSidebarNav"] {
        color: #3f332b !important;
    }
    [data-testid="stSidebarNav"] a {
        color: #3f332b !important;
    }
    [data-testid="stSidebarNav"] a:hover {
        background: rgba(207, 192, 178, 0.38) !important;
    }
    [data-testid="stSidebarNav"] a[aria-current="page"] {
        background: #cfc0b2 !important;
        color: #2f261f !important;
        font-weight: 800 !important;
    }
    [data-testid="stSidebarHeader"] {
        padding-top: 0.5rem !important;
        padding-bottom: 0rem !important;
        min-height: 0px !important;
    }
    @media (max-width: 768px) {
        [data-testid="stSidebarContent"] {
            padding-top: 1rem !important;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

pages = {
    "導覽": [
        st.Page("dashboard_home.py", title="行銷大數據儀表板", icon=":material/home:", default=True),
        st.Page("pages/1_整體營運分析.py", title="營業現況分析版", icon=":material/analytics:"),
        st.Page("pages/2_轄區營運分析.py", title="區域現況分析版", icon=":material/map:"),
        st.Page("pages/3_商品表現分析.py", title="商品表現分析", icon=":material/inventory_2:"),
        st.Page("pages/4_消費行為分析.py", title="消費行為分析", icon=":material/analytics:"),
        st.Page("pages/5_系統管理.py", title="系統管理", icon=":material/admin_panel_settings:"),
    ]
}

render_sidebar_header()
navigation = st.navigation(pages, position="sidebar")
navigation.run()
