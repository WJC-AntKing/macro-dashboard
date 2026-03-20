import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from fredapi import Fred
from datetime import datetime, timedelta

# --- 1. 配置 ---
st.set_page_config(page_title="蚂蚁和帅仔的宏观哨兵", layout="wide")
beijing_time = datetime.utcnow() + timedelta(hours=8)

# 安全获取 API Key
try:
    fred_key = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=fred_key)
except:
    st.error("请在 Streamlit Secrets 中配置 FRED_API_KEY")
    st.stop()

# FRED 指标代码对照表 (这些是全球最稳的数据源)
# DCOILBRENTEU: 布伦特原油 | DGS10: 10年美债 | DTWEXBGS: 美元指数 | NASDAQ100: 纳指
FRED_TICKERS = {
    "布伦特原油": "DCOILBRENTEU",
    "10Y美债收益率": "DGS10",
    "美元指数 (DXY)": "DTWEXAFEGS", 
    "纳斯达克100": "NASDAQ100"
}

# --- 2. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 逻辑预警阈值")
    oil_limit = st.slider("原油预警线 ($)", 70, 150, 100)
    bond_limit = st.slider("10Y美债预警线 (%)", 3.0, 6.0, 4.5)
    st.divider()
    chart_target = st.selectbox("选择观察指标", list(FRED_TICKERS.keys()))

# --- 3. 稳健抓取函数 ---
@st.cache_data(ttl=3600)
def fetch_fred_data():
    data = {}
    for name, code in FRED_TICKERS.items():
        try:
            # 获取最近30天数据确保能拿到最后两个有效交易日
            s = fred.get_series(code).dropna()
            current_val = s.iloc[-1]
            prev_val = s.iloc[-2]
            data[name] = {"current": current_val, "prev": prev_val, "series": s}
        except:
            data[name] = None
    return data

# --- 4. 界面渲染 ---
st.title("🛡️ 宏观传导预警 (FRED 官方源版)")
st.caption(f"数据更新时间: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} | 稳定数据驱动")

results = fetch_fred_data()

if results:
    # 指标卡片
    cols = st.columns(4)
    for i, (name, val) in enumerate(results.items()):
        if val:
            delta = val['current'] - val['prev']
            unit = "%" if "美债" in name else ""
            cols[i].metric(name, f"{val['current']:.2f}{unit}", f"{delta:.2f}{unit}")

    # K线图（FRED主要提供收盘价，所以这里展示丝滑的面积折线图，更适合宏观趋势）
    st.subheader(f"📈 {chart_target} 长期趋势")
    target_series = results[chart_target]['series']
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=target_series.index, y=target_series.values, fill='tozeroy', line_color='#007bff'))
    fig.update_layout(template='plotly_white', height=400, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

    # 5. 传导逻辑
    st.divider()
    oil_val = results['布伦特原油']['current']
    bond_val = results['10Y美债收益率']['current']
    
    c1, c2, c3, c4 = st.columns(4)
    c1.status("1. 石油供给风险", state="error" if oil_val > oil_limit else "complete")
    c2.status("2. 通胀风险上升", state="error" if oil_val > oil_limit else "complete")
    c3.status("3. 紧缩政策预期", state="error" if oil_val > oil_limit or bond_val > bond_limit else "complete")
    c4.status("4. 估值下修预警", state="error" if bond_val > bond_limit else "complete")

st.markdown("---")
st.markdown("💡 **蚂蚁和帅仔人生无限公司** | 数据源: St. Louis Fed (FRED)")
