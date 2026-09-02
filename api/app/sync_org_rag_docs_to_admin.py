from __future__ import annotations

import os
from pathlib import Path

import requests


API_URL = "http://localhost:8000"
RAG_FOLDER = Path(r"C:\ai-platform\Rag\org")


def title_from_doc_id(doc_id: str) -> str:
    title = doc_id
    if title.startswith("rag_org_"):
        title = title[len("rag_org_"):]
    return title.replace("_", " ").strip().title()


def category_from_doc_id(doc_id: str) -> str:
    if "info_mailbox" in doc_id:
        return "Administratie"
    if "claims" in doc_id:
        return "Administratie"
    if "krediet" in doc_id:
        return "Finance"
    if "facturatie" in doc_id:
        return "Finance"
    if "veiligheid" in doc_id or "vca" in doc_id:
        return "Veiligheid"
    if "odoo" in doc_id:
        return "Software"
    if "handboek" in doc_id:
        return "Algemeen"
    if "ceo" in doc_id or "romeo" in doc_id:
        return "Organisatie"
    return "Org"


def task_code_from_doc_id(doc_id: str) -> str | None:
    mapping = {
        "rag_org_info_mailbox": "INFO_MAILBOX",
        "rag_org_claims_odoo": "CLAIMS_ODOO",
        "rag_org_kredietlimieten": "KREDIETLIMIETEN",
        "rag_org_facturatie_finance": "FACTUREN_FINANCE",
        "rag_org_odoo_eerste_lijn": "ODOO_SUPPORT",
        "rag_org_veiligheid_vca": "VEILIGHEID_INCIDENT",
        "rag_org_co_ceo_romeo": "CO_CEO_ROMEO",
    }
    return mapping.get(doc_id)


def main() -> int:
    if not RAG_FOLDER.exists():
        print(f"Map bestaat niet: {RAG_FOLDER}")
        return 1

    files = sorted(RAG_FOLDER.glob("*.md"))

    if not files:
        print(f"Geen .md bestanden gevonden in: {RAG_FOLDER}")
        return 1

    print(f"Gevonden markdownbestanden: {len(files)}")
    print("-" * 80)

    ok = 0
    fail = 0

    for file_path in files:
        doc_id = file_path.stem.strip()
        inhoud_md = file_path.read_text(encoding="utf-8")

        payload = {
            "doc_id": doc_id,
            "titel": title_from_doc_id(doc_id),
            "categorie": category_from_doc_id(doc_id),
            "taak_code": task_code_from_doc_id(doc_id) or "",
            "inhoud_md": inhoud_md,
        }

        try:
            response = requests.post(
                API_URL.rstrip("/") + "/org-admin/rag-docs/create",
                data=payload,
                timeout=60,
                auth=(
                    os.getenv("ORG_ADMIN_USER", "admin"),
                    os.getenv("ORG_ADMIN_PASSWORD", "admin"),
                ),
                allow_redirects=False,
            )

            if response.status_code not in (200, 303):
                fail += 1
                print(f"FOUT {file_path.name}: HTTP {response.status_code}")
                print(response.text[:500])
                continue

            ok += 1
            print(f"OK   {file_path.name} -> {doc_id}")

        except Exception as e:
            fail += 1
            print(f"FOUT {file_path.name}: {e}")

    print("-" * 80)
    print(f"Klaar. Gelukt: {ok}, fouten: {fail}")

    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())