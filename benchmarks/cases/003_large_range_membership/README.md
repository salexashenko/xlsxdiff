# Large Range Membership

Purpose: A raw-data cell changes inside a large referenced range that is represented as a collapsed range node.

Expected: `RawData!C582` should reach `Summary!B2` through the virtual `RawData!A1:Z10000` membership edge.

Files:

- `baseline.xlsx`
- `candidate.xlsx`
- `workbook_diff.yml`
- `expected.diff.json`
- `expected.llm_summary.md`
