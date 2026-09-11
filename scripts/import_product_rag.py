from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Python package 'requests' ontbreekt.")
    print("Installeer met: pip install requests")
    sys.exit(1)


DEFAULT_FOLDER = r"C:\ai-platform\data\rag\products"
DEFAULT_API_URL = "http://localhost:8000"


def build_doc_id(path: Path) -> str:
    """
    Maakt stabiele product doc_id's.

    Voorbeeld:
    BLU-TEC-Datasheet-Proload (4).pdf
    -> product_proload_blu_tec_datasheet_proload_4
    """
    import re

    name = path.stem.lower()
    name = name.replace("blu-tec", "blu_tec")
    name = name.replace("blu tec", "blu_tec")
    name = name.replace("proload", "proload")
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")

    if not name.startswith("product_"):
        name = "product_" + name

    if "proload" in name and not name.startswith("product_proload"):
        name = name.replace("product_", "product_proload_", 1)

    return name


def ingest_file(
    api_url: str,
    file_path: Path,
    chunk_size: int,
    chunk_overlap: int,
    dry_run: bool = False,
) -> dict:
    doc_id = build_doc_id(file_path)

    if dry_run:
        return {
            "status": "dry_run",
            "doc_id": doc_id,
            "file": str(file_path),
        }

    endpoint = api_url.rstrip("/") + "/rag/ingest-file"

    with file_path.open("rb") as f:
        content_type = "application/pdf" if file_path.suffix.lower() == ".pdf" else "text/markdown"

        files = {
            "file": (
                file_path.name,
                f,
                content_type,
            )
        }
        data = {
            "doc_id": doc_id,
            "chunk_size": str(chunk_size),
            "chunk_overlap": str(chunk_overlap),
        }

        response = requests.post(
            endpoint,
            files=files,
            data=data,
            timeout=120,
        )

    try:
        payload = response.json()
    except Exception:
        payload = {
            "raw_response": response.text,
        }

    if response.status_code >= 400:
        raise RuntimeError(
            f"Import faalde voor {file_path.name} "
            f"HTTP {response.status_code}: {payload}"
        )

    return payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Importeer product RAG documenten naar Promati RAG API."
    )
    parser.add_argument(
        "--folder",
        default=DEFAULT_FOLDER,
        help=f"Map met .md bestanden. Default: {DEFAULT_FOLDER}",
    )
    parser.add_argument(
        "--api-url",
        default=DEFAULT_API_URL,
        help=f"Basis URL van de API. Default: {DEFAULT_API_URL}",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1200,
        help="Chunk size voor RAG. Default: 1200",
    )
    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=200,
        help="Chunk overlap voor RAG. Default: 200",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Toon alleen welke bestanden geïmporteerd zouden worden.",
    )

    args = parser.parse_args()

    folder = Path(args.folder)

    if not folder.exists():
        print(f"Map bestaat niet: {folder}")
        return 1

    if not folder.is_dir():
        print(f"Pad is geen map: {folder}")
        return 1

    files = sorted(
        list(folder.glob("*.md"))
        + list(folder.glob("*.txt"))
        + list(folder.glob("*.pdf"))
    )

    if not files:
        print(f"Geen .md, .txt of .pdf bestanden gevonden in: {folder}")
        return 1

    print(f"RAG import gestart")
    print(f"Map: {folder}")
    print(f"API: {args.api_url}")
    print(f"Aantal bestanden: {len(files)}")
    print("-" * 80)

    ok_count = 0
    failed_count = 0

    for file_path in files:
        doc_id = build_doc_id(file_path)

        try:
            result = ingest_file(
                api_url=args.api_url,
                file_path=file_path,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
                dry_run=args.dry_run,
            )

            ok_count += 1

            chunks = (
                result.get("chunks_upserted")
                or result.get("chunks_upserted_qdrant")
                or 0
            )

            print(f"OK  {file_path.name}")
            print(f"    doc_id: {doc_id}")
            print(f"    chunks: {chunks}")
            print(f"    response: {json.dumps(result, ensure_ascii=False)}")

        except Exception as e:
            failed_count += 1
            print(f"FOUT {file_path.name}")
            print(f"     {e}")

        print("-" * 80)

    print("Import klaar")
    print(f"Gelukt: {ok_count}")
    print(f"Fouten: {failed_count}")

    return 0 if failed_count == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())