# pages/voicefishing.py
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


# ----------------------------
# 0) Streamlit 기본 설정
# ----------------------------
st.set_page_config(page_title="보이스피싱", layout="wide")
st.title("📞 보이스피싱 대시보드 (BST로 기간 검색)")


# ----------------------------
# 1) 파일 로드 (현재 작업폴더가 루트든 pages든 둘 다 대응)
# ----------------------------
def pick(*cands: str) -> Path:
    for s in cands:
        p = Path(s)
        if p.exists():
            return p
    raise FileNotFoundError(f"CSV를 못 찾음: {cands}")

def read_csv_smart(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(path, encoding="utf-8", encoding_errors="ignore")

def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )

# 루트에서 실행하든 pages에서 실행하든 찾도록 후보 여러 개
monthly_path = pick(
    "police_voicephishing_monthly.csv",
    "../police_voicephishing_monthly.csv",
    "data/police_voicephishing_monthly.csv",
    "../data/police_voicephishing_monthly.csv",
)
yearly_path = pick(
    "police_voicephishing_yearly.csv",
    "../police_voicephishing_yearly.csv",
    "data/police_voicephishing_yearly.csv",
    "../data/police_voicephishing_yearly.csv",
)

with st.expander("🔎 파일 경로 확인"):
    st.write("월별 CSV:", str(monthly_path))
    st.write("연도별 CSV:", str(yearly_path))

mraw = read_csv_smart(monthly_path)
yraw = read_csv_smart(yearly_path)
mraw.columns = mraw.columns.astype(str).str.strip()
yraw.columns = yraw.columns.astype(str).str.strip()


# ----------------------------
# 2) 월별/연도별 전처리
# ----------------------------
def prepare_monthly(df: pd.DataFrame) -> pd.DataFrame:
    ycol = next((c for c in df.columns if re.search(r"연도|년도|년", c)), None)
    mcol = next((c for c in df.columns if re.search(r"월", c)), None)
    ccol = next((c for c in df.columns if ("발생" in c and "건수" in c)), None)
    if not (ycol and mcol and ccol):
        raise ValueError(f"월별 CSV 컬럼 인식 실패: {list(df.columns)}")

    d = df.copy()
    d[ycol], d[mcol], d[ccol] = num(d[ycol]), num(d[mcol]), num(d[ccol])

    d["date"] = pd.to_datetime(
        d[ycol].astype("Int64").astype(str)
        + "-"
        + d[mcol].astype("Int64").astype(str).str.zfill(2)
        + "-01",
        errors="coerce",
    )
    d = d.dropna(subset=["date"]).sort_values("date")
    out = d[["date", ccol]].rename(columns={ccol: "count"}).copy()
    out["count"] = out["count"].fillna(0).astype(float)
    return out.reset_index(drop=True)

def prepare_yearly(df: pd.DataFrame) -> pd.DataFrame:
    year_col = "구분" if "구분" in df.columns else next(
        (c for c in df.columns if ("연도" in c or "년도" in c or str(c).endswith("년"))),
        df.columns[0],
    )
    d = df.copy()
    d["year"] = num(d[year_col])
    d = d.dropna(subset=["year"]).copy()
    d["year"] = d["year"].astype(int)
    d = d.sort_values("year").reset_index(drop=True)
    return d

mdf = prepare_monthly(mraw)
ydf = prepare_yearly(yraw)


# ----------------------------
# 3) BST 구현 (기간 범위 검색용)
# ----------------------------
@dataclass
class Node:
    k: Any
    v: Any
    l: Optional["Node"] = None
    r: Optional["Node"] = None
    mn: Any = None
    mx: Any = None

def build(items: List[Tuple[Any, Any]]) -> Optional[Node]:
    """정렬된 (key, value) 리스트로 균형에 가까운 BST 생성"""
    if not items:
        return None
    mid = len(items) // 2
    k, v = items[mid]
    n = Node(k, v, build(items[:mid]), build(items[mid + 1 :]))

    mins = [n.k]
    maxs = [n.k]
    if n.l:
        mins.append(n.l.mn); maxs.append(n.l.mx)
    if n.r:
        mins.append(n.r.mn); maxs.append(n.r.mx)
    n.mn = min(mins)
    n.mx = max(maxs)
    return n

def collect(n: Optional[Node], lo: Any, hi: Any, out: List[Tuple[Any, Any]]) -> None:
    """[lo, hi] 범위에 들어오는 노드만 inorder 순서로 수집"""
    if (not n) or (n.mx < lo) or (n.mn > hi):
        return  # 서브트리 전체가 범위 밖이면 스킵
    collect(n.l, lo, hi, out)
    if lo <= n.k <= hi:
        out.append((n.k, n.v))
    collect(n.r, lo, hi, out)

# 월별 트리: key = date, value = count
mtree = build(list(zip(mdf["date"].tolist(), mdf["count"].tolist())))
# 연도별 트리: key = year, value = 해당 행(dict)
ytree = build(list(zip(ydf["year"].tolist(), ydf.to_dict("records"))))


# ----------------------------
# 4) UI 공통
# ----------------------------
with st.sidebar:
    view = st.radio("보기", ["월별(기간 선택)", "연도별(기간 선택)"])


# ----------------------------
# 5) 월별(기간 선택) 화면 (✅ 막대그래프 제거, 라인만)
# ----------------------------
if view == "월별(기간 선택)":
    min_d, max_d = mdf["date"].min().date(), mdf["date"].max().date()
    with st.sidebar:
        start = st.date_input("시작", value=min_d, min_value=min_d, max_value=max_d)
        end = st.date_input("끝", value=max_d, min_value=min_d, max_value=max_d)

    if pd.to_datetime(start) > pd.to_datetime(end):
        st.error("시작 날짜가 끝 날짜보다 늦어.")
        st.stop()

    out: List[Tuple[pd.Timestamp, float]] = []
    collect(mtree, pd.to_datetime(start), pd.to_datetime(end), out)
    if not out:
        st.warning("해당 기간 데이터가 없어.")
        st.stop()

    fdf = pd.DataFrame(out, columns=["date", "count"]).sort_values("date")

    a, b, c = st.columns(3)
    a.metric("총합", f"{int(fdf['count'].sum()):,}")
    b.metric("평균", f"{fdf['count'].mean():,.1f}")
    c.metric("개월 수", f"{len(fdf):,}")

    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.plot(fdf["date"], fdf["count"], marker="o", linewidth=2)
    ax.set_xlabel("월")
    ax.set_ylabel("발생건수")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    st.pyplot(fig, use_container_width=True, clear_figure=True)

    st.subheader("📄 필터된 월별 데이터")
    st.dataframe(fdf, use_container_width=True)


# ----------------------------
# 6) 연도별(기간 선택) 화면 (그대로)
# ----------------------------
else:
    min_y, max_y = int(ydf["year"].min()), int(ydf["year"].max())

    # 숫자형 지표 컬럼 자동 추출
    candidates: List[str] = []
    for c in ydf.columns:
        if c in ("year",):  # 내부 컬럼 제외
            continue
        s = num(ydf[c])
        if s.notna().mean() >= 0.4:
            candidates.append(c)

    if not candidates:
        st.error("연도별 CSV에서 숫자형 지표 컬럼을 찾지 못했어.")
        st.write("현재 컬럼:", list(ydf.columns))
        st.stop()

    with st.sidebar:
        yr_lo, yr_hi = st.slider("연도 범위", min_y, max_y, (min_y, max_y))
        chosen = st.multiselect(
            "그릴 지표(여러 개 가능)",
            options=candidates,
            default=candidates[:2] if len(candidates) >= 2 else candidates[:1],
        )

    if not chosen:
        st.info("사이드바에서 지표를 최소 1개 선택해줘.")
        st.stop()

    out: List[Tuple[int, Dict[str, Any]]] = []
    collect(ytree, yr_lo, yr_hi, out)
    if not out:
        st.warning("해당 연도 범위 데이터가 없어.")
        st.stop()

    rows = [r for _, r in sorted(out, key=lambda x: x[0])]
    tdf = pd.DataFrame(rows)
    # 연도 컬럼 보정
    tdf["year"] = pd.to_numeric(tdf.get("year", tdf.get("구분")), errors="coerce").astype("Int64")

    # 선택된 컬럼 숫자화
    for c in chosen:
        tdf[c] = num(tdf[c])

    st.subheader(f"📊 연도별 비교: {yr_lo} ~ {yr_hi}")
    fig, ax = plt.subplots(figsize=(10, 4.6))
    for c in chosen:
        ax.plot(tdf["year"], tdf[c], marker="o", linewidth=2, label=c)

    ax.set_xlabel("연도")
    ax.set_ylabel("값")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    ax.set_xticks(sorted(tdf["year"].dropna().astype(int).unique()))
    st.pyplot(fig, use_container_width=True, clear_figure=True)

    st.subheader("📄 필터된 연도별 데이터")
    st.dataframe(tdf[["year"] + chosen], use_container_width=True)
