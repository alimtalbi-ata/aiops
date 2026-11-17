"""Strict offline ACME synthetic receipt model (Pydantic v2)."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator

SCHEMA = "aiops.debian-acme-sim-e2e.v1"
REQUIRED_STAGES = (
    "capability_simulator", "capability_core", "capability_twin",
    "capability_policy", "capability_worker", "simulator_start",
    "pre_resolution_core", "pre_resolution_twin", "pre_resolution_policy",
    "pre_resolution_worker", "worker_no_effect", "core_finalization",
    "post_resolution_core", "post_resolution_twin", "post_resolution_policy",
    "post_resolution_worker", "resolved",
)

class AcmeIds(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    incident_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    ticket_id: str = Field(min_length=1)
    proposal_id: str = Field(min_length=1)
    approval_id: str = Field(min_length=1)

    @field_validator("incident_id", "run_id", "ticket_id", "proposal_id", "approval_id")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("identifier cannot be blank")
        return value

    @field_validator("ticket_id")
    @classmethod
    def simulated_ticket(cls, value: str) -> str:
        if not value.startswith("SIM-GLPI-"):
            raise ValueError("ticket must be simulated")
        return value

    @field_validator("approval_id")
    @classmethod
    def simulated_approval(cls, value: str) -> str:
        if not value.startswith("SIM-APP-"):
            raise ValueError("approval must be simulated")
        return value

class AcmeReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_: Literal[SCHEMA] = Field(alias="schema")
    collected_at: datetime
    attempt_id: str = Field(pattern=r"^ACME-SIM-[A-F0-9]{16}$")
    tenant_id: Literal["ACME-TEST"]
    scenario_id: Literal["ACME-SAN-PAYMENTS"]
    mode: Literal["SIMULATION"]
    status: Literal["PASS"]
    reason: Literal["SIMULATED_SANDBOX_ONLY"]
    approval_issuer: Literal["TWIN_ACME_SIMULATED"]
    human_approval_claimed: Literal[False]
    live_effects_allowed: Literal[False]
    real_glpi_writes_allowed: Literal[False]
    docker_mutations: int = Field(strict=True, ge=0, le=0)
    stages: dict[str, Literal["PASS"]]
    ids: AcmeIds

    @model_validator(mode="after")
    def stages_and_freshness(self, info: ValidationInfo) -> "AcmeReceipt":
        if any(self.stages.get(stage) != "PASS" for stage in REQUIRED_STAGES):
            raise ValueError("INCOMPLETE_E2E_STAGES")
        context = info.context or {}
        now = context.get("now") or datetime.now(timezone.utc)
        max_age = context.get("max_age_minutes", 60)
        if not isinstance(max_age, int) or isinstance(max_age, bool) or not 1 <= max_age <= 1440:
            raise ValueError("INVALID_MAX_AGE")
        if self.collected_at.tzinfo is None or now.tzinfo is None:
            raise ValueError("INVALID_TIMESTAMP")
        age = now - self.collected_at
        if not timedelta(0) <= age <= timedelta(minutes=max_age):
            raise ValueError("STALE_OR_FUTURE_RECEIPT")
        return self
