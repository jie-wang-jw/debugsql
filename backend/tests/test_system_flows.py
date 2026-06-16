from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.database import Base, get_engine, get_session_factory
from app.demo_pipeline import (
    PLAN_RUN_STORE,
    PLAN_STORE,
    RUN_OWNER_STORE,
    RUN_STORE,
    create_plan_run,
    generate_plan_for_message,
    get_execution_result,
    get_plan_graph,
    merge_plan_nodes,
    run_demo_execution,
    step_plan_run,
    update_plan_node,
)
from app.models.auth import User
from app.models.history import Conversation, Message
from app.persistence import persist_query_plan
from app.persistence import persist_execution_run


@pytest.fixture(autouse=True)
def isolated_sqlite(monkeypatch, tmp_path):
    db_path = tmp_path / "debugsql-test.sqlite"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("DEBUGSQL_AUTO_LOGIN", "1")
    monkeypatch.setenv("EMAIL_DEV_LOG_CODES", "1")
    monkeypatch.setenv("NL2IR_PROVIDER", "stub")
    monkeypatch.setenv("IR_TO_PLAN_PROVIDER", "internal")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    PLAN_STORE.clear()
    RUN_STORE.clear()
    RUN_OWNER_STORE.clear()
    PLAN_RUN_STORE.clear()

    import app.models.auth  # noqa: F401
    import app.models.history  # noqa: F401

    Base.metadata.create_all(get_engine())
    yield
    PLAN_STORE.clear()
    RUN_STORE.clear()
    RUN_OWNER_STORE.clear()
    PLAN_RUN_STORE.clear()
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


def _client() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_email_login_logout_cookie_lifecycle(monkeypatch) -> None:
    monkeypatch.setenv("DEBUGSQL_AUTO_LOGIN", "0")
    get_settings.cache_clear()

    import app.auth_routes as auth_routes

    monkeypatch.setattr(auth_routes.secrets, "randbelow", lambda _upper: 123456)
    monkeypatch.setattr(auth_routes, "send_login_code", lambda email, code: {"delivery": "logged"})

    client = _client()
    response = client.post("/auth/email/request-code", json={"email": "student@example.com"})
    assert response.status_code == 200

    response = client.post("/auth/email/verify-code", json={"email": "student@example.com", "code": "123456"})
    assert response.status_code == 200
    assert response.json()["data"]["email"] == "student@example.com"
    assert response.json()["data"]["isAdmin"] is False
    assert client.get("/auth/me").status_code == 200

    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").status_code == 401


def test_admin_history_requires_admin_and_can_view_all_users() -> None:
    client = _client()
    user_response = client.get("/auth/me")
    assert user_response.status_code == 200
    current_user = user_response.json()["data"]
    assert current_user["isAdmin"] is False

    with get_session_factory()() as session:
        other_user = User(
            id="user_other_admin_history",
            email="other@example.com",
            display_name="Other User",
            auth_mode="email",
        )
        session.add(other_user)
        session.add(
            Conversation(
                id="conv_other_admin_history",
                user_id=other_user.id,
                session_id="other-admin-history-session",
                title="Other user question",
                dataset_context={"benchmark": "bird", "dbId": "card_games"},
                active_plan_id="plan_other_admin_history",
            )
        )
        session.add(
            Message(
                id="msg_other_admin_history",
                conversation_id="conv_other_admin_history",
                user_id=other_user.id,
                role="user",
                content="show other user history",
                dataset_context={"benchmark": "bird", "dbId": "card_games"},
            )
        )
        session.commit()

    assert client.get("/admin/history/summary").status_code == 403

    with get_session_factory()() as session:
        admin = session.get(User, current_user["id"])
        assert admin is not None
        admin.is_admin = True
        session.commit()

    admin_me = client.get("/auth/me").json()["data"]
    assert admin_me["isAdmin"] is True

    summary_response = client.get("/admin/history/summary")
    assert summary_response.status_code == 200
    summary = summary_response.json()["data"]
    assert any(item["user"]["email"] == "other@example.com" for item in summary["conversations"])

    detail_response = client.get("/admin/history/conversations/conv_other_admin_history")
    assert detail_response.status_code == 200
    detail = detail_response.json()["data"]
    assert detail["user"]["email"] == "other@example.com"
    assert detail["messages"][0]["content"] == "show other user history"

    own_summary = client.get("/history/summary").json()["data"]
    assert all(item["id"] != "conv_other_admin_history" for item in own_summary["conversations"])


def test_history_summary_detail_and_export_are_user_scoped() -> None:
    client = _client()
    query_response = client.post(
        "/query",
        json={
            "message": "how many card games?",
            "sessionId": "pytest-history-session",
            "datasetContext": {"benchmark": "bird", "dbId": "card_games"},
        },
    )
    assert query_response.status_code == 200

    summary = client.get("/history/summary").json()["data"]
    assert summary["conversations"]
    conversation_id = summary["conversations"][0]["id"]

    detail = client.get(f"/history/conversations/{conversation_id}").json()["data"]
    assert detail["messages"][0]["role"] == "user"
    # Tool-assisted chat no longer persists an active query-plan id by default.
    assert "activePlanId" in detail

    exported = client.get("/history/operation-logs/export?format=json").json()["data"]
    assert any(item["operationType"] == "chat_query" for item in exported)

    csv_response = client.get("/history/operation-logs/export?format=csv")
    assert csv_response.status_code == 200
    assert "operationType" in csv_response.text


def test_query_plan_and_execution_restore_from_database() -> None:
    stored = generate_plan_for_message(
        "show cards",
        "pytest-restore-session",
        {"benchmark": "bird", "dbId": "card_games"},
    )
    plan_id = stored["plan"]["plan_id"]
    persist_query_plan(plan_id, "pytest-restore-session")
    execution = run_demo_execution("ignored", "pytest-restore-session", plan_id)
    run_id = execution["runId"]

    assert get_plan_graph(plan_id)
    assert get_execution_result(run_id)
    result_nodes = [
        node
        for node in get_plan_graph(plan_id)["nodes"]
        if node["data"].get("kind") == "data" and node["data"].get("nodeRole") == "result"
    ]
    assert result_nodes[0]["data"]["previewStatus"] == "materialized"

    PLAN_STORE.clear()
    RUN_STORE.clear()

    restored_graph = get_plan_graph(plan_id)
    restored_execution = get_execution_result(run_id)

    assert restored_graph is not None
    assert restored_execution is not None
    assert "columns" in restored_execution


def test_inspector_limit_sort_and_unsupported_edits() -> None:
    stored = generate_plan_for_message("rank stores by revenue in the last 30 days", "pytest-edit-session")
    plan_id = stored["plan"]["plan_id"]

    graph = get_plan_graph(plan_id)
    limit_node = next(node for node in graph["nodes"] if node["id"] == "op_limit")
    limit_data = {**limit_node["data"], "detail": "LIMIT 2"}
    updated = update_plan_node(plan_id, "op_limit", limit_data)
    assert updated["lastEditResult"]["status"] == "regenerated"
    assert "LIMIT 2" in PLAN_STORE[plan_id]["plan"]["executable"]["content"]

    sort_node = next(node for node in updated["nodes"] if node["id"] == "op_sort")
    sort_data = {**sort_node["data"], "detail": "total_sales ASC"}
    updated = update_plan_node(plan_id, "op_sort", sort_data)
    assert updated["lastEditResult"]["status"] == "regenerated"
    assert "ORDER BY total_sales ASC" in PLAN_STORE[plan_id]["plan"]["executable"]["content"]


def test_node_merge_valid_and_invalid_cases() -> None:
    stored = generate_plan_for_message("rank stores by revenue in the last 30 days", "pytest-merge-session")
    plan_id = stored["plan"]["plan_id"]

    valid = merge_plan_nodes(plan_id, ["op_group_by", "op_aggregate"])
    assert valid["lastEditResult"]["status"] == "graph_updated"
    assert valid["lastEditResult"]["mergedNodeIds"] == ["op_group_by", "op_aggregate"]

    invalid = merge_plan_nodes(plan_id, ["intent", "op_sort"])
    assert invalid["lastEditResult"]["status"] == "needs_replan"


def test_step_run_records_non_fake_node_previews() -> None:
    stored = generate_plan_for_message("rank stores by revenue in the last 30 days", "pytest-step-session")
    plan_id = stored["plan"]["plan_id"]
    run = create_plan_run(plan_id)
    assert run is not None

    stepped = step_plan_run(plan_id, run["runId"])
    assert stepped["stepsCompleted"] == 1
    assert stepped["nodePreviews"]

    graph = get_plan_graph(plan_id)
    preview_values = [
        node["data"].get("previewStatus")
        for node in graph["nodes"]
        if node["data"].get("kind") == "data" and node["data"].get("previewStatus")
    ]
    assert preview_values or stepped["nodePreviews"]


def test_evaluation_export_marks_repair_metrics_unavailable() -> None:
    client = _client()
    response = client.post("/evaluation/run", json={"benchmark": "bird", "dbId": "card_games", "limit": 1})
    assert response.status_code == 200
    data = response.json()["data"]
    run_id = data["runId"]
    assert data["summary"]["repairMetricsAvailable"] is False
    assert data["summary"]["debugRecoveryRate"] is None

    exported = client.get(f"/evaluation/runs/{run_id}/export").json()["data"]
    assert exported["runId"] == run_id

    csv_response = client.get(f"/evaluation/runs/{run_id}/export?format=csv")
    assert csv_response.status_code == 200
    assert "firstPassExecutionAccuracy" in csv_response.text


def _materialization_plan(plan_id: str = "plan-materialization") -> str:
    PLAN_STORE[plan_id] = {
        "message": "preview cards",
        "session_id": "pytest-materialization",
        "dataset_context": {"benchmark": "bird", "dbId": "card_games"},
        "ir": {"table": "cards"},
        "plan": {
            "plan_id": plan_id,
            "executable": {"type": "sql", "dialect": "sqlite", "content": "SELECT id, name FROM cards ORDER BY id LIMIT 10"},
            "metadata": {"dataset_context": {"benchmark": "bird", "dbId": "card_games"}},
        },
        "graph": {
            "queryLabel": "preview cards",
            "totalCost": 1,
            "nodes": [
                {"id": "intent", "data": {"kind": "intent", "intentLabel": "preview"}},
                {"id": "op_scan", "data": {"kind": "operation", "operationType": "SCAN", "detail": "table = cards"}},
                {"id": "op_join", "data": {"kind": "operation", "operationType": "JOIN", "detail": "unsupported"}},
                {"id": "op_limit", "data": {"kind": "operation", "operationType": "LIMIT", "detail": "LIMIT 3"}},
                {"id": "data_result", "data": {"kind": "data", "nodeRole": "result", "tableName": "Result"}},
            ],
            "edges": [
                {"source": "intent", "target": "op_scan"},
                {"source": "op_scan", "target": "op_join"},
                {"source": "op_join", "target": "op_limit"},
                {"source": "op_limit", "target": "data_result"},
            ],
        },
        "created_at": 1,
    }
    return plan_id


def test_true_per_node_materialization_scan_limit_unsupported_and_final_result() -> None:
    plan_id = _materialization_plan()
    run = create_plan_run(plan_id)
    assert run is not None

    step_plan_run(plan_id, run["runId"])  # intent
    stepped = step_plan_run(plan_id, run["runId"])  # scan
    scan_preview = stepped["nodePreviews"]["op_scan"]
    assert scan_preview["status"] == "materialized"
    assert scan_preview["fragmentSql"] == "SELECT * FROM cards\nLIMIT 20"
    assert len(scan_preview["rows"]) == 20

    stepped = step_plan_run(plan_id, run["runId"])  # unsupported join
    assert stepped["nodePreviews"]["op_join"]["status"] == "not_materializable"

    stepped = step_plan_run(plan_id, run["runId"])  # limit
    assert stepped["nodePreviews"]["op_limit"]["status"] == "materialized"
    assert len(stepped["nodePreviews"]["op_limit"]["rows"]) == 3

    stepped = step_plan_run(plan_id, run["runId"])  # final result
    assert stepped["nodePreviews"]["data_result"]["status"] == "materialized"
    assert stepped["result"]["rows"]


def test_repair_case_metrics_compute_drr_irr_and_edit_interventions() -> None:
    plan_id = _materialization_plan("plan-repair-controlled")
    persist_execution_run(
        run_id="run-before",
        plan_id=plan_id,
        session_id="repair",
        run_type="sql",
        status="error",
        sql="SELECT missing FROM cards",
        result={"rows": [{"error": "execution_error"}], "columns": []},
    )
    intent = PLAN_STORE[plan_id]["graph"]["nodes"][0]
    update_plan_node(
        plan_id,
        "intent",
        {**intent["data"], "intentLabel": "fixed preview", "targetColumns": ["id", "name"]},
    )
    limit = PLAN_STORE[plan_id]["graph"]["nodes"][3]
    update_plan_node(plan_id, "op_limit", {**limit["data"], "detail": "LIMIT 2"})
    persist_execution_run(
        run_id="run-after",
        plan_id=plan_id,
        session_id="repair",
        run_type="sql",
        status="success",
        sql="SELECT id, name FROM cards LIMIT 2",
        result={"rows": [{"id": 1, "name": "Ancestor's Chosen"}], "columns": [{"key": "id", "label": "id"}]},
    )

    client = _client()
    response = client.post(
        "/evaluation/repair-cases",
        json={"planId": plan_id, "originalRunId": "run-before", "postEditRunId": "run-after"},
    )
    assert response.status_code == 200
    metrics = response.json()["data"]["metrics"]
    assert metrics["metricsAvailable"] is True
    assert metrics["debugRecoveryRate"] is True
    assert metrics["intentRepairRate"] is True
    assert metrics["editInterventions"] == 2
    assert metrics["schemaLinkingCorrectionRate"] is True
    assert metrics["schemaLinkingMetricsAvailable"] is True

    case_id = response.json()["data"]["caseId"]
    assert client.get(f"/evaluation/repair-cases/{case_id}").json()["data"]["metrics"] == metrics

    summary = client.get("/evaluation/repair-summary").json()["data"]
    assert summary["debugRecoveryRate"] == 1.0
    assert summary["intentRepairRate"] == 1.0
    assert summary["averageEditInterventions"] == 2.0
    assert summary["schemaLinkingCorrectionRate"] == 1.0


def test_repair_case_without_controlled_logs_marks_metrics_unavailable() -> None:
    _materialization_plan("plan-repair-unavailable")
    response = _client().post("/evaluation/repair-cases", json={"planId": "plan-repair-unavailable"})
    assert response.status_code == 200
    assert response.json()["data"]["metrics"]["metricsAvailable"] is False
    assert response.json()["data"]["metrics"]["debugRecoveryRate"] is None
