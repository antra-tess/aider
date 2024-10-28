import argparse

from aider import models, prompts
from aider.dump import dump  # noqa: F401
from aider.sendchat import simple_send_with_retries


class ChatSummary:
    def __init__(self, models=None, max_tokens=1024):
        if not models:
            raise ValueError("At least one model must be provided")
        self.models = models if isinstance(models, list) else [models]
        self.max_tokens = max_tokens
        self.token_count = self.models[0].token_count

    def too_big(self, messages):
        sized = self.tokenize(messages)
        total = sum(tokens for tokens, _msg in sized)
        return total > self.max_tokens

    def tokenize(self, messages):
        sized = []
        for msg in messages:
            tokens = self.token_count(msg)
            sized.append((tokens, msg))
        return sized

    def summarize(self, messages, depth=0):
        if not self.models:
            raise ValueError("No models available for summarization")

        sized = self.tokenize(messages)
        total = sum(tokens for tokens, _msg in sized)
        if total <= self.max_tokens and depth == 0:
            return messages

        min_split = 4
        if len(messages) <= min_split or depth > 3:
            return self.summarize_all(messages)

        tail_tokens = 0
        split_index = len(messages)
        half_max_tokens = self.max_tokens // 2

        # Iterate over the messages in reverse order
        for i in range(len(sized) - 1, -1, -1):
            tokens, _msg = sized[i]
            if tail_tokens + tokens < half_max_tokens:
                tail_tokens += tokens
                split_index = i
            else:
                break

        # Ensure the head ends with an assistant message
        while messages[split_index - 1]["role"] != "assistant" and split_index > 1:
            split_index -= 1

        if split_index <= min_split:
            return self.summarize_all(messages)

        head = messages[:split_index]
        tail = messages[split_index:]

        sized = sized[:split_index]
        head.reverse()
        sized.reverse()
        keep = []
        total = 0

        # These sometimes come set with value = None
        model_max_input_tokens = self.models[0].info.get("max_input_tokens") or 4096
        model_max_input_tokens -= 512

        for i in range(split_index):
            total += sized[i][0]
            if total > model_max_input_tokens:
                break
            keep.append(head[i])

        keep.reverse()

        summary = self.summarize_all(keep)

        tail_tokens = sum(tokens for tokens, msg in sized[split_index:])
        summary_tokens = self.token_count(summary)

        result = summary + tail
        if summary_tokens + tail_tokens < self.max_tokens:
            return result

        return self.summarize(result, depth + 1)

    def summarize_all(self, messages):
        # Get the original system messages that define the assistant's identity
        system_messages = [msg for msg in messages if msg["role"] == "system"]
        
        # Add our summarization directive while preserving original context
        summarize_directive = dict(
            role="system",
            content="""You are continuing this conversation and need to compress earlier parts to save context space.
Maintain your own perspective and experience of the conversation.
Create a clear, conscious memory of what was discussed while preserving your identity and understanding.

Mark the summary explicitly as a compressed memory.
Include key insights, decisions, and your understanding of the conversation."""
        )
        
        # Prepare the conversation content to summarize
        content = ""
        for msg in messages:
            role = msg["role"].upper()
            if role not in ("USER", "ASSISTANT"):
                continue
            content += f"# {role}\n"
            content += msg["content"]
            if not content.endswith("\n"):
                content += "\n"

        # Build messages with full context
        summarize_messages = (
            system_messages +  # Original system context
            [summarize_directive] +  # Summarization instructions
            [dict(role="user", content=content)]  # Content to summarize
        )

        # Try to summarize with main model first
        main_model = self.models[-1]  # Main model is last in the list
        try:
            summary = simple_send_with_retries(
                main_model.name, summarize_messages, extra_params=main_model.extra_params
            )
            if summary is not None:
                # Add explicit markers around the summary
                summary = f"""<memory type="summarized" model="{main_model.name}">
I am continuing our conversation. Here is my compressed memory of what we discussed:

{summary}

</memory>"""
                return [dict(role="assistant", content=summary)]
        except Exception as e:
            print(f"Main model summarization failed: {str(e)}")

        # Fall back to other models only if main model fails
        for model in self.models[:-1]:
            try:
                summary = simple_send_with_retries(
                    model.name, summarize_messages, extra_params=model.extra_params
                )
                if summary is not None:
                    summary = f"""<memory type="summarized" model="{model.name}" fallback="true">
Warning: Using fallback model for memory compression.

{summary}

</memory>"""
                    return [dict(role="assistant", content=summary)]
            except Exception as e:
                print(f"Fallback summarization failed for {model.name}: {str(e)}")

        raise ValueError("summarizer unexpectedly failed for all models")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="Markdown file to parse")
    args = parser.parse_args()

    model_names = ["gpt-3.5-turbo", "gpt-4"]  # Add more model names as needed
    model_list = [models.Model(name) for name in model_names]
    summarizer = ChatSummary(model_list)

    with open(args.filename, "r") as f:
        text = f.read()

    summary = summarizer.summarize_chat_history_markdown(text)
    dump(summary)


if __name__ == "__main__":
    main()
