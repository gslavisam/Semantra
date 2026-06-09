"""Semantra Core SDK: reusable Pydantic models and service protocols.

This package provides the building blocks for the Semantra semantic
integration framework. It is intentionally framework-agnostic and has no
dependencies on FastAPI, Streamlit, or any specific persistence layer.
"""

from .models import schema, mapping, knowledge
from .services import (
    Connector,
    AsyncConnector,
    DecisionStore,
    InMemoryDecisionStore,
    InMemoryKnowledgeBase,
    InMemoryMappingEngine,
    InMemoryReportService,
    InMemoryReviewService,
    BoundedLLMService,
    KnowledgeBase,
    LLMService,
    AsyncLLMService,
    MappingEngine,
    AsyncMappingEngine,
    ReportService,
    ReviewService,
    StaticConnector,
)

__version__ = "0.1.0"

__all__ = [
    # Data models
    "schema",
    "mapping",
    "knowledge",
    # Service protocols
    "MappingEngine",
    "AsyncMappingEngine",
    "KnowledgeBase",
    "LLMService",
    "AsyncLLMService",
    "Connector",
    "AsyncConnector",
    "ReviewService",
    "DecisionStore",
    "ReportService",
    # Reference implementations
    "InMemoryMappingEngine",
    "InMemoryKnowledgeBase",
    "BoundedLLMService",
    "StaticConnector",
    "InMemoryReviewService",
    "InMemoryDecisionStore",
    "InMemoryReportService",
]
