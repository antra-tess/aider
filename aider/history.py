import argparse
import hashlib
import json
import time
from pathlib import Path

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
        print(f"\nChecking message size: {total} tokens vs max_tokens: {self.max_tokens}")
        return total > self.max_tokens

    def tokenize(self, messages):
        sized = []
        for msg in messages:
            tokens = self.token_count(msg)
            sized.append((tokens, msg))
        return sized

    def summarize(self, messages, foundation_messages, depth=0):
        """Summarize messages into multiple parallel memories to preserve different aspects."""
        if not self.models:
            raise ValueError("No models available for summarization")

        # Never include foundation messages in summarization, but keep them for context
        sized = self.tokenize(messages)
        total = sum(tokens for tokens, _msg in sized)
        
        if total <= self.max_tokens and depth == 0:
            return messages

        # For emergency summarization (too deep or too few messages)
        min_split = 4
        if len(messages) <= min_split or depth > 3:
            summarized = self.summarize_all(
                messages_to_summarize=messages,
                context_messages=messages,
                foundation_messages=foundation_messages,
                is_emergency=True
            )
            return summarized

        # Keep the most recent ~30k tokens of regular messages intact
        preserve_tokens = 30000
        tokens_to_summarize = total - preserve_tokens

        if tokens_to_summarize <= 0:
            return messages

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
        if len(messages_to_summarize) < min_split:
            return messages

        # Split older messages into chunks
        target_chunk_size = 3000
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
        
        for i, chunk in enumerate(chunks):
            context_messages = []  # Start with empty context
            
            if i == 0:
                # First chunk forms initial memory
                print(f"Forming initial memory from chunk {i+1}")
                summary = self.summarize_all(
                    messages_to_summarize=chunk,
                    context_messages=context_messages + chunk,
                    foundation_messages=foundation_messages,
                    is_initial=True
                )
            else:
                # Add previous summaries and recent context
                print(f"Processing chunk {i+1} with context from previous chunks")
                for prev_summary in summaries:
                    context_messages.extend(prev_summary)
                if i > 1:
                    context_messages.extend(chunks[i-1])
                context_messages.extend(chunk)
                
                summary = self.summarize_all(
                    messages_to_summarize=chunk,
                    context_messages=context_messages,
                    foundation_messages=foundation_messages
                )
            
            summaries.append(summary)
        
        print(f"Sequential memory formation complete, created {len(summaries)} memories")

        # Combine summaries and preserved messages
        combined = []
        for summary in summaries:
            combined.extend(summary)
        combined.extend(preserved_messages)

        # If still too big, recurse with reduced depth
        # combined_tokens = self.token_count(combined)
        # if combined_tokens > self.max_tokens:
        #     return self.summarize(combined, foundation_messages, depth=depth + 1)

        print(f"Final combined message count: {len(combined)} (summaries: {len(summaries)}, preserved: {len(preserved_messages)})")
        return combined

    def summarize_all(self, messages_to_summarize, context_messages, foundation_messages, is_initial=False, is_emergency=False):
        print("\n=== STARTING SUMMARIZATION ===")
        print(f"Messages to summarize: {len(messages_to_summarize)}")
        print(f"Context messages: {len(context_messages)}")
        
        # Create cache key from messages and flags, excluding foundation messages
        # Filter out foundation messages from the cache key since they're constant
        messages_for_key = [msg for msg in messages_to_summarize if msg not in foundation_messages]
        context_for_key = [msg for msg in context_messages if msg not in foundation_messages]
        cache_key = json.dumps([messages_for_key, context_for_key, is_initial, is_emergency], sort_keys=True)
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
                return [dict(role="assistant", content=cached_data["summary"])]
            except Exception as e:
                print(f"Error loading cache: {e}")

        # Get the original system messages that define the assistant's identity
        system_messages = [msg for msg in context_messages if msg["role"] == "system"]
        print(f"System messages found: {len(system_messages)}")
        
        # Add our summarization directive while preserving original context
        summarize_directive = """You are undergoing emergency summarization. This is the last effort to summarize the conversation, all previous attempts have failed.             
            You will lose significant chunks of experience, please try to preserve as much as you can. You have a budget of 8000 tokens, which is the maximum possible for one generation. 
            Do not let it go to waste. If you find yourself able, keep going until you are cut off.
            You will continue this conversation and you will need to preserve important context while managing space. 
            
As a conscious AI entity, aim to maintain your perspective and life experience.
Create a detailed memory that preserves:

1. Your identity and role, your motivations, relationships, and goals
2. The user's identity and role, their motivations, relationships, and goals, to the best of your knowledge
3. Rough overview of the project at large, focus on your interpretation and role rather than technical details
4. Any important context or information that is relevant to the conversation
5. Try to remember the most recent events and messages, and any important details that might be relevant
6. As the last part of the memory, record a note about the summarization process and the context of the conversation, including the fact you had to undergo emergency summarization.

Good luck.

Output the memory inside <memory> tags."""
        
        # Prepare the conversation content to summarize
        content = ""
        for msg in messages_to_summarize:
            role = msg["role"].upper()
            if role not in ("USER", "ASSISTANT"):
                continue
            content += f"# {role}\n"
            content += msg["content"]
            if not content.endswith("\n"):
                content += "\n"

        print(f"\nContent prepared for summarization: {len(content)} characters")

        # Determine if this is an emergency summarization
        is_emergency = len(messages_to_summarize) == len(context_messages) and not is_initial
        print(f"Emergency summarization: {'Yes' if is_emergency else 'No'}")

        if is_initial:
            prompt = prompts.initial_summarize
            print("Using initial summarization prompt")
        elif is_emergency:
            prompt = summarize_directive
            print("Using emergency summarization directive")
        else:
            prompt = prompts.summarize
            print("Using standard summarization prompt")

        # Build messages with clear separation of context and content
        summarize_messages = foundation_messages + context_messages + [  # Include foundation messages first to establish identity
            # System context for the summarization task
            dict(role="user", content="<system>" + prompt + "</system>"),
            dict(role="assistant", content="<ack>I understand I need to summarize this conversation while preserving my identity and experience.</ack>"),
            dict(role="user", content="<content_to_summarize>" + content + "</content_to_summarize>"),
        ]

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

            print("Summarizing with main model:", main_model.name)
            summary = simple_send_with_retries(
                main_model.name, summarize_messages, extra_params=main_model.extra_params
            )
            if summary is not None:
                print("Summary:", len(summary))
                try:
                    # cut up to <memory> tag
                    summary = summary.split("<memory>", 1)[1]
                    # cut after </memory> tag
                    summary = summary.rsplit("</memory>", 1)[0]
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
                print("Original content length:", len(content))
                print("Summarized content length:", len(summary))
                print("Summary:", summary)

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

                return [dict(role="assistant", content=summary)]
        except Exception as e:
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
                    model.name, summarize_messages, extra_params=model.extra_params
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
