#!/usr/bin/env python3
"""Summarise an Nsight Systems SQLite export.

Usage: python3 nsys-queries.py /tmp/prof.sqlite

Prints top kernels, memcpy by direction, top CUDA runtime API calls by CPU
time, and the GPU idle gap (wall span minus the union of kernel and memcpy
intervals, so overlapping streams are not double-counted).
"""
import sqlite3
import sys


def has_table(c, name):
    return c.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def main(path):
    c = sqlite3.connect(path)

    if not has_table(c, "CUPTI_ACTIVITY_KIND_KERNEL"):
        sys.exit("no CUPTI_ACTIVITY_KIND_KERNEL table: was the capture run with -t cuda?")

    rows = c.execute("""
        SELECT s.value, SUM(k.end - k.start), COUNT(*), AVG(k.end - k.start)
        FROM CUPTI_ACTIVITY_KIND_KERNEL k
        JOIN StringIds s ON s.id = k.demangledName
        GROUP BY s.value ORDER BY 2 DESC
    """).fetchall()
    total = sum(r[1] for r in rows) or 1
    print(f"Kernel GPU time: {total / 1e6:.1f} ms across {len(rows)} kernels\n")
    print(f"{'ms':>9} {'%':>5} {'n':>7} {'mean us':>9}  name")
    for name, t_ns, n, mean in rows[:20]:
        print(f"{t_ns / 1e6:>9.2f} {100 * t_ns / total:>5.1f} {n:>7} "
              f"{mean / 1e3:>9.1f}  {name.split('(')[0][:70]}")

    intervals = c.execute(
        "SELECT start, end FROM CUPTI_ACTIVITY_KIND_KERNEL").fetchall()

    if has_table(c, "CUPTI_ACTIVITY_KIND_MEMCPY"):
        print("\nMemcpy by direction (GPU time / count):")
        kinds = dict(c.execute("SELECT id, name FROM ENUM_CUDA_MEMCPY_OPER"))
        for kind, t_ns, n in c.execute("""
            SELECT copyKind, SUM(end - start), COUNT(*)
            FROM CUPTI_ACTIVITY_KIND_MEMCPY GROUP BY copyKind ORDER BY 2 DESC
        """):
            print(f"  {kinds.get(kind, kind)}: {t_ns / 1e6:.1f} ms / {n} calls")
        intervals += c.execute(
            "SELECT start, end FROM CUPTI_ACTIVITY_KIND_MEMCPY").fetchall()

    if has_table(c, "CUPTI_ACTIVITY_KIND_RUNTIME"):
        print("\nTop runtime API calls (CPU time):")
        for name, t_ns, n in c.execute("""
            SELECT s.value, SUM(r.end - r.start), COUNT(*)
            FROM CUPTI_ACTIVITY_KIND_RUNTIME r
            JOIN StringIds s ON s.id = r.nameId
            GROUP BY s.value ORDER BY 2 DESC LIMIT 10
        """):
            print(f"  {t_ns / 1e6:>8.1f} ms / {n:>7} calls  {name}")

    intervals.sort()
    busy, cur_start, cur_end = 0, None, None
    for s, e in intervals:
        if cur_end is None or s > cur_end:
            if cur_end is not None:
                busy += cur_end - cur_start
            cur_start, cur_end = s, e
        else:
            cur_end = max(cur_end, e)
    if cur_end is not None:
        busy += cur_end - cur_start
    span = intervals[-1][1] - intervals[0][0] if intervals else 0
    if span:
        idle = span - busy
        print(f"\nGPU span {span / 1e6:.1f} ms, busy {busy / 1e6:.1f} ms, "
              f"idle {idle / 1e6:.1f} ms ({100 * idle / span:.0f}%)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
