# AI ARR / Capex Example

This example compares two scenario workbooks modeling 2026 and 2027 OpenAI / Anthropic ARR and the hyperscaler capex those revenue assumptions could support.

## Layout

- `workbooks/`: committed baseline and candidate `.xlsx` files.
- `workbook_diff.yml`: output-cell and semantic-role config used by the diff.
- `run_diff.py`: small example script that imports the main `workbook_diff` library API.
- `reports/diff_main/`: generated report artifacts from the configured diff, ignored by Git.
- `previews/`: rendered workbook sheet previews, ignored by Git.
- `scripts/`: optional provenance scripts used to generate and inspect the workbooks.

## Run

```bash
python examples/ai_arr_capex/run_diff.py
```

The command rewrites `reports/diff_main` and prints the one-sentence LLM summary from `llm_summary.json`.

The scripts under `scripts/` use the Codex spreadsheet artifact runtime and are not required to run the diff example.
