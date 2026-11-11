"""Functional coverage for the PicoRV32 RV32IM verification environment.

Coverpoints are sampled from the reference model's view of each retired
instruction (operands + result) and from the memory BFM (latency per access)."""
import json
import os

from rv32im_model import s32

BASE = ["lui", "auipc", "jal", "jalr", "beq", "bne", "blt", "bge", "bltu", "bgeu",
        "lb", "lh", "lw", "lbu", "lhu", "sb", "sh", "sw",
        "addi", "slti", "sltiu", "xori", "ori", "andi", "slli", "srli", "srai",
        "add", "sub", "sll", "slt", "sltu", "xor", "srl", "sra", "or", "and"]
MEXT = ["mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu"]
LAT_BUCKETS = [(0, "0"), (1, "1"), (3, "2-3"), (7, "4-7"), (10**9, "8+")]


def decode_name(insn):
    op, f3, f7 = insn & 0x7F, (insn >> 12) & 7, insn >> 25
    if op == 0x33:
        if f7 == 1:
            return MEXT[f3]
        return ["sub" if f7 else "add", "sll", "slt", "sltu", "xor", "sra" if f7 else "srl", "or", "and"][f3]
    if op == 0x13:
        return ["addi", "slli", "slti", "sltiu", "xori", "srai" if f7 & 0x20 else "srli", "ori", "andi"][f3]
    if op == 0x03:
        return {0: "lb", 1: "lh", 2: "lw", 4: "lbu", 5: "lhu"}.get(f3, "?")
    if op == 0x23:
        return {0: "sb", 1: "sh", 2: "sw"}.get(f3, "?")
    if op == 0x63:
        return {0: "beq", 1: "bne", 4: "blt", 5: "bge", 6: "bltu", 7: "bgeu"}.get(f3, "?")
    return {0x37: "lui", 0x17: "auipc", 0x6F: "jal", 0x67: "jalr", 0x73: "ebreak"}.get(op, "?")


class CoverageModel:
    def __init__(self):
        self.cp = {
            "instruction": dict.fromkeys(BASE + MEXT, 0),
            "branch_outcome": {f"{b}.{o}": 0 for b in ["beq", "bne", "blt", "bge", "bltu", "bgeu"]
                               for o in ("taken", "not_taken")},
            "m_ext_corner": dict.fromkeys([
                "div_by_zero", "divu_by_zero", "rem_by_zero", "remu_by_zero", "div_overflow",
                "rem_overflow", "div_neg_dividend", "rem_neg_dividend", "div_neg_divisor",
                "mulh_neg_neg", "mulh_neg_pos", "mulhsu_neg_rs1", "mulhu_max", "mul_by_zero"], 0),
            "mem_lane": dict.fromkeys(["sb@0", "sb@1", "sb@2", "sb@3", "sh@0", "sh@2",
                                       "lb@0", "lb@1", "lb@2", "lb@3", "lbu@0", "lbu@3",
                                       "lh@0", "lh@2", "lhu@0", "lhu@2"], 0),
            "latency_x_access": {f"{k}/{b}": 0 for k in ("fetch", "load", "store") for _, b in LAT_BUCKETS},
            "control_flow": dict.fromkeys(["call", "return", "return_odd_addr", "backward_branch_taken",
                                           "forward_branch_taken", "rd_is_x0", "back_to_back_raw",
                                           "store_then_load_same_word"], 0),
        }
        self.prev_rd = 0
        self.last_store_word = None

    def _hit(self, p, b):
        self.cp[p][b] += 1

    def sample_access(self, kind, addr, wstrb, lat):
        b = next(name for lim, name in LAT_BUCKETS if lat <= lim)
        self._hit("latency_x_access", f"{kind}/{b}")

    def sample_retire(self, rec, a, b):
        """rec: model retirement record; a, b: source operand values before execution."""
        insn, name = rec["insn"], decode_name(rec["insn"])
        if name not in self.cp["instruction"]:
            return
        self._hit("instruction", name)
        rd, rs1, rs2 = (insn >> 7) & 31, (insn >> 15) & 31, (insn >> 20) & 31
        if self.prev_rd and self.prev_rd in (rs1, rs2) and name not in ("lui", "auipc", "jal"):
            self._hit("control_flow", "back_to_back_raw")
        if rd == 0 and name not in ("beq", "bne", "blt", "bge", "bltu", "bgeu", "sb", "sh", "sw", "jalr", "jal"):
            self._hit("control_flow", "rd_is_x0")
        pc, npc = rec["pc_rdata"], rec["pc_wdata"]
        if name.startswith("b"):
            taken = npc != pc + 4
            self._hit("branch_outcome", f"{name}.{'taken' if taken else 'not_taken'}")
            if taken:
                self._hit("control_flow", "backward_branch_taken" if npc < pc else "forward_branch_taken")
        if name == "jal" and rd == 1:
            self._hit("control_flow", "call")
        if name == "jalr" and rd == 0:
            self._hit("control_flow", "return")
            if (a + (((insn >> 20) ^ 0x800) - 0x800)) & 1:
                self._hit("control_flow", "return_odd_addr")
        if name in ("div", "divu", "rem", "remu"):
            if b == 0:
                self._hit("m_ext_corner", f"{name}_by_zero")
            if name in ("div", "rem") and a == 0x80000000 and b == 0xFFFFFFFF:
                self._hit("m_ext_corner", f"{name}_overflow")
            if name in ("div", "rem") and s32(a) < 0 and b:
                self._hit("m_ext_corner", f"{name}_neg_dividend")
            if name == "div" and s32(b) < 0:
                self._hit("m_ext_corner", "div_neg_divisor")
        if name == "mulh" and s32(a) < 0 and s32(b) < 0:
            self._hit("m_ext_corner", "mulh_neg_neg")
        if name == "mulh" and (s32(a) < 0) != (s32(b) < 0) and a and b:
            self._hit("m_ext_corner", "mulh_neg_pos")
        if name == "mulhsu" and s32(a) < 0:
            self._hit("m_ext_corner", "mulhsu_neg_rs1")
        if name == "mulhu" and a == b == 0xFFFFFFFF:
            self._hit("m_ext_corner", "mulhu_max")
        if name == "mul" and (a == 0 or b == 0):
            self._hit("m_ext_corner", "mul_by_zero")
        if rec["mem_wmask"] or rec["mem_rmask"]:
            ea_off = {"sb": 0, "sh": 0}.get(name, 0)
            lane = (rec["mem_wmask"] & -rec["mem_wmask"]).bit_length() - 1 if rec["mem_wmask"] else None
            if name in ("sb", "sh") and lane is not None:
                key = f"{name}@{lane + ea_off}"
                if key in self.cp["mem_lane"]:
                    self._hit("mem_lane", key)
            if name in ("lb", "lbu", "lh", "lhu"):
                off = (a + (((insn >> 20) ^ 0x800) - 0x800)) & 3
                key = f"{name}@{off}"
                if key in self.cp["mem_lane"]:
                    self._hit("mem_lane", key)
            if rec["mem_wmask"]:
                self.last_store_word = rec["mem_addr"]
            elif rec["mem_addr"] == self.last_store_word:
                self._hit("control_flow", "store_then_load_same_word")
        self.prev_rd = rec["rd_addr"]

    def score(self):
        bins = [c for p in self.cp.values() for c in p.values()]
        return sum(1 for c in bins if c), len(bins)

    def holes(self):
        return [f"{p}:{b}" for p, d in self.cp.items() for b, c in d.items() if c == 0]

    def save(self, path):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.cp, f, indent=2)


COV = CoverageModel()
