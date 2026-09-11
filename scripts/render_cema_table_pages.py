import fitz
from pathlib import Path

PDF = Path(r"C:\ai-platform\data\rag\kennis\CEMA_Belt-Conveyors_O-0000730-with-New-Logo-NG-2.pdf")
OUT_DIR = Path(r"C:\ai-platform\data\rag\table_pages_cema")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Ruim gekozen rond boekpagina's/hoofdstukken:
# Hoofdstuk 4 capacity: Pg 60-85
# CEMA standard area/capacity tables: rond Pg 81+
# Idlers: Pg 93-127
# Tension/power start: Pg 129+
PAGE_RANGES = [
    range(60, 90),
    range(100, 130),
    range(125, 140),
]

doc = fitz.open(PDF)

pages = sorted(set(p for r in PAGE_RANGES for p in r))

for p in pages:
    if p < 1 or p > len(doc):
        continue

    page = doc[p - 1]
    pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False)

    out = OUT_DIR / f"cema_page_{p:03d}.png"
    pix.save(out)
    print(f"gemaakt: {out}")