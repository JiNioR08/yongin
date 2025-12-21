import os
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="자연재난 피해 시각화", layout="wide")

st.title("자연재난(이상기후) 피해 시각화 대시보드")
st.caption("CSV(롱포맷): 재난원인, 구분, 연도, 금액")

# -----------------------------
# Data loading helpers
# -----------------------------
def load_default_csv():
    # 네가 방금 만든 파일 경로(로컬에서 실행할 때 사용)
    default_path = "natural_disaster_damage_long.csv"
    if os.path.exists(default_path):
        return pd.read_csv(default_path, encoding="utf-8-sig")
    return None

def clean_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    # 컬럼명 공백 제거
    df.columns = [c.strip() for c in df.columns]

    needed = {"재난원인", "구분", "연도", "금액"}
    if not needed.issubset(set(df.columns)):
        raise ValueError(f"필수 컬럼이 없습니다. 필요={needed}, 현재={set(df.columns)}")

    df["재난원인"] = df["재난원인"].astype(str).str.strip()
    df["구분"] = df["구분"].astype(str).str.strip()
    df["연도"] = pd.to_numeric(df["연도"], errors="coerce").astype("Int64")
    df["금액"] = pd.to_numeric(df["금액"], errors="coerce")

    df = df.dropna(subset=["연도", "금액"])
    df = df.sort_values(["재난원인", "구분", "연도"]).reset_index(drop=True)
    return df

# -----------------------------
# Sidebar controls
# -----------------------------
with st.sidebar:
    st.header("데이터 불러오기")
    up = st.file_uploader("롱포맷 CSV 업로드", type=["csv"])
    st.caption("없으면 같은 폴더의 natural_disaster_damage_long.csv를 자동으로 찾습니다.")

    st.divider()
    st.header("필터")

# Load data
if up is not None:
    df_raw = pd.read_csv(up, encoding="utf-8-sig")
else:
    df_raw = load_default_csv()

if df_raw is None:
    st.warning("CSV를 업로드하거나, 실행 폴더에 natural_disaster_damage_long.csv를 두세요.")
    st.stop()

try:
    df = clean_df(df_raw)
except Exception as e:
    st.error(f"데이터 처리 실패: {e}")
    st.stop()

# Filters
all_causes = sorted(df["재난원인"].unique().tolist())
all_types = sorted(df["구분"].unique().tolist())

min_year, max_year = int(df["연도"].min()), int(df["연도"].max())

with st.sidebar:
    year_range = st.slider("연도 범위", min_year, max_year, (min_year, max_year), step=1)

    causes = st.multiselect(
        "재난원인(여러 개 선택 가능)",
        options=all_causes,
        default=all_causes
    )

    types = st.multiselect(
        "구분(여러 개 선택 가능)",
        options=all_types,
        default=all_types
    )

    view_mode = st.radio(
        "구분 방법(그래프 분리 방식)",
        ["색으로 구분(한 그래프)", "구분별 그래프 나누기(패싯)"],
        index=0
    )

# Apply filters
dff = df[
    (df["연도"] >= year_range[0]) &
    (df["연도"] <= year_range[1]) &
    (df["재난원인"].isin(causes)) &
    (df["구분"].isin(types))
].copy()

# -----------------------------
# Summary KPIs
# -----------------------------
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("선택된 재난원인 수", len(causes))
with c2:
    st.metric("선택된 구분 수", len(types))
with c3:
    st.metric("표본 행 수", len(dff))

st.divider()

# -----------------------------
# Chart 1: Yearly trend (line)
# -----------------------------
st.subheader("1) 연도별 추세 (라인차트)")

if dff.empty:
    st.warning("필터 결과가 비었습니다. 조건을 바꿔보세요.")
    st.stop()

# 합쳐서 보기(원인+구분을 한 번에 구분 가능하게 라벨 생성)
dff["라벨"] = dff["재난원인"] + " | " + dff["구분"]

if view_mode.startswith("색으로"):
    fig1 = px.line(
        dff,
        x="연도",
        y="금액",
        color="라벨",
        markers=True,
        hover_data=["재난원인", "구분", "연도", "금액"],
        title="연도별 피해(금액) 변화"
    )
else:
    fig1 = px.line(
        dff,
        x="연도",
        y="금액",
        color="재난원인",
        facet_col="구분",
        facet_col_wrap=2,
        markers=True,
        hover_data=["재난원인", "구분", "연도", "금액"],
        title="연도별 피해(금액) 변화 (구분별 분리)"
    )
    fig1.for_each_annotation(lambda a: a.update(text=a.text.replace("구분=", "구분: ")))

st.plotly_chart(fig1, use_container_width=True)

# -----------------------------
# Chart 2: Total by cause (bar)
# -----------------------------
st.subheader("2) 기간 합계 비교 (막대그래프)")

agg_cause = (
    dff.groupby(["재난원인"], as_index=False)["금액"]
    .sum()
    .sort_values("금액", ascending=False)
)

fig2 = px.bar(
    agg_cause,
    x="금액",
    y="재난원인",
    orientation="h",
    hover_data=["재난원인", "금액"],
    title=f"{year_range[0]}~{year_range[1]} 기간 합계(재난원인별)"
)
st.plotly_chart(fig2, use_container_width=True)

# -----------------------------
# Chart 3: Heatmap (cause x year)
# -----------------------------
st.subheader("3) 히트맵 (재난원인 × 연도)")

pivot = (
    dff.groupby(["재난원인", "연도"], as_index=False)["금액"].sum()
    .pivot(index="재난원인", columns="연도", values="금액")
    .fillna(0)
)

fig3 = px.imshow(
    pivot,
    aspect="auto",
    labels=dict(x="연도", y="재난원인", color="금액"),
    title="재난원인-연도별 금액 히트맵(값이 큰 해가 진하게 보임)"
)
st.plotly_chart(fig3, use_container_width=True)

# -----------------------------
# Data table + download
# -----------------------------
st.subheader("4) 데이터 테이블 & 다운로드")

st.dataframe(dff, use_container_width=True)

csv_bytes = dff.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
st.download_button(
    "현재 필터 결과 CSV 다운로드",
    data=csv_bytes,
    file_name="filtered_natural_disaster_damage.csv",
    mime="text/csv"
)
