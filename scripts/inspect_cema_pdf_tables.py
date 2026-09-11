import pdfplumber
from pathlib import Path

PDF = Path(
    r"C:\ai-platform\data\rag\kennis\CEMA_Belt-Conveyors_O-0000730-with-New-Logo-NG-2.pdf"
)

# Zoekgebied voor CEMA capacity tables 4.41 t/m 4.48
PAGES = list(range(89, 102))

TABLE_SETTINGS = {
    "vertical_strategy": "lines",
    "horizontal_strategy": "lines",
    "intersection_tolerance": 5,
    "snap_tolerance": 3,
    "join_tolerance": 3,
    "edge_min_length": 20,
    "min_words_vertical": 1,
    "min_words_horizontal": 1,
}


def clean(value):
    if value is None:
        return ""
    return str(value).replace("\n", " ").strip()


with pdfplumber.open(PDF) as pdf:
    for page_no in PAGES:
        if page_no < 1 or page_no > len(pdf.pages):
            continue

        page = pdf.pages[page_no - 1]

        print("\n" + "=" * 100)
        print(f"PDF pagina {page_no}")

        text = page.extract_text() or ""

        table_lines = []
        for line in text.splitlines():
            if (
                "Table" in line
                or "table" in line
                or "Capacity" in line
                or "CEMA Standard" in line
                or "surcharge" in line
            ):
                table_lines.append(line)

        if table_lines:
            print("\nTEXT-HITS:")
            for line in table_lines[:20]:
                print("TEXT:", line)

        tables = page.extract_tables(TABLE_SETTINGS)
        print("\ntables gevonden:", len(tables))

        for ti, table in enumerate(tables, start=1):
            print(f"\n--- TABLE {ti} op PDF pagina {page_no} ---")
            print(f"rijen: {len(table)}")

            max_cols = max((len(row) for row in table if row), default=0)
            print(f"kolommen max: {max_cols}")

            for row in table[:18]:
                print([clean(cell) for cell in row])

            if len(table) > 18:
                print(f"... ({len(table) - 18} extra rijen)")