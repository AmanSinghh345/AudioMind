from audiomind.repository import Repository


def test_collection_and_job_lifecycle(tmp_path):
    repository = Repository(tmp_path / "test.db")
    collection_id = repository.create_collection("Operating Systems")
    assert repository.get_collection_by_name("Operating Systems")["id"] == collection_id

    job_id = repository.create_job("test", {"value": 1})
    repository.update_job(job_id, "completed", 100, result={"ok": True})
    job = repository.get_job(job_id)
    assert job["payload"] == {"value": 1}
    assert job["result"] == {"ok": True}
    assert job["status"] == "completed"
