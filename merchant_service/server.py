"""
Merchant Commerce Agent — a real, independently-running A2A service.

Every catalog, negotiation, and execution action is delegated to the MCP
tool server (app/mcp_tools/tools.py) through a real MCP ClientSession —
this process is an MCP *client*, not a shortcut around MCP. See
app/mcp_tools/mcp_client.py for the persistent stdio connection.

Implemented subset of A2A: Agent Card discovery + task submission/result
over HTTP. NOT implemented: streaming, push notifications, formal task
lifecycle states beyond what's modeled here, or inter-agent auth — a
deliberate, stated scope cut, not an oversight.
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from pydantic import BaseModel

from app.db import init_db
from app.mcp_tools import mcp_client

init_db()

app = FastAPI(title="Merchant Commerce Agent")

AGENT_CARD = {
    "name": "Merchant Commerce Agent",
    "description": "Handles product discovery, growth/bundle offers, negotiation, authorization, "
                    "and payment-link creation for merchant_demo's Razorpay test-mode catalog.",
    "url": "http://localhost:8001",
    "version": "1.1",
    "provider": {"organization": "merchant_demo"},
    "capabilities": {"streaming": False, "pushNotifications": False},
    "skills": [
        {"id": "product_discovery", "name": "Product Discovery"},
        {"id": "negotiate", "name": "Discount Negotiation"},
        {"id": "create_order", "name": "Order Authorization"},
        {"id": "human_approval", "name": "Human Approval Continuation"},
        {"id": "payment", "name": "Payment Link Creation & Status"},
    ],
}

@app.on_event("startup")
async def startup():
    await mcp_client.start()

@app.on_event("shutdown")
async def shutdown():
    await mcp_client.stop()

@app.get("/.well-known/agent.json")
def agent_card():
    return AGENT_CARD

class TaskRequest(BaseModel):
    task_type: str
    session_id: str
    buyer_id: str
    trace_id: str | None = None
    input: dict = {}

@app.post("/tasks")
async def handle_task(payload: TaskRequest):
    task_id = str(uuid.uuid4())[:8]
    t = payload.trace_id

    if payload.task_type == "PRODUCT_DISCOVERY":
        search_result = await mcp_client.call_tool("search_agent_catalog", {
            "buyer_id": payload.buyer_id, "product": payload.input.get("product") or "",
            "budget": payload.input.get("budget"), "wireless": payload.input.get("wireless"),
            "noise_cancellation": payload.input.get("noise_cancellation"),
            "top_n": payload.input.get("top_n", 3), "trace_id": t,
        })
        products = search_result.get("products", [])
        if not products:
            return {"task_id": task_id, "status": "COMPLETED", "output": {"products": [], "offer": None}}

        offer_result = await mcp_client.call_tool("propose_bundle", {
            "buyer_id": payload.buyer_id, "session_id": payload.session_id,
            "product_id": products[0]["id"], "budget": payload.input.get("budget"),
            "allow_bundle": payload.input.get("allow_bundle", True), "trace_id": t,
        })
        return {"task_id": task_id, "status": "COMPLETED", "output": {"products": products, "offer": offer_result}}

    if payload.task_type == "NEGOTIATE":
        result = await mcp_client.call_tool("negotiate_discount", {
            "buyer_id": payload.buyer_id, "session_id": payload.session_id,
            "offer_id": payload.input["offer_id"], "requested_discount": payload.input["requested_discount"],
            "trace_id": t,
        })
        return {"task_id": task_id, "status": "COMPLETED", "output": {"offer": result}}

    if payload.task_type == "CREATE_ORDER":
        result = await mcp_client.call_tool("create_order", {
            "buyer_id": payload.buyer_id, "session_id": payload.session_id,
            "offer_id": payload.input["offer_id"], "trace_id": t,
        })
        if result.get("status") == "AUTHORIZED":
            payment = await mcp_client.call_tool("create_payment", {
                "buyer_id": payload.buyer_id, "agreement_id": result["agreement_id"], "trace_id": t,
            })
            result["payment"] = payment
        return {"task_id": task_id, "status": "COMPLETED", "output": result}

    if payload.task_type == "CREATE_PAYMENT":
        # Direct retry entrypoint for an AUTHORIZED agreement whose payment
        # attempt failed at the provider (not expired — that's RETRY_PAYMENT).
        result = await mcp_client.call_tool("create_payment", {
            "buyer_id": payload.buyer_id, "agreement_id": payload.input["agreement_id"], "trace_id": t,
        })
        return {"task_id": task_id, "status": "COMPLETED", "output": result}

    if payload.task_type == "APPROVE_PENDING":
        result = await mcp_client.call_tool("approve_pending", {
            "buyer_id": payload.buyer_id, "agreement_id": payload.input["agreement_id"], "trace_id": t,
        })
        if result.get("status") == "AUTHORIZED":
            payment = await mcp_client.call_tool("create_payment", {
                "buyer_id": payload.buyer_id, "agreement_id": result["agreement_id"], "trace_id": t,
            })
            result["payment"] = payment
        return {"task_id": task_id, "status": "COMPLETED", "output": result}

    if payload.task_type == "REJECT_PENDING":
        result = await mcp_client.call_tool("reject_pending", {
            "buyer_id": payload.buyer_id, "agreement_id": payload.input["agreement_id"], "trace_id": t,
        })
        return {"task_id": task_id, "status": "COMPLETED", "output": result}

    if payload.task_type == "GET_PAYMENT_STATUS":
        result = await mcp_client.call_tool("get_payment_status", {
            "buyer_id": payload.buyer_id, "agreement_id": payload.input["agreement_id"], "trace_id": t,
        })
        return {"task_id": task_id, "status": "COMPLETED", "output": result}

    if payload.task_type == "RETRY_PAYMENT":
        result = await mcp_client.call_tool("create_payment", {
            "buyer_id": payload.buyer_id, "agreement_id": payload.input["agreement_id"],
            "retry_after_expiry": True, "trace_id": t,
        })
        return {"task_id": task_id, "status": "COMPLETED", "output": result}

    return {"task_id": task_id, "status": "FAILED", "error": f"Unknown task_type: {payload.task_type}"}
