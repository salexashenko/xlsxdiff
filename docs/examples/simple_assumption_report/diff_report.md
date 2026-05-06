# Workbook Diff Report

Compared:
- Baseline: `baseline.xlsx` `464a8ca5f82b`
- Candidate: `candidate.xlsx` `6ef5c6c9dfe9`
- Generated: 2026-05-06T00:56:25.956212+00:00
- Overall confidence: **high**

## Executive summary

1. Summary!G31 Total LTV changed from 1180 to 1220 (+40.0 / +3.4%), likely explained by Assumptions!D14 2026 Growth Rate changing from 0.18 to 0.22; 0 unexplained value changes were detected.
2. Formula changes: **0**.
3. Outputs changed: **2**.
4. Unexplained changes: **0**.

## Top direct changes

| Type | Location | Label | Old | New | Delta |
|---|---|---|---:|---:|---:|
| constant_changed | `Assumptions!D14` | 2026 Growth Rate | 0.18 | 0.22 | +4.00 pp |

## Top impacted outputs

| Output | Location | Old | New | Delta | Explanation strength | Likely upstream changes | Caveats |
|---|---|---:|---:|---:|---|---|---|
| 2027 Revenue | `Revenue!G22` | 1180 | 1220 | +40.0 / +3.4% | strong | `Assumptions!D14` |  |
| Total LTV | `Summary!G31` | 1180 | 1220 | +40.0 / +3.4% | strong | `Assumptions!D14` |  |

## Change DAG

- `Assumptions!D14` -> `Revenue!G22` (cell_reference)
- `Revenue!G22` -> `Summary!G31` (cell_reference)

## Diagnostics

- **CACHED_VALUE_MODE**: This report uses cached formula results. Numeric output deltas assume both workbooks were saved after recalculation.
