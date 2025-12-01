import re
import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ---------------------- 파일 경로 ----------------------
mf_path = "202508_202508_연령별인구현황_월간_남녀구분.csv"
total_path = "202508_202508_연령별인구현황_월간_남녀합계.csv"

# ---------------------- CSV 불러오기 ----------------------
mf_df = pd.read_csv(mf_path, encoding='cp949')
total_df = pd.read_csv(total_path, encoding='cp949')

# ---------------------- 컬럼 정리 ----------------------
mf_df.columns = mf_df.columns.str.strip()
total_df.columns = total_df.columns.str.strip()

# ---------------------- 연령 컬럼만 추출 ----------------------
age_cols_mf = [col for col in mf_df.columns if "세" in col]
age_cols_total = [col for col in total_df.columns if "세" in col]

# ---------------------- 숫자 변환(안전) ----------------------
def clean_numeric(df, cols):
    df = df.copy()
    for col in cols:
        s = (df[col].astype(str)
                     .str.replace("\u00a0", "", regex=False)   # NBSP 제거
                     .str.replace(",", "", regex=False)
                     .str.strip())
        df[col] = pd.to_numeric(s, errors="coerce").astype("Int64")  # nullable int
    return df

mf_df = clean_numeric(mf_df, age_cols_mf)
total_df = clean_numeric(total_df, age_cols_total)

# ---------------------- 지역 정규화 ----------------------
def normalize_region_series(s: pd.Series) -> pd.Series:
    """
    - 끝의 (숫자코드) 제거
    - 다중 공백/NBSP 정리
    - '…구 구' 같은 중복 단위 제거
    """
    s = (s.astype(str)
           .str.replace("\u00a0", "", regex=False)
           .str.replace(r"\s+", " ", regex=True)
           .str.replace(r"\s*\([^)]+\)\s*$", "", regex=True)  # (코드) 제거
           .str.strip())
    s = s.str.replace(r"(시|군|구)\s*\1$", r"\1", regex=True)  # 중복 단위
    return s

mf_df["지역"] = normalize_region_series(mf_df["행정구역"])
total_df["지역"] = normalize_region_series(total_df["행정구역"])

# ---------------------- Tab1 전용: 구(또는 시·군) 단위로 묶기 ----------------------
def to_gu_level(name: str) -> str:
    """
    - '... 강남구 역삼동' -> '... 강남구'
    - '... ○○군 △△면' -> '... ○○군'
    - '... ○○시 (구 없음)' -> '... ○○시'
    - 세종특별자치시처럼 단일 시는 전체 유지
    """
    if not isinstance(name, str):
        return name
    name = re.sub(r"\s+", " ", name).strip()

    m_gu = re.match(r"^(.*?구)(?:\s|$)", name)
    if m_gu:
        return m_gu.group(1)

    m_gun = re.match(r"^(.*?군)(?:\s|$)", name)
    if m_gun:
        return m_gun.group(1)

    m_si = re.match(r"^(.*?시)(?:\s|$)", name)
    if m_si:
        return m_si.group(1)

    return name  # 도/특별자치도 등

mf_df["지역_구단위"] = mf_df["지역"].apply(to_gu_level)

# 선택지(중복 제거 후 정렬)
region_options_gu = sorted(mf_df["지역_구단위"].dropna().unique().tolist())

# ---------------------- Tab2 선택지(남녀합계 그대로) ----------------------
region_options_total = sorted(total_df["지역"].dropna().unique().tolist())

# ---------------------- Streamlit UI ----------------------
st.title("🧭 연령별 인구 시각화 대시보드")
tab1, tab2 = st.tabs(["👫 남녀 인구 피라미드", "👥 전체 인구 구조"])

# ---------------------- Tab 1: 남녀 인구 피라미드 (구 단위 선택) ----------------------
with tab1:
    region = st.selectbox("지역 선택 (구 단위)", region_options_gu, key="tab1")

    # 같은 구 단위에 속하는 행 모두 포함(동/읍/면 등 세부는 자동 집계용으로 하나만 사용)
    subset = mf_df[mf_df["지역_구단위"] == region]

    if not subset.empty:
        # 가장 최신/대표 1행 사용 (필요하면 sum으로 집계 가능)
        row = subset.iloc[0]

        male_cols = [col for col in age_cols_mf if "_남_" in col]
        female_cols = [col for col in age_cols_mf if "_여_" in col]
        age_labels = [col.split("_")[-1] for col in male_cols]

        male = row[male_cols].fillna(0).astype(int).values * -1
        female = row[female_cols].fillna(0).astype(int).values

        fig = go.Figure()
        fig.add_trace(go.Bar(x=male, y=age_labels, orientation='h', name='남성', marker_color='blue'))
        fig.add_trace(go.Bar(x=female, y=age_labels, orientation='h', name='여성', marker_color='red'))
        fig.update_layout(
            title=f"{region} 인구 피라미드",
            barmode='relative',
            xaxis=dict(title='인구 수'),
            yaxis=dict(title='연령'),
            height=700
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("해당 지역 데이터가 없습니다.")

# ---------------------- Tab 2: 전체 인구 구조 (남녀합계 파일 사용) ----------------------
with tab2:
    region2 = st.selectbox("지역 선택 (전체 인구)", region_options_total, key="tab2")
    filtered2 = total_df[total_df['지역'] == region2]

    if not filtered2.empty:
        age_labels = [col.split("_")[-1] for col in age_cols_total]
        total_pop = filtered2.iloc[0][age_cols_total].fillna(0).astype(int).values

        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=age_labels, y=total_pop, mode='lines+markers', name='총인구'))
        fig2.update_layout(
            title=f"{region2} 연령별 인구 구조 (남녀합계 기준)",
            xaxis_title='연령',
            yaxis_title='인구 수',
            height=600
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.warning("해당 지역 데이터가 없습니다.")
