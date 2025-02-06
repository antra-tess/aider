from dataclasses import dataclass, field
from typing import List


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
    spotlight_messages: List = field(default_factory=list)  # Store indices of spotlight acknowledgments

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

    def find_spotlight_messages(self):
        """Find all messages containing spotlight tags and store results"""
        self.spotlight_messages = []
        
        # Search through current messages lists that might contain spotlight tags
        for index, msg in enumerate(self.cur):
            if isinstance(msg.get("content"), str) and msg["content"].startswith("<system><spotlight>"):
                # Searching acknowledgement message, not the spotlight itself
                self.spotlight_messages.append(index + 1)
        
        return self.spotlight_messages

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

        if self.chat:
            self.strip_cache_control(self.chat)

        # Use stored spotlight information
        if self.spotlight_messages:
            for item in self.spotlight_messages[:-1]:
                self.strip_cache_control([self.cur[item]])
            self.add_cache_control([self.cur[self.spotlight_messages[-1]]])
        else:
            # No spotlight locations, cache chat_files
            self.add_cache_control(self.chat_files)

    def add_cache_control(self, messages):
        if not messages:
            return

        content = messages[-1]["content"]
        if type(content) is str:
            content = dict(
                type="text",
                text=content,
            )
        if type(content) is list:
            content = content[0]
        content["cache_control"] = {"type": "ephemeral"}
        messages[-1]["content"] = [content]

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


