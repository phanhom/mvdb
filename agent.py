#!/usr/bin/env python3
"""MVDB — Media Search Agent CLI"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.agent.core import MediaAgent
from src.llm.adapter import load_config

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.styles import Style
    from prompt_toolkit.completion import WordCompleter
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("mvdb")

STYLE = Style.from_dict({
    "prompt": "bold #00ff88", "separator": "#666666", "status": "#888888 italic",
    "result-header": "bold #00aaff", "result-section": "bold #ffaa00",
    "link": "#00ccff underline", "code": "#aaaaaa bg:#222222", "info": "#888888",
})

COMMANDS = WordCompleter([
    "继续", "还有吗", "下一页", "再来", "不是这个", "不对", "换一批", "换个", "重新搜",
    "新建对话", "清除记忆", "帮助", "退出", "quit", "exit", "help", "new", "clear",
], ignore_case=False)

BANNER = r"""
  +====================================+
  |        MVDB                       |
  |        Media Search Agent         |
  |   Download + Stream, One Stop     |
  +====================================+
"""

HELP_TEXT = """
===== MVDB =====

Direct search:
  > Inception
  > Breaking Bad season 1
  > Lakers recent games
  > Jay Chou Qing Hua Ci download

Commands:
  continue / more               next page
  retry / different             re-search excluding previous results
  new                           start new session
  clear                         clear current session memory
  help                          show this help
  quit / exit                   quit

Supported content types:
  Movies, TV shows, variety shows, documentaries, anime
  Sports (NBA, football, esports...) live streams + replays
  Music (download links + online streaming)
  Games (web versions + download links + emulators)
  Any livestream (gaming, shows, etc.)
  Image / wallpaper search
"""

class CLI:
    def __init__(self):
        self.agent = MediaAgent()
        self.running = True
        self.session = None
        if HAS_PROMPT_TOOLKIT:
            hist_file = Path(__file__).parent / "data" / ".cli_history"
            hist_file.parent.mkdir(parents=True, exist_ok=True)
            self.session = PromptSession(
                history=FileHistory(str(hist_file)),
                style=STYLE, completer=COMMANDS,
            )

    def _print(self, text, style=None):
        if HAS_PROMPT_TOOLKIT and style:
            from prompt_toolkit import print_formatted_text
            from prompt_toolkit.formatted_text import FormattedText
            print_formatted_text(FormattedText([(style, text)]))
        else:
            print(text)

    def _handle_command(self, cmd):
        cmd = cmd.strip()
        # Route Chinese continue/retry commands to the agent
        if cmd in ("继续", "还有吗", "下一页", "再来"):
            self._print("Searching next page...", "status")
            result = self.agent.run("continue")
            print(result)
            print()
            return True
        elif cmd in ("不是这个", "不对", "换一批", "换个", "重新搜"):
            self._print("Re-searching...", "status")
            result = self.agent.run("retry")
            print(result)
            print()
            return True
        elif cmd in ("退出", "quit", "exit", "q"):
            self.running = False
            self._print("Bye!", "info")
            return True
        elif cmd in ("帮助", "help", "h", "?"):
            print(HELP_TEXT)
            return True
        elif cmd in ("新建对话", "new"):
            self.agent.memory.clear_session()
            self._print("New session started", "info")
            return True
        elif cmd in ("清除记忆", "clear"):
            self.agent.memory.clear_session()
            self._print("Memory cleared", "info")
            return True
        return False

    def run(self):
        self._print(BANNER)
        print(HELP_TEXT)
        try:
            config = load_config()
            llm = config.get("llm", {})
            self._print(f"LLM: {llm.get('model','?')} @ {llm.get('url','?')}", "status")
        except Exception as e:
            self._print(f"config: {e}", "status")
        print()
        while self.running:
            try:
                if self.session:
                    user_input = self.session.prompt([("class:prompt", ">>> ")])
                else:
                    user_input = input(">>> ")
                user_input = user_input.strip()
                if not user_input:
                    continue
                if self._handle_command(user_input):
                    continue
                self._print("Searching...", "status")
                result = self.agent.run(user_input)
                print(result)
                print()
            except KeyboardInterrupt:
                print("\n")
                continue
            except EOFError:
                self._print("\nBye!", "info")
                break
            except Exception as e:
                logger.exception("agent error")
                self._print(f"Error: {e}", "info")
                print()

def main():
    CLI().run()

if __name__ == "__main__":
    main()
