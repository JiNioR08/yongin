import re
from pathlib import Path

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

st.title("📞 보이스피싱 (RBT 기간 검색)")

def read_csv_smart(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(path, encoding="utf-8", encoding_errors="ignore")

def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")

# ---- 여기부터 에러를 화면에 보여주기 위해 통으로 감싼다 ----
try:
    ROOT = Path(__file__).resolve().parents[1]
    monthly_path = ROOT / "police_voicephishing_monthly.csv"
    yearly_path  = ROOT / "police_voicephishing_yearly.csv"

    with st.expander("🔎 파일 확인"):
        st.write("ROOT:", str(ROOT))
        st.write("월별 존재?", monthly_path.exists(), str(monthly_path))
        st.write("연도별 존재?", yearly_path.exists(), str(yearly_path))

    if not monthly_path.exists() or not yearly_path.exists():
        st.error("CSV 파일명이 다르거나 위치가 다름. (루트에 csv가 있어야 함)")
        st.stop()

    mraw = read_csv_smart(monthly_path)
    yraw = read_csv_smart(yearly_path)
    mraw.columns = mraw.columns.astype(str).str.strip()
    yraw.columns = yraw.columns.astype(str).str.strip()

    # --- 월별 전처리 ---
    ycol = next((c for c in mraw.columns if re.search(r"연도|년도|년", c)), None)
    mcol = next((c for c in mraw.columns if re.search(r"월", c)), None)
    ccol = next((c for c in mraw.columns if ("발생" in c and "건수" in c)), None)
    if not (ycol and mcol and ccol):
        raise ValueError(f"월별 컬럼 인식 실패: {list(mraw.columns)}")

    mdf = mraw.copy()
    mdf[ycol], mdf[mcol], mdf[ccol] = num(mdf[ycol]), num(mdf[mcol]), num(mdf[ccol])
    mdf["date"] = pd.to_datetime(
        mdf[ycol].astype("Int64").astype(str) + "-" +
        mdf[mcol].astype("Int64").astype(str).str.zfill(2) + "-01",
        errors="coerce"
    )
    mdf = mdf.dropna(subset=["date"]).sort_values("date")
    mdf = mdf[["date", ccol]].rename(columns={ccol: "count"}).reset_index(drop=True)
    mdf["count"] = mdf["count"].fillna(0).astype(float)

    # --- (간단) RBT 구현: 범위검색에 필요한 것만 ---
    RED, BLACK = 1, 0
    class Node:
        __slots__ = ("k","v","c","l","r","p")
        def __init__(self, k=None, v=None, c=BLACK):
            self.k, self.v, self.c = k, v, c
            self.l = self.r = self.p = None

    class RBTree:
        def __init__(self):
            self.nil = Node(c=BLACK)
            self.nil.l = self.nil.r = self.nil.p = self.nil
            self.root = self.nil

        def _lrot(self, x):
            y = x.r
            x.r = y.l
            if y.l != self.nil: y.l.p = x
            y.p = x.p
            if x.p == self.nil: self.root = y
            elif x == x.p.l: x.p.l = y
            else: x.p.r = y
            y.l = x
            x.p = y

        def _rrot(self, x):
            y = x.l
            x.l = y.r
            if y.r != self.nil: y.r.p = x
            y.p = x.p
            if x.p == self.nil: self.root = y
            elif x == x.p.r: x.p.r = y
            else: x.p.l = y
            y.r = x
            x.p = y

        def insert(self, k, v):
            z = Node(k, v, RED)
            z.l = z.r = z.p = self.nil
            y = self.nil
            x = self.root
            while x != self.nil:
                y = x
                x = x.l if k < x.k else x.r
            z.p = y
            if y == self.nil: self.root = z
            elif k < y.k: y.l = z
            else: y.r = z
            self._fix(z)

        def _fix(self, z):
            while z.p.c == RED:
                if z.p == z.p.p.l:
                    u = z.p.p.r
                    if u.c == RED:
                        z.p.c = BLACK; u.c = BLACK; z.p.p.c = RED
                        z = z.p.p
                    else:
                        if z == z.p.r:
                            z = z.p; self._lrot(z)
                        z.p.c = BLACK; z.p.p.c = RED
                        self._rrot(z.p.p)
                else:
                    u = z.p.p.l
                    if u.c == RED:
                        z.p.c = BLACK; u.c = BLACK; z.p.p.c = RED
                        z = z.p.p
                    else:
                        if z == z.p.l:
                            z = z.p; self._rrot(z)
                        z.p.c = BLACK; z.p.p.c = RED
                        self._lrot(z.p.p)
            self.root.c = BLACK

        def _min(self, x):
            while x.l != self.nil: x = x.l
            return x

        def succ(self, x):
            if x.r != self.nil: return self._min(x.r)
            y = x.p
            while y != self.nil and x == y.r:
                x = y; y = y.p
            return y

        def lower_bound(self, k):
            x = self.root
            res = self.nil
            while x != self.nil:
                if x.k >= k:
                    res = x; x = x.l
                else:
                    x = x.r
            return res

        def range_items(self, lo, hi):
            out = []
            x = self.lower_bound(lo)
            while x != self.nil and x.k <= hi:
                out.append((x.k, x.v))
                x = self.succ(x)
            return out

    t = RBTree()
    for d, cnt in zip(mdf["date"].tolist(), mdf["count"].tolist()):
        t.insert(d, float(cnt))

    # --- UI (키 붙여서 충돌도 예방) ---
    min_d, max_d = mdf["date"].min().date(), mdf["date"].max().date()
    start = st.date_input("시작", value=min_d, min_value=min_d, max_value=max_d, key="vf_start")
    end   = st.date_input("끝", value=max_d, min_value=min_d, max_value=max_d, key="vf_end")

    if pd.to_datetime(start) > pd.to_datetime(end):
        st.error("시작 날짜가 끝 날짜보다 늦다.")
        st.stop()

    out = t.range_items(pd.to_datetime(start), pd.to_datetime(end))
    if not out:
        st.warning("해당 기간 데이터가 없다.")
        st.stop()

    fdf = pd.DataFrame(out, columns=["date","count"]).sort_values("date")

    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.plot(fdf["date"], fdf["count"], marker="o", linewidth=2)
    ax.set_xlabel("월"); ax.set_ylabel("발생건수")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    st.pyplot(fig, use_container_width=True)

    st.dataframe(fdf, use_container_width=True)

except Exception as e:
    st.error("진짜 에러 원인이 아래에 뜬다:")
    st.exception(e)
    st.stop()
