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
    # 修正：增加 buffer 防止数据过滤过头
    days_map = {"1个月": 35, "3个月": 95, "6个月": 185, "1年": 370, "5年": 1830}

# --- 3. 增强版数据抓取 ---
@st.cache_data(ttl=600)
def fetch_robust_unified_data():
    results = {}
    # 显式设置开始日期，确保抓取完整性
    start_dt = "2020-01-01"
    end_dt = datetime.now().strftime('%Y-%m-%d')
    
    for name, ticker in TICKERS.items():
        try:
            # 强制使用 download 并指定 start/end
            df = yf.download(ticker, start=start_dt, end=end_dt, interval="1d", progress=False)
            
            if not df.empty and len(df) > 5:
                # 兼容处理：yfinance 返回的可能是 MultiIndex
                if isinstance(df.columns, pd.MultiIndex):
                    s = df['Close'][ticker]
                else:
                    s = df['Close']
                
                s = s.dropna()
                
                # 数值修正
                if ticker == "^TNX":
                    s = s / 10
                
                results[name] = {
                    "current": float(s.iloc[-1]),
                    "prev": float(s.iloc[-2]),
                    "history": s
                }
            else:
                st.error(f"❌ {name} 数据抓取量不足，请检查网络。")
        except Exception as e:
            st.error(f"抓取 {name} 失败: {e}")
    return results

# --- 4. 渲染 ---
st.title("🛡️ 全球宏观因子同步走势看板")
st.caption(f"更新于: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')} (北京时间) | 稳定趋势修复版")

data = fetch_robust_unified_data()

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
    
    # 关键修正：统一时间切片
    # 取最晚的时间点作为终点，往前推 days_map 里的天数
    latest_date = max([val['history'].index[-1] for val in data.values()])
    cutoff_date = latest_date - timedelta(days=days_map[lookback])
    
    colors = ['#26a69a', '#2962ff', '#787b86', '#ef5350']

    for i, name in enumerate(names):
        s = data[name]['history']
        df_p = s[s.index >= cutoff_date]
        
        # 如果切完没数据了，放宽限制
        if df_p.empty:
            df_p = s.tail(30) 

        fig.add_trace(go.Scatter(
            x=df_p.index, y=df_p.values, 
            line=dict(width=2.5, color=colors[i]),
            name=name,
            connectgaps=True # 自动连接缺失的点
        ), row=i+1, col=1)

    # 布局
    fig.update_layout(height=1000, showlegend=False, template='plotly_white', hovermode="x unified")
    fig.update_yaxes(side="right", autorange=True, zeroline=False, showgrid=True, gridcolor='#eeeeee')
    
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
    st.warning("⚠️ 数据正在重新加载中，请稍后刷新...")

st.markdown("---")
st.markdown("💡 **蚂蚁和帅仔人生无限公司** | 趋势已修复，已强制拉取 2020 年至今的完整数据链。")
