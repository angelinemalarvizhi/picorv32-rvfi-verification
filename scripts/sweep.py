#!/usr/bin/env python3
"""Seed sweep: run the full suite with N random seeds, merge coverage, write a report.

    python3 scripts/sweep.py --seeds 10 --progs 10
"""
import argparse
import json
import os
import pathlib
import random
import subprocess
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
RES = ROOT / "results"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--progs", type=int, default=10)
    a = ap.parse_args()
    RES.mkdir(exist_ok=True)
    merged, totals, rows, fails = {}, {"programs": 0, "instructions": 0}, [], 0
    cpis = {}
    for _ in range(a.seeds):
        seed = random.randint(1, 2**31 - 1)
        xml, cov = RES / f"sweep_{seed}.xml", RES / f"sweep_{seed}_cov.json"
        p = subprocess.run(["make", "-s", f"SEED={seed}", f"NUM_PROGS={a.progs}", f"COCOTB_RESULTS_FILE={xml}"],
                           cwd=ROOT, capture_output=True, text=True, env={**os.environ, "COV_FILE": str(cov)})
        (RES / f"sweep_{seed}.log").write_text(p.stdout + p.stderr)
        cases = list(ET.parse(xml).getroot().iter("testcase")) if xml.exists() else []
        bad = [c.get("name") for c in cases if c.find("failure") is not None or c.find("error") is not None]
        if not cases:
            bad = ["<build error>"]
        fails += bool(bad)
        tot = json.loads(pathlib.Path(str(cov).replace(".json", "_totals.json")).read_text())
        for k in totals:
            totals[k] += tot[k]
        for k, v in tot.items():
            if k.startswith("cpi_"):
                cpis.setdefault(k[4:], []).append(v)
        for cp, bins in json.loads(cov.read_text()).items():
            for b, c in bins.items():
                merged.setdefault(cp, {}).setdefault(b, 0)
                merged[cp][b] += c
        print(f"seed {seed:>10}: {len(cases)} tests  {'PASS' if not bad else 'FAIL ' + str(bad)}  "
              f"{tot['instructions']} instructions")
        rows.append(f"| {seed} | {len(cases)} | {'PASS' if not bad else 'FAIL'} | {tot['programs']} | {tot['instructions']} |")
    hit = sum(1 for d in merged.values() for c in d.values() if c)
    allb = sum(len(d) for d in merged.values())
    md = ["# Seed sweep report", "", f"{a.seeds} seeds, {a.progs} programs per random test", "",
          "| seed | tests | result | programs | instructions checked |", "|---|---|---|---|---|", *rows, "",
          f"**{totals['programs']} programs, {totals['instructions']} instructions compared against the model.**", "",
          "| memory profile | mean CPI |", "|---|---|",
          *[f"| {k} | {sum(v) / len(v):.2f} |" for k, v in cpis.items()], "",
          f"## Coverage: {hit}/{allb} bins ({100 * hit / allb:.1f}%)", ""]
    for cp, d in merged.items():
        holes = [b for b, c in d.items() if not c]
        md.append(f"* `{cp}`: {len(d) - len(holes)}/{len(d)}" + (f"; holes {holes}" if holes else ""))
    (RES / "coverage_merged.json").write_text(json.dumps(merged, indent=2))
    (RES / "SWEEP_REPORT.md").write_text("\n".join(md) + "\n")
    print(f"coverage {hit}/{allb}; {totals['instructions']} instructions; report results/SWEEP_REPORT.md")
    raise SystemExit(1 if fails else 0)


if __name__ == "__main__":
    main()
