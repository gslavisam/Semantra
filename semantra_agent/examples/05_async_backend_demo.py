"""Async backend demo for Semantra Agent.

This example shows how to build a LangChain tool set using the backend's
async mapping engine, so the mapping call can be dispatched without
blocking the event loop.
"""

from semantra_core.models.schema import DatasetHandle, SchemaProfile, ColumnProfile

try:
    from semantra_backend_adapter import create_backend_adapters
    from semantra_agent.langchain_tools import build_semantra_tools
except ImportError as exc:
    raise RuntimeError(
        "Please install the SDK extras: pip install -e '.[langchain]' "
        "and ensure the backend adapter is importable."
    ) from exc

# Build a tiny source/target pair.
source = DatasetHandle(
    dataset_id="src",
    dataset_name="customer_src",
    schema_profile=SchemaProfile(
        dataset_id="src",
        dataset_name="customer_src",
        row_count=10,
        columns=[
            ColumnProfile(
                name="cust_id",
                normalized_name="cust_id",
                dtype="str",
                null_ratio=0.0,
                unique_ratio=1.0,
                non_null_count=10,
            )
        ],
    ),
)
target = SchemaProfile(
    dataset_id="tgt",
    dataset_name="customer_tgt",
    row_count=0,
    columns=[
        ColumnProfile(
            name="customer_key",
            normalized_name="customer_key",
            dtype="str",
            null_ratio=0.0,
            unique_ratio=0.0,
            non_null_count=0,
        )
    ],
)

# Create backend adapters with async engine support.
adapters = create_backend_adapters(include_async_engine=True)

# Build LangChain tools with the async engine.
tools = build_semantra_tools(async_engine=adapters["async_engine"], llm=adapters["llm"])

print("Created LangChain tools:", [tool.name for tool in tools])

# Example call to the async validate tool, if you want to run it directly.
for tool in tools:
    if tool.name == "semantra_validate_mapping":
        result = tool._run(
            source_field="cust_id",
            candidate_targets=["customer_key", "customer_id"],
            context={"description": "customer identifier mapping"},
        )
        print("Validate mapping result:", result)
        break
else:
    print("No validate mapping tool available in the current tool set.")
