import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
from datetime import datetime, timedelta

# 페이지 설정
st.set_page_config(page_title="📈 글로벌 주식 트렌드", layout="wide")

st.title("📈 글로벌 시가총액 TOP10 기업 주가 추이")
st.markdown("💹 **최근 1년 간 주가와 누적 수익률을 시각화합니다.**")

# 시가총액 기준 상위 10개 기업 정보 (2025 기준, yfinance 호환 티커 사용)
company_info = {
    'Apple': 'AAPL',
    'Microsoft': 'MSFT',
    'Nvidia': 'NVDA',
    'Amazon': 'AMZN',
    'Alphabet (Google)': 'GOOGL',
    'Berkshire Hathaway': 'BRK.B',  # yfinance용 표기법
    'Meta': 'META',
    'Eli Lilly': 'LLY',
    'TSMC': 'TSM',
    'Visa': 'V'
}

# 사용자 선택
selected_companies = st.multiselect(
    "🔎 비교할 기업을 선택하세요",
    list(company_info.keys()),
    default=['Apple', 'Microsoft', 'Nvidia']
)

if not selected_companies:
    st.warning("⚠️ 최소 하나 이상의 회사를 선택해주세요.")
    st.stop()

# 티커 리스트 추출
tickers = [company_info[comp] for comp in selected_companies]

# 기간 설정
end_date = datetime.today()
start_date = end_date - timedelta(days=365)

# 데이터 다운로드
with st.spinner("📥 주가 데이터를 불러오는 중입니다..."):
    data = yf.download(tickers, start=start_date, end=end_date)

# 구조 처리
if isinstance(data.columns, pd.MultiIndex):
    if "Adj Close" in data.columns.levels[0]:
        df_raw = data["Adj Close"]
    elif "Close" in data.columns.levels[0]:
        df_raw = data["Close"]
    else:
        st.error("❌ 'Adj Close' 또는 'Close' 데이터가 없습니다.")
        st.stop()
else:
    df_raw = data
    df_raw.columns = [selected_companies[0]]  # 단일 선택

# 결측치 처리
df_raw = df_raw.ffill()

# 📊 주가 추이 시각화
st.subheader("📉 주가 변화 (최근 1년)")
fig1 = px.line(
    df_raw,
    x=df_raw.index,
    y=df_raw.columns,
    labels={'value': '주가', 'index': '날짜'},
    title="일별 종가 추이",
    markers=True
)
fig1.update_layout(hovermode="x unified")
st.plotly_chart(fig1, use_container_width=True)

# 📈 누적 수익률 계산
returns = df_raw.pct_change().dropna()
cumulative_returns = (1 + returns).cumprod() - 1

# 📊 누적 수익률 시각화
st.subheader("📈 누적 수익률 변화")
fig2 = px.line(
    cumulative_returns,
    x=cumulative_returns.index,
    y=cumulative_returns.columns,
    labels={'value': '누적 수익률', 'index': '날짜'},
    title="누적 수익률 (%)",
)
fig2.update_yaxes(tickformat=".0%")
fig2.update_layout(hovermode="x unified")
st.plotly_chart(fig2, use_container_width=True)

# 🔎 최근 수익률 비교 테이블
st.subheader("📋 최근 수익률 비교 (Top5 기준일)")
st.dataframe(cumulative_returns.tail().style.format("{:.2%}"))
