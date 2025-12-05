import re
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ====================== Streamlit 설정(맨 위!) ======================
st.set_page_config(page_title="보이스피싱 대시보드", layout="wide")
st.title("📞 보이스피싱 공공데이터 대시보드 (CSV 기반)")

# ====================== 경로(핵심) ======================
# 이 파일은 pages/ 안에 있으므로,
# __file__ 기준으로 한 단계 위가 "레포 루트"가 됨.
ROOT = Path(__file__).resolve().parents[1]

# CSV를 어디에 두든(루트 or 루트/data) 둘 다 시도해보는 후보 목록
YEARLY_CANDIDATES = [
    ROOT / "police_voicephishing_yearly.csv",
    ROOT / "data" / "police_voicephishing_yearly.csv",
]
MONTHLY_CANDIDATES = [
    ROOT / "police_voicephishing_monthly.csv",
    ROOT / "data" / "police_voicephishing_monthly.csv",
]

def pick_existing(cands: list[Path]) -> Path:
    """후보 경로 중 실제 존재하는 파일 경로를 하나 고른다."""
    for p in cands:
        if p.exists():
            return p
    # 어디에도 없으면 에러(파일명/위치가 다르다는 뜻)
    raise FileNotFoundError(f"파일을 못 찾음. 후보 경로: {[str(x) for x in cands]}")

yearly_path = pick_existing(YEARLY_CANDIDATES)
monthly_path = pick_existing(MONTHLY_CANDIDATES)

# (디버그용) 실제로 어디서 읽는지 보여주기
with st.expander("🔎 파일 경로 확인(문제 생길 때만 열어봐)"):
    st.write("ROOT:", str(ROOT))
    st.write("연도별 CSV:", str(yearly_path))
    st.write("월별 CSV:", str(monthly_path))


# ====================== CSV 불러오기(인코딩 자동) ======================
def read_csv_smart(path: Path) -> pd.DataFrame:
    # 공공데이터는 utf-8-sig / cp949가 대표적이라 이 순서가 좋음
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            pass
    # 최후: 깨지는 문자 무시하고 읽기
    return pd.read_csv(path, encoding="utf-8", encoding_errors="ignore")

try:
    yearly_df = read_csv_smart(yearly_path)
    monthly_df = read_csv_smart(monthly_path)
except Exception as e:
    st.error(f"CSV를 못 읽었어: {e}")
    st.info("CSV 출처(다운로드):")
    st.write("- 연도별: https://www.data.go.kr/data/15063815/fileData.do")
    st.write("- 월별: https://www.data.go.kr/data/15099013/fileData.do")
    st.stop()

# ====================== 컬럼 정리 ======================
yearly_df.columns = yearly_df.columns.astype(str).str.strip()
monthly_df.columns = monthly_df.columns.astype(str).str.strip()

# ====================== 사이드바 ======================
with st.sidebar:
    st.header("보기")
    view = st.radio("분석 선택", ["월별 추이(발생건수)", "연도별 비교(유형/피해액/발생)"])

# ====================== 월별 추이 ======================
if view == "월별 추이(발생건수)":
    # 컬럼 자동 탐색
    year_col = next((c for c in monthly_df.columns if re.search(r"연도|년도|년", c)), None)
    mon_col  = next((c for c in monthly_df.columns if re.search(r"월", c)), None)
    cnt_col  = next((c for c in monthly_df.columns if ("발생" in c and "건수" in c)), None)

    if not (year_col and mon_col and cnt_col):
        st.error(f"필수 컬럼을 못 찾음. 현재 컬럼: {list(monthly_df.columns)}")
        st.stop()

    df = monthly_df.copy()

    # 숫자 변환(문자/쉼표 등 방어)
    df[year_col] = pd.to_numeric(df[year_col].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    df[mon_col]  = pd.to_numeric(df[mon_col].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    df[cnt_col]  = pd.to_numeric(df[cnt_col].astype(str).str.replace(",", "").str.strip(), errors="coerce")

    # 날짜 생성 + 정렬
    df["date"] = pd.to_datetime(
        df[year_col].astype("Int64").astype(str) + "-" +
        df[mon_col].astype("Int64").astype(str).str.zfill(2) + "-01",
        errors="coerce"
    )
    df = df.dropna(subset=["date"]).sort_values("date")

    st.subheader("📈 월별 발생건수 추이")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["date"], y=df[cnt_col], mode="lines+markers", name="발생건수"))
    fig.update_layout(xaxis_title="월", yaxis_title="발생건수", height=450)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📄 월별 데이터(표)")
    st.dataframe(df, use_container_width=True)

# ====================== 연도별 비교 ======================
else:
    # 연도 컬럼 탐색 ('구분'이 연도인 경우가 흔함)
    year_col = "구분" if "구분" in yearly_df.columns else next(
        (c for c in yearly_df.columns if ("연도" in c or "년도" in c or str(c).endswith("년"))),
        yearly_df.columns[0]
    )

    df = yearly_df.copy()

    # 연도 숫자화 + 정렬
    df[year_col] = pd.to_numeric(df[year_col].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    df = df.dropna(subset=[year_col]).sort_values(year_col)

    # 유형별 피해액/발생건수 컬럼 찾기
    damage_cols = [c for c in df.columns if ("피해액" in c and ("억원" in c or "원" in c))]
    case_cols   = [c for c in df.columns if ("발생" in c and "건수" in c)]

    st.subheader("📊 연도별 데이터(표)")
    st.dataframe(df, use_container_width=True)

    if damage_cols:
        st.subheader("📈 연도별 피해액 추이(유형별)")
        fig = go.Figure()
        for c in damage_cols:
            fig.add_trace(go.Scatter(
                x=df[year_col],
                y=pd.to_numeric(df[c].astype(str).str.replace(",", "").str.strip(), errors="coerce"),
                mode="lines+markers",
                name=c
            ))
        fig.update_layout(xaxis_title="연도", yaxis_title="피해액", height=450)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("피해액 컬럼을 못 찾았어(컬럼명이 바뀌었을 수 있음).")

    if case_cols:
        st.subheader("📈 연도별 발생건수 추이(유형별)")
        fig = go.Figure()
        for c in case_cols:
            fig.add_trace(go.Scatter(
                x=df[year_col],
                y=pd.to_numeric(df[c].astype(str).str.replace(",", "").str.strip(), errors="coerce"),
                mode="lines+markers",
                name=c
            ))
        fig.update_layout(xaxis_title="연도", yaxis_title="발생건수", height=450)
        st.plotly_chart(fig, use_container_width=True)

st.divider()
st.caption("데이터 출처(공식 CSV): 공공데이터포털(경찰청) 보이스피싱 현황/월별 현황")
