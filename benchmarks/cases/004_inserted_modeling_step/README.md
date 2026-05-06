# Inserted Modeling Step

Purpose: A forecast model inserts a GPU expense row, shifting downstream formulas and labels.

Expected: Semantic alignment should avoid a delete/add storm and group the inserted GPU Expense modeling step.

Files:

- `baseline.xlsx`
- `candidate.xlsx`
- `workbook_diff.yml`
- `expected.diff.json`
- `expected.llm_summary.md`
