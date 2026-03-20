import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
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

# 定义统一的 yfinance 代码
# 布伦特原油: BZ=F | 10Y美债: ^TNX | 美元指数: DX-Y.NYB | 纳指100: ^NDX
TICKERS = {
    "布伦特原油 ($)": "BZ=F",
    "10Y美债收益率 (%)": "^TNX",
    "美元指数 (DXY)": "DX-Y.NYB", 
    "纳斯达克100 (指数)": "^NDX"
}

# --- 2. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 监控配置")
    oil_limit = st.slider("原油预警线 ($)", 70, 150, 100)
    bond_limit = st.slider("10Y美债预警线 (%)", 3.0, 6.0, 4.5)
    st.divider()
    lookback = st.radio("查看历史长度", ["1个月", "3个月", "6个月", "1年", "5年"], index=2)
    days_map = {"1个月": 30, "3个月": 90, "6个月": 180, "1年": 365, "5年": 1825}

# --- 3. 统一高效数据抓取 ---
@st.cache_data(ttl=600) # 每10分钟更新一次，确保及时性
def fetch_unified_data():
    results = {}
    for name, ticker in TICKERS.items():
        try:
            # 抓取足够长的历史数据
            df = yf.download(ticker, period="5y", interval="1d", progress=False)
            if not df.empty:
                s = df['Close']
                # 关键：修正美债显示逻辑 (yfinance 的 ^TNX 43 代表 4.3%)
                if ticker == "^TNX":
                    s = s / 10
                
                results[name] = {
                    "current": float(s.iloc[-1]),
                    "prev": float(s.iloc[-2]),
                    "history": s
                }
        except Exception as e:
            st.warning(f"无法获取 {name} 数据: {e}")
    return results

# --- 4. 界面渲染 ---
st.title("🛡️ 全球宏观因子同步走势看板")
st.caption(f"更新于: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间) | 统一实时数据源 (Yahoo Finance)")

data = fetch_unified_data()

if data:
    # 顶部卡片
    cols = st.columns(4)
    names = list(data.keys())
    for i in range(4):
        n = names[i]
        val = data[n]
        delta = val['current'] - val['prev']
        cols[i].metric(n, f"{val['current']:.2f}", f"{delta:.2f}")

    st.divider()

    # 核心：纵向对齐看板
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.06, subplot_titles=names)
    cutoff_date = data[names[0]]['history'].index[-1] - timedelta(days=days_map[lookback])
    
    # 颜色设置
    colors = ['#26a69a', '#2962ff', '#787b86', '#ef5350']

    for i, name in enumerate(names):
        s = data[name]['history']
        df_p = s[s.index >= cutoff_date]
        
        fig.add_trace(go.Scatter(
            x=df_p.index, y=df_p.values, 
            line=dict(width=2, color=colors[i]),
            name=name
        ), row=i+1, col=1)

    # 布局优化：实现动态缩放，不强制包含0
    fig.update_layout(height=1000, showlegend=False, template='plotly_white', hovermode="x unified")
    
    # 强制所有 Y 轴自动聚焦波动区间，不显示 0 刻度线
    fig.update_yaxes(
        side="right", 
        autorange=True, 
        zeroline=False, 
        showgrid=True, 
        gridcolor='#eeeeee',
        rangemode='normal' # 核心：不强制包含0，实现动态轴缩放
    )
    
    st.plotly_chart(fig, use_container_width=True)

    # 5. 传导逻辑检测
    st.divider()
    oil_v = data["布伦特原油 ($)"]["current"]
    bond_v = data["10Y美债收益率 (%)"]["current"]
    
    l_cols = st.columns(4)
    l_cols[0].status("1. 石油风险", state="error" if oil_v > oil_limit else "complete")
    l_cols[1].status("2. 通胀风险", state="error" if oil_v > oil_limit else "complete")
    l_cols[2].status("3. 流动性收紧", state="error" if oil_v > oil_limit or bond_v > bond_limit else "complete")
    l_cols[3].status("4. 估值下修", state="error" if bond_v > bond_limit else "complete")

st.markdown("---")
st.markdown("💡 **蚂蚁和帅仔人生无限公司** | 已切换至 yfinance 实时统一源，解决数据缺失与断层问题。")
