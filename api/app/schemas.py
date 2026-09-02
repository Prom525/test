
from pydantic import BaseModel, Field
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Literal

class MachineIn(BaseModel):
    type: str
    serienummer: str | None = None
    locatie: str | None = None
    installatiedatum: datetime | None = None
    status: str | None = None

class MachineOut(MachineIn):
    machine_id: int
    class Config:
        from_attributes = True

class InspectieIn(BaseModel):
    machine_id: int
    datum: datetime | None = None
    verslag_text: str | None = None
    score: int | None = None

class InspectieOut(InspectieIn):
    inspectie_id: int
    class Config:
        from_attributes = True

class RAGQuery(BaseModel):
    vraag: str
    top_k: int = 5
    answer_mode: str = "extractive"
    doc_id: Optional[str] = None
    doc_ids: Optional[list[str]] = None
    doc_id_contains: Optional[str] = None
    doc_id_not_contains: Optional[str] = None
    rerank_candidates: int = 30
    use_mmr: bool = True

    # NIEUW: productfilters
    brand: Optional[str] = None
    model: Optional[str] = None
    category: Optional[str] = None
    variant: Optional[str] = None
    document_type: Optional[str] = None
    status: Optional[str] = None
    product_id: Optional[str] = None