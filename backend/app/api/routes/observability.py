from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import require_admin
from app.core.config import reload_settings, settings_snapshot
from app.models.mapping import (
    CorrectionRuleCandidate,
    DecisionLogEntry,
    ReusableCorrectionRule,
    ReusableCorrectionRulePromotionRequest,
    RuntimeConfigSnapshot,
    UserCorrectionEntry,
)
from app.services.correction_service import correction_store
from app.services.decision_log_service import decision_log_store
from app.services.persistence_service import persistence_service


router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/decision-logs", response_model=list[DecisionLogEntry], dependencies=[Depends(require_admin)])
async def list_decision_logs() -> list[DecisionLogEntry]:
    return decision_log_store.list_entries()


@router.get("/corrections", response_model=list[UserCorrectionEntry], dependencies=[Depends(require_admin)])
async def list_user_corrections() -> list[UserCorrectionEntry]:
    return correction_store.list_entries()


@router.post("/corrections", response_model=UserCorrectionEntry, dependencies=[Depends(require_admin)])
async def create_user_correction(entry: UserCorrectionEntry) -> UserCorrectionEntry:
    correction_store.append(entry)
    return correction_store.list_entries()[-1]


@router.get("/corrections/reusable-rules", response_model=list[CorrectionRuleCandidate], dependencies=[Depends(require_admin)])
async def list_reusable_correction_rules(min_occurrences: int = Query(default=2, ge=2, le=20)) -> list[CorrectionRuleCandidate]:
    return correction_store.suggest_reusable_rules(min_occurrences=min_occurrences)


@router.get("/corrections/reusable-rules/active", response_model=list[ReusableCorrectionRule], dependencies=[Depends(require_admin)])
async def list_active_reusable_correction_rules() -> list[ReusableCorrectionRule]:
    return correction_store.list_reusable_rules()


@router.post("/corrections/reusable-rules/promote", response_model=ReusableCorrectionRule, dependencies=[Depends(require_admin)])
async def promote_reusable_correction_rule(
    request: ReusableCorrectionRulePromotionRequest,
) -> ReusableCorrectionRule:
    try:
        return correction_store.promote_reusable_rule(request)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.get("/config", response_model=RuntimeConfigSnapshot, dependencies=[Depends(require_admin)])
async def get_runtime_config() -> RuntimeConfigSnapshot:
    return RuntimeConfigSnapshot.model_validate(settings_snapshot())


@router.post("/config/reload", response_model=RuntimeConfigSnapshot, dependencies=[Depends(require_admin)])
async def reload_runtime_config() -> RuntimeConfigSnapshot:
    reloaded = reload_settings()
    persistence_service.reconfigure(reloaded.sqlite_path)
    return RuntimeConfigSnapshot.model_validate(settings_snapshot())