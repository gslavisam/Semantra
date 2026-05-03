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


def test_build_pending_corrections_includes_rejected_review_decision() -> None:
    fake_streamlit, [build_pending_corrections] = load_streamlit_functions("build_pending_corrections")

    fake_streamlit.session_state.update(
        {
            "mapping_editor_state": {
                "cust_ref": {
                    "target": "customer_id",
                    "suggested_target": "customer_id",
                    "status": "rejected",
                }
            }
        }
    )

    assert build_pending_corrections() == [
        {
            "source": "cust_ref",
            "suggested_target": "customer_id",
            "corrected_target": None,
            "status": "rejected",
        }
    ]


def test_materialize_transformation_template_replaces_source_and_target_placeholders() -> None:
    _, [materialize_transformation_template] = load_streamlit_functions("materialize_transformation_template")

    rendered = materialize_transformation_template(
        {
            "code_template": 'df_target["{target}"] = df_source["{source}"].astype(str).str.strip()'
        },
        "legacy_name",
        "customer_name",
    )

    assert rendered == 'df_target["customer_name"] = df_source["legacy_name"].astype(str).str.strip()'


def test_trust_layer_rows_preserves_selected_candidate_signals() -> None:
    fake_streamlit, functions = load_streamlit_functions(
        "suggested_mapping_by_source",
        "resolve_suggested_transformation_code",
        "effective_transformation_code",
        "transformation_mode",
        "canonical_concept_labels",
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
                        "canonical_details": {
                            "shared_concepts": [
                                {"concept_id": "customer.id", "display_name": "Customer ID", "strength": 1.0}
                            ]
                        },
                        "signals": {"knowledge": 1.0, "pattern": 1.0, "semantic": 0.9},
                    }
                ],
            }
        ],
    }

    rows = trust_layer_rows(mapping_response)

    assert rows[0]["signals"]["knowledge"] == 1.0
    assert rows[0]["signals"]["pattern"] == 1.0
    assert rows[0]["canonical_details"]["shared_concepts"][0]["concept_id"] == "customer.id"


def test_canonical_concept_labels_prefers_shared_concepts() -> None:
    _, [canonical_concept_labels] = load_streamlit_functions("canonical_concept_labels")

    labels = canonical_concept_labels(
        {
            "source_concepts": [{"concept_id": "customer.id", "display_name": "Customer ID"}],
            "target_concepts": [{"concept_id": "customer.id", "display_name": "Customer ID"}],
            "shared_concepts": [{"concept_id": "customer.id", "display_name": "Customer ID"}],
        }
    )

    assert labels == ["Customer ID (customer.id)"]


def test_canonical_path_label_formats_source_concept_target() -> None:
    _, functions = load_streamlit_functions("canonical_concept_labels", "canonical_path_label")
    canonical_path_label = functions[-1]

    label = canonical_path_label(
        "sold_to_party",
        "customer_id",
        {
            "shared_concepts": [{"concept_id": "customer.id", "display_name": "Customer ID"}],
        },
    )

    assert label == "sold_to_party -> Customer ID (customer.id) -> customer_id"


def test_current_mapping_rows_includes_canonical_path_for_selected_candidate() -> None:
    fake_streamlit, functions = load_streamlit_functions(
        "suggested_mapping_by_source",
        "validator_badge",
        "canonical_concept_labels",
        "canonical_path_label",
        "current_mapping_rows",
    )
    current_mapping_rows = functions[-1]

    fake_streamlit.session_state.update({"mapping_editor_state": {}})

    rows = current_mapping_rows(
        {
            "mappings": [
                {
                    "source": "sold_to_party",
                    "target": "customer_id",
                    "confidence": 0.94,
                    "confidence_label": "high_confidence",
                    "status": "accepted",
                    "method": "multi_signal_heuristic",
                    "canonical_details": {
                        "shared_concepts": [
                            {"concept_id": "customer.id", "display_name": "Customer ID", "strength": 1.0}
                        ]
                    },
                }
            ],
            "ranked_mappings": [
                {
                    "source": "sold_to_party",
                    "candidates": [
                        {
                            "target": "customer_id",
                            "confidence": 0.94,
                            "confidence_label": "high_confidence",
                            "method": "multi_signal_heuristic",
                            "canonical_details": {
                                "shared_concepts": [
                                    {"concept_id": "customer.id", "display_name": "Customer ID", "strength": 1.0}
                                ]
                            },
                        }
                    ],
                }
            ],
        }
    )

    assert rows[0]["canonical_path"] == "sold_to_party -> Customer ID (customer.id) -> customer_id"


def test_canonical_concept_groups_group_selected_mappings_by_shared_concept() -> None:
    fake_streamlit, functions = load_streamlit_functions(
        "suggested_mapping_by_source",
        "canonical_concept_labels",
        "canonical_path_label",
        "canonical_concept_groups",
    )
    canonical_concept_groups = functions[-1]

    fake_streamlit.session_state.update({"mapping_editor_state": {}})

    groups = canonical_concept_groups(
        {
            "mappings": [
                {
                    "source": "sold_to_party",
                    "target": "customer_id",
                    "canonical_details": {
                        "shared_concepts": [
                            {"concept_id": "customer.id", "display_name": "Customer ID", "strength": 1.0}
                        ]
                    },
                },
                {
                    "source": "ship_to_party",
                    "target": "customer_id",
                    "canonical_details": {
                        "shared_concepts": [
                            {"concept_id": "customer.id", "display_name": "Customer ID", "strength": 0.9}
                        ]
                    },
                },
                {
                    "source": "client_mail",
                    "target": "customer_email",
                    "canonical_details": {
                        "shared_concepts": [
                            {"concept_id": "customer.email", "display_name": "Customer Email", "strength": 1.0}
                        ]
                    },
                },
            ],
            "ranked_mappings": [
                {
                    "source": "sold_to_party",
                    "candidates": [
                        {
                            "target": "customer_id",
                            "canonical_details": {
                                "shared_concepts": [
                                    {"concept_id": "customer.id", "display_name": "Customer ID", "strength": 1.0}
                                ]
                            },
                        }
                    ],
                },
                {
                    "source": "ship_to_party",
                    "candidates": [
                        {
                            "target": "customer_id",
                            "canonical_details": {
                                "shared_concepts": [
                                    {"concept_id": "customer.id", "display_name": "Customer ID", "strength": 0.9}
                                ]
                            },
                        }
                    ],
                },
                {
                    "source": "client_mail",
                    "candidates": [
                        {
                            "target": "customer_email",
                            "canonical_details": {
                                "shared_concepts": [
                                    {"concept_id": "customer.email", "display_name": "Customer Email", "strength": 1.0}
                                ]
                            },
                        }
                    ],
                },
            ],
        }
    )

    assert groups == [
        {
            "concept": "Customer Email",
            "concept_id": "customer.email",
            "mapping_count": 1,
            "source_columns": "client_mail",
            "target_columns": "customer_email",
            "canonical_paths": "client_mail -> Customer Email (customer.email) -> customer_email",
        },
        {
            "concept": "Customer ID",
            "concept_id": "customer.id",
            "mapping_count": 2,
            "source_columns": "ship_to_party | sold_to_party",
            "target_columns": "customer_id",
            "canonical_paths": "ship_to_party -> Customer ID (customer.id) -> customer_id | sold_to_party -> Customer ID (customer.id) -> customer_id",
        },
    ]


def test_source_concept_rows_lists_selected_source_to_concept_paths() -> None:
    fake_streamlit, functions = load_streamlit_functions(
        "suggested_mapping_by_source",
        "source_concept_rows",
    )
    source_concept_rows = functions[-1]

    fake_streamlit.session_state.update({"mapping_editor_state": {}})

    rows = source_concept_rows(
        {
            "mappings": [
                {
                    "source": "sold_to_party",
                    "target": "customer_id",
                    "canonical_details": {
                        "shared_concepts": [
                            {"concept_id": "customer.id", "display_name": "Customer ID", "strength": 1.0}
                        ]
                    },
                }
            ],
            "ranked_mappings": [
                {
                    "source": "sold_to_party",
                    "candidates": [
                        {
                            "target": "customer_id",
                            "canonical_details": {
                                "shared_concepts": [
                                    {"concept_id": "customer.id", "display_name": "Customer ID", "strength": 1.0}
                                ]
                            },
                        }
                    ],
                }
            ],
        }
    )

    assert rows == [
        {
            "source": "sold_to_party",
            "concept": "Customer ID",
            "concept_id": "customer.id",
            "target": "customer_id",
            "strength": 1.0,
        }
    ]


def test_concept_target_rows_groups_selected_targets_by_concept() -> None:
    fake_streamlit, functions = load_streamlit_functions(
        "suggested_mapping_by_source",
        "concept_target_rows",
    )
    concept_target_rows = functions[-1]

    fake_streamlit.session_state.update({"mapping_editor_state": {}})

    rows = concept_target_rows(
        {
            "mappings": [
                {
                    "source": "sold_to_party",
                    "target": "customer_id",
                    "canonical_details": {
                        "shared_concepts": [
                            {"concept_id": "customer.id", "display_name": "Customer ID", "strength": 1.0}
                        ]
                    },
                },
                {
                    "source": "ship_to_party",
                    "target": "customer_id",
                    "canonical_details": {
                        "shared_concepts": [
                            {"concept_id": "customer.id", "display_name": "Customer ID", "strength": 0.9}
                        ]
                    },
                },
            ],
            "ranked_mappings": [
                {
                    "source": "sold_to_party",
                    "candidates": [
                        {
                            "target": "customer_id",
                            "canonical_details": {
                                "shared_concepts": [
                                    {"concept_id": "customer.id", "display_name": "Customer ID", "strength": 1.0}
                                ]
                            },
                        }
                    ],
                },
                {
                    "source": "ship_to_party",
                    "candidates": [
                        {
                            "target": "customer_id",
                            "canonical_details": {
                                "shared_concepts": [
                                    {"concept_id": "customer.id", "display_name": "Customer ID", "strength": 0.9}
                                ]
                            },
                        }
                    ],
                },
            ],
        }
    )

    assert rows == [
        {
            "concept": "Customer ID",
            "concept_id": "customer.id",
            "target": "customer_id",
            "source_columns": "ship_to_party | sold_to_party",
            "mapping_count": 2,
        }
    ]


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


def test_has_canonical_match_uses_signal_when_present() -> None:
    _, [has_canonical_match] = load_streamlit_functions("has_canonical_match")

    assert has_canonical_match({"canonical": 1.0}, None) is True
    assert has_canonical_match({"canonical": 0.0}, None) is False


def test_has_canonical_match_falls_back_to_explanation_text() -> None:
    _, [has_canonical_match] = load_streamlit_functions("has_canonical_match")

    assert has_canonical_match(
        {},
        ["Canonical glossary aligns both fields to business concept 'Customer ID' (customer.id)."],
    ) is True
    assert has_canonical_match({}, ["Pattern similarity is strong."]) is False


def test_canonical_explanation_lines_extracts_only_canonical_messages() -> None:
    _, [canonical_explanation_lines] = load_streamlit_functions("canonical_explanation_lines")

    lines = canonical_explanation_lines(
        [
            "Canonical glossary aligns both fields to business concept 'Customer ID' (customer.id).",
            "Field names are lexically very similar.",
        ]
    )

    assert lines == ["Canonical glossary aligns both fields to business concept 'Customer ID' (customer.id)."]


def test_build_mapping_set_payload_uses_current_dataset_ids_and_decisions() -> None:
    fake_streamlit, functions = load_streamlit_functions(
        "resolve_suggested_transformation_code",
        "effective_transformation_code",
        "build_mapping_decisions",
        "build_mapping_set_payload",
    )
    build_mapping_set_payload = functions[-1]

    fake_streamlit.session_state.update(
        {
            "upload_response": {
                "source": {"dataset_id": "source-1"},
                "target": {"dataset_id": "target-1"},
            },
            "mapping_editor_state": {
                "cust_id": {"target": "customer_id", "status": "accepted"},
            },
            "manual_transform_cust_id": "",
            "manual_apply_cust_id": False,
        }
    )

    payload = build_mapping_set_payload(
        "customer-master",
        "ba-user",
        "Initial draft",
        "governance-team",
        "analyst-1",
        "Ready for review",
    )

    assert payload == {
        "name": "customer-master",
        "source_dataset_id": "source-1",
        "target_dataset_id": "target-1",
        "mapping_decisions": [{"source": "cust_id", "target": "customer_id", "status": "accepted"}],
        "created_by": "ba-user",
        "note": "Initial draft",
        "owner": "governance-team",
        "assignee": "analyst-1",
        "review_note": "Ready for review",
    }