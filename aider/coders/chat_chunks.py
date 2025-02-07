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
    current_cache_indices: List = field(default_factory=list) # Storing the indices of current_messages cache marker placements

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
            # Cache marker 1
            self.repo,
            self.chat_files,
            # Cache marker 2
            self.cur,
            self.reminder
        ]:
            messages.extend(msg_list)
        return messages

    def add_cache_control_headers(self):
        # First cache marker goes here, to the farthest item
        first_marker_set = False
        for msg_list in [self.system, self.examples, self.readonly_files, self.memories,self.chat].reverse():
            if msg_list:
                self.strip_cache_control(msg_list)
                if not first_marker_set:
                    self.add_cache_control(msg_list)
                    first_marker_set = True
        second_marker_set = False
        for msg_list in [self.chat_files, self.repo]:
                self.strip_cache_control(msg_list)
                if not second_marker_set:
                    self.add_cache_control(msg_list)
                    second_marker_set = True
        if len(self.current_cache_indices) > 2:
            self.strip_cache_control(self.cur)
            self.current_cache_indices = self.current_cache_indices[-2:]
        for item in self.current_cache_indices:
            self.add_cache_control([self.cur[item]])

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


