#!/usr/bin/env python3
"""Debug script: dump raw PDF text and tables for LM73 and BMP280."""

import pdfplumber
import re
import logging

logging.getLogger("pdfminer").setLevel(logging.WARNING)

def dump_pdf_debug(pdf_path: str, label: str):
    print(f"\n{'='*72}")
    print(f"  DEBUG: {label}")
    print(f"{'='*72}")

    with pdfplumber.open(pdf_path) as pdf:
        # Dump first 5 pages text to look for I2C address patterns
        for i in range(min(len(pdf.pages), 35)):
            txt = pdf.pages[i].extract_text() or ""
            # Look for I2C address patterns
            if re.search(r'I2C|i2c|slave|address|register|0x[0-9A-Fa-f]{2}|pointer|LM73|ADDR', txt, re.I):
                # Only print pages with relevant content
                has_addr = bool(re.search(r'(?:slave|device|I2C).*(?:address|addr)', txt, re.I))
                has_reg = bool(re.search(r'register|pointer|0x[0-9A-Fa-f]{2}', txt, re.I))
                if has_addr or has_reg:
                    print(f"\n--- Page {i+1} (addr={has_addr}, reg={has_reg}) ---")
                    # Print relevant lines
                    for line in txt.split('\n'):
                        if re.search(r'address|addr|register|pointer|0x|slave|I2C|SDO|config|ctrl|status|temp|press|calib|id|reset', line, re.I):
                            print(f"  {line[:120]}")

            # Also check for tables
            try:
                tables = pdf.pages[i].extract_tables()
                for ti, tbl in enumerate(tables):
                    if tbl and len(tbl) >= 2:
                        header = [str(c).strip() if c else "" for c in tbl[0]]
                        header_str = " | ".join(header)
                        if re.search(r'addr|register|name|pointer|bit|field|offset', header_str, re.I):
                            print(f"\n  TABLE on page {i+1}, table #{ti}: [{len(tbl)} rows]")
                            print(f"    Header: {header_str[:120]}")
                            for row in tbl[1:min(8, len(tbl))]:
                                row_str = " | ".join(str(c).strip() if c else "" for c in row)
                                print(f"    Row: {row_str[:120]}")
                            if len(tbl) > 8:
                                print(f"    ... {len(tbl)-8} more rows")
            except Exception:
                pass


dump_pdf_debug(".uploads/lm73.pdf", "TI LM73")
dump_pdf_debug(".uploads/bmp280.pdf", "Bosch BMP280")
