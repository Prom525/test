import json
import os
import re
from collections import defaultdict
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text


def build_database_url() -> str:
    load_dotenv()

    db_url = os.getenv("DATABASE_URL")
    if db_url:
        return db_url

    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "SterkWachtwoord123")
    dbname = os.getenv("POSTGRES_DB", "promati")
    return f"postgresql://{user}:{password}@localhost:15432/{dbname}"


DATABASE_URL = build_database_url()
print("DATABASE_URL =", DATABASE_URL)

engine = create_engine(DATABASE_URL, future=True)

SIDE_PATTERN = re.compile(r"\b(oost|west|noord|zuid)\b", re.IGNORECASE)
HOSCH_PATTERN = re.compile(r"\bhosch\b", re.IGNORECASE)

TYPE_START_PATTERN = re.compile(
    r"^\s*(UI|TPH|TPL|RI|RV|AF|H|U)\b|^\s*(UI|TPH|TPL|RI|RV|AF|H|U)(?=\d)",
    re.IGNORECASE,
)

WIDTH_INLINE_PATTERN = re.compile(
    r"\b(UI|TPH|TPL|RI|RV|AF|H|U)\s*([0-9]{2,4})\b",
    re.IGNORECASE,
)

WIDTH_RANGE_PATTERN = re.compile(
    r"\b([0-9]{3,4})\s*[-/]\s*([0-9]{3,4})\b"
)

VARIANT_WORDS = [
    "REV",
    "HDI",
    "HD",
    "SP/M3",
    "LB",
    "TRIPPER",
    "UITHOUDER",
]

HEADER_WORDS = [
    "ONDERHOUDS-RAPPORT",
    "LOCATIE",
    "BAND-BREEDTE",
    "MERK + TYPE",
    "MESHOOGTE",
    "OPMERKING",
    "KLANTGEGEVENS",
    "UITGEVOERD DOOR",
    "DATUM",
    "HANDTEKENING",
]


def normalize_whitespace(value) -> str | None:
    if value is None:
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


def normalize_location(value: str | None) -> str | None:
    value = normalize_whitespace(value)
    if not value:
        return None
    return re.sub(r"\s+", "", value).upper()


def normalize_performed_by(value: str | None) -> list[str] | None:
    value = normalize_whitespace(value)
    if not value:
        return None

    parts = re.split(r"\s*[&/\\]+\s*", value)
    parts = [p.strip() for p in parts if p and p.strip()]
    return parts or None


def extract_side(*values: str | None) -> tuple[str | None, str | None]:
    for value in values:
        if not value:
            continue
        m = SIDE_PATTERN.search(value)
        if m:
            raw = m.group(1)
            return raw, raw.upper()
    return None, None


def strip_side_words(value: str | None) -> str | None:
    value = normalize_whitespace(value)
    if not value:
        return None
    value = SIDE_PATTERN.sub("", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def expand_short_width(num: int) -> int:
    if num in {100, 120, 140, 160, 180}:
        return num * 10
    return num


def normalize_band_breedte(raw: str | None, scraper_type_raw: str | None) -> tuple[int | None, str | None]:
    raw = normalize_whitespace(raw)

    if raw:
        digits = re.sub(r"[^0-9]", "", raw)
        if digits:
            num = int(digits)
            return num, str(num)

    st = normalize_whitespace(scraper_type_raw)
    if st:
        m = WIDTH_INLINE_PATTERN.search(st)
        if m:
            num = int(m.group(2))
            num = expand_short_width(num)
            return num, str(num)

    return None, None


def infer_family(value: str | None) -> str | None:
    value = normalize_whitespace(value)
    if not value:
        return None

    upper = value.upper()

    # UI voor U
    for fam in ["UI", "TPH", "TPL", "RI", "RV", "AF", "H", "U"]:
        if re.search(rf"^\s*{re.escape(fam)}\b", upper):
            return fam
        if re.search(rf"^\s*{re.escape(fam)}(?=\d)", upper):
            return fam

    return None


def infer_variant(value: str | None) -> str | None:
    value = normalize_whitespace(value)
    if not value:
        return None

    upper = value.upper()
    found: list[str] = []

    for patt in VARIANT_WORDS:
        if patt == "SP/M3":
            if "SP/M3" in upper:
                found.append("SP/M3")
        else:
            if re.search(rf"\b{re.escape(patt)}\b", upper):
                found.append(patt)

    if not found:
        return None

    return " ".join(dict.fromkeys(found))


def infer_position_suffix(scraper_type_norm: str | None, opmerking_raw: str | None) -> str | None:
    values = [scraper_type_norm or "", opmerking_raw or ""]
    upper = " | ".join(values).upper()

    found = []
    for patt in ["TRIPPER", "UITHOUDER", "LB", "REV"]:
        if re.search(rf"\b{re.escape(patt)}\b", upper):
            found.append(patt)

    if not found:
        return None

    return " ".join(dict.fromkeys(found))


def normalize_scraper_type(raw: str | None, opmerking_raw: str | None = None) -> tuple[str | None, str | None, str | None, str | None]:
    raw = normalize_whitespace(raw)
    if not raw:
        return None, None, None, None

    upper = raw.upper()
    upper = upper.replace(".", " ")
    upper = re.sub(r"\s+", " ", upper).strip()

    # zijdewoorden eruit halen voor type-normalisatie
    upper = strip_side_words(upper) or upper

    # spacing family + digits
    upper = re.sub(r"\bUI(?=\d)", "UI ", upper)
    upper = re.sub(r"\bTPH(?=\d)", "TPH ", upper)
    upper = re.sub(r"\bTPL(?=\d)", "TPL ", upper)
    upper = re.sub(r"\bRI(?=\d)", "RI ", upper)
    upper = re.sub(r"\bRV(?=\d)", "RV ", upper)
    upper = re.sub(r"\bAF(?=\d)", "AF ", upper)
    upper = re.sub(r"\bH(?=\d)", "H ", upper)
    upper = re.sub(r"\bU(?=\d)", "U ", upper)

    upper = re.sub(r"\s+", " ", upper).strip()

    family = infer_family(upper)
    variant = infer_variant(upper)

    material = "ONBEKEND"
    if family == "UI":
        material = "INOX"
    elif family == "U":
        material = "STANDAARD"

    # patroon FAMILY WIDTH
    width_num = None
    m = WIDTH_INLINE_PATTERN.search(upper)
    if m:
        width_num = int(m.group(2))
        width_num = expand_short_width(width_num)

    # bv TPH 1800-1500 HD moet zo blijven
    range_match = WIDTH_RANGE_PATTERN.search(upper)
    width_range = None
    if range_match:
        width_range = f"{range_match.group(1)}-{range_match.group(2)}"

    if family and width_range:
        norm = f"{family} {width_range}"
        if variant:
            extra = " ".join([x for x in variant.split() if x not in norm.split()])
            if extra:
                norm = f"{norm} {extra}"
        return norm.strip(), family, material, variant

    if family and width_num:
        norm = f"{family} {width_num}"
        if variant:
            extra = " ".join([x for x in variant.split() if x not in norm.split()])
            if extra:
                norm = f"{norm} {extra}"
        return norm.strip(), family, material, variant

    return upper, family, material, variant


def parse_mes(raw: str | None) -> tuple[float | None, str | None, str | None]:
    raw = normalize_whitespace(raw)
    if not raw:
        return None, None, None

    if re.fullmatch(r"[0-9]+(?:[.,][0-9]+)?", raw):
        val = float(raw.replace(",", "."))
        return val, None, None

    code = raw.upper()

    if code == "G":
        return None, "G", "GOED"
    if code == "M":
        return None, "M", "MONITOREN"
    if code == "V":
        return None, "V", "VERVANGEN"

    return None, code, "ONBEKEND"


def is_empty_row(
    locatie: str | None,
    band_breedte: str | None,
    scraper_type: str | None,
    mes_raw: str | None,
    opmerking: str | None,
    demontage: bool | None,
    reinigen: bool | None,
    vervangen: bool | None,
    montage: bool | None,
    afstellen: bool | None,
) -> bool:
    return not any([
        normalize_whitespace(locatie),
        normalize_whitespace(band_breedte),
        normalize_whitespace(scraper_type),
        normalize_whitespace(mes_raw),
        normalize_whitespace(opmerking),
        bool(demontage),
        bool(reinigen),
        bool(vervangen),
        bool(montage),
        bool(afstellen),
    ])


def is_header_like(locatie: str | None, scraper_type: str | None, opmerking: str | None) -> bool:
    blob = " | ".join([
        normalize_whitespace(locatie) or "",
        normalize_whitespace(scraper_type) or "",
        normalize_whitespace(opmerking) or "",
    ]).upper()

    if not blob.strip():
        return False

    return any(word in blob for word in HEADER_WORDS)


def likely_real_position(locatie_raw: str | None, scraper_type_raw: str | None, band_breedte_raw: str | None, opmerking_raw: str | None) -> bool:
    if normalize_whitespace(locatie_raw) and (
        normalize_whitespace(scraper_type_raw)
        or normalize_whitespace(band_breedte_raw)
        or normalize_whitespace(opmerking_raw)
    ):
        return True

    if normalize_whitespace(scraper_type_raw):
        return True

    if normalize_whitespace(band_breedte_raw):
        return True

    return False


def main() -> None:
    with engine.begin() as conn:
        print("[INFO] Leegmaken sb_excel_positions_v1 ...")
        conn.execute(text("TRUNCATE TABLE sb_excel_positions_v1 RESTART IDENTITY"))

        rows = conn.execute(text("""
            SELECT
                i.inspection_key,
                i.lijn_code,
                i.inspected_on,
                i.title,
                i.performed_by,
                i.source_file,
                i.sheet,

                it.section_idx,
                it.row_nr,
                it.locatie,
                it.band_breedte,
                it.merk_type,
                it.demontage,
                it.reinigen,
                it.vervangen,
                it.row_json
            FROM sb_inspection_items_v0 it
            JOIN sb_inspections_v0 i
              ON i.inspection_key = it.inspection_key
            ORDER BY i.lijn_code, i.inspection_key, it.section_idx, it.row_nr, it.id
        """)).mappings().all()

        print(f"[INFO] bronregels: {len(rows)}")

        by_inspection: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_inspection[row["inspection_key"]].append(dict(row))

        inserted = 0

        for inspection_key, items in by_inspection.items():
            last_top_locatie: str | None = None

            for r in items:
                row_json = r.get("row_json") or {}
                if isinstance(row_json, str):
                    try:
                        row_json = json.loads(row_json)
                    except Exception:
                        row_json = {}

                locatie_raw = normalize_whitespace(r.get("locatie"))
                band_breedte_raw = normalize_whitespace(r.get("band_breedte"))
                scraper_type_raw = normalize_whitespace(r.get("merk_type"))

                mes_raw = normalize_whitespace((row_json or {}).get("Unnamed: 8"))
                opmerking_raw = normalize_whitespace((row_json or {}).get("Unnamed: 9"))
                if not opmerking_raw:
                    opmerking_raw = normalize_whitespace((row_json or {}).get("Klantgegevens "))

                demontage = bool(r.get("demontage"))
                reinigen = bool(r.get("reinigen"))
                vervangen = bool(r.get("vervangen"))
                montage = str((row_json or {}).get("Unnamed: 6")).strip().upper() in {"X", "V", "TRUE"}
                afstellen = str((row_json or {}).get("Unnamed: 7")).strip().upper() in {"X", "V", "TRUE"}

                lege_regel = is_empty_row(
                    locatie_raw,
                    band_breedte_raw,
                    scraper_type_raw,
                    mes_raw,
                    opmerking_raw,
                    demontage,
                    reinigen,
                    vervangen,
                    montage,
                    afstellen,
                )

                header_achtig = is_header_like(locatie_raw, scraper_type_raw, opmerking_raw)

                if locatie_raw and likely_real_position(locatie_raw, scraper_type_raw, band_breedte_raw, opmerking_raw):
                    last_top_locatie = locatie_raw

                band_locatie_top = last_top_locatie
                is_subregel = bool((not locatie_raw) and band_locatie_top and likely_real_position(locatie_raw, scraper_type_raw, band_breedte_raw, opmerking_raw))
                band_locatie_final = locatie_raw or band_locatie_top
                band_locatie_norm = normalize_location(band_locatie_final)

                zijde_raw, zijde_norm = extract_side(scraper_type_raw, opmerking_raw)

                scraper_type_norm, scraper_family, scraper_material, scraper_variant = normalize_scraper_type(
                    scraper_type_raw,
                    opmerking_raw,
                )

                positie_suffix = infer_position_suffix(scraper_type_norm, opmerking_raw)

                band_breedte_num, band_breedte_norm = normalize_band_breedte(
                    band_breedte_raw,
                    scraper_type_raw,
                )

                mes_num, mes_code, mes_interpretatie = parse_mes(mes_raw)

                hosch_flag = bool(
                    HOSCH_PATTERN.search(scraper_type_raw or "")
                    or HOSCH_PATTERN.search(opmerking_raw or "")
                )
                concurrent_naam = "HOSCH" if hosch_flag else None

                performed_by_norm = normalize_performed_by(r.get("performed_by"))

                data_quality_flag = "OK"
                parse_notes: list[str] = []

                if not band_locatie_final and not lege_regel and not header_achtig:
                    data_quality_flag = "GEEN_LOCATIE"
                    parse_notes.append("Geen locatie of bovenliggende locatie gevonden")

                if is_subregel:
                    parse_notes.append("Locatie aangevuld vanuit bovenliggende locatie")

                if not scraper_type_raw and not lege_regel and not header_achtig:
                    parse_notes.append("Geen scraper type ingevuld")

                if not mes_raw and not lege_regel and not header_achtig:
                    parse_notes.append("Geen meshoogte ingevuld")

                if hosch_flag:
                    parse_notes.append("Concurrent Hosch gedetecteerd")

                parse_confidence = 1.00
                if is_subregel:
                    parse_confidence = 0.85
                if not band_locatie_final and not lege_regel and not header_achtig:
                    parse_confidence = 0.40

                band_key = None
                if r.get("lijn_code") and band_locatie_norm:
                    band_key = f"{r['lijn_code']}|{band_locatie_norm}"

                position_key = "|".join([
                    r.get("lijn_code") or "UNKNOWN",
                    band_locatie_norm or "GEEN_LOCATIE",
                    zijde_norm or "GEEN_ZIJDE",
                    scraper_type_norm or "GEEN_TYPE",
                ])

                conn.execute(text("""
                    INSERT INTO sb_excel_positions_v1 (
                        inspection_key,
                        lijn_code,
                        source_file,
                        sheet,
                        row_nr,
                        section_idx,

                        effective_date,
                        report_title,
                        performed_by_raw,
                        performed_by_norm,

                        locatie_raw,
                        band_breedte_raw,
                        scraper_type_raw,
                        mes_raw,
                        opmerking_raw,

                        band_locatie_top,
                        band_locatie_final,
                        band_locatie_norm,

                        zijde_raw,
                        zijde_norm,
                        positie_suffix,

                        band_breedte_num,
                        band_breedte_norm,

                        scraper_family,
                        scraper_material,
                        scraper_type_norm,
                        scraper_variant,

                        mes_num,
                        mes_code,
                        mes_interpretatie,

                        demontage,
                        reinigen,
                        vervangen,
                        montage,
                        afstellen,

                        hosch_flag,
                        concurrent_naam,

                        is_subregel,
                        is_header_achtig,
                        is_lege_regel,
                        parse_confidence,
                        data_quality_flag,
                        parse_notes,

                        band_key,
                        position_key
                    )
                    VALUES (
                        :inspection_key,
                        :lijn_code,
                        :source_file,
                        :sheet,
                        :row_nr,
                        :section_idx,

                        :effective_date,
                        :report_title,
                        :performed_by_raw,
                        :performed_by_norm,

                        :locatie_raw,
                        :band_breedte_raw,
                        :scraper_type_raw,
                        :mes_raw,
                        :opmerking_raw,

                        :band_locatie_top,
                        :band_locatie_final,
                        :band_locatie_norm,

                        :zijde_raw,
                        :zijde_norm,
                        :positie_suffix,

                        :band_breedte_num,
                        :band_breedte_norm,

                        :scraper_family,
                        :scraper_material,
                        :scraper_type_norm,
                        :scraper_variant,

                        :mes_num,
                        :mes_code,
                        :mes_interpretatie,

                        :demontage,
                        :reinigen,
                        :vervangen,
                        :montage,
                        :afstellen,

                        :hosch_flag,
                        :concurrent_naam,

                        :is_subregel,
                        :is_header_achtig,
                        :is_lege_regel,
                        :parse_confidence,
                        :data_quality_flag,
                        :parse_notes,

                        :band_key,
                        :position_key
                    )
                """), {
                    "inspection_key": r["inspection_key"],
                    "lijn_code": r["lijn_code"],
                    "source_file": r.get("source_file"),
                    "sheet": r.get("sheet"),
                    "row_nr": r.get("row_nr"),
                    "section_idx": r.get("section_idx") or 1,

                    "effective_date": r.get("inspected_on"),
                    "report_title": r.get("title"),
                    "performed_by_raw": r.get("performed_by"),
                    "performed_by_norm": performed_by_norm,

                    "locatie_raw": locatie_raw,
                    "band_breedte_raw": band_breedte_raw,
                    "scraper_type_raw": scraper_type_raw,
                    "mes_raw": mes_raw,
                    "opmerking_raw": opmerking_raw,

                    "band_locatie_top": band_locatie_top,
                    "band_locatie_final": band_locatie_final,
                    "band_locatie_norm": band_locatie_norm,

                    "zijde_raw": zijde_raw,
                    "zijde_norm": zijde_norm,
                    "positie_suffix": positie_suffix,

                    "band_breedte_num": band_breedte_num,
                    "band_breedte_norm": band_breedte_norm,

                    "scraper_family": scraper_family,
                    "scraper_material": scraper_material,
                    "scraper_type_norm": scraper_type_norm,
                    "scraper_variant": scraper_variant,

                    "mes_num": mes_num,
                    "mes_code": mes_code,
                    "mes_interpretatie": mes_interpretatie,

                    "demontage": demontage,
                    "reinigen": reinigen,
                    "vervangen": vervangen,
                    "montage": montage,
                    "afstellen": afstellen,

                    "hosch_flag": hosch_flag,
                    "concurrent_naam": concurrent_naam,

                    "is_subregel": is_subregel,
                    "is_header_achtig": header_achtig,
                    "is_lege_regel": lege_regel,
                    "parse_confidence": parse_confidence,
                    "data_quality_flag": data_quality_flag,
                    "parse_notes": " | ".join(parse_notes) if parse_notes else None,

                    "band_key": band_key,
                    "position_key": position_key,
                })

                inserted += 1

        print(f"[DONE] inserted: {inserted}")


if __name__ == "__main__":
    main()