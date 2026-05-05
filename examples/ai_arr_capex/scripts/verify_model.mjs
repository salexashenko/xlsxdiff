import path from "node:path";
import { fileURLToPath } from "node:url";
import { FileBlob, SpreadsheetFile } from "@oai/artifact-tool";

const exampleDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const files = [
  path.join(exampleDir, "workbooks", "ai_arr_capex_model_v1_march.xlsx"),
  path.join(exampleDir, "workbooks", "ai_arr_capex_model_v2_may.xlsx"),
];

for (const file of files) {
  const workbook = await SpreadsheetFile.importXlsx(await FileBlob.load(file));
  console.log(`\n${file}`);
  for (const range of ["Summary!A5:F15", "Assumptions!A6:H14", "Capex_Model!A3:H15", "Checks!A3:G8"]) {
    const inspect = await workbook.inspect({
      kind: "table",
      range,
      include: "values,formulas",
      tableMaxRows: 18,
      tableMaxCols: 10,
    });
    console.log(inspect.ndjson.split("\n").slice(0, 5).join("\n"));
  }
  const errors = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 300 },
    summary: "formula error scan",
  });
  console.log("errors:", errors.ndjson.trim() || "none");
}
