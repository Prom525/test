#!/usr/bin/env python3
"""
promote_to_inspection_items_v3.py

Fixes over v2:
- Infer lijn_code ONLY from source_file (not from sheet) to avoid WEEKxx codes
- Explicitly ignore matches like WEEK10
- Docstring uses forward slashes to avoid Python invalid escape warnings.

Run:
  $env:DB_URL = "postgresql://postgres:SterkWachtwoord123@127.0.0.1:15432/promati"
  python promote_to_inspection_items_v3.py --reset
"""

import os
import re
import json
import argparse
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text

DB_URL = os.environ.get("DB_URL", "postgresql://postgres:SterkWachtwoord123@127.0.0.1:15432/promati")

# Codes like MV1, EO1, BR1, KOFA1, E200 etc.
RE_CODE = re.compile(r"\b([A-Z]{1,6}\d{1,4})\b")
RE_WEEKCODE = re.compile(r"(?i)^WEEK\d+$")

TRUE_TOKENS = {
    "x", "ja", "j", "yes", "y", "true", "1", "ok", "v", "√", "check", "checked",
    "uitgevoerd", "done"
}

def norm(v: Any) -> str:
    return "" if v is None else str(v).strip()

def norm_lower(v: Any) -> str:
    return norm(v).lower()

def parse_bool(v: Any) -> bool:
    s = norm_lower(v)
    if not s:
        return False
    if s in TRUE_TOKENS:
        return True
    if s.startswith("x"):
        return True
    return False

def looks_like_header(row: Dict[str, Any]) -> bool:
    vals = [norm_lower(row.get(f"Unnamed: {i}")) for i in range(0, 16)]
    if not any(vals):
        return False

    has_locatie = any("locatie" in v for v in vals)
    has_band = any("band" in v for v in vals)
    has_merk = any("merk" in v for v in vals) or any("type" in v for v in vals)

    has_dem = any("demontage" in v for v in vals)
    has_rei = any("reinigen" in v for v in vals)
    has_ver = any("vervangen" in v for v in vals)

    if has_locatie and has_band and has_merk:
        return True
    if has_locatie and has_band and (has_dem or has_rei or has_ver):
        return True
    return False

def header_signature(row: Dict[str, Any]) -> str:
    parts = []
    for i in range(0, 12):
        s = norm_lower(row.get(f"Unnamed: {i}"))
        s = re.sub(r"\s+", " ", s)
        parts.append(s)
    sig = "|".join(parts)
    sig = re.sub(r"\b\d+\s*x\s*hypergo\b", "x hypergo", sig)
    return sig

def build_colmap_from_header(row: Dict[str, Any]) -> Dict[str, int]:
    vals = {i: norm_lower(row.get(f"Unnamed: {i}")) for i in range(0, 25)}
    colmap: Dict[str, int] = {}

    def find_idx(keyword: str) -> Optional[int]:
        for i, v in vals.items():
            if keyword in v:
                return i
        return None

    i_loc = find_idx("locatie")
    i_band = find_idx("band")
    i_merk = find_idx("merk")
    i_type = find_idx("type")

    colmap["locatie"] = i_loc if i_loc is not None else 0
    colmap["band"] = i_band if i_band is not None else 1
    if i_merk is not None:
        colmap["merk"] = i_merk
    elif i_type is not None:
        colmap["merk"] = i_type
    else:
        colmap["merk"] = 2

    i_dem = find_idx("demontage")
    i_rei = find_idx("reinigen")
    i_ver = find_idx("vervangen")

    base = colmap["merk"]
    colmap["demontage"] = i_dem if i_dem is not None else base + 1
    colmap["reinigen"] = i_rei if i_rei is not None else base + 2
    colmap["vervangen"] = i_ver if i_ver is not None else base + 3
    return colmap

def row_get(row: Dict[str, Any], idx: int) -> str:
    return norm(row.get(f"Unnamed: {idx}"))

def row_is_blank(row: Dict[str, Any], idxs: List[int]) -> bool:
    return all(not norm(row.get(f"Unnamed: {i}")) for i in idxs)

def infer_lijn_code(lijn_code: str, source_file: str) -> str:
    """
    If lijn_code is UNKNOWN, try to extract a code from source_file only.
    We explicitly ignore WEEKxx.
    """
    if lijn_code and lijn_code != "UNKNOWN":
        return lijn_code

    hay = (source_file or "").upper()

    # Prefer a known set first (extend this list as you like)
    for known in ["MV1", "MV2", "EO1", "BR1", "KOFA1", "KOFA2", "E200", "E300"]:
        if known in hay:
            return known

    m = RE_CODE.search(hay)
    if m:
        cand = m.group(1)
        if RE_WEEKCODE.match(cand):
            return "UNKNOWN"
        return cand

    return "UNKNOWN"

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="truncate sb_inspection_items_v0 before rebuild")
    args = ap.parse_args()

    engine = create_engine(DB_URL)

    create_table_sql = text("""
      create table if not exists sb_inspection_items_v0 (
        id bigserial primary key,
        inspection_key text not null,
        lijn_code text not null,
        source_file text not null,
        sheet text not null,

        section_idx int not null default 1,
        header_row_nr int,
        row_nr int not null,

        locatie text,
        band_breedte text,
        merk_type text,

        demontage boolean default false,
        reinigen boolean default false,
        vervangen boolean default false,

        row_json jsonb,
        created_at timestamptz default now()
      )
    """)
    create_unique_sql = text("""
      create unique index if not exists sb_inspection_items_uq
      on sb_inspection_items_v0 (inspection_key, section_idx, row_nr)
    """)

    q_inspections = text("""
      select inspection_key, lijn_code, source_file, sheet
      from sb_inspections_v0
      order by lijn_code, source_file, sheet
    """)

    q_rows = text("""
      select row_nr, data->'row' as row
      from sb_stg_inspecties_raw
      where lijn_code=:lijn_code and source_file=:source_file and sheet=:sheet
      order by row_nr
    """)

    insert_item = text("""
      insert into sb_inspection_items_v0
        (inspection_key, lijn_code, source_file, sheet, section_idx, header_row_nr, row_nr,
         locatie, band_breedte, merk_type, demontage, reinigen, vervangen, row_json)
      values
        (:inspection_key, :lijn_code, :source_file, :sheet, :section_idx, :header_row_nr, :row_nr,
         :locatie, :band_breedte, :merk_type, :demontage, :reinigen, :vervangen, cast(:row_json as jsonb))
      on conflict (inspection_key, section_idx, row_nr) do update
        set lijn_code = excluded.lijn_code,
            locatie = excluded.locatie,
            band_breedte = excluded.band_breedte,
            merk_type = excluded.merk_type,
            demontage = excluded.demontage,
            reinigen = excluded.reinigen,
            vervangen = excluded.vervangen,
            row_json = excluded.row_json
    """)

    total_items = 0
    total_sections = 0

    with engine.begin() as conn:
        conn.execute(create_table_sql)
        conn.execute(create_unique_sql)

        if args.reset:
            conn.execute(text("truncate table sb_inspection_items_v0"))

        inspections = conn.execute(q_inspections).fetchall()
        print(f"inspections: {len(inspections)}")

        for n, (inspection_key, lijn_code, source_file, sheet) in enumerate(inspections, start=1):
            rows = conn.execute(
                q_rows,
                {"lijn_code": lijn_code, "source_file": source_file, "sheet": sheet},
            ).fetchall()

            parsed_rows: List[Tuple[int, Dict[str, Any]]] = []
            for row_nr, row_obj in rows:
                if row_obj is None:
                    continue
                parsed_rows.append((int(row_nr), dict(row_obj)))

            # headers (ignore consecutive duplicates)
            header_indices: List[int] = []
            last_sig: Optional[str] = None
            for i, (row_nr, row_dict) in enumerate(parsed_rows):
                if looks_like_header(row_dict):
                    sig = header_signature(row_dict)
                    if sig == last_sig:
                        continue
                    header_indices.append(i)
                    last_sig = sig
                else:
                    last_sig = None

            if not header_indices:
                continue

            lijn_code_fixed = infer_lijn_code(lijn_code, source_file)

            for s_idx, h_i in enumerate(header_indices, start=1):
                header_row_nr, header_row = parsed_rows[h_i]
                colmap = build_colmap_from_header(header_row)
                total_sections += 1

                next_header_i = header_indices[s_idx] if s_idx < len(header_indices) else None

                blank_streak = 0
                last_locatie: Optional[str] = None

                for j in range(h_i + 1, len(parsed_rows)):
                    if next_header_i is not None and j >= next_header_i:
                        break

                    row_nr, row_dict = parsed_rows[j]

                    key_idxs = [colmap["locatie"], colmap["band"], colmap["merk"]]
                    if row_is_blank(row_dict, key_idxs):
                        blank_streak += 1
                        if blank_streak >= 3:
                            break
                        continue
                    blank_streak = 0

                    c0 = norm_lower(row_dict.get("Unnamed: 0"))
                    if c0.startswith("datum") or c0.startswith("uitgevoerd door") or "onderhouds-rapport" in c0:
                        continue

                    locatie = row_get(row_dict, colmap["locatie"])
                    band = row_get(row_dict, colmap["band"])
                    merk = row_get(row_dict, colmap["merk"])

                    # carry-forward locatie (merged cells)
                    if not locatie and (band or merk):
                        if last_locatie:
                            locatie = last_locatie
                    if locatie:
                        last_locatie = locatie

                    dem = parse_bool(row_dict.get(f"Unnamed: {colmap['demontage']}"))
                    rei = parse_bool(row_dict.get(f"Unnamed: {colmap['reinigen']}"))
                    ver = parse_bool(row_dict.get(f"Unnamed: {colmap['vervangen']}"))

                    if not (locatie or band or merk or dem or rei or ver):
                        continue

                    conn.execute(
                        insert_item,
                        {
                            "inspection_key": inspection_key,
                            "lijn_code": lijn_code_fixed,
                            "source_file": source_file,
                            "sheet": sheet,
                            "section_idx": s_idx,
                            "header_row_nr": header_row_nr,
                            "row_nr": row_nr,
                            "locatie": locatie or None,
                            "band_breedte": band or None,
                            "merk_type": merk or None,
                            "demontage": bool(dem),
                            "reinigen": bool(rei),
                            "vervangen": bool(ver),
                            "row_json": json.dumps(row_dict, ensure_ascii=False),
                        }
                    )
                    total_items += 1

            if n % 200 == 0:
                print(f"processed {n}/{len(inspections)} inspections, items so far: {total_items}")

    print(f"DONE. sections: {total_sections}, items upserted: {total_items}")

if __name__ == "__main__":
    main()