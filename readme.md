# Agentic Commerce Demo

A buyer agent and a merchant agent that negotiate, authorize, and pay for a
purchase over real MCP + A2A + Razorpay — no mocked provider
calls.

## Architecture (short version)

Three processes:

1. **Buyer agent** — `app/main.py`, FastAPI, port **8000**. Serves the chat
   UI, extracts intent with Groq, and talks to the merchant agent over HTTP
   ("A2A").
2. **Merchant agent** — `merchant_service/server.py`, FastAPI, port **8001**.
   Receives tasks over HTTP and delegates every action to the MCP tool
   server below.
3. **MCP tool subprocess** — `app/mcp_tools/tools.py`, spawned by the
   merchant agent over stdio (not a separate port). This is where catalog
   search, negotiation, policy authorization, and the real Razorpay calls
   live.

All three share one SQLite file: `data.db` (created automatically).

## 1. Prerequisites

- Python 3.11+
- A [Groq API key](https://console.groq.com/keys) (free tier works)
- A [Razorpay test-mode key](https://dashboard.razorpay.com/app/keys) (`rzp_test_...`)

## 2. Setup

```bash
# from the project root
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

Copy the example env file and fill in your real keys:

```bash
cp .env.example .env
```

`.env` should look like:

```
GROQ_API_KEY=gsk_your-real-key
GROQ_MODEL=openai/gpt-oss-120b
RAZORPAY_KEY_ID=rzp_test_your-real-key
RAZORPAY_KEY_SECRET=your-real-secret
MERCHANT_SERVICE_URL=http://localhost:8001
```

> **Important:** the buyer agent and merchant agent are two separate
> processes and neither inherits the other's environment. Both load
> `.env` independently — if you ever add a new env var, make sure it's
> read in both `app/main.py` and `merchant_service/server.py`, and that
> you restart **both** processes after changing `.env`.

## 3. Seed the catalog (first run only)

```bash
python -m app.seed_catalog
```

This populates `data.db` with the demo product catalog. Safe to re-run —
it won't duplicate rows.

## 4. Run the app

You need **two terminals**, both with the venv activated.

**Terminal 1 — Merchant agent (port 8001):**

```bash
python -m uvicorn merchant_service.server:app --port 8001 --reload
```

This is the process that spawns the MCP tool subprocess on startup — check
its logs for `Started server process` and no `RAZORPAY_KEY_ID` warnings.

**Terminal 2 — Buyer agent (port 8000):**

```bash
python -m uvicorn app.main:app --port 8000 --reload
```

Then open **http://localhost:8000** in your browser. Start typing —
e.g. "I want headphones under 5000".

Start the merchant agent first; the buyer agent checks it can reach
`http://localhost:8001/.well-known/agent.json` on startup and will refuse
chat requests otherwise ("Merchant Agent unreachable").

## 5. Inspecting the MCP tool server directly

The actual tools (`search_agent_catalog`, `propose_bundle`,
`negotiate_discount`, `create_order`, `create_payment`, etc.) live in
`app/mcp_tools/tools.py` as a standalone MCP server. You can talk to it
directly — bypassing the buyer/merchant HTTP layer entirely — using the
official **MCP Inspector**.

Install the CLI extra (adds the `mcp` command):

```bash
pip install "mcp[cli]"
```

Launch the Inspector against the tool server:

```bash
mcp dev app/mcp_tools/tools.py
```

This prints a local URL (usually `http://localhost:5173` with a session
token) — open it in your browser. From there you can:

- See every registered tool, its input schema, and its docstring
- Call any tool directly with hand-typed JSON arguments (e.g. call
  `search_agent_catalog` with `{"buyer_id": "test", "product": "headphones", "budget": 5000}`
  and see the raw result, no LLM or HTTP hop involved)
- Watch stdio traffic (the raw JSON-RPC requests/responses) in real time

This is the fastest way to confirm whether a bug is in a tool itself
versus in how `merchant_service` calls it.

**Note:** run this in a separate terminal from your normal app processes.
It spawns its own instance of `tools.py`, so it shares `data.db` with the
running app but does not share the merchant agent's live MCP session.

### Checking the merchant agent's A2A discovery

The merchant agent exposes a standard "agent card" — this is what the
buyer agent checks on startup to confirm the merchant supports the
skills it needs:

```bash
curl http://localhost:8001/.well-known/agent.json
```

You should see a JSON document listing skills:
`product_discovery`, `negotiate`, `create_order`, `human_approval`,
`payment`. Or just click "Show Merchant Agent Card" in the chat UI.

## 6. Useful things while developing

- **Audit trail** — click "Show Audit Trail" in the UI, or:
  ```bash
  curl http://localhost:8000/audit
  ```
  Returns the full hash-chained event log plus `chain_verified: true/false`.

- **Reset all data** — stop both processes, delete `data.db`, then re-run
  the seed step:
  ```bash
  rm data.db
  python -m app.seed_catalog
  ```

- **Payment links are real Razorpay test-mode links.** They will open an
  actual (test-mode) Razorpay checkout page. Use Razorpay's
  [test card numbers](https://razorpay.com/docs/payments/payments/test-card-upi-details/)
  to simulate a successful or failed payment.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| "Merchant Agent unreachable" in chat | `merchant_service` isn't running on 8001, or wasn't started before the buyer agent |
| `RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not set` | `.env` wasn't loaded in `merchant_service/server.py` — restart that process after adding keys |
| `GROQ_API_KEY is not set` | Same issue but in `app/main.py`'s process |
| Offer says `OFFER_EXPIRED` immediately | Server timezone bug in offer-age calculation — see project history / `app/mcp_tools/tools.py` around `time.mktime` |
| Payment link never appears after approval | Check Terminal 1 (merchant agent) logs — the Razorpay call happens there via the MCP subprocess |