// build_report.js — turn findings.json into a Word disclosure-review report.
// Usage: node build_report.js <findings.json> <output.docx>
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, HeadingLevel,
  Table, TableRow, TableCell, WidthType, BorderStyle, ShadingType, TableLayoutType,
} = require("docx");

const NAVY = "1F3864";
const BORDER = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const ALLB = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER,
               insideHorizontal: BORDER, insideVertical: BORDER };
const STATUS = {
  "PRESENT":           { fill: "C6E0B4", text: "375623" },
  "NOT FOUND":         { fill: "F8CBAD", text: "843C0C" },
  "N/A":               { fill: "D9D9D9", text: "595959" },
  "BELOW MATERIALITY": { fill: "DDEBF7", text: "1F4E79" },
  "REVIEW":            { fill: "FFE699", text: "806000" },
  "REPRESENTED DIFFERENTLY": { fill: "FCE4D6", text: "843C0C" },
  "ADDRESSED":         { fill: "C6E0B4", text: "375623" },
};
const RAG = {
  "GREEN": { fill: "C6E0B4", text: "375623" },
  "AMBER": { fill: "FFE699", text: "806000" },
  "RED":   { fill: "FFC7CE", text: "9C0006" },
};
function money(v) {
  if (v == null) return "—";
  if (v >= 1e6) return "$" + (v / 1e6).toFixed(2) + "m";
  if (v >= 1e3) return "$" + (v / 1e3).toFixed(0) + "k";
  return "$" + Math.round(v);
}

const argv = process.argv.slice(2);
const findingsPath = argv[0] || path.join(__dirname, "..", "output", "findings.json");
const outPath = argv[1] || path.join(__dirname, "..", "output", "Disclosure_Review.docx");
const F = JSON.parse(fs.readFileSync(findingsPath, "utf-8"));
// Resolution tallies for category-B / flagged items.
const repDiff = F.results.filter(r => r.status === "PRESENT" && r.representationNote && r.divergent).length;
const addressed = F.results.filter(r => r.status === "PRESENT" && r.representationNote && !r.divergent).length;

function cellPara(text, { bold = false, color = "000000", align = AlignmentType.LEFT, size = 17 } = {}) {
  return String(text).split("\n").map(line =>
    new Paragraph({ alignment: align, spacing: { after: 0 },
      children: [new TextRun({ text: line, bold, color, size })] }));
}
function tc(text, w, opts = {}) {
  return new TableCell({ width: { size: w, type: WidthType.PERCENTAGE },
    shading: opts.fill ? { type: ShadingType.CLEAR, fill: opts.fill, color: "auto" } : undefined,
    margins: { top: 40, bottom: 40, left: 80, right: 80 },
    children: cellPara(text, opts) });
}
function hdrRow(labels, widths) {
  return new TableRow({ tableHeader: true, children: labels.map((t, i) =>
    new TableCell({ width: { size: widths[i], type: WidthType.PERCENTAGE },
      shading: { type: ShadingType.CLEAR, fill: NAVY, color: "auto" },
      margins: { top: 60, bottom: 60, left: 80, right: 80 },
      children: cellPara(t, { bold: true, color: "FFFFFF", size: 17 }) })) });
}
function H1(t) { return new Paragraph({ heading: HeadingLevel.HEADING_1, spacing: { before: 320, after: 140 },
  children: [new TextRun({ text: t, bold: true, color: NAVY, size: 30 })] }); }
function H2(t) { return new Paragraph({ heading: HeadingLevel.HEADING_2, spacing: { before: 220, after: 90 },
  children: [new TextRun({ text: t, bold: true, color: NAVY, size: 24 })] }); }
function P(t, o = {}) { return new Paragraph({ spacing: { after: o.after ?? 100 },
  children: [new TextRun({ text: t, size: o.size ?? 19, italics: !!o.italic, bold: !!o.bold, color: o.color || "000000" })] }); }
function bullet(t, o = {}) { return new Paragraph({ bullet: { level: 0 }, spacing: { after: 60 },
  children: [new TextRun({ text: t, size: 19, bold: !!o.bold, color: o.color || "000000" })] }); }

const children = [];

// Title
children.push(new Paragraph({ spacing: { before: 800, after: 0 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: "Disclosure Review", bold: true, size: 48, color: NAVY })] }));
children.push(new Paragraph({ spacing: { before: 120 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: `${F.entity}${F.ticker ? " (ASX: " + F.ticker + ")" : ""}`, size: 30, color: "000000" })] }));
children.push(new Paragraph({ spacing: { before: 80 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: `${F.reportType === "interim" ? "Half-year / interim report" : "Annual report"} — ${F.reportFile}`, size: 22, color: "808080" })] }));
children.push(new Paragraph({ spacing: { before: 60 }, alignment: AlignmentType.CENTER,
  children: [new TextRun({ text: `Screened against AASB / IFRS disclosure checklist v${F.checklistVersion}`, size: 18, color: "808080" })] }));

// Summary
children.push(H1("1.  Executive summary"));
children.push(P(F.basis));
children.push(P(`Checklist screen: ${F.summary.present} disclosures present (${addressed} confirmed addressed in standard form), ${repDiff} represented differently from the standard (consultation points), ${F.summary.not_found} not found (candidate gaps), ${F.summary.below_materiality ?? 0} below materiality, ${F.summary.na} not applicable to this entity's business model.`, { bold: true }));
children.push(P(`Assessment basis: items are assessed qualitatively (is the disclosure present?) and, where the requirement is balance-driven, quantitatively against materiality of ${money(F.materiality)} (${F.materialityBasis}). Quantitative items below materiality are noted, not flagged as gaps; qualitative items (e.g. related parties, KMP, going concern) are assessed regardless of amount.`, {}));
children.push(P(F.detectionNote, { italic: true, color: "808080" }));

// Board and management
const officers = F.officers || [];
if (officers.length > 0) {
  children.push(H2("Board and management"));
  const drows = [hdrRow(["Name", "Role"], [50, 50])];
  for (const o of officers) {
    drows.push(new TableRow({ children: [
      tc(o.name || "", 50, { bold: true, size: 17 }),
      tc(o.roleNorm || o.role || "", 50, { size: 17 }),
    ]}));
  }
  children.push(new Table({ rows: drows, width: { size: 100, type: WidthType.PERCENTAGE }, layout: TableLayoutType.FIXED, borders: ALLB }));
}

// Recommendations (NOT FOUND, sorted by materiality)
const order = { high: 0, medium: 1, low: 2 };
// Recommendations = every keyword MISS (NOT FOUND), PLUS every category-B disclosure-quality
// point regardless of keyword hit (these must be confirmed as ADEQUATELY addressed, since
// boilerplate policy text can trigger a false PRESENT). Deduplicated, ordered by materiality.
const recSet = new Map();
for (const r of F.results) {
  if (r.status === "NOT FOUND" || r.category === "B") recSet.set(r.id, r);
}
const recs = [...recSet.values()].sort((a, b) => (order[a.materiality] ?? 1) - (order[b.materiality] ?? 1));
children.push(H1("2.  Disclosures to confirm, by standard"));
if (recs.length === 0) {
  children.push(P("No items flagged. Confirm by review against the financial report.", { italic: true }));
} else {
  children.push(P("Each row sets out a disclosure required of an entity of this type, with the Australian Accounting Standard (or Corporations Act / ASX Listing Rule) and paragraph it derives from. The reader can trace every item directly to its source.", {}));
  children.push(P("The Screen column is an automated keyword check of the lodged report — it indicates whether the disclosure's terms appear in the document, not whether the disclosure is complete:", { after: 40 }));
  children.push(bullet("Not detected — the disclosure's terms were not found; it is likely absent and should be added or located.", { }));
  children.push(bullet("Detected — the terms appear; confirm the disclosure fully meets the cited paragraph (a keyword match alone does not establish completeness).", { }));
  children.push(P("Every item must be verified against the financial report itself. This is a review aid, not an audit or assurance opinion. Ordered by significance (High → Low).", { italic: true, color: "808080", after: 120 }));
  const rows = [hdrRow(["Standard & reference", "Disclosure required", "Significance", "Screen", "What to confirm"], [17, 21, 11, 13, 38])];
  for (const g of recs) {
    let screen, sc, action;
    if (g.status === "BELOW MATERIALITY") {
      screen = "Below materiality"; sc = STATUS["BELOW MATERIALITY"];
      action = `Underlying balance ${money(g.balance)} is below materiality ${money(g.materialityThreshold)} — disclosure not required on quantitative grounds. Confirm it is not qualitatively material.`;
    } else if (g.status === "NOT FOUND") {
      screen = "Not detected"; sc = STATUS["NOT FOUND"]; action = g.recommendation;
    } else if (g.representationNote && g.divergent) {
      // present, but not in the standard's illustrative form — consultation point
      screen = "Represented differently"; sc = STATUS["REPRESENTED DIFFERENTLY"];
      action = `Located in the report, but not in the form the standard illustrates — flag as a consultation point (the standard's presentation was not strictly followed). ${g.recommendation}\nWhere it is represented: ${g.representationNote}`;
    } else if (g.representationNote) {
      // present in the standard form — resolved/addressed, no action beyond confirming location
      screen = "Addressed"; sc = STATUS["ADDRESSED"];
      action = `Detected in the report in standard form — appears addressed; no action beyond confirming the disclosure. ${g.representationNote}`;
    } else {
      screen = "Detected"; sc = STATUS.REVIEW; action = g.recommendation;
    }
    rows.push(new TableRow({ children: [
      tc(`${g.standard}\n${g.clause || ""}`, 17, { bold: true, size: 14 }),
      tc(`${g.title}${g.assessment === "quantitative" ? "\n[quantitative]" : ""}`, 21, { size: 15 }),
      tc(g.materiality.toUpperCase(), 11, { bold: true, size: 14 }),
      tc(screen, 13, { fill: sc.fill, color: sc.text, bold: true, size: 14 }),
      tc(action, 38, { size: 15 }),
    ] }));
  }
  children.push(new Table({ rows, width: { size: 100, type: WidthType.PERCENTAGE }, layout: TableLayoutType.FIXED, borders: ALLB }));
}

// Full checklist results
children.push(H1("3.  Full checklist results"));
const rows = [hdrRow(["Standard & reference", "Disclosure", "Status"], [26, 50, 24])];
for (const r of F.results) {
  let label = r.status;
  if (r.status === "PRESENT" && r.representationNote) label = r.divergent ? "REPRESENTED DIFFERENTLY" : "ADDRESSED";
  const s = STATUS[label] || STATUS.REVIEW;
  rows.push(new TableRow({ children: [
    tc(`${r.standard}\n${r.clause || ""}`, 26, { bold: true, size: 14 }),
    tc(r.title, 50, { size: 16 }),
    tc(label, 24, { fill: s.fill, color: s.text, bold: true, size: 14 }),
  ] }));
}
children.push(new Table({ rows, width: { size: 100, type: WidthType.PERCENTAGE }, layout: TableLayoutType.FIXED, borders: ALLB }));

// 4. Corporate activity — CLIENT-FACING, neutral (theme + significance, no GP/opportunity wording)
const SIGNIF = {  // subtle, professional shading — not traffic lights
  "High":    { fill: "DDEBF7", text: "1F4E79" },
  "Medium":  { fill: "F2F7FB", text: "1F4E79" },
  "Low":     { fill: undefined, text: "595959" },
  "Routine": { fill: undefined, text: "808080" },
};
const signifOf = (imp) => imp === "None" || !imp ? "Routine" : imp;
children.push(H1("4.  Corporate activity (trailing 12 months)"));
const asx = F.asx || { items: [] };
if (!F.ticker) {
  children.push(P("No ASX ticker detected — announcements not retrieved.", { italic: true }));
} else if (!asx.items || asx.items.length === 0) {
  children.push(P(`No announcements retrieved for ${F.ticker}.`, { italic: true }));
} else {
  if (asx.periodStart) {
    children.push(P(`Period: ${asx.periodStart} to ${asx.periodEnd}. ${asx.count} ASX announcements, of which ${asx.priceSensitive ?? "?"} were market-sensitive.`, { bold: true }));
  }
  children.push(P("Every ASX announcement over the period, classified by theme and significance — the corporate-activity context for this review.", {}));
  const arows = [hdrRow(["Date", "Announcement", "Theme", "Mkt-sens.", "Significance"], [12, 40, 22, 10, 16])];
  for (const a of asx.items) {
    const sig = signifOf(a.importance);
    const sg = SIGNIF[sig] || SIGNIF.Routine;
    arows.push(new TableRow({ children: [
      tc((a.date || "").slice(0, 10), 12, { size: 14 }),
      tc(a.headline || "", 40, { size: 14 }),
      tc(a.theme || "Administrative", 22, { size: 14 }),
      tc(a.priceSensitive === true ? "Yes" : "", 10, { size: 13, color: "595959" }),
      tc(sig, 16, { fill: sg.fill, color: sg.text, bold: sig === "High", size: 14 }),
    ] }));
  }
  children.push(new Table({ rows: arows, width: { size: 100, type: WidthType.PERCENTAGE }, layout: TableLayoutType.FIXED, borders: ALLB }));
  children.push(P("Significance reflects the corporate materiality of the event type (strategic transactions and capital management rank highest; routine administrative lodgements lowest).", { italic: true, color: "808080", after: 40 }));
}

// Scope note — excluded announcement types (rendered whenever any types were toggled off)
const excl = (asx.excludedTypeInfo || []).filter(e => e.excluded > 0);
if (excl.length > 0) {
  const totalExcluded = excl.reduce((s, e) => s + e.excluded, 0);
  children.push(H2("Scope note — excluded announcement types"));
  children.push(P(
    `${totalExcluded} announcement${totalExcluded !== 1 ? "s" : ""} across ${excl.length} type${excl.length !== 1 ? "s" : ""} ` +
    `were excluded from this review and are not reflected in the corporate activity table above. ` +
    `These are listed below for transparency. If any excluded type is relevant to your assessment, run a new review with those types included.`,
    { after: 120 }
  ));
  const erows = [hdrRow(["Announcement type", "Omitted", "Total in period"], [55, 20, 25])];
  for (const e of excl) {
    erows.push(new TableRow({ children: [
      tc(e.type, 55, { size: 15 }),
      tc(String(e.excluded), 20, { bold: true, size: 15 }),
      tc(String(e.total), 25, { size: 15, color: "808080" }),
    ]}));
  }
  children.push(new Table({ rows: erows, width: { size: 100, type: WidthType.PERCENTAGE }, layout: TableLayoutType.FIXED, borders: ALLB }));
  children.push(P(""));
}

children.push(P(""));
children.push(P("This report is an automated first-pass screen against a keyword-based AASB/IFRS checklist. It is not an audit, review, or assurance opinion. Confirm every finding against the source documents.", { italic: true, color: "808080" }));

// ---- INTERNAL APPENDIX (remove before sending to client) ----
if (asx.items && asx.items.length) {
  const opps = asx.items.filter(i => i.rag === "GREEN" || i.rag === "AMBER")
    .sort((a, b) => (a.priority ?? 5) - (b.priority ?? 5) || String(b.date).localeCompare(String(a.date)));
  const oc = asx.oppCounts || { GREEN: 0, AMBER: 0, RED: 0 };
  children.push(new Paragraph({ pageBreakBefore: true, spacing: { after: 80 },
    children: [new TextRun({ text: "APPENDIX — INTERNAL: ENGAGEMENT OPPORTUNITIES", bold: true, size: 30, color: "9C0006" })] }));
  children.push(P("INTERNAL USE ONLY — REMOVE THIS PAGE BEFORE SENDING TO THE CLIENT.", { bold: true, color: "9C0006" }));
  children.push(P(`Growth Partners business-development view of the same announcements. A ✓ marks the service line the announcement signals; its colour is the priority — green = clear, high-value opportunity (${oc.GREEN}); amber = possible, monitor (${oc.AMBER}). Rows are ordered by importance to GP (highest first), so acquisitions sit above periodic reports.`, {}));
  // GP service lines as checkbox columns (ticked where the announcement matches).
  const SERVICES = [
    { full: "Transaction Readiness", short: "Transaction\nReadiness" },
    { full: "Financial Reporting", short: "Financial\nReporting" },
    { full: "Business Process Redesign", short: "Process\nRedesign" },
    { full: "Commercial Opportunities", short: "Commercial\nOpps" },
    { full: "Audit Readiness", short: "Audit\nReadiness" },
  ];
  if (opps.length) {
    // RAG column removed — its colour now lives in the ticked checkbox cells.
    // Ranking preserved by row order (sorted by priority); columns: Date, Announcement, Type, services.
    const w = [10, 30, 26, 6.8, 6.8, 6.8, 6.8, 6.8];
    const orows = [hdrRow(["Date", "Announcement", "Type", ...SERVICES.map(s => s.short)], w)];
    for (const g of opps) {
      const rg = RAG[g.rag] || RAG.RED;
      const svc = g.oppServices || [];
      const cells = [
        tc((g.date || "").slice(0, 10), w[0], { size: 12 }),
        tc(g.headline || "", w[1], { size: 12 }),
        tc(g.type || "", w[2], { size: 11 }),
      ];
      SERVICES.forEach((s, i) => {
        const hit = svc.includes(s.full);
        cells.push(tc(hit ? "✓" : "", w[3 + i],
          { align: AlignmentType.CENTER, bold: true, size: 16,
            fill: hit ? rg.fill : undefined, color: hit ? rg.text : "000000" }));
      });
      orows.push(new TableRow({ children: cells }));
    }
    children.push(new Table({ rows: orows, width: { size: 100, type: WidthType.PERCENTAGE }, layout: TableLayoutType.FIXED, borders: ALLB }));
  }
  children.push(P("✓ marks the Growth Partners service the announcement signals; tick colour = priority (green = high-value, amber = monitor). Service-to-trigger mapping is configurable in config/opportunity_map.json. Reflects BD opportunity, not disclosure compliance.", { italic: true, color: "808080", after: 40 }));

  // Internal-only excluded type note — flag if any GREEN/AMBER types were excluded (missed BD signal)
  if (excl.length > 0) {
    const exclOpps = excl.filter(e => e.rag === "GREEN" || e.rag === "AMBER");
    children.push(H2("Excluded types — internal note"));
    if (exclOpps.length > 0) {
      children.push(P(
        `⚠ ${exclOpps.length} excluded type${exclOpps.length !== 1 ? "s" : ""} carry a GREEN or AMBER opportunity signal. ` +
        `These announcements were not included in the client report and are absent from the engagement-opportunity matrix above.`,
        { bold: true, color: "9C0006", after: 80 }
      ));
    }
    const irows = [hdrRow(["Announcement type", "Omitted", "Total", "Opportunity signal"], [42, 14, 14, 30])];
    for (const e of excl) {
      const rg = e.rag === "GREEN" ? RAG.GREEN : e.rag === "AMBER" ? RAG.AMBER : RAG.RED;
      irows.push(new TableRow({ children: [
        tc(e.type, 42, { size: 14 }),
        tc(String(e.excluded), 14, { bold: true, size: 14 }),
        tc(String(e.total), 14, { size: 14, color: "808080" }),
        tc(e.rag, 30, { fill: rg.fill, color: rg.text, bold: true, size: 14 }),
      ]}));
    }
    children.push(new Table({ rows: irows, width: { size: 100, type: WidthType.PERCENTAGE }, layout: TableLayoutType.FIXED, borders: ALLB }));
  }
}

const doc = new Document({
  creator: "Disclosure Review Kit", title: `Disclosure Review — ${F.entity}`,
  styles: { default: { document: { run: { font: "Calibri" } } } },
  sections: [{ properties: { page: { margin: { top: 720, bottom: 720, left: 720, right: 720 } } }, children }],
});

Packer.toBuffer(doc).then(buf => {
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  try {
    fs.writeFileSync(outPath, buf);
    console.log("Wrote", outPath, buf.length, "bytes");
  } catch (e) {
    if (e.code === "EBUSY" || e.code === "EPERM") {
      const alt = outPath.replace(/\.docx$/, `_${Date.now()}.docx`);
      fs.writeFileSync(alt, buf);
      console.log("TARGET LOCKED — wrote", alt, buf.length, "bytes");
    } else { throw e; }
  }
});
