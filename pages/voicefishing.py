import re  # 컬럼명에서 '년/월/발생/피해' 같은 키워드 탐색용(정규식)
import streamlit as st  # 웹 앱 UI (버튼/사이드바/표/그래프 출력)
import pandas as pd  # CSV 로딩 + 데이터 전처리/계산
import plotly.graph_objects as go  # Plotly로 라인 차트 생성

# ---------------------- 페이지 기본 설정 ----------------------
st.set_page_config(page_title="보이스피싱 대시보드", layout="wide")  # 화면 넓게(wide) 사용
st.title("📞 보이스피싱 공공데이터 대시보드 (CSV 기반)")  # 앱 제목

# ---------------------- 파일 경로 ----------------------
# 레포에 넣어둔 CSV를 로컬 파일처럼 읽어오는 방식
yearly_path = "police_voicephishing_yearly.csv"    # 연도별: 유형/피해액/발생/검거
monthly_path = "police_voicephishing_monthly.csv"  # 월별: 년/월/발생건수

# ---------------------- CSV 불러오기 ----------------------
# 공공데이터 CSV는 cp949인 경우가 많아서 encoding을 고정
# (인코딩이 다르면 여기서 바로 에러가 날 수 있음)
try:
    yearly_df = pd.read_csv(yearly_path, encoding="cp949")   # 연도별 CSV 로딩
    monthly_df = pd.read_csv(monthly_path, encoding="cp949") # 월별 CSV 로딩
except Exception as e:
    # 읽기 실패 시 앱에서 친절히 안내하고 멈춤(밑에서 undefined 변수 오류가 나지 않게)
    st.error(f"CSV를 못 읽었어: {e}")
    st.info("CSV 출처(다운로드):")
    st.write("- 연도별: https://www.data.go.kr/data/15063815/fileData.do")
    st.write("- 월별: https://www.data.go.kr/data/15099013/fileData.do")
    st.stop()  # 여기서 실행 종료

# ---------------------- 컬럼 정리 ----------------------
# 컬럼명 끝/앞 공백 때문에 KeyError 나는 경우가 많아서 strip 처리
yearly_df.columns = yearly_df.columns.str.strip()
monthly_df.columns = monthly_df.columns.str.strip()

# ---------------------- 사이드바(사용자 선택 UI) ----------------------
with st.sidebar:
    st.header("보기 설정")
    # 사용자가 "월별"을 볼지 "연도별"을 볼지 선택
    view = st.radio("분석 선택", ["월별 추이(발생건수)", "연도별 비교(유형/피해액/발생)"])

# ======================================================================
# [알고리즘/원리] 월별 추이
# 1) '연도/월/발생건수' 컬럼을 자동 탐색
# 2) 연도+월을 날짜(date)로 변환
# 3) 날짜순 정렬 후 라인차트 출력
# ======================================================================
if view == "월별 추이(발생건수)":
    # ---- 1) 컬럼 자동 탐색 ----
    # '연도/년도/년'이 들어간 컬럼을 연도 컬럼으로 잡음
    year_col = next((c for c in monthly_df.columns if re.search(r"연도|년도|년", c)), None)

    # '월'이 들어간 컬럼을 월 컬럼으로 잡음
    mon_col = next((c for c in monthly_df.columns if re.search(r"월", c)), None)

    # '발생'과 '건수'가 동시에 들어간 컬럼을 발생건수 컬럼으로 잡음
    cnt_col = next((c for c in monthly_df.columns if ("발생" in c and "건수" in c)), None)

    # ---- 컬럼 탐색 실패 시 중단(컬럼명 이슈 방지) ----
    if not (year_col and mon_col and cnt_col):
        st.error(f"필수 컬럼을 못 찾음. 현재 컬럼: {list(monthly_df.columns)}")
        st.stop()

    # ---- 2) 타입 변환 + 날짜 만들기 ----
    df = monthly_df.copy()  # 원본 보호를 위해 복사본 사용

    # 문자열/공백/이상값이 있을 수 있으니 숫자로 변환(실패는 NaN)
    df[year_col] = pd.to_numeric(df[year_col], errors="coerce")
    df[mon_col] = pd.to_numeric(df[mon_col], errors="coerce")
    df[cnt_col] = pd.to_numeric(df[cnt_col], errors="coerce")

    # '연도-월-01' 형태로 날짜 생성 -> 시계열 그래프 x축으로 활용
    df["date"] = pd.to_datetime(
        df[year_col].astype("Int64").astype(str) + "-" +
        df[mon_col].astype("Int64").astype(str).str.zfill(2) + "-01",
        errors="coerce"
    )

    # 날짜가 만들어지지 않은 행 제거 + 시간순 정렬(그래프가 뒤죽박죽 되는 걸 방지)
    df = df.dropna(subset=["date"]).sort_values("date")

    # ---- 3) 시각화 ----
    st.subheader("📈 월별 발생건수 추이")
    fig = go.Figure()  # Plotly Figure 객체 생성

    # 라인+마커로 월별 변화 표시
    fig.add_trace(go.Scatter(
        x=df["date"], y=df[cnt_col],
        mode="lines+markers",
        name="발생건수"
    ))

    # 축 제목/높이 지정(보기 좋아지게)
    fig.update_layout(xaxis_title="월", yaxis_title="발생건수", height=450)

    # Streamlit에 출력
    st.plotly_chart(fig, use_container_width=True)

    # 원본 확인용 표 출력(디버깅 + 보고서 증빙에 좋음)
    st.subheader("📄 월별 데이터(표)")
    st.dataframe(df, use_container_width=True)

# ======================================================================
# [알고리즘/원리] 연도별 비교
# 1) 연도 컬럼(구분/연도 등)을 자동 탐색 후 숫자로 변환
# 2) '피해액', '발생건수' 컬럼을 키워드로 여러 개 찾음(유형별)
# 3) 연도축 기준으로 컬럼별 라인차트 출력
# ======================================================================
else:
    # ---- 1) 연도 컬럼 찾기 ----
    # 공공데이터는 연도 컬럼이 '구분'인 경우가 많음 -> 있으면 우선 사용
    if "구분" in yearly_df.columns:
        year_col = "구분"
    else:
        # 없으면 컬럼명에 '연도/년도/년'이 들어간 걸 탐색
        year_col = next((c for c in yearly_df.columns if ("연도" in c or "년도" in c or c.endswith("년"))), yearly_df.columns[0])

    df = yearly_df.copy()
    df[year_col] = pd.to_numeric(df[year_col], errors="coerce")  # 연도 숫자화
    df = df.dropna(subset=[year_col]).sort_values(year_col)      # 연도 없는 행 제거 + 정렬

    # ---- 2) 유형별 컬럼 자동 탐색 ----
    # 피해액(억원/원 등 표기가 달라도 '피해액' 키워드로 모으기)
    damage_cols = [c for c in df.columns if ("피해액" in c and ("억원" in c or "원" in c))]

    # 발생건수(유형별로 여러 컬럼일 수 있음)
    case_cols = [c for c in df.columns if ("발생" in c and "건수" in c)]

    # ---- 3) 표 + 그래프 출력 ----
    st.subheader("📊 연도별 데이터(표)")
    st.dataframe(df, use_container_width=True)

    # 피해액 그래프
    if damage_cols:
        st.subheader("📈 연도별 피해액 추이(유형별)")
        fig = go.Figure()

        # 피해액 컬럼이 여러 개면(기관사칭형/대출사기형 등) 각각 선으로 추가
        for c in damage_cols:
            fig.add_trace(go.Scatter(
                x=df[year_col],
                y=pd.to_numeric(df[c], errors="coerce"),
                mode="lines+markers",
                name=c
            ))

        fig.update_layout(xaxis_title="연도", yaxis_title="피해액", height=450)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("피해액 컬럼을 못 찾았어(컬럼명이 다를 수 있음).")

    # 발생건수 그래프
    if case_cols:
        st.subheader("📈 연도별 발생건수 추이(유형별)")
        fig = go.Figure()

        for c in case_cols:
            fig.add_trace(go.Scatter(
                x=df[year_col],
                y=pd.to_numeric(df[c], errors="coerce"),
                mode="lines+markers",
                name=c
            ))

        fig.update_layout(xaxis_title="연도", yaxis_title="발생건수", height=450)
        st.plotly_chart(fig, use_container_width=True)

# ---------------------- 출처 표시(보고서용) ----------------------
st.divider()
st.caption("데이터 출처: 공공데이터포털(경찰청) 보이스피싱 현황/월별 현황 (CSV 다운로드)")
