import streamlit as st

def acquire_user_slot():
    return True, 1, 100

def render_session_monitor():
    st.info("展示版本已放寬限制")

def render_waiting_room():
    st.success("歡迎進入展示版")

def touch_current_page(page_name):
    pass

def get_current_active_count():
    return 1

def get_session_limit_status():
    return True, 1, 100
