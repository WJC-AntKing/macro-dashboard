import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta

# 页面基础设置
st.set_page_config(page_title="我们的宏观风险哨兵", layout="wide", initial_sidebar_state="expanded")

# 自定义样式：让看板看起来更专业
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("🛡️ 宏观经济传导逻辑预警")
beijing_time = datetime.utcnow() + timedelta(hours=8)
st.caption(f"数据更新时间: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间) | 专属分析看板")

# --- 侧边栏：预警逻辑配置 ---
with st.sidebar:
    st.header("⚙️ 逻辑阈值设置")
    st.info("当指标超过以下数值时，系统将触发传导链警报")
    oil_limit = st.slider("原油预警线 ($)", 70, 150, 100)
    bond_limit = st.slider("10Y美债预警线 (%)", 3.0, 6.0, 4.5)
    dxy_limit = st.slider("美元指数预警线", 90, 120, 105)

# --- 数据抓取函数 ---
@st.cache_data(ttl=3600) # 缓存数据1小时，避免请求频繁
def fetch_data():
    # 抓取原油、美债收益率、美元指数、纳斯达克
    tickers = {"原油": "BZ=F", "美债10Y": "^TNX", "美元指数": "DX-Y.NYB", "纳指100": "^NDX"}
    data = {}
    for name, ticker in tickers.items():
        val = yf.Ticker(ticker).history(period="2d")['Close']
        data[name] = {"current": val.iloc[-1], "prev": val.iloc[-2]}
    return data

try:
    prices = fetch_data()
    
    # --- 顶层状态卡片 ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("布伦特原油", f"${prices['原油']['current']:.2f}", f"{prices['原油']['current']-prices['原油']['prev']:.2f}")
    col2.metric("10Y美债收益率", f"{prices['美债10Y']['current']/10:.2f}%", f"{(prices['美债10Y']['current']-prices['美债10Y']['prev'])/10:.2f}%")
    col3.metric("美元指数 (DXY)", f"{prices['美元指数']['current']:.2f}", f"{prices['美元指数']['current']-prices['美元指数']['prev']:.2f}")
    col4.metric("纳斯达克100", f"{prices['纳指100']['current']:.0f}", f"{prices['纳指100']['current']-prices['纳指100']['prev']:.0f}")

    # --- 核心逻辑传导推演 ---
    st.divider()
    st.subheader("🔗 风险传导路径状态推演")
    
    # 定义逻辑节点
    oil_risk = prices['原油']['current'] > oil_limit
    bond_risk = prices['美债10Y']['current']/10 > bond_limit
    
    # 模拟传导链条
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
        st.warning("⚠️ 极端预警：当前处于'高油价+高利率'双杀环境，建议增加现金避险。")

except Exception as e:
    st.error(f"数据加载失败，请检查网络或稍后再试。错误: {e}")

# 底部署名
st.markdown("---")
st.markdown("💡 *蚂蚁和帅仔人生无限公司技术支持*")
