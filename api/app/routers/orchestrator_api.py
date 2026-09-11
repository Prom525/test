from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks

from app.orchestrator.error_taxonomy import (
    build_exception_run_response,
)
from app.orchestrator.models_cp1 import OrchestratorAskRequest
from app.orchestrator.run_logging import persist_orchestrator_run
from app.orchestrator.response_shaping import shape_orchestrator_response
from app.orchestrator.service import run_orchestrator


router = APIRouter(
    prefix="/orchestrator",
    tags=["orchestrator"],
)


@router.post(
    "/ask",
    operation_id="promati_orchestrator_ask",
    openapi_extra={
        "x-openai-isConsequential": False,
    },
)
def orchestrator_ask(
    payload: OrchestratorAskRequest,
    background_tasks: BackgroundTasks,
):
    """
    Dunne HTTP-laag boven de orchestrator-service.

    Read-only voor PROMATI-businessdata.
    Operationele run-metadata wordt fail-open gelogd.

    P3.2:
    - normale responses behouden hun publieke contract;
    - uncaught exceptions krijgen intern een vaste
      error-taxonomie;
    - de exception wordt daarna opnieuw opgegooid zodat
      bestaand HTTP-gedrag behouden blijft.
    """
    trace_id = str(uuid4())

    try:

        response = run_orchestrator(
            payload
        )

    except Exception as exc:

        exception_response = build_exception_run_response(
            exc
        )
        exception_response["trace_id"] = trace_id

        persist_orchestrator_run(
            exception_response
        )

        raise


    response["trace_id"] = trace_id

    background_tasks.add_task(
        persist_orchestrator_run,
        response,
    )

    return shape_orchestrator_response(
        response,
        payload.response_profile,
    )
