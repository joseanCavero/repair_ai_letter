"""Input contracts for repair description generation.

These models define the data the caller (Postman today, SAP later) supplies.
They intentionally exclude prices and customer personal data.
"""

from enum import StrEnum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

#: Languages supported by the first PoC iteration.
SupportedLanguage = Literal["en", "de", "es"]


class RepairType(StrEnum):
    COMPONENT_REPAIR = "component_repair"
    COMPONENT_REPLACEMENT = "component_replacement"
    INSPECTION = "inspection"
    MAINTENANCE = "maintenance"


class OperationStatus(StrEnum):
    PROPOSED = "proposed"
    COMPLETED = "completed"


class DescriptionStyle(StrEnum):
    PROFESSIONAL = "professional_customer_facing"
    CONCISE = "concise_customer_facing"


class RepairDataModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Equipment(RepairDataModel):
    type: str = Field(min_length=1, max_length=150)


class RepairFinding(RepairDataModel):
    code: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=1000)


class RepairOperation(RepairDataModel):
    code: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    status: OperationStatus


class Material(RepairDataModel):
    material_id: str | None = Field(default=None, max_length=100)
    description: str = Field(min_length=1, max_length=200)
    quantity: float = Field(gt=0, allow_inf_nan=False)
    unit: str = Field(min_length=1, max_length=20)


class RepairDescriptionRequest(RepairDataModel):
    request_id: UUID = Field(default_factory=uuid4)
    repair_type: RepairType
    language: SupportedLanguage = "en"
    equipment: Equipment
    findings: list[RepairFinding] = Field(max_length=50)
    operations: list[RepairOperation] = Field(max_length=50)
    materials: list[Material] = Field(max_length=100)
    style: DescriptionStyle = DescriptionStyle.PROFESSIONAL
