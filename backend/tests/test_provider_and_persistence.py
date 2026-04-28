from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from app.core.config import reload_settings, settings
from app.models.mapping import DecisionLogEntry, EvaluationMetrics, UserCorrectionEntry
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


def setup_function() -> None:
    decision_log_store.clear()
    correction_store.clear()
    persistence_service.clear_benchmark_datasets()
    persistence_service.clear_evaluation_runs()


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
    assert correction_store.list_entries()[0].version == 1
    assert correction_store.list_entries()[0].correction_id is not None


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