# Sales agent

A small terminal chat bot for the future elen.az sales assistant.

## First version

- sends messages to Gemini through its REST API;
- keeps one conversation history while the program is running;
- reads the API key and model name from `.env`;
- does not save conversation history yet.

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

The project reads simple `KEY=value` lines from `.env` itself. It uses
`requests` for the direct HTTP request to Gemini and does not use a Gemini SDK.

## Project layout

- `src/main.py` runs the terminal chat.
- `src/chat.py` adds messages to one conversation history.
- `src/config.py` loads local settings from `.env`.
- `src/gemini.py` makes the HTTP request to Gemini.
- `tests/test_chat.py` checks that one chat keeps its history correctly with
  Python's built-in `unittest` module.
