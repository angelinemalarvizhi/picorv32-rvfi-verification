"""PicoRV32 (RV32IM) verification: RVFI trace vs. reference model, with a
randomised-latency memory BFM.

Checked per retired instruction: order, pc_rdata, pc_wdata, insn, trap,
rd_addr, rd_wdata, rs1/rs2 read values, memory address, masks, write data
(masked lanes) and load data."""
import json
import os
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ReadOnly, RisingEdge, Timer

from asm import assemble
from coverage_model import COV, decode_name
from mem_bfm import MemoryBFM, uint
from rv32im_model import RV32IM
from stimgen import DATA_BASE, ProgramGen

N_PROGS = int(os.environ.get("NUM_PROGS", "10"))
SCRAMBLE = os.environ.get("BUS_SCRAMBLE", "1") == "1"
COV_PATH = os.environ.get("COV_FILE", "results/coverage.json")
TOTALS = {"programs": 0, "instructions": 0, "cycles": 0}


class Mismatch(AssertionError):
    pass


async def execute(dut, asm_src, data=(), ifetch="mixed", dmem="mixed", tag="prog", max_cycles=400_000):
    """Run one program to EBREAK with per-instruction comparison. Returns the model."""
    await Timer(1, unit="ns")        # leave any ReadOnly phase from a previous program
    rng = random.Random(random.getrandbits(32))
    code = assemble(asm_src)
    bfm = MemoryBFM(dut, rng, ifetch, dmem, scramble=SCRAMBLE)
    bfm.load_words(0, code)
    bfm.load_words(DATA_BASE, list(data))
    bfm.on_access = COV.sample_access
    model = RV32IM(bfm.mem)          # model gets its own copy of the initial image

    clk = cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    mem = cocotb.start_soon(bfm.run())
    dut.resetn.value = 0
    for _ in range(4):
        await RisingEdge(dut.clk)
    dut.resetn.value = 1

    history, order, cycles = [], 0, 0
    try:
        for cycles in range(max_cycles):
            await RisingEdge(dut.clk)
            await ReadOnly()
            if str(dut.rvfi_valid.value) != "1":
                continue
            got = {k: uint(getattr(dut, f"rvfi_{k}")) for k in
                   ("order", "insn", "trap", "pc_rdata", "pc_wdata", "rd_addr", "rd_wdata",
                    "rs1_addr", "rs2_addr", "rs1_rdata", "rs2_rdata",
                    "mem_addr", "mem_rmask", "mem_wmask", "mem_wdata", "mem_rdata")}
            a, b = model.x[(model.rd_word(model.pc) >> 15) & 31], model.x[(model.rd_word(model.pc) >> 20) & 31]
            exp = model.step()
            history.append((exp, got))
            errs = []

            def chk(field, e, g):
                if e != g:
                    errs.append(f"{field}: expected 0x{e:08x}, got 0x{g:08x}")

            chk("order", order, got["order"])
            for k in ("pc_rdata", "insn", "trap", "pc_wdata"):
                chk(k, exp[k], got[k])
            if not exp["trap"]:
                chk("rd_addr", exp["rd_addr"], got["rd_addr"])
                chk("rd_wdata", exp["rd_wdata"], got["rd_wdata"])
                for s in ("rs1", "rs2"):            # PicoRV32 reports 0 for unused sources
                    if got[f"{s}_addr"]:
                        chk(f"{s}_addr", (exp["insn"] >> (15 if s == "rs1" else 20)) & 31, got[f"{s}_addr"])
                        chk(f"{s}_rdata", a if s == "rs1" else b, got[f"{s}_rdata"])
                chk("mem_wmask", exp["mem_wmask"], got["mem_wmask"])
                if exp["mem_wmask"] or exp["mem_rmask"]:
                    chk("mem_addr", exp["mem_addr"], got["mem_addr"])
                lanes = sum(0xFF << 8 * k for k in range(4) if exp["mem_wmask"] >> k & 1)
                chk("mem_wdata", exp["mem_wdata"] & lanes, got["mem_wdata"] & lanes)
                if exp["mem_rmask"]:
                    chk("mem_rmask!=0", 1, int(got["mem_rmask"] != 0))
                    chk("mem_rdata", exp["mem_rdata"], got["mem_rdata"])
            if errs:
                rows = [f"  #{e['pc_rdata']:08x} {decode_name(e['insn']):<7} rd=x{e['rd_addr']:<2} "
                        f"exp={e['rd_wdata']:08x} got={g['rd_wdata']:08x}" for e, g in history[-8:]]
                raise Mismatch(f"[{tag}] instruction #{order} at pc 0x{exp['pc_rdata']:08x} "
                               f"({decode_name(exp['insn'])}):\n    " + "\n    ".join(errs) +
                               "\n  last retired:\n" + "\n".join(rows))
            COV.sample_retire(exp, a, b)
            order += 1
            if exp["trap"]:
                break
        else:
            raise TimeoutError(f"[{tag}] no EBREAK within {max_cycles} cycles")
        assert not bfm.violations, bfm.violations[:3]
        TOTALS["programs"] += 1
        TOTALS["instructions"] += order
        TOTALS["cycles"] += cycles
    except AssertionError:
        os.makedirs("results", exist_ok=True)
        with open(f"results/failing_{tag}.S", "w") as f:
            f.write(asm_src)
        raise
    finally:
        mem.cancel()
        clk.cancel()
    return model


def wrap_up(dut, name):
    hit, tot = COV.score()
    dut._log.info(f"[{name}] programs={TOTALS['programs']} instructions={TOTALS['instructions']} "
                  f"coverage={hit}/{tot}")
    COV.save(COV_PATH)
    with open(COV_PATH.replace(".json", "_totals.json"), "w") as f:
        json.dump(TOTALS, f)


# ======================================================================= directed
@cocotb.test()
async def test_isa_smoke(dut):
    """Every RV32I instruction once with known operands; final registers checked by hand."""
    src = """
        li   x5, 7
        li   x6, -3
        add  x7, x5, x6        # 4
        sub  x8, x5, x6        # 10
        sll  x9, x5, x5        # 7<<7 = 896
        slt  x10, x6, x5       # 1
        sltu x11, x6, x5       # 0
        xor  x12, x5, x6
        srl  x13, x6, x5
        sra  x14, x6, x5       # -1
        or   x15, x5, x6
        and  x16, x5, x6
        addi x17, x5, -8       # -1
        slti x18, x6, -2       # 1
        sltiu x19, x5, -1      # 1
        xori x20, x5, 0x7ff
        ori  x21, x5, 0x100
        andi x22, x6, 0xff
        slli x23, x5, 28
        srli x24, x6, 28       # 0xf
        srai x25, x6, 1        # -2
        lui  x26, 0xabcde
        auipc x27, 1
        li   x31, 0x1000
        sw   x6, 0(x31)
        sh   x5, 4(x31)
        sb   x5, 7(x31)
        lw   x2, 0(x31)
        lh   x3, 0(x31)
        lhu  x4, 0(x31)
        lb   x28, 1(x31)
        lbu  x29, 1(x31)
        lw   x30, 4(x31)       # 0x07000007
        beq  x5, x5, t1
        addi x1, x0, 1
    t1: bne  x5, x6, t2
        addi x1, x0, 2
    t2: blt  x6, x5, t3
        addi x1, x0, 3
    t3: bge  x5, x6, t4
        addi x1, x0, 4
    t4: bltu x5, x6, t5
        addi x1, x0, 5
    t5: bgeu x6, x5, t6
        addi x1, x0, 6
    t6: jal  x1, f
        ebreak
    f:  jalr x0, 0(x1)
    """
    m = await execute(dut, src, tag="smoke")
    x = m.x
    assert (x[7], x[8], x[9], x[10], x[11], x[14] & 0xFFFFFFFF) == (4, 10, 896, 1, 0, 0xFFFFFFFF)
    assert x[24] == 0xF and x[30] == 0x07000007 and x[29] == 0xFF and x[1] != 1
    wrap_up(dut, "smoke")


@cocotb.test()
async def test_m_extension_corners(dut):
    """Division by zero, -2^31/-1 overflow, all MULH sign combinations."""
    vals = ["0", "1", "-1", "0x80000000", "0x7fffffff", "3", "-7"]
    lines = []
    for p in vals:
        for q in vals:
            lines += [f"li x5, {p}", f"li x6, {q}"]
            lines += [f"{op} x7, x5, x6" for op in
                      ("mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu")]
    lines.append("ebreak")
    m = await execute(dut, "\n".join(lines), ifetch="zero", dmem="zero", tag="mcorner")
    wrap_up(dut, "m-corners")


@cocotb.test()
async def test_memory_lanes(dut):
    """Every store width at every legal offset followed by every load width."""
    lines = ["li x31, 0x1000", "li x5, 0x8091a2b3"]
    for off in range(4):
        lines += [f"sw x0, 16(x31)", f"sb x5, {16 + off}(x31)", "lw x6, 16(x31)",
                  f"lb x7, {16 + off}(x31)", f"lbu x8, {16 + off}(x31)"]
    for off in (0, 2):
        lines += [f"sw x0, 32(x31)", f"sh x5, {32 + off}(x31)", "lw x6, 32(x31)",
                  f"lh x7, {32 + off}(x31)", f"lhu x8, {32 + off}(x31)"]
    lines += ["sw x5, 48(x31)", "lw x9, 48(x31)", "ebreak"]
    m = await execute(dut, "\n".join(lines), dmem="slow", tag="lanes")
    assert m.x[9] == 0x8091A2B3
    wrap_up(dut, "lanes")


# ======================================================================= random
async def random_campaign(dut, n, ifetch, dmem, name, **kw):
    i0, c0 = TOTALS["instructions"], TOTALS["cycles"]
    for k in range(n):
        g = ProgramGen(random.Random(random.getrandbits(32)), **kw)
        await execute(dut, g.program(), g.data_image(), ifetch, dmem, tag=f"{name}{k}")
    di, dc = TOTALS["instructions"] - i0, TOTALS["cycles"] - c0
    dut._log.info(f"[{name}] {n} programs, {di} instructions, CPI for this memory profile = {dc / max(di, 1):.2f}")
    TOTALS[f"cpi_{name}"] = round(dc / max(di, 1), 2)
    wrap_up(dut, name)


@cocotb.test()
async def test_random_zero_wait(dut):
    """Random programs, single-cycle memory."""
    await random_campaign(dut, N_PROGS, "zero", "zero", "zero_wait")


@cocotb.test()
async def test_random_mixed_latency(dut):
    """Random programs, randomised fetch/data latency (0-12 cycles)."""
    await random_campaign(dut, N_PROGS, "mixed", "mixed", "mixed_lat")


@cocotb.test()
async def test_random_slow_memory_mdu_heavy(dut):
    """Slow memory + MUL/DIV-heavy mix."""
    mix = {"alu": 10, "alui": 8, "shift": 4, "mul": 20, "div": 20, "load": 10, "store": 10,
           "branch": 10, "loop": 3, "call": 3, "lui": 1, "auipc": 1}
    await random_campaign(dut, max(N_PROGS // 2, 1), "slow", "slow", "slow_mdu", mix=mix)
    if COV.holes():
        dut._log.warning(f"coverage holes: {COV.holes()}")
