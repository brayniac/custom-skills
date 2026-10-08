#!/usr/bin/env python3
"""Tabulate a SystemsLab sweep with gates 1-3 from SKILL.md step 5.

For every experiment in the given contexts, prints the parameters that vary,
the load generator's result, the gate signals read from the rezolus
recordings, and a verdict:

  ranked         passed gates 1-3
  unclassified   finished cleanly but no saturation signal fired; classify
                 the limit by hand (SKILL.md step 6). A server that parks in
                 futex on a lock, or one capped by a shared ceiling, lands here
  loadgen-bound  the client was out of headroom
  link-bound     rx+tx reached --link-frac of --link-gbps
  no-data        a gate's metrics were missing; nothing was decided
  failed         the experiment ended in failure or error; or errors, failed
                 connections, dropped requests, fewer active connections than
                 --min-conns-frac of planned, or no result
  not-finished   the experiment was pending, cancelled or timed out in the queue
  error          the script could not read the experiment (message on stderr)

Not checked here; check by hand: Little's law (gate 1), the client's busiest
CPU (gate 3, printed as c_maxcpu but not gated, because a pinned polling thread
reads 100% busy without being saturated), and gate 4 (host state matched the
plan).

The result is the first JSON object with "type": "result" in the client job's
log, which cachecannon prints with `format = "json"`. Another load generator
needs this parser changed.

Thresholds are defaults from one rig. Calibrate them (`calibrate-to-source`)
before trusting a verdict.

  sweep_report.py --url http://localhost:8080 --app-cpus 16-63 <context-id> [...]
"""
import argparse
import json
import math
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

NAN = float("nan")


def cpu_set(spec):
    cpus = set()
    for part in spec.split(","):
        if "-" in part:
            lo, hi = part.split("-")
            cpus.update(range(int(lo), int(hi) + 1))
        elif part:
            cpus.add(int(part))
    return cpus


def fmt(value, spec):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "-"
    return spec % value


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("contexts", nargs="+")
    ap.add_argument("--url", required=True, help="SystemsLab server URL")
    ap.add_argument("--server-job", default="server")
    ap.add_argument("--client-job", default="client")
    ap.add_argument("--app-cpus", required=True, help="server CPUs the subject runs on, e.g. 16-63")
    ap.add_argument("--connections-param", default="CONNECTIONS",
                    help="sweep parameter holding the planned total connections the client opens")
    ap.add_argument("--min-conns-frac", type=float, default=0.99,
                    help="active connections at the end, as a fraction of planned, below which a cell failed")
    ap.add_argument("--min-rqwait", type=float, default=1.0,
                    help="core-equivalents of run-queue wait on the app CPUs that count as CPU-saturated")
    ap.add_argument("--max-poll-per-req", type=float, default=0.1,
                    help="polls per request at or below which a server that does poll counts as "
                         "saturated on its event loop")
    ap.add_argument("--min-app-busy", type=float, default=1.0,
                    help="app-CPU cores busy required before the poll test applies")
    ap.add_argument("--no-poll-gate", action="store_true",
                    help="disable the poll test, for a server that busy-polls or never blocks in poll/epoll")
    ap.add_argument("--max-client-rq99", type=float, default=40.0, help="client run-queue p99 in us")
    ap.add_argument("--max-client-netrx", type=float, default=0.8,
                    help="busiest client CPU's share of time in net_rx softirq")
    ap.add_argument("--link-gbps", type=float, default=0.0,
                    help="link rate; with it, rx+tx at --link-frac or more is link-bound")
    ap.add_argument("--link-frac", type=float, default=0.9)
    args = ap.parse_args()
    app = cpu_set(args.app_cpus)

    def run(*cmd):
        p = subprocess.run(["systemslab", "--systemslab-url", args.url, *cmd], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError("systemslab %s: %s" % (" ".join(cmd[:2]), (p.stderr or p.stdout).strip()[:200]))
        return p.stdout

    def api(path):
        out = run("api", path)
        try:
            return json.loads(out)
        except ValueError:
            raise RuntimeError("non-JSON response from %s: %s" % (path, out.strip()[:200]))

    def series(eid, jid, expr):
        """Mean of each returned series over the recording, keyed by its labels.

        An empty dict means the query matched nothing; callers treat that as
        missing data, never as zero."""
        p = subprocess.run(["systemslab", "--systemslab-url", args.url, "promql", "--experiment", eid,
                            "--job", jid, "--output", "json", expr], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError("promql %s: %s" % (expr, (p.stderr or p.stdout).strip()[:200]))
        try:
            doc = json.loads(p.stdout)
        except ValueError:
            return {}
        res = {}
        for s in doc.get("result", []):
            vals = [float(v) for _, v in s.get("values", []) if v not in ("NaN", "+Inf", "-Inf")]
            if vals:
                res[tuple(sorted(s.get("metric", {}).items()))] = sum(vals) / len(vals)
        return res

    def by_cpu(eid, jid, expr):
        return {int(dict(k)["id"]): v for k, v in series(eid, jid, expr).items() if "id" in dict(k)}

    def scalar(eid, jid, expr):
        values = list(series(eid, jid, expr).values())
        return values[0] if len(values) == 1 else NAN

    def measure(exp):
        eid = exp["experiment_id"]
        row = {"params": exp.get("params", {}), "id": eid, "state": "?"}
        try:
            x = api(f"/api/v1/experiment/{eid}")
            row["state"] = x["state"]
            if x["state"] in ("pending", "cancelled", "timeout"):
                row["verdict"] = "not-finished"
                return row
            if x["state"] != "success":
                row["verdict"] = "failed"
                return row
            jobs = {j["name"]: j["id"] for j in x["jobs"]}
            missing = [j for j in (args.server_job, args.client_job) if j not in jobs]
            if missing:
                raise RuntimeError("no job named %s (jobs: %s)" % (", ".join(missing), ", ".join(jobs)))
            results = []
            for line in run("logs", "--experiment", eid, "--job", args.client_job).splitlines():
                body = line.split("| ", 1)[-1]
                if body.startswith("{"):
                    try:
                        obj = json.loads(body)
                    except ValueError:
                        continue
                    if obj.get("type") == "result":
                        results.append(obj)
            if not results:
                row["verdict"] = "failed"
                return row
            r = row["result"] = results[0]
            t = r.get("throughput", 0)
            planned = row["params"].get(args.connections_param)
            if (t <= 0 or r.get("errors") or r.get("conns_failed") or r.get("requests_dropped")
                    or (planned is not None and r.get("conns_active") is not None
                        and int(r["conns_active"]) < args.min_conns_frac * int(planned))):
                row["verdict"] = "failed"
                return row
            s, c = jobs[args.server_job], jobs[args.client_job]
            busy = by_cpu(eid, s, "sum by (id) (irate(cpu_usage[5s])) / 1e9")
            rqw = by_cpu(eid, s, "sum by (id) (irate(scheduler_runqueue_wait[5s])) / 1e9")
            snetrx = by_cpu(eid, s, 'sum by (id) (irate(softirq_time{kind="net_rx"}[5s])) / 1e9')
            cnetrx = by_cpu(eid, c, 'sum by (id) (irate(softirq_time{kind="net_rx"}[5s])) / 1e9')
            cbusy = by_cpu(eid, c, "sum by (id) (irate(cpu_usage[5s])) / 1e9")
            row.update(
                rqwait=sum(v for k, v in rqw.items() if k in app) if rqw else NAN,
                app_busy=sum(v for k, v in busy.items() if k in app) if busy else NAN,
                cpu_us=1e6 * sum(busy.values()) / t if busy else NAN,
                poll=scalar(eid, s, 'sum(irate(syscall{op="poll"}[5s]))') / t,
                futex=scalar(eid, s, 'sum(irate(syscall{op="lock"}[5s]))') / t,
                vcs=scalar(eid, s, 'sum(irate(scheduler_context_switch{kind="voluntary"}[5s]))') / t,
                migr=scalar(eid, s, 'sum(irate(cpu_migrations{direction="to"}[5s]))'),
                server_netrx=max(snetrx.values()) if snetrx else NAN,
                client_rq99=scalar(eid, c, "histogram_quantile(0.99, scheduler_runqueue_latency) / 1000"),
                client_netrx=max(cnetrx.values()) if cnetrx else NAN,
                client_maxcpu=max(cbusy.values()) if cbusy else NAN,
                link_gbps=(r.get("rx_bps", 0) + r.get("tx_bps", 0)) / 1e9,
            )
            # A saturated client is reported as such even when other metrics are missing.
            if row["client_rq99"] > args.max_client_rq99 or row["client_netrx"] > args.max_client_netrx:
                row["verdict"] = "loadgen-bound"
            elif any(math.isnan(row[k]) for k in ("client_rq99", "client_netrx", "rqwait", "app_busy")):
                row["verdict"] = "no-data"
            elif args.link_gbps and row["link_gbps"] >= args.link_frac * args.link_gbps:
                row["verdict"] = "link-bound"
            elif row["rqwait"] >= args.min_rqwait:
                row["verdict"] = "ranked"
            elif (not args.no_poll_gate and not math.isnan(row["poll"]) and 0 < row["poll"] <= args.max_poll_per_req
                    and row["app_busy"] >= args.min_app_busy):
                row["verdict"] = "ranked"
            else:
                row["verdict"] = "unclassified"
        except Exception as e:  # one bad experiment must not end the report
            row["verdict"] = "error"
            row["message"] = str(e)
        return row

    exps = []
    for ctx in args.contexts:
        exps += api(f"/api/v1/context/{ctx}")["experiments"]
    with ThreadPoolExecutor(8) as pool:
        rows = list(pool.map(measure, exps))

    varying = sorted(k for k in {k for r in rows for k in r["params"]}
                     if len({str(r["params"].get(k)) for r in rows}) > 1)
    order = ["ranked", "unclassified", "loadgen-bound", "link-bound", "no-data", "failed", "not-finished", "error"]
    def throughput(r):
        try:
            return float(r.get("result", {}).get("throughput", 0))
        except (TypeError, ValueError):
            return 0.0
    rows.sort(key=lambda r: (order.index(r["verdict"]), -throughput(r)))

    head = varying + ["verdict", "state", "req/s", "p50", "p99", "rqwait", "poll/rq", "appC", "cpu_us",
                      "futex/rq", "vcs/rq", "migr/s", "s_netrx", "c_rq99", "c_netrx", "c_maxcpu", "Gbps", "experiment"]
    print("\t".join(head))
    for r in rows:
        cells = [str(r["params"].get(k, "")) for k in varying] + [r["verdict"], r["state"]]
        res = r.get("result", {})
        get = res.get("get", {})
        cells += [str(res.get("throughput", "-")), str(get.get("p50_us", "-")), str(get.get("p99_us", "-")),
                  fmt(r.get("rqwait"), "%.1f"), fmt(r.get("poll"), "%.2f"), fmt(r.get("app_busy"), "%.1f"),
                  fmt(r.get("cpu_us"), "%.1f"), fmt(r.get("futex"), "%.2f"), fmt(r.get("vcs"), "%.2f"),
                  fmt(r.get("migr"), "%.0f"), fmt(r.get("server_netrx"), "%.2f"), fmt(r.get("client_rq99"), "%.1f"),
                  fmt(r.get("client_netrx"), "%.2f"), fmt(r.get("client_maxcpu"), "%.2f"),
                  fmt(r.get("link_gbps"), "%.1f"), r["id"]]
        print("\t".join(cells))
        if r.get("message"):
            print("  %s: %s" % (r["id"], r["message"]), file=sys.stderr)


if __name__ == "__main__":
    main()
