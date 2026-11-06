#!/usr/bin/env python3
"""Exhaustive semantic enumeration of S -> 1 | x | eml(S,S), eml(u,v) = exp(u) - ln(v).

    python3 corpus_enum.py [float|exact]        (default: exact)

Re-implements the depth-<=4 enumeration reported in the submitted paper (v6);
the original enumerator was not preserved.

Method (Methods, "Grammar enumeration and corpus"):
  * grid x = 0.35, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.5, 6.5;
  * a composition eml(a, b) is dropped if ln receives a non-positive argument at
    a grid point (undefined) or if an exp-port input exceeds 300 (overflow
    guard; every threshold from 100 to 600 gives identical counts);
  * a class is filed at the smallest depth at which it appears, with the
    smallest u-depth among its trees at that depth.  Depth = eml nodes on the
    longest root-to-leaf path; u-depth = most first-argument (exp-port) edges
    on any root-to-leaf path;
  * in span: every node of the class's representative tree stays at or below
    the device ceiling, 1366 units (8.4 decades, 1 unit = 0.5 uA);
  * constant: values spread by less than 1e-9 over the grid.

Two equality keys:
  float  values in double precision, equal when printed as %.9e (10 significant
         digits).  This reproduces the submitted paper's record exactly: |F(d)| = 2, 6, 26,
         442, 44,559; the depth x u-depth table; 194,688 depth-4 candidates,
         46,672 survivors; 6,786 in span; 355 constants (u-depth-3 survival
         5,324 against the record's 5,325, one borderline class).  But 2,535
         of its 2,555 depth-4 merges are rounding collisions: two different
         functions agree to 10 digits because exp of a large argument swamps
         the term that tells them apart.
  exact  values in 400-digit arithmetic (mpmath), equal to 300 significant
         digits at all 9 points.  Only true identities merge.  This is the
         count the paper reports.

Also counts the defined syntactic trees per depth (trees none of whose nodes is
undefined or overflows), so the gap between trees and functions can be split
into undefined trees and true duplicates.

Writes corpus_stats_<mode>.json next to this file.
"""
import json
import os
import sys

import mpmath as mp
import numpy as np

GRID_S = ["0.35", "0.5", "0.75", "1.0", "1.5", "2.0", "3.0", "4.5", "6.5"]
CEIL = 1366.0
EXP_GUARD = 300
MAXDEPTH = 4
HERE = os.path.dirname(os.path.abspath(__file__))


class Backend:
    def __init__(self, mode):
        self.mode = mode
        if mode == "exact":
            mp.mp.dps = 400
            self.grid = [mp.mpf(s) for s in GRID_S]
            self.one = [mp.mpf(1)] * len(GRID_S)
        else:
            self.grid = np.array([float(s) for s in GRID_S])
            self.one = np.ones(len(GRID_S))

    def key(self, v):
        if self.mode == "exact":
            return tuple(mp.nstr(t, 300) for t in v)
        return tuple(float("%.9e" % t) for t in v)

    def exp(self, v):            # None if any input exceeds the guard
        if max(v) > EXP_GUARD:
            return None
        return [mp.exp(t) for t in v] if self.mode == "exact" else np.exp(v)

    def log(self, v):            # None if any argument is non-positive
        if min(v) <= 0:
            return None
        return [mp.log(t) for t in v] if self.mode == "exact" else np.log(v)

    def sub(self, a, b):
        return [s - t for s, t in zip(a, b)] if self.mode == "exact" else a - b

    @staticmethod
    def peak(v):
        return max(abs(float(t)) for t in v)

    @staticmethod
    def spread(v):
        return float(max(v) - min(v))


class Cls:
    __slots__ = ("vals", "depth", "udepth", "peak", "tree", "e", "l", "mult")

    def __init__(self, B, vals, depth, udepth, peak, tree):
        self.vals, self.depth, self.udepth, self.peak, self.tree = vals, depth, udepth, peak, tree
        self.e, self.l = B.exp(vals), B.log(vals)
        self.mult = 0        # syntactic trees of depth <= current level in this class


def enumerate_corpus(mode="exact", maxdepth=MAXDEPTH):
    B = Backend(mode)
    classes = {}
    for vals, tree in ((B.one, "1"), (B.grid, "x")):
        c = Cls(B, vals, 0, 0, B.peak(vals), tree)
        c.mult = 1
        classes[B.key(vals)] = c
    per_depth = {0: dict(candidates=0, undefined=0, overflow=0, survivors=0, merged=0,
                         new=0, defined_trees=2)}
    merges = []                      # (existing tree, merged tree) at the new depth
    for d in range(1, maxdepth + 1):
        prev = list(classes.values())
        st = dict(candidates=0, undefined=0, overflow=0, survivors=0, merged=0, new=0)
        mult = {}
        defined_trees = 2            # the two leaves
        found = {}
        for a in prev:
            for b in prev:
                fresh = a.depth == d - 1 or b.depth == d - 1   # depth exactly d
                if fresh:
                    st["candidates"] += 1
                if b.l is None:
                    st["undefined"] += fresh
                    continue
                if a.e is None:
                    st["overflow"] += fresh
                    continue
                vals = B.sub(a.e, b.l)
                k = B.key(vals)
                n = a.mult * b.mult
                defined_trees += n
                mult[k] = mult.get(k, 0) + n
                if not fresh:
                    continue
                st["survivors"] += 1
                ud = max(a.udepth + 1, b.udepth)
                tree = "eml(%s,%s)" % (a.tree, b.tree)
                if k in classes:
                    st["merged"] += 1
                    merges.append((classes[k].tree, tree))
                    continue
                if k in found:
                    st["merged"] += 1
                    c = found[k]
                    merges.append((c.tree, tree))
                    peak = max(a.peak, b.peak, B.peak(vals))
                    if (ud, peak) < (c.udepth, c.peak):
                        c.udepth, c.peak, c.tree = ud, peak, tree
                    continue
                found[k] = Cls(B, vals, d, ud, max(a.peak, b.peak, B.peak(vals)), tree)
        st["new"] = len(found)
        classes.update(found)
        for k, c in classes.items():
            c.mult = mult.get(k, 0) + (1 if c.depth == 0 else 0)
        st["defined_trees"] = defined_trees
        per_depth[d] = st
    return B, classes, per_depth, merges


def summarize(mode):
    B, classes, per_depth, merges = enumerate_corpus(mode)
    cs = list(classes.values())
    const = lambda c: B.spread(c.vals) < 1e-9
    cum = [sum(1 for c in cs if c.depth <= d) for d in range(MAXDEPTH + 1)]
    T = [2]
    for _ in range(MAXDEPTH):
        T.append(2 + T[-1] ** 2)
    grid, by_u = {}, {}
    for c in cs:
        ok = c.peak <= CEIL and not const(c)
        g = grid.setdefault("%d,%d" % (c.depth, c.udepth), dict(n=0, in_span=0, in_span_nonconst=0))
        g["n"] += 1
        g["in_span"] += int(c.peak <= CEIL)
        g["in_span_nonconst"] += int(ok)
        u = by_u.setdefault(str(c.udepth), dict(n=0, in_span_nonconst=0))
        u["n"] += 1
        u["in_span_nonconst"] += int(ok)
    out = dict(
        mode=mode, grid=GRID_S, ceiling_units=CEIL, exp_guard=EXP_GUARD,
        syntactic_trees_cum=T,
        defined_trees_cum=[per_depth[d]["defined_trees"] for d in range(MAXDEPTH + 1)],
        distinct_cum=cum, per_depth=per_depth, by_depth_udepth=grid, by_udepth=by_u,
        n_constant=sum(1 for c in cs if const(c)),
        n_in_span=sum(1 for c in cs if c.peak <= CEIL),
        n_merges=len(merges), merges=merges,
    )
    json.dump(out, open(os.path.join(HERE, "corpus_stats_%s.json" % mode), "w"), indent=1)
    print("mode", mode)
    print("syntactic trees cum", T)
    print("defined trees cum  ", out["defined_trees_cum"])
    print("distinct cum       ", cum)
    for d in range(1, MAXDEPTH + 1):
        print("depth", d, per_depth[d])
    for d in range(MAXDEPTH + 1):
        print("d=%d" % d, [grid.get("%d,%d" % (d, p), {}).get("n", 0) for p in range(4)])
    print("constant", out["n_constant"], " in span", out["n_in_span"], " merges", len(merges))
    print("by u-depth", by_u)
    return out


if __name__ == "__main__":
    summarize(sys.argv[1] if len(sys.argv) > 1 else "exact")
