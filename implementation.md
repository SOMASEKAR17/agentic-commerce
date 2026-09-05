# Agentic Commerce — Implementation Plan
**Track:** AI Growth & Agentic Commerce (Razorpay Buildathon)
**Deadline:** Sept 5, 11:59 PM
**Effective build time:** ~25–35 hours

---

## 1. What we're actually building

A merchant-side commerce agent that:
1. Negotiates and grows a transaction (upsell/bundle/bounded discount) via a lightweight buyer agent
2. Authorizes every money action through a deterministic policy engine — never the LLM directly
3. Executes against Razorpay test-mode APIs through real MCP tools
4. Logs every decision to a hash-chained, tamper-evident audit trail
5. Demonstrates one real failure handled gracefully (idempotent retry) and one policy block

**Explicitly out of scope:** consumer storefront/browsing UI, merchant CRUD dashboard, dual product-source adapter, policy-agreement consent screens, Postgres, Next.js. None of these are judged by "The Bar" (explainable, bounded, gated, audit trail, one failure handled gracefully) and building them burns the majority of available time on infrastructure that doesn't touch the grading criteria.

**Core principle to repeat in the pitch:** *The LLM proposes. The deterministic system authorizes.*

---

## 2. Architecture

```
Buyer agent ──states intent──> Merchant agent (catalog + growth engine)
                                        │
                                        ▼
                              Proposed action (unauthorized)
                                        │
                                        ▼
                              Policy engine (spend, tool, risk budgets)
                                        │
                          ┌─────────────┴─────────────┐
                        BLOCK                       APPROVE
                          │                             │
                       Explain                    MCP tool call
                                                         │
                                                         ▼
                                              Razorpay (test mode)
                                                         │
                                                         ▼
                                          Hash-chained audit log
```

### Negotiation flow detail (Buyer agent ↔ Merchant agent)
1. Buyer agent extracts structured intent (max 3 clarification turns, then force-search)
2. Buyer agent → Merchant agent: `PRODUCT_DISCOVERY` request (JSON)
3. Merchant agent searches seeded catalog (`agent_enabled = true` only), ranks deterministically
4. Growth engine checks for a bundle/upsell opportunity within remaining budget
5. Merchant agent → Buyer agent: `COMMERCIAL_OFFER` (JSON, includes bundle if applicable)
6. Buyer agent evaluates against budget + preferences; may send `COUNTER_OFFER`
7. Merchant agent checks counter against max-discount policy (hard cap, not LLM-decided)
8. Both sides converge → **Accepted Offer** object is created — this is the critical handoff point

### The Accepted Offer object
Negotiation is LLM-driven; everything after this object is not.

```json
{
  "agreement_id": "agr_001",
  "buyer_id": "buyer_agent",
  "merchant_id": "merchant_123",
  "items": [
    {"product_id": "p1", "name": "Headphones", "price": 4500},
    {"product_id": "p2", "name": "Case", "price": 400}
  ],
  "final_amount": 4700,
  "currency": "INR",
  "status": "ACCEPTED"
}
```
This is passed to the policy engine as plain data. No further model call is needed to authorize it.

### Policy engine checks (all deterministic code, no LLM)
| Check | Rule |
|---|---|
| Tool call budget | max N tool calls per session |
| Buyer purchase authority | `AUTO_LIMITED` (≤ configured max) or `ASK_ALWAYS` |
| Merchant transaction limit | max per-transaction, daily aggregate |
| Risk score | deterministic: high amount / new buyer / repeated attempt / price mismatch → weighted score |
| Tenant scope | `product.merchant_id == requested_merchant_id`, enforced at the **query layer**, not the prompt |
| Duplicate charge | same buyer + order + amount within a short window → block |
| Price tamper | client-proposed price vs. server catalog price mismatch → block |

Result: `APPROVED`, `HUMAN_APPROVAL_REQUIRED`, or `BLOCKED` (with a machine-readable `decision_reason`, separate from the LLM's human-readable `agent_explanation`).

### MCP tools (real MCP server, not "MCP-style")
- `search_agent_catalog`
- `get_product_details`
- `propose_bundle`
- `create_order`
- `create_payment`
- `get_payment_status`

The policy engine sits **in front of** the tool layer — MCP tools never bypass it.

### Audit log
Append-only, one entry per meaningful event (search, offer, negotiation step, policy decision, payment, failure). Each entry hashes the previous entry:
```json
{
  "event_id": "uuid",
  "timestamp": "...",
  "actor": "merchant_agent",
  "action": "CREATE_PAYMENT",
  "amount": 4700,
  "decision_reason": "WITHIN_LIMITS",
  "agent_explanation": "Transaction is within the merchant's configured limit.",
  "previous_hash": "...",
  "hash": "..."
}
```
Call this **tamper-evident**, not immutable — a fully compromised store can still recompute the chain forward. Say this honestly in the pitch.

---

## 3. Day-by-day timeline

### Day 1 — Agent skeleton
- [ ] One FastAPI service, SQLite, single-page chat UI (no separate frontend app) — 1–2h
- [ ] Seed fixed catalog directly into SQLite (10–20 products, `agent_enabled` flag) — 1h
- [ ] Buyer agent: intent extraction + max-3-turn clarification → structured intent JSON — 3–4h
- [ ] Merchant agent: catalog search + deterministic ranking (weighted score, LLM only narrates) — 3–4h
- [ ] Basic buyer ↔ merchant JSON message exchange (typed contract, doesn't need full A2A spec) — 2–3h

### Day 2 — The graded part
- [ ] Growth engine: bundle/upsell proposal + bounded discount negotiation — 3–4h
- [ ] Accepted Offer object — 1–2h
- [ ] Policy engine: spend/tool/risk budgets, tenant-scope check at query level — 4–5h
- [ ] Real MCP server exposing the six tools above — 2–3h

### Day 3 — Payment, audit, failure, rehearsal
- [ ] Razorpay test-mode: create order → payment link → verify — 3–4h
- [ ] Hash-chain audit log + plain rendered timeline (no dashboard needed) — 2h
- [ ] Failure demo 1: simulated timeout → status-check before retry (no blind retry) — 1–2h
- [ ] Failure demo 2: policy block on over-limit purchase → explained, no API call made — 1h
- [ ] **Reserve final 4–6h for rehearsal only** — no new features

---

## 4. Cut priority if time runs short
Cut in this order, stop as soon as you're back on schedule:
1. Real negotiation/counter-offer → fall back to accept-only (bundle proposal alone still shows growth)
2. Fine-grained risk patterns → keep only spend cap + tenant scope
3. Second failure demo → keep only the idempotent-retry one
4. Hash chaining on audit log → fall back to plain append-only table, mention hash-chaining as "next step"

**Never cut:** the Accepted Offer object, the policy engine between proposal and execution, and the existence of the audit trail. These three are what separate this from a chatbot with a checkout button.

---

## 4a. Architecture update — real A2A, not in-process

The Buyer Agent and Merchant Agent now run as **two separate processes** communicating over HTTP:

- `merchant_service/server.py` (port 8001) — owns the catalog, growth engine, negotiation policy, and the authorize-then-execute checkout path. Exposes:
  - `GET /.well-known/agent.json` — an Agent Card, so a Buyer Agent can discover what this merchant can do before talking to it
  - `POST /tasks` — accepts typed tasks (`PRODUCT_DISCOVERY`, `NEGOTIATE`, `CREATE_ORDER`) and returns typed results
- `app/main.py` (port 8000) — the Buyer Agent / chat UI. Talks to the Merchant Agent purely through `app/agents/a2a_client.py`, which makes real HTTP calls — there is no in-process shortcut back into the merchant's code.

**Honest scope note for judges:** this implements Agent Card discovery and task submission/result over HTTP — the core shape of A2A. It does **not** implement the full spec's streaming responses, push notifications, multi-step task lifecycle states, or a formal auth scheme between agents. That's a deliberate, stated scope cut for hackathon time, not an oversight — say so if asked rather than implying full spec compliance.

### Running it (now two terminals)
```bash
# Terminal 1 — Merchant Agent
uvicorn merchant_service.server:app --port 8001 --reload

# Terminal 2 — Buyer Agent / chat UI
uvicorn app.main:app --port 8000 --reload
```
Open `http://localhost:8000`. If the merchant service isn't running, `/chat` will tell you explicitly instead of crashing — check for `"Merchant Agent unreachable"` in the reply.

Bonus demo moment: hit `http://localhost:8001/.well-known/agent.json` directly in a browser, or click **Show Merchant Agent Card** in the UI — this is the actual discovery document, live, not a description of one.

## 5. Demo script (~3 minutes)
1. "Headphones under ₹5,000" → buyer agent clarifies (wireless? noise cancellation?) → structured intent
2. Merchant agent ranks catalog, growth engine proposes a bundle (headphones + case, ₹5,100 → ₹4,900)
3. Buyer agent counters ("cheaper?") → merchant agent checks discount policy → new offer ₹4,700
4. Accepted Offer created → policy engine checks pass → MCP `create_payment` → Razorpay test-mode payment link
5. Show audit timeline: every step logged, hash-chain intact
6. **Failure 1:** simulate timeout mid-capture → agent checks payment status before retrying → no double charge → explain this live
7. **Failure 2:** buyer tries to force a ₹10,000 purchase over their configured limit → policy engine blocks it → agent explains why → audit shows `BLOCKED`, no API call made
8. Close on the line: *"The LLM proposes. The deterministic system authorizes."*

## 4b. Third review round — execution-boundary fixes (this round)

The prior architecture (separate Buyer/Merchant processes, Agent Card discovery) was sound but several claimed boundaries weren't actually enforced in the running code. Fixed, item by item against the reviewer's own numbered list:

| # | Issue | Fix |
|---|---|---|
| 1 | AcceptedOffer not the real execution boundary | Offers are now versioned rows in a real `offers` table (never mutated — negotiation always inserts a new version pointing at the old one via `supersedes`). Accepting an offer validates it through the actual `AcceptedOffer` pydantic model before it's ever persisted to `agreements`. Policy reads from that persisted row — never from a network-supplied dict. |
| 2 | MCP bypassed at runtime | `merchant_service` is now a real MCP **client** — it spawns `app/mcp_tools/tools.py` as a subprocess over stdio and calls every catalog/negotiation/execution action through `session.call_tool(...)`. There is no other code path into the business logic. |
| 3 | Retry demo was simulated | Replaced with `check_and_recover_payment()`, which makes a real Razorpay API call to check payment-link status before deciding whether a retry is warranted. |
| 4 | Payment lifecycle incomplete | Real state machine: `ACCEPTED → AUTHORIZED → PAYMENT_CREATED → PAYMENT_PENDING → PAID/EXPIRED`, driven by actual payment-link creation and status polling, not just order creation. |
| 5 | Human approval couldn't continue | `approve_pending` / `reject_pending` MCP tools + `/approve` `/reject` endpoints. Approval takes only `agreement_id` — never a new amount or items — and re-authorizes against the exact persisted snapshot. |
| 6 | Buyer authority hardcoded | `buyer_policies` table (`approval_mode`, `max_auto_purchase`, `daily_limit`), read per-buyer at authorization time. |
| 7 | Tool budget didn't count real tools | `record_tool_call()` now fires at every MCP tool invocation, not just on approval. |
| 8 | Tenant scope enforced in Python | `validate_items_in_sql()` — one query per item: `WHERE id=? AND merchant_id=? AND agent_enabled=1 AND stock>0`. |
| 9 | Stock reservation could race | Atomic `UPDATE ... WHERE stock > 0`, checked via `cursor.rowcount`, rolled back as one transaction if any item fails — before any Razorpay call. |
| 10 | Idempotency had a race | `payment_attempts` table with `agreement_id` as primary key — the INSERT itself is the atomic race-winner check, not a separate read-then-write. |

Also fixed: negative discounts rejected (schema-level `Field(ge=0)` + re-validated inside the tool itself), ranking now scores stated preferences (wireless/noise-cancellation) not just budget/rating, deterministic clarification cap enforced in code rather than trusted from the LLM, one `trace_id` generated per session and threaded through every audit event, search/negotiation events now audited (`CATALOG_SEARCHED`, `PRODUCT_RANKED`, `BUNDLE_PROPOSED`, `COUNTER_OFFER`, `DISCOUNT_DECISION`), Groq/Razorpay clients lazy-initialize instead of crashing on import, and Agent Card discovery is checked at buyer startup — the app refuses to proceed if the Merchant Agent doesn't advertise the skills it needs.

**Bugs caught only by actually running this, not by writing it:**
- The MCP subprocess doesn't inherit the parent process's environment by default — `RAZORPAY_KEY_ID` silently never reached the tool server until `env=os.environ.copy()` was added explicitly to `StdioServerParameters`.
- The original idempotency guard treated *any* existing `payment_attempts` row as "already handled," which meant a genuine provider failure (not a duplicate) would permanently block all future retries. Fixed by tracking attempt status (`CREATING` / `CREATED` / `FAILED`) and only replaying on `CREATED`.
- A leftover global `HUMAN_CONFIRM_THRESHOLD` constant was silently overriding the new persisted per-buyer `max_auto_purchase` policy, making Critical #6's fix look like it worked in isolation but not once wired into the real authorization check. Removed.

**Deliberately not implemented, per the reviewer's own stated allowances:** persisting `SESSIONS`/conversation state to SQLite ("not essential for a single demo") and inter-agent authentication ("acceptable for hackathon scope if explicitly documented as demo-only" — so documented, here).
