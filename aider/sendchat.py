import hashlib
import json
import os
import time
from pathlib import Path

from aider.dump import dump  # noqa: F401
from aider.exceptions import LiteLLMExceptions
from aider.llm import litellm
from aider.utils import format_messages

import openai

# from diskcache import Cache


CACHE_PATH = ".aider.send.cache.v1"
CACHE = None
# CACHE = Cache(CACHE_PATH)

RETRY_TIMEOUT = 60


def sanity_check_messages(messages):
    """Check if messages alternate between user and assistant roles.
    System messages can be interspersed anywhere.
    Also verifies the last non-system message is from the user.
    Returns True if valid, False otherwise."""
    last_role = None
    last_non_system_role = None

    for msg in messages:
        role = msg.get("role")
        if role == "system":
            continue

        if last_role and role == last_role:
            turns = format_messages(messages)
            raise ValueError("Messages don't properly alternate user/assistant:\n\n" + turns)

        last_role = role
        last_non_system_role = role

    # Ensure last non-system message is from user
    return last_non_system_role == "user"


def ensure_alternating_roles(messages):
    """Ensure messages alternate between 'assistant' and 'user' roles.

    Inserts empty messages of the opposite role when consecutive messages
    of the same role are found.

    Args:
        messages: List of message dictionaries with 'role' and 'content' keys.

    Returns:
        List of messages with alternating roles.
    """
    if not messages:
        return messages

    fixed_messages = []
    prev_role = None

    for msg in messages:
        current_role = msg.get("role")  # Get 'role', None if missing

        # If current role same as previous, insert empty message
        # of the opposite role
        if current_role == prev_role:
            if current_role == "user":
                fixed_messages.append({"role": "assistant", "content": ""})
            else:
                fixed_messages.append({"role": "user", "content": ""})

        fixed_messages.append(msg)
        prev_role = current_role

    return fixed_messages


def ensure_request_logs_dir():
    logs_dir = Path("request_logs")
    logs_dir.mkdir(exist_ok=True)
    return logs_dir

def get_next_log_number(logs_dir):
    existing_logs = [f for f in logs_dir.glob("request_*.json")]
    if not existing_logs:
        return 1
    numbers = [int(f.stem.split('_')[1]) for f in existing_logs]
    return max(numbers) + 1

def log_request(request_data, response_data, logs_dir):
    log_num = get_next_log_number(logs_dir)
    log_file = logs_dir / f"request_{log_num}.json"

    log_entry = {
        "request": request_data,
        "response": response_data
    }

    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump(log_entry, f, indent=2, default=str)

def send_completion(
    model_name,
    messages,
    functions,
    stream,
    temperature=0,
    extra_params=None,
):
    #
    #
    if os.environ.get("AIDER_SANITY_CHECK_TURNS"):
        sanity_check_messages(messages)
    #
    #

    if "deepseek-reasoner" in model_name:
        messages = ensure_alternating_roles(messages)

    kwargs = dict(
        model=model_name,
        messages=messages,
        stream=stream,
    )
    if temperature is not None:
        kwargs["temperature"] = temperature

    if functions is not None:
        function = functions[0]
        kwargs["tools"] = [dict(type="function", function=function)]
        kwargs["tool_choice"] = {"type": "function", "function": {"name": function["name"]}}

    if extra_params is not None:
        kwargs.update(extra_params)

    key = json.dumps(kwargs, sort_keys=True).encode()

    # Generate SHA1 hash of kwargs and append it to chat_completion_call_hashes
    hash_object = hashlib.sha1(key)

    if not stream and CACHE is not None and key in CACHE:
        return hash_object, CACHE[key]

    # Create logs directory and prepare request data
    logs_dir = ensure_request_logs_dir()
    
    # Track only original values that undergo transformation
    original_params = {}
    if functions is not None:
        original_params["functions"] = functions
    if extra_params is not None:
        original_params["extra_params"] = extra_params
    if "deepseek-reasoner" in model_name and messages:
        original_params["messages"] = messages

    request_data = {
        "original_params": original_params,
        "kwargs": kwargs  # final API parameters
    }

    res = litellm.completion(**kwargs)

    # Log both request and response
    response_data = res.model_dump() if hasattr(res, 'model_dump') else str(res)
    log_request(request_data, response_data, logs_dir)

    if not stream and CACHE is not None:
        CACHE[key] = res

    return hash_object, res


def simple_send_with_retries(model, messages, **kwargs):
    litellm_ex = LiteLLMExceptions()

    if "deepseek-reasoner" in model.name:
        messages = ensure_alternating_roles(messages)

    retry_delay = 0.125
    while True:
        try:
            old_kwargs = kwargs
            kwargs = {
                "model_name": model.name,
                "messages": messages,
                "functions": None,
                "stream": False,
                "temperature": None if not model.use_temperature else 0,
                "extra_params": model.extra_params,
            }
            kwargs['extra_params'].update(old_kwargs)
            _hash, response = send_completion(**kwargs)
            if not response or not hasattr(response, "choices") or not response.choices:
                return None
            return response.choices[0].message.content
        except litellm_ex.exceptions_tuple() as err:
            ex_info = litellm_ex.get_ex_info(err)

            print(str(err))
            if ex_info.description:
                print(ex_info.description)

            should_retry = ex_info.retry
            if should_retry:
                retry_delay *= 2
                if retry_delay > RETRY_TIMEOUT:
                    should_retry = False

            if not should_retry:
                return None

            print(f"Retrying in {retry_delay:.1f} seconds...")
            time.sleep(retry_delay)
            continue
        except AttributeError as e:
            print(f"Error in simple_send_with_retries: {e}")
            return None
