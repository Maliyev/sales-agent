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

The project reads simple `KEY=value` lines from `.env` itself. It uses
`requests` for the direct HTTP request to Gemini and does not use a Gemini SDK.
It uses a conservative character-based estimate and stops when a conversation
is longer than roughly 250,000 tokens.

The files in `prompts/` and `knowledge/store.md` are loaded when the program
starts. Edit them to change the assistant's behavior, then restart the bot.

When a customer asks about a product, the agent works in three short steps:

1. Gemini decides whether a product search is needed.
2. Search results receive temporary candidate IDs and Gemini keeps up to five
   relevant products.
3. Python loads current product details and Gemini writes the customer answer.

The full search result and the temporary selection response are not added to
the conversation history or SQLite. The final request contains only the chosen
product data. Python checks every candidate ID before it opens a product URL.

## Project layout

- `src/main.py` runs the terminal chat.
- `src/agent.py` coordinates product search, selection, and the final answer.
- `src/chat.py` adds messages to a conversation history.
- `src/database.py` saves and loads session histories from SQLite.
- `src/prompts.py` builds the system instruction from Markdown files.
- `src/config.py` loads local settings from `.env`.
- `src/gemini.py` makes the HTTP request to Gemini.
- `src/product_search.py` reads product search result pages.
- `src/product_parser.py` reads current product details and variants.
- `tests/test_chat.py` checks chat history and session isolation with Python's
  built-in `unittest` module.
