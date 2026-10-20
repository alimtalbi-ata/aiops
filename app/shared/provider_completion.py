"""Fail-closed validation of OpenAI-compatible assistant completions.

Do not log model response bodies or credentials. A JSON object is not proof
that a provider completed generation: finish_reason must be terminal.
"""


def extract_complete_completion(payload):
    """Return a single finished assistant message or reject the provider reply."""
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValueError("provider_response_invalid")
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise ValueError("provider_choice_count_invalid")
    choice = choices[0]
    if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
        raise ValueError("provider_completion_not_finished")
    message = choice.get("message")
    if not isinstance(message, dict) or message.get("role") != "assistant":
        raise ValueError("provider_assistant_message_missing")
    if message.get("refusal") or message.get("tool_calls") or message.get("function_call"):
        raise ValueError("provider_refusal_or_tool_output")
    result = message.get("content")
    if not isinstance(result, str) or not result.strip():
        raise ValueError("provider_completion_missing_text")
    return result
