from pathlib import Path
import pandas as pd

EXCEL_FILE = Path(r"C:\ai-platform\NWOnderhoudslijstpromati.xlsx")

def main():
    if not EXCEL_FILE.exists():
        raise FileNotFoundError(f"Bestand niet gevonden: {EXCEL_FILE}")

    xl = pd.ExcelFile(EXCEL_FILE)

    print("=" * 80)
    print(f"BESTAND: {EXCEL_FILE}")
    print(f"AANTAL SHEETS: {len(xl.sheet_names)}")
    print("=" * 80)

    for sheet in xl.sheet_names:
        print()
        print("#" * 80)
        print(f"SHEET: {sheet}")
        print("#" * 80)

        df_raw = pd.read_excel(EXCEL_FILE, sheet_name=sheet, header=None)
        print(f"Vorm zonder headers: {df_raw.shape[0]} rijen x {df_raw.shape[1]} kolommen")
        print()
        print("Eerste 20 rijen zonder header:")
        print(df_raw.head(20).to_string(index=True))

        print()
        print("-" * 80)
        print("Poging met eerste rij als header:")
        df = pd.read_excel(EXCEL_FILE, sheet_name=sheet)
        print(f"Vorm met header: {df.shape[0]} rijen x {df.shape[1]} kolommen")
        print()
        print("Kolommen:")
        for i, col in enumerate(df.columns, start=1):
            print(f"{i:02d}. {repr(col)}")

        print()
        print("Eerste 10 dataregels:")
        print(df.head(10).to_string(index=False))

        print()
        print("Niet-lege telling per kolom:")
        print(df.notna().sum().to_string())

if __name__ == "__main__":
    main()