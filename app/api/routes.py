from datetime import datetime

from fastapi import APIRouter, HTTPException
from loguru import logger

from app.deps import repo, parser
from app.models.schemas import (
    AddTransactionRequest,
    CreateObligationRequest,
    LLMResponse,
    Obligation,
    ParseRequest,
    Transaction,
    UpdateObligationRequest,
)

router = APIRouter()


@router.post("/parse", response_model=LLMResponse)
def parse_message(request: ParseRequest):
    logger.info("Parsing message: {}", request.message)
    context = repo.get_all(status="active")
    result = parser.parse(request.message, context=context)
    return result


@router.post("/obligations", response_model=list[Obligation])
def create_obligations(request: CreateObligationRequest):
    remaining = request.total_amount
    # For split expenses, the caller provides per-person amount as total_amount
    obligation = Obligation(
        person_name=request.person_name,
        type=request.type,
        direction=request.direction,
        trxn_id=request.trxn_id,
        total_amount=request.total_amount,
        expected_per_cycle=request.expected_per_cycle,
        remaining_amount=remaining,
        note=request.note,
    )
    created = repo.add(obligation)
    logger.info("Created obligation #{} for {}", created.id, created.person_name)
    return [created]


@router.get("/obligations", response_model=list[Obligation])
def list_obligations(status: str | None = None):
    return repo.get_all(status=status)


@router.get("/obligations/{obligation_id}", response_model=Obligation)
def get_obligation(obligation_id: int):
    obligation = repo.get(obligation_id)
    if obligation is None:
        raise HTTPException(status_code=404, detail="Obligation not found")
    return obligation


@router.patch("/obligations/{obligation_id}", response_model=Obligation)
def update_obligation(obligation_id: int, request: UpdateObligationRequest):
    existing = repo.get(obligation_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Obligation not found")

    updates = request.model_dump(exclude_none=True)
    if "total_amount" in updates:
        already_paid = existing.total_amount - existing.remaining_amount
        updates["remaining_amount"] = max(updates["total_amount"] - already_paid, 0)
    updated = repo.update(obligation_id, **updates)
    logger.info("Updated obligation #{}", obligation_id)
    return updated


@router.delete("/obligations/{obligation_id}")
def delete_obligation(obligation_id: int):
    if not repo.delete(obligation_id):
        raise HTTPException(status_code=404, detail="Obligation not found")
    logger.info("Deleted obligation #{}", obligation_id)
    return {"detail": "Obligation deleted"}


@router.post("/obligations/{obligation_id}/transactions", response_model=Obligation)
def add_transaction(obligation_id: int, request: AddTransactionRequest):
    existing = repo.get(obligation_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Obligation not found")
    if existing.status == "settled":
        raise HTTPException(status_code=400, detail="Obligation is already settled")
    if existing.type == "one_time" and request.amount != existing.remaining_amount:
        raise HTTPException(
            status_code=400,
            detail="One-time obligations must be settled in full",
        )

    transaction = Transaction(
        amount=request.amount,
        paid_at=datetime.now(),
        note=request.note,
    )
    updated = repo.add_transaction(obligation_id, transaction)
    logger.info(
        "Added transaction of {} to obligation #{}", request.amount, obligation_id
    )
    return updated


@router.post("/obligations/{obligation_id}/settle", response_model=Obligation)
def settle_obligation(obligation_id: int):
    existing = repo.get(obligation_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Obligation not found")
    if existing.status == "settled":
        raise HTTPException(status_code=400, detail="Obligation is already settled")

    settled = repo.settle(obligation_id)
    logger.info("Settled obligation #{}", obligation_id)
    return settled
