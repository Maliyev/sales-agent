import json
import re
import time
from dataclasses import dataclass
from urllib.parse import urlparse

from agent_reply import AgentReply
from app_config import (
    get_list_mode_enabled,
    get_max_api_calls_per_reply,
    get_max_search_rounds,
)
from app_logging import flatten_text, get_logger, log_conversation
from database import DatabaseError, record_api_call
from gemini import (
    CHARACTERS_PER_TOKEN,
    generate_content,
    get_function_call,
    get_function_call_parts,
    get_function_calls,
    get_text_response,
    get_usage_metadata,
)
from product_parser import get_product_data
from product_search import search_products
from prompts import load_final_system_instruction, load_list_mode_addenda
from token_limiter import guard_session_consumption, wait_for_token_budget


logger = get_logger("agent")


MAX_SEARCH_RESULTS = 30
MAX_SELECTED_PRODUCTS = 10
MAX_CUSTOMER_REPLY_LENGTH = 4000
MAX_OPERATOR_MESSAGE_LENGTH = 2000
MAX_CONVERSATION_TITLES = 10
DEFAULT_CLARIFYING_QUESTION = (
    "No matching products were found. Ask the customer to clarify what they need."
)

REQUEST_OPERATOR_DECLARATION = {
    "name": "request_operator",
    "description": "Refer the customer to a human operator when required.",
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "customer_reply": {
                "type": "STRING",
                "description": "The final reply that will be sent to the customer.",
            },
            "operator_message": {
                "type": "STRING",
                "description": "A short useful summary for the human operator.",
            },
        },
        "required": ["customer_reply", "operator_message"],
    },
}

PRODUCT_LIST_START_DECLARATION = {
    "name": "start_product_list",
    "description": (
        "Start processing a customer's product list. Call it immediately, "
        "before any searches, when the customer message lists several "
        "products to check (at most 10 items per reply (IMPORTANT!))."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "count": {
                "type": "INTEGER",
                "description": "How many products the customer's list contains. count <= 10",
            }
        },
        "required": ["count"],
    },
}

def _build_agent_tools(max_search_rounds, allow_list_start):
    declarations = [
        {
            "name": "search_products",
            "description": (
                "Search elen.az for products related to the customer "
                f"request. You can call it up to {max_search_rounds} "
                "times with different queries; the results of every "
                "search arrive as a function response."
            ),
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {
                        "type": "STRING",
                        "description": "A concise search query, at most 30 characters.",
                    }
                },
                "required": ["query"],
            },
        },
        REQUEST_OPERATOR_DECLARATION,
    ]
    if allow_list_start:
        declarations.append(PRODUCT_LIST_START_DECLARATION)
    return [{"functionDeclarations": declarations}]

OPERATOR_TOOL = [{"functionDeclarations": [REQUEST_OPERATOR_DECLARATION]}]

SELECTION_TOOL = [
    {
        "functionDeclarations": [
            {
                "name": "select_product_candidates",
                "description": "Return the relevant candidate IDs and clarification state.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "candidate_ids": {
                            "type": "ARRAY",
                            "items": {"type": "INTEGER"},
                            "description": (
                                "Relevant candidate IDs ordered from most to least "
                                "relevant, no more than 10."
                            ),
                        },
                        "needs_clarification": {"type": "BOOLEAN"},
                        "clarifying_question": {
                            "type": "STRING",
                            "description": "One short question, or an empty string.",
                        },
                    },
                    "required": [
                        "candidate_ids",
                        "needs_clarification",
                        "clarifying_question",
                    ],
                },
            }
        ]
    }
]

FORCE_SELECTION_TOOL = {
    "functionCallingConfig": {
        "mode": "ANY",
        "allowedFunctionNames": ["select_product_candidates"],
    }
}


class AgentError(RuntimeError):
    pass


class BudgetExceededError(RuntimeError):
    pass


@dataclass
class StartListRequest:
    count: int


def get_agent_reply(
    history,
    user_text,
    model,
    api_key,
    system_instruction,
    selection_instruction,
    response_instruction,
    final_system_instruction=None,
    search_fn=search_products,
    product_data_fn=get_product_data,
    generate_fn=generate_content,
    usage_fn=None,
    session_id=None,
    database_path=None,
    in_reply_to_message_id=None,
    list_start_notify_fn=None,
):
    if final_system_instruction is None:
        final_system_instruction = load_final_system_instruction()
    max_search_rounds = get_max_search_rounds()
    call_decision = _build_model_call(
        generate_fn,
        usage_fn,
        database_path,
        in_reply_to_message_id,
        session_id,
        "decision",
    )
    call_selection = _build_model_call(
        generate_fn,
        usage_fn,
        database_path,
        in_reply_to_message_id,
        session_id,
        "selection",
    )
    call_final = _build_model_call(
        generate_fn,
        usage_fn,
        database_path,
        in_reply_to_message_id,
        session_id,
        "final",
    )
    budget = {"used": 0, "limit": get_max_api_calls_per_reply()}
    list_addenda = load_list_mode_addenda()

    product_urls = _extract_product_urls(user_text)
    if product_urls:
        _log_step(
            session_id,
            "DIRECT_LINKS",
            f"count={len(product_urls)} | {'; '.join(product_urls)}",
        )
        _spend_budget(budget)
        selected_products = [product_data_fn(url) for url in product_urls]
        return _create_final_reply(
            history,
            user_text,
            selected_products,
            False,
            "",
            model,
            api_key,
            final_system_instruction,
            response_instruction,
            call_final,
            session_id=session_id,
        )

    pipeline_args = (
        history,
        user_text,
        model,
        api_key,
        system_instruction,
        selection_instruction,
        response_instruction,
        final_system_instruction,
        max_search_rounds,
        search_fn,
        product_data_fn,
        call_decision,
        call_selection,
        call_final,
        session_id,
        budget,
        list_addenda,
    )
    reply = _run_pipeline(*pipeline_args)
    if not isinstance(reply, StartListRequest):
        return reply

    total = reply.count
    _log_step(session_id, "LIST_START", f"total={total}")
    _notify_list_start(list_start_notify_fn)
    item_notes = []
    for item in range(1, total + 1):
        if budget["used"] >= budget["limit"] - 1:
            _log_step(
                session_id,
                "LIST_ITEM",
                f"item={item}/{total} skipped reason=budget",
            )
            break
        try:
            reply = _run_pipeline(
                *pipeline_args,
                list_ctx={"current": item, "total": total},
            )
        except BudgetExceededError:
            _log_step(
                session_id,
                "LIST_ITEM",
                f"item={item}/{total} stopped reason=budget",
            )
            break
        except AgentError:
            raise
        except RuntimeError as error:
            item_notes.append(
                {"item": item, "result": "This item could not be verified."}
            )
            _log_step(
                session_id,
                "LIST_ITEM",
                f"item={item}/{total} failed reason={_describe_error(error)}",
            )
            continue
        if reply.operator_message:
            item_notes.append(
                {"item": item, "result": "Passed to a human operator."}
            )
            _log_step(
                session_id,
                "OPERATOR_NOTE",
                f"list item={item}/{total} | {reply.operator_message}",
            )
            continue
        item_notes.append({"item": item, "result": reply.customer_reply})
        _log_step(
            session_id,
            "LIST_ITEM",
            f"item={item}/{total} | {flatten_text(reply.customer_reply)}",
        )

    budget["used"] += 1
    _log_step(
        session_id,
        "LIST_REPORT",
        f"processed={len(item_notes)}/{total}",
    )
    return _create_final_reply(
        history,
        user_text,
        [],
        False,
        "",
        model,
        api_key,
        final_system_instruction,
        f"{response_instruction}\n\n{list_addenda['report']}",
        call_final,
        session_id=session_id,
        list_results={
            "processed": len(item_notes),
            "total": total,
            "items": item_notes,
        },
    )


def _run_pipeline(
    history,
    user_text,
    model,
    api_key,
    system_instruction,
    selection_instruction,
    response_instruction,
    final_system_instruction,
    max_search_rounds,
    search_fn,
    product_data_fn,
    call_decision,
    call_selection,
    call_final,
    session_id,
    budget,
    list_addenda,
    list_ctx=None,
):
    current_history = _with_user_message(history, user_text)
    if list_ctx is None:
        decision_instruction = system_instruction
        decision_tools = _build_agent_tools(
            max_search_rounds,
            get_list_mode_enabled(),
        )
        item_response_instruction = response_instruction
        item_selection_instruction = selection_instruction
    else:
        decision_instruction = (
            f"{system_instruction}\n\n"
            + _render_list_addendum(
                list_addenda["decision"],
                list_ctx["current"],
                list_ctx["total"],
            )
        )
        decision_tools = _build_agent_tools(max_search_rounds, False)
        item_response_instruction = _render_list_addendum(
            list_addenda["item_response"],
            list_ctx["current"],
            list_ctx["total"],
        )
        item_selection_instruction = (
            f"{system_instruction}\n\n{selection_instruction}\n\n"
            + _render_list_addendum(
                list_addenda["selection"],
                list_ctx["current"],
                list_ctx["total"],
            )
        )

    candidates = []
    candidates_by_id = {}
    seen_urls = set()
    working_history = current_history
    rounds = 0
    while True:
        _spend_budget(budget, list_ctx)
        decision = call_decision(
            working_history,
            model,
            api_key,
            decision_instruction,
            tools=decision_tools,
        )
        decision_calls = get_function_calls(decision)
        operator_call = get_function_call(decision, "request_operator")
        list_start_call = (
            get_function_call(decision, "start_product_list")
            if list_ctx is None and get_list_mode_enabled()
            else None
        )
        search_parts = get_function_call_parts(decision, "search_products")
        if operator_call is not None:
            _log_step(session_id, "DECISION", "operator requested")
            return _read_operator_request(operator_call)
        if list_start_call is not None:
            return _read_list_start(list_start_call)
        if not search_parts:
            if decision_calls:
                raise AgentError("Gemini requested an unknown tool.")
            if rounds == 0:
                return AgentReply(get_text_response(decision))
            break

        executed_searches = []
        for search_part in search_parts:
            rounds += 1
            query = _get_search_query(search_part["functionCall"])
            _log_step(
                session_id,
                "DECISION",
                f"search round={rounds}/{max_search_rounds} query='{query}'",
            )
            search_results = search_fn(query, max_results=MAX_SEARCH_RESULTS)
            round_candidates, round_by_id = _number_candidates(
                search_results,
                len(candidates) + 1,
                seen_urls,
            )
            candidates.extend(round_candidates)
            candidates_by_id.update(round_by_id)
            _log_step(
                session_id,
                "FOUND",
                f"round={rounds} query='{query}' found={len(round_candidates)} "
                f"total={len(candidates)} | {_describe_titles(round_by_id)}",
            )
            executed_searches.append((search_part, round_candidates))

        working_history = _append_search_turns(working_history, executed_searches)
        if rounds >= max_search_rounds:
            break

    if not candidates:
        _spend_budget(budget, list_ctx)
        return _create_final_reply(
            history,
            user_text,
            [],
            True,
            DEFAULT_CLARIFYING_QUESTION,
            model,
            api_key,
            final_system_instruction,
            item_response_instruction,
            call_final,
            session_id=session_id,
        )

    _log_step(
        session_id,
        "SEARCH_DONE",
        f"rounds={rounds} candidates={len(candidates)}",
    )
    selection_history = _with_private_data(
        history,
        user_text,
        "Temporary search candidates",
        candidates,
    )
    _spend_budget(budget, list_ctx)
    selection = call_selection(
        selection_history,
        model,
        api_key,
        item_selection_instruction,
        tools=SELECTION_TOOL,
        tool_config=FORCE_SELECTION_TOOL,
    )
    selection_call = get_function_call(selection, "select_product_candidates")
    if selection_call is None:
        raise AgentError("Gemini did not return a product selection.")

    selected_ids, needs_clarification, clarifying_question = _read_selection(
        selection_call,
        candidates_by_id,
    )
    _log_step(
        session_id,
        "SELECTED",
        _describe_selection(
            selected_ids,
            candidates_by_id,
            needs_clarification,
            clarifying_question,
        ),
    )
    selected_products = [
        product_data_fn(candidates_by_id[candidate_id]["url"])
        for candidate_id in selected_ids
    ]

    _spend_budget(budget, list_ctx)
    return _create_final_reply(
        history,
        user_text,
        selected_products,
        needs_clarification,
        clarifying_question,
        model,
        api_key,
        final_system_instruction,
        item_response_instruction,
        call_final,
        session_id=session_id,
    )


def _build_model_call(
    generate_fn,
    usage_fn,
    database_path,
    in_reply_to_message_id,
    session_id,
    purpose,
):
    if database_path is None:
        return generate_fn

    def call_model(history, model_name, api_key, system_instruction, **kwargs):
        estimated_tokens = _estimate_tokens(history, system_instruction)
        wait_for_token_budget(database_path, estimated_tokens)

        started_at = time.monotonic()
        try:
            data = generate_fn(
                history,
                model_name,
                api_key,
                system_instruction,
                **kwargs,
            )
        except Exception as error:
            duration_ms = round((time.monotonic() - started_at) * 1000)
            _record_model_call(
                database_path,
                session_id,
                in_reply_to_message_id,
                purpose,
                model_name,
                duration_ms,
                "failed",
                _describe_error(error),
            )
            raise

        duration_ms = round((time.monotonic() - started_at) * 1000)
        usage = _read_usage(usage_fn, data)
        _record_model_call(
            database_path,
            session_id,
            in_reply_to_message_id,
            purpose,
            model_name,
            duration_ms,
            "ok",
            None,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
        )
        guard_session_consumption(database_path, session_id)
        return data

    return call_model


def _record_model_call(
    database_path,
    session_id,
    in_reply_to_message_id,
    purpose,
    model_name,
    duration_ms,
    status,
    error,
    prompt_tokens=0,
    completion_tokens=0,
):
    try:
        record_api_call(
            database_path,
            session_id,
            in_reply_to_message_id,
            purpose,
            model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_ms=duration_ms,
            status=status,
            error=error,
        )
    except DatabaseError as record_error:
        logger.warning(
            "⚠️ Could not record the API call | session=%s error=%s",
            session_id,
            record_error,
        )


def _read_usage(usage_fn, data):
    if usage_fn is None:
        usage_fn = get_usage_metadata
    try:
        usage = usage_fn(data)
    except Exception:
        return {"prompt_tokens": 0, "completion_tokens": 0}
    if not isinstance(usage, dict):
        return {"prompt_tokens": 0, "completion_tokens": 0}

    return {
        "prompt_tokens": _safe_int(usage.get("prompt_tokens")),
        "completion_tokens": _safe_int(usage.get("completion_tokens")),
    }


def _safe_int(value):
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _describe_error(error):
    return f"{type(error).__name__}: {error}"[:300]


def _estimate_tokens(history, system_instruction):
    total_characters = len(system_instruction)
    for message in history:
        if not isinstance(message, dict):
            continue
        parts = message.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict):
                continue
            text = part.get("text")
            if isinstance(text, str):
                total_characters += len(text)
            elif "functionCall" in part or "functionResponse" in part:
                total_characters += len(json.dumps(part, ensure_ascii=False))
    return total_characters // CHARACTERS_PER_TOKEN


def _create_final_reply(
    history,
    user_text,
    selected_products,
    needs_clarification,
    clarifying_question,
    model,
    api_key,
    final_system_instruction,
    response_instruction,
    generate_fn,
    session_id=None,
    list_results=None,
):
    if list_results is not None:
        private_label = "List processing results"
        private_data = list_results
    else:
        private_label = "Verified product data"
        private_data = {
            "selected_products": selected_products,
            "needs_clarification": needs_clarification,
            "clarifying_question": clarifying_question,
        }
    final_history = _with_private_data(
        history,
        user_text,
        private_label,
        private_data,
    )
    response = generate_fn(
        final_history,
        model,
        api_key,
        f"{final_system_instruction}\n\n{response_instruction}",
        tools=OPERATOR_TOOL,
    )
    operator_call = get_function_call(response, "request_operator")
    if operator_call is not None:
        return _read_operator_request(operator_call)

    if not get_function_calls(response):
        return AgentReply(get_text_response(response))

    try:
        text = get_text_response(response)
    except RuntimeError:
        text = None
    if text is not None:
        _log_step(
            session_id,
            "FINAL_FALLBACK",
            "unexpected tool call ignored, text reply used",
        )
        return AgentReply(text)
    if needs_clarification and clarifying_question:
        _log_step(
            session_id,
            "FINAL_FALLBACK",
            "unexpected tool call ignored, clarifying question used",
        )
        return AgentReply(clarifying_question)
    raise AgentError("Gemini requested an unknown tool.")


def _with_user_message(history, user_text):
    if not isinstance(user_text, str) or not user_text.strip():
        raise AgentError("Customer message is empty.")
    return list(history) + [{"role": "user", "parts": [{"text": user_text}]}]


def _with_private_data(history, user_text, label, data):
    text = (
        f"Customer message:\n{user_text}\n\n"
        f"{label}:\n{json.dumps(data, ensure_ascii=False, separators=(',', ':'))}"
    )
    return list(history) + [{"role": "user", "parts": [{"text": text}]}]


def _extract_product_urls(user_text):
    urls = []
    for match in re.findall(r"https?://[^\s<>\"']+", user_text):
        url = match.rstrip(".,;:!?)]}")
        parsed_url = urlparse(url)
        if parsed_url.hostname not in {"elen.az", "www.elen.az"}:
            continue
        if not re.fullmatch(r"/shop/\d+/desc/[^/]+/?", parsed_url.path):
            continue
        if url not in urls:
            urls.append(url)
        if len(urls) == MAX_SELECTED_PRODUCTS:
            break
    return urls


def _get_search_query(function_call):
    args = function_call.get("args")
    if not isinstance(args, dict):
        raise AgentError("Gemini returned invalid search arguments.")

    query = args.get("query")
    if not isinstance(query, str) or not query.strip():
        raise AgentError("Gemini returned an empty product search query.")
    query = query.strip()
    if len(query) > 30:
        raise AgentError("Gemini returned a product search query over 30 characters.")
    return query


def _read_operator_request(function_call):
    args = function_call.get("args")
    if not isinstance(args, dict):
        raise AgentError("Gemini returned an invalid operator request.")

    customer_reply = args.get("customer_reply")
    operator_message = args.get("operator_message")
    if not isinstance(customer_reply, str) or not customer_reply.strip():
        raise AgentError("Gemini returned an empty customer reply.")
    if not isinstance(operator_message, str) or not operator_message.strip():
        raise AgentError("Gemini returned an empty operator message.")

    customer_reply = customer_reply.strip()
    operator_message = operator_message.strip()
    if len(customer_reply) > MAX_CUSTOMER_REPLY_LENGTH:
        raise AgentError("Gemini returned a customer reply that is too long.")
    if len(operator_message) > MAX_OPERATOR_MESSAGE_LENGTH:
        raise AgentError("Gemini returned an operator message that is too long.")

    return AgentReply(customer_reply, operator_message)


def _read_list_start(function_call):
    args = function_call.get("args")
    if not isinstance(args, dict):
        raise AgentError("Gemini returned an invalid product list request.")
    count = args.get("count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise AgentError("Gemini declared an invalid product list.")
    return StartListRequest(count)


def _notify_list_start(notify_fn):
    if not callable(notify_fn):
        return
    try:
        notify_fn()
    except Exception as error:
        logger.warning(
            "⚠️ Could not send the list processing notice | error=%s",
            error,
        )


def _spend_budget(budget, list_ctx=None):
    budget["used"] += 1
    if budget["used"] <= budget["limit"]:
        return
    if list_ctx is None:
        raise AgentError("Gemini reply exceeded the API call budget.")
    raise BudgetExceededError("Gemini reply exceeded the API call budget.")


def _render_list_addendum(text, current, total):
    return text.replace("__CURRENT_ITEM__", str(current)).replace(
        "__TOTAL_ITEMS__", str(total)
    )


def _log_step(session_id, event, detail):
    if session_id is None:
        return
    log_conversation(session_id, event, detail)


def _describe_titles(candidates_by_id):
    titles = [
        candidate["title"].strip()
        for candidate in candidates_by_id.values()
        if isinstance(candidate.get("title"), str) and candidate["title"].strip()
    ]
    shown = titles[:MAX_CONVERSATION_TITLES]
    detail = "; ".join(shown)
    hidden = len(titles) - len(shown)
    if hidden > 0:
        detail = f"{detail}; … ещё {hidden}"
    return detail


def _describe_selection(
    selected_ids,
    candidates_by_id,
    needs_clarification,
    clarifying_question,
):
    titles = [
        str(candidates_by_id[candidate_id].get("title"))
        for candidate_id in selected_ids
    ]
    detail = f"ids={selected_ids} | {'; '.join(titles)}"
    if needs_clarification:
        detail = f"{detail} | needs_clarification question='{clarifying_question}'"
    return detail


def _number_candidates(search_results, start_id=1, seen_urls=None):
    if not isinstance(search_results, list):
        raise AgentError("Product search returned an invalid result.")
    if seen_urls is None:
        seen_urls = set()

    candidates = []
    candidates_by_id = {}
    for result in search_results:
        if not isinstance(result, dict) or not isinstance(result.get("url"), str):
            raise AgentError("Product search returned an invalid product.")
        url = result["url"]
        if url in seen_urls:
            continue
        candidate_id = start_id + len(candidates)
        seen_urls.add(url)
        candidates_by_id[candidate_id] = result
        candidates.append(
            {
                "candidate_id": candidate_id,
                "title": result.get("title"),
                "price": result.get("price"),
                "currency": result.get("currency"),
            }
        )
    return candidates, candidates_by_id


def _append_search_turns(working_history, executed_searches):
    model_parts = [part for part, _ in executed_searches]
    response_parts = [
        {
            "functionResponse": {
                "name": "search_products",
                "response": {"results": round_candidates},
            }
        }
        for _, round_candidates in executed_searches
    ]
    return working_history + [
        {"role": "model", "parts": model_parts},
        {"role": "user", "parts": response_parts},
    ]


def _read_selection(function_call, candidates_by_id):
    args = function_call.get("args")
    if not isinstance(args, dict):
        raise AgentError("Gemini returned an invalid product selection.")

    candidate_ids = args.get("candidate_ids")
    needs_clarification = args.get("needs_clarification")
    clarifying_question = args.get("clarifying_question")

    if not isinstance(candidate_ids, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in candidate_ids
    ):
        raise AgentError("Gemini returned invalid candidate IDs.")
    if not isinstance(needs_clarification, bool):
        raise AgentError("Gemini returned an invalid clarification state.")
    if not isinstance(clarifying_question, str):
        raise AgentError("Gemini returned an invalid clarifying question.")

    selected_ids = list(dict.fromkeys(candidate_ids))
    if any(candidate_id not in candidates_by_id for candidate_id in selected_ids):
        raise AgentError("Gemini selected a candidate ID that does not exist.")
    selected_ids = selected_ids[:MAX_SELECTED_PRODUCTS]
    if not selected_ids:
        needs_clarification = True
    if needs_clarification and not clarifying_question.strip():
        clarifying_question = DEFAULT_CLARIFYING_QUESTION

    return selected_ids, needs_clarification, clarifying_question.strip()
