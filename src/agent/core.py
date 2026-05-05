"""
Media Agent Core
"""

import json
import logging

from ..llm.adapter import get_llm, load_config
from ..search.engine import search
from ..search.scraper import scrape_search_results
from ..memory.store import MemoryStore
from ..prompts.templates import (
    SYSTEM_PROMPT, INTENT_ANALYSIS_PROMPT, RESULT_FORMAT_PROMPT,
    get_search_queries,
)

logger = logging.getLogger(__name__)


class MediaAgent:

    def __init__(self, session_id: str = "default"):
        self.memory = MemoryStore()
        self.memory.switch_session(session_id)
        self.config = load_config()
        self.search_config = self.config.get("search", {})
        self.max_rounds = self.search_config.get("max_rounds", 3)
        self.max_results = self.search_config.get("max_results", 15)

    def _analyze_intent(self, user_message: str) -> dict:
        history = self.memory.get_history(limit=10)
        history_str = "\n".join(
            f"[{m['role']}]: {m['content'][:200]}" for m in history
        )
        prompt = INTENT_ANALYSIS_PROMPT.format(
            user_message=user_message,
            history=history_str or "(no history)",
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]
        try:
            llm = get_llm()
            response = llm.chat(messages, temperature=0.3, max_tokens=1024)
        except Exception as e:
            logger.warning(f"LLM intent analysis failed: {e}. Using fallback.")
            return self._fallback_analysis(user_message)

        try:
            js = response.find("{")
            je = response.rfind("}") + 1
            if js >= 0 and je > js:
                analysis = json.loads(response[js:je])
            else:
                analysis = self._fallback_analysis(user_message)
        except (json.JSONDecodeError, KeyError):
            analysis = self._fallback_analysis(user_message)
        logger.info(f"Intent: {json.dumps(analysis, ensure_ascii=False)}")
        return analysis

    def _fallback_analysis(self, user_message: str) -> dict:
        content_type = "other"
        msg_lower = user_message.lower()

        sport_keywords = ["nba", "lakers", "warriors", "celtics", "bulls",
                          "heat", "nets", "篮球", "足球", "英超", "西甲",
                          "中超", "欧冠", "世界杯", "f1", "ufc", "boxing",
                          "tennis", "网球", "lol", "dota", "csgo", "valorant",
                          "直播", "比赛"]
        if any(kw in msg_lower for kw in sport_keywords):
            content_type = "sports"

        music_keywords = ["mp3", "flac", "无损", "歌曲", "专辑", "演唱会",
                          "concert", "album", "song", "band", "乐队"]
        if any(kw in msg_lower for kw in music_keywords):
            content_type = "music"

        game_keywords = ["网页版", "在线玩", "模拟器", "steam", "switch",
                         "ps5", "xbox", "游戏"]
        if any(kw in msg_lower for kw in game_keywords):
            content_type = "game"

        if "下载" in msg_lower or "download" in msg_lower:
            intent = "download"
        elif "在线" in msg_lower or "在线观看" in msg_lower or "stream" in msg_lower:
            intent = "stream"
        else:
            intent = "both"

        queries = get_search_queries(
            content_type, intent, user_message,
            is_live=("直播" in msg_lower or "live" in msg_lower),
        )
        return {
            "intent": intent,
            "keywords": [user_message],
            "is_sports": content_type == "sports",
            "is_live": "直播" in msg_lower or "live" in msg_lower,
            "content_type": content_type,
            "search_queries": queries[:8],
        }

    def _is_continue(self, text: str) -> bool:
        t = text.strip()
        return t in ("continue", "more", "next")

    def _is_retry(self, text: str) -> bool:
        t = text.strip()
        return t in ("retry", "different", "change")

    def _handle_continue(self) -> dict:
        last_query = self.memory.get_last_query()
        excluded = self.memory.get_excluded_sites()
        if not last_query:
            return self._fallback_analysis("")
        offset = self.memory.get_next_page_offset()
        page_query = last_query
        if excluded:
            parts = " ".join(f"-site:{s}" for s in excluded)
            page_query = f"{last_query} {parts}"
        return {
            "intent": "continue",
            "keywords": [last_query],
            "is_sports": False,
            "is_live": False,
            "content_type": "other",
            "search_queries": [last_query, page_query],
            "offset": offset,
        }

    def _handle_retry(self) -> dict:
        last_query = self.memory.get_last_query()
        excluded = self.memory.get_excluded_sites()
        if not last_query:
            return self._fallback_analysis("")
        parts = " ".join(f"-site:{s}" for s in excluded)
        alt_query = f"{last_query} {parts}" if parts else last_query
        return {
            "intent": "retry",
            "keywords": [last_query],
            "is_sports": False,
            "is_live": False,
            "content_type": "other",
            "search_queries": [alt_query],
        }

    def _search_and_scrape(self, queries):
        all_scraped = []
        for q in queries[:8]:
            if not q.strip():
                continue
            results = search(
                q,
                max_results=self.max_results,
                timeout=self.search_config.get("timeout", 15),
            )
            scraped = scrape_search_results(
                results,
                max_pages=6,
                timeout=self.search_config.get("timeout", 15),
            )
            all_scraped.extend(scraped)
        sites_seen = {r["url"] for r in all_scraped if not r.get("error")}
        if queries:
            self.memory.add_search_record(
                query=queries[0],
                sites=list(sites_seen),
            )
        return all_scraped

    def _collect_links(self, scraped: list) -> dict:
        aggregated = {
            "magnets": [], "thunder": [], "pan": [],
            "aliyun": [], "quark": [], "m3u8": [], "online": [],
        }
        for page in scraped:
            if page.get("error"):
                continue
            links = page.get("links", {})
            for k in aggregated:
                aggregated[k].extend(links.get(k, []))
        for k in aggregated:
            seen = set()
            unique = []
            for item in aggregated[k]:
                if item["url"] not in seen:
                    seen.add(item["url"])
                    unique.append(item)
            aggregated[k] = unique
        return aggregated

    def run(self, user_input: str) -> str:
        self.memory.add_message("user", user_input)
        user_lower = user_input.strip().lower()

        if self._is_continue(user_lower):
            analysis = self._handle_continue()
        elif self._is_retry(user_lower):
            analysis = self._handle_retry()
        else:
            analysis = self._analyze_intent(user_input)

        queries = analysis.get("search_queries", [user_input])
        if not queries or not queries[0].strip():
            if analysis.get("intent") in ("continue", "retry"):
                msg = "No previous search history. Please search for something first."
            else:
                msg = "Empty query. Please describe what you want to find."
            self.memory.add_message("assistant", msg)
            return msg

        all_aggregated = {
            "magnets": [], "thunder": [], "pan": [],
            "aliyun": [], "quark": [], "m3u8": [], "online": [],
        }
        suffixes = [" 1080p", " HD", " 4K", " Blu-ray"]

        for rnd in range(self.max_rounds):
            if rnd > 0 and queries:
                base = queries[0]
                queries = [f"{base}{suffixes[(rnd - 1) % len(suffixes)]}"]
            scraped = self._search_and_scrape(queries)
            aggregated = self._collect_links(scraped)
            for k in all_aggregated:
                all_aggregated[k].extend(aggregated[k])
            total = sum(len(v) for v in all_aggregated.values())
            if total >= 10:
                break

        for k in all_aggregated:
            seen = set()
            unique = []
            for item in all_aggregated[k]:
                if item["url"] not in seen:
                    seen.add(item["url"])
                    unique.append(item)
            all_aggregated[k] = unique

        total_count = sum(len(v) for v in all_aggregated.values())
        if total_count == 0:
            msg = (
                "No resources found.\n\n"
                "Suggestions:\n"
                "1. Try shorter keywords\n"
                "2. Add 'download' or 'stream'\n"
                "3. Check spelling\n"
                "4. Type 'continue' for next page"
            )
            self.memory.add_message("assistant", msg)
            return msg

        output = self._format_results(user_input, all_aggregated,
                                       total_count, analysis)
        self.memory.add_message("assistant", output)
        return output

    def _format_results(self, user_query, aggregated, total_count, analysis):
        lines = []
        intent = analysis.get("intent", "both")
        ct = analysis.get("content_type", "other")
        labels = {
            "movie": "Movie", "tv": "TV Show",
            "variety": "Variety", "documentary": "Documentary",
            "anime": "Anime", "sports": "Sports",
            "music": "Music", "game": "Game",
            "other": "Media",
        }
        lines.append(f"## {labels.get(ct, 'Media')} Results")
        lines.append(f"Found {total_count} resources")
        lines.append("")

        has_dl = any(aggregated.get(k) for k in
                     ("magnets", "thunder", "pan", "aliyun", "quark"))
        if has_dl and intent in ("download", "both"):
            lines.append("### Download Links")
            lines.append("")
            for section, title in [
                ("magnets", "Magnet Links"),
                ("thunder", "Thunder Links"),
                ("pan", "Baidu Pan"),
                ("aliyun", "Aliyun Drive"),
                ("quark", "Quark Pan"),
            ]:
                items = aggregated.get(section, [])
                if items:
                    lines.append(f"**{title}**")
                    for item in items[:10]:
                        extra = ""
                        if section == "pan" and item.get("code"):
                            extra = f" (code: {item['code']})"
                        lines.append(f"- {item['url']}{extra}")
                    lines.append("")

            if aggregated.get("m3u8"):
                lines.append("**M3U8 Streams**")
                for m3 in aggregated["m3u8"][:5]:
                    lines.append(f"- `{m3['url']}`")
                lines.append("")

        if aggregated.get("online") and intent in ("stream", "both"):
            lines.append("### Online / Stream")
            lines.append("")
            for o in aggregated["online"][:15]:
                lines.append(f"- {o['url']}")
            lines.append("")

        lines.append("---")
        lines.append("Type **continue** for next page | **retry** to re-search | or enter a new query")
        return "\n".join(lines)
