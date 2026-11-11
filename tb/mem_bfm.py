"""Native-interface memory slave for PicoRV32 with randomised response latency.

Latency profile per access is drawn from a configurable distribution so the
core sees 0-wait, short and long stalls, separately for fetches and data."""
import random

from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge

_XMAP = str.maketrans("xXzZuUwWlLhH-", "0000000000010")


def uint(sig):
    """Integer value of a signal with X/Z resolved to 0 (core leaves wdata undriven on reads)."""
    return int(str(sig.value).translate(_XMAP), 2)


class LatencyProfile:
    def __init__(self, name, weights):
        self.name, self.weights = name, weights  # {latency: weight}

    def draw(self, rng):
        return rng.choices(list(self.weights), list(self.weights.values()))[0]


PROFILES = {
    "zero":   LatencyProfile("zero", {0: 1}),
    "fixed1": LatencyProfile("fixed1", {1: 1}),
    "mixed":  LatencyProfile("mixed", {0: 50, 1: 20, 2: 10, 3: 10, 6: 5, 12: 5}),
    "slow":   LatencyProfile("slow", {4: 40, 8: 40, 16: 20}),
}


class MemoryBFM:
    SIZE = 64 * 1024

    def __init__(self, dut, rng=random, ifetch="mixed", data="mixed", scramble=True):
        """scramble: drive random garbage on mem_rdata whenever mem_ready is low.
        A real bus gives no guarantee about rdata outside the handshake; holding it
        stable hides bugs where the core samples data at the wrong time."""
        self.dut, self.rng, self.scramble = dut, rng, scramble
        self.mem = bytearray(self.SIZE)
        self.prof_i, self.prof_d = PROFILES[ifetch], PROFILES[data]
        self.on_access = None          # callback(kind, addr, wstrb, latency) for coverage
        self.violations = []
        dut.mem_ready.value = 0
        dut.mem_rdata.value = 0

    def load_words(self, base, words):
        for k, w in enumerate(words):
            self.mem[base + 4 * k: base + 4 * k + 4] = (w & 0xFFFFFFFF).to_bytes(4, "little")

    def word(self, addr):
        a = addr % self.SIZE & ~3
        return int.from_bytes(self.mem[a:a + 4], "little")

    async def run(self):
        d = self.dut
        pending = None  # (addr, wstrb, wdata, instr, remaining)
        while True:
            await RisingEdge(d.clk)
            await ReadOnly()
            valid = str(d.mem_valid.value) == "1"
            ready = str(d.mem_ready.value) == "1"
            if ready:
                pending = None            # handshake completed at this edge
            elif valid:
                cur = (uint(d.mem_addr), uint(d.mem_wstrb), uint(d.mem_wdata),
                       str(d.mem_instr.value) == "1")
                if pending is None:
                    prof = self.prof_i if cur[3] else self.prof_d
                    lat = prof.draw(self.rng)
                    pending = [*cur, lat]
                    if self.on_access:
                        kind = "fetch" if cur[3] else ("store" if cur[1] else "load")
                        self.on_access(kind, cur[0], cur[1], lat)
                elif tuple(pending[:4]) != cur:
                    self.violations.append(f"mem request changed while waiting: {pending[:4]} -> {cur}")
            await FallingEdge(d.clk)
            if ready:
                d.mem_ready.value = 0
                if self.scramble:
                    d.mem_rdata.value = self.rng.getrandbits(32)
            elif pending is not None:
                if pending[4] == 0:
                    addr, wstrb, wdata, _ = pending[:4]
                    a = addr % self.SIZE & ~3
                    if wstrb:
                        for b in range(4):
                            if wstrb >> b & 1:
                                self.mem[a + b] = (wdata >> 8 * b) & 0xFF
                    d.mem_rdata.value = self.word(addr)
                    d.mem_ready.value = 1
                else:
                    pending[4] -= 1
                    if self.scramble:
                        d.mem_rdata.value = self.rng.getrandbits(32)
