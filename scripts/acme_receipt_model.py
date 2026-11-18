"""Strict offline ACME synthetic receipt model (Pydantic v2)."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import re
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
    ticket_id: str = Field(min_length=1, json_schema_extra={"pattern": r"^SIM-GLPI-[A-Za-z0-9][A-Za-z0-9_-]*$"})
    proposal_id: str = Field(min_length=1)
    approval_id: str = Field(min_length=1, json_schema_extra={"pattern": r"^SIM-APP-[A-Za-z0-9][A-Za-z0-9_-]*$"})

    @field_validator("incident_id", "run_id", "ticket_id", "proposal_id", "approval_id")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("identifier cannot be blank")
        return value

    @field_validator("ticket_id")
    @classmethod
    def simulated_ticket(cls, value: str) -> str:
        if re.fullmatch(r"SIM-GLPI-[A-Za-z0-9][A-Za-z0-9_-]*", value, flags=re.ASCII) is None:
            raise ValueError("ticket must be simulated")
        return value

    @field_validator("approval_id")
    @classmethod
    def simulated_approval(cls, value: str) -> str:
        if re.fullmatch(r"SIM-APP-[A-Za-z0-9][A-Za-z0-9_-]*", value, flags=re.ASCII) is None:
            raise ValueError("approval must be simulated")
        return value

class AcmeReceipt(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_: Literal[SCHEMA] = Field(alias="schema")
    collected_at: datetime = Field(json_schema_extra={"pattern": r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)$"})
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
    stages: dict[str, Literal["PASS"]] = Field(json_schema_extra={
        "properties": {name: {"const": "PASS", "type": "string"} for name in REQUIRED_STAGES},
        "required": list(REQUIRED_STAGES),
        "additionalProperties": False,
    })
    ids: AcmeIds

    @field_validator("collected_at", mode="before")
    @classmethod
    def utc_timestamp(cls, value):
        if isinstance(value, str):
            if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)", value) is None:
                raise ValueError("INVALID_UTC_TIMESTAMP")
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        elif not isinstance(value, datetime):
            raise ValueError("INVALID_UTC_TIMESTAMP")
        return value

    @field_validator("human_approval_claimed", "live_effects_allowed", "real_glpi_writes_allowed", mode="before")
    @classmethod
    def explicitly_false(cls, value):
        if value is not False:
            raise ValueError("EXPECTED_LITERAL_FALSE")
        return value

    @model_validator(mode="after")
    def stages_and_freshness(self, info: ValidationInfo) -> "AcmeReceipt":
        if set(self.stages) != set(REQUIRED_STAGES) or any(self.stages.get(stage) != "PASS" for stage in REQUIRED_STAGES):
            raise ValueError("INCOMPLETE_E2E_STAGES")
        context = info.context or {}
        now = context.get("now") or datetime.now(timezone.utc)
        max_age = context.get("max_age_minutes", 60)
        if not isinstance(max_age, int) or isinstance(max_age, bool) or not 1 <= max_age <= 1440:
            raise ValueError("INVALID_MAX_AGE")
        if self.collected_at.utcoffset() != timedelta(0) or now.utcoffset() is None:
            raise ValueError("INVALID_TIMESTAMP")
        age = now - self.collected_at
        if not timedelta(0) <= age <= timedelta(minutes=max_age):
            raise ValueError("STALE_OR_FUTURE_RECEIPT")
        return self
