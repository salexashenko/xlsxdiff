# Workbook Diff Report

Compared:
- Baseline: `ai_arr_capex_model_v1_march.xlsx` `191e2e4e18e4`
- Candidate: `ai_arr_capex_model_v2_may.xlsx` `f26069df8d8d`
- Generated: 2026-05-05T21:17:16.749291+00:00
- Overall confidence: **high**

## Executive summary

1. Summary!D6 2027 market coverage changed from 0.261522095556 to 0.34370748144 (+8.22 pp / +31.4%), associated with Assumptions!B14 Anchor ARR Anthropic changing from 19 to 30 and 7 other top direct change(s); 0 unexplained value changes were detected.
2. Formula changes: **6**.
3. Outputs changed: **96**.
4. Unexplained changes: **0**.

## Top direct changes

| Type | Location | Label | Old | New | Delta |
|---|---|---|---:|---:|---:|
| constant_changed | `Assumptions!B14` | Anchor ARR Anthropic | 19 | 30 | +11.0 / +57.9% |
| constant_changed | `Assumptions!D13` | 2026 exit growth S1 | 0.4 | 0.6 | +20.0 pp |
| constant_changed | `Assumptions!D14` | 2026 exit growth S2/S3 | 0.58 | 0.73 | +15.0 pp |
| constant_changed | `Assumptions!E14` | 2027 ARR growth S2/S3 | 0.83 | 0.63 | -20.0 pp |
| constant_changed | `Assumptions!F13` | Compute spend / ARR S1 | 0.55 | 0.58 | +3.00 pp |
| constant_changed | `Assumptions!C8` | 2027E Capex support multiple | 4 | 4.5 | +0.50 / +12.5% |
| constant_changed | `Assumptions!F14` | Compute spend / ARR S2/S3 | 0.65 | 0.68 | +3.00 pp |
| constant_changed | `Assumptions!G13` | Hyperscaler-hosted share S1 | 0.8 | 0.82 | +2.00 pp |
| formula_reference_changed | `Capex_Model!G11` | Capex_Model | =G8*G10 | =G8*G9*G10 | +108.3 / +46.0% |
| constant_changed | `Assumptions!G14` | Hyperscaler-hosted share S2/S3 | 0.85 | 0.88 | +3.00 pp |
| constant_changed | `Assumptions!B8` | 2026E Capex support multiple | 4 | 4.5 | +0.50 / +12.5% |
| constant_changed | `Assumptions!B7` | 2026E Hyperscaler capex market | 610 | 725 | +115.0 / +18.9% |
| constant_changed | `Assumptions!C9` | 2027E Capex realization factor | 1 | 0.9 | -10.00 pp |
| formula_reference_changed | `Capex_Model!F11` | Supportable hyperscaler capex ($B) | =F8*F10 | =F8*F9*F10 | +79.4 / +62.1% |
| formula_reference_changed | `Capex_Model!E11` | Supportable hyperscaler capex ($B) | =E8*E10 | =E8*E9*E10 | +83.6 / +68.9% |

## Top impacted outputs

| Output | Location | Old | New | Delta | Explanation strength | Likely upstream changes |
|---|---|---:|---:|---:|---|---|
| Anthropic 2026E Anchor ARR / prior-year ARR ($B) | `Capex_Model!D4` | 19 | 30 | +11.0 / +57.9% | strong | `Assumptions!B14` |
| Anthropic 2026E Exit ARR ($B) | `Capex_Model!D5` | 30.02 | 51.9 | +21.9 / +72.9% | moderate | `Assumptions!B14`, `Assumptions!D14` |
| OpenAI 2026E Exit ARR ($B) | `Capex_Model!B5` | 35 | 40 | +5.00 / +14.3% | strong | `Assumptions!D13` |
| Anthropic 2027E Exit ARR ($B) | `Capex_Model!E5` | 54.9366 | 84.597 | +29.7 / +54.0% | moderate | `Assumptions!B14`, `Assumptions!D14`, `Assumptions!E14` |
| Anthropic 2027E Annual hyperscaler AI service revenue ($B) | `Capex_Model!E8` | 30.3524715 | 50.6228448 | +20.3 / +66.8% | moderate | `Assumptions!B14`, `Assumptions!D14`, `Assumptions!E14`, `Assumptions!F14`, `Assumptions!G14` |
| Anthropic 2026E Annual hyperscaler AI service revenue ($B) | `Capex_Model!D8` | 16.58605 | 31.05696 | +14.5 / +87.2% | moderate | `Assumptions!B14`, `Assumptions!D14`, `Assumptions!F14`, `Assumptions!G14` |
| OpenAI 2026E Annual hyperscaler AI service revenue ($B) | `Capex_Model!B8` | 15.4 | 19.024 | +3.62 / +23.5% | moderate | `Assumptions!D13`, `Assumptions!F13`, `Assumptions!G13` |
| OpenAI 2027E Annual hyperscaler AI service revenue ($B) | `Capex_Model!C8` | 28.49 | 34.2432 | +5.75 / +20.2% | moderate | `Assumptions!D13`, `Assumptions!E13`, `Assumptions!F13`, `Assumptions!G13` |
| Total 2027E | `Capex_Model!G8` | 58.8424715 | 84.8660448 | +26.0 / +44.2% | moderate | `Assumptions!D13`, `Assumptions!E13`, `Assumptions!F13`, `Assumptions!G13`, `Assumptions!B14`, `Assumptions!D14`, `Assumptions!E14`, `Assumptions!F14`, `Assumptions!G14` |
| Total 2026E Annual hyperscaler AI service revenue ($B) | `Capex_Model!F8` | 31.98605 | 50.08096 | +18.1 / +56.6% | moderate | `Assumptions!D13`, `Assumptions!F13`, `Assumptions!G13`, `Assumptions!B14`, `Assumptions!D14`, `Assumptions!F14`, `Assumptions!G14` |
| Actual 2027 support total ties to companies | `Checks!B6` | 235.369886 | 343.70748144 | +108.3 / +46.0% | moderate | `Assumptions!C8`, `Assumptions!C9`, `Assumptions!D13`, `Assumptions!E13`, `Assumptions!F13`, `Assumptions!G13`, `Assumptions!B14`, `Assumptions!D14`, `Assumptions!E14`, `Assumptions!F14`, `Assumptions!G14`, `Capex_Model!G11` |
| Expected 2027 support total ties to companies | `Checks!C6` | 235.369886 | 343.70748144 | +108.3 / +46.0% | moderate | `Assumptions!C8`, `Assumptions!C9`, `Assumptions!D13`, `Assumptions!E13`, `Assumptions!F13`, `Assumptions!G13`, `Assumptions!B14`, `Assumptions!D14`, `Assumptions!E14`, `Assumptions!F14`, `Assumptions!G14`, `Capex_Model!C11`, `Capex_Model!E11` |
| Actual 2026 support total ties to companies | `Checks!B5` | 127.9442 | 207.3351744 | +79.4 / +62.1% | moderate | `Assumptions!B8`, `Assumptions!B9`, `Assumptions!D13`, `Assumptions!F13`, `Assumptions!G13`, `Assumptions!B14`, `Assumptions!D14`, `Assumptions!F14`, `Assumptions!G14`, `Capex_Model!F11` |
| Expected 2026 support total ties to companies | `Checks!C5` | 127.9442 | 207.3351744 | +79.4 / +62.1% | moderate | `Assumptions!B8`, `Assumptions!B9`, `Assumptions!D13`, `Assumptions!F13`, `Assumptions!G13`, `Assumptions!B14`, `Assumptions!D14`, `Assumptions!F14`, `Assumptions!G14`, `Capex_Model!B11`, `Capex_Model!D11` |
| OpenAI 2027E Exit ARR ($B) | `Capex_Model!C5` | 64.75 | 72 | +7.25 / +11.2% | moderate | `Assumptions!D13`, `Assumptions!E13` |

## Change DAG

- `Capex_Model!C11` -> `Checks!C6` (cell_reference)
- `Capex_Model!G11` -> `Capex_Model!G13` (cell_reference)
- `Assumptions!E14` -> `Capex_Model!E5` (cell_reference)
- `Capex_Model!D11` -> `Checks!C5` (cell_reference)
- `Assumptions!C9` -> `Capex_Model!C9` (cell_reference)
- `Capex_Model!F11` -> `Checks!B5` (cell_reference)
- `Summary!D11` -> `Summary!B19` (cell_reference)
- `Capex_Model!E11` -> `Checks!C6` (cell_reference)
- `Assumptions!D14` -> `Capex_Model!D5` (cell_reference)
- `Summary!D12` -> `Summary!B20` (cell_reference)
- `Assumptions!G14` -> `Capex_Model!E7` (cell_reference)
- `Capex_Model!D5` -> `Summary!B12` (cell_reference)
- `Capex_Model!D7` -> `Capex_Model!D8` (cell_reference)
- `Assumptions!C8` -> `Capex_Model!E10` (cell_reference)
- `Capex_Model!F8` -> `Capex_Model!F11` (cell_reference)
- `Capex_Model!E8` -> `Capex_Model!E11` (cell_reference)
- `Capex_Model!G13` -> `Summary!D6` (cell_reference)
- `Capex_Model!B7` -> `Capex_Model!B8` (cell_reference)
- `Assumptions!G13` -> `Capex_Model!C7` (cell_reference)
- `Capex_Model!C6` -> `Capex_Model!C8` (cell_reference)
- `Capex_Model!C8` -> `Capex_Model!C11` (cell_reference)
- `Capex_Model!E13` -> `Summary!F12` (cell_reference)
- `Capex_Model!B11` -> `Summary!D11` (cell_reference)
- `Capex_Model!F13` -> `Summary!C6` (cell_reference)
- `Assumptions!C8` -> `Capex_Model!C10` (cell_reference)
- `Capex_Model!G11` -> `Summary!B6` (cell_reference)
- `Capex_Model!D10` -> `Capex_Model!D11` (cell_reference)
- `Capex_Model!D5` -> `Capex_Model!E4` (cell_reference)
- `Capex_Model!C4` -> `Capex_Model!G4` (cell_reference)
- `Assumptions!F13` -> `Capex_Model!B6` (cell_reference)
- `Summary!B6` -> `Summary!G19` (cell_reference)
- `Capex_Model!C8` -> `Capex_Model!G8` (cell_reference)
- `Capex_Model!E7` -> `Capex_Model!E8` (cell_reference)
- `Capex_Model!D8` -> `Capex_Model!F8` (cell_reference)
- `Capex_Model!E8` -> `Capex_Model!G8` (cell_reference)
- `Capex_Model!E6` -> `Capex_Model!E8` (cell_reference)
- `Capex_Model!B10` -> `Capex_Model!B11` (cell_reference)
- `Assumptions!B14` -> `Capex_Model!D4` (cell_reference)
- `Capex_Model!D5` -> `Capex_Model!E5` (cell_reference)
- `Capex_Model!C5` -> `Capex_Model!C8` (cell_reference)

## Diagnostics

- **CACHED_VALUE_MODE**: This report uses cached formula results. Numeric output deltas assume both workbooks were saved after recalculation.
