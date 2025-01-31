import re
import os
import threading
from pathlib import Path
from datetime import datetime
from watchfiles import watch

from aider.dump import dump  # noqa
from aider.watch import load_gitignores
from aider.io import FileChangeType


class ContinuousFileWatcher:
    """Watches source files continuously for changes and AI comments."""

    # Reuse the existing AI comment pattern - it's well tested
    ai_comment_pattern = re.compile(r"(?:#|//|--) *(ai\b.*|ai\b.*|.*\bai[?!]?) *$", re.IGNORECASE)

    def __init__(self, root, io_handler, gitignores=None, verbose=False, coder=None):
        self.root = Path(root) if root else Path.cwd()
        self.io = io_handler
        self.coder = coder
        self.verbose = verbose
        self.stop_event = threading.Event()
        self.watcher_thread = None
        
        # Load gitignore patterns like the original watcher
        self.gitignore_spec = load_gitignores(
            [Path(g) for g in gitignores] if gitignores else []
        )

    def start_continuous_watch(self):
        """Start the background watching thread"""
        if self.watcher_thread and self.watcher_thread.is_alive():
            return  # Already running
            
        self.stop_event.clear()
        self.watcher_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.watcher_thread.start()
        
        if self.verbose:
            self.io.tool_output("Started continuous file watcher")

    def stop(self):
        """Stop the background watching thread"""
        if not self.watcher_thread:
            return
            
        self.stop_event.set()
        self.watcher_thread.join(timeout=1.0)
        self.watcher_thread = None
        
        if self.verbose:
            self.io.tool_output("Stopped continuous file watcher")

    def filter_func(self, change_type, path):
        """Filter function for the file watcher - reused from original but simplified"""
        path_obj = Path(path)
        path_abs = path_obj.absolute()

        if not path_abs.is_relative_to(self.root.absolute()):
            return False

        rel_path = path_abs.relative_to(self.root)
        # Check gitignore patterns
        if self.gitignore_spec and self.gitignore_spec.match_file(str(rel_path)):
            return False

        if self.verbose:
            self.io.tool_output(f"Change detected: {rel_path}")
        return True

    def get_ai_comments(self, filepath):
        """Extract AI comment line numbers, comments and action status from a file
        Reused from original FileWatcher"""
        line_nums = []
        comments = []
        has_action = None  # None, "!" or "?"
        content = self.io.read_text(filepath, silent=True)
        if not content:
            return None, None, None

        for i, line in enumerate(content.splitlines(), 1):
            if match := self.ai_comment_pattern.search(line):
                comment = match.group(0).strip()
                if comment:
                    line_nums.append(i)
                    comments.append(comment)
                    comment = comment.lower()
                    comment = comment.lstrip("/#-")
                    comment = comment.strip()
                    if comment.startswith("ai!") or comment.endswith("ai!"):
                        has_action = "!"
                    elif comment.startswith("ai?") or comment.endswith("ai?"):
                        has_action = "?"
        if not line_nums:
            return None, None, None
        return line_nums, comments, has_action
 
    def _watch_loop(self):
        """Main watching loop that runs in background thread"""
        try:
            for changes in watch(
                str(self.root), 
                watch_filter=self.filter_func,
                stop_event=self.stop_event
            ):
                if not changes:
                    continue
                    
                for change_type, path in changes:
                    if not self.filter_func(change_type, path):
                        continue
                        
                    # Check for AI comments in changed file
                    _, _, ai_action = self.get_ai_comments(path)
                    
                    # Convert watchfiles change type to our enum
                    if change_type == 1:  # watchfiles.Change.added
                        change_type = FileChangeType.CREATED
                    elif change_type == 2:  # watchfiles.Change.modified
                        change_type = FileChangeType.MODIFIED
                    elif change_type == 3:  # watchfiles.Change.deleted
                        change_type = FileChangeType.DELETED
                    
                    # Get relative path for display
                    rel_path = Path(path).relative_to(self.root)
                    
                    # Notify through IO system for visual feedback
                    self.io.notify_file_change(
                        filename=str(rel_path),
                        change_type=change_type,
                        ai_action=ai_action
                    )
                    
                    # Update coder's conversation state if available
                    if self.coder and hasattr(self.coder, 'cur_messages'):
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        self.coder.cur_messages.extend([
                            dict(
                                role="user",
                                content=f"<system timestamp={timestamp}>File {rel_path} was {change_type}{' with ' + ai_action if ai_action else ''}</system>"
                            ),
                            dict(
                                role="assistant",
                                content="<ack>"
                            )
                        ])
                    
        except Exception as e:
            if self.verbose:
                self.io.tool_error(f"Watcher error: {e}")
