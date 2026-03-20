import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from fredapi import Fred
from datetime import datetime, timedelta

# --- 1. 基础配置 ---
st.set_page_config(page_title="宏观风险哨兵 | 蚂蚁和帅仔", layout="wide")
beijing_time = datetime.utcnow() + timedelta(hours=8)

# 安全获取 FRED API Key
try:
    fred_key = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=fred_key)
except Exception:
    st.error("❌ 未在 Secrets 中检测到 FRED_API_KEY，请检查配置。")
    st.stop()

# 使用最稳的 FRED 官方代码
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
    # 转换为大约的交易日行数
    rows_map = {"1个月": 22, "3个月": 66, "6个月": 132, "1年": 252, "5年": 1260}

# --- 3. 稳健数据抓取 ---
@st.cache_data(ttl=3600)
def fetch_fred_stable_data():
    results = {}
    for name, code in FRED_TICKERS.items():
        try:
            # 抓取长线数据，FRED 接口非常稳定
            s = fred.get_series(code, observation_start='2020-01-01').dropna()
            if not s.empty:
                results[name] = {
                    "current": float(s.iloc[-1]),
                    "prev": float(s.iloc[-2]),
                    "history": s
                }
        except Exception as e:
            st.error(f"FRED 数据抓取失败 ({name}): {e}")
    return results

# --- 4. 界面渲染 ---
st.title("🛡️ 宏观因子同步看板 (FRED 官方稳定版)")
st.caption(f"数据源: St. Louis Fed | 更新时间: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京)")

data = fetch_fred_stable_data()

if data and len(data) == 4:
    # 1. 指标卡片
    cols = st.columns(4)
    names = list(data.keys())
    for i in range(4):
        n = names[i]
        val = data[n]
        delta = val['current'] - val['prev']
        # 美债在 FRED 里已经是 4.3 这种格式，无需再除以 10
        cols[i].metric(n, f"{val['current']:.2f}", f"{delta:.2f}")

    st.divider()

    # 2. 纵向对齐看板
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.06, subplot_titles=names)
    colors = ['#26a69a', '#2962ff', '#787b86', '#ef5350']

    for i, name in enumerate(names):
        s = data[name]['history']
        
        # 核心：使用 tail(N) 确保无论数据滞后几天，都能画出线
        df_plot = s.tail(rows_map[lookback])
        
        fig.add_trace(go.Scatter(
            x=df_plot.index, 
            y=df_plot.values, 
            line=dict(width=2.5, color=colors[i]),
            name=name,
            connectgaps=True
        ), row=i+1, col=1)

    # 布局优化
    fig.update_layout(height=1000, showlegend=False, template='plotly_white', hovermode="x unified")
    fig.update_yaxes(side="right", autorange=True, zeroline=False, showgrid=True, gridcolor='#eeeeee')
    
    st.plotly_chart(fig, use_container_width=True)

    # 3. 传导逻辑
    st.divider()
    oil_v, bond_v = data["布伦特原油 ($)"]["current"], data["10Y美债收益率 (%)"]["current"]
    l_cols = st.columns(4)
    l_cols[0].status("1. 石油风险", state="error" if oil_v > oil_limit else "complete")
    l_cols[1].status("2. 通胀风险", state="error" if oil_v > oil_limit else "complete")
    l_cols[2].status("3. 流动性收紧", state="error" if oil_v > oil_limit or bond_v > bond_limit else "complete")
    l_cols[3].status("4. 估值下修", state="error" if bond_v > bond_limit else "complete")

else:
    st.warning("⚠️ 正在尝试连接 FRED 数据库，请确保 API Key 正确且网络通畅。")

st.markdown("---")
st.markdown("💡 **蚂蚁和帅仔人生无限公司** | 切换至美联储 FRED 物理专线，彻底告别 yfinance 的 IP 封锁问题。")
