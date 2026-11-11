# PicoRV32 RV32IM Processor Verification: RVFI Trace Comparison + Mutation Testing

A verification environment for the open-source **PicoRV32** RISC-V core (configured as **RV32IM**).
Every retired instruction is compared on **16 RVFI fields** against an independent reference model, while a
**randomised-latency memory BFM** stresses the bus interface. The testbench's own quality is measured with
**mutation testing**: 13 realistic bugs are planted in the RTL, and the testbench must find every one.

![regression](../../actions/workflows/regression.yml/badge.svg)

## Environment
```
  stimgen.py ──► assembly text ──► asm.py (2-pass assembler) ──► program image
                                                                     │
              ┌──────────────────────── cocotb ──────────────────────┼──────────────────┐
              │  mem_bfm.py  ◄── mem_valid/addr/wstrb ──  PicoRV32   │                  │
              │  random latency, ──► mem_ready/rdata ──►  (RV32IM)   │                  │
              │  scrambled idle data                         │ RVFI  ▼                  │
              │                                              └──► compare ◄── rv32im_model.py
              │  coverage_model.py ◄── retire records + bus accesses                    │
              └─────────────────────────────────────────────────────────────────────────┘
```
| Component | What it does |
|---|---|
| `tb/rv32im_model.py` | RV32IM reference model (spec-exact div/rem corner cases), emits RVFI records |
| `tb/asm.py` | two-pass text assembler with labels and pseudo-instructions |
| `tb/stimgen.py` | random programs: ALU/shift/MUL/DIV with corner-operand injection, loads/stores, forward branches, counted loops, calls to leaf functions (incl. odd return addresses) |
| `tb/mem_bfm.py` | native-bus slave with latency profiles; checks request stability; drives **random data on `mem_rdata` while not ready** |
| `tb/coverage_model.py` | 110 bins: 45 instructions, branch outcomes, 14 M-extension corners, 16 memory lanes, a 3×5 access-type × latency cross, control flow |
| `sva/mem_if_sva.sv` | 9 assertions + 3 covers on the bus protocol and RVFI consistency (bind file included) |
| `scripts/mutate.py` | mutation-testing engine (13 mutants) |
| `scripts/sweep.py` | multi-seed regression with merged coverage |

## Results
| Metric | Result |
|---|---|
| Seeds × tests | 10 × 6, all pass |
| Instructions compared on 16 fields | **~72,000** |
| Functional coverage | **110/110 bins (100%)** |
| Mutation score | **13/13 (100%)** |
| Mean CPI, zero-wait / mixed / slow+MDU-heavy memory | 9.7 / 10.9 / 22.3 (iterative shifter, 32-cycle MUL/DIV) |

### Mutation testing
| id | planted bug | killed by |
|---|---|---|
| M01 | signed compare done unsigned | smoke, random |
| M02 | SUB performs ADD | smoke, random |
| M03 | SRA by ≥4 is logical | smoke, random |
| M04 | BGEU behaves as BLTU | smoke, random |
| M05/M06 | LB/LH zero-extend | lanes, random |
| M07 | SB always writes lane 0 | lanes, random |
| M08 | JALR keeps bit 0 | random (odd return address) |
| M09/M10 | MULH sign / high-word errors | M-corners, random |
| M11 | divide-by-zero sign fix-up | M-corners |
| M12 | REM sign follows divisor | M-corners |
| M13 | core samples live bus data instead of latched data | all (after BFM fix) |

**Finding:** M13 **survived** the first run. The BFM held `mem_rdata` stable after each transfer, which hid
the bug. Real buses guarantee nothing outside the handshake, so the BFM now drives random data whenever
`mem_ready` is low. With that change M13 is killed by every test. Reproduce the original escape with
`BUS_SCRAMBLE=0 python3 scripts/mutate.py --only M13`.

## Run it
```bash
sudo apt install -y iverilog python3-pip make
pip install -r requirements.txt

make                                       # 6 tests: 3 directed + 3 random (zero/mixed/slow memory)
make NUM_PROGS=30 SEED=99                  # more programs, reproducible
python3 scripts/sweep.py --seeds 10 --progs 10     # -> results/SWEEP_REPORT.md
python3 scripts/mutate.py                          # -> results/MUTATION_REPORT.md
```
Failing programs are saved as `results/failing_<test>.S` for debugging.

## Structure
```
rtl/      picorv32.v (unmodified upstream, ISC)  dut_top.v (RV32IM + RVFI wrapper)
tb/       test_picorv32.py  rv32im_model.py  asm.py  stimgen.py  mem_bfm.py  coverage_model.py
sva/      mem_if_sva.sv  bind.sv
scripts/  sweep.py  mutate.py
docs/     testplan.md
```

## Next steps
- Enable `COMPRESSED_ISA` and extend the model/assembler to RV32IMC
- IRQ verification (`ENABLE_IRQ=1`): random interrupt injection against the model
- Cross-check the model against Spike on generated programs
- Formal checks with riscv-formal using the same RVFI port
