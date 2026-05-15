#!/usr/bin/env python3
"""Debug BMP280 parsing: show all text patterns relevant to access, voltage, SPI."""
import pdfplumber, re, logging
logging.getLogger("pdfminer").setLevel(logging.WARNING)

with pdfplumber.open(".uploads/bmp280.pdf") as pdf:
    texts = []
    for p in pdf.pages:
        texts.append(p.extract_text() or "")
    full = "\n".join(texts)

    print("=== ACCESS TYPE PATTERNS ===")
    # Look for category access patterns
    for m in re.finditer(
        r'(Control|Data|Status|Calibration|Reset|Revision|Reserved)\s*'
        r'(?:registers?)?[^.\n]{0,40}?'
        r'(read[\s/]*only|write[\s/]*only|read\s*/?\s*write)',
        full, re.I):
        print(f"  CAT: [{m.group(1)}] -> [{m.group(2)}]  context: ...{m.group(0)[:80]}...")

    # Look for per-register access
    for m in re.finditer(
        r'Register\s+(?:0[xX])([0-9A-Fa-f]{2})\s*"?(\w+)"?\s*.{0,200}?(read[\s/]*only|write[\s/]*only|read\s*/?\s*write)',
        full, re.I | re.DOTALL):
        print(f"  REG 0x{m.group(1)}: [{m.group(2)}] -> [{m.group(3)}]")

    print("\n=== VOLTAGE PATTERNS ===")
    for m in re.finditer(r'(\d+\.?\d*)\s*V\s*(?:to|-|–)\s*(\d+\.?\d*)\s*V', full):
        v1, v2 = float(m.group(1)), float(m.group(2))
        if 0.5 <= v1 <= 6.0 and 0.5 <= v2 <= 6.0:
            context = full[max(0,m.start()-40):m.start()].split('\n')[-1]
            print(f"  {v1}V - {v2}V  context: ...{context.strip()}...{m.group(0)}")

    for m in re.finditer(r'(?:VDD|VDDIO|supply).*?(\d+\.?\d*)\s*V', full[:5000], re.I):
        print(f"  SUPPLY: {m.group(0)[:100]}")

    print("\n=== SPI PATTERNS ===")
    for m in re.finditer(r'(?:SPI|CPOL|CPHA|mode).{0,60}', full[:8000], re.I):
        print(f"  {m.group(0)[:100]}")
    for m in re.finditer(r'(?:CPOL|CPHA)\s*=\s*\S+', full, re.I):
        print(f"  MODE: {m.group(0)}")

    print("\n=== REGISTER ACCESS TABLE (page 24-25) ===")
    # Look for the access category table on page 24
    for i in [23, 24]:
        try:
            tbls = pdf.pages[i].extract_tables()
            for ti, tbl in enumerate(tbls):
                if tbl:
                    for row in tbl:
                        rs = " | ".join(str(c)[:30] if c else "" for c in row)
                        if re.search(r'read|write|only|control|data|status|reset', rs, re.I):
                            print(f"  P{i+1} T{ti}: {rs[:150]}")
        except Exception as e:
            print(f"  Error page {i+1}: {e}")

    print("\n=== CALIBRATION REGISTER PATTERNS ===")
    for m in re.finditer(r'(?:calib|calibration|0x88|0xA1|dig_[TP]\d)', full, re.I):
        ctx = full[m.start():m.start()+80].split('\n')[0]
        print(f"  {ctx[:100]}")
        if len([1 for _ in re.finditer(r'calib', full[:m.start()+1], re.I)]) > 20:
            print("  ... (many more calib references)")
            break
