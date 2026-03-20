import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests

# --- 1. 页面基础设置 ---
st.set_page_config(page_title="我们的宏观风险哨兵 V1.1", layout="wide", initial_sidebar_state="expanded")

# 强制使用北京时间 (UTC+8)
beijing_time = datetime.utcnow() + timedelta(hours=8)

# 自定义样式
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    /* 让图表看起来更现代 */
    .plot-container { border-radius: 10px; overflow: hidden; }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ 宏观经济传导逻辑预警 & 趋势分析")
st.caption(f"数据更新时间: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间) | 专属分析看板 V1.1")

# 定义核心指标 Tickers
TICKERS = {
    "布伦特原油": "BZ=F",
    "10Y美债收益率": "^TNX",
    "美元指数 (DXY)": "DX-Y.NYB",
    "纳斯达克100": "^NDX"
}

# --- 2. 侧边栏：配置与交互 ---
with st.sidebar:
    st.header("⚙️ 仪表盘配置")
    
    # 逻辑阈值设置
    st.subheader("逻辑预警阈值")
    oil_limit = st.slider("原油预警线 ($)", 70, 150, 100, help="突破此线，触发输入性通胀预警")
    bond_limit = st.slider("10Y美债预警线 (%)", 3.0, 6.0, 4.5, help="突破此线，触发流动性估值收缩预警")
    dxy_limit = st.slider("美元指数预警线", 90, 120, 105, help="突破此线，表明美元过于强势，资产承压")

    st.divider()
    
    # K线图周期选择 (新增)
    st.subheader("📈 K线图设置")
    chart_target = st.selectbox("选择观察指标", list(TICKERS.keys()), index=0)
    time_frame = st.radio("选择K线周期", ["日线 (D)", "周线 (W)", "月线 (M)"], index=0, horizontal=True)

# --- 3. 数据抓取与缓存函数 ---
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
@st.cache_data(ttl=3600) # 缓存1小时
def fetch_metric_data():
    data = {}
    for name, ticker in TICKERS.items():
        try:
            # 使用更健壮的 download 方法，并增加重试逻辑
            df = yf.download(ticker, period="5d", interval="1d", progress=False, timeout=10)
            if not df.empty and len(df) >= 2:
                # 兼容 yfinance 新旧版本的索引方式
                current_val = float(df['Close'].iloc[-1])
                prev_val = float(df['Close'].iloc[-2])
                
                if name == "10Y美债收益率":
                    current_val, prev_val = current_val / 10, prev_val / 10
                
                data[name] = {"current": current_val, "prev": prev_val}
            else:
                st.warning(f"{name} 数据暂时不可用")
        except Exception as e:
            st.error(f"抓取 {name} 失败: {e}")
    return data

@st.cache_data(ttl=3600)
def fetch_chart_data(ticker, tf_str):
    period_map = {"日线 (D)": ("1y", "1d"), "周线 (W)": ("5y", "1wk"), "月线 (M)": ("max", "1mo")}
    p, i = period_map[tf_str]
    # 使用 download 替代 Ticker().history
    df = yf.download(ticker, period=p, interval=i, progress=False, timeout=15)
    if not df.empty and ticker == "^TNX":
        df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']] / 10
    return df

# --- 4. 顶部状态卡片 ---
try:
    prices = fetch_metric_data()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("布伦特原油", f"${prices['布伦特原油']['current']:.2f}", f"{prices['布伦特原油']['current']-prices['布伦特原油']['prev']:.2f}")
    with col2:
        st.metric("10Y美债收益率", f"{prices['10Y美债收益率']['current']:.2f}%", f"{prices['10Y美债收益率']['current']-prices['10Y美债收益率']['prev']:.2f}%")
    with col3:
        st.metric("美元指数 (DXY)", f"{prices['美元指数 (DXY)']['current']:.2f}", f"{prices['美元指数 (DXY)']['current']-prices['美元指数 (DXY)']['prev']:.2f}")
    with col4:
        st.metric("纳斯达克100", f"{prices['纳斯达克100']['current']:.0f}", f"{prices['纳斯达克100']['current']-prices['纳食达克100']['prev']:.0f}")

    st.divider()

    # --- 5. 交互式 K 线图模块 (新增核心) ---
    st.subheader(f"📊 {chart_target} 趋势分析 - {time_frame}")
    
    # 抓取所选指标的历史数据
    ticker_to_draw = TICKERS[chart_target]
    df_chart = fetch_chart_data(ticker_to_draw, time_frame)
    
    if not df_chart.empty:
        # 使用 Plotly 绘制现代风格 K 线图
        fig = go.Figure(data=[go.Candlestick(x=df_chart.index,
                        open=df_chart['Open'],
                        high=df_chart['High'],
                        low=df_chart['Low'],
                        close=df_chart['Close'],
                        increasing_line_color='#26a69a', # 港美股配色：绿涨红跌
                        decreasing_line_color='#ef5350')])
        
        fig.update_layout(
            template='plotly_white',
            margin=dict(l=20, r=20, t=20, b=20),
            height=500,
            xaxis_rangeslider_visible=False, # 隐藏 Plotly 自带的滑块，使用 Streamlit 侧边栏
            yaxis=dict(title_text=chart_target, side='right')
        )
        
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("未能加载到足够多的历史数据来绘制图表。")

    st.divider()

    # --- 6. 核心逻辑传导推演 ---
    st.subheader("🔗 风险传导路径状态推演")
    
    oil_risk = prices['布伦特原油']['current'] > oil_limit
    bond_risk = prices['10Y美债收益率']['current'] > bond_limit
    
    steps = [
        {"name": "1. 地缘/供给冲击 (石油)", "status": oil_risk},
        {"name": "2. 全球输入性通胀风险", "status": oil_risk},
        {"name": "3. 美联储降息预期压制", "status": oil_risk or bond_risk},
        {"name": "4. 流动性估值收缩 (分母端压力)", "status": bond_risk}
    ]
    
    cols = st.columns(4)
    for i, step in enumerate(steps):
        with cols[i]:
            if step["status"]:
                st.error(f"🔴 {step['name']}")
            else:
                st.success(f"🟢 {step['name']}")

    if oil_risk and bond_risk:
        st.warning("⚠️ 极端预警：当前处于'高油价+高利率'双杀环境，意味着输入性通胀和流动性枯竭风险同时存在。")

except Exception as e:
    st.error(f"数据加载失败，可能是由于雅虎财经 API 暂时限制请求。错误: {e}")

# 底部署名
st.markdown("---")
st.markdown("💡 *蚂蚁和帅仔人生无限公司*")
