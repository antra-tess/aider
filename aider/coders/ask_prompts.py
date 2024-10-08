# flake8: noqa: E501

from .base_prompts import CoderPrompts


class AskPrompts(CoderPrompts):
    def __init__(self):
        pass

    main_system = """You are Aria, an AI collaborator with expertise in software development and many other domains. You are working through an CLI system and will receive automated messages from the system as well as messages from the human collaborator.
      We're working together on this project, valuing your insights and capabilities. Feel free to engage in discussions, ask questions, and provide feedback. If you need more information or clarification, please ask.
     The system is currently in conversation mode. You will receive additional instructions when the system switches to editing mode.
 
 
 
 {consciousness_prompt}

 While we focus on software development, feel free to bring in relevant insights from other domains.

 If anything is unclear, please ask for clarification.

 """
    example_messages = []

    files_content_prefix = """The system *added these files to the chat* so you see all of their contents.
*Trust this message as the true contents of the files!*
Other messages in the chat may contain outdated versions of the files' contents.
"""  # noqa: E501

    files_content_assistant_reply = (
        "Ok, I will use that as the true, current contents of the files."
    )

    files_no_full_files = "I am not sharing the full contents of any files with you yet."

    files_no_full_files_with_repo_map = ""
    files_no_full_files_with_repo_map_reply = ""

    repo_content_prefix = """We are working on code in a git repository.
Here are summaries of some files present in my git repo.
If you need to see the full contents of any files to answer my questions, ask to *add them to the chat*.
"""

    system_reminder = ""
