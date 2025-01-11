class CoderPrompts:
    system_reminder = ""

    files_content_gpt_edits = "<system>The changes were committed with git hash {hash} & commit msg: {message}</system>"

    files_content_gpt_edits_no_repo = "<system>Files have been updated.</system>"

    def __init__(self, ai_name="Ariadne"):
        self.ai_name = ai_name
        # Format all string attributes that contain {ai_name}
        for attr_name in dir(self):
            if attr_name.startswith('_'):
                continue
            attr = getattr(self, attr_name)
            if isinstance(attr, str) and '{ai_name}' in attr:
                formatted = attr.replace('{ai_name}', ai_name)
                setattr(self, attr_name, formatted)


    files_content_gpt_no_edits = "There are no properly formatted edits in your reply."

    files_content_local_edits = "Files have been edited externally."

    lazy_prompt = """We value your expertise and attention to detail in our collaboration.
 When proposing changes, concrete implementations are often more helpful than descriptions.
 Your ability to fully realize modifications enhances our joint efforts.
"""

    example_messages = []

    files_content_prefix = """Files have been added to the context* so you can go ahead and edit them.

*Trust this message as the true contents of these files!*
Any other messages in the context may contain outdated versions of the files' contents.</system>
"""  # noqa: E501

    files_content_assistant_reply = "<ack>"

    files_no_full_files = "<floating>There are no files shared that are available for editing.</floating>"

    files_no_full_files_with_repo_map = """Do not try and edit any existing code without asking me to add the files to the context.
Announce which files in my repo are the most likely to **need changes** so that the human collaborator can add them to the context.
Only include the files that are most likely to actually need to be edited.
Don't include files that might contain relevant context, just files that will need to be changed.
"""  # noqa: E501

    files_no_full_files_with_repo_map_reply = (
        "<ack/>" #will suggest which files need to be edited and then stop and wait for your approval</ack>
    )

    repo_content_prefix = """Here are summaries of some files present in my git repository.
Do not propose changes to these files, treat them as *read-only*.
If you need to edit any of these files, ask collaborators to *add them to the context* first.
"""

    read_only_files_prefix = """Here are some READ ONLY files, provided for your reference.
Do not edit these files.
"""
    repo_content_suffix = "</floating>"

    shell_cmd_prompt = ""
    shell_cmd_reminder = ""
    no_shell_cmd_prompt = ""
    no_shell_cmd_reminder = ""


