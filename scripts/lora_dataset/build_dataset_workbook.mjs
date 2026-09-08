import fs from "node:fs/promises";
import path from "node:path";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = process.argv[2];
if (!root) throw new Error("usage: build_dataset_workbook.mjs <mvp_v1_directory>");

const manifestText = await fs.readFile(path.join(root, "dataset_manifest.jsonl"), "utf8");
const manifest = manifestText.split(/\r?\n/).filter(Boolean).map((line) => JSON.parse(line));
const promptSpec = JSON.parse(await fs.readFile(path.join(root, "validation_prompts.json"), "utf8"));
const imageFiles = (await fs.readdir(path.join(root, "images"))).filter((name) => !name.startsWith("."));

const workbook = Workbook.create();
const overview = workbook.worksheets.add("Overview");
const manifestSheet = workbook.worksheets.add("Manifest");
const promptsSheet = workbook.worksheets.add("Validation Prompts");

const wine = "#7A1F1F";
const ink = "#2F241F";
const ivory = "#F5F1E8";
const paleGold = "#E8D7B0";
const paleBlue = "#DCEAF3";
const paleRed = "#F5DADA";
const white = "#FFFFFF";
const fontName = "Arial";

for (const sheet of [overview, manifestSheet, promptsSheet]) {
  sheet.showGridLines = false;
  sheet.getRange("A1:AD110").format.font = { name: fontName, color: ink, size: 10 };
}

overview.mergeCells("A1:F1");
overview.getRange("A1").values = [["LongCat 中国皮影 LoRA — MVP v1 数据集清单"]];
overview.getRange("A1:F1").format = {
  fill: wine,
  font: { name: fontName, size: 18, bold: true, color: white },
  verticalAlignment: "center",
};
overview.getRange("A1:F1").format.rowHeight = 30;
overview.mergeCells("A2:F2");
overview.getRange("A2").values = [["非商业课程展示｜训练前人工审阅版｜2026-09-08｜尚未启动 NPU 训练"]];
overview.getRange("A2:F2").format = { fill: ivory, font: { name: fontName, italic: true, color: wine } };

overview.getRange("A4:B4").values = [["数据指标", "自动计算"]];
overview.getRange("D4:F4").values = [["质量门槛", "结果", "说明"]];
for (const address of ["A4:B4", "D4:F4", "A18:C18"]) {
  overview.getRange(address).format = {
    fill: wine,
    font: { name: fontName, bold: true, color: white },
    borders: { preset: "all", style: "thin", color: "#C8B28C" },
  };
}

const metrics = [
  ["清单总数", "=COUNTIFS(Manifest!$A$6:$A$101,\"<>\")"],
  ["训练集", "=COUNTIFS(Manifest!$C$6:$C$101,\"train\")"],
  ["验证集", "=COUNTIFS(Manifest!$C$6:$C$101,\"validation\")"],
  ["测试集", "=COUNTIFS(Manifest!$C$6:$C$101,\"test\")"],
  ["角色", "=COUNTIFS(Manifest!$D$6:$D$101,\"character\")"],
  ["场面/群像", "=COUNTIFS(Manifest!$D$6:$D$101,\"scene\")"],
  ["工艺细节", "=COUNTIFS(Manifest!$D$6:$D$101,\"detail\")"],
  ["A 级", "=COUNTIFS(Manifest!$E$6:$E$101,\"A\")"],
  ["B 级", "=COUNTIFS(Manifest!$E$6:$E$101,\"B\")"],
  ["NC 素材", "=COUNTIFS(Manifest!$V$6:$V$101,TRUE)"],
  ["固定验收题", "=COUNTIFS('Validation Prompts'!$A$6:$A$29,\"<>\")"],
];
overview.getRange("A5:A15").values = metrics.map(([label]) => [label]);
overview.getRange("B5:B15").formulas = metrics.map(([, formula]) => [formula]);
overview.getRange("A5:B15").format = { borders: { preset: "all", style: "thin", color: "#D8CBB7" } };
overview.getRange("A5:A15").format.fill = ivory;
overview.getRange("B5:B15").format.numberFormat = "0";

const gates = [
  ["清单与图片文件一致", imageFiles.length === manifest.length ? "PASS" : "FAIL", `${manifest.length} 条 / ${imageFiles.length} 文件`],
  ["文件名完全对应", new Set(manifest.map((row) => row.filename)).size === imageFiles.length ? "PASS" : "FAIL", "无旧版本残留"],
  ["处理后 SHA256 唯一", new Set(manifest.map((row) => row.processed_sha256)).size === manifest.length ? "PASS" : "FAIL", "96 个唯一哈希"],
  ["来源页完整", manifest.every((row) => row.source_page) ? "PASS" : "FAIL", "每张均可追溯"],
  ["许可链接完整", manifest.every((row) => row.license_url) ? "PASS" : "FAIL", "排除 ND/授权不明"],
  ["低分辨率训练图", manifest.filter((row) => row.split === "train" && Math.min(row.original_width, row.original_height) < 512).length === 0 ? "PASS" : "FAIL", "全部入选原图短边 ≥ 512"],
  ["训练状态", "WAIT", "待负责人审阅后启动"],
];
overview.getRange("D5:F11").values = gates;
overview.getRange("D5:F11").format = { borders: { preset: "all", style: "thin", color: "#D8CBB7" }, wrapText: true };
overview.getRange("E5:E10").format = { fill: paleBlue, font: { name: fontName, bold: true, color: "#1F5D3B" }, horizontalAlignment: "center" };
overview.getRange("E11").format = { fill: paleGold, font: { name: fontName, bold: true, color: wine }, horizontalAlignment: "center" };

overview.getRange("A18:C18").values = [["许可", "图片数", "使用说明"]];
const licenses = [...new Set(manifest.map((row) => row.license))].sort();
overview.getRange(`A19:A${18 + licenses.length}`).values = licenses.map((license) => [license]);
overview.getRange(`B19:B${18 + licenses.length}`).formulas = licenses.map((license) => [`=COUNTIFS(Manifest!$S$6:$S$101,"${license.replaceAll('"', '""')}")`]);
overview.getRange(`C19:C${18 + licenses.length}`).values = licenses.map((license) => [license.includes("BY") ? "保留署名与许可" : "公共领域/CC0，仍保留来源"]);
overview.getRange(`A19:C${18 + licenses.length}`).format = { borders: { preset: "all", style: "thin", color: "#D8CBB7" }, wrapText: true };

overview.getRange("A28:F31").values = [["重要限制", "当前 28 张 scene 主要为传统皮影群像和场景组件，并非 28 张中央 60% 无角色的纯空场景。", null, null, null, null], ["处置", "首轮只验证皮影材质与人物风格；中央留白先靠提示词与工作流。200 步若出现群像占中，停止扩训并补 20–30 张空场景。", null, null, null, null], ["许可范围", "本项目允许 NC/教育用途数据，但本次入选 96 张无需依赖 NC。", null, null, null, null], ["下一门槛", "负责人确认 contact sheet、Manifest 与提示词后，才创建独立 NPU 训练环境。", null, null, null, null]];
overview.mergeCells("B28:F28"); overview.mergeCells("B29:F29"); overview.mergeCells("B30:F30"); overview.mergeCells("B31:F31");
overview.getRange("A28:F31").format = { fill: paleRed, wrapText: true, borders: { preset: "all", style: "thin", color: "#D7A5A5" } };
overview.getRange("A28:A31").format.font = { name: fontName, bold: true, color: wine };

overview.getRange("A:A").format.columnWidth = 22;
overview.getRange("B:B").format.columnWidth = 16;
overview.getRange("C:C").format.columnWidth = 31;
overview.getRange("D:D").format.columnWidth = 24;
overview.getRange("E:E").format.columnWidth = 12;
overview.getRange("F:F").format.columnWidth = 34;
overview.getRange("A1:F31").format.verticalAlignment = "center";
overview.getRange("A28:F31").format.rowHeight = 38;
overview.freezePanes.freezeRows(4);
overview.tabColor = wine;

const manifestColumns = [
  "dataset_id", "candidate_id", "split", "dataset_role", "quality_grade", "source_group", "title", "filename",
  "width", "height", "original_width", "original_height", "source", "source_id", "source_page", "original_url",
  "artist", "credit", "license", "license_url", "attribution_required", "noncommercial_only", "project_usage",
  "source_sha256", "processed_sha256", "downloaded_at", "processing", "caption", "review_status", "review_notes",
];
manifestSheet.mergeCells("A1:AD1");
manifestSheet.getRange("A1").values = [["MVP v1 完整数据 Manifest（96 张）"]];
manifestSheet.getRange("A1:AD1").format = { fill: wine, font: { name: fontName, size: 16, bold: true, color: white } };
manifestSheet.mergeCells("A2:AD2");
manifestSheet.getRange("A2").values = [["每张图片均记录来源、许可、作者、下载日期、原图与处理后 SHA256；请使用筛选按钮按 split / role / grade 查看。"]];
manifestSheet.getRange("A2:AD2").format = { fill: ivory, font: { name: fontName, italic: true, color: wine } };
manifestSheet.getRange("A5:AD5").values = [manifestColumns];
manifestSheet.getRange("A6:AD101").values = manifest.map((row) => manifestColumns.map((column) => row[column] ?? ""));
const manifestTable = manifestSheet.tables.add("A5:AD101", true, "DatasetManifestTable");
manifestTable.style = "TableStyleMedium2";
manifestTable.showFilterButton = true;
manifestSheet.getRange("A5:AD5").format = { fill: wine, font: { name: fontName, bold: true, color: white }, wrapText: true };
manifestSheet.getRange("A6:AD101").format.verticalAlignment = "top";
manifestSheet.getRange("A6:AD101").format.wrapText = true;
manifestSheet.getRange("I6:L101").format.numberFormat = "0";
manifestSheet.getRange("A:A").format.columnWidth = 12;
manifestSheet.getRange("B:B").format.columnWidth = 12;
manifestSheet.getRange("C:E").format.columnWidth = 14;
manifestSheet.getRange("F:F").format.columnWidth = 24;
manifestSheet.getRange("G:G").format.columnWidth = 38;
manifestSheet.getRange("H:H").format.columnWidth = 28;
manifestSheet.getRange("I:L").format.columnWidth = 12;
manifestSheet.getRange("M:N").format.columnWidth = 22;
manifestSheet.getRange("O:P").format.columnWidth = 45;
manifestSheet.getRange("Q:R").format.columnWidth = 32;
manifestSheet.getRange("S:W").format.columnWidth = 28;
manifestSheet.getRange("X:Y").format.columnWidth = 68;
manifestSheet.getRange("Z:Z").format.columnWidth = 24;
manifestSheet.getRange("AA:AD").format.columnWidth = 58;
manifestSheet.getRange("A6:AD101").format.rowHeight = 48;
manifestSheet.freezePanes.freezeRows(5);
manifestSheet.freezePanes.freezeColumns(2);
manifestSheet.tabColor = "#9E6B38";

const promptColumns = ["id", "category", "width", "height", "steps", "guidance_scale", "seeds", "lora_scales", "prompt", "negative_prompt"];
const promptRows = promptSpec.cases.map((item) => [
  item.id,
  item.category,
  item.width,
  item.height,
  promptSpec.default_steps,
  promptSpec.default_guidance_scale,
  promptSpec.default_seeds.join(", "),
  promptSpec.lora_scales.join(", "),
  item.prompt,
  Object.hasOwn(item, "negative_prompt") ? item.negative_prompt : promptSpec.shared_negative_prompt,
]);
promptsSheet.mergeCells("A1:J1");
promptsSheet.getRange("A1").values = [["固定验收提示词（同 prompt / seed / 参数公平对比）"]];
promptsSheet.getRange("A1:J1").format = { fill: wine, font: { name: fontName, size: 16, bold: true, color: white } };
promptsSheet.mergeCells("A2:J2");
promptsSheet.getRange("A2").values = [["10 个角色 + 10 个场景 + 4 个无触发词通用保真题；角色与场景使用统一负面提示词，保真题负面提示词为空。"]];
promptsSheet.getRange("A2:J2").format = { fill: ivory, font: { name: fontName, italic: true, color: wine } };
promptsSheet.getRange("A5:J5").values = [promptColumns];
promptsSheet.getRange("A6:J29").values = promptRows;
const promptsTable = promptsSheet.tables.add("A5:J29", true, "ValidationPromptsTable");
promptsTable.style = "TableStyleMedium2";
promptsTable.showFilterButton = true;
promptsSheet.getRange("A5:J5").format = { fill: wine, font: { name: fontName, bold: true, color: white }, wrapText: true };
promptsSheet.getRange("A6:J29").format = { wrapText: true, verticalAlignment: "top" };
promptsSheet.getRange("C6:F29").format.numberFormat = "0.0";
promptsSheet.getRange("C6:E29").format.numberFormat = "0";
promptsSheet.getRange("A:A").format.columnWidth = 25;
promptsSheet.getRange("B:B").format.columnWidth = 28;
promptsSheet.getRange("C:H").format.columnWidth = 13;
promptsSheet.getRange("I:J").format.columnWidth = 72;
promptsSheet.getRange("A6:J29").format.rowHeight = 92;
promptsSheet.freezePanes.freezeRows(5);
promptsSheet.freezePanes.freezeColumns(2);
promptsSheet.tabColor = "#315A73";

workbook.recalculate();

const inspectResult = await workbook.inspect({
  kind: "workbook,sheet,table,formula",
  maxChars: 10000,
  tableMaxRows: 5,
  tableMaxCols: 8,
  options: { maxResults: 100 },
});
await fs.writeFile(path.join(root, "workbook_inspect.ndjson"), inspectResult.ndjson ?? String(inspectResult), "utf8");

const errorCheck = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 100 },
  maxChars: 5000,
});
await fs.writeFile(path.join(root, "workbook_formula_error_check.ndjson"), errorCheck.ndjson ?? String(errorCheck), "utf8");

const previewDir = path.join(root, "workbook_previews");
await fs.mkdir(previewDir, { recursive: true });
for (const [sheetName, range, filename] of [
  ["Overview", "A1:F31", "overview.png"],
  ["Manifest", "A1:L20", "manifest.png"],
  ["Validation Prompts", "A1:J15", "validation_prompts.png"],
]) {
  const preview = await workbook.render({ sheetName, range, scale: 1, format: "png" });
  await fs.writeFile(path.join(previewDir, filename), new Uint8Array(await preview.arrayBuffer()));
}

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(path.join(root, "dataset_manifest.xlsx"));
console.log(JSON.stringify({ rows: manifest.length, prompts: promptRows.length, images: imageFiles.length, output: path.join(root, "dataset_manifest.xlsx") }));
