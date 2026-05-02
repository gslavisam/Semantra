from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from app.core.config import reload_settings, settings
from app.models.knowledge import KnowledgeAuditEntry, KnowledgeOverlayEntry
from app.models.mapping import DecisionLogEntry, EvaluationMetrics, ReusableCorrectionRule, TransformationTestCase, UserCorrectionEntry
from app.services.correction_service import correction_store
from app.services.decision_log_service import decision_log_store
from app.services.llm_service import OllamaProvider, OpenAIResponsesProvider, build_provider_from_settings
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


def setup_function() -> None:
    decision_log_store.clear()
    correction_store.clear()
    correction_store.clear_reusable_rules()
    persistence_service.clear_mapping_sets()
    persistence_service.clear_benchmark_datasets()
    persistence_service.clear_evaluation_runs()
    persistence_service.clear_transformation_test_sets()
    persistence_service.clear_knowledge_overlays()


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
    settings.lmstudio_base_url = "http://127.0.0.1:1234/v1/responses"
    settings.openai_api_key = "should-not-be-used"
    try:
        provider = build_provider_from_settings()

        assert isinstance(provider, OpenAIResponsesProvider)
        assert provider.base_url == "http://127.0.0.1:1234/v1/responses"
        assert provider.api_key == ""
    finally:
        settings.llm_provider, settings.llm_model, settings.lmstudio_base_url, settings.openai_api_key = previous


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
    assert correction_store.list_entries()[0].corrected_target == "phone_number"
    assert correction_store.list_entries()[0].status == "overridden"
    assert correction_store.list_entries()[0].version == 1
    assert correction_store.list_entries()[0].correction_id is not None


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
        created_by="qa-user",
        note="Initial draft",
    )
    updated = persistence_service.update_mapping_set_status(saved.mapping_set_id, "review")
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

    assert saved.version == 1
    assert updated.status == "review"
    assert listed[0].name == "customer-master"
    assert loaded.mapping_decisions[0].target == "customer_id"
    assert audit.audit_id is not None
    assert audits[0].action == "status_change"


def test_mapping_set_versions_increment_for_same_name() -> None:
    first = persistence_service.save_mapping_set("customer-master", [])
    second = persistence_service.save_mapping_set("customer-master", [])

    assert first.version == 1
    assert second.version == 2


def test_settings_can_be_loaded_from_dotenv_file() -> None:
    dotenv_path = Path(__file__).parent / ".test.env"
    dotenv_path.write_text(
        "SEMANTRA_LLM_PROVIDER=ollama\n"
        "SEMANTRA_LLM_MODEL=gemma3\n"
        "SEMANTRA_CORS_ORIGINS=http://localhost:3000,http://localhost:5173\n",
        encoding="utf-8",
    )
    previous = (settings.llm_provider, settings.llm_model, list(settings.cors_origins))
    try:
        loaded = reload_settings(dotenv_path)
        assert loaded.llm_provider == "ollama"
        assert loaded.llm_model == "gemma3"
        assert loaded.cors_origins == ["http://localhost:3000", "http://localhost:5173"]
    finally:
        dotenv_path.unlink(missing_ok=True)
        settings.llm_provider, settings.llm_model, settings.cors_origins = previous


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