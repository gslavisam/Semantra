from __future__ import annotations

import re

from app.models.schema import ColumnProfile, SchemaProfile
from app.utils.normalization import normalize_name, tokenize_name


CREATE_TABLE_START_RE = re.compile(
    r"create\s+table\s+(?:if\s+not\s+exists\s+)?([\w\[\]`\"]+(?:\.[\w\[\]`\"]+)?)\s*\(",
    re.IGNORECASE,
)
CONSTRAINT_PREFIXES = ("primary key", "foreign key", "constraint", "unique", "check", "index", "key")


def build_schema_profile_from_sql_snapshot(
    sql_text: str,
    dataset_id: str,
    dataset_name: str,
    selected_table: str | None = None,
) -> SchemaProfile:
    table_blocks = extract_create_table_blocks(sql_text)
    if not table_blocks:
        raise ValueError("SQL snapshot must contain at least one CREATE TABLE statement")

    available_tables = [sanitize_identifier(table_name.split(".")[-1]) for table_name, _ in table_blocks]
    if len(table_blocks) > 1 and not selected_table:
        raise ValueError(
            "SQL snapshot contains multiple tables. Provide a table selection. "
            f"Available tables: {', '.join(available_tables)}"
        )

    selected_block = resolve_selected_table_block(table_blocks, selected_table)
    if selected_block is None:
        raise ValueError(
            f"Unknown selected table '{selected_table}'. Available tables: {', '.join(available_tables)}"
        )

    selected_table_name, definition_block = selected_block
    columns = build_columns_from_table_block(definition_block)

    if not columns:
        raise ValueError(f"SQL snapshot table '{selected_table_name}' did not contain any column definitions")

    return SchemaProfile(dataset_id=dataset_id, dataset_name=dataset_name, row_count=0, columns=columns)


def list_tables_from_sql_snapshot(sql_text: str) -> list[str]:
    table_blocks = extract_create_table_blocks(sql_text)
    if not table_blocks:
        raise ValueError("SQL snapshot must contain at least one CREATE TABLE statement")
    return [sanitize_identifier(table_name.split(".")[-1]) for table_name, _ in table_blocks]


def resolve_selected_table_block(
    table_blocks: list[tuple[str, str]], selected_table: str | None
) -> tuple[str, str] | None:
    if len(table_blocks) == 1 and not selected_table:
        return table_blocks[0]

    requested = sanitize_identifier((selected_table or "").split(".")[-1]).lower()
    for table_name, definition_block in table_blocks:
        sanitized = sanitize_identifier(table_name.split(".")[-1])
        if sanitized.lower() == requested:
            return sanitized, definition_block
    return None


def build_columns_from_table_block(definition_block: str) -> list[ColumnProfile]:
    columns: list[ColumnProfile] = []
    for raw_definition in split_sql_definitions(definition_block):
        definition = raw_definition.strip()
        if not definition:
            continue
        lowered = definition.lower()
        if lowered.startswith(CONSTRAINT_PREFIXES):
            continue
        column = parse_column_definition(definition)
        if column is not None:
            columns.append(column)
    return columns


def extract_create_table_blocks(sql_text: str) -> list[tuple[str, str]]:
    blocks: list[tuple[str, str]] = []
    for match in CREATE_TABLE_START_RE.finditer(sql_text):
        table_name = match.group(1)
        block_start = match.end()
        depth = 1
        index = block_start
        while index < len(sql_text) and depth > 0:
            char = sql_text[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            index += 1
        if depth != 0:
            raise ValueError(f"Unbalanced parentheses in CREATE TABLE statement for {table_name}")
        blocks.append((table_name, sql_text[block_start : index - 1]))
    return blocks


def split_sql_definitions(block: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in block:
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        if char == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


def parse_column_definition(definition: str) -> ColumnProfile | None:
    tokens = definition.split()
    if len(tokens) < 2:
        return None

    raw_name = sanitize_identifier(tokens[0])
    dtype = infer_sql_dtype(definition)
    column_name = raw_name
    detected_patterns = [] if dtype != "object" else ["empty"]
    if dtype == "integer":
        detected_patterns = ["integer", "numeric_id"]
    elif dtype == "float":
        detected_patterns = ["float"]
    elif dtype == "date":
        detected_patterns = ["date"]

    return ColumnProfile(
        name=column_name,
        normalized_name=normalize_name(column_name),
        dtype=dtype,
        null_ratio=0.0,
        unique_ratio=0.0,
        avg_length=0.0,
        non_null_count=0,
        sample_values=[],
        distinct_sample_values=[],
        detected_patterns=detected_patterns,
        tokenized_name=tokenize_name(column_name),
    )


def infer_sql_dtype(definition: str) -> str:
    lowered = definition.lower()
    if any(token in lowered for token in ("bigint", "int", "smallint", "serial")):
        return "integer"
    if any(token in lowered for token in ("decimal", "numeric", "float", "double", "real")):
        return "float"
    if "date" in lowered or "time" in lowered:
        return "date"
    return "object"


def sanitize_identifier(identifier: str) -> str:
    return identifier.strip().strip('"').strip("`").strip("[]")