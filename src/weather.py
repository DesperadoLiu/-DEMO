import random
import datetime
import streamlit as st

@st.cache_data(ttl=600)  # 每 10 分鐘更新一次模擬數據
def get_weather_data(location: str = "Taipei"):
    """
    展示版：模擬天氣數據，避免 GitHub Pages 的 CORS 限制。
    """
    now = datetime.datetime.now()
    hour = now.hour
    
    # 根據小時模擬溫度 (清晨涼，下午熱)
    if 5 <= hour < 11:
        base_temp = 22
    elif 11 <= hour < 17:
        base_temp = 28
    elif 17 <= hour < 22:
        base_temp = 24
    else:
        base_temp = 19
        
    temp = base_temp + random.randint(-2, 3)
    
    # 隨機降雨機率與紫外線
    rain_chance = random.choice([0, 10, 20, 30, 40, 60, 80])
    uv_index = random.randint(1, 10)
    
    return {
        "temp": f"{temp}°C",
        "rain": f"{rain_chance}%",
        "uv": str(uv_index)
    }
