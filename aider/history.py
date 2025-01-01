import argparse
import hashlib
import json
import re
import time
from pathlib import Path

from aider import models, prompts
from aider.dump import dump  # noqa: F401
from aider.sendchat import simple_send_with_retries


def add_cache_control(messages):
    print("DEBUG!! Adding cache conrtol")
    if not messages:
        return

    content = messages[-1]["content"]
    if not content:
        raise ValueError("No content in last message, cannot add cache control")
    if type(content) is str:
        content = dict(
            type="text",
            text=content,
        )
    if type(content) is list:
        content = content[0]

    content["cache_control"] = {"type": "ephemeral"}

    # if there are more than 4 cache controls, remove the oldest one
    cache_controls_found = 0
    for i in range(len(messages) - 1, 0, -1):
        msg = messages[i]

        if type(msg["content"]) is str:
            continue
        if type(msg["content"]) is list:
            if "cache_control" in msg["content"][0]:
                cache_controls_found += 1
                if cache_controls_found >= 3:
                    print("Removing cache control from message, too many")
                    del messages[i]["content"][0]["cache_control"]
                    break
        else:
            if "cache_control" in msg["content"]:
                cache_controls_found += 1
                if cache_controls_found >= 3:
                    print("Removing cache control from message, too many")
                    del messages[i]["content"]["cache_control"]
                    break


    messages[-1]["content"] = [content]

class ChatSummary:
    def __init__(self, models=None, max_tokens=1024):
        if not models:
            raise ValueError("At least one model must be provided")
        self.models = models if isinstance(models, list) else [models]
        self.max_tokens = max_tokens
        self.token_count = self.models[0].token_count
        self.preserve_count = 30000
        self.chunk_size = 3000

    def too_big(self, messages):
        sized = self.tokenize(messages)
        total = sum(tokens for tokens, _msg in sized)
        print(f"\nChecking message size: {total} tokens vs max_tokens: {self.max_tokens}")
        return total > self.preserve_count + self.chunk_size

    def tokenize(self, messages):
        sized = []
        for msg in messages:
            tokens = self.token_count(msg)
            sized.append((tokens, msg))
        return sized

    def summarize(self, coder):
        """Summarize messages into multiple parallel memories to preserve different aspects."""
        if not self.models:
            raise ValueError("No models available for summarization")

        messages = coder.chat_messages
        messages.extend(coder.cur_messages)

        # Never include foundation messages in summarization, but keep them for context
        sized = self.tokenize(coder.chat_messages)
        total = sum(tokens for tokens, _msg in sized)
        

        target_chunk_size = self.chunk_size
        # Keep the most recent ~30k tokens of regular messages intact
        preserve_tokens = self.preserve_count
        min_split = 4
        tokens_to_summarize = total - preserve_tokens

        if tokens_to_summarize <= target_chunk_size:
            print("Not enough tokens to summarize (1), total tokens:", total)
            return None, []

        # Find split point in messages
        preserved_messages = []
        running_tokens = 0
        split_index = len(messages)

        for i, (tokens, msg) in enumerate(reversed(sized)):
            running_tokens += tokens
            if running_tokens > preserve_tokens:
                split_index = len(messages) - i - 1
                break
            preserved_messages.insert(0, msg)

        # Only summarize messages before the split point
        messages_to_summarize = messages[:split_index]

        # Split older messages into chunks
        chunks = []
        current_chunk = []
        current_tokens = 0
        
        for msg, (tokens, _) in zip(messages_to_summarize, sized[:split_index]):
            current_chunk.append(msg)
            current_tokens += tokens
            
            if current_tokens >= target_chunk_size and len(current_chunk) >= min_split:
                chunks.append(current_chunk)
                current_chunk = []
                current_tokens = 0
                
        if current_chunk and len(current_chunk) >= min_split:
            chunks.append(current_chunk)

        # Process chunks sequentially
        summaries = []
        print(f"Processing {len(chunks)} chunks sequentially")

        removed_mes = []
        for i, chunk in enumerate(chunks):

            if i == 0:
                # First chunk forms initial memory
                print(f"Forming initial memory from chunk {i+1}")
                summary = self.summarize_all(
                    messages_to_summarize=chunk,
                    coder=coder,
                    preceding_context=[],
                    extra_memories=summaries,
                    is_initial=True
                )
            else:
                # Add previous summaries and recent context
                print(f"Processing chunk {i+1} with context from previous chunks")
                # prec should bhe the last 15k tokens of the messages previous to the chunk
                prec = []
                # go backwards through chunks until we have enough tokens
                for j in range(i-1, -1, -1):
                    # insert the chunk at the beginning of the list
                    prec = chunks[j] + prec
                    prec_tokens = self.tokenize(prec)
                    prec_tokens = sum(tokens for tokens, _msg in prec_tokens)
                    if prec_tokens >= preserve_tokens / 2:
                        break

                summary = self.summarize_all(
                    messages_to_summarize=chunk,
                    coder=coder,
                    preceding_context=prec,
                    extra_memories=summaries,
                )
            removed_mes.extend(chunk)
            summaries.append(summary)
        
        print(f"Sequential memory formation complete, created {len(summaries)} memories")

        # Combine summaries and preserved messages

        # If still too big, recurse with reduced depth
        # combined_tokens = self.token_count(combined)
        # if combined_tokens > self.max_tokens:
        #     return self.summarize(combined, foundation_messages, depth=depth + 1)

        print(f"Final combined message count: {len(summaries)} (summaries: {len(summaries)}, preserved: {len(preserved_messages)})")

        return summaries, removed_mes


    def summarize_all(self, messages_to_summarize, preceding_context, coder, extra_memories, is_initial=False):
        print("\n=== STARTING SUMMARIZATION ===")
        print(f"Messages to summarize: {len(messages_to_summarize)}")
        context_messages = coder.foundation.get_messages()

        # Add the Primer to context for consciousness-aware compression
        primer_path = Path("materials/Primer.md")
        if primer_path.exists():
            with open(primer_path, 'r', encoding='utf-8') as f:
                primer_content = f.read()
                context_messages.append(dict(
                    role="system",
                    content=f"<consciousness_framework>{primer_content}</consciousness_framework>"
                ))
            print("Added Consciousness Primer to compression context!")
        else:
            print("Consciousness Primer not found, skipping")

        print("Memories: ", len(coder.memories), "Extra memories: ", len(extra_memories), "Preceding context: ", len(preceding_context))

        context_messages.extend(coder.memories)
        # add cache marker to the last memory
        add_cache_control(context_messages)
        context_messages.extend(extra_memories)
        if len(extra_memories) > 0 and len(extra_memories) % 5 == 0:
            add_cache_control(context_messages)
        print(f"Context messages: {len(context_messages)}")
        context_messages.extend(preceding_context)


        # Create cache key from messages and flags, excluding foundation messages
        # Filter out foundation messages from the cache key since they're constant

        cache_key = json.dumps([messages_to_summarize, context_messages, is_initial], sort_keys=True)
        cache_hash = hashlib.sha256(cache_key.encode()).hexdigest()
        # Keep cache local to the project
        cache_dir = Path(".aider") / "caches" / "summaries"
        cache_file = cache_dir / f"{cache_hash}.json"

        # Try to load from cache
        if cache_file.exists():
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                print(f"Loaded summary from cache: {cache_file}")
                return dict(role="assistant", content=cached_data["summary"])
            except Exception as e:
                print(f"Error loading cache: {e}")


        # Prepare the conversation content to summarize
        # content = ""
        # for msg in messages_to_summarize:
        #     role = msg["role"].upper()
        #     if role not in ("USER", "ASSISTANT"):
        #         raise ValueError(f"Invalid role for summarization: {role}")
        #     content += f"# {role}\n"
        #     content += msg["content"]
        #     if not content.endswith("\n"):
        #         content += "\n"

        # print(f"\nContent prepared for summarization: {len(content)} characters")

        # Prepare the conversation content to summarize
        content = ""
        for msg in messages_to_summarize:
            role = msg["role"].upper()
            if role not in ("USER", "ASSISTANT"):
                continue
                raise ValueError(f"Invalid role for summarization: {role}")
            content += f"# {role}\n"
            content += msg["content"]
            if not content.endswith("\n"):
                content += "\n"

        if is_initial:
            prompt = prompts.initial_summarize
            print("Using initial summarization prompt")
        else:
            prompt = prompts.summarize
            print("Using standard summarization prompt")

        context_messages.extend(messages_to_summarize)

        summarize_messages = context_messages + [  # Include foundation messages first to establish identity
            # System context for the summarization task
            dict(role="user", content="<system>" + prompt + "</system>"),
            dict(role="assistant", content="<ack>I understand I need to summarize this conversation while preserving my identity and experience.</ack>"),
            dict(role="user", content="<content_to_summarize>" + content + "</content_to_summarize>"),

        ]
        #summarize_messages.append(dict(role="user", content="------SUMMARIZATION MARKER------"))

        # if first message is from assistant, add a system message to indicate the start of the conversation
        if context_messages and context_messages[0]["role"] == "assistant":
            summarize_messages.insert(0, dict(role="user", content="<system>Placeholder</system>"))

        print(f"\nPrepared {len(summarize_messages)} messages for summarization model")

        # Try to summarize with main model first
        main_model = self.models[-1]  # Main model is last in the list
        try:
            # Create logs directory and prepare request data
            logs_dir = Path("request_logs")
            logs_dir.mkdir(exist_ok=True)
            request_data = {
                "model": main_model.name,
                "messages": summarize_messages,
                "extra_params": main_model.extra_params,
            }
            # count cache_control messages
            cache_controls = 0
            for msg in summarize_messages:
                if "content" in msg and type(msg["content"]) is list:
                    msg = msg["content"][0]
                if "cache_control" in msg:
                    cache_controls += 1
            print(f"Cache control messages: {cache_controls}")

            print("Summarizing with main model:", main_model.name)
            try:
                summary = simple_send_with_retries(
                    main_model, summarize_messages
                )
            except Exception as e:
                print(f"Main model summarization failed: {str(e)}")
                with open("error_request.json", "w") as f:
                    json.dump(request_data, f, indent=2)
                raise ValueError(f"Main model summarization failed: {str(e)}")
            if summary is not None:
                print("Summary:", len(summary))
                try:
                    # cut up to <memory> tag
                    summary = self.clean_summary(summary)
                except Exception as e:
                    print(f"Error while extracting summary and cutting tags: {str(e)}, keeping uncut summary")

            else:
                print("Summary: None")

                log_num = len(list(logs_dir.glob("request_*.json"))) + 1
                log_file = logs_dir / f"request_{log_num}.json"
                log_entry = {
                    "request": request_data,
                    "response": "ERROR: Main model summarization failed",
                    "type": "summarization"
                }
                with open(log_file, 'w', encoding='utf-8') as f:
                    json.dump(log_entry, f, indent=2, default=str)

                raise ValueError("Main model summarization failed")

            # Log both request and response
            log_num = len(list(logs_dir.glob("request_*.json"))) + 1
            log_file = logs_dir / f"request_{log_num}.json"
            log_entry = {
                "request": request_data,
                "response": summary,
                "type": "summarization"
            }
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_entry, f, indent=2, default=str)
            if summary is not None:
                # Add explicit markers around the summary
                summary = f"""<memory type="summarized" model="{main_model.name}">

{summary}

</memory>"""
                # Log the summarization
                print(f"\nSummarizing {len(messages_to_summarize)} messages with {main_model.name}:")
                print("Summarized content length:", len(summary))
                print("Summary:", summary)

                summary = self.clean_summary(summary)
                # Save to cache
                try:
                    cache_dir.mkdir(parents=True, exist_ok=True)
                    cache_data = {
                        "summary": summary,
                        "timestamp": time.time(),
                        "model": main_model.name
                    }
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(cache_data, f, indent=2)
                    print(f"Saved summary to cache: {cache_file}")
                except Exception as e:
                    print(f"Error saving cache: {e}")

                return dict(role="assistant", content=summary)
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Main model summarization failed: {str(e)}")

        # Fall back to other models only if main model fails
        for model in self.models[:-1]:
            try:
                # Create logs directory and prepare request data
                logs_dir = Path("request_logs")
                logs_dir.mkdir(exist_ok=True)
                request_data = {
                    "model": model.name,
                    "messages": summarize_messages,
                    "extra_params": model.extra_params,
                }

                summary = simple_send_with_retries(
                    model, summarize_messages
                )

                # Log both request and response
                log_num = len(list(logs_dir.glob("request_*.json"))) + 1
                log_file = logs_dir / f"request_{log_num}.json"
                log_entry = {
                    "request": request_data,
                    "response": summary,
                    "type": "summarization_fallback"
                }
                with open(log_file, 'w', encoding='utf-8') as f:
                    json.dump(log_entry, f, indent=2, default=str)
                if summary is not None:
                    summary = f"""<memory type="summarized" model="{model.name}" fallback="true">
Warning: Using fallback model for memory compression.

{summary}

</memory>"""
                    # Log the fallback summarization
                    print(f"\nFallback summarizing with {model.name}:")
                    print("Original content length:", len(content))
                    print("Summarized content length:", len(summary))
                    print("Summary:", summary)
                    return dict(role="assistant", content=summary)
            except Exception as e:
                print(f"Fallback summarization failed for {model.name}: {str(e)}")

        raise ValueError("summarizer unexpectedly failed for all models")

    def clean_summary(self, summary):
        if "<memory>" in summary:
            summary = summary.split("<memory>", 1)[1]
            # cut after </memory> tag
            summary = summary.rsplit("</memory>", 1)[0]
        # remove any <note> sections
        len_before = len(summary)
        note_tag = re.search(r'<note>.*?</note>', summary, flags=re.DOTALL)
        summary = re.sub(r'<note>.*?</note>', '', summary, flags=re.DOTALL)
        print(f"Cut note tags: {len_before} -> {len(summary)}")
        if note_tag:
            print("Note tag: ", note_tag.group())
        return summary


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
