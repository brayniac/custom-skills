#!/usr/bin/env python3
"""Top functions from an xctrace Time Profiler recording.

    xctrace_top.py <file.trace> [--top N] [--process NAME] [--run N]

Exports a run's time-profile table (the last run unless --run is given) and
prints, for the leaf frame of each sample (self time) and for every frame on
the stack (total time), the sample count and share. xctrace writes each
frame, thread and process once with an id and refers to it afterwards with
ref=, so names are resolved through those ids rather than counted as they
appear.
"""
import argparse
import collections
import subprocess
import sys
import xml.etree.ElementTree as ET

XPATH = '/trace-toc/run[@number="{run}"]/data/table[@schema="time-profile"]'


def xctrace_export(*args):
    return subprocess.run(
        ["xcrun", "xctrace", "export", *args], check=True, capture_output=True
    ).stdout


def last_run(trace):
    toc = ET.fromstring(xctrace_export("--input", trace, "--toc"))
    runs = [int(r.attrib["number"]) for r in toc.iter("run")]
    if not runs:
        sys.exit("no runs in the trace")
    return max(runs)


def export(trace, run):
    xpath = XPATH.format(run=run)
    return ET.fromstring(xctrace_export("--input", trace, "--xpath", xpath))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("trace")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--process", help="only samples from this process name")
    ap.add_argument("--run", type=int, help="run number (default: the last)")
    args = ap.parse_args()

    last = last_run(args.trace)
    run = args.run if args.run is not None else last
    if not 1 <= run <= last:
        sys.exit(f"run {run} is not in the trace (runs 1 to {last})")
    root = export(args.trace, run)
    by_id = {}
    for el in root.iter():
        if "id" in el.attrib:
            by_id[el.attrib["id"]] = el

    def resolve(el):
        return by_id.get(el.attrib["ref"], el) if "ref" in el.attrib else el

    self_count = collections.Counter()
    total_count = collections.Counter()
    samples = 0
    for row in root.iter("row"):
        if args.process:
            proc = row.find("process")
            name = "" if proc is None else resolve(proc).attrib.get("fmt", "")
            if name.rsplit(" (", 1)[0] != args.process:
                continue
        tagged = row.find("tagged-backtrace")
        if tagged is None:
            continue
        bt = resolve(tagged).find("backtrace")
        if bt is None:
            continue
        bt = resolve(bt)
        frames = [resolve(f).attrib.get("name", "?") for f in bt.findall("frame")]
        if not frames:
            continue
        samples += 1
        self_count[frames[0]] += 1
        for name in set(frames):
            total_count[name] += 1

    if samples == 0:
        print("no samples in the time-profile table", file=sys.stderr)
        sys.exit(1)
    print(f"run {run}: {samples} samples")
    for title, counter in (("self", self_count), ("total", total_count)):
        print(f"\n{title}:")
        for name, n in counter.most_common(args.top):
            print(f"{n:8d} {100 * n / samples:5.1f}%  {name}")


if __name__ == "__main__":
    main()
