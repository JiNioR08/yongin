import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


# ✅ pages에서는 set_page_config() 쓰지 말 것
st.title("📞 보이스피싱 대시보드 (Red-Black Tree 기간 검색)")


# ----------------------------
# A) CSV 로딩 유틸
# ----------------------------
ROOT = Path(__file__).resolve().parents[1]  # 레포 루트(= main.py 있는 곳)

MONTHLY_CANDS = [
    ROOT / "police_voicephishing_monthly.csv",
    ROOT / "data" / "police_voicephishing_monthly.csv",
]
YEARLY_CANDS = [
    ROOT / "police_voicephishing_yearly.csv",
    ROOT / "data" / "police_voicephishing_yearly.csv",
]


def pick_existing(cands: List[Path]) -> Path:
    for p in cands:
        if p.exists():
            return p
    raise FileNotFoundError(f"CSV를 못 찾음: {[str(x) for x in cands]}")


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


monthly_path = pick_existing(MONTHLY_CANDS)
yearly_path = pick_existing(YEARLY_CANDS)

with st.expander("🔎 파일 경로 확인"):
    st.write("ROOT:", str(ROOT))
    st.write("월별 CSV:", str(monthly_path))
    st.write("연도별 CSV:", str(yearly_path))

mraw = read_csv_smart(monthly_path)
yraw = read_csv_smart(yearly_path)
mraw.columns = mraw.columns.astype(str).str.strip()
yraw.columns = yraw.columns.astype(str).str.strip()


def prepare_monthly(df: pd.DataFrame) -> pd.DataFrame:
    ycol = next((c for c in df.columns if re.search(r"연도|년도|년", c)), None)
    mcol = next((c for c in df.columns if re.search(r"월", c)), None)
    ccol = next((c for c in df.columns if ("발생" in c and "건수" in c)), None)
    if not (ycol and mcol and ccol):
        raise ValueError(f"월별 컬럼 인식 실패: {list(df.columns)}")

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
    return d.sort_values("year").reset_index(drop=True)


mdf = prepare_monthly(mraw)
ydf = prepare_yearly(yraw)


# ----------------------------
# B) Red-Black Tree (RBT)
# ----------------------------
RED = 1
BLACK = 0


@dataclass
class RBNode:
    k: Any
    v: Any
    color: int = RED
    left: Optional["RBNode"] = None
    right: Optional["RBNode"] = None
    parent: Optional["RBNode"] = None


class RBTree:
    def __init__(self):
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

    def _find(self, key: Any) -> RBNode:
        cur = self.root
        while cur != self.nil:
            if key == cur.k:
                return cur
            cur = cur.left if key < cur.k else cur.right
        return self.nil

    def insert(self, key: Any, value: Any) -> None:
        # 중복이면 업데이트
        ex = self._find(key)
        if ex != self.nil:
            ex.v = value
            return

        z = RBNode(k=key, v=value, color=RED, left=self.nil, right=self.nil, parent=self.nil)

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

        self._insert_fixup(z)

    def _insert_fixup(self, z: RBNode) -> None:
        while z.parent.color == RED:
            if z.parent == z.parent.parent.left:
                u = z.parent.parent.right  # 삼촌
                if u.color == RED:
                    z.parent.color = BLACK
                    u.color = BLACK
                    z.parent.parent.color = RED
                    z = z.parent.parent
                else:
                    if z == z.parent.right:
                        z = z.parent
                        self._left_rotate(z)
                    z.parent.color = BLACK
                    z.parent.parent.color = RED
                    self._right_rotate(z.parent.parent)
            else:
                u = z.parent.parent.left
                if u.color == RED:
                    z.parent.color = BLACK
                    u.color = BLACK
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
        out: List[Tuple[Any, Any]] = []
        x = self.lower_bound(lo)
        while x != self.nil and x.k <= hi:
            out.append((x.k, x.v))
            x = self.successor(x)
        return out


def get_tree_month() -> RBTree:
    key = "mtree_rbt"
    if key not in st.session_state:
        t = RBTree()
        for k, v in zip(mdf["date"].tolist(), mdf["count"].tolist()):
            t.insert(k, float(v))
        st.session_state[key] = t
    return st.session_state[key]


def get_tree_year() -> RBTree:
    key = "ytree_rbt"
    if key not in st.session_state:
        t = RBTree()
        for y, row in zip(ydf["year"].tolist(), ydf.to_dict("records")):
            t.insert(int(y), row)
        st.session_state[key] = t
    return st.session_state[key]


mtree = get_tree_month()
ytree = get_tree_year()


# ----------------------------
# C) UI
# ----------------------------
with st.sidebar:
    view = st.radio("보기", ["월별(기간)", "연도별(기간)"])

if view == "월별(기간)":
    min_d, max_d = mdf["date"].min().date(), mdf["date"].max().date()
    with st.sidebar:
        start = st.date_input("시작", value=min_d, min_value=min_d, max_value=max_d)
        end = st.date_input("끝", value=max_d, min_value=min_d, max_value=max_d)

    if pd.to_datetime(start) > pd.to_datetime(end):
        st.error("시작 날짜가 끝 날짜보다 늦다.")
        st.stop()

    lo, hi = pd.to_datetime(start), pd.to_datetime(end)
    out = mtree.range_items(lo, hi)
    if not out:
        st.warning("해당 기간 데이터가 없다.")
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

else:
    min_y, max_y = int(ydf["year"].min()), int(ydf["year"].max())

    candidates: List[str] = []
    for c in ydf.columns:
        if c == "year":
            continue
        s = num(ydf[c])
        if s.notna().mean() >= 0.4:
            candidates.append(c)

    if not candidates:
        st.error("연도별 CSV에서 숫자형 지표 컬럼을 찾지 못했다.")
        st.write("현재 컬럼:", list(ydf.columns))
        st.stop()

    with st.sidebar:
        yr_lo, yr_hi = st.slider("연도 범위", min_y, max_y, (min_y, max_y))
        chosen = st.multiselect("그릴 지표", options=candidates, default=candidates[:1])

    if not chosen:
        st.info("지표를 최소 1개 선택해라.")
        st.stop()

    out = ytree.range_items(yr_lo, yr_hi)
    if not out:
        st.warning("해당 연도 범위 데이터가 없다.")
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
