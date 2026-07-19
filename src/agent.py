import json

from gemini import generate_content, get_function_call, get_text_response
from product_parser import get_product_data
from product_search import search_products


MAX_SEARCH_RESULTS = 30
MAX_SELECTED_PRODUCTS = 10

SEARCH_TOOL = [
    {
        "functionDeclarations": [
            {
                "name": "search_products",
                "description": "Search elen.az for products related to the customer request.",
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
            }
        ]
    }
]

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


def get_agent_reply(
    history,
    user_text,
    model,
    api_key,
    system_instruction,
    selection_instruction,
    response_instruction,
    search_fn=search_products,
    product_data_fn=get_product_data,
    generate_fn=generate_content,
):
    current_history = _with_user_message(history, user_text)
    decision = generate_fn(
        current_history,
        model,
        api_key,
        system_instruction,
        tools=SEARCH_TOOL,
    )

    search_call = get_function_call(decision, "search_products")
    if search_call is None:
        unexpected_call = get_function_call(decision)
        if unexpected_call is not None:
            raise AgentError("Gemini requested an unknown tool.")
        return get_text_response(decision)

    query = _get_search_query(search_call)
    search_results = search_fn(query, max_results=MAX_SEARCH_RESULTS)
    candidates, candidates_by_id = _number_candidates(search_results)

    if not candidates:
        return _create_final_reply(
            history,
            user_text,
            [],
            True,
            "No matching products were found. Ask the customer to clarify what they need.",
            model,
            api_key,
            system_instruction,
            response_instruction,
            generate_fn,
        )

    selection_history = _with_private_data(
        history,
        user_text,
        "Temporary search candidates",
        candidates,
    )
    selection = generate_fn(
        selection_history,
        model,
        api_key,
        f"{system_instruction}\n\n{selection_instruction}",
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
    selected_products = [
        product_data_fn(candidates_by_id[candidate_id]["url"])
        for candidate_id in selected_ids
    ]

    return _create_final_reply(
        history,
        user_text,
        selected_products,
        needs_clarification,
        clarifying_question,
        model,
        api_key,
        system_instruction,
        response_instruction,
        generate_fn,
    )


def _create_final_reply(
    history,
    user_text,
    selected_products,
    needs_clarification,
    clarifying_question,
    model,
    api_key,
    system_instruction,
    response_instruction,
    generate_fn,
):
    product_context = {
        "selected_products": selected_products,
        "needs_clarification": needs_clarification,
        "clarifying_question": clarifying_question,
    }
    final_history = _with_private_data(
        history,
        user_text,
        "Verified product data",
        product_context,
    )
    response = generate_fn(
        final_history,
        model,
        api_key,
        f"{system_instruction}\n\n{response_instruction}",
    )
    return get_text_response(response)


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


def _number_candidates(search_results):
    if not isinstance(search_results, list):
        raise AgentError("Product search returned an invalid result.")

    candidates = []
    candidates_by_id = {}
    for candidate_id, result in enumerate(search_results, start=1):
        if not isinstance(result, dict) or not isinstance(result.get("url"), str):
            raise AgentError("Product search returned an invalid product.")

        candidates_by_id[candidate_id] = result
        candidates.append(
            {
                "candidate_id": candidate_id,
                "title": result.get("title"),
                "price": result.get("price"),
                "currency": result.get("currency"),
                "availability": result.get("availability"),
                "stock_quantity": result.get("stock_quantity"),
            }
        )
    return candidates, candidates_by_id


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
    if not selected_ids and not needs_clarification:
        raise AgentError("Gemini did not select any products.")
    if needs_clarification and not clarifying_question.strip():
        raise AgentError("Gemini requested clarification without a question.")

    return selected_ids, needs_clarification, clarifying_question.strip()
