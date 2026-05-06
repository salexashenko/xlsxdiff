# xlsxdiff Public Benchmarks

These fixtures are small, real-world-shaped workbook changes used as public regression cases. Each case contains:

- `baseline.xlsx`
- `candidate.xlsx`
- `workbook_diff.yml`
- `expected.diff.json`
- `expected.llm_summary.md`
- `README.md`

Regenerate all benchmark fixtures and the checked-in sample report with:

```bash
python benchmarks/generate_benchmarks.py
```

The fixtures are intentionally committed. They are not generated example output; they are the public regression set for the library.
