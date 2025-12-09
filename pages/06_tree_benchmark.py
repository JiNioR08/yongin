import time
import random
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
import pandas as pd


st.title("🌲 BST vs Red-Black Tree 성능 비교(직접 실험)")


# -----------------------------
# 데이터 로드(월별만 사용: date->count)
# -----------------------------
ROOT = Path(__file__).resolve().parents[1]
MONTHLY = ROOT / "police_voicephishing_monthly.csv"

def read_csv_smart(p: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return pd.read_csv(p, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(p, encoding="utf-8", encoding_errors="ignore")

def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")

mraw = read_csv_smart(MONTHLY)
mraw.columns = mraw.columns.astype(str).str.strip()

# 컬럼 자동 탐색(너가 쓰던 방식 유지)
import re
ycol = next((c for c in mraw.columns if re.search(r"연도|년도|년", c)), None)
mcol = next((c for c in mraw.columns if re.search(r"월", c)), None)
ccol = next((c for c in mraw.columns if ("발생" in c and "건수" in c)), None)
if not (ycol and mcol and ccol):
    st.error(f"월별 컬럼 인식 실패: {list(mraw.columns)}")
    st.stop()

df = mraw.copy()
df[ycol], df[mcol], df[ccol] = num(df[ycol]), num(df[mcol]), num(df[ccol])
df["date"] = pd.to_datetime(
    df[ycol].astype("Int64").astype(str) + "-" + df[mcol].astype("Int64").astype(str).str.zfill(2) + "-01",
    errors="coerce"
)
df = df.dropna(subset=["date"]).sort_values("date")
df = df[["date", ccol]].rename(columns={ccol: "count"}).reset_index(drop=True)
df["count"] = df["count"].fillna(0).astype(float)

base_items = list(zip(df["date"].tolist(), df["count"].tolist()))
n_base = len(base_items)

with st.expander("🔎 데이터 확인"):
    st.write("데이터 개수(월):", n_base)
    st.dataframe(df, use_container_width=True)


# -----------------------------
# BST (일반, 불균형 가능)
# -----------------------------
@dataclass
class BSTNode:
    k: object
    v: object
    left: "BSTNode|None" = None
    right: "BSTNode|None" = None
    parent: "BSTNode|None" = None

class BST:
    def __init__(self):
        self.root = None

    def insert(self, k, v):
        if self.root is None:
            self.root = BSTNode(k, v)
            return
        cur = self.root
        parent = None
        while cur is not None:
            parent = cur
            if k == cur.k:
                cur.v = v
                return
            cur = cur.left if k < cur.k else cur.right
        node = BSTNode(k, v, parent=parent)
        if k < parent.k:
            parent.left = node
        else:
            parent.right = node

    def _minimum(self, x):
        while x.left is not None:
            x = x.left
        return x

    def successor(self, x):
        if x.right is not None:
            return self._minimum(x.right)
        y = x.parent
        while y is not None and x == y.right:
            x = y
            y = y.parent
        return y

    def lower_bound(self, k):
        cur = self.root
        res = None
        while cur is not None:
            if cur.k >= k:
                res = cur
                cur = cur.left
            else:
                cur = cur.right
        return res

    def range_items(self, lo, hi):
        out = []
        x = self.lower_bound(lo)
        while x is not None and x.k <= hi:
            out.append((x.k, x.v))
            x = self.successor(x)
        return out

    def height(self):
        def h(x):
            if x is None: return 0
            return 1 + max(h(x.left), h(x.right))
        return h(self.root)


# -----------------------------
# Red-Black Tree (최악 O(log n) 보장)
# -----------------------------
RED, BLACK = 1, 0

class RBNode:
    __slots__ = ("k","v","c","l","r","p")
    def __init__(self, k=None, v=None, c=BLACK):
        self.k, self.v, self.c = k, v, c
        self.l = self.r = self.p = None

class RBTree:
    def __init__(self):
        self.nil = RBNode(c=BLACK)
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
        z = RBNode(k, v, RED)
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

    def height(self):
        def h(x):
            if x == self.nil: return 0
            return 1 + max(h(x.l), h(x.r))
        return h(self.root)


# -----------------------------
# 벤치마크
# -----------------------------
def make_items(mult: int, order: str, seed: int):
    # 데이터를 크게 만들어 차이를 “체감” 가능하게 (날짜는 1일씩 밀어서 유니크 유지)
    items = []
    for t in range(mult):
        for d, c in base_items:
            items.append((d + pd.Timedelta(days=t * 400), c))  # 날짜 중복 방지(대충 400일씩 띄움)
    if order == "정렬(최악: BST가 한쪽으로 쏠림)":
        items.sort(key=lambda x: x[0])
    elif order == "역순(최악)":
        items.sort(key=lambda x: x[0], reverse=True)
    else:
        rnd = random.Random(seed)
        rnd.shuffle(items)
    return items

def make_ranges(keys, q: int, seed: int):
    rnd = random.Random(seed)
    n = len(keys)
    ranges = []
    for _ in range(q):
        i = rnd.randrange(0, n)
        j = rnd.randrange(0, n)
        lo = keys[min(i, j)]
        hi = keys[max(i, j)]
        ranges.append((lo, hi))
    return ranges

def bench(items, ranges):
    # build
    t0 = time.perf_counter()
    bst = BST()
    for k, v in items:
        bst.insert(k, v)
    t1 = time.perf_counter()

    rbt = RBTree()
    for k, v in items:
        rbt.insert(k, v)
    t2 = time.perf_counter()

    # query
    q0 = time.perf_counter()
    s1 = 0
    for lo, hi in ranges:
        s1 += len(bst.range_items(lo, hi))
    q1 = time.perf_counter()

    q2 = time.perf_counter()
    s2 = 0
    for lo, hi in ranges:
        s2 += len(rbt.range_items(lo, hi))
    q3 = time.perf_counter()

    return {
        "BST build(ms)": (t1 - t0) * 1000,
        "RBT build(ms)": (t2 - t1) * 1000,
        "BST query(ms)": (q1 - q0) * 1000,
        "RBT query(ms)": (q3 - q2) * 1000,
        "BST height": bst.height(),
        "RBT height": rbt.height(),
        "BST total_hits": s1,
        "RBT total_hits": s2,
        "n_items": len(items),
        "n_queries": len(ranges),
    }


with st.sidebar:
    st.subheader("실험 설정")
    mult = st.selectbox("데이터 확장 배수(차이 체감용)", [1, 10, 50, 100], index=1)
    order = st.selectbox("삽입 순서", ["정렬(최악: BST가 한쪽으로 쏠림)", "역순(최악)", "셔플(평균)"])
    q = st.slider("범위 조회 횟수(Q)", 10, 2000, 500, step=10)
    seed = st.number_input("랜덤 시드", value=42, step=1)
    run = st.button("🚀 벤치마크 실행")


if run:
    items = make_items(mult=mult, order=order, seed=seed)
    keys = [k for k, _ in items]
    ranges = make_ranges(keys, q=q, seed=seed)

    res = bench(items, ranges)
    out = pd.DataFrame([res])

    st.subheader("결과")
    st.dataframe(out, use_container_width=True)

    st.write(
        f"- BST 높이={res['BST height']} / RBT 높이={res['RBT height']}  "
        f"(높이가 클수록 탐색이 느려지기 쉬움)"
    )

    st.info(
        "팁: 삽입 순서를 '정렬(최악)'로 두고 배수를 50~100으로 올리면 "
        "BST가 한쪽으로 쏠리는 효과가 확 커져서 차이가 눈에 띈다."
    )
else:
    st.write("왼쪽에서 설정하고 **벤치마크 실행**을 눌러봐.")
