# LLM Workbook Diff Summary

## One Sentence

Summary!B2 External Input changed from 10 to 12 (+2.00 / +20.0%), associated with Summary!B2 2027E External input changing from ='[budget_old.xlsx]Inputs'!A1 to ='[budget_new.xlsx]Inputs'!A1; 0 unexplained value changes were detected.

## Counts

- direct_changes: 1
- raw_direct_changes: 1
- propagated_changes: 0
- unexplained_changes: 0
- formula_changes: 1
- outputs_changed: 1
- shifted_semantic_matches: 0

## Top Direct Changes

- `Summary!B2` 2027E External input: ='[budget_old.xlsx]Inputs'!A1 -> ='[budget_new.xlsx]Inputs'!A1 +2.00 / +20.0%

## Top Impacted Outputs

- `Summary!B2` External Input: 10 -> 12 +2.00 / +20.0%; strength=weak; dependency=weak; value_delta=moderate

## Caveats

- Uses cached workbook formula values; numeric deltas assume both workbooks were saved after recalculation.
- Warnings present: FORMULA_PARSE_PARTIAL.
- Output confidence factors: external_reference, formula_and_value_changed, partial_formula_parse.
