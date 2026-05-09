from streamlit_ui.workspace_views import should_show_table_selector


def test_should_show_table_selector_for_multitable_sql_snapshot() -> None:
    assert should_show_table_selector(["customers", "contacts"], "data", is_sql=True) is True


def test_should_not_show_table_selector_for_schema_spec_without_sql() -> None:
    assert should_show_table_selector(["customers", "contacts"], "Schema spec", is_sql=False) is False