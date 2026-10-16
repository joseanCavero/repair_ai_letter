"""Shared test fixtures and helpers."""

import pytest

from repair_ai.schemas.repair import (
    Equipment,
    Material,
    OperationStatus,
    RepairDescriptionRequest,
    RepairFinding,
    RepairOperation,
    RepairType,
)


def sample_payload() -> dict:
    """A valid request payload as plain JSON-able data."""
    return {
        "repair_type": "component_replacement",
        "language": "en",
        "equipment": {"type": "Hydraulic pump"},
        "findings": [
            {"code": "F-01", "description": "Bearing wear detected"},
        ],
        "operations": [
            {
                "code": "OP-10",
                "description": "Replace bearing",
                "status": "proposed",
            },
        ],
        "materials": [
            {
                "material_id": "MAT-123",
                "description": "Bearing 6204",
                "quantity": 2.0,
                "unit": "pc",
            },
        ],
        "style": "professional_customer_facing",
    }


@pytest.fixture
def sample_request() -> RepairDescriptionRequest:
    return RepairDescriptionRequest(
        repair_type=RepairType.COMPONENT_REPLACEMENT,
        language="en",
        equipment=Equipment(type="Hydraulic pump"),
        findings=[RepairFinding(code="F-01", description="Bearing wear detected")],
        operations=[
            RepairOperation(
                code="OP-10",
                description="Replace bearing",
                status=OperationStatus.PROPOSED,
            )
        ],
        materials=[
            Material(
                material_id="MAT-123",
                description="Bearing 6204",
                quantity=2.0,
                unit="pc",
            )
        ],
    )
