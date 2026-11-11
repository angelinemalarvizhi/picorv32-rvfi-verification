# Verification Test Plan: PicoRV32 (RV32IM) core

## DUT
PicoRV32 configured as RV32IM (`ENABLE_MUL=1`, `ENABLE_DIV=1`, iterative shifter, misalignment and illegal-instruction traps enabled)
with the RISC-V Formal Interface (RVFI) trace port enabled.

## Method
1. **Reference model** (`tb/rv32im_model.py`): instruction-accurate RV32IM model producing RVFI records.
2. **Per-instruction comparison** of 16 RVFI fields: `order, pc_rdata, pc_wdata, insn, trap, rd_addr, rd_wdata,
   rs1/rs2 addr+rdata, mem_addr, mem_rmask, mem_wmask, mem_wdata (active lanes), mem_rdata`.
3. **Memory BFM** (`tb/mem_bfm.py`) on the native `mem_valid/mem_ready` interface, with per-access random latency
   (profiles: zero / mixed 0–12 / slow 4–16 cycles), protocol checks (request must stay stable while waiting), and
   **random data on `mem_rdata` when `mem_ready` is low**.
4. **Random programs** (`tb/stimgen.py`) written as assembly text with labels, then put through the in-house two-pass assembler (`tb/asm.py`).
5. **Mutation testing** (`scripts/mutate.py`): 13 hand-written RTL mutants measure how many bugs the testbench finds.

## Features → stimulus → coverage
| ID | Feature | Stimulus | Coverage points |
|---|---|---|---|
| F1 | 37 RV32I instructions | `test_isa_smoke` (hand-checked results), random | `instruction` |
| F2 | 8 M-extension instructions | `test_m_extension_corners` (7×7 operand grid), MDU-heavy random | `instruction`, `m_ext_corner` |
| F3 | Div-by-zero, −2³¹/−1 overflow, MULH sign combos | operand grid + generator injection | `m_ext_corner.*` |
| F4 | Byte/half stores and loads in every lane, sign/zero extension | `test_memory_lanes` | `mem_lane.*` |
| F5 | Branch taken/not taken, forward and backward | generator: forward labels, counted loops | `branch_outcome`, `control_flow` |
| F6 | Calls/returns, JALR bit-0 clearing | generator leaf functions with odd return address | `control_flow.call/return/return_odd_addr` |
| F7 | Memory latency tolerance for fetch, load and store | 3 latency profiles | `latency_x_access` (3×5 cross) |
| F8 | Bus protocol (hold/stability, legal strobes, aligned) | all tests | BFM checks + `sva/mem_if_sva.sv` |
| F9 | RVFI consistency (order increments, x0 reads as 0) | all tests | comparison + SVA |

## Exit criteria
* 0 mismatches over ≥10 seeds
* 110/110 coverage bins
* Mutation score 100% (all 13 mutants killed)
