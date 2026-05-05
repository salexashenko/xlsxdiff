import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const exampleDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const workbookDir = path.join(exampleDir, "workbooks");
const previewDir = path.join(exampleDir, "previews");

const sources = [
  ["S1", "OpenAI / Anthropic March revenue pace", "OpenAI on pace for $25B revenue in 2026; Anthropic at $19B", "2026-03-18", "Axios", "https://www.axios.com/2026/03/18/ai-enterprise-revenue-anthropic-openai"],
  ["S2", "Anthropic official compute / revenue update", "Run-rate revenue surpassed $30B; multiple GW of Google/Broadcom TPU capacity starting 2027", "2026-04-06", "Anthropic", "https://www.anthropic.com/news/google-broadcom-partnership-compute"],
  ["S3", "Anthropic growth context", "Anthropic run-rate revenue passed $30B, up from $19B in early March and $9B at end-2025", "2026-04-13", "Axios", "https://www.axios.com/2026/04/13/anthropic-revenue-growth-ai"],
  ["S4", "Hyperscaler capex midrange guidance", "2026 hyperscaler capex expected at $610B midrange of company guidance", "2026-02-11", "Axios", "https://www.axios.com/2026/02/11/hyperscaler-spending-meta-microsoft-amazon-google"],
  ["S5", "Post-Q1 hyperscaler capex plan", "Alphabet, Amazon, Microsoft, and Meta 2026 capex plans reported at $725B", "2026-04-30", "Tom's Hardware / Financial Times", "https://www.tomshardware.com/tech-industry/big-tech/big-techs-ai-spending-plans-reach-725-billion"],
  ["S6", "AI energy and data center financing", "Hyperscalers could spend $1T+ in 2025-26; power constraints expected around 2027-28", "2026-03-01", "Morgan Stanley", "https://www.morganstanley.com/insights/articles/powering-ai-energy-market-outlook-2026"],
  ["S7", "Trillion-dollar capex cycle context", "AI capex wave projected to top $1T next year", "2026-05-05", "Axios", "https://www.axios.com/2026/05/05/jamie-dimon-ai-capex-anthropic"],
];

const versions = {
  baseline: {
    fileName: "ai_arr_capex_model_v1_march.xlsx",
    versionLabel: "v1 March baseline",
    sourceSet: "March 2026 public run-rate anchor",
    global: {
      hyperscalerCapex: { y2026: 610, y2027: 900, source: "S4/S6", note: "2027 is analyst scenario extrapolation from Morgan Stanley/Axios buildout context." },
      supportMultiple: { y2026: 4.0, y2027: 4.0, source: "Analyst assumption", note: "Gross capex support multiple = annual hyperscaler AI service revenue x contract/payback multiple." },
      realization: { y2026: 1.0, y2027: 1.0, source: "Analyst assumption", note: "Baseline formula did not haircut capex for delivery margin / utilization leakage." },
      capexPerGw: { y2026: 45, y2027: 45, source: "Analyst assumption", note: "Illustrative all-in data center + compute capex per GW equivalent." },
    },
    companies: [
      ["OpenAI", 25, "S1", 0.40, 0.85, 0.55, 0.80, "Consumer + API scale, with enterprise focus increasing."],
      ["Anthropic", 19, "S1", 0.58, 0.83, 0.65, 0.85, "Enterprise-heavy Claude demand before official April update."],
    ],
    capexFormulaIncludesRealization: false,
  },
  candidate: {
    fileName: "ai_arr_capex_model_v2_may.xlsx",
    versionLabel: "v2 May update",
    sourceSet: "May 2026 public update and Q1 capex reset",
    global: {
      hyperscalerCapex: { y2026: 725, y2027: 1000, source: "S5/S7", note: "2026 updated after Q1 earnings; 2027 aligns with trillion-dollar capex wave framing." },
      supportMultiple: { y2026: 4.5, y2027: 4.5, source: "Analyst assumption", note: "Longer committed AI capacity contracts increase supportable capex multiple." },
      realization: { y2026: 0.92, y2027: 0.90, source: "Analyst assumption", note: "Formula now haircuts capex support for gross margin, utilization, and delivery leakage." },
      capexPerGw: { y2026: 50, y2027: 52, source: "Analyst assumption", note: "Higher component and power bottleneck costs after Q1 earnings." },
    },
    companies: [
      ["OpenAI", 25, "S1", 0.60, 0.80, 0.58, 0.82, "OpenAI remains anchored to public $25B pace; growth case revised for enterprise/ad monetization."],
      ["Anthropic", 30, "S2/S3", 0.73, 0.63, 0.68, 0.88, "Updated to official $30B+ run-rate and multiple-GW 2027 compute agreement."],
    ],
    capexFormulaIncludesRealization: true,
  },
};

await fs.mkdir(workbookDir, { recursive: true });
await fs.mkdir(previewDir, { recursive: true });
for (const version of Object.values(versions)) {
  await buildWorkbook(version);
}

async function buildWorkbook(version) {
  const workbook = Workbook.create();
  const summary = workbook.worksheets.getOrAdd("Summary", { renameFirstIfOnlyNewSpreadsheet: true });
  const assumptions = workbook.worksheets.add("Assumptions");
  const capex = workbook.worksheets.add("Capex_Model");
  const sourcesSheet = workbook.worksheets.add("Sources");
  const checks = workbook.worksheets.add("Checks");

  for (const sheet of [summary, assumptions, capex, sourcesSheet, checks]) {
    sheet.showGridLines = false;
  }

  buildSources(sourcesSheet);
  buildAssumptions(assumptions, version);
  buildCapex(capex, version);
  buildSummary(summary, version);
  buildChecks(checks);
  applyWorkbookFormatting(summary, assumptions, capex, sourcesSheet, checks);

  const errorScan = await workbook.inspect({
    kind: "match",
    searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
    options: { useRegex: true, maxResults: 300 },
    summary: "formula error scan",
  });
  console.log(`${version.fileName} errors:`, errorScan.ndjson.trim() || "none");

  for (const [sheetName, range] of [
    ["Summary", "A1:J30"],
    ["Assumptions", "A1:H18"],
    ["Capex_Model", "A1:H18"],
    ["Sources", "A1:F12"],
    ["Checks", "A1:G12"],
  ]) {
    const preview = await workbook.render({ sheetName, range, scale: 1.25, format: "png" });
    await fs.writeFile(
      path.join(previewDir, `${version.fileName.replace(".xlsx", "")}_${sheetName}.png`),
      Buffer.from(await preview.arrayBuffer()),
    );
  }

  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(path.join(workbookDir, version.fileName));
}

function buildSources(sheet) {
  sheet.getRange("A1:F1").values = [["Source ID", "Item", "Value / fact used", "As-of", "Source", "URL"]];
  sheet.getRange(`A2:F${sources.length + 1}`).values = sources;
  sheet.getRange("A10:F10").values = [["Caveat", "Run-rate / ARR convention", "Private-company revenue figures are public reports or company statements and are not audited GAAP revenue. Capex support is an illustrative payback proxy, not investment advice.", "2026-05-05", "Model note", ""]];
}

function buildAssumptions(sheet, version) {
  sheet.getRange("A1:H1").values = [["AI ARR and Hyperscaler Capex Support Model", "", "", "", "", "", "", ""]];
  sheet.getRange("A3:B4").values = [
    ["Model version", version.versionLabel],
    ["Source set", version.sourceSet],
  ];
  sheet.getRange("A6:F6").values = [["Global capex assumptions", "2026E", "2027E", "Unit", "Source ID", "Notes"]];
  sheet.getRange("A7:F10").values = [
    ["Hyperscaler capex market", version.global.hyperscalerCapex.y2026, version.global.hyperscalerCapex.y2027, "$B", version.global.hyperscalerCapex.source, version.global.hyperscalerCapex.note],
    ["Capex support multiple", version.global.supportMultiple.y2026, version.global.supportMultiple.y2027, "x", version.global.supportMultiple.source, version.global.supportMultiple.note],
    ["Capex realization factor", version.global.realization.y2026, version.global.realization.y2027, "%", version.global.realization.source, version.global.realization.note],
    ["All-in capex per GW equivalent", version.global.capexPerGw.y2026, version.global.capexPerGw.y2027, "$B/GW", version.global.capexPerGw.source, version.global.capexPerGw.note],
  ];
  sheet.getRange("A12:H12").values = [["Company ARR and compute assumptions", "Anchor ARR", "Anchor source", "2026 exit growth", "2027 ARR growth", "Compute spend / ARR", "Hyperscaler-hosted share", "Model note"]];
  sheet.getRange("A13:H14").values = version.companies;
  sheet.getRange("A16:H18").values = [
    ["Interpretation", "", "", "", "", "", "", ""],
    ["Supportable capex", "ARR x compute spend % x hyperscaler-hosted % x support multiple", "", "", "", "", "", "Candidate formula adds a realization factor haircut."],
    ["Market coverage", "Supportable capex / total hyperscaler capex market", "", "", "", "", "", "This shows share of global hyperscaler buildout plausibly underwritten by these two labs."],
  ];
}

function buildCapex(sheet, version) {
  sheet.getRange("A1:H1").values = [["Capex support model", "", "", "", "", "", "", ""]];
  sheet.getRange("A3:H3").values = [["Metric", "OpenAI 2026E", "OpenAI 2027E", "Anthropic 2026E", "Anthropic 2027E", "Total 2026E", "Total 2027E", "Notes"]];
  sheet.getRange("A4:A15").values = [
    ["Anchor ARR / prior-year ARR ($B)"],
    ["Exit ARR ($B)"],
    ["Compute spend / ARR"],
    ["Hyperscaler-hosted share"],
    ["Annual hyperscaler AI service revenue ($B)"],
    ["Capex realization factor"],
    ["Capex support multiple"],
    ["Supportable hyperscaler capex ($B)"],
    ["Hyperscaler capex market ($B)"],
    ["Supported capex / market"],
    ["Supported GW equivalent"],
    ["Coverage gap to market ($B)"],
  ];
  sheet.getRange("H4:H15").values = [
    ["Anchored to public run-rate estimates and prior calculated ARR."],
    ["2026 exit ARR = anchor x growth; 2027 = 2026 ARR x 2027 growth."],
    ["Input assumption; intended to proxy inference/training cloud spend as a share of ARR."],
    ["Share of compute spend that flows to hyperscalers vs owned/non-hyperscaler capacity."],
    ["Revenue opportunity visible to hyperscalers from AI lab demand."],
    ["Candidate version adds a margin/utilization haircut."],
    ["Contract/payback multiple applied to annual hyperscaler service revenue."],
    ["Primary model output."],
    ["Global hyperscaler capex benchmark."],
    ["Supportable capex as a percent of the total market benchmark."],
    ["Supportable capex divided by all-in capex per GW equivalent."],
    ["Benchmark capex less supportable capex."],
  ];
  sheet.getRange("B4:G15").formulas = [
    ["=Assumptions!B13", "=B5", "=Assumptions!B14", "=D5", "=B4+D4", "=C4+E4"],
    ["=B4*(1+Assumptions!D13)", "=B5*(1+Assumptions!E13)", "=D4*(1+Assumptions!D14)", "=D5*(1+Assumptions!E14)", "=B5+D5", "=C5+E5"],
    ["=Assumptions!F13", "=Assumptions!F13", "=Assumptions!F14", "=Assumptions!F14", "=B8/F5", "=C8/G5"],
    ["=Assumptions!G13", "=Assumptions!G13", "=Assumptions!G14", "=Assumptions!G14", "=B8/(F5*F6)", "=C8/(G5*G6)"],
    ["=B5*B6*B7", "=C5*C6*C7", "=D5*D6*D7", "=E5*E6*E7", "=B8+D8", "=C8+E8"],
    ["=Assumptions!B9", "=Assumptions!C9", "=Assumptions!B9", "=Assumptions!C9", "=Assumptions!B9", "=Assumptions!C9"],
    ["=Assumptions!B8", "=Assumptions!C8", "=Assumptions!B8", "=Assumptions!C8", "=Assumptions!B8", "=Assumptions!C8"],
    supportFormulaRow(version.capexFormulaIncludesRealization),
    ["=Assumptions!B7", "=Assumptions!C7", "=Assumptions!B7", "=Assumptions!C7", "=Assumptions!B7", "=Assumptions!C7"],
    ["=B11/B12", "=C11/C12", "=D11/D12", "=E11/E12", "=F11/F12", "=G11/G12"],
    ["=B11/Assumptions!B10", "=C11/Assumptions!C10", "=D11/Assumptions!B10", "=E11/Assumptions!C10", "=F11/Assumptions!B10", "=G11/Assumptions!C10"],
    ["=B12-B11", "=C12-C11", "=D12-D11", "=E12-E11", "=F12-F11", "=G12-G11"],
  ];
}

function supportFormulaRow(includeRealization) {
  if (includeRealization) {
    return ["=B8*B9*B10", "=C8*C9*C10", "=D8*D9*D10", "=E8*E9*E10", "=F8*F9*F10", "=G8*G9*G10"];
  }
  return ["=B8*B10", "=C8*C10", "=D8*D10", "=E8*E10", "=F8*F10", "=G8*G10"];
}

function buildSummary(sheet, version) {
  sheet.getRange("A1:J1").values = [["AI ARR -> Hyperscaler Capex Support", "", "", "", "", "", "", "", "", ""]];
  sheet.getRange("A3:J3").values = [[`Model version: ${version.versionLabel}. Currency in $B unless noted. Run-rate/ARR figures are source-backed public estimates or scenario assumptions.`, "", "", "", "", "", "", "", "", ""]];
  sheet.getRange("A5:E7").values = [
    ["Combined supportable capex 2026E", "Combined supportable capex 2027E", "2026 market coverage", "2027 market coverage", "Model status"],
    ["", "", "", "", ""],
    ["", "", "", "", ""],
  ];
  sheet.getRange("A6:E6").formulas = [["=Capex_Model!F11", "=Capex_Model!G11", "=Capex_Model!F13", "=Capex_Model!G13", "=Checks!F8"]];
  sheet.getRange("A10:F10").values = [["Company", "2026E ARR", "2027E ARR", "2026 supportable capex", "2027 supportable capex", "2027 support / market"]];
  sheet.getRange("A11:F12").formulas = [
    ['="OpenAI"', "=Capex_Model!B5", "=Capex_Model!C5", "=Capex_Model!B11", "=Capex_Model!C11", "=Capex_Model!C13"],
    ['="Anthropic"', "=Capex_Model!D5", "=Capex_Model!E5", "=Capex_Model!D11", "=Capex_Model!E11", "=Capex_Model!E13"],
  ];
  sheet.getRange("A14:F14").values = [["Readout", "2026E", "2027E", "Market benchmark", "Coverage", "Implication"]];
  sheet.getRange("A15:F15").formulas = [
    [
      '="Combined"',
      "=Capex_Model!F11",
      "=Capex_Model!G11",
      "=Capex_Model!G12",
      "=Capex_Model!G13",
      '="These two labs support "&ROUND(Capex_Model!G13*100,1)&"% of modeled 2027 hyperscaler capex."',
    ],
  ];
  sheet.getRange("A18:C20").values = [["Company", "2026 supportable capex", "2027 supportable capex"], ["OpenAI", null, null], ["Anthropic", null, null]];
  sheet.getRange("B19:C20").formulas = [["=D11", "=E11"], ["=D12", "=E12"]];
  sheet.getRange("E18:G20").values = [["Benchmark", "2026", "2027"], ["Supported by OpenAI + Anthropic", null, null], ["Total hyperscaler capex market", null, null]];
  sheet.getRange("F19:G20").formulas = [["=A6", "=B6"], ["=Capex_Model!F12", "=Capex_Model!G12"]];

  const chartData = computeChartData(version);
  sheet.charts.add("bar", {
    title: "Supportable hyperscaler capex by lab",
    categories: ["OpenAI", "Anthropic"],
    series: [
      { name: "2026E", values: [chartData.openai.support2026, chartData.anthropic.support2026] },
      { name: "2027E", values: [chartData.openai.support2027, chartData.anthropic.support2027] },
    ],
    hasLegend: true,
    legend: { position: "bottom" },
    barOptions: { direction: "column", grouping: "clustered", gapWidth: 120 },
    yAxis: { title: { text: "$B" }, numberFormatCode: "$#,##0" },
    from: { row: 21, col: 0 },
    extent: { widthPx: 520, heightPx: 270 },
  });
  sheet.charts.add("bar", {
    title: "Supported capex vs market benchmark",
    categories: ["2026", "2027"],
    series: [
      { name: "Supported by OpenAI + Anthropic", values: [chartData.total.support2026, chartData.total.support2027] },
      { name: "Total hyperscaler capex market", values: [version.global.hyperscalerCapex.y2026, version.global.hyperscalerCapex.y2027] },
    ],
    hasLegend: true,
    legend: { position: "bottom" },
    barOptions: { direction: "column", grouping: "clustered", gapWidth: 110 },
    yAxis: { title: { text: "$B" }, numberFormatCode: "$#,##0" },
    from: { row: 21, col: 5 },
    extent: { widthPx: 520, heightPx: 270 },
  });
}

function computeChartData(version) {
  const [openai, anthropic] = version.companies.map((company) => {
    const anchor = company[1];
    const growth2026 = company[3];
    const growth2027 = company[4];
    const computeSpend = company[5];
    const hostedShare = company[6];
    const arr2026 = anchor * (1 + growth2026);
    const arr2027 = arr2026 * (1 + growth2027);
    const support2026 = arr2026 * computeSpend * hostedShare * version.global.supportMultiple.y2026 * (version.capexFormulaIncludesRealization ? version.global.realization.y2026 : 1);
    const support2027 = arr2027 * computeSpend * hostedShare * version.global.supportMultiple.y2027 * (version.capexFormulaIncludesRealization ? version.global.realization.y2027 : 1);
    return { arr2026, arr2027, support2026, support2027 };
  });
  return {
    openai,
    anthropic,
    total: {
      support2026: openai.support2026 + anthropic.support2026,
      support2027: openai.support2027 + anthropic.support2027,
    },
  };
}

function buildChecks(sheet) {
  sheet.getRange("A1:G1").values = [["Model checks", "", "", "", "", "", ""]];
  sheet.getRange("A3:G3").values = [["Check", "Actual", "Expected", "Difference", "Tolerance", "Status", "Notes"]];
  sheet.getRange("A4:G8").values = [
    ["Sources table populated", "", "", "", 0, "", "Source IDs and URLs are available for public anchors."],
    ["2026 support total ties to companies", "", "", "", 0.001, "", "Total supportable capex equals OpenAI plus Anthropic."],
    ["2027 support total ties to companies", "", "", "", 0.001, "", "Total supportable capex equals OpenAI plus Anthropic."],
    ["Market benchmark positive", "", "", "", 0, "", "Total hyperscaler capex benchmark must be positive."],
    ["Overall model status", "", "", "", 0, "", "Aggregates the checks above."],
  ];
  sheet.getRange("B4:D8").formulas = [
    ["=COUNTA(Sources!A2:F9)", "=42", "=B4-C4"],
    ["=Capex_Model!F11", "=Capex_Model!B11+Capex_Model!D11", "=B5-C5"],
    ["=Capex_Model!G11", "=Capex_Model!C11+Capex_Model!E11", "=B6-C6"],
    ["=MIN(Capex_Model!F12:G12)", "=0", "=B7-C7"],
    ["=COUNTIF(F4:F7,\"OK\")", "=4", "=B8-C8"],
  ];
  sheet.getRange("F4:F8").formulas = [
    ['=IF(B4>=C4,"OK","Check")'],
    ['=IF(ABS(D5)<=E5,"OK","Check")'],
    ['=IF(ABS(D6)<=E6,"OK","Check")'],
    ['=IF(D7>E7,"OK","Check")'],
    ['=IF(B8=C8,"OK","Check")'],
  ];
}

function applyWorkbookFormatting(summary, assumptions, capex, sourcesSheet, checks) {
  const titleFill = "#17324D";
  const headerFill = "#DCEAF7";
  const sectionFill = "#EAF3E8";
  const cardFill = "#F5F7FA";
  const border = "#B8C2CC";
  for (const sheet of [summary, assumptions, capex, checks]) {
    sheet.getRange("A1:J1").format = {
      fill: titleFill,
      font: { color: "#FFFFFF", bold: true, size: 16 },
      horizontalAlignment: "left",
      verticalAlignment: "center",
    };
    sheet.getRange("A1:J1").format.rowHeightPx = 34;
    sheet.getRange("A:K").format.font = { name: "Aptos", size: 10 };
  }

  summary.getRange("A3:J3").format = { fill: "#EEF2F6", font: { color: "#334155" }, wrapText: true };
  summary.getRange("A5:E5").format = { fill: sectionFill, font: { bold: true, color: "#17324D" }, horizontalAlignment: "center", wrapText: true, borders: { preset: "outside", style: "thin", color: border } };
  summary.getRange("A6:E6").format = { fill: cardFill, font: { bold: true, size: 14 }, horizontalAlignment: "center", borders: { preset: "outside", style: "thin", color: border } };
  summary.getRange("A10:F10").format = { fill: headerFill, font: { bold: true, color: "#17324D" }, horizontalAlignment: "center", wrapText: true };
  summary.getRange("A14:F14").format = { fill: headerFill, font: { bold: true, color: "#17324D" }, horizontalAlignment: "center", wrapText: true };
  summary.getRange("A18:C18").format = { fill: "#FDECC8", font: { bold: true }, horizontalAlignment: "center" };
  summary.getRange("E18:G18").format = { fill: "#FDECC8", font: { bold: true }, horizontalAlignment: "center" };
  summary.getRange("A10:F15").format.borders = { preset: "outside", style: "thin", color: border };

  assumptions.getRange("A6:F6").format = { fill: headerFill, font: { bold: true, color: "#17324D" }, horizontalAlignment: "center", wrapText: true };
  assumptions.getRange("A12:H12").format = { fill: headerFill, font: { bold: true, color: "#17324D" }, horizontalAlignment: "center", wrapText: true };
  assumptions.getRange("A16:H16").format = { fill: sectionFill, font: { bold: true, color: "#17324D" } };
  assumptions.getRange("B7:C10").format.font = { color: "#0000FF" };
  assumptions.getRange("B13:G14").format.font = { color: "#0000FF" };
  assumptions.getRange("A6:F10").format.borders = { preset: "outside", style: "thin", color: border };
  assumptions.getRange("A12:H14").format.borders = { preset: "outside", style: "thin", color: border };

  capex.getRange("A3:H3").format = { fill: headerFill, font: { bold: true, color: "#17324D" }, horizontalAlignment: "center", wrapText: true };
  capex.getRange("A4:A15").format.font = { bold: true };
  capex.getRange("B4:G15").format.font = { color: "#000000" };
  capex.getRange("B4:G15").format.horizontalAlignment = "right";
  capex.getRange("A3:H15").format.borders = { preset: "outside", style: "thin", color: border };

  sourcesSheet.getRange("A1:F1").format = { fill: headerFill, font: { bold: true, color: "#17324D" }, horizontalAlignment: "center", wrapText: true };
  sourcesSheet.getRange("A10:F10").format = { fill: "#FFF7ED", font: { color: "#7C2D12" }, wrapText: true };
  sourcesSheet.getRange("A1:F10").format.borders = { preset: "outside", style: "thin", color: border };

  checks.getRange("A3:G3").format = { fill: headerFill, font: { bold: true, color: "#17324D" }, horizontalAlignment: "center", wrapText: true };
  checks.getRange("A3:G8").format.borders = { preset: "outside", style: "thin", color: border };
  checks.getRange("F4:F8").conditionalFormats.add("containsText", { text: "OK", format: { fill: "#DCFCE7", font: { color: "#166534", bold: true } } });
  checks.getRange("F4:F8").conditionalFormats.add("containsText", { text: "Check", format: { fill: "#FECACA", font: { color: "#991B1B", bold: true } } });

  for (const sheet of [summary, assumptions, capex, sourcesSheet, checks]) {
    sheet.getRange("A:J").format.verticalAlignment = "center";
    sheet.getRange("A:J").format.wrapText = true;
    sheet.getRange("A:J").format.autofitRows();
  }

  setWidths(summary, [210, 170, 170, 165, 150, 220, 120, 120, 120, 120]);
  setWidths(assumptions, [235, 100, 100, 130, 130, 130, 140, 360]);
  setWidths(capex, [255, 125, 125, 135, 135, 120, 120, 360]);
  setWidths(sourcesSheet, [80, 265, 520, 100, 170, 650]);
  setWidths(checks, [235, 110, 110, 110, 95, 95, 360]);

  summary.getRange("A6:D6").format.numberFormat = "$#,##0.0";
  summary.getRange("C6:D6").format.numberFormat = "0.0%";
  summary.getRange("B11:E15").format.numberFormat = "$#,##0.0";
  summary.getRange("F11:F12").format.numberFormat = "0.0%";
  summary.getRange("E15:E15").format.numberFormat = "0.0%";
  summary.getRange("F15:F15").format.numberFormat = "@";
  summary.getRange("B19:C20").format.numberFormat = "$#,##0.0";
  summary.getRange("F19:G20").format.numberFormat = "$#,##0.0";

  assumptions.getRange("B7:C7").format.numberFormat = "$#,##0";
  assumptions.getRange("B8:C8").format.numberFormat = "0.0x";
  assumptions.getRange("B9:C9").format.numberFormat = "0.0%";
  assumptions.getRange("B10:C10").format.numberFormat = "$#,##0";
  assumptions.getRange("B13:B14").format.numberFormat = "$#,##0.0";
  assumptions.getRange("D13:G14").format.numberFormat = "0.0%";

  capex.getRange("B4:G5").format.numberFormat = "$#,##0.0";
  capex.getRange("B6:G7").format.numberFormat = "0.0%";
  capex.getRange("B8:G8").format.numberFormat = "$#,##0.0";
  capex.getRange("B9:G9").format.numberFormat = "0.0%";
  capex.getRange("B10:G10").format.numberFormat = "0.0x";
  capex.getRange("B11:G12").format.numberFormat = "$#,##0.0";
  capex.getRange("B13:G13").format.numberFormat = "0.0%";
  capex.getRange("B14:G14").format.numberFormat = "0.0";
  capex.getRange("B15:G15").format.numberFormat = "$#,##0.0";

  checks.getRange("B4:E8").format.numberFormat = "0.000";
  checks.getRange("F4:F8").format.horizontalAlignment = "center";

  assumptions.freezePanes.freezeRows(6);
  capex.freezePanes.freezeRows(3);
  sourcesSheet.freezePanes.freezeRows(1);
  checks.freezePanes.freezeRows(3);
}

function setWidths(sheet, widths) {
  for (let i = 0; i < widths.length; i++) {
    const col = String.fromCharCode("A".charCodeAt(0) + i);
    sheet.getRange(`${col}:${col}`).format.columnWidthPx = widths[i];
  }
}
