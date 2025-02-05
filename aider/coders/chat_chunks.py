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
        """Find all messages containing spotlight tags, returns (message, index) pairs"""
        spotlight_messages = []
        
        # Search through all message lists that might contain spotlight tags
        for msg_list in [self.chat, self.cur]:
            for i, msg in enumerate(msg_list):
                if isinstance(msg.get("content"), str) and "<spotlight" in msg["content"]:
                    spotlight_messages.append((msg, msg_list))
        
        return spotlight_messages

    def add_cache_control_headers(self, spotlight_locations=None):
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

        if spotlight_locations:
            # Strip cache from all spotlight acknowledgments
            for msg_list, idx in spotlight_locations:
                if idx < len(msg_list):  # Safety check
                    self.strip_cache_control([msg_list[idx]])
            
            # Find the last spotlight in cur_messages
            cur_spotlights = [(i, loc) for i, (msg_list, idx) in enumerate(spotlight_locations) 
                            if msg_list is self.cur and idx < len(msg_list)]
            
            if cur_spotlights:
                # Add cache to the most recent spotlight acknowledgment in cur_messages
                _, (msg_list, idx) = cur_spotlights[-1]
                self.add_cache_control([msg_list[idx]])
            else:
                # No spotlight messages in current messages, cache chat_files
                self.add_cache_control(self.chat_files)
        else:
            # No spotlight locations provided, cache chat_files
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


