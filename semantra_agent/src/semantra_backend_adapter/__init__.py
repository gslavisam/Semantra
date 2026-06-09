"""Semantra Backend Adapter.

Exposes the existing Semantra FastAPI/Streamlit backend as concrete
implementations of the `semantra_core.services.protocols` contracts.

Typical usage:

    from semantra_backend_adapter import create_backend_adapters
    adapters = create_backend_adapters()
    engine = adapters["engine"]
    candidates = engine.map_source_to_target(source, target)
"""

from .context import BackendContext, create_default_context
from .factory import create_backend_adapters
from .mapping import BackendAsyncMappingEngine, BackendMappingEngine
from .knowledge import BackendKnowledgeBase
from .llm import BackendLLMService
from .connector import BackendConnector

__version__ = "0.1.0"

__all__ = [
    # Context
    "BackendContext",
    "create_default_context",
    # Factory
    "create_backend_adapters",
    # Adapters
    "BackendAsyncMappingEngine",
    "BackendMappingEngine",
    "BackendKnowledgeBase",
    "BackendLLMService",
    "BackendConnector",
]
