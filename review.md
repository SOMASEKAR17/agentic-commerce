# Agent Commerce - Implementation Review

## Review Scope

This review is based on the current implementation in the submitted
project archive, including:

-   FastAPI application
-   SQLite database
-   Buyer intent agent using Groq
-   Merchant catalog search and ranking
-   Growth/bundle engine
-   Policy engine
-   MCP server
-   Razorpay client
-   Hash-chained audit log
-   Single-page chat UI

This is a code and architecture review of what is currently implemented,
not what is described as planned in `implementation.md`.

------------------------------------------------------------------------

# Executive Verdict

## Current status: Strong prototype foundation, but not yet a complete agentic commerce implementation

The project has a good core idea and several correct architectural
decisions:

> The LLM proposes. Deterministic code authorizes.

That principle is visible in the current `authorize()` flow and is the
strongest part of the implementation.

However, there is currently a significant gap between the architecture
described in `implementation.md` and the code that actually runs.

The biggest issue is this:

> The project currently demonstrates an AI shopping workflow with policy
> checks, not yet a fully implemented A2A + MCP agentic commerce system.

The demo can look convincing, but a technical judge inspecting the
repository can identify several claims that are currently stronger than
the implementation.

### Current implementation score

  ------------------------------------------------------------------------
  Area                                         Score Assessment
  --------------------- ---------------------------- ---------------------
  Core idea                                     9/10 Strong and relevant
                                                     to the track

  Architecture                                  8/10 Good separation
  direction                                          between proposal and
                                                     authorization

  Current                                       5/10 Major planned
  implementation                                     components are
  completeness                                       missing or bypassed

  Agentic behavior                              6/10 Buyer intent
                                                     extraction works, but
                                                     agent separation is
                                                     weak

  A2A implementation                            2/10 No actual A2A
                                                     protocol or
                                                     independent agent
                                                     communication

  MCP implementation                            4/10 Real MCP server
                                                     exists, but main
                                                     runtime does not use
                                                     it

  Policy engine                                 6/10 Good starting point,
                                                     but several claimed
                                                     controls are missing

  Payment safety                                4/10 Razorpay order
                                                     creation exists;
                                                     payment execution and
                                                     idempotency are
                                                     incomplete

  Audit trail                                   6/10 Hash-chain concept is
                                                     implemented, but
                                                     ordering and context
                                                     need work

  Demo readiness                                7/10 Can demonstrate the
                                                     concept, but should
                                                     avoid overselling
                                                     features
  ------------------------------------------------------------------------

## Brutal summary

If judged only from the UI, this can appear like a sophisticated agentic
commerce prototype.

If judged from the code, the main risk is that a technically strong
evaluator may ask:

-   Where is the actual A2A communication?
-   Where is MCP used in the real purchase path?
-   Where are the merchant and buyer policies?
-   Where is the configured user approval flow?
-   Where is duplicate charge prevention?
-   Where is daily spending enforcement?
-   How is tenant scope enforced if products have no `merchant_id`?
-   Why does the retry demo simulate capture without actually capturing
    a payment?

Those questions must be fixed before the final submission.

------------------------------------------------------------------------

# What Is Already Good

## 1. The proposal and authorization separation is correct

The implementation does not allow the Groq model to directly call
Razorpay.

The flow is:

``` text
LLM / agent
    |
    v
Offer
    |
    v
Deterministic authorize()
    |
    +-- BLOCK
    |
    +-- APPROVE
            |
            v
       Razorpay order
```

This is the correct direction.

The most important architectural rule should remain:

> LLM output is untrusted until deterministic validation authorizes it.

Do not remove this separation.

------------------------------------------------------------------------

## 2. The product ranking is deterministic

`search_and_rank()` uses deterministic ranking rather than asking the
LLM to decide which products are best.

This is good because it gives the project explainability.

The current score uses:

-   budget proximity
-   rating
-   review count

This is much easier to defend than:

> The AI thought this product was best.

------------------------------------------------------------------------

## 3. The agent-enabled catalog concept is implemented

The search query correctly uses:

``` sql
agent_enabled = 1
AND stock > 0
```

This supports the idea that products can be selectively exposed to Agent
Commerce.

That is an important concept for the project.

------------------------------------------------------------------------

## 4. The audit trail is not falsely called immutable

The implementation uses a previous-hash chain.

That is more technically honest than claiming SQLite records are
immutable.

The current terminology should remain:

> Tamper-evident audit chain.

Not:

> Immutable audit log.

------------------------------------------------------------------------

## 5. The policy engine is separate from the LLM

The policy engine has independent checks for:

-   tool budget
-   maximum transaction amount
-   price mismatch
-   catalog scope
-   risk score
-   human confirmation threshold

The structure is good even though some checks need improvement.

------------------------------------------------------------------------

# Critical Problems

These should be fixed before adding more features.

------------------------------------------------------------------------

# CRITICAL 1 - There is no real A2A implementation

## What the architecture claims

The documentation describes:

``` text
Buyer Agent
    |
    | A2A
    v
Merchant Agent
```

with:

-   product discovery requests
-   commercial offers
-   counter-offers
-   accepted offers

## What the code actually does

The `/chat` endpoint directly calls:

``` python
intent = extract_intent(convo)
top, offer = search_and_rank(intent)
```

There is no separate Buyer Agent process or service sending a request to
a Merchant Agent.

There is also no:

-   Agent Card
-   A2A task/message lifecycle
-   agent endpoint discovery
-   independent agent transport
-   A2A protocol implementation

The current architecture is closer to:

``` text
Chat UI
   |
   v
FastAPI orchestrator
   |
   +--> Buyer intent extraction
   |
   +--> Merchant search function
```

This is function-to-function orchestration, not A2A.

## Why this matters

If the pitch says:

> We implemented agent-to-agent commerce using A2A.

a technical evaluator can challenge this immediately.

## Required fix

At minimum, separate the two agents behind distinct interfaces.

Recommended structure:

``` text
Buyer Agent Service
        |
        | structured request
        v
Merchant Agent Service
        |
        | structured offer
        v
Buyer Agent Service
```

For hackathon time, even two FastAPI routers/services with typed request
contracts are better than direct function calls.

If claiming actual A2A protocol support, implement the actual protocol
rather than calling JSON messages "A2A."

------------------------------------------------------------------------

# CRITICAL 2 - MCP exists but is bypassed by the real application

## Current MCP implementation

A real FastMCP server exists in:

``` text
app/mcp_tools/tools.py
```

That is good.

However, the main purchase flow does not call MCP.

`/accept` does:

``` python
decision = authorize(...)
rp_order = rp_create_order(...)
```

The runtime directly calls the Razorpay client.

So the actual flow is:

``` text
FastAPI endpoint
    |
    v
authorize()
    |
    v
Razorpay client
```

not:

``` text
Agent
    |
    v
Policy
    |
    v
MCP Tool
    |
    v
Razorpay
```

## Why this matters

The implementation document explicitly says:

> MCP tools never bypass the policy engine.

But the more important problem is:

> The main application itself bypasses MCP.

## Required fix

Choose one architecture and use it consistently.

Recommended:

``` text
Accepted Offer
      |
      v
Policy Engine
      |
      v
Authorized Commerce Service
      |
      v
MCP Tool
      |
      v
Razorpay
```

Do not maintain a separate MCP implementation purely for the pitch.

The live demo path should actually invoke it.

------------------------------------------------------------------------

# CRITICAL 3 - MCP tool surface is incomplete

The implementation plan claims six tools:

-   search_agent_catalog
-   get_product_details
-   propose_bundle
-   create_order
-   create_payment
-   get_payment_status

The actual MCP server currently has only:

-   `search_agent_catalog`
-   `get_product_details`
-   `create_order`

The code itself contains:

``` python
# create_payment / get_payment_status are added Day 3
```

That means the implementation is unfinished.

## Required fix

Either:

1.  Finish the missing tools.

or:

2.  Stop claiming six MCP tools in the README/pitch.

For a hackathon demo, I recommend implementing only the tools actually
needed:

``` text
search_agent_catalog
get_product_details
create_order
create_payment_link
get_payment_status
```

Do not create unnecessary tools just to inflate the architecture.

------------------------------------------------------------------------

# CRITICAL 4 - The project has no real merchant identity or tenant scope enforcement

The policy engine claims to enforce tenant scope.

However, the database schema for `products` has no:

``` text
merchant_id
```

The products table is currently:

``` text
id
name
description
price
rating
reviews
stock
agent_enabled
```

But `check_scope()` only checks whether a product exists:

``` python
if catalog_lookup(item["product_id"]) is None:
    return False
```

That is not tenant scope enforcement.

The implementation documentation claims:

> product.merchant_id == requested_merchant_id

But this is impossible with the current schema.

## Why this matters

This is a direct mismatch between the security claim and the
implementation.

## Required fix

Add:

``` sql
merchant_id TEXT NOT NULL
```

to products.

Then enforce at the database query layer:

``` sql
SELECT *
FROM products
WHERE id = ?
AND merchant_id = ?
AND agent_enabled = 1
```

Do not fetch a product first and compare it only in Python.

The database query itself should enforce scope.

------------------------------------------------------------------------

# CRITICAL 5 - Buyer purchase authority does not exist

The architecture claims:

``` text
ASK_ALWAYS

AUTO_LIMITED
```

with configurable purchase limits.

The current implementation has none of:

-   user settings table
-   approval mode
-   maximum auto purchase amount
-   consent record
-   daily user spending limit

The policy engine instead uses hardcoded constants:

``` python
MAX_TRANSACTION = 5000
AUTO_APPROVE_LIMIT = 500
HUMAN_CONFIRM_THRESHOLD = 3000
```

Also, `AUTO_APPROVE_LIMIT` is declared but never used.

## Required fix

Add a policy table.

Example:

``` text
buyer_purchase_policy

user_id
approval_mode
max_auto_purchase
daily_limit
risk_limit
consent_version
accepted_at
```

Then the policy engine should receive policy configuration instead of
using global constants.

This is required if the UI promises configurable purchasing behavior.

------------------------------------------------------------------------

# CRITICAL 6 - Human approval is not actually implemented

The policy engine can return:

``` text
HUMAN_APPROVAL_REQUIRED
```

But the application does not implement:

``` text
Pending approval
      |
      v
User approves
      |
      v
Resume exactly the same transaction
```

The `/accept` endpoint simply returns the decision.

There is no:

-   approval token
-   pending order
-   expiration
-   approve endpoint
-   reject endpoint

## Required fix

Create a pending authorization state:

``` text
PENDING_HUMAN_APPROVAL
```

Store:

``` text
approval_id
agreement_id
offer_hash
amount
expires_at
status
```

Then add:

``` text
POST /approval/{id}/approve
POST /approval/{id}/reject
```

Most importantly, approval must bind to the exact accepted offer.

The user must not approve ₹4,700 and then have the agent submit ₹4,900.

------------------------------------------------------------------------

# CRITICAL 7 - Duplicate charge prevention is claimed but not implemented

The implementation plan claims:

> same buyer + order + amount within a short window -\> block

The current code does not perform this check.

`_recent_transactions` is used only for risk scoring based on:

``` python
merchant_id
amount
```

That is not duplicate detection.

Two unrelated customers buying the same ₹4,700 item can increase the
risk score.

At the same time, the same customer can potentially accept the same
offer repeatedly.

## Required fix

Use an idempotency key.

Example:

``` text
idempotency_key =
hash(
    agreement_id
    + buyer_id
    + final_amount
)
```

Store payment attempts:

``` text
idempotency_key UNIQUE
agreement_id
payment_provider_order_id
status
```

Before creating a Razorpay order:

``` text
Does this idempotency key already exist?

YES -> return previous result
NO  -> create new payment attempt
```

This is more important than the current risk heuristic.

------------------------------------------------------------------------

# CRITICAL 8 - Repeated acceptance can create multiple Razorpay orders

`/accept` creates an agreement and then creates a Razorpay order.

There is no protection against:

``` text
POST /accept
POST /accept
POST /accept
```

for the same active offer.

Each call can generate:

-   a new agreement ID
-   a new Razorpay order

## Required fix

Once accepted:

``` text
session.current_offer.status = ACCEPTED
```

or, preferably, persist the offer state.

Then enforce:

``` text
ACTIVE -> ACCEPTED
```

Only once.

Use a database transaction or unique idempotency constraint.

------------------------------------------------------------------------

# CRITICAL 9 - Stock is checked but never reserved or decremented

The merchant search requires:

``` sql
stock > 0
```

But accepting an offer does not:

-   reserve stock
-   decrement stock
-   verify stock again before order creation

This allows multiple accepted offers to sell the same final unit.

## Required fix

At authorization/order creation:

``` sql
UPDATE products
SET stock = stock - 1
WHERE id = ?
AND stock > 0
```

Check the affected row count.

For multi-item offers, use a database transaction.

For a hackathon, reservation can be simplified, but stock must be
revalidated at execution time.

------------------------------------------------------------------------

# CRITICAL 10 - The timeout retry demo is not a real payment retry flow

The function is:

``` python
simulate_capture_with_timeout()
```

However, it does not actually capture a Razorpay payment.

It checks:

``` python
fetch_order_status(order_id)
```

and then recursively returns:

``` text
CAPTURED_ON_RETRY
```

without actually making a capture request.

Also, the Razorpay order is created with:

``` python
payment_capture = 0
```

but there is no actual payment capture API call.

## Why this matters

The demo claims:

> Status check before retry prevented a double charge.

But the implementation does not actually prove that against a payment
operation.

## Required fix

For hackathon credibility, simplify and be honest:

### Option A - Payment Link Flow

``` text
Create payment link
      |
      v
Timeout receiving client response
      |
      v
Fetch payment link status
      |
      +--> paid -> do not retry
      |
      +--> not paid -> show retry / continue flow
```

### Option B - Real capture flow

Use a real Razorpay test payment capture lifecycle if supported by your
chosen test flow.

Do not call a simulated function a real idempotent payment
implementation.

------------------------------------------------------------------------

# CRITICAL 11 - The policy engine does not implement the three budgets described in the architecture

The proposed architecture includes:

``` text
tool_call_budget
money_budget
risk_budget
```

Current implementation:

### Tool budget

Partially implemented.

Problem:

The counter increments only after approval.

It does not count actual tool calls such as:

-   search
-   details lookup
-   bundle proposal

So it is not really a tool-call budget.

### Money budget

Only:

``` python
MAX_TRANSACTION = 5000
```

exists.

Missing:

-   daily aggregate spending
-   buyer-specific limit
-   merchant-configured limit

### Risk budget

No cumulative risk budget exists.

The code computes risk for a single offer.

## Required fix

Model these independently:

``` text
Execution Budget
    max_tool_calls
    used_tool_calls

Money Budget
    max_per_transaction
    daily_limit
    daily_spent

Risk Budget
    max_session_risk
    accumulated_risk
```

Do not mix them.

------------------------------------------------------------------------

# High-Priority Problems

------------------------------------------------------------------------

# HIGH 1 - Discount input can be abused with a negative number

`requested_discount` has no validation.

For example:

``` text
requested_discount = -500
```

Then:

``` python
granted = min(-500, max_allowed)
```

returns:

``` text
-500
```

and:

``` python
final_amount = original_total - (-500)
```

increases the price.

This is a basic input validation bug.

## Required fix

Use Pydantic constraints:

``` python
requested_discount: int = Field(ge=0)
```

Also enforce:

``` text
discount <= merchant maximum
```

------------------------------------------------------------------------

# HIGH 2 - The discount policy is global, not merchant-configured

Current:

``` python
MAX_DISCOUNT_PCT = 10
```

But the architecture claims merchant policy.

## Required fix

Store:

``` text
merchant_policy

merchant_id
max_discount_percent
max_transaction_amount
daily_limit
auto_checkout_enabled
```

The growth engine must read merchant policy before creating an offer.

------------------------------------------------------------------------

# HIGH 3 - Bundle selection is unrealistic

The growth engine searches for:

``` sql
name LIKE '%Case%'
```

This means it can attach a random case to almost any product.

A laptop could potentially receive a phone case.

This weakens the "growth engine" claim.

## Required fix

Add product metadata:

``` text
category
product_type
compatible_with
related_product_ids
```

Then bundle using deterministic compatibility.

Example:

``` text
Headphones
    |
    +--> Headphone case
    +--> Warranty
    +--> Audio cable
```

not:

``` text
Any product
    |
    +--> First database item containing "Case"
```

------------------------------------------------------------------------

# HIGH 4 - Search quality is weak

The search uses singularization:

``` python
keyword[:-1]
```

and SQL `LIKE`.

This will fail or behave poorly for many queries.

Examples:

``` text
mouse -> fine
mice -> no conversion
headphones -> headphone
wireless headphones -> unlikely to match descriptions well
```

For hackathon scope this is acceptable, but the agent will appear weak
with natural language queries.

## Recommended improvement

Do not build a vector database unless required.

Instead:

1.  LLM extracts structured intent.
2.  Map intent to categories/features.
3.  SQL filters candidates.
4.  Deterministic scoring ranks candidates.

This will be more reliable than raw keyword matching.

------------------------------------------------------------------------

# HIGH 5 - The intent completion logic does not really enforce three clarification turns

The prompt says:

> Complete after three clarification questions.

But the application does not explicitly track:

``` text
clarification_count
```

Instead, the model sees previous assistant JSON messages and is expected
to infer the count.

This is unreliable.

## Required fix

Store session state:

``` python
{
    "conversation": [],
    "clarification_count": 0,
    "intent": {}
}
```

Increment the count deterministically when a clarification question is
sent.

The LLM should not control loop limits.

------------------------------------------------------------------------

# HIGH 6 - In-memory sessions are fragile

Current:

``` python
SESSIONS = {}
```

This means:

-   restart loses sessions
-   multiple workers break session consistency
-   sessions grow forever
-   no expiration exists

For hackathon scope, this is not fatal.

## Recommended fix

Since SQLite already exists, store:

``` text
agent_sessions
conversation_messages
offers
```

At minimum, add TTL cleanup if keeping memory sessions.

------------------------------------------------------------------------

# HIGH 7 - Audit events are incomplete

The documentation says:

> one entry per meaningful event

But the current `/chat` path does not log:

-   user request
-   clarification
-   catalog search
-   ranking
-   bundle proposal

Only acceptance and payment-related events are logged.

## Required fix

Log at least:

``` text
INTENT_EXTRACTED
CLARIFICATION_REQUESTED
CATALOG_SEARCHED
OFFER_CREATED
DISCOUNT_REQUESTED
DISCOUNT_DECISION
OFFER_ACCEPTED
POLICY_DECISION
ORDER_CREATED
PAYMENT_STATUS_CHECKED
```

Avoid logging every LLM token or raw prompt.

------------------------------------------------------------------------

# HIGH 8 - Audit chain ordering is potentially unstable

Audit entries use timestamps with second-level precision:

``` python
time.strftime("%Y-%m-%d %H:%M:%S")
```

Multiple events can occur during the same second.

But previous hash retrieval uses:

``` sql
ORDER BY timestamp DESC LIMIT 1
```

and timeline uses:

``` sql
ORDER BY timestamp ASC
```

Events with identical timestamps do not have deterministic ordering.

That can make chain verification unreliable.

## Required fix

Add a monotonically increasing sequence ID or order by SQLite insertion
rowid.

Recommended:

``` text
sequence INTEGER PRIMARY KEY AUTOINCREMENT
```

Then:

``` sql
ORDER BY sequence DESC LIMIT 1
```

and:

``` sql
ORDER BY sequence ASC
```

This is a real implementation issue.

------------------------------------------------------------------------

# HIGH 9 - Audit logs have no agreement/session correlation

An evaluator cannot easily answer:

> Show me the full trace for this specific purchase.

Current audit records do not include:

``` text
agreement_id
session_id
order_id
```

## Required fix

Add:

``` text
trace_id
agreement_id
session_id
provider_order_id
```

A single `trace_id` should follow the commerce flow.

------------------------------------------------------------------------

# HIGH 10 - Razorpay credentials are loaded at import time

Current:

``` python
client = razorpay.Client(
    auth=(
        os.environ["RAZORPAY_KEY_ID"],
        os.environ["RAZORPAY_KEY_SECRET"]
    )
)
```

If environment variables are missing, importing the module can fail.

The same pattern exists for:

``` python
os.environ["GROQ_API_KEY"]
```

## Required fix

Validate configuration during startup and provide meaningful errors.

Use:

``` python
os.getenv(...)
```

with explicit startup validation.

Do not allow confusing `KeyError` failures.

------------------------------------------------------------------------

# Medium-Priority Problems

------------------------------------------------------------------------

# MEDIUM 1 - The `AcceptedOffer` model is defined but not actually used

`models.py` defines:

``` python
AcceptedOffer
```

But `/accept` manually constructs and inserts data instead.

This creates a risk of schema drift.

## Fix

Create the accepted offer through the Pydantic model and pass that
object through:

``` text
Negotiation
    |
    v
AcceptedOffer
    |
    v
Policy Engine
    |
    v
Execution
```

The Accepted Offer should be the canonical boundary object.

------------------------------------------------------------------------

# MEDIUM 2 - Offer mutation is in-place

`apply_discount_request()` modifies:

``` python
offer
```

directly.

This makes auditability harder because the original offer is
overwritten.

## Fix

Keep offer versions:

``` text
offer_v1
offer_v2
offer_v3
```

Each should reference:

``` text
parent_offer_id
```

This would make negotiation much more defensible.

------------------------------------------------------------------------

# MEDIUM 3 - No offer expiry

An offer can remain active indefinitely.

## Fix

Add:

``` text
expires_at
status
```

When accepted:

``` text
now <= expires_at
```

must be validated.

------------------------------------------------------------------------

# MEDIUM 4 - No payment verification webhook

The application creates an order but does not have a proper payment
completion path.

For a realistic Razorpay integration, payment success should be verified
server-side.

Recommended:

``` text
Payment provider event
        |
        v
Webhook
        |
        v
Verify signature
        |
        v
Update order state
        |
        v
Audit event
```

For hackathon scope, a verified test callback/status fetch may be
enough, but there must be a clear payment state transition.

------------------------------------------------------------------------

# MEDIUM 5 - No authentication or authorization

Currently any caller can potentially use:

``` text
/accept
/audit
/demo/timeout-retry
```

with arbitrary session/order identifiers.

For a hackathon prototype this may be tolerated, but the merchant/buyer
security story is weak without identity.

At minimum:

-   validate session ownership
-   do not expose all audit records publicly
-   scope records by user/merchant

------------------------------------------------------------------------

# MEDIUM 6 - `/demo/timeout-retry` trusts user input

The endpoint accepts:

``` text
order_id
amount
```

directly from the client.

The amount should be loaded from the server-side order/agreement.

Never trust:

``` text
client amount = payment amount
```

## Fix

Accept only:

``` text
agreement_id
```

Then retrieve:

``` text
final_amount
provider_order_id
```

from the database.

------------------------------------------------------------------------

# MEDIUM 7 - `payment_capture = 0` conflicts with the current product story

The implementation says:

> explicit capture step

but no capture implementation exists.

Either implement the intended payment lifecycle or simplify to the
payment flow Razorpay actually supports for the demo.

Do not leave partially implemented payment semantics.

------------------------------------------------------------------------

# What the Project Is Missing at the Product Level

The current repository intentionally skipped the larger e-commerce
application.

That was a reasonable time-management decision for the original grading
criteria.

However, based on the broader project concept discussed earlier, the
current code is missing:

## Customer-side features

-   policy agreement screen
-   configurable recommendation count
-   configurable purchase approval mode
-   purchase authority limits
-   normal e-commerce browsing
-   customer product selection controls

## Merchant-side features

-   merchant authentication
-   merchant dashboard
-   product CRUD
-   agent catalog enable/disable control
-   merchant-specific discount policy
-   merchant transaction limits

## Data model features

-   merchant ID on products
-   categories
-   product compatibility
-   user purchase policies
-   merchant policies
-   orders/payment attempts
-   offer versions
-   approval records
-   idempotency keys

Do not attempt to build all of these if the deadline is short.

The priority is below.

------------------------------------------------------------------------

# Recommended Priority Order

## Priority 0 - Fix before demo

These are non-negotiable:

``` text
1. Stop claiming A2A unless it is actually implemented.

2. Make the live purchase path actually use MCP, or remove MCP as a core claim.

3. Add merchant_id to products and implement real tenant scope.

4. Add idempotency protection to accepted offers and payments.

5. Fix the payment retry demo so it reflects a real provider state transition.

6. Implement actual human approval continuation.

7. Validate discount inputs.

8. Fix audit ordering and add trace/agreement IDs.
```

------------------------------------------------------------------------

## Priority 1 - Highest value implementation improvements

``` text
1. Persist Buyer Policy.

2. Persist Merchant Policy.

3. Implement daily money limits.

4. Implement actual tool-call accounting.

5. Implement product stock revalidation/reservation.

6. Log the full agent decision timeline.

7. Use the AcceptedOffer model as the execution boundary.
```

------------------------------------------------------------------------

## Priority 2 - Agentic credibility

``` text
1. Separate Buyer Agent and Merchant Agent interfaces.

2. Implement structured request and offer contracts.

3. Add offer versioning.

4. Add actual counter-offer messages.

5. Make growth bundles product-compatible.
```

------------------------------------------------------------------------

## Priority 3 - UI and polish

Only after the above:

``` text
- Better product cards
- Merchant dashboard
- Audit visualization
- Policy settings UI
- Recommendation count setting
```

------------------------------------------------------------------------

# Recommended Final Architecture

``` text
                         USER
                          |
                          v
                    BUYER AGENT
                          |
                  Structured Request
                          |
                    A2A / Agent API
                          |
                          v
                   MERCHANT AGENT
                    /           \
                   /             \
                  v               v
          Catalog Search      Growth Engine
                  \             /
                   \           /
                    v         v
                   OFFER VERSION
                         |
                         v
                    NEGOTIATION
                         |
                         v
                   ACCEPTED OFFER
                  (immutable snapshot)
                         |
                         v
                  POLICY ENGINE
                         |
          +--------------+--------------+
          |              |              |
          v              v              v
        BLOCK       NEED APPROVAL      APPROVE
          |              |              |
          v              v              v
      Explanation      User Action   EXECUTION
                                        |
                                        v
                                   MCP TOOL
                                        |
                                        v
                                    RAZORPAY
                                        |
                                        v
                                  PAYMENT STATE
                                        |
                                        v
                                    AUDIT LOG
```

The important invariant is:

> No money-capable tool should be reachable directly from an
> LLM-controlled path.

------------------------------------------------------------------------

# Minimum Database Schema I Recommend

## Products

``` text
products

id
merchant_id
name
description
category
price
rating
reviews
stock
agent_enabled
```

## Merchant Policy

``` text
merchant_policy

merchant_id
max_discount_percent
max_transaction_amount
daily_transaction_limit
agent_checkout_enabled
```

## Buyer Policy

``` text
buyer_policy

user_id
approval_mode
max_auto_purchase
daily_limit
max_risk_budget
consent_version
accepted_at
```

## Offers

``` text
offers

offer_id
session_id
merchant_id
parent_offer_id
items_json
original_total
final_amount
status
expires_at
```

## Agreements

``` text
agreements

agreement_id
offer_id
buyer_id
merchant_id
final_amount
status
idempotency_key
created_at
```

## Payment Attempts

``` text
payment_attempts

id
agreement_id
idempotency_key UNIQUE
razorpay_order_id
status
amount
created_at
```

## Audit Log

``` text
audit_log

sequence AUTOINCREMENT
event_id
trace_id
agreement_id
actor
action
amount
decision_reason
previous_hash
hash
timestamp
```

------------------------------------------------------------------------

# Suggested Demo After Fixes

## Scenario 1 - Normal successful flow

``` text
User:
Wireless headphones under ₹5,000.

Buyer Agent:
Clarifies requirements.

Buyer Agent:
Sends structured product request.

Merchant Agent:
Searches only agent-enabled products.

Merchant Agent:
Ranks candidates deterministically.

Growth Engine:
Offers a compatible bundle.

Buyer Agent:
Accepts/counters.

Merchant Policy:
Approves allowed discount.

Accepted Offer:
Created as a frozen snapshot.

Policy Engine:
Checks buyer policy, merchant policy, risk, limits, scope and stock.

MCP:
Creates payment order.

Razorpay:
Payment state verified.

Audit:
Shows full trace.
```

------------------------------------------------------------------------

## Scenario 2 - Human approval

``` text
Offer amount: ₹4,700
Buyer auto limit: ₹3,000

Policy:
HUMAN_APPROVAL_REQUIRED

User:
Approves the exact agreement.

Execution:
Continues using the same agreement ID.
```

This is much stronger than simply returning:

``` text
HUMAN_APPROVAL_REQUIRED
```

and stopping.

------------------------------------------------------------------------

## Scenario 3 - Idempotent failure

``` text
Payment operation times out locally.

System:
Does NOT blindly retry.

System:
Fetches provider state using the same payment/order reference.

Provider says:
Already completed.

System:
Does not create another charge.

Audit:
TIMEOUT
STATUS_CHECK
ALREADY_PROCESSED
NO_RETRY
```

This is the strongest failure demo.

------------------------------------------------------------------------

# What I Would Remove

To avoid unnecessary complexity:

## Remove or avoid

### Fake "ML risk classifier"

The deterministic risk engine is more credible.

### Full marketplace frontend before core correctness

Do not spend time cloning Amazon if the agent flow is the judged
feature.

### Complex multi-agent orchestration frameworks

A small state machine is easier to demonstrate.

### Too many MCP tools

Five working tools are better than ten claimed tools.

### Fake protocol terminology

Do not call internal function calls:

``` text
A2A
```

unless you actually have an agent-to-agent boundary.

------------------------------------------------------------------------

# Final Evaluation

## Is the project idea good?

Yes.

The strongest differentiator is not:

> AI shopping recommendations.

That already exists everywhere.

The differentiator is:

> An agent can negotiate and propose commerce actions, but deterministic
> policies independently authorize every consequential action.

That is the correct direction for an Agentic Commerce project.

## Is the current implementation enough?

Not yet.

The current code is approximately:

``` text
65% solid prototype
35% architecture claims not yet implemented
```

The highest-risk mismatch is between:

``` text
implementation.md
```

and:

``` text
actual runtime code
```

Before submission, reduce that gap.

## What would impress a technical evaluator most?

Not adding another UI feature.

Implement these three things properly:

### 1. A real agent boundary

Buyer Agent and Merchant Agent exchange structured messages.

### 2. An actual authorization boundary

The Accepted Offer becomes immutable input to deterministic policy
checks.

### 3. An idempotent payment execution path

The same agreement can never produce duplicate provider actions.

If those three are correct, the project becomes substantially more
credible.

------------------------------------------------------------------------

# Final Submission Checklist

## Architecture

-   [ ] Buyer and Merchant agent boundary is real.
-   [ ] Protocol terminology matches implementation.
-   [ ] Accepted Offer is the canonical execution object.
-   [ ] LLM never directly controls a payment-capable operation.

## MCP

-   [ ] MCP tools used by the real runtime path.
-   [ ] Missing tools implemented or removed from claims.
-   [ ] Policy checks happen before money-capable tools.

## Policy

-   [ ] Buyer policy persisted.
-   [ ] Merchant policy persisted.
-   [ ] Per-transaction limits enforced.
-   [ ] Daily limits enforced.
-   [ ] Tool calls actually counted.
-   [ ] Risk budget is explicit if claimed.
-   [ ] Human approval can resume an exact pending agreement.

## Security

-   [ ] Products have merchant_id.
-   [ ] Tenant scope enforced in SQL/API query.
-   [ ] Client cannot submit arbitrary payment amount.
-   [ ] Discount values validated.
-   [ ] Idempotency key prevents duplicate execution.

## Commerce

-   [ ] Stock revalidated before execution.
-   [ ] Offers expire.
-   [ ] Offer versions are preserved.
-   [ ] Bundles are compatibility-aware.

## Payment

-   [ ] Razorpay flow matches actual implementation.
-   [ ] Payment status is verified server-side.
-   [ ] Retry checks provider state before retry.
-   [ ] Duplicate payment attempts cannot occur.

## Audit

-   [ ] Stable event sequence ordering.
-   [ ] trace_id exists.
-   [ ] agreement_id exists.
-   [ ] Full decision flow is logged.
-   [ ] Hash-chain verification works consistently.

------------------------------------------------------------------------

# Bottom Line

Do not add more broad features right now.

The project does not primarily need:

``` text
More pages
More UI
More agents
More APIs
```

It needs correctness at the boundaries:

``` text
Agent proposal
      ->
Accepted Offer
      ->
Deterministic authorization
      ->
Idempotent execution
      ->
Verified provider state
      ->
Traceable audit
```

If those boundaries are implemented cleanly, this becomes a strong
hackathon project.

If they remain partially implemented while the pitch claims A2A, MCP,
tenant isolation, duplicate prevention, and idempotent payments, the
project is vulnerable to technical questioning.
