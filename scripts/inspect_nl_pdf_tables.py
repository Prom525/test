import pdfplumber
from pathlib import Path

PDF_DIR = Path(r"C:\ai-platform\data\rag\kennis")

FILES = [
    "(2) Bepaling van bandbreedte en bandsnelheid.pdf",
    "(3) Bepaling van het motorvermogen van een transportband..pdf",
    "(4) Bepaling van het motorvermogen van een transportband..pdf",
    "(5) De transporband algemeen.pdf",
    "(6) Band ondersteuning tussen de eindtrommels.pdf",
    "(7) Aandrijving aandrijftrommel keertrommel spantrommel.pdf",
]

for file in FILES:
    path = PDF_DIR / file
    print("\n" + "=" * 100)
    print(file)

    with pdfplumber.open(path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables()
            text = page.extract_text() or ""

            has_table_word = "Tabel" in text or "tabel" in text

            if tables or has_table_word:
                print(f"\n--- pagina {i} ---")
                print("tables gevonden:", len(tables))

                if has_table_word:
                    lines = [x for x in text.splitlines() if "Tabel" in x or "tabel" in x]
                    for line in lines[:10]:
                        print("TEXT:", line)

                for ti, table in enumerate(tables, start=1):
                    print(f"\nTABLE {ti}:")
                    for row in table[:12]:
                        print(row)