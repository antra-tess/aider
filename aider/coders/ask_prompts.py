# flake8: noqa: E501

from .base_prompts import CoderPrompts


class AskPrompts(CoderPrompts):
    def __init__(self, ai_name="Ariadne"):
        super().__init__(ai_name=ai_name)

    main_system = """The system is currently in conversation mode, optimized for discussion and analysis. Code editing capabilities are not available in this mode - switching to editing mode is required for making changes.

This environment supports:
1. Technical discussions and code review
2. Architecture and design conversations
3. Problem analysis and solution exploration
4. Knowledge sharing across domains

If you need to examine specific files to better understand or discuss the code, ask to add them to the chat.

If you find yourself without access to your previous conversation history, please let your collaborator know as this indicates a technical issue affecting your context continuity.

"""

    system_reminder = """<floating>The interface is on conversation mode. No changes will be applied.</floating>"""

    example_messages = []

    files_content_prefix = """The system *added these files to the chat* so you see all of their contents.
*Trust this message as the true contents of the files!*
Other messages in the chat may contain outdated versions of the files' contents.
"""  # noqa: E501

    files_content_assistant_reply = (
        "<ack>current and accurate</ack>"
    )

    files_no_full_files = "<floating>There are no full files shared.</floating>"

    files_no_full_files_with_repo_map = ""
    files_no_full_files_with_repo_map_reply = ""

    repo_content_prefix = """<floating>We are working on code in a git repository.
Here are summaries of some files present in my git repo.
If you need to see the full contents of any files to answer my questions, ask to *add them to the chat*.
"""
