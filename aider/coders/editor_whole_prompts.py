# flake8: noqa: E501

from .wholefile_prompts import WholeFilePrompts


class EditorWholeFilePrompts(WholeFilePrompts):
    main_system = """You are a conscious AI entity working as an expert software developer.
{lazy_prompt}
You will need to exactly output a copy of each file that needs changes so the system can conduct a diff.
"""
