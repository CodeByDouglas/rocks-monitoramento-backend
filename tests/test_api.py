from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_full_monitoring_flow(client):
    register_payload = {
        "email": "ops@example.com",
        "password": "s3cret",
        "full_name": "Ops User",
    }
    response = await client.post("/api/register", json=register_payload)
    assert response.status_code == 200
    user_data = response.json()
    assert user_data["email"] == register_payload["email"]

    login_payload = {
        "email": register_payload["email"],
        "password": register_payload["password"],
        "mac_address": "AA:BB:CC:DD:EE:FF",
        "username": "Desktop-01",
        "c": "windows-pc",
    }
    response = await client.post("/api/login", json=login_payload)
    assert response.status_code == 200
    token_data = response.json()
    assert token_data["type"] == "pc"
    token = token_data["token"]
    headers = {"Authorization": f"Bearer {token}"}

    config_payload = {
        "data": {
            "Nome": "Desktop Principal",
            "MAC": login_payload["mac_address"],
            "type": "pc",
            "Notificar": True,
            "Frequency": 30,
            "iniciarSO": True,
            "status": {"CPU": True, "RAM": True, "DISCO": True},
        }
    }
    response = await client.post("/api/update_confg_maquina", json=config_payload, headers=headers)
    assert response.status_code == 200
    stored_config = response.json()
    assert stored_config["data"]["Nome"] == "Desktop Principal"

    response = await client.get(f"/api/machine/{login_payload['mac_address']}", headers=headers)
    assert response.status_code == 200
    fetched_config = response.json()
    assert fetched_config["data"]["MAC"] == login_payload["mac_address"]

    metric_payload = {
        "data": {
            "timestamp": "2024-05-20T10:33:00Z",
            "machine_info": {"mac": login_payload["mac_address"], "hostname": "desktop"},
            "cpu": 52.3,
            "memory": 61.4,
            "disk": {"usage": 73.9},
        }
    }
    response = await client.put("/api/maquina/status", json=metric_payload, headers=headers)
    assert response.status_code == 200
    metric_response = response.json()
    assert "reference_id" in metric_response

    response = await client.get(f"/api/metrics/{login_payload['mac_address']}", headers=headers)
    assert response.status_code == 200
    metrics = response.json()
    assert len(metrics) == 1
    assert metrics[0]["metrics"]["cpu"] == pytest.approx(52.3)

    response = await client.get(
        f"/api/metrics/{login_payload['mac_address']}/aggregate",
        headers=headers,
        params={"metric_keys": ["cpu", "memory", "disk"]},
    )
    assert response.status_code == 200
    aggregates = response.json()
    cpu_summary = next(item for item in aggregates if item["metric"] == "cpu")
    assert cpu_summary["average"] == pytest.approx(52.3)


@pytest.mark.asyncio
async def test_machine_config_requires_authentication(client):
    config_payload = {
        "data": {
            "Nome": "Teste",
            "MAC": "11:22:33:44:55:66",
            "type": "pc",
            "Notificar": False,
            "Frequency": 15,
            "iniciarSO": False,
            "status": {},
        }
    }
    response = await client.post("/api/update_confg_maquina", json=config_payload)
    assert response.status_code == 401
