from pathlib import Path
import re
import sys

import pandas as pd


FILES = [
    r"C:\ai-platform\Inspectie Hoo7.xlsx",
    r"C:\ai-platform\Hoogoven 6.xls",
    r"C:\ai-platform\Hoogoven 7..xls",
    r"C:\ai-platform\Inspectie Hoo6.xlsx",
    r"C:\ai-platform\Pefa (Welboren).xls",
    r"C:\ai-platform\Pefa (John).xls",
    r"C:\ai-platform\Pefa (Roel).xls",
    r"C:\ai-platform\Pefa (Ruiter).xls",
]


# Gerichte verdachte sheets uit asset_model_health.
# Alleen gebruiken als sheet bestaat in het bestand.
TARGET_SHEETS_BY_FILE = {
    "Inspectie Hoo7.xlsx": [
        "07-02-20",
        "03-04-20",
        "06-03-20",
    ],
    "Inspectie Hoo6.xlsx": [
        "07-07-17",
        "04-08-17",
        "08-09-17",
    ],
    "Hoogoven 6.xls": [
        "15-09-98",
        "30-12-98",
        "13-4-99",
    ],
    "Hoogoven 7..xls": [
        "12-01-99",
        "09-02-99",
        "27-4-99",
    ],
    "Pefa (John).xls": [
        "25-01-10",
        "14-04-10",
        "20-05-10",
    ],
    "Pefa (Welboren).xls": [
        "25-01-10",
        "04-05-10",
        "18-05-10",
    ],
    "Pefa (Roel).xls": [
        "25-01-10",
        "14-04-10",
        "20-05-10",
    ],
    "Pefa (Ruiter).xls": [
        "17-11-10",
        "18-01-11",
        "05-04-12",
    ],
}


# Oude pattern uit load_sb_excel_positions_v5.py
OLD_LOCATION_LIKE_PATTERN = re.compile(
    r"^[A-Z]{1,3}\s*[0-9]{1,4}$|^(WG\s*[0-9]{2,4})$|^(STACKER(\s*[0-9]{2,4})?)$|^(OPVOERBAND)$|^(UITHOUDER)$",
    re.IGNORECASE,
)


# Nieuwe voorgestelde pattern
NEW_LOCATION_LIKE_PATTERN = re.compile(
    r"""
    ^
    (
        [A-Z]{1,4}\s*[0-9]{1,4}\s*[A-Z]?
        |
        WG\s*[0-9]{2,4}
        |
        STACKER(\s*[0-9]{2,4})?
        |
        OPVOERBAND
        |
        UITHOUDER
    )
    $
    """,
    re.IGNORECASE | re.VERBOSE,
)


def normalize_whitespace(value) -> str | None:
    if value is None:
        return None

    if pd.isna(value):
        return None

    if isinstance(value, bool):
        value = str(value)
    elif isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            value = str(int(value))
        else:
            value = str(value)
    elif not isinstance(value, str):
        value = str(value)

    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def looks_like_location_old(value) -> bool:
    value = normalize_whitespace(value)
    if not value:
        return False
    return bool(OLD_LOCATION_LIKE_PATTERN.match(value))


def looks_like_location_new(value) -> bool:
    value = normalize_whitespace(value)
    if not value:
        return False
    return bool(NEW_LOCATION_LIKE_PATTERN.match(value))


def format_value(value) -> str:
    value = normalize_whitespace(value)
    if value is None:
        return ""
    return repr(value)


def dump_sheet(path: str, sheet: str, max_rows: int = 60, max_cols: int = 12) -> None:
    print("\n" + "-" * 140)
    print(f"SHEET: {sheet}")
    print("-" * 140)

    try:
        df = pd.read_excel(
            path,
            sheet_name=sheet,
            header=None,
            nrows=max_rows,
        )
    except Exception as exc:
        print(f"[ERROR] Cannot read sheet {sheet!r}: {type(exc).__name__}: {exc}")
        return

    df = df.iloc[:max_rows, :max_cols]

    print("\n[RAW GRID]")
    for idx, row in df.iterrows():
        values = []

        for col_idx, value in enumerate(row.tolist(), start=1):
            norm = normalize_whitespace(value)
            if norm is None:
                continue

            values.append(f"C{col_idx}={norm!r}")

        if values:
            print(f"R{idx + 1}: " + " | ".join(values))

    print("\n[LOCATION COLUMN TEST - C1]")
    print("row_nr | C1 value | old_match | new_match")
    print("-" * 80)

    for idx, row in df.iterrows():
        c1 = row.iloc[0] if len(row) > 0 else None
        c1_norm = normalize_whitespace(c1)

        if not c1_norm:
            continue

        old_match = looks_like_location_old(c1_norm)
        new_match = looks_like_location_new(c1_norm)

        # Toon alleen relevante waarden: headers, locaties, en verschillen tussen oud/nieuw.
        show = (
            old_match
            or new_match
            or c1_norm.upper() in {"LOCATIE", "DATUM :", "DATUM                :", "UITGEVOERD DOOR :"}
            or old_match != new_match
        )

        if show:
            marker = ""
            if old_match != new_match:
                marker = "  <-- VERSCHIL"

            print(
                f"{idx + 1:>6} | {c1_norm!r:<25} | "
                f"{str(old_match):<9} | {str(new_match):<9}{marker}"
            )

    print("\n[INHERITANCE CANDIDATES]")
    print("Toont rijen waar C1 leeg is maar C2/C3 of inspectiesignalen gevuld zijn.")
    print("Deze regels moeten meestal locatie erven van de vorige locatie/bandregel.")
    print("-" * 120)

    for idx, row in df.iterrows():
        c1 = normalize_whitespace(row.iloc[0] if len(row) > 0 else None)
        c2 = normalize_whitespace(row.iloc[1] if len(row) > 1 else None)
        c3 = normalize_whitespace(row.iloc[2] if len(row) > 2 else None)
        c4 = normalize_whitespace(row.iloc[3] if len(row) > 3 else None)
        c5 = normalize_whitespace(row.iloc[4] if len(row) > 4 else None)
        c6 = normalize_whitespace(row.iloc[5] if len(row) > 5 else None)
        c7 = normalize_whitespace(row.iloc[6] if len(row) > 6 else None)
        c8 = normalize_whitespace(row.iloc[7] if len(row) > 7 else None)
        c9 = normalize_whitespace(row.iloc[8] if len(row) > 8 else None)
        c10 = normalize_whitespace(row.iloc[9] if len(row) > 9 else None)
        c11 = normalize_whitespace(row.iloc[10] if len(row) > 10 else None)
        c12 = normalize_whitespace(row.iloc[11] if len(row) > 11 else None)

        if c1:
            continue

        has_data = any([c2, c3, c4, c5, c6, c7, c8, c9, c10, c11, c12])
        if not has_data:
            continue

        print(
            f"R{idx + 1}: "
            f"C2={format_value(c2)} | "
            f"C3={format_value(c3)} | "
            f"C4={format_value(c4)} | "
            f"C5={format_value(c5)} | "
            f"C6={format_value(c6)} | "
            f"C7={format_value(c7)} | "
            f"C8={format_value(c8)} | "
            f"C9={format_value(c9)} | "
            f"C10={format_value(c10)} | "
            f"C11={format_value(c11)} | "
            f"C12={format_value(c12)}"
        )


def dump_file(path: str) -> None:
    p = Path(path)

    print("\n" + "=" * 140)
    print(f"FILE: {p.name}")
    print("=" * 140)

    if not p.exists():
        print(f"[ERROR] File does not exist: {path}")
        return

    try:
        xls = pd.ExcelFile(path)
    except Exception as exc:
        print(f"[ERROR] Cannot open workbook: {type(exc).__name__}: {exc}")
        return

    print("AVAILABLE SHEETS:")
    print(xls.sheet_names)

    requested_sheets = TARGET_SHEETS_BY_FILE.get(p.name)

    if requested_sheets:
        sheets = [s for s in requested_sheets if s in xls.sheet_names]

        missing = [s for s in requested_sheets if s not in xls.sheet_names]
        if missing:
            print("\n[MISSING TARGET SHEETS]")
            for s in missing:
                print(f"- {s}")

        if not sheets:
            print("\n[WARN] Geen target sheets gevonden; gebruik eerste 3 sheets als fallback.")
            sheets = xls.sheet_names[:3]
    else:
        sheets = xls.sheet_names[:3]

    print("\nSHEETS TO DUMP:")
    print(sheets)

    for sheet in sheets:
        dump_sheet(path, sheet, max_rows=60, max_cols=12)


def run_pattern_unit_tests() -> None:
    values = [
        "TB 70",
        "TB 78 A",
        "TB 78 B",
        "TB64",
        "TB 61",
        "H601",
        "H 601",
        "C 112",
        "M 111",
        "V 125",
        "F 113",
        "K112",
        "K 122",
        "WG 100",
        "STACKER",
        "STACKER 1",
        "OPVOERBAND",
        "UITHOUDER",
        "MERK + TYPE",
        "Datum",
        "John & Nick",
        "2017-07-07 00:00:00",
        "zie urenstaat",
    ]

    print("\n" + "=" * 140)
    print("LOCATION PATTERN UNIT TESTS")
    print("=" * 140)
    print("value | old_match | new_match")
    print("-" * 80)

    for value in values:
        old_match = looks_like_location_old(value)
        new_match = looks_like_location_new(value)
        marker = "  <-- VERSCHIL" if old_match != new_match else ""

        print(
            f"{value!r:<30} | "
            f"{str(old_match):<9} | "
            f"{str(new_match):<9}{marker}"
        )


def main() -> int:
    run_pattern_unit_tests()

    for file in FILES:
        dump_file(file)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())