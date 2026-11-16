"""V2.8 fenced denial HTTP routes."""
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from core.denial_fencing import claim_denials
from core.denial_finalize import finalize_denial

class ClaimRequest(BaseModel):
    owner: str = Field(min_length=1,max_length=128)
    limit: int = Field(default=20,ge=1,le=50)
    lease_seconds: int = Field(default=60,ge=10,le=300)

class FinalizeRequest(BaseModel):
    owner: str = Field(min_length=1,max_length=128)
    fencing_token: int = Field(ge=1)
    verdict: dict

def register_denial_routes(app, db, auth, bearer):
    router = APIRouter()

    @router.post("/api/denial-intents/claim")
    def claim(x: ClaimRequest, authorization: str | None = Header(None)):
        auth(bearer(authorization))
        try:
            with db() as conn:
                items = claim_denials(
                    conn,x.owner,x.limit,x.lease_seconds)
            return {"items":items}
        except ValueError as exc:
            raise HTTPException(422,str(exc))

    @router.post("/api/runs/{rid}/denial-intent/{cid}/finalize")
    def finalize(rid: str,cid: str,x: FinalizeRequest,
                 authorization: str | None = Header(None)):
        auth(bearer(authorization))
        try:
            with db() as conn:
                return finalize_denial(
                    conn,rid,cid,x.owner,
                    x.fencing_token,x.verdict)
        except ValueError as exc:
            raise HTTPException(409,str(exc))

    app.include_router(router)
