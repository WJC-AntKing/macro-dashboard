import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from fredapi import Fred
import yfinance as yf
from datetime import datetime, timedelta

# --- 1. 基础配置 ---
st.set_page_config(page_title="蚂蚁和帅仔的私人终端", layout="wide")
beijing_time = datetime.utcnow() + timedelta(hours=8)

# 安全获取 FRED Key
try:
    fred_key = st.secrets["FRED_API_KEY"]
    fred = Fred(api_key=fred_key)
except Exception:
    st.error("❌ 未在 Secrets 中检测到 FRED_API_KEY")
    st.stop()

# --- 2. 侧边栏导航 ---
with st.sidebar:
    st.title("💼 导航中心")
    page = st.radio("前往页面", ["🛡️ 宏观哨兵", "💰 资产配置"])
    st.divider()

# --- 3. 页面：宏观哨兵 (复用之前的逻辑) ---
if page == "🛡️ 宏观哨兵":
    st.title("🛡️ 宏观经济传导逻辑预警")
    
    # (此处省略部分重复的配置代码以节省篇幅，实际运行时逻辑完全保留)
    FRED_TICKERS = {
        "布伦特原油 ($)": "DCOILBRENTEU",
        "10Y美债收益率 (%)": "DGS10",
        "美元指数 (DXY)": "DTWEXAFEGS", 
        "纳斯达克100 (指数)": "NASDAQ100"
    }
    
    @st.cache_data(ttl=3600)
    def fetch_fred_data():
        results = {}
        for name, code in FRED_TICKERS.items():
            try:
                s = fred.get_series(code, observation_start='2020-01-01').dropna()
                results[name] = {"current": s.iloc[-1], "prev": s.iloc[-2], "history": s}
            except: pass
        return results

    data = fetch_fred_data()
    if data:
        # 指标卡片
        cols = st.columns(4)
        for i, (name, val) in enumerate(data.items()):
            cols[i].metric(name, f"{val['current']:.2f}", f"{val['current']-val['prev']:.2f}")
        
        # 绘图逻辑 (tail 252 约等于一年)
        fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.05)
        for i, name in enumerate(data.keys()):
            df_p = data[name]['history'].tail(252)
            fig.add_trace(go.Scatter(x=df_p.index, y=df_p.values, name=name), row=i+1, col=1)
        fig.update_layout(height=800, template='plotly_white')
        st.plotly_chart(fig, use_container_width=True)

# --- 4. 页面：资产配置管理 ---
elif page == "💰 资产配置":
    st.title("💰 个人资产配置持仓管理")
    
    # A. 定义你的持仓数据 (在这里修改你的持仓)
    # 格式: 名称: [yfinance代码, 持仓份额]
    # 注意: A股后缀为 .SS 或 .SZ, 港股为 .HK, 美股直接填代码
    MY_ASSETS = {
        "腾讯控股": ["0700.HK", 500],
        "标普500ETF": ["VOO", 50],
        "贵州茅台": ["600519.SS", 100],
        "微软": ["MSFT", 20]
    }

    @st.cache_data(ttl=600)
    def fetch_portfolio_data(assets):
        rows = []
        for name, info in assets.items():
            ticker_code, shares = info[0], info[1]
            try:
                tk = yf.Ticker(ticker_code)
                # 获取实时价格
                price = tk.history(period="1d")['Close'].iloc[-1]
                # 获取市盈率 (PE)
                pe = tk.info.get('trailingPE', 'N/A')
                # 获取货币单位
                currency = tk.info.get('currency', 'USD')
                
                rows.append({
                    "资产名称": name,
                    "代码": ticker_code,
                    "持仓份额": shares,
                    "实时价格": round(price, 2),
                    "市值 (本币)": round(price * shares, 2),
                    "市盈率 (PE)": pe,
                    "币种": currency
                })
            except:
                st.warning(f"无法获取 {name} 的实时数据")
        return pd.DataFrame(rows)

    with st.spinner("正在同步全球证券市场行情..."):
        df_portfolio = fetch_portfolio_data(MY_ASSETS)

    if not df_portfolio.empty:
        # B. 计算汇总数据
        # 注意：此处简化处理，假设所有市值已按汇率换算（实际进阶版需增加汇率转换）
        total_value = df_portfolio["市值 (本币)"].sum()
        df_portfolio["权重 (%)"] = (df_portfolio["市值 (本币)"] / total_value * 100).round(2)

        # C. 顶部汇总卡片
        m1, m2 = st.columns(2)
        m1.metric("持仓总市值 (折合概算)", f"${total_value:,.2f}")
        m2.metric("主要风险敞口", df_portfolio.loc[df_portfolio["权重 (%)"].idxmax()]["资产名称"])

        # D. 展示持仓表格
        st.subheader("📋 详细持仓清单")
        st.dataframe(
            df_portfolio,
            column_config={
                "实时价格": st.column_config.NumberColumn(format="¥ %.2f" if "SS" in str(df_portfolio["代码"]) else "$ %.2f"),
                "权重 (%)": st.column_config.ProgressColumn(min_value=0, max_value=100)
            },
            hide_index=True,
            use_container_width=True
        )

        # E. 资产分布图
        col_left, col_right = st.columns(2)
        with col_left:
            st.subheader("🍕 资产权重分布")
            fig_pie = go.Figure(data=[go.Pie(labels=df_portfolio["资产名称"], values=df_portfolio["权重 (%)"], hole=.3)])
            fig_pie.update_layout(margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig_pie, use_container_width=True)
            
        with col_right:
            st.subheader("📊 PE 估值横向对比")
            # 过滤掉非数字的 PE
            pe_df = df_portfolio[df_portfolio["市盈率 (PE)"] != "N/A"]
            fig_bar = go.Bar(x=pe_df["资产名称"], y=pe_df["市盈率 (PE)"], marker_color='#2962ff')
            st.plotly_chart(go.Figure(data=[fig_bar], layout=dict(margin=dict(l=20, r=20, t=20, b=20))), use_container_width=True)

# 页脚
st.divider()
st.markdown(f"💡 **蚂蚁和帅仔资产终端** | 数据最后同步：{datetime.now().strftime('%H:%M:%S')}")
