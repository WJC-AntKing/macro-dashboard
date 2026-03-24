import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from fredapi import Fred
import yfinance as yf
import json
import os
from datetime import datetime, timedelta

# --- [新增：持久化数据处理函数] ---
DATA_FILE = "portfolio.json"

def load_data():
    """从本地 JSON 文件加载持仓数据"""
    import os
    import json
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return pd.DataFrame(data)
        except Exception as e:
            st.error(f"读取数据失败: {e}")
    # 如果文件不存在，返回初始示例数据
    return pd.DataFrame([
        {"资产名称": "腾讯控股", "代码": "0700.HK", "持仓份额": 500},
        {"资产名称": "标普500ETF", "代码": "VOO", "持仓份额": 50}
    ])

def save_data(df):
    """将持仓数据保存到本地 JSON 文件"""
    import json
    try:
        # 确保目录存在（Streamlit Cloud 环境下）
        df_dict = df.to_dict(orient="records")
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(df_dict, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        st.error(f"保存失败: {e}")
        return False

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
    st.title("💰 资产持仓永久管理")
    
    # 加载现有持仓
    if 'df_portfolio' not in st.session_state:
        st.session_state.df_portfolio = load_data()

    # 1. 编辑区域
    with st.expander("🛠️ 编辑持仓数据 (修改后记得点保存)", expanded=True):
        edited_df = st.data_editor(
            st.session_state.df_portfolio,
            num_rows="dynamic",
            use_container_width=True,
            key="main_editor"
        )
        
        if st.button("💾 保存持仓到云端"):
            save_data(edited_df)
            st.session_state.df_portfolio = edited_df
            st.success("✅ 持仓已同步至 JSON 数据库！")

    # 2. 行情分析
    st.divider()
    if st.button("🚀 刷新实时行情"):
        @st.cache_data(ttl=300)
        def get_prices(df):
            rows = []
            for _, item in df.iterrows():
                try:
                    tk = yf.Ticker(str(item["代码"]))
                    price = tk.history(period="1d")['Close'].iloc[-1]
                    pe = tk.info.get('trailingPE', 0)
                    rows.append({
                        "资产": item["资产名称"], "代码": item["代码"], 
                        "份额": item["持仓份额"], "现价": round(price, 2),
                        "市值": round(price * item["持仓份额"], 2), "PE": pe if pe else "N/A"
                    })
                except: pass
            return pd.DataFrame(rows)

        final_df = get_prices(st.session_state.df_portfolio)
        
        if not final_df.empty:
            total = final_df["市值"].sum()
            final_df["权重%"] = (final_df["市值"] / total * 100).round(2)
            
            c1, c2 = st.columns(2)
            c1.metric("总资产估值", f"${total:,.2f}")
            c2.metric("最大头寸", final_df.loc[final_df["权重%"].idxmax()]["资产"])
            
            st.dataframe(final_df, use_container_width=True, hide_index=True)
            
            # 可视化
            p_cols = st.columns(2)
            with p_cols[0]:
                fig_p = go.Figure(data=[go.Pie(labels=final_df["资产"], values=final_df["市值"], hole=.4)])
                st.plotly_chart(fig_p, use_container_width=True)
            with p_cols[1]:
                pe_df = final_df[final_df["PE"] != "N/A"]
                st.plotly_chart(go.Figure(data=[go.Bar(x=pe_df["资产"], y=pe_df["PE"])]), use_container_width=True)


st.markdown("---")
st.caption("💡 蚂蚁和帅仔人生无限公司 | V2.2 模块化对齐版")
