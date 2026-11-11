"""Constrained-random RV32IM test-program generator (emits assembly text).

Program shape
    prologue   : x31 = data base, x2..x28 random (30% special values)
    body       : weighted mix of ALU, shifts, MUL/DIV (with corner-operand
                 injection), loads/stores, forward branches to labels,
                 counted backward loops, calls to leaf functions
    ebreak
    functions  : leaf bodies ending in `jalr x0, 0(x1)` (sometimes via an odd address)

Reserved registers: x1 = ra, x29 = scratch, x30 = loop counter, x31 = data base.
"""
import random

from asm import BR, I, LD, R, SH, ST

DATA_BASE = 0x1000
BASE_ALU = [m for m in R if R[m][0] != 1]
MUL = ["mul", "mulh", "mulhsu", "mulhu"]
DIV = ["div", "divu", "rem", "remu"]
SPECIAL = ["0", "1", "-1", "0x80000000", "0x7fffffff", "0xffff", "0x8000", "0xff", "0x80"]
DEFAULT_MIX = {"alu": 22, "alui": 16, "shift": 8, "mul": 8, "div": 7, "load": 12, "store": 10,
               "branch": 10, "loop": 3, "call": 3, "lui": 2, "auipc": 1}


class ProgramGen:
    def __init__(self, rng=None, length=150, mix=None, dep_bias=0.4):
        self.g = rng or random.Random()
        self.length, self.mix, self.dep_bias = length, mix or DEFAULT_MIX, dep_bias
        self.pool = [f"x{k}" for k in range(2, 29)]
        self.last_rd = None
        self.lines, self.funcs = [], []
        self.pending = {}          # body index -> [labels]
        self.nlab = 0

    # ---------------------------------------------------------- helpers
    def rd(self):
        r = "x0" if self.g.random() < 0.03 else self.g.choice(self.pool)
        self.last_rd = r
        return r

    def rs(self):
        if self.last_rd and self.last_rd != "x0" and self.g.random() < self.dep_bias:
            return self.last_rd
        return self.g.choice(["x0"] + self.pool)

    def imm(self):
        return str(self.g.choice([0, 1, -1, 2047, -2048, self.g.randint(-2048, 2047)]))

    def label(self):
        self.nlab += 1
        return f"L{self.nlab}"

    def emit(self, s):
        self.lines.append("    " + s)

    # ---------------------------------------------------------- items
    def simple(self, kind):
        g = self.g
        if kind == "alu":
            return [f"{g.choice(BASE_ALU)} {self.rd()}, {self.rs()}, {self.rs()}"]
        if kind == "alui":
            return [f"{g.choice(list(I))} {self.rd()}, {self.rs()}, {self.imm()}"]
        if kind == "shift":
            return [f"{g.choice(list(SH))} {self.rd()}, {self.rs()}, {g.randint(0, 31)}"]
        if kind == "mul":
            return [f"{g.choice(MUL)} {self.rd()}, {self.rs()}, {self.rs()}"]
        if kind == "div":
            a, b, out = self.rs(), self.rs(), []
            p = g.random()
            if p < 0.15:                       # divide by zero
                b = "x29"
                out.append("li x29, 0")
            elif p < 0.25:                     # signed overflow  -2^31 / -1
                a, b = "x29", "x30"
                out += ["li x29, 0x80000000", "li x30, -1"]
            return out + [f"{g.choice(DIV)} {self.rd()}, {a}, {b}"]
        if kind in ("load", "store"):
            mn = g.choice(list(LD) if kind == "load" else list(ST))
            size = {"b": 1, "h": 2, "w": 4}[mn[1]]
            off = g.randrange(0, 2048, size)
            if kind == "store":
                return [f"{mn} {self.rs()}, {off}(x31)"]
            return [f"{mn} {self.rd()}, {off}(x31)"]
        if kind == "lui":
            return [f"lui {self.rd()}, {g.getrandbits(20)}"]
        if kind == "auipc":
            return [f"auipc {self.rd()}, {g.getrandbits(20)}"]
        raise ValueError(kind)

    def item(self, idx):
        g = self.g
        kind = g.choices(list(self.mix), list(self.mix.values()))[0]
        if kind == "branch":
            tgt = self.label()
            self.pending.setdefault(min(idx + g.randint(1, 5), self.length), []).append(tgt)
            a = self.rs()
            b = a if g.random() < 0.3 else self.rs()
            return [f"{g.choice(list(BR))} {a}, {b}, {tgt}"]
        if kind == "loop":
            top = self.label()
            body = [ln for _ in range(g.randint(1, 3))
                    for ln in self.simple(g.choice(["alu", "alui", "mul", "load", "store"]))]
            body = [ln for ln in body if "x30" not in ln]
            return [f"li x30, {g.randint(1, 4)}", f"{top}:"] + body + \
                   ["addi x30, x30, -1", f"bne x30, x0, {top}"]
        if kind == "call":
            fn = f"F{len(self.funcs)}"
            body = [ln for _ in range(g.randint(1, 3)) for ln in self.simple(g.choice(["alu", "alui", "mul"]))]
            if g.random() < 0.3:
                ret = ["addi x29, x1, 1", "jalr x0, 0(x29)"]     # odd return address: bit 0 must be cleared
            else:
                ret = ["jalr x0, 0(x1)"]
            self.funcs.append([f"{fn}:"] + body + ret)
            return [f"jal x1, {fn}"]
        return self.simple(kind)

    # ---------------------------------------------------------- program
    def program(self):
        g = self.g
        self.emit(f"li x31, {DATA_BASE:#x}")
        for r in self.pool:
            v = g.choice(SPECIAL) if g.random() < 0.3 else hex(g.getrandbits(32))
            self.emit(f"li {r}, {v}")
        for idx in range(self.length):
            for lab in self.pending.pop(idx, []):
                self.lines.append(f"{lab}:")
            for ln in self.item(idx):
                self.lines.append(ln if ln.endswith(":") else "    " + ln)
        for labs in self.pending.values():
            for lab in labs:
                self.lines.append(f"{lab}:")
        self.emit("ebreak")
        for f in self.funcs:
            self.lines += [ln if ln.endswith(":") else "    " + ln for ln in f]
        return "\n".join(self.lines) + "\n"

    def data_image(self, nwords=1024):
        return [int(self.g.choice(SPECIAL), 0) & 0xFFFFFFFF if self.g.random() < 0.2
                else self.g.getrandbits(32) for _ in range(nwords)]
