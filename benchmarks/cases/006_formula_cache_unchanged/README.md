# Formula Changed but Cache Unchanged

Purpose: An output formula changes, but the workbook cache still shows the old numeric result.

Expected: The formula change should be detected while value-delta confidence is downgraded because the cached output did not move.

Files:

- `baseline.xlsx`
- `candidate.xlsx`
- `workbook_diff.yml`
- `expected.diff.json`
- `expected.llm_summary.md`
