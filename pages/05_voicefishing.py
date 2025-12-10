# pages/06_tree_benchmark.py
import time, random, re
from dataclasses import dataclass
from pathlib import Path

import streamlit as st
import pandas as pd

st.title("🌲 BST vs Red-Black Tree 효율 비교(직접 실험)")

# -----------------------------
# 1) 월별 CSV -> (key:int, value:float) 만들기
# -----------------------------
ROOT = Path(__file__).resolve().parents[1]
CSV = ROOT / "police_voicephishing_monthly.csv"

def read_csv_smart(p: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "cp949", "euc-kr", "utf-8"):
        try:
            return pd.read_csv(p, encoding=enc)
        except Exception:
            pass
    return pd.read_csv(p, encoding="utf-8", encoding_errors="ignore")

def num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s.astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")

if not CSV.exists():
    st.error(f"CSV 파일이 없음: {CSV}")
    st.stop()

mraw = read_csv_smart(CSV)
mraw.columns = mraw.columns.astype(str).str.strip()

ycol = next((c for c in mraw.columns if re.search(r"연도|년도|년", c)), None)
mcol = next((c for c in mraw.columns if re.search(r"월", c)), None)
ccol = next((c for c in mraw.columns if ("발생" in c and "건수" in c)), None)
if not (ycol and mcol and ccol):
    st.error(f"컬럼 인식 실패: {list(mraw.columns)}")
    st.stop()

df = mraw.copy()
df[ycol], df[mcol], df[ccol] = num(df[ycol]), num(df[mcol]), num(df[ccol])
df["date"] = pd.to_datetime(
    df[ycol].astype("Int64").astype(str) + "-" + df[mcol].astype("Int64").astype(str).str.zfill(2) + "-01",
    errors="coerce",
)
df = df.dropna(subset=["date"]).sort_values("date")
df = df[["date", ccol]].rename(columns={ccol: "count"}).reset_index(drop=True)
df["count"] = df["count"].fillna(0).astype(float)

# key를 int(ns)로 바꾸면 비교가 빨라지고 실험도 안정적임
base_keys = df["date"].astype("int64").tolist()
base_vals = df["count"].tolist()
base_items = list(zip(base_keys, base_vals))
step = int(pd.Timedelta(days=400).value)  # 배수 확장 시 키 겹침 방지

with st.expander("🔎 데이터 확인"):
    st.write("월 개수:", len(base_items))
    st.dataframe(df.head(10), use_container_width=True)

# -----------------------------
# 2) BST (불균형 가능)
# -----------------------------
@dataclass
class BSTNode:
    k: int
    v: float
    left: "BSTNode|None" = None
    right: "BSTNode|None" = None
    parent: "BSTNode|None" = None

class BST:
    def __init__(self):
        self.root = None

    def insert(self, k: int, v: float):
        if self.root is None:
            self.root = BSTNode(k, v)
            return
        cur, parent = self.root, None
        while cur is not None:
            parent = cur
            if k == cur.k:
                cur.v = v
                return
            cur = cur.left if k < cur.k else cur.right
        node = BSTNode(k, v, parent=parent)
        if k < parent.k: parent.left = node
        else: parent.right = node

    def lower_bound(self, k: int):
        cur, res = self.root, None
        while cur is not None:
            if cur.k >= k:
                res = cur
                cur = cur.left
            else:
                cur = cur.right
        return res

    def _minimum(self, x: BSTNode):
        while x.left is not None:
            x = x.left
        return x

    def successor(self, x: BSTNode):
        if x.right is not None:
            return self._minimum(x.right)
        y = x.parent
        while y is not None and x == y.right:
            x, y = y, y.parent
        return y

    def range_count(self, lo: int, hi: int) -> int:
        cnt = 0
        x = self.lower_bound(lo)
        while x is not None and x.k <= hi:
            cnt += 1
            x = self.successor(x)
        return cnt

    # ✅ 재귀 금지(배수 100에서 RecursionError 방지)
    def height(self) -> int:
        if self.root is None:
            return 0
        maxh = 0
        stack = [(self.root, 1)]
        while stack:
            node, h = stack.pop()
            if h > maxh: maxh = h
            if node.left is not None: stack.append((node.left, h + 1))
            if node.right is not None: stack.append((node.right, h + 1))
        return maxh

# -----------------------------
# 3) Red-Black Tree (균형 유지)
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

    def insert(self, k: int, v: float):
        z = RBNode(k, v, RED)
        z.l = z.r = z.p = self.nil
        y, x = self.nil, self.root
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
                        z = z.p
                        self._lrot(z)
                    z.p.c = BLACK; z.p.p.c = RED
                    self._rrot(z.p.p)
            else:
                u = z.p.p.l
                if u.c == RED:
                    z.p.c = BLACK; u.c = BLACK; z.p.p.c = RED
                    z = z.p.p
                else:
                    if z == z.p.l:
                        z = z.p
                        self._rrot(z)
                    z.p.c = BLACK; z.p.p.c = RED
                    self._lrot(z.p.p)
        self.root.c = BLACK

    def lower_bound(self, k: int):
        x, res = self.root, self.nil
        while x != self.nil:
            if x.k >= k:
                res = x
                x = x.l
            else:
                x = x.r
        return res

    def _min(self, x):
        while x.l != self.nil:
            x = x.l
        return x

    def succ(self, x):
        if x.r != self.nil:
            return self._min(x.r)
        y = x.p
        while y != self.nil and x == y.r:
            x, y = y, y.p
        return y

    def range_count(self, lo: int, hi: int) -> int:
        cnt = 0
        x = self.lower_bound(lo)
        while x != self.nil and x.k <= hi:
            cnt += 1
            x = self.succ(x)
        return cnt

    # ✅ 재귀 금지(안전)
    def height(self) -> int:
        if self.root == self.nil:
            return 0
        maxh = 0
        stack = [(self.root, 1)]
        while stack:
            node, h = stack.pop()
            if h > maxh: maxh = h
            if node.l != self.nil: stack.append((node.l, h + 1))
            if node.r != self.nil: stack.append((node.r, h + 1))
        return maxh

# -----------------------------
# 4) 벤치마크
# -----------------------------
def make_items(mult: int, order: str, seed: int):
    items = []
    for t in range(mult):
        off = t * step
        for k, v in base_items:
            items.append((k + off, v))
    if order == "정렬(최악: BST 쏠림)":
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
        i = rnd.randrange(n); j = rnd.randrange(n)
        a, b = keys[i], keys[j]
        ranges.append((a, b) if a <= b else (b, a))
    return ranges

def bench(items, ranges):
    # build
    t0 = time.perf_counter()
    bst = BST()
    for k, v in items: bst.insert(k, v)
    t1 = time.perf_counter()

    rbt = RBTree()
    for k, v in items: rbt.insert(k, v)
    t2 = time.perf_counter()

    # query (리스트 생성 없이 count만)
    q0 = time.perf_counter()
    s1 = 0
    for lo, hi in ranges: s1 += bst.range_count(lo, hi)
    q1 = time.perf_counter()

    q2 = time.perf_counter()
    s2 = 0
    for lo, hi in ranges: s2 += rbt.range_count(lo, hi)
    q3 = time.perf_counter()

    return {
        "n_items": len(items),
        "n_queries": len(ranges),
        "BST build(ms)": (t1 - t0) * 1000,
        "RBT build(ms)": (t2 - t1) * 1000,
        "BST query(ms)": (q1 - q0) * 1000,
        "RBT query(ms)": (q3 - q2) * 1000,
        "BST height": bst.height(),
        "RBT height": rbt.height(),
        "BST total_hits": s1,
        "RBT total_hits": s2,
    }

with st.sidebar:
    st.subheader("실험 설정")
    mult = st.selectbox("데이터 확장 배수", [1, 10, 50, 100], index=1, key="bm_mult")
    order = st.selectbox("삽입 순서", ["정렬(최악: BST 쏠림)", "역순(최악)", "셔플(평균)"], key="bm_order")
    q = st.slider("범위 조회 횟수 Q", 10, 2000, 500, 10, key="bm_q")
    seed = st.number_input("랜덤 시드", value=42, step=1, key="bm_seed")
    run = st.button("🚀 실행", key="bm_run")

if run:
    try:
        items = make_items(mult, order, seed)
        keys = [k for k, _ in items]
        ranges = make_ranges(keys, q, seed)

        res = bench(items, ranges)
        st.dataframe(pd.DataFrame([res]), use_container_width=True)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("BST 높이", str(res["BST height"]))
        c2.metric("RBT 높이", str(res["RBT height"]))
        c3.metric("BST query(ms)", f"{res['BST query(ms)']:.1f}")
        c4.metric("RBT query(ms)", f"{res['RBT query(ms)']:.1f}")

        st.info("팁: 삽입 순서를 '정렬(최악)'로 두고 배수를 올리면 BST가 한쪽으로 쏠려 차이가 잘 보인다.")
    except Exception as e:
        st.error("에러 원인:")
        st.exception(e)
else:
    st.write("왼쪽에서 설정하고 실행을 눌러봐.")
