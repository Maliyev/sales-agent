# Sales agent

A small terminal chat bot for the future elen.az sales assistant.

## First version

- sends messages to Gemini through its REST API;
- saves separate conversation histories in a local SQLite database;
- reads the API key and model name from `.env`;
- keeps the database file out of Git.
- stops before it sends an oversized history to Gemini.
- reads its instructions and store knowledge from Markdown files.
- searches elen.az and filters several relevant product candidates.
- reads elen.az product links sent directly by a customer.
- processes a customer's product list item by item and reports all results at once.
- converts attached Excel (.xlsx) and Word (.docx) documents into text and feeds it to the agent.
- permanently blocks a session that sends more than 15 messages in 60 seconds.
- can explicitly refer a customer to a human operator.

## Architecture (as of September 8, 2026)

What happens when a customer message arrives:

```text
Telegram / WhatsApp / terminal / admin dashboard
        │  incoming messages (polling or webhook)
        ▼
Channel adapters (telegram_bot.py, whatsapp_bot.py, main.py)
        │  SessionCoordinator.submit(session_id, text)
        ▼
SessionCoordinator (session_coordinator.py)
        │  message_service.generate_customer_reply (message_service.py)
        ▼
agent.get_agent_reply (agent.py) — the three-stage Gemini pipeline
        │
        ▼
AgentReply → saved to SQLite → sent back through the channel
```

**Session queue** (`session_coordinator.py`). One worker thread per session
(6 workers in the full runner), so messages of one session never interleave.
The worker waits one second (debounce) and merges message bursts into a single
combined request. A spam guard permanently blocks a session that sends more
than 15 messages per minute.

**History and context** (`message_service.py`). The reply flow loads the
session history from SQLite. If the history no longer fits the context limit,
the request first triggers auto-compaction (a separate model summarizes the
oldest turns and replaces them; every session keeps its own summary in the
database) or, as a fallback, auto-resets the conversation.

**Stage 1 — decision** (0..N Gemini calls). Context: the full system
instruction (`prompts/01_role.md`, `02_response_rules.md`,
`03_security_rules.md`, `04_product_tools.md`, `05_operator.md` plus
`knowledge/store.md`), the persistent chat history, and the current user
message. Tools: `search_products` (searches the elen.az catalog) and
`request_operator` (hands the chat to a human). For simple questions the model
answers with plain text and no tool call. For product questions it searches up
to `limits.max_search_rounds` times (default 3); the numbered candidates of
every round (id, title, price, currency) are appended to its context as
function results, so each next query can build on the previous ones (English
queries first, Russian keywords as a second attempt). If the model emits
several `search_products` calls in one turn, all of them are executed in that
turn and answered together.

**Stage 2 — selection** (1 Gemini call). Context: the same base instruction
plus `prompts/product_selection.md` and all accumulated candidates as
temporary private data. A forced function call `select_product_candidates`
returns up to 10 relevant candidate IDs, a `needs_clarification` flag, and one
clarifying question. An empty selection is treated as a clarification request,
never as a crash.

**Stage 3 — final answer** (1 Gemini call). Context: the system instruction
without the search rules (`04_product_tools.md` is excluded), plus
`prompts/product_response.md`, the chat history, and the verified product
data: the fully parsed elen.az pages of the selected products (price, stock,
variants). Tool: `request_operator` only. This call writes the customer-facing
text; if it wrongly tries to search here, the code degrades to its plain text
or the clarifying question instead of failing.

**Shortcut.** elen.az product links inside the customer message skip stages
1–2 entirely: the pages are parsed directly and handed to the final stage.

**Product lists.** When the decision stage sees a list of several products to
check, it calls `start_product_list(count)` before any search. The code then
restarts the full pipeline once per list item: the decision stage gets an
addendum (`prompts/product_list_decision.md`) naming the current item and its
number, searches run as usual (up to `limits.max_search_rounds` per item),
and the final stage writes a 1–2 sentence internal note instead of a customer
reply (`prompts/product_list_item_response.md`). Each note lands in an
in-memory cache; after the last item one extra final call with
`prompts/product_list_report.md` turns all notes into a single customer
report. The whole list lives inside one `generate_customer_reply` turn, is
capped by `limits.max_api_calls_per_reply` (the report call is always
reserved), and a list that ends early still gets a partial report.

**Document attachments.** Telegram (`message.document`) and WhatsApp
(`type: "document"`) attachments with an `.xlsx` or `.docx` extension are
downloaded by the channel adapter (max 5 MB) and converted to plain text by
`document_reader.py`: Excel sheets become tab-separated rows (one section per
sheet, cached formula values via openpyxl), Word paragraphs and tables keep
their document order (stdlib ZIP + XML parsing). The extractor caps the text
at 40 000 characters with a truncation notice. The converted text is wrapped
in a system note ("The customer sent a document ..., the system converted it
to plain text below"), stored as the incoming message, and processed like a
regular customer text — so a product table inside an attachment automatically
triggers list mode. Unsupported formats (`.pdf`, legacy `.doc`/`.xls`) get a
friendly reply asking for `.xlsx`/`.docx`.

**Photo attachments.** Compressed photos (`message.photo`, `type: "image"`)
and images sent as document files (`.jpg`/`.jpeg`/`.png`/`.webp` or an
`image/*` MIME type) are downloaded by the channel adapter (max 5 MB) and sent
to a vision model with a dedicated prompt (`prompts/07_image_describer.md`):
it identifies the component or transcribes a product list from the photo. The
returned description is wrapped in a system note ("... may contain
inaccuracies") together with the customer caption and processed like regular
text. The vision call is recorded in `api_calls` with purpose `vision` and
uses `gemini.vision_model` (falls back to the main model when empty). The
agent is instructed to warn the customer that image recognition is
experimental and to ask for text input.

**Every Gemini call** goes through a token estimate, a per-minute TPM limiter
(over-budget requests wait for the next minute window instead of failing), the
API call itself (usage recorded in the `api_calls` table per purpose:
decision / selection / final / compaction / vision), and a per-session
consumption guard that blocks sessions burning too many tokens too fast.

**Reply path.** The final text (and, when the agent escalated to a human, an
operator note) is saved with status `RESPONSE_READY`, delivered through the
same channel adapter, and marked `DELIVERED` or `FAILED_DELIVERY`. Each step
is mirrored to `data/logs/conversations.log` and the rotating ops log.

## Setup

Create a `.env` file from `.env.example` and add your Gemini API key.

Install the dependency:

```powershell
python -m pip install -r requirements.txt
```

Run the chat:

```powershell
python src/main.py
```

## Telegram demo

Create a bot by opening [@BotFather](https://t.me/BotFather), send `/newbot`,
and follow its instructions. Keep the received token private and add it only to
your local `.env` file:

```text
TELEGRAM_BOT_TOKEN=your_real_token
```

Run the Telegram bot while this computer stays online:

```powershell
python src/telegram_bot.py
```

Each Telegram chat uses its own session such as `telegram:123456`. Send
`/reset` in Telegram to clear only that chat's saved history. This first demo
uses long polling. Up to four different sessions can wait for Gemini at the
same time.

Messages from one session stay in order. The bot waits one second before a new
request so that short message bursts can be combined. If another message
arrives during the first Gemini request, the old result is not saved or sent.
The bot rebuilds the request once with both messages. Further messages wait for
the next turn. This is still a local demo, not a production deployment.

Type `exit` to stop the program.

Useful terminal commands:

- `/use magerram` switches to the session `terminal:magerram`.
- `/sessions` shows sessions created in this run.
- `/reset` clears only the current session history.

The part before `:` is the message channel. Later, the website chat can use a
key such as `website:<visitor_id>` and WhatsApp can use `whatsapp:<number>`.
They stay separate even when the part after `:` is the same.

The database is created automatically as `data/sales_agent.db`. It is local to
this computer and is ignored by Git because it can contain customer messages.
Spam limits and blocked session IDs are stored in the same database. A blocked
session stays blocked after the program restarts and is not cleared by `/reset`.

The project reads simple `KEY=value` lines from `.env` itself. It uses
`requests` for the direct HTTP request to Gemini and does not use a Gemini SDK.
It uses a conservative character-based estimate and stops when a conversation
is longer than roughly 250,000 tokens.

The files in `prompts/` and `knowledge/store.md` are loaded when the program
starts. Edit them to change the assistant's behavior, then restart the bot.

When Gemini calls `request_operator`, the customer receives a short referral
message. A separate operator summary is printed in the terminal for now. The
session remains active, and no operator message is added to customer history.

When a customer asks about a product, the agent works in three short steps:

1. Gemini decides whether a product search is needed.
2. Search results receive temporary candidate IDs and Gemini keeps up to ten
   relevant products.
3. Python loads current product details and Gemini writes the customer answer.

If the customer sends a direct elen.az product link, Python validates and opens
the link immediately. The search and candidate-selection steps are skipped.

## WhatsApp Cloud API

The WhatsApp connector uses Meta's official Cloud API. It is separate from the
agent core: the webhook turns an incoming customer message into a session such
as `whatsapp:994501234567`, then uses the same history, spam guard, concurrency,
and agent code as Telegram.

The connector currently accepts text messages. It validates Meta's
`X-Hub-Signature-256` signature, ignores events for other phone numbers, and
stores received WhatsApp message IDs in SQLite so webhook retries do not create
duplicate customer replies.

Required local settings are listed in `.env.example`. This checkout can also
load private Meta credentials from `.private/meta-whatsapp/credentials.env`.
That folder is local and must never be committed.

Run the local webhook server:

```powershell
python src/whatsapp_bot.py
```

It listens on `http://127.0.0.1:8000/webhooks/whatsapp`. Meta needs a public
HTTPS callback URL, so local development will use an HTTPS tunnel such as
Cloudflare Tunnel or ngrok. Router port forwarding is not required. The value entered in Meta's
Verify token field must exactly match `WHATSAPP_VERIFY_TOKEN`.

## Run everything with one command

```powershell
python src/runner.py
```

The runner starts Telegram polling, the WhatsApp webhook server, and the
admin dashboard in one process with one shared session coordinator
(six parallel workers). All channels write to the same two log files.
Stop it with Ctrl+C.

The standalone entry points (`telegram_bot.py`, `whatsapp_bot.py`,
`admin_dashboard.py`, `main.py`) keep working for running one channel alone,
but do not combine them with the runner for the same channel.

## Application logs

The project writes two rotating log files.

`data/logs/sales_agent.log` is the operational log. It records startup,
queueing, reply timing, delivery, operator requests, blocked sessions, and
errors. It does not record message text, access tokens, or API keys.

`data/logs/conversations.log` is the full conversation log. It records the
customer message text, the agent's decision steps (product search query,
found product titles, selected candidates), the final model reply, operator
requests, and manual replies sent from the dashboard. Each line starts with
the session ID:

```text
2026-08-23 21:00:01 | telegram:123456 | USER | Есть Samsung TV?
2026-08-23 21:00:02 | telegram:123456 | DECISION | search query='Samsung TV'
2026-08-23 21:00:02 | telegram:123456 | FOUND | query='Samsung TV' found=30 | Samsung 43" Crystal; LG OLED; … ещё 28
2026-08-23 21:00:03 | telegram:123456 | SELECTED | ids=[3] | Samsung 43" Crystal UHD
2026-08-23 21:00:05 | telegram:123456 | MODEL | Да, в наличии…
```

Both active files are limited to 2 MB. Up to three older files are kept
automatically. To watch a log live in PowerShell:

```powershell
Get-Content .\data\logs\sales_agent.log -Wait -Tail 50
Get-Content .\data\logs\conversations.log -Wait -Tail 50
```

Do not run `src/runner.py` and a standalone bot for the same channel at the
same time: two Telegram pollers would steal updates from each other, and the
WhatsApp port 8000 can only be bound by one process.

## Database

All data lives in one SQLite file: `data/sales_agent.db`. The schema is created
and upgraded by numbered migrations in `src/database.py`. The applied version is
stored in SQLite's `user_version` pragma, so starting the program on an older
file applies only the missing migration steps.

Current tables:

- `sessions` — one row per conversation (`telegram:123`, `whatsapp:994…`) with
  a `channel` column.
- `messages` — every stored message with `role` (`user`, `model`, `operator`,
  `tool`), an `archived` flag, a lifecycle `status`, and a `created_at`
  timestamp.
- `tool_calls` — full details of agent tool calls (arguments, result, error,
  timing), linked to their lightweight `messages` row through `message_id`.
- `api_calls` — one row per model API request with its purpose (`decision`,
  `selection`, `final`), token usage, duration, and outcome. The table and the
  token accounting are provider-agnostic: each provider module (currently
  `gemini.py`) supplies its own usage extractor.
- `recent_messages` and `blocked_sessions` — the spam rate limiter and token
  abuse blocks.
- `whatsapp_inbound_messages` — webhook deduplication.

`/reset` deletes nothing: it marks the session's messages as `archived = 1`,
so the working context becomes empty while the full history stays in the file
for analytics and future export.

Message `status` values: `INITIALIZING`, `AWAITING_RESPONSE`,
`AGENT_PROCESSING`, `RESPONSE_READY`, `DELIVERED`, and three failure states:
`FAILED_LLM_API` (generation failed), `FAILED_DELIVERY` (the reply exists but
could not be delivered), `FAILED_OTHER`. A customer message is stored as soon
as it arrives (`INITIALIZING`) and is hidden from the model history until the
turn finishes; successful sends mark the whole turn `DELIVERED`.

## Configuration reference (config.json)

Every model request is written to `api_calls`, linked to the customer message
that triggered it. All tunable settings live in `config.json` in the project
root (secrets stay in `.env`). Complete reference:

```json
{
  "gemini": {
    "model": "gemini-2.5-flash-lite",
    "vision_model": "",
    "tpm_limit": 0,
    "thinking_level": "",
    "retry": {
      "delays": [15, 30, 60, 120, 240],
      "max_wait_seconds": 600
    }
  },
  "limits": {
    "max_search_rounds": 3,
    "max_api_calls_per_reply": 70,
    "message_rate": {
      "max_messages": 15,
      "window_seconds": 60
    },
    "token_abuse": {
      "limit": 0,
      "window_seconds": 60
    },
    "context_overflow": {
      "auto_reset": true,
      "auto_compaction": false,
      "compaction_model": ""
    }
  }
}
```

- `gemini.model` — the Gemini model name (moved out of `.env`).
- `gemini.vision_model` — the model used to describe customer photos; an
  empty string falls back to `gemini.model`. The description call is recorded
  in `api_calls` with the `vision` purpose.
- `gemini.tpm_limit` — an estimated tokens-per-minute budget across all
  sessions. `0` disables it. When a request would exceed the budget, the
  worker waits and retries every few seconds until the current minute window
  frees up; after 10 minutes of waiting the turn fails. A single request that
  is larger than the whole budget can never fit, so it fails fast instead of
  waiting (see `limits.context_overflow` below).
- `gemini.thinking_level` — the reasoning effort for thinking models
  (`minimal`, `low`, `medium`, `high`); an empty string leaves the provider's
  dynamic default. Applied to the agent and the compactor alike. A level the
  chosen model does not support is rejected by the API as a fatal HTTP 400.
- `gemini.retry.delays` — the waits between retries when the provider returns
  a transient failure: HTTP 429 (rate limit), 500, 503, 504, or a network
  error (connection failure, timeout). After the list is exhausted the last
  value is reused.
- `gemini.retry.max_wait_seconds` — the total waiting ceiling for retries
  (about 10 minutes by default). After that the turn fails with
  `FAILED_LLM_API`. Fatal provider errors (HTTP 400, 401, 403, 404 — bad
  request, invalid API key, missing permissions, unknown model) fail
  immediately without retries.
- `limits.message_rate` — a session is blocked after `max_messages` messages
  inside `window_seconds` (the spam guard, previously hard-coded to 15 per
  60 seconds).
- `limits.max_search_rounds` — how many product searches the agent may run
  inside one reply (3 by default, minimum 1). After every search the model
  sees the accumulated results of all previous searches (with their queries)
  and can refine the query, refer the customer to the operator, or move on to
  product selection. When the limit is reached the best candidates so far are
  selected; searches also stop early once the model is satisfied.
- `limits.max_api_calls_per_reply` — the maximum number of Gemini calls a
  single reply may consume across all stages (70 by default). A regular
  reply needs at most 6 calls (up to 3 searches, selection, final), so the
  limit only matters for product lists: a list of 10 items costs roughly
  20–60 calls plus one extra report call. When the budget runs out
  mid-list, the agent stops early and still delivers a partial report.
- `limits.list_mode_enabled` — the experimental product list feature
  (`true` by default). `false` removes the `start_product_list` tool from
  the decision stage entirely, so the agent never enters list mode.
- `limits.token_abuse` — if one session consumes more than `limit` tokens
  inside `window_seconds`, it is blocked in `blocked_sessions` exactly like a
  spam session. `0` disables it.
- `limits.context_overflow.auto_reset` — when a session's context alone is
  too large for the TPM budget (`true` by default), the session history is
  reset (archived, like `/reset`), the customer is told that the conversation
  became too long, and the reply is generated again from a fresh context.
  `false` makes the turn fail immediately instead.
- `limits.context_overflow.auto_compaction` — instead of resetting, a
  dedicated compactor prompt summarizes the whole session (with UTC
  timestamps) into a short bullet summary. The summarized messages are
  archived and replaced by one internal summary row, so the conversation can
  continue without the customer noticing. If compaction is impossible or
  fails, the `auto_reset` behavior is used as a fallback (when enabled).
  Compaction requests are recorded in `api_calls` with the
  `compaction` purpose and are intentionally exempt from the TPM wait (the
  request has to be larger than the limit it recovers from).
- `limits.context_overflow.compaction_model` — the model used for the
  compaction request; an empty string falls back to `gemini.model`.
- `limits.context_overflow.context_token_limit` — a per-session context
  threshold, independent of the TPM budget: when a single session's estimated
  request (history + system instruction + message) exceeds it, compaction
  fires even though the request would fit the per-minute budget. `0`
  disables it (compaction then only triggers when the request cannot fit
  `gemini.tpm_limit` at all).

A missing, invalid, or incomplete `config.json` falls back to safe defaults
(invalid values abort the startup with a clear error). Token usage comes from
the provider response (`usageMetadata` for Gemini). The pre-request estimate
uses the same conservative characters-per-token heuristic as the history size
check.

The previous pre-migration file is kept untouched as
`data/sales_agent_legacy.db`; the program no longer reads it.

## Local chat dashboard

Run the local operator dashboard in a separate PowerShell window:

```powershell
python src/admin_dashboard.py
```

Or use the combined runner, which also serves the dashboard at the same
address in the same process (see "Run everything with one command").

Open `http://127.0.0.1:8001`. The page lists the current SQLite sessions,
refreshes the selected conversation automatically, and can send a manual reply
to WhatsApp or Telegram sessions through the existing channel clients. It binds
only to localhost and is not exposed through the WhatsApp Cloudflare tunnel.

The full search result and the temporary selection response are not added to
the conversation history or SQLite. The final request contains only the chosen
product data. Python checks every candidate ID before it opens a product URL.

Detailed product data stays compact. A product without selectable options has
its price and stock at the top level. A configurable product has no top-level
price or stock; instead, every radio or dropdown value is returned in
`variants` with only its name, price, and stock quantity. Product descriptions
are included as plain text, with table rows kept on separate lines.

## Project layout

- `src/runner.py` runs Telegram, WhatsApp, and the dashboard in one process.
- `src/main.py` runs the terminal chat.
- `src/telegram_bot.py` receives and sends Telegram messages.
- `src/whatsapp_bot.py` connects the shared agent to WhatsApp Cloud API.
- `src/whatsapp_client.py` sends text messages through Meta Graph API.
- `src/whatsapp_webhook.py` verifies and parses Meta webhook events.
- `src/whatsapp_server.py` exposes the small Flask webhook endpoint.
- `src/whatsapp_store.py` prevents duplicate webhook processing.
- `src/reply_delivery.py` delivers normal replies and operator events to channels.
- `src/app_logging.py` configures private rotating application logs.
- `src/message_service.py` runs one customer message through the shared agent.
- `src/message_guard.py` blocks sessions that exceed the message rate limit.
- `src/session_coordinator.py` coordinates parallel sessions and message bursts.
- `src/agent.py` coordinates product search, selection, and the final answer.
- `src/agent_reply.py` separates the customer reply from an operator request.
- `src/chat.py` adds messages to a conversation history.
- `src/database.py` owns the SQLite schema, runs its migrations, and handles
  all conversation queries.
- `src/prompts.py` builds the system instruction from Markdown files.
- `src/config.py` loads local settings from `.env`.
- `src/gemini.py` makes the HTTP request to Gemini.
- `src/product_search.py` reads product search result pages.
- `src/product_parser.py` reads current product details and variants.
- `tests/test_chat.py` checks chat history and session isolation with Python's
  built-in `unittest` module.
