# Manual Calculation Caveat

Purpose: A normal assumption impact happens in a workbook saved with manual calculation mode enabled.

Expected: The impact path should be detected, but confidence should be downgraded because cached formula values may be stale.

Files:

- `baseline.xlsx`
- `candidate.xlsx`
- `workbook_diff.yml`
- `expected.diff.json`
- `expected.llm_summary.md`
