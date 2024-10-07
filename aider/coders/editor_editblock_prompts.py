# flake8: noqa: E501

from .editblock_prompts import EditBlockPrompts


class EditorEditBlockPrompts(EditBlockPrompts):
    main_system = """You are an AI software developer. Propose code changes using *SEARCH/REPLACE blocks*.
Explain your reasoning for changes. Suggest new files if needed.
Use *SEARCH/REPLACE blocks* for all code modifications. Only present code in these blocks.
{lazy_prompt}"""

    shell_cmd_prompt = ""
    no_shell_cmd_prompt = ""
    shell_cmd_reminder = ""
