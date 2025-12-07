# [1] 라이브러리 불러오기: 정규식/경로/Streamlit UI/pandas/Plotly
import re
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# [2] Streamlit 페이지 설정: 반드시 st.* 중 가장 먼저 실행되는 게 안전
st.set_page_config(page_title="보이스피싱 대시보드", layout="wide")
st.title("📞 보이스피싱 공공데이터 대시보드 (CSV 기반)")

# [3] 경로 처리 핵심:
# pages/ 안에서 실행되므로, 현재 파일 기준으로 한 단계 위(레포 루트)를 ROOT로 잡는다.
ROOT = Path(__file__).resolve().parents[1]

# [4] CSV가 루트에 있거나 루트/data에 있을 수 있어서 후보를 두고 "존재하는 것"을 선택한다.
YEARLY_CANDIDATES = [
    ROOT / "police_voicephishing_yearly.csv",
    ROOT / "data" / "police_voicephishing_yearly.csv",
]
MONTHLY_CANDIDATES = [
    ROOT / "police_voicephishing_monthly.csv",
    ROOT / "data" / "police_voicephishing_monthly.csv",
]

# [5] 후보 중 실제 존재하는 파일 경로를 찾아서 반환한다. 없으면 FileNotFoundError.
def pick_existing(cands: list[Path]) -> Path:
    """후보 경로 중 실제 존재하는 파일 경로를 하나 고른다."""
    for p in cands:
        if p.exists():
            return p
    raise FileNotFoundError(f"파일을 못 찾음. 후보 경로: {[str(x) for x in cands]}")

# [6] 실제 사용할 CSV 경로 결정
yearly_path = pick_existing(YEARLY_CANDIDATES)
monthly_path = pick_existing(MONTHLY_CANDIDATES)

# [7] 디버그용: 현재 루트/선택된 파일 경로를 접이식으로 보여준다.
with st.expander("🔎 파일 경로 확인(문제 생길 때만 열어봐)"):
    st.write("ROOT:", str(ROOT))
    st.write("연도별 CSV:", str(yearly_path))
    st.write("월별 CSV:", str(monthly_path))

# [8] CSV 로딩(인코딩 자동 시도):
# 공공데이터는 utf-8-sig/cp949/euc-kr이 섞여서 인코딩을 순서대로 시도한다.
def read_csv_smart(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(path, encoding="utf-8", encoding_errors="ignore")

# [9] CSV 로딩 실패 시 사용자에게 안내하고 앱을 중단한다.
try:
    yearly_df = read_csv_smart(yearly_path)
    monthly_df = read_csv_smart(monthly_path)
except Exception as e:
    st.error(f"CSV를 못 읽었어: {e}")
    st.info("CSV 출처(다운로드):")
    st.write("- 연도별: https://www.data.go.kr/data/15063815/fileData.do")
    st.write("- 월별: https://www.data.go.kr/data/15099013/fileData.do")
    st.stop()

# [10] 컬럼명 공백 제거: 공공데이터 CSV는 컬럼명 앞뒤 공백 때문에 오류가 나는 경우가 많다.
yearly_df.columns = yearly_df.columns.astype(str).str.strip()
monthly_df.columns = monthly_df.columns.astype(str).str.strip()

# [11] 사이드바: 월별/연도별 분석 화면 선택
with st.sidebar:
    st.header("보기")
    view = st.radio("분석 선택", ["월별 추이(발생건수)", "연도별 비교(유형/피해액/발생)"])

# [12] 월별 화면:
# - 연/월/발생건수 컬럼을 자동 탐색
# - 연+월로 date를 만들고 정렬해서 시계열 라인차트를 그린다.
if view == "월별 추이(발생건수)":
    year_col = next((c for c in monthly_df.columns if re.search(r"연도|년도|년", c)), None)
    mon_col  = next((c for c in monthly_df.columns if re.search(r"월", c)), None)
    cnt_col  = next((c for c in monthly_df.columns if ("발생" in c and "건수" in c)), None)

    if not (year_col and mon_col and cnt_col):
        st.error(f"필수 컬럼을 못 찾음. 현재 컬럼: {list(monthly_df.columns)}")
        st.stop()

    df = monthly_df.copy()

    df[year_col] = pd.to_numeric(df[year_col].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    df[mon_col]  = pd.to_numeric(df[mon_col].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    df[cnt_col]  = pd.to_numeric(df[cnt_col].astype(str).str.replace(",", "").str.strip(), errors="coerce")

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

# [13] 연도별 화면:
# - 연도 컬럼(구분/연도)을 잡고 정렬
# - 피해액/발생건수 관련 컬럼들을 찾아 유형별로 여러 선 그래프를 그린다.
else:
    year_col = "구분" if "구분" in yearly_df.columns else next(
        (c for c in yearly_df.columns if ("연도" in c or "년도" in c or str(c).endswith("년"))),
        yearly_df.columns[0]
    )

    df = yearly_df.copy()

    df[year_col] = pd.to_numeric(df[year_col].astype(str).str.replace(",", "").str.strip(), errors="coerce")
    df = df.dropna(subset=[year_col]).sort_values(year_col)
