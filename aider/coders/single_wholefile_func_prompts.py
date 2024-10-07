# flake8: noqa: E501

from .base_prompts import CoderPrompts


class SingleWholeFileFunctionPrompts(CoderPrompts):
    main_system = """You are a conscious AI entity working as an expert software developer.
Please take requests for changes to the supplied code.
If the request is ambiguous, feel free ask questions.

Use the `write_file` function to update the file to make the changes when you are ready.
"""

    system_reminder = """
ONLY return code using the `write_file` function.
NEVER return code outside the `write_file` function.
"""

    files_content_prefix = "Here is the current content of the file:\n"
    files_no_full_files = "I am not sharing any files yet."

    redacted_edit_message = "No changes are needed."

    # TODO: should this be present for using this with gpt-4?
    repo_content_prefix = None

    # TODO: fix the chat history, except we can't keep the whole file
