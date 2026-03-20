import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime, timedelta

# --- 1. 基础配置 ---
st.set_page_config(page_title="宏观风险哨兵 | 蚂蚁和帅仔", layout="wide")
beijing_time = datetime.utcnow() + timedelta(hours=8)

# 统一实时源代码
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
    # 将时间跨度转化为大约需要的交易日行数
    rows_map = {"1个月": 22, "3个月": 66, "6个月": 132, "1年": 252, "5年": 1260}

# --- 3. 数据抓取（增加重试和多索引兼容） ---
@st.cache_data(ttl=600)
def fetch_final_data():
    results = {}
    for name, ticker in TICKERS.items():
        try:
            # 获取 5 年数据，确保历史充足
            df = yf.download(ticker, period="5y", interval="1d", progress=False)
            if not df.empty:
                # 兼容 yfinance 多级索引格式
                if isinstance(df.columns, pd.MultiIndex):
                    s = df['Close'][ticker]
                else:
                    s = df['Close']
                
                s = s.dropna()
                if ticker == "^TNX": s = s / 10
                
                results[name] = {
                    "current": float(s.iloc[-1]),
                    "prev": float(s.iloc[-2]),
                    "history": s
                }
        except:
            st.error(f"无法获取 {name} 数据，请刷新页面重试。")
    return results

# --- 4. 界面渲染 ---
st.title("🛡️ 全球宏观因子同步走势看板")
st.caption(f"更新于: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间) | V1.9 稳定渲染版")

data = fetch_final_data()

if data and len(data) == 4:
    # 指标卡片
    cols = st.columns(4)
    names = list(data.keys())
    for i in range(4):
        n = names[i]
        val = data[n]
        delta = val['current'] - val['prev']
        cols[i].metric(n, f"{val['current']:.2f}", f"{delta:.2f}")

    st.divider()

    # 纵向对齐看板
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.06, subplot_titles=names)
    colors = ['#26a69a', '#2962ff', '#787b86', '#ef5350']

    for i, name in enumerate(names):
        s = data[name]['history']
        
        # --- 核心修复：直接按行数截取数据，不再计算日期 ---
        # 这样无论时区如何，都能保证取到最近 N 行数据，不会变成一个点
        needed_rows = rows_map[lookback]
        df_plot = s.tail(needed_rows)
        
        fig.add_trace(go.Scatter(
            x=df_plot.index, 
            y=df_plot.values, 
            line=dict(width=2.5, color=colors[i]),
            name=name,
            connectgaps=True
        ), row=i+1, col=1)

    # 布局
    fig.update_layout(height=1000, showlegend=False, template='plotly_white', hovermode="x unified")
    fig.update_yaxes(side="right", autorange=True, zeroline=False, showgrid=True, gridcolor='#eeeeee')
    # 彻底关闭范围选择器，防止干扰
    fig.update_xaxes(rangeslider_visible=False)
    
    st.plotly_chart(fig, use_container_width=True)

    # 5. 传导逻辑
    st.divider()
    oil_v, bond_v = data["布伦特原油 ($)"]["current"], data["10Y美债收益率 (%)"]["current"]
    l_cols = st.columns(4)
    l_cols[0].status("1. 石油风险", state="error" if oil_v > oil_limit else "complete")
    l_cols[1].status("2. 通胀风险", state="error" if oil_v > oil_limit else "complete")
    l_cols[2].status("3. 流动性收紧", state="error" if oil_v > oil_limit or bond_v > bond_limit else "complete")
    l_cols[3].status("4. 估值下修", state="error" if bond_v > bond_limit else "complete")

else:
    st.info("🔄 数据源响应中，请稍等...")

st.markdown("---")
st.markdown("💡 **蚂蚁和帅仔人生无限公司** | 索引定位技术已上线，趋势线现已强制锁定并回归。")
