import os
import glob
import re
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="이상기후별 피해액 분석", layout="wide")

st.title("이상기후별 피해액 분석 (2015~2023)")
st.caption("데이터: 자연재난상황통계(피해액) / PPT 발표용으로 항목 정리(지진·풍랑 제거, 합계 제거, 가/나 통일)")

# -----------------------------
# CSV Load
# -----------------------------
def load_default_csv():
    candidates = [
        "natural_disaster_damage_long.csv",
        "./natural_disaster_damage_long.csv",
        "./data/natural_disaster_damage_long.csv",
    ]
    for p in candidates:
        if os.path.exists(p):
            return pd.read_csv(p, encoding="utf-8-sig")

    found = glob.glob("**/*.csv", recursive=True)
    prefer = [f for f in found if os.path.basename(f) == "natural_disaster_damage_long.csv"]
    if prefer:
        return pd.read_csv(prefer[0], encoding="utf-8-sig")
    return None


def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    needed = {"재난원인", "구분", "연도", "금액"}
    if not needed.issubset(df.columns):
        raise ValueError(f"필수 컬럼이 없습니다. 필요={needed}, 현재={set(df.columns)}")

    df["재난원인"] = df["재난원인"].astype(str).str.strip()
    df["구분"] = df["구분"].astype(str).str.strip()

    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df["금액"] = pd.to_numeric(df["금액"], errors="coerce")

    df = df.dropna(subset=["연도", "금액"]).copy()
    df["연도"] = df["연도"].astype(int)

    return df


def normalize_cause(s: str) -> str:
    # 표기 흔들림 정리: 공백 제거, 점(·) 처리 정도만
    x = str(s).strip()
    x = x.replace("·", ",")
    x = re.sub(r"\s+", "", x)
    return x


# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.header("데이터 불러오기")
    up = st.file_uploader("CSV 업로드(롱포맷)", type=["csv"])
    st.caption("업로드 안 하면 레포에서 natural_disaster_damage_long.csv 자동 탐색")

    st.divider()
    st.header("PPT용 필터(추천 설정)")

    # 가/나 통일
    metric = st.radio("구분(가/나)", ["가만 보기", "나만 보기", "둘 다 보기"], index=0)

    # 분석 대상 이상기후(3P 기준: 풍랑 제거, 지진 제거)
    st.caption("분석 대상(이상기후): 호우/태풍/대설/강풍/폭염")
    use_default_causes = st.checkbox("이상기후 5종만 고정", value=True)

    st.divider()
    st.header("그래프 옵션")
    remove_total = st.checkbox("‘합계’ 항목 제거", value=True)
    show_markers = st.checkbox("라인차트 점 표시", value=True)

# Load
if up is not None:
    df_raw = pd.read_csv(up, encoding="utf-8-sig")
else:
    df_raw = load_default_csv()

if df_raw is None:
    st.warning("CSV를 업로드하거나, 레포에 natural_disaster_damage_long.csv를 넣어주세요.")
    st.write("현재 폴더 파일:", os.listdir("."))
    st.stop()

df = clean_df(df_raw)

# Normalize cause
df["재난원인_norm"] = df["재난원인"].apply(normalize_cause)

# Remove '합계'
if remove_total:
    df = df[df["재난원인_norm"] != "합계"].copy()

# Remove 지진 / 풍랑(풍랑,강풍 포함 전부 제거)
df = df[~df["재난원인_norm"].str.contains("지진")].copy()
df = df[~df["재난원인_norm"].str.contains("풍랑")].copy()

# Metric filter (가/나)
if metric == "가만 보기":
    df = df[df["구분"] == "가"].copy()
elif metric == "나만 보기":
    df = df[df["구분"] == "나"].copy()

# Keep only 5 climate-related causes (PPT 3P와 일치)
allowed = ["호우", "태풍", "대설", "강풍", "폭염"]
if use_default_causes:
    df = df[df["재난원인_norm"].isin(allowed)].copy()

# Year range
min_year, max_year = int(df["연도"].min()), int(df["연도"].max())

with st.sidebar:
    year_range = st.slider("연도 범위", min_year, max_year, (min_year, max_year), step=1)

# Apply year filter
df = df[(df["연도"] >= year_range[0]) & (df["연도"] <= year_range[1])].copy()

if df.empty:
    st.warning("필터 결과가 비었습니다. 조건을 바꿔주세요.")
    st.stop()

# -----------------------------
# 1) Line chart (trend)
# -----------------------------
st.subheader("1) 연도별 추세 (라인차트)")

# 라벨: 가/나 둘 다 볼 때만 구분을 붙여 혼동 방지
if metric == "둘 다 보기":
    df["라벨"] = df["재난원인_norm"] + " " + df["구분"]
    color_col = "라벨"
else:
    df["라벨"] = df["재난원인_norm"]
    color_col = "라벨"

fig1 = px.line(
    df.sort_values(["라벨", "연도"]),
    x="연도",
    y="금액",
    color=color_col,
    markers=show_markers,
    title="연도별 피해(금액) 변화"
)
st.plotly_chart(fig1, use_container_width=True)

# -----------------------------
# 2) Bar chart (total comparison)
# -----------------------------
st.subheader("2) 기간 합계 비교 (막대그래프)")

agg = (
    df.groupby("재난원인_norm", as_index=False)["금액"]
      .sum()
      .sort_values("금액", ascending=False)
)

fig2 = px.bar(
    agg,
    x="금액",
    y="재난원인_norm",
    orientation="h",
    title=f"{year_range[0]}~{year_range[1]} 기간 합계(재난원인별)"
)
st.plotly_chart(fig2, use_container_width=True)

# -----------------------------
# 3) Table + download
# -----------------------------
st.subheader("3) 데이터 확인")

show_cols = ["재난원인", "재난원인_norm", "구분", "연도", "금액"]
st.dataframe(df[show_cols].sort_values(["재난원인_norm", "구분", "연도"]), use_container_width=True)

st.download_button(
    "현재 필터 결과 CSV 다운로드",
    data=df.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig"),
    file_name="filtered_damage.csv",
    mime="text/csv"
)
