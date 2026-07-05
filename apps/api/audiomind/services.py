from __future__ import annotations

from dataclasses import dataclass

from .config import Settings, get_settings
from .embeddings import EmbeddingService
from .ingestion import IngestionService
from .narration import NarrationService
from .rag import RAGService
from .repository import Repository
from .vector_store import ChromaVectorStore
from .web_ingestion import WebIngestionService


@dataclass
class ServiceContainer:
    settings: Settings
    repository: Repository
    embeddings: EmbeddingService
    vector_store: ChromaVectorStore
    ingestion: IngestionService
    rag: RAGService
    narration: NarrationService
    web_ingestion: WebIngestionService


_container: ServiceContainer | None = None


def get_services(settings: Settings | None = None) -> ServiceContainer:
    global _container
    if _container is not None and settings is None:
        return _container
    configured = settings or get_settings()
    configured.ensure_directories()
    repository = Repository(configured.database_path)
    embeddings = EmbeddingService(configured.embedding_model)
    vector_store = ChromaVectorStore(configured.vector_path)
    ingestion = IngestionService(configured, repository, embeddings, vector_store)
    container = ServiceContainer(
        settings=configured,
        repository=repository,
        embeddings=embeddings,
        vector_store=vector_store,
        ingestion=ingestion,
        rag=RAGService(configured, repository, embeddings, vector_store),
        narration=NarrationService(repository),
        web_ingestion=WebIngestionService(ingestion),
    )
    if settings is None:
        _container = container
    return container
