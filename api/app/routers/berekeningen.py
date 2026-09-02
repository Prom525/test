from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/berekeningen", tags=["berekeningen"])


class BerekeningRunIn(BaseModel):
    """
    Wrapper zodat OpenAPI een object schema met properties heeft
    (Actions vindt 'dict' zonder properties te vaag).
    """
    params: Dict[str, Any] = Field(..., description="Vrije parameters voor de berekening")
    calc_name: Optional[str] = Field(None, description="Optionele naam van de berekening")


@router.post("/run")
def run_calc(body: BerekeningRunIn):
    # Dummy berekening: som van numerieke waarden in body.params
    total = 0.0
    for v in body.params.values():
        try:
            total += float(v)
        except Exception:
            continue

    return {
        "calc_name": body.calc_name,
        "input": body.params,
        "resultaat": total,
    }