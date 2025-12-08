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
st.title("📞 보이스피싱 대시보드 (Red-Black Tree로 기간 검색)")


# ----------------------------
# 1) 파일 로드 (현재 작업폴더가 루트든 pages든 둘 다 대응)
# ----------------------------
def pick(*cands: str) -> Path:
    """후보 경로들 중 실제 존재하는 파일을 하나 고른다."""
    for s in cands:
        p = Path(s)
        if p.exists():
            return p
    raise FileNotFoundError(f"CSV를 못 찾음: {cands}")

def read_csv_smart(path: Path) -> pd.DataFrame:
    """공공데이터 CSV 인코딩(utf-8-sig/cp949/euc-kr 등) 자동 시도해서 읽는다."""
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(path, encoding="utf-8", encoding_errors="ignore")

def num(s: pd.Series) -> pd.Series:
    """콤마/공백 제거 후 숫자로 변환(실패는 NaN)."""
    return pd.to_numeric(
        s.astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )

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
    """월별 CSV에서 (date, count)만 뽑아 시계열 DataFrame으로 만든다."""
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
    """연도별 CSV에서 year(정수)를 만들고 연도순으로 정렬한다."""
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
# 3) Red-Black Tree 구현 (범위 조회: lower_bound + successor)
# ----------------------------
RED = 1
BLACK = 0

@dataclass
class RBNode:
    k: Any
    v: Any
    color: int = RED
    left: "RBNode|None" = None
    right: "RBNode|None" = None
    parent: "RBNode|None" = None

class RBTree:
    def __init__(self):
        # NIL 센티넬 노드(리프 역할, 항상 BLACK)
        self.nil = RBNode(k=None, v=None, color=BLACK)
        self.nil.left = self.nil.right = self.nil.parent = self.nil
        self.root = self.nil

    def _left_rotate(self, x: RBNode) -> None:
        y = x.right
        x.right = y.left
        if y.left != self.nil:
            y.left.parent = x
        y.parent = x.parent
        if x.parent == self.nil:
            self.root = y
        elif x == x.parent.left:
            x.parent.left = y
        else:
            x.parent.right = y
        y.left = x
        x.parent = y

    def _right_rotate(self, x: RBNode) -> None:
        y = x.left
        x.left = y.right
        if y.right != self.nil:
            y.right.parent = x
        y.parent = x.parent
        if x.parent == self.nil:
            self.root = y
        elif x == x.parent.right:
            x.parent.right = y
        else:
            x.parent.left = y
        y.right = x
        x.parent = y

    def _find_node(self, key: Any) -> RBNode:
        cur = self.root
        while cur != self.nil:
            if key == cur.k:
                return cur
            cur = cur.left if key < cur.k else cur.right
        return self.nil

    def insert(self, key: Any, value: Any) -> None:
        # 중복 키면 값만 갱신
        existing = self._find_node(key)
        if existing != self.nil:
            existing.v = value
            return

        # 새 노드는 RED로 삽입
        z = RBNode(k=key, v=value, color=RED, left=self.nil, right=self.nil, parent=self.nil)

        # BST 규칙대로 삽입 위치 찾기
        y = self.nil
        x = self.root
        while x != self.nil:
            y = x
            x = x.left if z.k < x.k else x.right

        z.parent = y
        if y == self.nil:
            self.root = z
        elif z.k < y.k:
            y.left = z
        else:
            y.right = z

        # 색 규칙 깨진 부분 복구
        self._insert_fixup(z)

    def _insert_fixup(self, z: RBNode) -> None:
        while z.parent.color == RED:
            if z.parent == z.parent.parent.left:
                y = z.parent.parent.right  # 삼촌(uncle)
                if y.color == RED:
                    # Case 1: 삼촌이 RED -> recolor
                    z.parent.color = BLACK
                    y.color = BLACK
                    z.parent.parent.color = RED
                    z = z.parent.parent
                else:
                    if z == z.parent.right:
                        # Case 2: 꺾임 -> 회전으로 일자 만들기
                        z = z.parent
                        self._left_rotate(z)
                    # Case 3: 일자 -> 회전 + recolor
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._right_rotate(z.parent.parent)
            else:
                # 좌우 대칭(미러)
                y = z.parent.parent.left
                if y.color == RED:
                    z.parent.color = BLACK
                    y.color = BLACK
                    z.parent.parent.color = RED
                    z = z.parent.parent
                else:
                    if z == z.parent.left:
                        z = z.parent
                        self._right_rotate(z)
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._left_rotate(z.parent.parent)
        self.root.color = BLACK

    def _minimum(self, x: RBNode) -> RBNode:
        while x.left != self.nil:
            x = x.left
        return x

    def successor(self, x: RBNode) -> RBNode:
        if x.right != self.nil:
            return self._minimum(x.right)
        y = x.parent
        while y != self.nil and x == y.right:
            x = y
            y = y.parent
        return y

    def lower_bound(self, key: Any) -> RBNode:
        """key 이상인 가장 작은 노드"""
        cur = self.root
        res = self.nil
        while cur != self.nil:
            if cur.k >= key:
                res = cur
                cur = cur.left
            else:
                cur = cur.right
        return res

    def range_items(self, lo: Any, hi: Any) -> List[Tuple[Any, Any]]:
        """[lo, hi] 범위의 (key, value)들을 오름차순으로 반환"""
        out: List[Tuple[Any, Any]] = []
        x = self.lower_bound(lo)
        while x != self.nil and x.k <= hi:
            out.append((x.k, x.v))
            x = self.successor(x)
        return out


@st.cache_resource(show_spinner=False)
def build_month_tree(df: pd.DataFrame) -> RBTree:
    """월별 date->count를 RBT에 넣어 트리를 만든다(캐시됨)."""
    t = RBTree()
    for k, v in zip(df["date"].tolist(), df["count"].tolist()):
        t.insert(k, float(v))
    return t

@st.cache_resource(show_spinner=False)
def build_year_tree(df: pd.DataFrame) -> RBTree:
    """연도 year->row(dict)를 RBT에 넣어 트리를 만든다(캐시됨)."""
    t = RBTree()
    for y, row in zip(df["year"].tolist(), df.to_dict("records")):
        t.insert(int(y), row)
    return t

mtree = build_month_tree(mdf)
ytree = build_year_tree(ydf)


# ----------------------------
# 4) UI 공통
# ----------------------------
with st.sidebar:
    view = st.radio("보기", ["월별(기간 선택)", "연도별(기간 선택)"])


# ----------------------------
# 5) 월별(기간 선택) 화면 (라인만)
# ----------------------------
if view == "월별(기간 선택)":
    min_d, max_d = mdf["date"].min().date(), mdf["date"].max().date()
    with st.sidebar:
        start = st.date_input("시작", value=min_d, min_value=min_d, max_value=max_d)
        end = st.date_input("끝", value=max_d, min_value=min_d, max_value=max_d)

    if pd.to_datetime(start) > pd.to_datetime(end):
        st.error("시작 날짜가 끝 날짜보다 늦어.")
        st.stop()

    lo = pd.to_datetime(start)
    hi = pd.to_datetime(end)
    out = mtree.range_items(lo, hi)
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
# 6) 연도별(기간 선택) 화면
# ----------------------------
else:
    min_y, max_y = int(ydf["year"].min()), int(ydf["year"].max())

    # 숫자형 지표 컬럼 자동 추출
    candidates: List[str] = []
    for c in ydf.columns:
        if c in ("year",):
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

    out = ytree.range_items(yr_lo, yr_hi)
    if not out:
        st.warning("해당 연도 범위 데이터가 없어.")
        st.stop()

    rows = [r for _, r in sorted(out, key=lambda x: x[0])]
    tdf = pd.DataFrame(rows)
    tdf["year"] = pd.to_numeric(tdf.get("year", tdf.get("구분")), errors="coerce").astype("Int64")

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
