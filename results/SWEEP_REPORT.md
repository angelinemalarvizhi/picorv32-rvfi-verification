# Seed sweep report

10 seeds, 10 programs per random test

| seed | tests | result | programs | instructions checked |
|---|---|---|---|---|
| 451001921 | 6 | PASS | 28 | 7122 |
| 929072927 | 6 | PASS | 28 | 7362 |
| 1522151854 | 6 | PASS | 28 | 7216 |
| 275371948 | 6 | PASS | 28 | 6990 |
| 990532625 | 6 | PASS | 28 | 7413 |
| 2120016617 | 6 | PASS | 28 | 7382 |
| 380750736 | 6 | PASS | 28 | 7081 |
| 1311380406 | 6 | PASS | 28 | 7182 |
| 575099489 | 6 | PASS | 28 | 7407 |
| 747971689 | 6 | PASS | 28 | 7023 |

**280 programs, 72178 instructions compared against the model.**

| memory profile | mean CPI |
|---|---|
| zero_wait | 9.35 |
| mixed_lat | 10.97 |
| slow_mdu | 22.60 |

## Coverage: 110/110 bins (100.0%)

* `instruction`: 45/45
* `branch_outcome`: 12/12
* `m_ext_corner`: 14/14
* `mem_lane`: 16/16
* `latency_x_access`: 15/15
* `control_flow`: 8/8
