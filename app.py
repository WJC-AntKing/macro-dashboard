import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from fredapi import Fred
from datetime import datetime, timedelta

# --- 1. 基础配置 ---
st.set_page_config(page_title="宏观风险哨兵 | 蚂蚁和帅仔", layout="wide")
beijing_time = datetime.utcnow() + timedelta(hours=8)

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stMetricValue"] { font-size: 24px; font-weight: 700; }
    </style>
    """, unsafe_allow_html=True)

try:
    fred_key = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=fred_key)
except Exception:
    st.error("❌ 未在 Secrets 中检测到 FRED_API_KEY")
    st.stop()

FRED_TICKERS = {
    "布伦特原油 ($)": "DCOILBRENTEU",
    "10Y美债收益率 (%)": "DGS10",
    "美元指数 (DXY)": "DTWEXAFEGS", 
    "纳斯达克100 (指数)": "NASDAQ100"
}

# --- 2. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 监控配置")
    oil_limit = st.slider("原油预警线 ($)", 70, 150, 100)
    bond_limit = st.slider("10Y美债预警线 (%)", 3.0, 6.0, 4.5)
    st.divider()
    lookback = st.radio("查看历史长度", ["1个月", "3个月", "6个月", "1年", "5年"], index=2)
    days_map = {"1个月": 30, "3个月": 90, "6个月": 180, "1年": 365, "5年": 1825}

@st.cache_data(ttl=3600)
def fetch_all_data():
    results = {}
    for name, code in FRED_TICKERS.items():
        try:
            s = fred.get_series(code, observation_start='2020-01-01').dropna()
            if not s.empty:
                results[name] = {"current": s.iloc[-1], "prev": s.iloc[-2], "history": s}
        except: pass
    return results

# --- 3. 渲染 ---
st.title("🛡️ @蚂蚁和帅仔")
st.caption(f"更新于: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间) | 动态轴优化版")

data = fetch_all_data()

if data:
    # 指标卡片
    cols = st.columns(4)
    names = list(data.keys())
    for i in range(4):
        n = names[i]
        cols[i].metric(n, f"{data[n]['current']:.2f}", f"{data[n]['current']-data[n]['prev']:.2f}")

    st.divider()

    # 核心：纵向对齐看板
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.05, subplot_titles=names)
    cutoff_date = data[names[0]]['history'].index[-1] - timedelta(days=days_map[lookback])
    colors = ['#26a69a', '#2962ff', '#787b86', '#ef5350']

    for i, name in enumerate(names):
        s = data[name]['history']
        df_p = s[s.index >= cutoff_date]
        fig.add_trace(go.Scatter(x=df_p.index, y=df_p.values, fill='tozeroy', line=dict(width=2, color=colors[i]), name=name), row=i+1, col=1)

    # --- 关键修改：动态调整纵坐标 ---
    fig.update_layout(height=1000, showlegend=False, template='plotly_white', hovermode="x unified")
    
    # 强制所有子图的 Y 轴不从 0 开始，自动聚焦波动区间
    fig.update_yaxes(
        side="right", 
        autorange=True,      # 核心设置：自动根据数据极值缩放
        fixedrange=False, 
        zeroline=False,      # 不强制画出 0 刻度线
        showgrid=True, 
        gridcolor='#eeeeee'
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # 4. 逻辑检测
    st.divider()
    oil_v, bond_v = data["布伦特原油 ($)"]["current"], data["10Y美债收益率 (%)"]["current"]
    l_cols = st.columns(4)
    l_cols[0].status("1. 石油风险", state="error" if oil_v > oil_limit else "complete")
    l_cols[1].status("2. 通胀风险", state="error" if oil_v > oil_limit else "complete")
    l_cols[2].status("3. 流动性收紧", state="error" if oil_v > oil_limit or bond_v > bond_limit else "complete")
    l_cols[3].status("4. 估值下修", state="error" if bond_v > bond_limit else "complete")

st.markdown("---")
st.markdown("💡 **蚂蚁和帅仔人生无限公司** | 动态坐标轴已激活：图表会自动放大近期波动。")
