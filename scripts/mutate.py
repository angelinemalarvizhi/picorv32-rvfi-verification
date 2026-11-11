#!/usr/bin/env python3
"""Mutation testing: measure how good the testbench is at finding bugs.

Each mutant is a copy of rtl/picorv32.v with one small, realistic code change.
The full test suite runs against every mutant; a mutant is KILLED if any test
fails. Mutation score = killed / total.

    python3 scripts/mutate.py              # all mutants
    python3 scripts/mutate.py --only M05   # one mutant
"""
import argparse
import os
import pathlib
import subprocess
import time
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "rtl" / "picorv32.v"
MUT = ROOT / "mutants"
RES = ROOT / "results"

MUTANTS = [
    ("M01", "SLT/BLT compare unsigned",
     "alu_lts = $signed(reg_op1) < $signed(reg_op2);", "alu_lts = reg_op1 < reg_op2;"),
    ("M02", "SUB performs ADD",
     "alu_add_sub = instr_sub ? reg_op1 - reg_op2 : reg_op1 + reg_op2;", "alu_add_sub = reg_op1 + reg_op2;"),
    ("M03", "SRA by >=4 is logical",
     "instr_srai || instr_sra: reg_op1 <= $signed(reg_op1) >>> 4;",
     "instr_srai || instr_sra: reg_op1 <= reg_op1 >> 4;"),
    ("M04", "BGEU behaves as BLTU",
     "alu_out_0 = !alu_ltu;", "alu_out_0 = alu_ltu;"),
    ("M05", "LB zero-extends",
     "latched_is_lb: reg_out <= $signed(mem_rdata_word[7:0]);", "latched_is_lb: reg_out <= mem_rdata_word[7:0];"),
    ("M06", "LH zero-extends",
     "latched_is_lh: reg_out <= $signed(mem_rdata_word[15:0]);", "latched_is_lh: reg_out <= mem_rdata_word[15:0];"),
    ("M07", "SB always writes byte lane 0",
     "mem_la_wstrb = 4'b0001 << reg_op1[1:0];", "mem_la_wstrb = 4'b0001;"),
    ("M08", "JALR does not clear bit 0",
     "& ~1 : reg_next_pc;", ": reg_next_pc;"),
    ("M09", "MULH treats rs2 as unsigned",
     "wire instr_rs2_signed = |{instr_mulh};", "wire instr_rs2_signed = 0;"),
    ("M10", "MULH* return the low word",
     "pcpi_rd <= instr_any_mulh ? rd >> 32 : rd;", "pcpi_rd <= rd;"),
    ("M11", "DIV by zero: sign fix-up wrongly applied",
     "&& |pcpi_rs2) || (instr_rem && pcpi_rs1[31]);", ") || (instr_rem && pcpi_rs1[31]);"),
    ("M12", "REM sign follows divisor instead of dividend",
     "(instr_rem && pcpi_rs1[31]);", "(instr_rem && pcpi_rs2[31]);"),
    ("M13", "fetch uses live (unlatched) bus data",
     "assign mem_rdata_latched_noshuffle = (mem_xfer || LATCHED_MEM_RDATA) ? mem_rdata : mem_rdata_q;",
     "assign mem_rdata_latched_noshuffle = mem_rdata;"),
]


def build_mutant(mid, find, repl):
    src = SRC.read_text()
    n = src.count(find)
    if n == 0:
        raise SystemExit(f"{mid}: pattern not found in picorv32.v")
    MUT.mkdir(exist_ok=True)
    path = MUT / f"{mid}.v"
    path.write_text(src.replace(find, repl))
    return path, n


def run(core, tag, progs):
    xml = RES / f"mut_{tag}.xml"
    xml.unlink(missing_ok=True)
    cmd = ["make", "-s", f"CORE={core}", f"NUM_PROGS={progs}", "SEED=12345",
           f"SIM_BUILD=sim_build_{tag}", f"COCOTB_RESULTS_FILE={xml}"]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                       env={**os.environ, "COV_FILE": str(RES / f"mut_{tag}_cov.json")})
    (RES / f"mut_{tag}.log").write_text(p.stdout + p.stderr)
    if not xml.exists():
        return None, ["<compile error>"]
    cases = list(ET.parse(xml).getroot().iter("testcase"))
    failed = [c.get("name") for c in cases if c.find("failure") is not None or c.find("error") is not None]
    return len(cases), failed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--progs", type=int, default=4)
    a = ap.parse_args()
    RES.mkdir(exist_ok=True)
    print("sanity: original core must pass ...", flush=True)
    n, failed = run(SRC, "orig", a.progs)
    if failed:
        raise SystemExit(f"original core fails {failed}; fix the testbench first")
    rows, killed, total = [], 0, 0
    for mid, desc, find, repl in MUTANTS:
        if a.only and a.only != mid:
            continue
        path, sites = build_mutant(mid, find, repl)
        t0 = time.time()
        n, failed = run(path, mid, a.progs)
        total += 1
        status = "KILLED" if failed else "SURVIVED"
        killed += bool(failed)
        print(f"{mid} {status:<9} {desc:<58} ({time.time() - t0:.0f}s) {failed}", flush=True)
        rows.append(f"| {mid} | {desc} | {sites} | {status if failed else '**SURVIVED**'} | {', '.join(failed)} |")
    score = 100.0 * killed / max(total, 1)
    md = ["# Mutation testing report", "", f"**Mutation score: {killed}/{total} = {score:.0f}%**", "",
          "| id | mutation | sites | result | killed by |", "|---|---|---|---|---|"] + rows
    (RES / "MUTATION_REPORT.md").write_text("\n".join(md) + "\n")
    print(f"mutation score {killed}/{total} = {score:.0f}%  -> results/MUTATION_REPORT.md")
    raise SystemExit(0 if killed == total else 1)


if __name__ == "__main__":
    main()
