// Shared helpers for building the NVU vs Accurri comparison Word documents.
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, TableLayoutType,
} = require("docx");

// Status palette
const STATUS = {
  NOT_IN_NVU:   { label: "NOT IN NVU",            fill: "F8CBAD", text: "843C0C" }, // red-ish
  NOT_IN_TPL:   { label: "NOT IN TEMPLATE",       fill: "FFE699", text: "806000" }, // amber
  NIL_LOSS:     { label: "NIL (LOSS CO.)",        fill: "FFE699", text: "806000" }, // amber
  STRUCT_DIFF:  { label: "STRUCTURALLY DIFFERENT",fill: "F4B183", text: "843C0C" }, // red/orange
  BOTH:         { label: "BOTH PRESENT",          fill: "C6E0B4", text: "375623" }, // green
};

const NAVY = "1F3864";
const GREY = "808080";
const BORDER = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const ALLB = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER,
               insideHorizontal: BORDER, insideVertical: BORDER };

function H1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 140 },
    children: [new TextRun({ text, bold: true, color: NAVY, size: 30 })],
  });
}
function H2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2, spacing: { before: 240, after: 100 },
    children: [new TextRun({ text, bold: true, color: NAVY, size: 24 })],
  });
}
function P(text, opts = {}) {
  return new Paragraph({
    spacing: { after: opts.after ?? 100 },
    children: [new TextRun({ text, size: opts.size ?? 19, italics: !!opts.italic,
      bold: !!opts.bold, color: opts.color || "000000" })],
  });
}
function bullet(text, opts = {}) {
  return new Paragraph({
    bullet: { level: opts.level ?? 0 }, spacing: { after: 60 },
    children: [new TextRun({ text, size: 19, bold: !!opts.bold, color: opts.color || "000000" })],
  });
}

function cellPara(text, { bold = false, color = "000000", align = AlignmentType.LEFT, size = 17 } = {}) {
  const runs = String(text).split("\n").map((line, i) =>
    new Paragraph({ alignment: align, spacing: { after: 0 },
      children: [new TextRun({ text: line, bold, color, size })] }));
  return runs;
}

function tc(text, { width, fill, bold, color, align } = {}) {
  return new TableCell({
    width: width ? { size: width, type: WidthType.PERCENTAGE } : undefined,
    shading: fill ? { type: ShadingType.CLEAR, fill, color: "auto" } : undefined,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    children: cellPara(text, { bold, color, align }),
  });
}

// Build a comparison table.
// rows: [ {item, tpl, nvu, status, note} ]  status = key of STATUS
function comparisonTable(rows, opts = {}) {
  const widths = opts.widths || [22, 22, 22, 14, 20];
  const headerCells = ["Line item", "Pinnacle template ($'000)", "NVU ($, full)", "Status", "Notes"]
    .map((t, i) => new TableCell({
      width: { size: widths[i], type: WidthType.PERCENTAGE },
      shading: { type: ShadingType.CLEAR, fill: NAVY, color: "auto" },
      margins: { top: 60, bottom: 60, left: 80, right: 80 },
      children: cellPara(t, { bold: true, color: "FFFFFF", size: 17 }),
    }));
  const trs = [new TableRow({ tableHeader: true, children: headerCells })];

  for (const r of rows) {
    const s = STATUS[r.status] || STATUS.BOTH;
    trs.push(new TableRow({ children: [
      new TableCell({ width: { size: widths[0], type: WidthType.PERCENTAGE },
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: cellPara(r.item, { bold: true }) }),
      new TableCell({ width: { size: widths[1], type: WidthType.PERCENTAGE },
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: cellPara(r.tpl ?? "—", { align: AlignmentType.RIGHT }) }),
      new TableCell({ width: { size: widths[2], type: WidthType.PERCENTAGE },
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: cellPara(r.nvu ?? "—", { align: AlignmentType.RIGHT }) }),
      new TableCell({ width: { size: widths[3], type: WidthType.PERCENTAGE },
        shading: { type: ShadingType.CLEAR, fill: s.fill, color: "auto" },
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: cellPara(s.label, { bold: true, color: s.text, size: 15 }) }),
      new TableCell({ width: { size: widths[4], type: WidthType.PERCENTAGE },
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: cellPara(r.note ?? "", { size: 16 }) }),
    ] }));
  }
  return new Table({ rows: trs, width: { size: 100, type: WidthType.PERCENTAGE },
    layout: TableLayoutType.FIXED, borders: ALLB });
}

// Generic reference table: headers = [..], rows = [[..],[..]], widths = [..]
function refTable(headers, rows, widths) {
  const trs = [new TableRow({ tableHeader: true, children: headers.map((t, i) =>
    new TableCell({ width: { size: widths[i], type: WidthType.PERCENTAGE },
      shading: { type: ShadingType.CLEAR, fill: NAVY, color: "auto" },
      margins: { top: 50, bottom: 50, left: 80, right: 80 },
      children: cellPara(t, { bold: true, color: "FFFFFF", size: 17 }) })) })];
  for (const r of rows) {
    trs.push(new TableRow({ children: r.map((t, i) =>
      new TableCell({ width: { size: widths[i], type: WidthType.PERCENTAGE },
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: cellPara(t, { bold: i === 0, size: 16 }) })) }));
  }
  return new Table({ rows: trs, width: { size: 100, type: WidthType.PERCENTAGE },
    layout: TableLayoutType.FIXED, borders: ALLB });
}

function legend() {
  const order = ["NOT_IN_NVU", "NOT_IN_TPL", "NIL_LOSS", "STRUCT_DIFF", "BOTH"];
  const desc = {
    NOT_IN_NVU: "Template line item absent from NVU filing",
    NOT_IN_TPL: "NVU line item absent from the Accurri template format",
    NIL_LOSS:   "NVU figure is nil because it is a loss-making entity",
    STRUCT_DIFF:"Both report the area but with different classification / format",
    BOTH:       "Both disclose; figures differ by scale or nature",
  };
  const trs = [new TableRow({ tableHeader: true, children: ["Status", "Meaning"].map(t =>
    new TableCell({ shading: { type: ShadingType.CLEAR, fill: NAVY, color: "auto" },
      margins: { top: 50, bottom: 50, left: 80, right: 80 },
      width: { size: t === "Status" ? 30 : 70, type: WidthType.PERCENTAGE },
      children: cellPara(t, { bold: true, color: "FFFFFF" }) })) })];
  for (const k of order) {
    const s = STATUS[k];
    trs.push(new TableRow({ children: [
      new TableCell({ shading: { type: ShadingType.CLEAR, fill: s.fill, color: "auto" },
        width: { size: 30, type: WidthType.PERCENTAGE },
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: cellPara(s.label, { bold: true, color: s.text }) }),
      new TableCell({ width: { size: 70, type: WidthType.PERCENTAGE },
        margins: { top: 40, bottom: 40, left: 80, right: 80 },
        children: cellPara(desc[k]) }),
    ] }));
  }
  return new Table({ rows: trs, width: { size: 100, type: WidthType.PERCENTAGE },
    layout: TableLayoutType.FIXED, borders: ALLB });
}

function titlePage(title, subtitle, meta) {
  const out = [
    new Paragraph({ spacing: { before: 1200, after: 0 }, alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: title, bold: true, size: 44, color: NAVY })] }),
    new Paragraph({ spacing: { before: 160, after: 0 }, alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: subtitle, size: 26, color: GREY })] }),
  ];
  meta.forEach(m => out.push(new Paragraph({ spacing: { before: 120 }, alignment: AlignmentType.CENTER,
    children: [new TextRun({ text: m, size: 20, color: "000000" })] })));
  return out;
}

module.exports = {
  Document, Packer, Paragraph, TextRun, AlignmentType,
  H1, H2, P, bullet, comparisonTable, legend, refTable, titlePage, NAVY,
};
