from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace


STREAMLIT_APP_PATH = Path(__file__).resolve().parents[1] / "streamlit_app.py"


def load_streamlit_functions(*function_names: str):
    source = STREAMLIT_APP_PATH.read_text(encoding="utf-8")
    module = ast.parse(source, filename=str(STREAMLIT_APP_PATH))
    selected_nodes = [
        node for node in module.body if isinstance(node, ast.FunctionDef) and node.name in function_names
    ]
    fake_streamlit = SimpleNamespace(session_state={})
    namespace = {"st": fake_streamlit}
    exec(compile(ast.Module(body=selected_nodes, type_ignores=[]), str(STREAMLIT_APP_PATH), "exec"), namespace)
    return fake_streamlit, [namespace[name] for name in function_names]


def test_resolve_suggested_transformation_code_drops_stale_code_after_target_change() -> None:
    _, [resolve_suggested_transformation_code] = load_streamlit_functions("resolve_suggested_transformation_code")

    resolved = resolve_suggested_transformation_code(
        {
            "target": "full_name",
            "suggested_target": "customer_name",
            "suggested_transformation_code": 'df_source["email"].str.title()',
        },
        'df_source["email"]',
    )

    assert resolved == ""


def test_build_mapping_decisions_excludes_stale_suggested_transformation_code() -> None:
    fake_streamlit, functions = load_streamlit_functions(
        "resolve_suggested_transformation_code",
        "effective_transformation_code",
        "build_mapping_decisions",
    )
    build_mapping_decisions = functions[-1]

    fake_streamlit.session_state.update(
        {
            "mapping_editor_state": {
                "email": {
                    "target": "full_name",
                    "status": "accepted",
                    "suggested_target": "customer_name",
                    "suggested_transformation_code": 'df_source["email"].str.split("@").str[0].str.title()',
                }
            },
            "transform_email": True,
            "manual_transform_email": "",
            "manual_apply_email": False,
        }
    )

    assert build_mapping_decisions() == [
        {
            "source": "email",
            "target": "full_name",
            "status": "accepted",
        }
    ]


def test_build_mapping_decisions_keeps_suggested_transformation_for_original_target() -> None:
    fake_streamlit, functions = load_streamlit_functions(
        "resolve_suggested_transformation_code",
        "effective_transformation_code",
        "build_mapping_decisions",
    )
    build_mapping_decisions = functions[-1]

    fake_streamlit.session_state.update(
        {
            "mapping_editor_state": {
                "email": {
                    "target": "customer_name",
                    "status": "accepted",
                    "suggested_target": "customer_name",
                    "suggested_transformation_code": 'df_source["email"].str.split("@").str[0].str.title()',
                }
            },
            "transform_email": True,
            "manual_transform_email": "",
            "manual_apply_email": False,
        }
    )

    assert build_mapping_decisions() == [
        {
            "source": "email",
            "target": "customer_name",
            "status": "accepted",
            "transformation_code": 'df_source["email"].str.split("@").str[0].str.title()',
        }
    ]


def test_trust_layer_rows_preserves_selected_candidate_signals() -> None:
    fake_streamlit, functions = load_streamlit_functions(
        "suggested_mapping_by_source",
        "resolve_suggested_transformation_code",
        "effective_transformation_code",
        "transformation_mode",
        "trust_layer_rows",
    )
    trust_layer_rows = functions[-1]

    fake_streamlit.session_state.update({"mapping_editor_state": {}})

    mapping_response = {
        "mappings": [
            {
                "source": "KUNNR",
                "target": "customer_id",
                "confidence": 0.94,
                "explanation": ["Internal metadata dictionary aligns both fields to concept 'Customer ID'."],
                "signals": {"knowledge": 1.0, "pattern": 1.0, "semantic": 0.9},
            }
        ],
        "ranked_mappings": [
            {
                "source": "KUNNR",
                "candidates": [
                    {
                        "target": "customer_id",
                        "confidence": 0.94,
                        "explanation": ["Internal metadata dictionary aligns both fields to concept 'Customer ID'."],
                        "signals": {"knowledge": 1.0, "pattern": 1.0, "semantic": 0.9},
                    }
                ],
            }
        ],
    }

    rows = trust_layer_rows(mapping_response)

    assert rows[0]["signals"]["knowledge"] == 1.0
    assert rows[0]["signals"]["pattern"] == 1.0


def test_has_knowledge_match_uses_signal_when_present() -> None:
    _, [has_knowledge_match] = load_streamlit_functions("has_knowledge_match")

    assert has_knowledge_match({"knowledge": 1.0}, None) is True
    assert has_knowledge_match({"knowledge": 0.0}, None) is False


def test_has_knowledge_match_falls_back_to_explanation_text() -> None:
    _, [has_knowledge_match] = load_streamlit_functions("has_knowledge_match")

    assert has_knowledge_match(
        {},
        ["Context prior: source SAP KNA1.KUNNR aligns with target Workday Customer.Customer_ID."],
    ) is True
    assert has_knowledge_match({}, ["Pattern similarity is strong."]) is False