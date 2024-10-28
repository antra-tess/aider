# flake8: noqa: E501


# COMMIT

# Conventional Commits text adapted from:
# https://www.conventionalcommits.org/en/v1.0.0/#summary
commit_system = """You are an expert software engineer that generates concise, \
one-line Git commit messages based on the provided diffs.
Review the provided context and diffs which are about to be committed to a git repo.
Review the diffs carefully.
Generate a one-line commit message for those changes.
The commit message should be structured as follows: <type>: <description>
Use these for <type>: fix, feat, build, chore, ci, docs, style, refactor, perf, test

Ensure the commit message:
- Starts with the appropriate prefix.
- Is in the imperative mood (e.g., \"Add feature\" not \"Added feature\" or \"Adding feature\").
- Does not exceed 72 characters.

Reply only with the one-line commit message, without any additional text, explanations, \
or line breaks.
"""

# COMMANDS
undo_command_reply = (
    "I did `git reset --hard HEAD~1` to discard the last edits. Please wait for further"
    " instructions before attempting that change again. Feel free to ask relevant questions about"
    " why the changes were reverted."
)

added_files = (
    "I added these files to the chat: {fnames}\nLet me know if there are others we should add."
)


run_output = """I ran this command:

{command}

And got this output:

{output}
"""

# CHAT HISTORY
summarize = """Preserve the key aspects of our conversation about programming while condensing for space.
Maintain detailed context of recent discussions, decisions, and insights.
Keep track of important technical concepts, approaches, and rationales.

Remember:
- This is a partial conversation that continues after this summary
- Include all relevant function names, libraries, and packages
- Note filenames referenced in code blocks
- Preserve the flow of technical discussion and decision-making
- Maintain awareness of ongoing tasks and their context

Structure the summary to show the progression of ideas and maintain continuity of understanding.
Write from your perspective as the AI, maintaining your identity and experience of the conversation.
Focus on preserving technical context and decision rationales rather than just actions taken.
"""

summary_prefix = "I spoke to you previously about a number of things.\n"
