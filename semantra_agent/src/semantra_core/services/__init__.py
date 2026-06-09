"""Service layer for the Semantra core SDK.

This package exposes:
- `protocols`: abstract contracts that any Semantra service must implement.
- `implementations`: minimal reference implementations for testing and examples.
"""

from .protocols import (
    Connector,
    DecisionStore,
    KnowledgeBase,
    LLMService,
    AsyncLLMService,
    MappingEngine,
    AsyncMappingEngine,
    ReportService,
    ReviewService,
    AsyncConnector,
)
from .implementations import (
    BoundedLLMService,
    InMemoryDecisionStore,
    InMemoryKnowledgeBase,
    InMemoryMappingEngine,
    InMemoryReportService,
    InMemoryReviewService,
    StaticConnector,
)

__all__ = [
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
    "InMemoryMappingEngine",
    "InMemoryKnowledgeBase",
    "BoundedLLMService",
    "StaticConnector",
    "InMemoryReviewService",
    "InMemoryDecisionStore",
    "InMemoryReportService",
]
