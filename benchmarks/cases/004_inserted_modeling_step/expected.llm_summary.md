# LLM Workbook Diff Summary

## One Sentence

Summary!C5 2027 EBITDA changed from 48 to 33 (-15.0 / -31.2%), associated with Summary!C5 2027E EBITDA changing from =C3 to =C4-C3 and 4 other top direct change(s); 0 unexplained value changes were detected.

## Counts

- direct_changes: 5
- raw_direct_changes: 5
- propagated_changes: 0
- unexplained_changes: 0
- formula_changes: 2
- outputs_changed: 2
- final_outputs_changed: 2
- impacted_intermediates: 0
- shifted_semantic_matches: 6

## Top Direct Changes

- `Summary!C5` 2027E EBITDA: =C3 -> =C4-C3 -15.0 / -31.2%
- `Summary!B5` 2026E EBITDA: =B3 -> =B4-B3 -10.0 / -25.0%
- `Summary!B3` 2026E GPU Expense:  -> 10
- `Summary!C3` 2027E GPU Expense:  -> 15
- `Summary!A3` Revenue:  -> GPU Expense

## Top Change Groups

- Inserted modeling step: GPU Expense: Inserted modeling step 'GPU Expense' on Summary.
- 3 cell changes on Summary: 3 cell changes detected in Summary!A3:C3.

## Final Outputs

- `Summary!C5` 2027 EBITDA: 48 -> 33 -15.0 / -31.2%; strength=moderate; dependency=moderate; value_delta=moderate
- `Summary!B5` 2026 EBITDA: 40 -> 30 -10.0 / -25.0%; strength=moderate; dependency=moderate; value_delta=moderate

## Caveats

- Uses cached workbook formula values; numeric deltas assume both workbooks were saved after recalculation.
- Output confidence factors: formula_and_value_changed, multiple_upstream_roots.
