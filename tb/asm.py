"""Two-pass text assembler for RV32IM (subset used by the generator and directed tests).

    words = assemble('''
        li   x1, 0x1234
    loop:
        addi x1, x1, -1
        bne  x1, x0, loop
        ebreak
    ''')
Supports labels, `li` (always 2 words), `nop`, `mv`, `j`, `ebreak`, `.word`.
"""
import re

R = {"add": (0, 0), "sub": (0x20, 0), "sll": (0, 1), "slt": (0, 2), "sltu": (0, 3), "xor": (0, 4),
     "srl": (0, 5), "sra": (0x20, 5), "or": (0, 6), "and": (0, 7),
     "mul": (1, 0), "mulh": (1, 1), "mulhsu": (1, 2), "mulhu": (1, 3),
     "div": (1, 4), "divu": (1, 5), "rem": (1, 6), "remu": (1, 7)}
I = {"addi": 0, "slti": 2, "sltiu": 3, "xori": 4, "ori": 6, "andi": 7}
SH = {"slli": (0, 1), "srli": (0, 5), "srai": (0x20, 5)}
LD = {"lb": 0, "lh": 1, "lw": 2, "lbu": 4, "lhu": 5}
ST = {"sb": 0, "sh": 1, "sw": 2}
BR = {"beq": 0, "bne": 1, "blt": 4, "bge": 5, "bltu": 6, "bgeu": 7}
SIZE2 = {"li"}


def reg(t):
    t = t.strip()
    m = re.fullmatch(r"x(\d+)", t)
    if not m or int(m.group(1)) > 31:
        raise ValueError(f"bad register {t!r}")
    return int(m.group(1))


def num(t, labels=None, pc=None):
    t = t.strip()
    if labels is not None and t in labels:
        return labels[t] - pc
    return int(t, 0)


def _fit(v, bits, what):
    lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    if not lo <= v <= hi:
        raise ValueError(f"{what} {v} out of range")
    return v & ((1 << bits) - 1)


def encode(mn, ops, labels, pc):
    if mn in R:
        f7, f3 = R[mn]
        rd, a, b = map(reg, ops)
        return (f7 << 25) | (b << 20) | (a << 15) | (f3 << 12) | (rd << 7) | 0x33
    if mn in I:
        rd, a = reg(ops[0]), reg(ops[1])
        return (_fit(num(ops[2]), 12, "imm") << 20) | (a << 15) | (I[mn] << 12) | (rd << 7) | 0x13
    if mn in SH:
        f7, f3 = SH[mn]
        rd, a, sh = reg(ops[0]), reg(ops[1]), num(ops[2]) & 31
        return (f7 << 25) | (sh << 20) | (a << 15) | (f3 << 12) | (rd << 7) | 0x13
    if mn in LD or mn in ST or mn == "jalr":
        m = re.fullmatch(r"\s*(-?\w+)\((x\d+)\)\s*", ops[1])
        off, base = (num(m.group(1)), reg(m.group(2))) if m else (num(ops[2]), reg(ops[1]))
        if mn in ST:
            o = _fit(off, 12, "offset")
            return ((o >> 5) << 25) | (reg(ops[0]) << 20) | (base << 15) | (ST[mn] << 12) | ((o & 31) << 7) | 0x23
        f3, op = (LD[mn], 0x03) if mn in LD else (0, 0x67)
        return (_fit(off, 12, "offset") << 20) | (base << 15) | (f3 << 12) | (reg(ops[0]) << 7) | op
    if mn in BR:
        o = _fit(num(ops[2], labels, pc), 13, "branch")
        return (((o >> 12) & 1) << 31) | (((o >> 5) & 0x3F) << 25) | (reg(ops[1]) << 20) | \
            (reg(ops[0]) << 15) | (BR[mn] << 12) | (((o >> 1) & 0xF) << 8) | (((o >> 11) & 1) << 7) | 0x63
    if mn == "jal":
        o = _fit(num(ops[1], labels, pc), 21, "jump")
        return (((o >> 20) & 1) << 31) | (((o >> 1) & 0x3FF) << 21) | (((o >> 11) & 1) << 20) | \
            (((o >> 12) & 0xFF) << 12) | (reg(ops[0]) << 7) | 0x6F
    if mn in ("lui", "auipc"):
        return ((num(ops[1]) & 0xFFFFF) << 12) | (reg(ops[0]) << 7) | (0x37 if mn == "lui" else 0x17)
    raise ValueError(f"unknown mnemonic {mn!r}")


def expand(mn, ops):
    """Pseudo-instructions -> list of (mnemonic, operands)."""
    if mn == "li":
        v = num(ops[1]) & 0xFFFFFFFF
        lo = v & 0xFFF
        lo = lo - 0x1000 if lo & 0x800 else lo
        hi = ((v - lo) >> 12) & 0xFFFFF
        return [("lui", [ops[0], str(hi)]), ("addi", [ops[0], ops[0], str(lo)])]
    if mn == "nop":
        return [("addi", ["x0", "x0", "0"])]
    if mn == "mv":
        return [("addi", [ops[0], ops[1], "0"])]
    if mn == "j":
        return [("jal", ["x0", ops[0]])]
    return [(mn, ops)]


def assemble(src, base=0):
    lines = src.splitlines() if isinstance(src, str) else list(src)
    items, labels, pc = [], {}, base
    for ln in lines:
        ln = ln.split("#")[0].strip()
        while ":" in ln:
            lab, ln = ln.split(":", 1)
            labels[lab.strip()] = pc
            ln = ln.strip()
        if not ln:
            continue
        parts = ln.split(None, 1)
        mn, ops = parts[0].lower(), [o.strip() for o in parts[1].split(",")] if len(parts) > 1 else []
        if mn == ".word":
            items.append((pc, ".word", ops))
            pc += 4
            continue
        if mn == "ebreak":
            items.append((pc, "ebreak", []))
            pc += 4
            continue
        for e in expand(mn, ops):
            items.append((pc, *e))
            pc += 4
    out = []
    for pc, mn, ops in items:
        if mn == ".word":
            out.append(num(ops[0]) & 0xFFFFFFFF)
        elif mn == "ebreak":
            out.append(0x00100073)
        else:
            out.append(encode(mn, ops, labels, pc))
    return out
