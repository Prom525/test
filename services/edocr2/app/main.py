from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from pathlib import Path
import os
import re
import subprocess
import tempfile

from minio import Minio


app = FastAPI(title="eDOCR2 Service", version="0.2.0")


class ProcessPayload(BaseModel):
    rfq_id: str | None = None
    position_id: str | None = None
    document_id: str | None = None
    storage_path: str | None = None
    file_name: str | None = None
    bucket: str | None = None
    test: bool | None = False
    source: str | None = None


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "edocr2",
        "version": "0.2.0",
    }


def get_minio_client() -> Minio:
    endpoint = os.getenv("MINIO_ENDPOINT")
    access_key = os.getenv("MINIO_ACCESS_KEY")
    secret_key = os.getenv("MINIO_SECRET_KEY")

    if not endpoint or not access_key or not secret_key:
        raise RuntimeError("MINIO_ENDPOINT, MINIO_ACCESS_KEY or MINIO_SECRET_KEY is missing")

    secure = endpoint.startswith("https://")
    endpoint_clean = endpoint.replace("http://", "").replace("https://", "")

    return Minio(
        endpoint_clean,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
    )


def download_from_minio(bucket: str, storage_path: str, target_path: Path) -> None:
    client = get_minio_client()
    client.fget_object(bucket, storage_path, str(target_path))


def extract_text_with_pdftotext(pdf_path: Path) -> str:
    txt_path = pdf_path.with_suffix(".txt")

    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), str(txt_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr or "pdftotext failed")

    if not txt_path.exists():
        return ""

    return txt_path.read_text(encoding="utf-8", errors="ignore")


def extract_numbers_from_text(text: str, file_name: str | None = None) -> dict:
    source = f"{file_name or ''}\n{text or ''}"

    extracted = {}

    # Voorbeelden:
    # Tail Drum Ø500x524x1400x2165x150
    # Tail Drum 500x524x1400x2165x150
    pattern = re.search(
        r"[Øø]?\s*(\d{3,4})\s*[xX]\s*(\d{2,4})\s*[xX]\s*(\d{3,5})\s*[xX]\s*(\d{3,5})\s*[xX]\s*(\d{2,4})",
        source,
    )

    if pattern:
        values = [int(v) for v in pattern.groups()]
        extracted["diameter_mm"] = values[0]
        extracted["drum_width_mm"] = values[2]
        extracted["shaft_diameter_mm"] = values[4]
        extracted["raw_dimension_sequence"] = values

    bearing_match = re.search(r"\b(CTL[-\s]?\d{3}/\d{2,4})\b", source, re.IGNORECASE)
    if bearing_match:
        bearing = bearing_match.group(1).replace(" ", "")
        extracted["bearing_type"] = bearing
        extracted["bearing_housing"] = bearing

    if re.search(r"\bNBR\b", source, re.IGNORECASE):
        extracted["rubber_material"] = "NBR"

    return extracted


@app.post("/process")
def process_document(payload: ProcessPayload):
    if payload.test:
        return {
            "status": "received",
            "service": "edocr2",
            "mode": "test",
            "payload": payload.dict(),
        }

    if not payload.storage_path:
        raise HTTPException(
            status_code=400,
            detail="storage_path is required",
        )

    bucket = payload.bucket or os.getenv("MINIO_BUCKET", "rfq-artifacts")

    with tempfile.TemporaryDirectory(prefix="edocr2_") as tmpdir:
        tmpdir_path = Path(tmpdir)

        suffix = Path(payload.file_name or payload.storage_path).suffix or ".pdf"
        local_pdf = tmpdir_path / f"{payload.document_id or 'document'}{suffix}"

        try:
            download_from_minio(bucket, payload.storage_path, local_pdf)
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"MinIO download failed: {exc}",
            )

        text = ""
        text_error = None

        try:
            text = extract_text_with_pdftotext(local_pdf)
        except Exception as exc:
            text_error = str(exc)

        extracted = extract_numbers_from_text(text, payload.file_name)

        return {
            "status": "ok",
            "service": "edocr2",
            "version": "0.2.0",
            "rfq_id": payload.rfq_id,
            "position_id": payload.position_id,
            "document_id": payload.document_id,
            "bucket": bucket,
            "storage_path": payload.storage_path,
            "file_name": payload.file_name,
            "local_file_size": local_pdf.stat().st_size if local_pdf.exists() else None,
            "text_length": len(text),
            "text_error": text_error,
            "text_excerpt": text[:1500],
            "extracted": extracted,
        }