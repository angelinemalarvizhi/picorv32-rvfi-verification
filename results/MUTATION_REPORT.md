# Mutation testing report

**Mutation score: 13/13 = 100%**

| id | mutation | sites | result | killed by |
|---|---|---|---|---|
| M01 | SLT/BLT compare unsigned | 1 | KILLED | test_isa_smoke, test_random_zero_wait, test_random_mixed_latency, test_random_slow_memory_mdu_heavy |
| M02 | SUB performs ADD | 1 | KILLED | test_isa_smoke, test_random_zero_wait, test_random_mixed_latency, test_random_slow_memory_mdu_heavy |
| M03 | SRA by >=4 is logical | 1 | KILLED | test_isa_smoke, test_random_zero_wait, test_random_mixed_latency, test_random_slow_memory_mdu_heavy |
| M04 | BGEU behaves as BLTU | 1 | KILLED | test_isa_smoke, test_random_zero_wait, test_random_mixed_latency, test_random_slow_memory_mdu_heavy |
| M05 | LB zero-extends | 1 | KILLED | test_isa_smoke, test_memory_lanes, test_random_zero_wait, test_random_mixed_latency, test_random_slow_memory_mdu_heavy |
| M06 | LH zero-extends | 1 | KILLED | test_isa_smoke, test_memory_lanes, test_random_zero_wait, test_random_mixed_latency |
| M07 | SB always writes byte lane 0 | 1 | KILLED | test_isa_smoke, test_memory_lanes, test_random_zero_wait, test_random_mixed_latency, test_random_slow_memory_mdu_heavy |
| M08 | JALR does not clear bit 0 | 2 | KILLED | test_random_zero_wait, test_random_mixed_latency, test_random_slow_memory_mdu_heavy |
| M09 | MULH treats rs2 as unsigned | 2 | KILLED | test_m_extension_corners, test_random_zero_wait, test_random_mixed_latency, test_random_slow_memory_mdu_heavy |
| M10 | MULH* return the low word | 1 | KILLED | test_m_extension_corners, test_random_zero_wait, test_random_mixed_latency, test_random_slow_memory_mdu_heavy |
| M11 | DIV by zero: sign fix-up wrongly applied | 1 | KILLED | test_m_extension_corners, test_random_zero_wait |
| M12 | REM sign follows divisor instead of dividend | 1 | KILLED | test_m_extension_corners, test_random_mixed_latency, test_random_slow_memory_mdu_heavy |
| M13 | fetch uses live (unlatched) bus data | 1 | KILLED | test_isa_smoke, test_m_extension_corners, test_random_zero_wait, test_random_mixed_latency, test_random_slow_memory_mdu_heavy |
