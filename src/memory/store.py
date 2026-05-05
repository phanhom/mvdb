"""
Session memory — persists conversation history and search-site records as JSON.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data"
MEMORY_FILE = DATA_DIR / "memory.json"


class MemoryStore:
    """Manages conversation sessions, search history, and known sites."""

    def __init__(self):
        self._data = None

    @property
    def data(self) -> dict:
        if self._data is None:
            self._data = self._load()
        return self._data

    def _load(self) -> dict:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if MEMORY_FILE.exists():
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load memory: {e}")
        return {"sessions": {}, "known_sites": [], "current_session": "default"}

    def _save(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def _ensure_session(self, session_id: str = None):
        if session_id is None:
            session_id = self.data.get("current_session", "default")
        if session_id not in self.data["sessions"]:
            self.data["sessions"][session_id] = {
                "history": [],
                "searched_sites": [],
                "created_at": time.time(),
            }
        return session_id

    def add_message(self, role: str, content: str, session_id: str = None):
        """Append a message to the conversation history of a session."""
        sid = self._ensure_session(session_id)
        session = self.data["sessions"][sid]
        session["history"].append({
            "role": role,
            "content": content,
            "time": time.time(),
        })
        # Trim to max_history
        max_history = 50
        if len(session["history"]) > max_history * 2:
            session["history"] = session["history"][-(max_history * 2):]
        self._save()

    def add_search_record(self, query: str, sites: list[str],
                          session_id: str = None):
        """Record which sites were searched for a given query."""
        sid = self._ensure_session(session_id)
        session = self.data["sessions"][sid]
        session["searched_sites"].append({
            "query": query,
            "sites": sites,
            "time": time.time(),
        })
        max_sites = 200
        if len(session["searched_sites"]) > max_sites:
            session["searched_sites"] = session["searched_sites"][-max_sites:]
        self._save()

    def get_history(self, session_id: str = None,
                    limit: int = 20) -> list[dict]:
        """Get recent conversation history as messages for LLM."""
        sid = self._ensure_session(session_id)
        history = self.data["sessions"][sid]["history"]
        recent = history[-limit:]
        return [{"role": m["role"], "content": m["content"]} for m in recent]

    def get_excluded_sites(self, session_id: str = None) -> set[str]:
        """Get sites from the last search that should be excluded on retry."""
        sid = self._ensure_session(session_id)
        searched = self.data["sessions"][sid]["searched_sites"]
        if not searched:
            return set()

        last = searched[-1]
        return {s.split("/")[2] if "/" in s else s
                for s in last.get("sites", [])}

    def get_last_query(self, session_id: str = None) -> Optional[str]:
        """Get the most recent search query."""
        sid = self._ensure_session(session_id)
        searched = self.data["sessions"][sid]["searched_sites"]
        if searched:
            return searched[-1]["query"]
        return None

    def add_known_site(self, url: str, tags: list[str] = None):
        """Record a known good media site."""
        existing = [s for s in self.data["known_sites"]
                    if s["url"] == url]
        if existing:
            existing[0]["last_seen"] = time.time()
            if tags:
                existing_tags = set(existing[0].get("tags", []))
                existing_tags.update(tags)
                existing[0]["tags"] = list(existing_tags)
        else:
            self.data["known_sites"].append({
                "url": url,
                "tags": tags or [],
                "added_at": time.time(),
                "last_seen": time.time(),
            })
        self._save()

    def get_known_sites(self, tag_filter: str = None) -> list[dict]:
        """Get all known sites, optionally filtered by tag."""
        if tag_filter:
            return [s for s in self.data["known_sites"]
                    if tag_filter in s.get("tags", [])]
        return self.data["known_sites"]

    def clear_session(self, session_id: str = None):
        """Clear a session's history."""
        sid = self._ensure_session(session_id)
        self.data["sessions"][sid]["history"] = []
        self.data["sessions"][sid]["searched_sites"] = []
        self._save()
        logger.info(f"Cleared session: {sid}")

    def switch_session(self, session_id: str):
        """Switch active session."""
        self.data["current_session"] = session_id
        self._ensure_session(session_id)
        self._save()
        logger.info(f"Switched to session: {session_id}")

    def get_next_page_offset(self, session_id: str = None) -> int:
        """For pagination: count how many times the last query was searched."""
        sid = self._ensure_session(session_id)
        searched = self.data["sessions"][sid]["searched_sites"]
        if not searched:
            return 0
        last_q = searched[-1]["query"]
        return sum(1 for s in searched if s["query"].startswith(last_q))
