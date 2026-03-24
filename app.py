import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from fredapi import Fred
import yfinance as yf
from datetime import datetime, timedelta

# --- [模块 1: 基础配置与 CSS] ---
st.set_page_config(page_title="蚂蚁和帅仔的私人终端", layout="wide")
beijing_time = datetime.utcnow() + timedelta(hours=8)

st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #f0f2f6; }
    [data-testid="stMetricValue"] { font-size: 28px; font-weight: 700; color: #1e1e1e; }
    .stStatus { border-radius: 8px; }
    </style>
    """, unsafe_allow_html=True)

try:
    fred_key = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=fred_key)
except Exception:
    st.error("❌ 未在 Secrets 中检测到 FRED_API_KEY")
    st.stop()

# --- [模块 2: 侧边栏导航] ---
with st.sidebar:
    st.title("💼 私人交易终端")
    page = st.radio("功能切换", ["🛡️ 宏观哨兵", "💰 资产配置"])
    st.divider()
    
    if page == "🛡️ 宏观哨兵":
        st.header("⚙️ 监控配置")
        oil_limit = st.slider("原油预警线 ($)", 70, 150, 100)
        bond_limit = st.slider("10Y美债预警线 (%)", 3.0, 6.0, 4.5)
        lookback = st.radio("历史跨度", ["1个月", "3个月", "6个月", "1年", "5年"], index=2)
        rows_map = {"1个月": 22, "3个月": 66, "6个月": 132, "1年": 252, "5年": 1260}

# --- [模块 3: 宏观哨兵逻辑] ---
if page == "🛡️ 宏观哨兵":
    st.title("🛡️ 宏观经济传导预警")
    st.caption(f"数据源: FRED | 更新时间: {beijing_time.strftime('%Y-%m-%d %H:%M:%S')}")

    FRED_TICKERS = {
        "布伦特原油 ($)": "DCOILBRENTEU",
        "10Y美债收益率 (%)": "DGS10",
        "美元指数 (DXY)": "DTWEXAFEGS", 
        "纳斯达克100 (指数)": "NASDAQ100"
    }

    @st.cache_data(ttl=3600)
    def fetch_fred_stable():
        results = {}
        for name, code in FRED_TICKERS.items():
            try:
                s = fred.get_series(code, observation_start='2020-01-01').dropna()
                results[name] = {"current": s.iloc[-1], "prev": s.iloc[-2], "history": s}
            except: pass
        return results

    data = fetch_fred_stable()
    if data:
        # 指标卡
        m_cols = st.columns(4)
        for idx, (name, val) in enumerate(data.items()):
            m_cols[idx].metric(name, f"{val['current']:.2f}", f"{val['current']-val['prev']:.2f}")

        # 图表 (保留动态缩放和物理切片)
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.05, subplot_titles=list(data.keys()))
        colors = ['#26a69a', '#2962ff', '#787b86', '#ef5350']
        
        for i, name in enumerate(data.keys()):
            df_plot = data[name]['history'].tail(rows_map[lookback])
            fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot.values, line=dict(color=colors[i], width=2), name=name), row=i+1, col=1)

        fig.update_layout(height=900, template='plotly_white', hovermode="x unified", showlegend=False)
        fig.update_yaxes(side="right", autorange=True, zeroline=False, rangemode='normal')
        st.plotly_chart(fig, use_container_width=True)

        # 风险推演
        st.divider()
        oil_v, bond_v = data["布伦特原油 ($)"]["current"], data["10Y美债收益率 (%)"]["current"]
        r_cols = st.columns(4)
        r_cols[0].status("1. 石油/供给冲击", state="error" if oil_v > oil_limit else "complete")
        r_cols[1].status("2. 通胀上行风险", state="error" if oil_v > oil_limit else "complete")
        r_cols[2].status("3. 流动性收紧压力", state="error" if bond_v > bond_limit else "complete")
        r_cols[3].status("4. 估值下修预警", state="error" if bond_v > bond_limit else "complete")

# --- [模块 4: 资产配置 (在线修改优化版)] ---
elif page == "💰 资产配置":
    st.title("💰 资产配置在线管理")
    
    # 1. 初始化或获取 session_state 中的持仓数据
    if 'portfolio_data' not in st.session_state:
        st.session_state.portfolio_data = pd.DataFrame([
            {"资产名称": "腾讯控股", "代码": "0700.HK", "持仓份额": 500},
            {"资产名称": "标普500ETF", "代码": "VOO", "持仓份额": 50},
            {"资产名称": "纳指100ETF", "代码": "QQQ", "持仓份额": 30}
        ])

    st.subheader("📝 编辑持仓")
    st.info("💡 提示：在表格中修改代码(yfinance格式)或份额，系统将自动重算市值。")
    
    # 使用 data_editor 实现交互式修改
    edited_df = st.data_editor(
        st.session_state.portfolio_data,
        num_rows="dynamic", # 允许动态增减行
        use_container_width=True,
        key="portfolio_editor"
    )
    
    # 当用户修改数据时，保存到状态中
    st.session_state.portfolio_data = edited_df

    # 2. 实时行情抓取函数
    @st.cache_data(ttl=300) # 持仓数据缓存 5 分钟
    def sync_market_data(df):
        rows = []
        for _, item in df.iterrows():
            ticker_code = str(item["代码"]).strip()
            if not ticker_code: continue
            try:
                tk = yf.Ticker(ticker_code)
                # 抓取价格和PE
                hist = tk.history(period="1d")
                if not hist.empty:
                    price = hist['Close'].iloc[-1]
                    pe = tk.info.get('trailingPE', 0)
                    rows.append({
                        "资产": item["资产名称"],
                        "代码": ticker_code,
                        "份额": item["持仓份额"],
                        "现价": round(price, 2),
                        "市值": round(price * item["持仓份额"], 2),
                        "PE": pe if pe else "N/A"
                    })
            except:
                st.warning(f"无法同步代码: {ticker_code}")
        return pd.DataFrame(rows)

    # 3. 计算与展示
    if st.button("🚀 同步行情并计算"):
        with st.spinner("正在从交易所拉取实时报价..."):
            display_df = sync_market_data(st.session_state.portfolio_data)
            
            if not display_df.empty:
                total_val = display_df["市值"].sum()
                display_df["权重(%)"] = (display_df["市值"] / total_val * 100).round(2)

                st.divider()
                c1, c2, c3 = st.columns(3)
                c1.metric("总资产概算", f"${total_val:,.2f}")
                c2.metric("持仓数量", len(display_df))
                c3.metric("核心敞口", display_df.loc[display_df["权重(%)"].idxmax()]["资产"])

                # 展示最终结果表
                st.dataframe(display_df, use_container_width=True, hide_index=True)

                # 绘图对比
                col_left, col_right = st.columns(2)
                with col_left:
                    fig_pie = go.Figure(data=[go.Pie(labels=display_df["资产"], values=display_df["市值"], hole=.4)])
                    fig_pie.update_layout(title="资产市值权重", margin=dict(t=30, b=0, l=0, r=0))
                    st.plotly_chart(fig_pie, use_container_width=True)
                with col_right:
                    # 过滤 N/A 的 PE 进行对比
                    pe_plot_df = display_df[display_df["PE"] != "N/A"]
                    fig_bar = go.Bar(x=pe_plot_df["资产"], y=pe_plot_df["PE"], marker_color='#2962ff')
                    st.plotly_chart(go.Figure(data=[fig_bar], layout=dict(title="持仓估值对比(PE)", margin=dict(t=30, b=0, l=0, r=0))), use_container_width=True)
            else:
                st.error("未发现有效代码，请检查表格中的'代码'列是否符合 yfinance 格式。")

st.markdown("---")
st.caption("💡 蚂蚁和帅仔人生无限公司 | V2.2 模块化对齐版")
