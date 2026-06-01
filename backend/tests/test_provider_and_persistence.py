"""Tests provider selection logic and SQLite-backed persistence contracts."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch
from urllib.error import URLError

from app.core.config import reload_settings, settings
from app.models.knowledge import KnowledgeAuditEntry, KnowledgeOverlayEntry
from app.models.mapping import DecisionLogEntry, EvaluationMetrics, ReusableCorrectionRule, TransformationTestCase, UserCorrectionEntry
from app.services.correction_service import correction_store
from app.services.decision_log_service import decision_log_store
from app.services.llm_service import (
    LMStudioProvider,
    OllamaProvider,
    OpenAIResponsesProvider,
    build_provider_from_settings,
    summarize_llm_runtime,
    summarize_tts_runtime,
)
from app.services.persistence_service import persistence_service


class FakeHTTPResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


class RequestCaptureResponse(FakeHTTPResponse):
    def __init__(self, payload: dict, sink: list[dict]) -> None:
        super().__init__(payload)
        self._sink = sink

    def __call__(self, http_request, timeout=None):
        self._sink.append(
            {
                "full_url": http_request.full_url,
                "headers": dict(http_request.header_items()),
                "body": http_request.data.decode("utf-8") if http_request.data else "",
                "timeout": timeout,
            }
        )
        return self


class SequencedURLopener:
    def __init__(self, *responses) -> None:
        self._responses = list(responses)

    def __call__(self, http_request, timeout=None):
        if not self._responses:
            raise AssertionError("No more fake HTTP responses configured")
        response = self._responses.pop(0)
        if callable(response):
            return response(http_request, timeout=timeout)
        return response


def setup_function() -> None:
    decision_log_store.clear()
    correction_store.clear()
    correction_store.clear_reusable_rules()
    persistence_service.clear_mapping_sets()
    persistence_service.clear_benchmark_datasets()
    persistence_service.clear_evaluation_runs()
    persistence_service.clear_transformation_test_sets()
    persistence_service.clear_knowledge_overlays()
    persistence_service.clear_uploaded_datasets()


def test_sqlite_connection_applies_busy_timeout_and_rollback(tmp_path: Path) -> None:
    original_db_path = persistence_service.db_path
    persistence_service.reconfigure(str(tmp_path / "persistence_contract.sqlite3"))
    try:
        with persistence_service.connection() as connection:
            busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
            journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]

        assert int(busy_timeout) >= 5000
        assert str(journal_mode).lower() == "wal"

        try:
            with persistence_service.connection() as connection:
                connection.execute("INSERT INTO draft_sessions (name, payload) VALUES (?, ?)", ("temp", "{}"))
                raise RuntimeError("force rollback")
        except RuntimeError:
            pass

        with persistence_service.connection() as connection:
            row_count = connection.execute("SELECT COUNT(*) FROM draft_sessions").fetchone()[0]

        assert row_count == 0
    finally:
        persistence_service.reconfigure(original_db_path)


def test_openai_provider_extracts_text_from_responses_api_shape() -> None:
    provider = OpenAIResponsesProvider(api_key="test-key", model="gpt-test", base_url="http://example.test")

    with patch("app.services.llm_service.request.urlopen", return_value=FakeHTTPResponse({"output": [{"content": [{"text": '{"selected_target":"phone_number","confidence":0.8,"reasoning":["ok"]}'}]}]})):
        result = provider.generate("prompt", timeout_seconds=1.0)

    assert "selected_target" in result


def test_ollama_provider_extracts_response_text() -> None:
    provider = OllamaProvider(model="gemma", base_url="http://example.test")

    with patch("app.services.llm_service.request.urlopen", return_value=FakeHTTPResponse({"response": '{"selected_target":"phone_number","confidence":0.8,"reasoning":["ok"]}'})):
        result = provider.generate("prompt", timeout_seconds=1.0)

    assert "selected_target" in result


def test_provider_factory_builds_expected_provider() -> None:
    previous = (settings.llm_provider, settings.openai_api_key, settings.llm_model)
    settings.llm_provider = "ollama"
    settings.llm_model = "gemma"
    try:
        provider = build_provider_from_settings()
        assert isinstance(provider, OllamaProvider)
    finally:
        settings.llm_provider, settings.openai_api_key, settings.llm_model = previous


def test_provider_factory_builds_lmstudio_openai_compatible_provider() -> None:
    previous = (settings.llm_provider, settings.llm_model, settings.lmstudio_base_url, settings.openai_api_key)
    settings.llm_provider = "lmstudio"
    settings.llm_model = "local-model"
    settings.lmstudio_base_url = "http://127.0.0.1:1234/v1/chat/completions"
    settings.openai_api_key = "should-not-be-used"
    try:
        provider = build_provider_from_settings()

        assert isinstance(provider, LMStudioProvider)
        assert provider.base_url == "http://127.0.0.1:1234/v1/chat/completions"
        assert provider.model == "local-model"
    finally:
        settings.llm_provider, settings.llm_model, settings.lmstudio_base_url, settings.openai_api_key = previous


def test_lmstudio_provider_auto_discovers_model_when_configured_as_auto() -> None:
    captured_requests: list[dict] = []
    provider = LMStudioProvider(model="auto", base_url="http://127.0.0.1:1234/v1")

    with patch(
        "app.services.llm_service.request.urlopen",
        new=SequencedURLopener(
            FakeHTTPResponse({"data": [{"id": "nvidia/nemotron-3-nano-4b"}]}),
            RequestCaptureResponse({"choices": [{"message": {"content": "OK"}}]}, captured_requests),
        ),
    ):
        result = provider.generate("prompt", timeout_seconds=1.0)

    assert result == "OK"
    assert captured_requests
    assert captured_requests[0]["full_url"] == "http://127.0.0.1:1234/v1/chat/completions"
    assert '"model": "nvidia/nemotron-3-nano-4b"' in captured_requests[0]["body"]


def test_summarize_llm_runtime_reports_missing_lmstudio_model() -> None:
    previous = (settings.llm_provider, settings.llm_model, settings.lmstudio_base_url)
    settings.llm_provider = "lmstudio"
    settings.llm_model = "gemma-4-e2b-it"
    settings.lmstudio_base_url = "http://127.0.0.1:1234/v1"
    try:
        with patch(
            "app.services.llm_service.request.urlopen",
            return_value=FakeHTTPResponse({"data": [{"id": "nvidia/nemotron-3-nano-4b"}]}),
        ):
            snapshot = summarize_llm_runtime()

        assert snapshot["llm_status"] == "misconfigured"
        assert snapshot["llm_reachable"] is True
        assert snapshot["llm_resolved_model"] == "nvidia/nemotron-3-nano-4b"
    finally:
        settings.llm_provider, settings.llm_model, settings.lmstudio_base_url = previous


def test_summarize_tts_runtime_reports_unreachable_lmstudio() -> None:
    previous = (settings.tts_provider, settings.lmstudio_orpheus_model, settings.lmstudio_tts_base_url, settings.tts_timeout_seconds)
    settings.tts_provider = "lmstudio_orpheus"
    settings.lmstudio_orpheus_model = "orpheus-3b-0.1-ft"
    settings.lmstudio_tts_base_url = "http://127.0.0.1:1234"
    settings.tts_timeout_seconds = 30.0
    try:
        with patch("app.services.llm_service.request.urlopen", side_effect=URLError("connection refused")):
            snapshot = summarize_tts_runtime()

        assert snapshot["tts_status"] == "unreachable"
        assert snapshot["tts_reachable"] is False
        assert "network_error" in snapshot["tts_status_detail"]
    finally:
        (
            settings.tts_provider,
            settings.lmstudio_orpheus_model,
            settings.lmstudio_tts_base_url,
            settings.tts_timeout_seconds,
        ) = previous


def test_summarize_tts_runtime_reports_missing_orpheus_model() -> None:
    previous = (settings.tts_provider, settings.lmstudio_orpheus_model, settings.lmstudio_tts_base_url, settings.tts_timeout_seconds)
    settings.tts_provider = "lmstudio_orpheus"
    settings.lmstudio_orpheus_model = "orpheus-3b-0.1-ft"
    settings.lmstudio_tts_base_url = "http://127.0.0.1:1234"
    settings.tts_timeout_seconds = 30.0
    try:
        with patch(
            "app.services.llm_service.request.urlopen",
            return_value=FakeHTTPResponse({"data": [{"id": "gemma-4-e2b-it"}]}),
        ):
            snapshot = summarize_tts_runtime()

        assert snapshot["tts_status"] == "misconfigured"
        assert snapshot["tts_reachable"] is True
        assert "Configured TTS model 'orpheus-3b-0.1-ft'" in snapshot["tts_status_detail"]
    finally:
        (
            settings.tts_provider,
            settings.lmstudio_orpheus_model,
            settings.lmstudio_tts_base_url,
            settings.tts_timeout_seconds,
        ) = previous


def test_openai_compatible_provider_omits_authorization_when_api_key_is_empty() -> None:
    captured_requests: list[dict] = []
    provider = OpenAIResponsesProvider(api_key="", model="local-model", base_url="http://example.test")

    with patch(
        "app.services.llm_service.request.urlopen",
        new=RequestCaptureResponse({"output": [{"content": [{"text": '{"selected_target":"phone_number","confidence":0.8,"reasoning":["ok"]}'}]}]}, captured_requests),
    ):
        result = provider.generate("prompt", timeout_seconds=1.0)

    assert "selected_target" in result
    assert captured_requests
    assert "Authorization" not in captured_requests[0]["headers"]


def test_decision_logs_and_corrections_roundtrip_through_persistence() -> None:
    decision_entry = DecisionLogEntry(
        source="cust_ref",
        created_by="qa-user",
        workspace_id="ws-persistence-01",
        candidate_targets=["customer_id", "phone_number"],
        heuristic_scores={"customer_id": 0.42, "phone_number": 0.77},
        final_target="phone_number",
        final_status="accepted",
        used_llm=False,
    )
    correction_entry = UserCorrectionEntry(
        source="cust_ref",
        suggested_target="customer_id",
        corrected_target="phone_number",
        note="user corrected based on phone pattern",
    )

    decision_log_store.append(decision_entry)
    correction_store.append(correction_entry)

    assert decision_log_store.list_entries()[0].final_target == "phone_number"
    assert decision_log_store.list_entries()[0].created_by == "qa-user"
    assert decision_log_store.list_entries()[0].workspace_id == "ws-persistence-01"
    assert correction_store.list_entries()[0].corrected_target == "phone_number"
    assert correction_store.list_entries()[0].status == "overridden"
    assert correction_store.list_entries()[0].version == 1
    assert correction_store.list_entries()[0].correction_id is not None


def test_store_reads_refresh_from_persistence_even_when_memory_cache_is_stale() -> None:
    decision_entry = DecisionLogEntry(
        source="cust_ref",
        created_by="qa-user",
        workspace_id="ws-persistence-02",
        candidate_targets=["customer_id"],
        heuristic_scores={"customer_id": 0.42},
        final_target="customer_id",
        final_status="accepted",
        used_llm=False,
    )
    correction_entry = UserCorrectionEntry(
        source="cust_ref",
        suggested_target="customer_id",
        corrected_target="phone_number",
        status="overridden",
    )

    decision_log_store.append(decision_entry)
    correction_store.append(correction_entry)

    decision_log_store._entries = []
    correction_store._entries = []

    assert decision_log_store.list_entries()[0].final_target == "customer_id"
    assert correction_store.list_entries()[0].corrected_target == "phone_number"


def test_reusable_correction_rules_roundtrip_through_persistence() -> None:
    first = persistence_service.save_reusable_correction_rule(
        ReusableCorrectionRule(
            source="cust_ref",
            suggested_target="customer_id",
            corrected_target="account_id",
            status="overridden",
            occurrence_count=3,
            created_by="qa-user",
            note="Promoted from repeated overrides",
        )
    )
    second = persistence_service.save_reusable_correction_rule(
        ReusableCorrectionRule(
            source="cust_ref",
            suggested_target="customer_id",
            corrected_target="account_id",
            status="overridden",
            occurrence_count=5,
        )
    )

    listed = persistence_service.list_reusable_correction_rules()

    assert first.rule_id is not None
    assert second.rule_id == first.rule_id
    assert listed[0].occurrence_count == 5
    assert listed[0].created_by == "qa-user"


def test_mapping_sets_roundtrip_and_audit_through_persistence() -> None:
    saved = persistence_service.save_mapping_set(
        "customer-master",
        [
            {
                "source": "cust_id",
                "target": "customer_id",
                "status": "accepted",
            }
        ],
        source_dataset_id="source-1",
        target_dataset_id="target-1",
        integration_name="Customer Master Sync",
        source_system="SAP",
        target_system="Salesforce",
        business_domain="Customer",
        interface_type="batch",
        description="Nightly customer sync",
        artifact_type="standard",
        canonical_concepts=["customer.id", "customer.phone"],
        unmatched_sources=["country_code"],
        created_by="qa-user",
        note="Initial draft",
        owner="governance-team",
        assignee="analyst-1",
        review_note="Initial governance context",
    )
    updated = persistence_service.update_mapping_set_status(
        saved.mapping_set_id,
        "review",
        owner="governance-team",
        assignee="analyst-2",
        review_note="Ready for review",
    )
    audit = persistence_service.append_mapping_set_audit_log(
        {
            "mapping_set_id": saved.mapping_set_id,
            "mapping_set_name": saved.name,
            "version": saved.version,
            "action": "status_change",
            "status": "review",
            "changed_by": "qa-user",
            "note": "Ready for review",
            "created_at": "2026-05-02T10:00:00+00:00",
        }
    )

    listed = persistence_service.list_mapping_sets()
    loaded = persistence_service.get_mapping_set(saved.mapping_set_id)
    audits = persistence_service.list_mapping_set_audit_logs(saved.mapping_set_id)
    catalog = persistence_service.list_catalog_integrations()

    assert saved.version == 1
    assert updated.status == "review"
    assert listed[0].name == "customer-master"
    assert loaded.mapping_decisions[0].target == "customer_id"
    assert loaded.integration_name == "Customer Master Sync"
    assert loaded.artifact_type == "standard"
    assert loaded.canonical_concepts == ["customer.id", "customer.phone"]
    assert loaded.unmatched_sources == ["country_code"]
    assert loaded.owner == "governance-team"
    assert loaded.assignee == "analyst-2"
    assert loaded.review_note == "Ready for review"
    assert audit.audit_id is not None
    assert audits[0].action == "status_change"
    assert catalog[0].integration_name == "Customer Master Sync"
    assert catalog[0].status == "review"
    assert catalog[0].source_system == "SAP"
    assert catalog[0].target_system == "Salesforce"


def test_catalog_entry_infers_canonical_only_artifact_from_saved_mapping_set() -> None:
    saved = persistence_service.save_mapping_set(
        "sap-country-concepts",
        [
            {"source": "KUNNR", "target": "customer.id", "status": "accepted"},
            {"source": "LAND1", "target": "", "status": "needs_review"},
        ],
        integration_name="SAP Customer Canonical",
        target_system="canonical",
    )

    catalog = persistence_service.list_catalog_integrations(
        artifact_type="canonical-only",
        integration_name="SAP Customer Canonical",
    )

    assert saved.artifact_type == "canonical-only"
    assert catalog[0].canonical_concepts == ["customer.id"]
    assert catalog[0].unmatched_sources == ["LAND1"]


def test_catalog_entry_infers_standard_artifact_from_concrete_target_system() -> None:
    saved = persistence_service.save_mapping_set(
        "customer-master-no-target-dataset",
        [
            {"source": "KUNNR", "target": "customer.id", "status": "accepted"},
        ],
        integration_name="Customer Master Sync",
        source_system="SAP",
        target_system="Salesforce",
    )

    catalog = persistence_service.list_catalog_integrations(integration_name="Customer Master Sync")

    assert saved.artifact_type == "standard"
    assert catalog[0].artifact_type == "standard"


def test_catalog_detail_groups_versions_and_exposes_latest_approved() -> None:
    first = persistence_service.save_mapping_set(
        "customer-master",
        [{"source": "cust_id", "target": "customer.id", "status": "accepted"}],
        integration_name="Customer Master Sync",
        source_system="SAP",
        target_system="Salesforce",
        business_domain="Customer",
        artifact_type="canonical-only",
        canonical_concepts=["customer.id"],
    )
    persistence_service.update_mapping_set_status(first.mapping_set_id, "approved", owner="governance-team")
    persistence_service.save_mapping_set(
        "customer-master",
        [{"source": "cust_id", "target": "customer.id", "status": "accepted"}],
        integration_name="Customer Master Sync",
        source_system="SAP",
        target_system="Salesforce",
        business_domain="Customer",
        artifact_type="canonical-only",
        canonical_concepts=["customer.id", "customer.name"],
        unmatched_sources=["LAND1"],
    )

    detail = persistence_service.get_catalog_integration_detail("Customer Master Sync")

    assert detail.latest_version.version == 2
    assert detail.latest_approved_version is not None
    assert detail.latest_approved_version.version == 1
    assert detail.canonical_concepts == ["customer.id", "customer.name"]
    assert detail.unmatched_sources == ["LAND1"]
    assert [version.version for version in detail.versions] == [2, 1]


def test_catalog_detail_includes_ranked_similar_integrations() -> None:
    persistence_service.save_mapping_set(
        "customer-master",
        [{"source": "cust_id", "target": "customer.id", "status": "accepted"}],
        integration_name="Customer Master Sync",
        source_system="SAP",
        target_system="Salesforce",
        business_domain="Customer",
        artifact_type="canonical-only",
        canonical_concepts=["customer.id", "customer.name", "customer.country_code"],
    )
    persistence_service.save_mapping_set(
        "lead-reuse",
        [{"source": "lead_id", "target": "customer.id", "status": "accepted"}],
        integration_name="Lead Reuse Sync",
        source_system="CRM",
        target_system="Salesforce",
        business_domain="Customer",
        artifact_type="canonical-only",
        canonical_concepts=["customer.id", "customer.name"],
    )
    persistence_service.save_mapping_set(
        "customer-finance",
        [{"source": "cust_code", "target": "customer.id", "status": "accepted"}],
        integration_name="Customer Finance Snapshot",
        source_system="SAP",
        target_system="Salesforce",
        business_domain="Finance",
        artifact_type="standard",
        canonical_concepts=["customer.id"],
    )

    detail = persistence_service.get_catalog_integration_detail("Customer Master Sync")

    assert [item.integration_name for item in detail.similar_integrations] == [
        "Lead Reuse Sync",
        "Customer Finance Snapshot",
    ]
    assert detail.similar_integrations[0].shared_concepts == ["customer.id", "customer.name"]
    assert detail.similar_integrations[0].same_target_system is True
    assert detail.similar_integrations[0].same_business_domain is True
    assert detail.similar_integrations[1].same_source_system is True
    assert detail.similar_integrations[1].same_artifact_type is False


def test_catalog_concept_detail_lists_all_matching_integrations() -> None:
    persistence_service.save_mapping_set(
        "customer-master",
        [{"source": "cust_id", "target": "customer.id", "status": "accepted"}],
        integration_name="Customer Master Sync",
        source_system="SAP",
        target_system="Salesforce",
        business_domain="Customer",
        canonical_concepts=["customer.id"],
    )
    persistence_service.save_mapping_set(
        "lead-master",
        [{"source": "lead_ref", "target": "customer.id", "status": "accepted"}],
        integration_name="Lead Reuse Sync",
        source_system="CRM",
        target_system="Salesforce",
        business_domain="Customer",
        canonical_concepts=["customer.id"],
    )

    concept_detail = persistence_service.get_catalog_concept_detail("customer.id")

    assert concept_detail.concept_id == "customer.id"
    assert concept_detail.usage_count == 2
    assert [item.integration_name for item in concept_detail.integrations] == [
        "Customer Master Sync",
        "Lead Reuse Sync",
    ]


def test_catalog_search_matches_metadata_and_concept_filters() -> None:
    persistence_service.save_mapping_set(
        "customer-master",
        [{"source": "cust_id", "target": "customer.id", "status": "accepted"}],
        integration_name="Customer Master Sync",
        source_system="SAP",
        target_system="Salesforce",
        business_domain="Customer",
        owner="governance-team",
        canonical_concepts=["customer.id"],
    )
    persistence_service.save_mapping_set(
        "vendor-master",
        [{"source": "vendor_id", "target": "vendor.id", "status": "accepted"}],
        integration_name="Vendor Master Sync",
        source_system="SAP",
        target_system="Coupa",
        business_domain="Vendor",
        owner="finance-team",
        canonical_concepts=["vendor.id"],
    )

    concept_matches = persistence_service.search_catalog_integrations("customer.id")
    filtered_matches = persistence_service.search_catalog_integrations(
        "SAP",
        business_domain="Customer",
        owner="governance-team",
    )

    assert [item.integration_name for item in concept_matches] == ["Customer Master Sync"]
    assert [item.integration_name for item in filtered_matches] == ["Customer Master Sync"]


def test_mapping_set_versions_increment_for_same_name() -> None:
    first = persistence_service.save_mapping_set("customer-master", [])
    second = persistence_service.save_mapping_set("customer-master", [])

    assert first.version == 1
    assert second.version == 2


def test_mapping_set_diff_reports_added_removed_and_changed_decisions() -> None:
    baseline = persistence_service.save_mapping_set(
        "customer-master",
        [
            {"source": "cust_id", "target": "customer_id", "status": "accepted"},
            {"source": "phone", "target": "phone_number", "status": "needs_review"},
            {
                "source": "email",
                "target": "email_address",
                "status": "accepted",
                "transformation_code": 'df_target["email_address"] = df_source["email"].str.lower()',
            },
        ],
    )
    current = persistence_service.save_mapping_set(
        "customer-master",
        [
            {"source": "cust_id", "target": "customer_number", "status": "accepted"},
            {
                "source": "email",
                "target": "email_address",
                "status": "accepted",
                "transformation_code": 'df_target["email_address"] = df_source["email"].astype(str).str.strip().str.lower()',
            },
            {"source": "city", "target": "city_name", "status": "accepted"},
        ],
    )

    diff = persistence_service.diff_mapping_sets(current.mapping_set_id, baseline.mapping_set_id)

    assert diff.current_version == 2
    assert diff.against_version == 1
    assert diff.added_count == 1
    assert diff.removed_count == 1
    assert diff.changed_count == 2
    assert [change.change_type for change in diff.changes] == ["added", "changed", "changed", "removed"]
    assert diff.changes[0].source == "city"
    assert diff.changes[1].source == "cust_id"
    assert diff.changes[1].from_target == "customer_id"
    assert diff.changes[1].to_target == "customer_number"
    assert diff.changes[2].source == "email"
    assert diff.changes[2].from_transformation_code is not None
    assert diff.changes[2].to_transformation_code is not None
    assert diff.changes[3].source == "phone"


def test_settings_can_be_loaded_from_dotenv_file() -> None:
    dotenv_path = Path(__file__).parent / ".test.env"
    dotenv_path.write_text(
        "SEMANTRA_LLM_PROVIDER=ollama\n"
        "SEMANTRA_LLM_MODEL=gemma3\n"
        "SEMANTRA_SCORING_PROFILE=canonical_first\n"
        'SEMANTRA_SCORING_WEIGHT_OVERRIDES={"knowledge": 0.25, "canonical": 0.2}\n'
        "SEMANTRA_CORS_ORIGINS=http://localhost:3000,http://localhost:5173\n",
        encoding="utf-8",
    )
    previous = (settings.llm_provider, settings.llm_model, settings.scoring_profile, dict(settings.scoring_weight_overrides), list(settings.cors_origins))
    try:
        loaded = reload_settings(dotenv_path)
        assert loaded.llm_provider == "ollama"
        assert loaded.llm_model == "gemma3"
        assert loaded.scoring_profile == "canonical_first"
        assert loaded.scoring_weight_overrides == {"knowledge": 0.25, "canonical": 0.2}
        assert loaded.cors_origins == ["http://localhost:3000", "http://localhost:5173"]
    finally:
        dotenv_path.unlink(missing_ok=True)
        settings.llm_provider, settings.llm_model, settings.scoring_profile, settings.scoring_weight_overrides, settings.cors_origins = previous


def test_benchmark_datasets_roundtrip_through_persistence() -> None:
    saved = persistence_service.save_benchmark_dataset(
        "phone-benchmark",
        [
            {
                "source_columns": [{"name": "cust_ref"}],
                "target_columns": [{"name": "phone_number"}],
                "ground_truth": {"cust_ref": "phone_number"},
            }
        ],
    )

    listed = persistence_service.list_benchmark_datasets()
    loaded_cases = persistence_service.get_benchmark_dataset_cases(saved.dataset_id)

    assert listed[0].name == "phone-benchmark"
    assert listed[0].case_count == 1
    assert loaded_cases[0]["ground_truth"]["cust_ref"] == "phone_number"
    assert listed[0].version == 1


def test_benchmark_dataset_versions_increment_for_same_name() -> None:
    first = persistence_service.save_benchmark_dataset("phone-benchmark", [{"ground_truth": {}}])
    second = persistence_service.save_benchmark_dataset("phone-benchmark", [{"ground_truth": {}}])

    assert first.version == 1
    assert second.version == 2


def test_evaluation_runs_roundtrip_through_persistence() -> None:
    saved = persistence_service.save_evaluation_run(
        dataset_id=1,
        dataset_name="phone-benchmark",
        provider_name="none",
        metrics=EvaluationMetrics(
            total_cases=1,
            total_fields=1,
            correct_matches=1,
            top1_accuracy=1.0,
            accuracy=1.0,
            confidence_by_bucket={"high_confidence": 1.0, "medium_confidence": 0.0, "low_confidence": 0.0},
        ),
    )

    listed = persistence_service.list_evaluation_runs()

    assert saved.run_id >= 1
    assert listed[0].dataset_name == "phone-benchmark"
    assert listed[0].accuracy == 1.0


def test_transformation_test_sets_roundtrip_through_persistence() -> None:
    saved = persistence_service.save_transformation_test_set(
        "customer-name-transform",
        [
            {
                "source": "email",
                "target": "customer_name",
                "status": "accepted",
                "transformation_code": 'df_target["customer_name"] = df_source["email"].str.split("@").str[0].str.replace(".", " ", regex=False).str.title()',
            }
        ],
        [
            TransformationTestCase(
                case_name="email to name",
                source_rows=[{"email": "ana.markovic@example.com"}],
                assertions=[
                    {
                        "target": "customer_name",
                        "expected_status": "validated",
                        "expected_classification": "safe",
                        "expected_warning_codes": [],
                        "expected_output_values": ["Ana Markovic"],
                    }
                ],
            )
        ],
    )

    listed = persistence_service.list_transformation_test_sets()
    loaded = persistence_service.get_transformation_test_set(saved.test_set_id)

    assert listed[0].name == "customer-name-transform"
    assert listed[0].case_count == 1
    assert listed[0].mapping_count == 1
    assert loaded.mapping_decisions[0].target == "customer_name"
    assert loaded.cases[0].case_name == "email to name"


def test_transformation_test_set_versions_increment_for_same_name() -> None:
    first = persistence_service.save_transformation_test_set("customer-name-transform", [], [])
    second = persistence_service.save_transformation_test_set("customer-name-transform", [], [])

    assert first.version == 1
    assert second.version == 2


def test_knowledge_overlay_versions_and_entries_roundtrip_through_persistence() -> None:
    version = persistence_service.save_knowledge_overlay_version(
        "customer-knowledge-v1",
        status="validated",
        created_by="qa-user",
        source_filename="knowledge_overlay.csv",
    )
    saved_entries = persistence_service.save_knowledge_overlay_entries(
        version.overlay_id,
        [
            KnowledgeOverlayEntry(
                entry_type="field_alias",
                canonical_term="customer id",
                alias="KUNNR",
                domain="master_data",
                source_system="SAP",
                note="SAP customer number",
                normalized_canonical_term="customer id",
                normalized_alias="kunnr",
            )
        ],
    )

    listed_versions = persistence_service.list_knowledge_overlay_versions()
    loaded_entries = persistence_service.get_knowledge_overlay_entries(version.overlay_id)

    assert listed_versions[0].name == "customer-knowledge-v1"
    assert listed_versions[0].status == "validated"
    assert listed_versions[0].created_by == "qa-user"
    assert saved_entries[0].entry_id is not None
    assert loaded_entries[0].alias == "KUNNR"
    assert loaded_entries[0].normalized_alias == "kunnr"


def test_activate_knowledge_overlay_version_sets_single_active_record() -> None:
    first = persistence_service.save_knowledge_overlay_version("overlay-v1", status="validated")
    second = persistence_service.save_knowledge_overlay_version("overlay-v2", status="validated")

    activated_first = persistence_service.activate_knowledge_overlay_version(first.overlay_id)
    activated_second = persistence_service.activate_knowledge_overlay_version(second.overlay_id)
    listed_versions = persistence_service.list_knowledge_overlay_versions()
    active_version = persistence_service.get_active_knowledge_overlay_version()

    assert activated_first.status == "active"
    assert activated_second.status == "active"
    assert active_version is not None
    assert active_version.overlay_id == second.overlay_id
    assert [version.status for version in listed_versions] == ["validated", "active"]


def test_deactivate_knowledge_overlay_version_returns_to_validated_state() -> None:
    version = persistence_service.save_knowledge_overlay_version("overlay-v1", status="validated")

    persistence_service.activate_knowledge_overlay_version(version.overlay_id)
    deactivated = persistence_service.deactivate_knowledge_overlay_version(version.overlay_id)
    active_version = persistence_service.get_active_knowledge_overlay_version()

    assert deactivated.status == "validated"
    assert active_version is None


def test_rollback_knowledge_overlay_version_reactivates_previous_validated_version() -> None:
    first = persistence_service.save_knowledge_overlay_version("overlay-v1", status="validated")
    second = persistence_service.save_knowledge_overlay_version("overlay-v2", status="validated")

    persistence_service.activate_knowledge_overlay_version(first.overlay_id)
    persistence_service.activate_knowledge_overlay_version(second.overlay_id)
    rolled_back = persistence_service.rollback_knowledge_overlay_version()
    active_version = persistence_service.get_active_knowledge_overlay_version()

    assert rolled_back is not None
    assert rolled_back.overlay_id == first.overlay_id
    assert active_version is not None
    assert active_version.overlay_id == first.overlay_id


def test_knowledge_audit_logs_roundtrip_through_persistence() -> None:
    saved = persistence_service.append_knowledge_audit_log(
        KnowledgeAuditEntry(
            overlay_id=1,
            overlay_name="overlay-v1",
            action="activate",
            message="Activated knowledge overlay 'overlay-v1'.",
            created_at="2026-05-02T10:00:00+00:00",
        )
    )

    listed = persistence_service.list_knowledge_audit_logs()

    assert saved.audit_id is not None
    assert listed[0].action == "activate"
    assert listed[0].overlay_name == "overlay-v1"