import os
import requests

MERCHANT_SERVICE_URL = os.environ.get("MERCHANT_SERVICE_URL", "http://localhost:8001")

def request_task(task_type: str, session_id: str, buyer_id: str, trace_id: str | None, input_data: dict) -> dict:
    try:
        resp = requests.post(
            f"{MERCHANT_SERVICE_URL}/tasks",
            json={"task_type": task_type, "session_id": session_id, "buyer_id": buyer_id,
                  "trace_id": trace_id, "input": input_data},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        return {"status": "FAILED", "error": f"Could not reach Merchant Agent service: {e}"}

def discover_merchant_agent() -> dict | None:
    try:
        resp = requests.get(f"{MERCHANT_SERVICE_URL}/.well-known/agent.json", timeout=5)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None
