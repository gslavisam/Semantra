"""Factory for instantiating all backend adapters together."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .context import BackendContext, create_default_context
from .mapping import BackendAsyncMappingEngine, BackendMappingEngine
from .knowledge import BackendKnowledgeBase
from .llm import BackendLLMService
from .connector import BackendConnector


def create_backend_adapters(
    context: Optional[BackendContext] = None,
    dataset_id: Optional[str] = None,
    include_async_engine: bool = False,
) -> Dict[str, Any]:
    """Build the four backend adapters and return them in a dict.

    Args:
        context: A pre-built `BackendContext`. If None, calls
            `create_default_context()` which will raise if the backend
            package is not importable.
        dataset_id: Optional dataset id to bind to the connector. If
            omitted, the connector is not created and the dict will not
            contain a `"connector"` key.

    Returns:
        A dict with keys: `"engine"`, `"knowledge"`, `"llm"`, and
        optionally `"connector"` and `"async_engine"`.
    """
    if context is None:
        context = create_default_context()

    adapters: Dict[str, Any] = {
        "engine": BackendMappingEngine(context=context),
        "knowledge": BackendKnowledgeBase(context=context),
        "llm": BackendLLMService(context=context),
    }
    if include_async_engine:
        adapters["async_engine"] = BackendAsyncMappingEngine(context=context)
    if dataset_id is not None:
        adapters["connector"] = BackendConnector(dataset_id=dataset_id, context=context)
    return adapters
