import streamlit as st

st.title('系統管理 (展示版本)')
st.info('在實際部署環境中，此頁面用於監測同時在線人數、釋放閒置名額以及管理系統狀態。')

col1, col2, col3, col4 = st.columns(4)
col1.metric('目前使用中', 1)
col2.metric('同時上限', 100)
col3.metric('閒置名額', 0)
col4.metric('閒置回收門檻', '無限制')

st.success('✅ 模擬數據運作正常')
st.caption('註：展示版本已移除所有管理權限限制與 Session 監控，僅供體驗 UI 功能。')

with st.expander("查看技術說明"):
    st.markdown("""
    ### 展示技術架構
    - **Frontend**: Streamlit + Plotly
    - **Runtime**: stlite (Pyodide / WebAssembly)
    - **Hosting**: GitHub Pages (Static)
    - **Data Source**: Mock Data Generator (Python)
    """)
