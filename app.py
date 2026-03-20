import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from fredapi import Fred
import yfinance as yf
from datetime import datetime, timedelta

# --- 1. 基础配置 ---
st.set_page_config(page_title="宏观风险哨兵 | 蚂蚁和帅仔", layout="wide")
beijing_time = datetime.utcnow() + timedelta(hours=8)

try:
    fred_key = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=fred_key)
except Exception:
    st.error("❌ 未在 Secrets 中检测到 FRED_API_KEY")
    st.stop()

# 定义混合数据源：FRED优先，yfinance备选
# 这里的Key是显示名，Value是 (FRED代码, yfinance代码)
TICKER_MAP = {
    "布伦特原油 ($)": ("DCOILBRENTEU", "BZ=F"),
    "10Y美债收益率 (%)": ("DGS10", "^TNX"),
    "美元指数 (DXY)": ("DTWEXAFEGS", "DX-Y.NYB"), 
    "纳斯达克100 (指数)": ("NASDAQ100", "^NDX")
}

# --- 2. 侧边栏 ---
with st.sidebar:
    st.header("⚙️ 监控配置")
    oil_limit = st.slider("原油预警线 ($)", 70, 150, 100)
    bond_limit = st.slider("10Y美债预警线 (%)", 3.0, 6.0, 4.5)
    st.divider()
    lookback = st.radio("查看历史长度", ["1个月", "3个月", "6个月", "1年", "5年"], index=2)
    days_map = {"1个月": 30, "3个月": 90, "6个月": 180, "1年": 365, "5年": 1825}

# --- 3. 增强型数据抓取：自动补齐滞后数据 ---
@st.cache_data(ttl=3600)
def fetch_robust_data():
    results = {}
    end_date = datetime.now()
    start_date = end_date - timedelta(days=2000)
    
    for name, (fred_code, yf_code) in TICKER_MAP.items():
        try:
            # 1. 尝试从 FRED 抓取
            s = fred.get_series(fred_code, observation_start='2020-01-01').dropna()
            
            # 2. 如果 FRED 数据太旧（超过3天没更新），尝试用 yfinance 补齐最后几天
            if s.empty or (datetime.now() - s.index[-1]).days > 3:
                yf_data = yf.download(yf_code, start=s.index[-1].strftime('%Y-%m-%d'), progress=False)['Close']
                if not yf_data.empty:
                    # 数值单位转换：美债 yfinance 是 43 格式，需要转为 4.3
                    if name == "10Y美债收益率 (%)":
                        yf_data = yf_data / 10
                    # 合并数据并去重
                    s = pd.concat([s, yf_data]).sort_index()
                    s = s[~s.index.duplicated(keep='last')]
            
            if not s.empty:
                results[name] = {"current": s.iloc[-1], "prev": s.iloc[-2], "history": s}
        except:
            # 最后的保底：完全使用 yfinance
            try:
                s = yf.download(yf_code, start='2020-01-01', progress=False)['Close']
                if name == "10Y美债收益率 (%)": s = s / 10
                results[name] = {"current": s.iloc[-1], "prev": s.iloc[-2], "history": s}
            except: pass
    return results

# --- 4. 渲染 ---
st.title("🛡️ 全球宏观因子同步走势看板")
st.caption(f"更新于: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京) | 混合数据源补齐版")

data = fetch_robust_data()

if data:
    # 顶部卡片
    cols = st.columns(4)
    names = list(data.keys())
    for i in range(4):
        n = names[i]
        cols[i].metric(n, f"{data[n]['current']:.2f}", f"{data[n]['current']-data[n]['prev']:.2f}")

    st.divider()

    # 核心：纵向对齐看板
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.06, subplot_titles=names)
    cutoff_date = datetime.now() - timedelta(days=days_map[lookback])
    colors = ['#26a69a', '#2962ff', '#787b86', '#ef5350']

    for i, name in enumerate(names):
        s = data[name]['history']
        # 统一过滤到用户选择的时间段
        df_p = s[s.index >= cutoff_date]
        
        fig.add_trace(go.Scatter(
            x=df_p.index, y=df_p.values, 
            line=dict(width=2, color=colors[i]),
            name=name
        ), row=i+1, col=1)

    # 布局优化：实现动态缩放
    fig.update_layout(height=1000, showlegend=False, template='plotly_white', hovermode="x unified")
    fig.update_yaxes(side="right", autorange=True, zeroline=False, rangemode='normal')
    
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
st.markdown("💡 **补齐逻辑已激活**：当美联储(FRED)数据滞后时，系统自动切换至交易所(Yahoo Finance)实时源，确保时间轴对齐。")
