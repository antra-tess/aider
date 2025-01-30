from dataclasses import dataclass, field
from typing import List
from ..history import add_cache_control


@dataclass
class ChatChunks:
    system: List = field(default_factory=list)
    examples: List = field(default_factory=list)
    repo: List = field(default_factory=list)
    memories: List = field(default_factory=list)
    chat: List = field(default_factory=list)
    readonly_files: List = field(default_factory=list)
    chat_files: List = field(default_factory=list)
    cur: List = field(default_factory=list)
    reminder: List = field(default_factory=list)
    foundation: List = field(default_factory=list)  # Foundation messages that form the bedrock of context

    def all_messages(self):
        # Start with foundation messages
        messages = list(self.foundation)
        
        # Add other messages in order
        for msg_list in [
            self.system,
            self.examples,
            self.readonly_files,
            self.memories,
            self.chat,
            self.repo,
            self.chat_files,
            self.cur,
            self.reminder
        ]:
            messages.extend(msg_list)
        
        return messages

    def add_cache_control_headers(self):
        if self.examples:
            self.add_cache_control(self.examples)
        else:
            self.add_cache_control(self.system)

        if self.memories:
            self.strip_cache_control(self.memories)
            self.add_cache_control(self.memories)

        if self.repo:
            # this will mark both the readonly_files and repomap chunk as cacheable
            self.add_cache_control(self.repo)
        else:
            # otherwise, just cache readonly_files if there are any
            self.add_cache_control(self.readonly_files)

        self.add_cache_control(self.chat_files)

    def add_cache_control(self, messages):
        # Reusing cache_control from history.py. Reducing duplication of methods
        # because behaviour was the same.
        return add_cache_control(messages)

    def strip_cache_control(self, messages):
        for message in messages:
            if isinstance(message.get("content"), list) and message["content"][0].get(
                "cache_control"
            ):
                message["content"][0].pop("cache_control")

    def cacheable_messages(self):
        messages = self.all_messages()
        for i, message in enumerate(reversed(messages)):
            if isinstance(message.get("content"), list) and message["content"][0].get(
                "cache_control"
            ):
                return messages[: len(messages) - i]
        return messages


