from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests


DEFAULT_API_URL = "http://localhost:8000"
DEFAULT_FOLDER = r"C:\ai-platform\data\rag\products\master"

DOC_IDS = [
    "product_master_bandbeveiliging_sitec",
    "product_master_barrier_metaaldetector",
]


def replace_doc(api_url: str, folder: Path, doc_id: str) -> dict:
    path = folder / f"{doc_id}.md"

    if not path.exists():
        raise FileNotFoundError(f"Bestand niet gevonden: {path}")

    text = path.read_text(encoding="utf-8")

    payload = {
        "doc_id": doc_id,
        "text": text,
        "chunk_size": 1200,
        "chunk_overlap": 200,
    }

    response = requests.post(
        api_url.rstrip("/") + "/rag/replace",
        json=payload,
        timeout=180,
    )

    try:
        data = response.json()
    except Exception:
        data = {"raw_response": response.text}

    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {data}")

    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default=DEFAULT_API_URL)
    parser.add_argument("--folder", default=DEFAULT_FOLDER)
    parser.add_argument("--doc-id", default=None)

    args = parser.parse_args()

    folder = Path(args.folder)
    doc_ids = [args.doc_id] if args.doc_id else DOC_IDS

    print("RAG replace gestart")
    print(f"API: {args.api_url}")
    print(f"Folder: {folder}")
    print("-" * 80)

    for doc_id in doc_ids:
        print(f"Replace: {doc_id}")
        result = replace_doc(args.api_url, folder, doc_id)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print("-" * 80)

    print("Klaar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())