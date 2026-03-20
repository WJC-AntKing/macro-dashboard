import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from fredapi import Fred
from datetime import datetime, timedelta

# --- 1. 基础配置与时区处理 ---
st.set_page_config(page_title="宏观风险哨兵 | 蚂蚁和帅仔", layout="wide")
beijing_time = datetime.utcnow() + timedelta(hours=8)

# 自定义 CSS 样式：优化卡片和间距
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stMetricValue"] { font-size: 24px; font-weight: 700; }
    .plot-container { border: 1px solid #f0f2f6; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# 安全获取 API Key
try:
    fred_key = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=fred_key)
except Exception:
    st.error("❌ 未在 Secrets 中检测到 FRED_API_KEY，请检查 Streamlit 后台配置。")
    st.stop()

# 核心指标定义 (FRED ID)
# DCOILBRENTEU: 原油 | DGS10: 10Y美债 | DTWEXAFEGS: 美元指数 | NASDAQ100: 纳指
FRED_TICKERS = {
    "布伦特原油 ($)": "DCOILBRENTEU",
    "10Y美债收益率 (%)": "DGS10",
    "美元指数 (DXY)": "DTWEXAFEGS", 
    "纳斯达克100 (指数)": "NASDAQ100"
}

# --- 2. 侧边栏配置 ---
with st.sidebar:
    st.header("⚙️ 监控配置")
    st.write("设置触发传导链警报的红线：")
    oil_limit = st.slider("原油预警线 ($)", 70, 150, 100)
    bond_limit = st.slider("10Y美债预警线 (%)", 3.0, 6.0, 4.5)
    
    st.divider()
    st.subheader("📅 时间轴范围")
    lookback = st.radio("查看历史长度", ["1个月", "3个月", "6个月", "1年", "5年"], index=2)
    days_map = {"1个月": 30, "3个月": 90, "6个月": 180, "1年": 365, "5年": 1825}

# --- 3. 高效数据抓取函数 ---
@st.cache_data(ttl=3600)
def fetch_all_data():
    results = {}
    for name, code in FRED_TICKERS.items():
        try:
            # 抓取自2020年以来的所有数据，确保回溯可用
            s = fred.get_series(code, observation_start='2020-01-01').dropna()
            if not s.empty:
                results[name] = {
                    "current": s.iloc[-1],
                    "prev": s.iloc[-2],
                    "history": s
                }
        except Exception as e:
            st.warning(f"数据源暂时无法获取 {name}: {e}")
    return results

# --- 4. 界面渲染 ---
st.title("🛡️ 全球宏观因子同步走势看板")
st.caption(f"蚂蚁和帅仔人生无限公司 | 更新于: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间)")

data = fetch_all_data()

if data:
    # 顶部指标快照
    cols = st.columns(4)
    names = list(data.keys())
    for i in range(4):
        name = names[i]
        val = data[name]
        delta = val['current'] - val['prev']
        # 自动判断涨跌颜色 (yfinance风格：绿涨红跌可在此处通过CSS控制，metric默认是绿正红负)
        cols[i].metric(name, f"{val['current']:.2f}", f"{delta:.2f}")

    st.divider()

    # 核心：纵向对齐的多子图看板
    st.subheader(f"🕵️ 多因子时间轴对齐图 (回溯: {lookback})")
    
    # 建立 4行1列 的画布，共享 X 轴
    fig = make_subplots(
        rows=4, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.04, # 子图间距
        subplot_titles=names
    )

    # 确定时间切片
    cutoff_date = data[names[0]]['history'].index[-1] - timedelta(days=days_map[lookback])

    # 循环添加 4 条曲线
    colors = ['#26a69a', '#2962ff', '#787b86', '#ef5350'] # 绿、蓝、灰、红
    for i, name in enumerate(names):
        s = data[name]['history']
        df_plot = s[s.index >= cutoff_date]
        
        fig.add_trace(
            go.Scatter(
                x=df_plot.index, 
                y=df_plot.values, 
                name=name,
                fill='tozeroy', # 面积图
                line=dict(width=2, color=colors[i]),
                hovertemplate='%{x|%Y-%m-%d}<br>数值: %{y:.2f}<extra></extra>'
            ),
            row=i+1, col=1
        )

    # 统一布局优化
    fig.update_layout(
        height=1000, # 足够高才能看清4张图
        showlegend=False,
        template='plotly_white',
        hovermode="x unified", # 跨图对齐悬停线 (灵魂功能)
        margin=dict(l=20, r=20, t=40, b=20)
    )
    
    # 将 Y 轴刻度移到右边，不遮挡曲线起点
    fig.update_yaxes(side="right", tickfont=dict(size=10))
    fig.update_xaxes(showgrid=False)
    
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # --- 5. 传导逻辑检测 ---
    st.subheader("🔗 传导链逻辑检测")
    
    oil_val = data["布伦特原油 ($)"]["current"]
    bond_val = data["10Y美债收益率 (%)"]["current"]
    
    # 逻辑开关
    oil_triggered = oil_val > oil_limit
    bond_triggered = bond_val > bond_limit

    l_col1, l_col2, l_col3, l_col4 = st.columns(4)
    
    # 使用 st.status 实现动态 UI
    with l_col1:
        with st.status("1. 石油供给风险", state="error" if oil_triggered else "complete"):
            st.write(f"当前: ${oil_val:.2f} (线: {oil_limit})")
            
    with l_col2:
        with st.status("2. 通胀风险预警", state="error" if oil_triggered else "complete"):
            st.write("能源价格 -> CPI/PCE 传导")

    with l_col3:
        with st.status("3. 货币紧缩压力", state="error" if bond_triggered else "complete"):
            st.write(f"10Y美债: {bond_val:.2f}% (线: {bond_limit})")

    with l_col4:
        with st.status("4. 估值泡沫风险", state="error" if bond_triggered else "complete"):
            st.write("分母端上移，高估值资产风险")

# 页脚
st.markdown("---")
st.markdown("💡 **操作指南**：在任意一张图上**拖动鼠标左键**可局部放大，**双击**恢复。4张图会同步移动。")
