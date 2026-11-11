"""RV32IM reference model producing RVFI-format retirement records.

Mirrors the RISC-V unprivileged spec, including M-extension corner cases:
division by zero (quotient = -1 / all ones, remainder = dividend) and signed
overflow (-2^31 / -1 = -2^31, remainder 0)."""

MASK = 0xFFFFFFFF


def s32(v):
    v &= MASK
    return v - (1 << 32) if v & 0x80000000 else v


def sext(v, bits):
    v &= (1 << bits) - 1
    return v - (1 << bits) if v >> (bits - 1) & 1 else v


def _div(a, b, signed):
    if b == 0:
        return MASK
    if signed:
        x, y = s32(a), s32(b)
        if x == -(1 << 31) and y == -1:
            return a
        q = abs(x) // abs(y)
        return (-q if (x < 0) != (y < 0) else q) & MASK
    return a // b


def _rem(a, b, signed):
    if b == 0:
        return a
    if signed:
        x, y = s32(a), s32(b)
        if x == -(1 << 31) and y == -1:
            return 0
        r = abs(x) % abs(y)
        return (-r if x < 0 else r) & MASK
    return a % b


class RV32IM:
    def __init__(self, memory):
        """memory: object with .word(addr) and .mem bytearray (shared layout with the BFM image)."""
        self.mem = bytearray(memory)
        self.x = [0] * 32
        self.pc = 0
        self.ops = {0x37: self._lui, 0x17: self._auipc, 0x6F: self._jal, 0x67: self._jalr,
                    0x63: self._branch, 0x03: self._load, 0x23: self._store, 0x13: self._opimm,
                    0x33: self._op, 0x73: self._system}

    # ------------------------------------------------------------ helpers
    def rd_word(self, a):
        a = a % len(self.mem) & ~3
        return int.from_bytes(self.mem[a:a + 4], "little")

    def _set(self, rec, rd, val):
        if rd:
            self.x[rd] = val & MASK
            rec["rd_addr"], rec["rd_wdata"] = rd, val & MASK

    # ------------------------------------------------------------ execute
    def step(self):
        insn = self.rd_word(self.pc)
        rec = {"pc_rdata": self.pc, "pc_wdata": (self.pc + 4) & MASK, "insn": insn, "trap": 0,
               "rd_addr": 0, "rd_wdata": 0, "mem_addr": 0, "mem_rmask": 0, "mem_wmask": 0,
               "mem_wdata": 0, "mem_rdata": 0}
        f = {"rd": (insn >> 7) & 31, "f3": (insn >> 12) & 7, "rs1": (insn >> 15) & 31,
             "rs2": (insn >> 20) & 31, "f7": insn >> 25}
        f["a"], f["b"] = self.x[f["rs1"]], self.x[f["rs2"]]
        handler = self.ops.get(insn & 0x7F)
        if handler is None:
            rec["trap"], rec["pc_wdata"] = 1, self.pc
        else:
            handler(insn, f, rec)
        self.pc = rec["pc_wdata"]
        return rec

    def _lui(self, i, f, r):
        self._set(r, f["rd"], i & 0xFFFFF000)

    def _auipc(self, i, f, r):
        self._set(r, f["rd"], self.pc + (i & 0xFFFFF000))

    def _jal(self, i, f, r):
        off = sext((((i >> 31) & 1) << 20) | (((i >> 12) & 0xFF) << 12) | (((i >> 20) & 1) << 11) |
                   (((i >> 21) & 0x3FF) << 1), 21)
        self._set(r, f["rd"], self.pc + 4)
        r["pc_wdata"] = (self.pc + off) & MASK

    def _jalr(self, i, f, r):
        tgt = (f["a"] + sext(i >> 20, 12)) & MASK & ~1
        self._set(r, f["rd"], self.pc + 4)
        r["pc_wdata"] = tgt

    def _branch(self, i, f, r):
        a, b = f["a"], f["b"]
        take = {0: a == b, 1: a != b, 4: s32(a) < s32(b), 5: s32(a) >= s32(b), 6: a < b, 7: a >= b}[f["f3"]]
        if take:
            off = sext((((i >> 31) & 1) << 12) | (((i >> 7) & 1) << 11) | (((i >> 25) & 0x3F) << 5) |
                       (((i >> 8) & 0xF) << 1), 13)
            r["pc_wdata"] = (self.pc + off) & MASK

    def _load(self, i, f, r):
        addr = (f["a"] + sext(i >> 20, 12)) & MASK
        w, sh = self.rd_word(addr), 8 * (addr & 3)
        val = {0: sext(w >> sh, 8), 1: sext(w >> sh, 16), 2: w,
               4: (w >> sh) & 0xFF, 5: (w >> sh) & 0xFFFF}[f["f3"]]
        r.update(mem_addr=addr & ~3, mem_rmask=0xF, mem_rdata=w)
        self._set(r, f["rd"], val)

    def _store(self, i, f, r):
        addr = (f["a"] + sext(((i >> 25) << 5) | ((i >> 7) & 31), 12)) & MASK
        nbytes = 1 << f["f3"]
        mask = ((1 << nbytes) - 1) << (addr & 3)
        data = (f["b"] << 8 * (addr & 3)) & MASK
        a = addr % len(self.mem) & ~3
        for k in range(4):
            if mask >> k & 1:
                self.mem[a + k] = (data >> 8 * k) & 0xFF
        r.update(mem_addr=addr & ~3, mem_wmask=mask, mem_wdata=data)

    def _opimm(self, i, f, r):
        imm, a, f3 = sext(i >> 20, 12) & MASK, f["a"], f["f3"]
        sh = (i >> 20) & 31
        val = {0: a + imm, 2: int(s32(a) < s32(imm)), 3: int(a < imm), 4: a ^ imm, 6: a | imm, 7: a & imm,
               1: a << sh, 5: (s32(a) >> sh) if f["f7"] & 0x20 else (a >> sh)}[f3]
        self._set(r, f["rd"], val)

    def _op(self, i, f, r):
        a, b, f3, f7 = f["a"], f["b"], f["f3"], f["f7"]
        if f7 == 1:
            val = {0: a * b,
                   1: (s32(a) * s32(b)) >> 32,
                   2: (s32(a) * b) >> 32,
                   3: (a * b) >> 32,
                   4: _div(a, b, True), 5: _div(a, b, False),
                   6: _rem(a, b, True), 7: _rem(a, b, False)}[f3]
        else:
            sh = b & 31
            val = {0: (a - b) if f7 & 0x20 else (a + b), 1: a << sh, 2: int(s32(a) < s32(b)), 3: int(a < b),
                   4: a ^ b, 5: (s32(a) >> sh) if f7 & 0x20 else (a >> sh), 6: a | b, 7: a & b}[f3]
        self._set(r, f["rd"], val)

    def _system(self, i, f, r):
        r["trap"], r["pc_wdata"] = 1, self.pc   # EBREAK/ECALL end the test (PicoRV32 traps)
