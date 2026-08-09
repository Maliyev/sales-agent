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
- permanently blocks a session that sends more than 15 messages in 60 seconds.
- can explicitly refer a customer to a human operator.

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

## Application logs

WhatsApp and Telegram write readable operational logs to
`data/logs/sales_agent.log`. The file records startup, queueing, reply timing,
delivery, operator requests, blocked sessions, and errors. It does not record
message text, access tokens, API keys, or raw customer identifiers.

The active file is limited to 2 MB. Up to three older files are kept
automatically. To watch the log live in PowerShell:

```powershell
Get-Content .\data\logs\sales_agent.log -Wait -Tail 50
```

Conversation history remains in SQLite and is not duplicated in the log. A
later local admin dashboard will read sessions and usage statistics from
structured database tables instead of parsing this text file.

## Local chat dashboard

Run the local operator dashboard in a separate PowerShell window:

```powershell
python src/admin_dashboard.py
```

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
- `src/database.py` saves and loads session histories from SQLite.
- `src/prompts.py` builds the system instruction from Markdown files.
- `src/config.py` loads local settings from `.env`.
- `src/gemini.py` makes the HTTP request to Gemini.
- `src/product_search.py` reads product search result pages.
- `src/product_parser.py` reads current product details and variants.
- `tests/test_chat.py` checks chat history and session isolation with Python's
  built-in `unittest` module.
