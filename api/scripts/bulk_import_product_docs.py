import csv
import mimetypes
from pathlib import Path
import requests

API_URL = "http://localhost:8000/rag/ingest-product-document"
ROOT = Path(r"C:\ai-platform\demo_docs")
MANIFEST = Path(r"C:\ai-platform\api\product_import_manifest.csv")

CATEGORY_MAP = {
    "Bandschrapers": "Bandschraper",
    "Polyurethaan kopschrapers": "Bandschraper",
    "Rollen en Steunen": "Rollen en steunen",
    "Trommels en Lagers": "Trommels en lagers",
    "Ontstoffingssysteem": "Ontstoffing",
    "Afdichtingen": "Afdichting",
    "Automatische stuurrollen": "Stuurrollen",
    "Weeg": "Weeg- en detectietechniek",
    "Magnetische roosters": "Metaaldetectie/magneten",
    "Slijtplaten": "Slijtplaten",
    "Overkapping": "Overkapping",
}


def infer_category(folder_name: str) -> str:
    for key, value in CATEGORY_MAP.items():
        if key.lower() in folder_name.lower():
            return value
    return folder_name


def infer_brand_model_variant(filename: str):
    name = filename.replace(".pdf", "").replace(".docx", "")

    brand = "Promati"
    model = name
    variant = "standaard"

    lower = name.lower()

    if "belle banne" in lower or "bandschraper u" in lower:
        brand = "Belle Banne"

    if "reversibel" in lower or "rev" in lower:
        variant = "REV"

    # eenvoudige modelherkenning
    for candidate in ["U", "H", "R", "P", "TPH", "TPL", "AF"]:
        if f" {candidate.lower()} " in f" {lower} " or lower.endswith(candidate.lower()):
            model = candidate
            break

    return brand, model, variant


def already_imported_paths():
    if not MANIFEST.exists():
        return set()

    with MANIFEST.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return {row["path"] for row in reader if row.get("status") == "ok"}


def append_manifest(row: dict):
    exists = MANIFEST.exists()

    with MANIFEST.open("a", newline="", encoding="utf-8") as f:
        fieldnames = [
            "status", "path", "doc_id", "title", "brand", "model",
            "variant", "category", "chunks_db", "chunks_qdrant", "error"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not exists:
            writer.writeheader()

        writer.writerow(row)


def import_file(path: Path):
    folder = path.parent.name
    category = infer_category(folder)
    brand, model, variant = infer_brand_model_variant(path.name)

    title = f"{brand} {model} {variant} - {path.stem}".replace(" standaard", "")
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    with path.open("rb") as f:
        files = {
            "file": (path.name, f, content_type)
        }

        data = {
            "title": title,
            "brand": brand,
            "model": model,
            "category": category,
            "variant": variant,
            "language": "nl",
            "document_type": "product_document",
            "status": "concept",
        }

        response = requests.post(API_URL, files=files, data=data, timeout=120)
        response.raise_for_status()
        return response.json(), data


def main():
    imported = already_imported_paths()

    files = sorted([
        p for p in ROOT.rglob("*")
        if p.suffix.lower() in [".pdf", ".docx"]
    ])

    print(f"Gevonden bestanden: {len(files)}")

    for path in files:
        path_str = str(path)

        if path_str in imported:
            print(f"SKIP al geïmporteerd: {path.name}")
            continue

        print(f"Import: {path}")

        try:
            result, meta = import_file(path)

            append_manifest({
                "status": "ok",
                "path": path_str,
                "doc_id": result.get("doc_id"),
                "title": result.get("title"),
                "brand": meta["brand"],
                "model": meta["model"],
                "variant": meta["variant"],
                "category": meta["category"],
                "chunks_db": result.get("chunks_inserted_db"),
                "chunks_qdrant": result.get("chunks_upserted_qdrant"),
                "error": "",
            })

        except Exception as e:
            append_manifest({
                "status": "error",
                "path": path_str,
                "doc_id": "",
                "title": path.name,
                "brand": "",
                "model": "",
                "variant": "",
                "category": path.parent.name,
                "chunks_db": "",
                "chunks_qdrant": "",
                "error": str(e),
            })
            print(f"FOUT: {path.name}: {e}")


if __name__ == "__main__":
    main()