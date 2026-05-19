"""Tests canonical-gap extraction and suggestion behavior for stewardship flows."""

from app.models.mapping import AutoMappingResponse, CanonicalGapSuggestion, MappingCandidate, ScoringSignals
from app.models.schema import ColumnProfile, SchemaProfile
from app.services.canonical_gap_service import approve_canonical_gap_suggestion, extract_canonical_gap_candidates
from app.services.mapping_service import generate_mapping_candidates
from app.services.metadata_knowledge_service import metadata_knowledge_service
from app.services.persistence_service import persistence_service


def setup_function() -> None:
    persistence_service.clear_knowledge_overlays()
    metadata_knowledge_service.refresh()


def make_mapping_response() -> AutoMappingResponse:
    return AutoMappingResponse(
        mappings=[
            MappingCandidate(
                source="NTGEW",
                target="net_weight",
                confidence=0.72,
                confidence_label="medium_confidence",
                status="needs_review",
                method="multi_signal_heuristic",
                signals=ScoringSignals(name=0.8, semantic=0.75),
                explanation=["Name and semantic signals strongly align."],
            )
        ]
    )


def make_column(name: str, patterns: list[str], sample_values: list[str]) -> ColumnProfile:
    return ColumnProfile(
        name=name,
        normalized_name=name.replace("_", " "),
        dtype="object",
        null_ratio=0.0,
        unique_ratio=1.0,
        avg_length=10.0,
        non_null_count=len(sample_values),
        sample_values=sample_values,
        distinct_sample_values=sample_values,
        detected_patterns=patterns,
        tokenized_name=name.replace("_", " ").split(),
    )


def test_extracts_high_confidence_mapping_without_canonical_path() -> None:
    candidates = extract_canonical_gap_candidates(make_mapping_response())

    assert len(candidates) == 1
    assert candidates[0].source == "NTGEW"
    assert candidates[0].target == "net_weight"
    assert "canonical concept" in candidates[0].reason


def test_extracts_llm_backed_medium_confidence_gap_without_canonical_path() -> None:
    response = AutoMappingResponse(
        mappings=[
            MappingCandidate(
                source="AKONT",
                target="reconciliation_account",
                confidence=0.5181,
                confidence_label="low_confidence",
                status="needs_review",
                method="llm_validator",
                signals=ScoringSignals(name=0.25, semantic=0.22, llm=0.6),
                explanation=["LLM retained the financial account target, but no canonical path was resolved."],
                llm_consulted=True,
            )
        ]
    )

    candidates = extract_canonical_gap_candidates(response)

    assert len(candidates) == 1
    assert candidates[0].source == "AKONT"
    assert candidates[0].target == "reconciliation_account"


def test_approve_persists_overlay_only_new_canonical_concept_alias() -> None:
    candidate = extract_canonical_gap_candidates(make_mapping_response())[0]
    suggestion = CanonicalGapSuggestion(
        action="new_canonical_concept",
        concept_id="material.net_weight",
        display_name="Material Net Weight",
        aliases=["NTGEW", "net_weight", "MARA-NTGEW"],
        confidence=0.88,
        reasoning=["SAP NTGEW and net_weight describe material net weight."],
    )

    response = approve_canonical_gap_suggestion(candidate, suggestion, approved_by="test")

    assert response.activated is True
    assert response.saved_entry_count >= 3
    assert metadata_knowledge_service.resolve_canonical_concept_id("NTGEW") == "material.net_weight"
    matches = metadata_knowledge_service.match_canonical_concepts(
        ColumnProfile(
            name="net_weight",
            normalized_name="net weight",
            dtype="float",
            null_ratio=0.0,
            unique_ratio=1.0,
            avg_length=4.0,
            non_null_count=2,
            sample_values=["10.5", "12.0"],
            distinct_sample_values=["10.5", "12.0"],
            detected_patterns=["float"],
            tokenized_name=["net", "weight"],
        )
    )
    assert any(match.concept_id == "material.net_weight" for match in matches)


def test_approve_then_rerun_material_mapping_fills_shared_canonical_concept() -> None:
    source_schema = SchemaProfile(
        dataset_id="source",
        dataset_name="source.csv",
        row_count=2,
        columns=[make_column("NTGEW", ["float"], ["10.5", "12.0"])],
    )
    target_schema = SchemaProfile(
        dataset_id="target",
        dataset_name="target.csv",
        row_count=2,
        columns=[
            make_column("net_weight", ["float"], ["10.5", "12.0"]),
            make_column("gross_weight", ["float"], ["11.0", "12.5"]),
        ],
    )

    before = generate_mapping_candidates(source_schema, target_schema)
    before_selected = before.mappings[0]

    assert before_selected.target == "net_weight"
    assert before_selected.canonical_details.shared_concepts == []

    candidate = extract_canonical_gap_candidates(before)[0]
    approve_canonical_gap_suggestion(
        candidate,
        CanonicalGapSuggestion(
            action="new_canonical_concept",
            concept_id="material.net_weight",
            display_name="Material Net Weight",
            aliases=["NTGEW", "net_weight", "MARA-NTGEW"],
            confidence=0.88,
            reasoning=["SAP NTGEW and net_weight describe material net weight."],
        ),
        approved_by="test",
    )

    after = generate_mapping_candidates(source_schema, target_schema)
    after_selected = after.mappings[0]

    assert after_selected.target == "net_weight"
    assert after_selected.signals.canonical > 0
    assert [concept.concept_id for concept in after_selected.canonical_details.shared_concepts] == ["material.net_weight"]
