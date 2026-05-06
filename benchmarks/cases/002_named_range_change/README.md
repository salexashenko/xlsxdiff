# Named Range Driver Change

Purpose: A defined name changes target cells while formulas continue to refer to the same name.

Expected: `Growth_2027` should act as a non-cell root and explain `Summary!B2` with moderate confidence.

Files:

- `baseline.xlsx`
- `candidate.xlsx`
- `workbook_diff.yml`
- `expected.diff.json`
- `expected.llm_summary.md`
