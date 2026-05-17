from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import require_admin
from app.models.mapping import CatalogConceptDetail, CatalogIntegrationDetail, CatalogIntegrationRecord, CatalogReuseFitRequest, CatalogReuseFitResponse
from app.services.catalog_reuse_fit_service import build_catalog_reuse_fit
from app.services.llm_service import build_provider_from_settings
from app.services.persistence_service import persistence_service


router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/integrations", response_model=list[CatalogIntegrationRecord], dependencies=[Depends(require_admin)])
async def list_catalog_integrations(
    source_system: str | None = Query(None),
    target_system: str | None = Query(None),
    business_domain: str | None = Query(None),
    owner: str | None = Query(None),
    status: str | None = Query(None),
    artifact_type: str | None = Query(None),
    integration_name: str | None = Query(None),
) -> list[CatalogIntegrationRecord]:
    return persistence_service.list_catalog_integrations(
        source_system=source_system,
        target_system=target_system,
        business_domain=business_domain,
        owner=owner,
        status=status,
        artifact_type=artifact_type,
        integration_name=integration_name,
    )


@router.get("/search", response_model=list[CatalogIntegrationRecord], dependencies=[Depends(require_admin)])
async def search_catalog_integrations(
    q: str = Query(""),
    source_system: str | None = Query(None),
    target_system: str | None = Query(None),
    business_domain: str | None = Query(None),
    owner: str | None = Query(None),
    status: str | None = Query(None),
    artifact_type: str | None = Query(None),
) -> list[CatalogIntegrationRecord]:
    return persistence_service.search_catalog_integrations(
        q,
        source_system=source_system,
        target_system=target_system,
        business_domain=business_domain,
        owner=owner,
        status=status,
        artifact_type=artifact_type,
    )


@router.get("/integrations/{integration_name}", response_model=CatalogIntegrationDetail, dependencies=[Depends(require_admin)])
async def get_catalog_integration_detail(integration_name: str) -> CatalogIntegrationDetail:
    try:
        return persistence_service.get_catalog_integration_detail(integration_name)
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/concepts/{concept_id}", response_model=CatalogConceptDetail, dependencies=[Depends(require_admin)])
async def get_catalog_concept_detail(
    concept_id: str,
    source_system: str | None = Query(None),
    target_system: str | None = Query(None),
    status: str | None = Query(None),
    artifact_type: str | None = Query(None),
) -> CatalogConceptDetail:
    try:
        return persistence_service.get_catalog_concept_detail(
            concept_id,
            source_system=source_system,
            target_system=target_system,
            status=status,
            artifact_type=artifact_type,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/reuse-fit", response_model=CatalogReuseFitResponse, dependencies=[Depends(require_admin)])
async def explain_catalog_reuse_fit(request: CatalogReuseFitRequest) -> CatalogReuseFitResponse:
    provider = build_provider_from_settings()
    return build_catalog_reuse_fit(request, provider=provider)