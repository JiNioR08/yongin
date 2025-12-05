# ============================================================
# app.py  (Streamlit + Plotly)
# 목적: 보이스피싱 CSV(연도별/월별)를 읽어서
#      전처리(정제) -> 지표 계산 -> 시각화(대시보드)까지 한 번에 보여주기
# ============================================================

import re                            # 컬럼 자동탐색(정규식)용
from pathlib import Path              # 파일 경로 안전 처리용
import streamlit as st                # Streamlit UI
import pandas as pd                   # CSV 로딩/전처리/계산
import plotly.graph_objects as go     # Plotly 그래프

# ---------------------- Streamlit 설정은 반드시 맨 위 ----------------------
st.set_page_config(page_title="보이스피싱 대시보드", layout="wide")
st.title("📞 보이스피싱 공공데이터 대시보드 (CSV 기반)")

# ============================================================
# 0) 파일 경로 설정 (여기만 너 파일명에 맞게 바꾸면 됨)
# ============================================================
BASE_DIR = Path(__file__).parent  # 현재 app.py가 있는 폴더

# 레포 루트에 CSV를 뒀다면 아래처럼
yearly_path = BASE_DIR / "police_voicephishing_yearly.csv"     # 연도별(2016~2024 등)
monthly_path = BASE_DIR / "police_voicephishing_monthly.csv"   # 월별(2018~2025.6 등)

# data 폴더에 넣었다면 예: BASE_DIR / "data" / "파일.csv"
# yearly_path = BASE_DIR / "data" / "police_voicephishing_yearly.csv"
# monthly_path = BASE_DIR / "data" / "police_voicephishing_monthly.csv"


# ============================================================
# 1) CSV 로딩 (인코딩/구분자 자동 대응)
#    - 네가 겪은 'cp949 codec can't decode ...' 같은 오류를 피하려고
#      utf-8-sig / utf-8 / cp949 / euc-kr 순으로 시도
#    - 쉼표(,) 말고 탭(\t), 세미콜론(;) 구분인 CSV도 있어서 같이 시도
# ============================================================
def read_csv_auto(path: Path) -> tuple[pd.DataFrame, str, str]:
    """
    반환값:
      df: DataFrame
      used_encoding: 실제로 성공한 인코딩 문자열
      used_sep: 실제로 성공한 구분자
    """
    encodings = ["utf-8-sig", "utf-8", "cp949", "euc-kr"]   # 공공데이터에서 흔한 순서
    seps = [",", "\t", ";"]                                 # 흔한 구분자 후보

    last_error = None

    for enc in encodings:
        for sep in seps:
            try:
                df = pd.read_csv(path, encoding=enc, sep=sep)

                # CSV를 잘못 읽으면 "컬럼이 1개"로 뭉개지는 경우가 잦음
                # (예: 진짜는 여러 컬럼인데 구분자를 잘못 잡은 경우)
                # 보통 공공데이터는 2개 이상 컬럼이므로 2개 미만이면 다른 sep 시도.
                if df.shape[1] < 2:
                    continue

                return df, enc, sep
            except Exception as e:
                last_error = e

    # 그래도 실패하면 마지막 시도: 깨지는 문자 무시하고 읽기(최후의 수단)
    try:
        df = pd.read_csv(path, encoding="utf-8", encoding_errors="ignore")
        return df, "utf-8(ignore)", "unknown"
    except Exception as e:
        raise RuntimeError(
            f"CSV 로드 실패: {path}\n마지막 오류: {last_error}"
        ) from e


# ============================================================
# 2) 컬럼 정리/숫자 변환 유틸
# ============================================================
def strip_columns(df: pd.DataFrame) -> pd.DataFrame:
    """컬럼명의 앞뒤 공백 제거(공공데이터에서 자주 문제됨)"""
    out = df.copy()
    out.columns = out.columns.astype(str).str.strip()
    return out

def to_number_series(s: pd.Series) -> pd.Series:
    """쉼표/공백 제거 후 숫자로 변환"""
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.strip(), errors="coerce")


# ============================================================
# 3) 컬럼 자동 탐색 유틸(컬럼명이 바뀌어도 최대한 버티게)
# ============================================================
def pick_col_by_patterns(cols: list[str], patterns: list[str]) -> str | None:
    """
    patterns 리스트 중 하나라도 매칭되는 첫 컬럼을 반환.
    (예: 연도/년도/년, 월, 발생건수 등)
    """
    for pat in patterns:
        rx = re.compile(pat)
        for c in cols:
            if rx.search(c):
                return c
    return None

def find_case_count_col(cols: list[str]) -> str | None:
    """
    발생건수 컬럼 찾기:
    - '발생'+'건수'가 같이 있는 게 가장 흔함
    - 또는 '전화금융사기 발생건수' 같은 긴 이름
    """
    for c in cols:
        if ("발생" in c and "건수" in c):
            return c
    # 대체 후보(혹시 표기가 다른 경우)
    for c in cols:
        if "건수" in c:
            return c
    return None

def find_damage_cols(cols: list[str]) -> list[str]:
    """
    피해액 컬럼들(유형별 여러 개)을 모아오기
    - 예: 기관사칭형_피해액_억원, 대출사기형_피해액_억원 ...
    """
    cands = []
    for c in cols:
        if "피해액" in c:
            cands.append(c)
    return cands

def find_case_cols(cols: list[str]) -> list[str]:
    """발생건수 컬럼들(유형별 여러 개)"""
    cands = []
    for c in cols:
        if ("발생" in c and "건수" in c):
            cands.append(c)
    return cands


# ============================================================
# 4) CSV 로드(여기서 실패하면 친절히 안내하고 종료)
# ============================================================
try:
    yearly_df, yearly_enc, yearly_sep = read_csv_auto(yearly_path)
    monthly_df, monthly_enc, monthly_sep = read_csv_auto(monthly_path)
except Exception as e:
    st.error(f"CSV를 못 읽었어: {e}")
    st.info("✅ 체크할 것")
    st.write("1) 파일이 레포/폴더에 실제로 존재하는지(경로/파일명)")
    st.write("2) 인코딩이 cp949가 아닐 수도 있음(utf-8-sig가 많음)")
    st.write("3) 구분자가 쉼표가 아니라 탭/세미콜론일 수도 있음")
    st.stop()

# 컬럼 공백 제거
yearly_df = strip_columns(yearly_df)
monthly_df = strip_columns(monthly_df)

# 로딩 정보(디버깅용) 표시
with st.expander("🔎 로딩 정보(인코딩/구분자/컬럼 목록)"):
    st.write(f"연도별 로딩: encoding={yearly_enc}, sep={repr(yearly_sep)}, rows={len(yearly_df)}, cols={yearly_df.shape[1]}")
    st.write(yearly_df.columns.tolist())
    st.write(f"월별 로딩: encoding={monthly_enc}, sep={repr(monthly_sep)}, rows={len(monthly_df)}, cols={monthly_df.shape[1]}")
    st.write(monthly_df.columns.tolist())


# ============================================================
# 5) 사용자 UI(사이드바)
# ============================================================
with st.sidebar:
    st.header("보기 설정")
    view = st.radio("분석 선택", ["월별 추이(발생건수)", "연도별 비교(유형/피해액/발생)"])

    st.caption("CSV 출처(보고서용)")
    st.write("- 연도별: https://www.data.go.kr/data/15063815/fileData.do")
    st.write("- 월별: https://www.data.go.kr/data/15099013/fileData.do")


# ============================================================
# 6) 월별 추이(발생건수)
#    알고리즘(원리):
#    1) 연도/월/발생건수 컬럼을 자동으로 찾는다.
#    2) 연도+월을 date(YYYY-MM-01)로 만들어 시계열로 변환한다.
#    3) 정렬 후 라인차트로 추세를 보여준다.
# ============================================================
if view == "월별 추이(발생건수)":
    cols = monthly_df.columns.tolist()

    # 연도 컬럼 후보: '년', '연도', '년도', '기준년도' 등
    year_col = pick_col_by_patterns(cols, [r"^년$", r"연도", r"년도", r"년"])
    # 월 컬럼 후보
    mon_col = pick_col_by_patterns(cols, [r"^월$", r"월"])
    # 발생건수 컬럼 후보
    cnt_col = find_case_count_col(cols)

    # 혹시 '기준년월'처럼 합쳐진 컬럼이 있는 경우도 대비
    yyyymm_col = pick_col_by_patterns(cols, [r"년월", r"기준년월"])

    if yyyymm_col and (year_col is None or mon_col is None):
        # '기준년월' 하나로 year/month를 만들 수 있는 경우
        tmp = monthly_df.copy()
        s = tmp[yyyymm_col].astype(str)

        # 숫자만 뽑기(예: '2025.6' / '202506' / '2025-06' 등 보정)
        digits = s.str.replace(r"[^0-9]", "", regex=True)

        # 자리수 보정: 20256 같은 경우 -> 202506(맨 뒤를 월로 간주)
        # 여기서는 "연도 4자리 + 월 1~2자리" 가정
        year = digits.str.slice(0, 4)
        month = digits.str.slice(4, 6).replace("", pd.NA)
        tmp["_year"] = pd.to_numeric(year, errors="coerce")
        tmp["_month"] = pd.to_numeric(month, errors="coerce")

        year_col = "_year"
        mon_col = "_month"
        df = tmp
    else:
        df = monthly_df.copy()

    if not (year_col and mon_col and cnt_col):
        st.error("월별 그래프를 만들 필수 컬럼(년/월/발생건수)을 못 찾았어.")
        st.write("현재 컬럼:", cols)
        st.stop()

    # 숫자 변환(문자열/쉼표 들어있어도 처리)
    df[year_col] = to_number_series(df[year_col])
    df[mon_col] = to_number_series(df[mon_col])
    df[cnt_col] = to_number_series(df[cnt_col])

    # 날짜 생성: YYYY-MM-01
    df["date"] = pd.to_datetime(
        df[year_col].astype("Int64").astype(str) + "-" +
        df[mon_col].astype("Int64").astype(str).str.zfill(2) + "-01",
        errors="coerce"
    )

    # date가 없으면 그래프가 깨지니 제거 + 정렬
    df = df.dropna(subset=["date"]).sort_values("date")

    # 기간 필터(보고서에서 “필터링 가능”이라고 쓰기 좋음)
    min_d = df["date"].min().to_pydatetime()
    max_d = df["date"].max().to_pydatetime()
    start, end = st.slider("기간 선택", min_value=min_d, max_value=max_d, value=(min_d, max_d))
    f = df[(df["date"] >= pd.to_datetime(start)) & (df["date"] <= pd.to_datetime(end))].copy()

    # 요약 지표(핵심 숫자 3개)
    c1, c2, c3 = st.columns(3)
    c1.metric("선택기간 총 발생건수", int(f[cnt_col].sum(skipna=True)))
    c2.metric("월 평균 발생건수", float(f[cnt_col].mean(skipna=True)))
    c3.metric("최대 월 발생건수", int(f[cnt_col].max(skipna=True)))

    # Plotly 라인차트
    st.subheader("📈 월별 발생건수 추이")
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=f["date"], y=f[cnt_col],
        mode="lines+markers",
        name="발생건수"
    ))
    fig.update_layout(xaxis_title="월", yaxis_title="발생건수", height=450)
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("📄 월별 데이터(필터 적용)")
    st.dataframe(f, use_container_width=True)


# ============================================================
# 7) 연도별 비교(유형/피해액/발생)
#    알고리즘(원리):
#    1) 연도 컬럼을 찾고(구분/연도 등) 숫자로 만든다.
#    2) 피해액 컬럼들/발생건수 컬럼들을 키워드로 모은다.
#    3) 연도 축으로 라인차트를 여러 개 그려 유형별 변화 비교를 한다.
# ============================================================
else:
    df = yearly_df.copy()
    cols = df.columns.tolist()

    # 연도 컬럼 찾기: 공공데이터는 '구분'이 연도일 때가 많음
    year_col = "구분" if "구분" in cols else pick_col_by_patterns(cols, [r"연도", r"년도", r"년$"])
    if year_col is None:
        # 최후: 첫 컬럼을 연도로 가정
        year_col = cols[0]

    # 연도를 숫자로 바꾸고(불가능하면 NaN), NaN 제거 + 정렬
    df[year_col] = to_number_series(df[year_col])
    df = df.dropna(subset=[year_col]).sort_values(year_col)

    # 후보 컬럼 찾기
    damage_cols = find_damage_cols(cols)  # 피해액 관련 컬럼들
    case_cols = find_case_cols(cols)      # 발생건수 관련 컬럼들

    # 혹시 피해액이 너무 많이 잡히면(불필요 컬럼 포함) 사용자가 직접 선택 가능하게
    st.subheader("📊 연도별 데이터(표)")
    st.dataframe(df, use_container_width=True)

    # 피해액 그래프
    st.subheader("📈 연도별 피해액 추이(유형별)")
    if damage_cols:
        selected_damage = st.multiselect(
            "표시할 피해액 컬럼 선택",
            options=damage_cols,
            default=damage_cols[: min(3, len(damage_cols))]  # 기본은 앞쪽 3개 정도
        )
        if selected_damage:
            fig = go.Figure()
            for c in selected_damage:
                fig.add_trace(go.Scatter(
                    x=df[year_col],
                    y=to_number_series(df[c]),
                    mode="lines+markers",
                    name=c
                ))
            fig.update_layout(xaxis_title="연도", yaxis_title="피해액", height=450)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("피해액 컬럼을 선택해줘.")
    else:
        st.info("피해액 컬럼을 못 찾았어(컬럼명이 다를 수 있음).")

    # 발생건수 그래프
    st.subheader("📈 연도별 발생건수 추이(유형별)")
    if case_cols:
        selected_case = st.multiselect(
            "표시할 발생건수 컬럼 선택",
            options=case_cols,
            default=case_cols[: min(3, len(case_cols))]
        )
        if selected_case:
            fig = go.Figure()
            for c in selected_case:
                fig.add_trace(go.Scatter(
                    x=df[year_col],
                    y=to_number_series(df[c]),
                    mode="lines+markers",
                    name=c
                ))
            fig.update_layout(xaxis_title="연도", yaxis_title="발생건수", height=450)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("발생건수 컬럼을 선택해줘.")
    else:
        st.info("발생건수 컬럼을 못 찾았어(컬럼명이 다를 수 있음).")


# ============================================================
# 8) 출처(보고서용 문장)
# ============================================================
st.divider()
st.caption("데이터 출처: 공공데이터포털(경찰청) 보이스피싱 현황/월별 현황 CSV")
