"""Recalculate an xlsx workbook and verify there are zero formula errors.

Usage: python scripts/recalc.py NVU_Financial_Model.xlsx

Loads the workbook, evaluates every formula with the `formulas` engine,
scans all calculated values for Excel error tokens (#REF!, #DIV/0!, #VALUE!,
#NAME?, #N/A, #NUM!, #NULL!), prints a per-sheet summary, and exits non-zero
if any error is found. Also runs a set of accounting reconciliation checks
specific to the NVU model when present.
"""
import sys, os, re

ERROR_TOKENS = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "#NULL!", "#ERROR")

def main(path):
    if not os.path.exists(path):
        print(f"ERROR: file not found: {path}"); return 2
    import formulas
    print(f"Loading and recalculating: {path}")
    xl = formulas.ExcelModel().loads(path).finish()
    sol = xl.calculate()

    errors = []
    values = {}  # 'SHEET'!CELL -> value
    for key, cell in sol.items():
        # keys look like "'[NVU_FINANCIAL_MODEL.XLSX]P&L'!B6"
        m = re.search(r"\][^']*'?!?", key)
        try:
            val = cell.value
        except Exception:
            val = None
        # normalise numpy/array scalars
        try:
            import numpy as np
            if hasattr(val, "ravel"):
                flat = val.ravel()
                val = flat[0] if flat.size == 1 else val
        except Exception:
            pass
        values[key] = val
        sval = str(val)
        if any(tok in sval for tok in ERROR_TOKENS):
            errors.append((key, sval))

    print(f"Evaluated {len(values)} cells.")
    if errors:
        print(f"\n*** {len(errors)} FORMULA ERROR(S) FOUND ***")
        for k, v in errors[:50]:
            print(f"  {k} = {v}")
        return 1
    print("PASS: zero formula errors (#REF!, #DIV/0!, #VALUE!, #NAME?, #N/A, #NUM!, #NULL!).")

    # ---- NVU-specific reconciliation checks ----
    def find(sheet_frag, cell):
        for k, v in values.items():
            if sheet_frag.upper() in k.upper() and k.upper().endswith("!" + cell.upper()):
                return v
        return None

    checks = []
    def chk(desc, got, expected, tol=1.0):
        if got is None:
            checks.append((desc, "MISSING", None, None)); return
        ok = abs(float(got) - expected) <= tol
        checks.append((desc, "OK" if ok else "MISMATCH", got, expected))

    # P&L: FY net loss
    chk("P&L FY net loss = -7,601,225", find("P&L", "D19"), -7601225)
    # P&L: H2 net loss = FY - H1
    h1 = find("P&L", "B19"); fy = find("P&L", "D19"); h2 = find("P&L", "C19")
    if None not in (h1, fy, h2):
        chk("P&L H2 = FY - H1 (net loss)", h2, float(fy) - float(h1))
    # Balance sheet: net assets
    chk("BS net assets 30 Jun = 12,959,638", find("BALANCE SHEET", "B30"), 12959638)
    chk("BS net assets 31 Dec = 12,093,430", find("BALANCE SHEET", "C30"), 12093430)
    # Total equity equals net assets (balance check)
    na_dec = find("BALANCE SHEET", "C30"); te_dec = find("BALANCE SHEET", "C37")
    if None not in (na_dec, te_dec):
        chk("BS balances: Net assets = Total equity (31 Dec)", te_dec, float(na_dec))
    # Cash flow: FY end cash ties to BS cash 31 Dec
    cf_end_fy = find("CASH FLOW", "D24"); bs_cash = find("BALANCE SHEET", "C6")
    if None not in (cf_end_fy, bs_cash):
        chk("CF FY end cash = BS cash 31 Dec (1,807,712)", cf_end_fy, float(bs_cash))

    print("\nReconciliation checks:")
    bad = 0
    for desc, status, got, exp in checks:
        extra = "" if got is None else f" (got {got:,.0f}" + (f", exp {exp:,.0f})" if exp is not None else ")")
        print(f"  [{status}] {desc}{extra}")
        if status != "OK":
            bad += 1
    if bad:
        print(f"\n*** {bad} reconciliation check(s) failed ***")
        return 1
    print("\nALL CHECKS PASSED.")
    return 0

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/recalc.py <workbook.xlsx>"); sys.exit(2)
    sys.exit(main(sys.argv[1]))
