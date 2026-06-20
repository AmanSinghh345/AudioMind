from audiomind.config import Settings
from audiomind.services import get_services


def make_services(tmp_path):
    settings = Settings(
        data_dir=tmp_path,
        chunk_size=300,
        chunk_overlap=50,
        retrieval_candidates=6,
        retrieval_top_k=3,
        embedding_model="unavailable-test-model",
    )
    services = get_services(settings)
    services.embeddings._semantic_unavailable = True
    return services


def test_ingest_retrieve_cite_and_deduplicate(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    services = make_services(tmp_path)
    collection_id = services.repository.create_collection("OS")
    content = (
        b"DEADLOCKS\n\nA deadlock occurs when processes wait forever for resources held by each other. "
        b"The four necessary conditions include mutual exclusion, hold and wait, no preemption, and circular wait."
    )
    first = services.ingestion.ingest_bytes(collection_id, "notes.txt", content)
    second = services.ingestion.ingest_bytes(collection_id, "notes.txt", content)
    assert first["chunk_count"] >= 1
    assert second["deduplicated"] is True

    answer = services.rag.ask(collection_id, "What are the necessary deadlock conditions?")
    assert answer.sources
    assert answer.sources[0].filename == "notes.txt"
    assert answer.sources[0].page_number == 1
    assert "[1]" in answer.answer


def test_document_change_replaces_vectors(tmp_path):
    services = make_services(tmp_path)
    collection_id = services.repository.create_collection("DBMS")
    first = services.ingestion.ingest_bytes(collection_id, "unit.txt", b"Normalization reduces redundancy.")
    second = services.ingestion.ingest_bytes(collection_id, "unit.txt", b"Transactions use atomicity and isolation.")
    assert first["id"] != second["id"]
    documents = services.repository.list_documents(collection_id)
    assert len(documents) == 1
    assert documents[0]["id"] == second["id"]


def test_csv_ingestion(tmp_path):
    services = make_services(tmp_path)
    collection_id = services.repository.create_collection("Marks")
    result = services.ingestion.ingest_bytes(
        collection_id, "scores.csv", b"student,topic,score\nAsha,Deadlocks,91"
    )
    chunks = services.repository.get_document_chunks(result["id"])
    assert "Asha | Deadlocks | 91" in chunks[0]["text"]
