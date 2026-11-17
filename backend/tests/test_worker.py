from app.workers.celery_app import analyze_job, ping


def test_worker_ping_is_not_a_detection():
    result = ping.run()
    assert result == {"service": "trustify-worker", "status": "ok"}
    assert "confidence" not in result


def test_analyze_job_task_name_is_registered():
    assert analyze_job.name == "trustify.analyze_job"
