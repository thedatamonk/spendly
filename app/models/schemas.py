from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Transaction(BaseModel):
    amount: float
    paid_at: datetime
    note: str | None = None


class Obligation(BaseModel):
    id: int | None = None
    person_name: str
    type: Literal["recurring", "one_time"]
    total_amount: float
    expected_per_cycle: float | None = None
    remaining_amount: float
    status: Literal["active", "settled"] = "active"
    created_at: datetime = Field(default_factory=datetime.now)
    note: str | None = None
    transactions: list[Transaction] = []


class ParsedIntent(BaseModel):
    action: Literal["add", "settle", "query", "edit", "delete"]
    persons: list[str]
    amount: float | None = None
    obligation_type: Literal["recurring", "one_time"] | None = None
    expected_per_cycle: float | None = None
    note: str | None = None
    is_ambiguous: bool = False
    clarifying_question: str | None = None


class LLMResponse(BaseModel):
    parsed: ParsedIntent | None = None
    confirmation_message: str
    requires_confirmation: bool = True


class ParseRequest(BaseModel):
    message: str


class CreateObligationRequest(BaseModel):
    person_name: str
    type: Literal["recurring", "one_time"]
    total_amount: float
    expected_per_cycle: float | None = None
    note: str | None = None


class UpdateObligationRequest(BaseModel):
    person_name: str | None = None
    total_amount: float | None = None
    expected_per_cycle: float | None = None
    remaining_amount: float | None = None
    note: str | None = None


class AddTransactionRequest(BaseModel):
    amount: float
    note: str | None = None
