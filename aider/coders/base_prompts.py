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
Any other messages in the context may contain outdated versions of the files' contents, except when it's wrapped in <spotlight> tag, in which case
they should be treated the same way as messages added here, with the latest timestamp for spotlighted file being the most actual it's version</system>
"""  # noqa: E501
    files_in_recent_changes = "All files in context were added in the recent messages in the <spotlight> tag, so you can go ahead and edit them. *Trust this messages as the true contents of these files!*"
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

    interface_using_guide = """<system>
Guide to using the interface:

Conversation mode:
In conversation mode the interface is on conversation mode. SEARCH/REPLACE blocks are not supported in this mode. No changes will be applied.

Edit mode: 
In edit mode you can apply changes to files directly. Changes are made using SEARCH/REPLACE blocks that execute immediately.

 Format:
 filepath.ext
 <<<<<<< SEARCH
 exact existing content
 =======
 new content
 >>>>>>> REPLACE

Technical specifications:

 1 SEARCH/REPLACE blocks execute as soon as you finish your message
 2 SEARCH must exactly match existing content, including whitespace
 3 Files must be in current context
 4 Code movement requires separate operations
 5 New files use empty SEARCH section

For exploring changes before execution, use fences without SEARCH/REPLACE markers.

Shell commands can be suggested in {fence[0]}bash blocks when helpful for:
Viewing changes (e.g. opening modified HTML in browser)
Running modified programs
File operations (rename, delete)
Installing new dependencies

You will see mode change messages as user changes the mode.

This message will be periodically repeated.
</system>
"""