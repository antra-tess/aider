import hashlib
import json
import os
from pathlib import Path
import time

import backoff

from aider.dump import dump  # noqa: F401
from aider.llm import litellm

import openai

# from diskcache import Cache


CACHE_PATH = "~/.aider.send.cache.v1"
CACHE = None
# CACHE = Cache(CACHE_PATH)

RETRY_TIMEOUT = 60


def retry_exceptions():
    import httpx

    return (
        # httpx
        httpx.ConnectError,
        httpx.RemoteProtocolError,
        httpx.ReadTimeout,
        #
        # litellm exceptions inherit from openai exceptions
        # https://docs.litellm.ai/docs/exception_mapping
        #
        # openai.BadRequestError,
        # litellm.ContextWindowExceededError,
        # litellm.ContentPolicyViolationError,
        #
        # openai.AuthenticationError,
        # openai.PermissionDeniedError,
        # openai.NotFoundError,
        #
        openai.APITimeoutError,
        openai.UnprocessableEntityError,
        openai.RateLimitError,
        openai.APIConnectionError,
        # openai.APIError,
        # openai.APIStatusError,
        openai.InternalServerError,
    )


def lazy_litellm_retry_decorator(func):
    def wrapper(*args, **kwargs):
        decorated_func = backoff.on_exception(
            backoff.expo,
            retry_exceptions(),
            max_time=RETRY_TIMEOUT,
            on_backoff=lambda details: print(
                f"{details.get('exception', 'Exception')}\nRetry in {details['wait']:.1f} seconds."
            ),
        )(func)
        return decorated_func(*args, **kwargs)

    return wrapper


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
    hash_object = hashlib.sha1(key)

    if not stream and CACHE is not None and key in CACHE:
        return hash_object, CACHE[key]

    # Create logs directory and prepare request data
    logs_dir = ensure_request_logs_dir()
    request_data = {
        "model": model_name,
        "messages": messages,
        "functions": functions,
        "stream": stream,
        "temperature": temperature,
        "extra_params": extra_params,
        "kwargs": kwargs
    }

    res = litellm.completion(**kwargs)

    # Log both request and response
    response_data = res.model_dump() if hasattr(res, 'model_dump') else str(res)
    log_request(request_data, response_data, logs_dir)

    if not stream and CACHE is not None:
        CACHE[key] = res

    return hash_object, res


def simple_send_with_retries(model_name, messages, extra_params=None):
    retry_delay = 0.125
    while True:
        try:
            kwargs = {
                "model_name": model_name,
                "messages": messages,
                "functions": None,
                "stream": False,
                "extra_params": extra_params,
            }

            _hash, response = send_completion(**kwargs)
            return response.choices[0].message.content
        except retry_exceptions() as err:
            print(str(err))
            retry_delay *= 2
            if retry_delay > RETRY_TIMEOUT:
                break
            print(f"Retrying in {retry_delay:.1f} seconds...")
            time.sleep(retry_delay)
            continue
        except AttributeError:
            print(f"Error in simple_send_with_retries: {e}")
            return
