import os
import json
from datetime import datetime
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
PROMPTS_DIR = BASE_DIR / "prompts"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
HISTORY_FILE = BASE_DIR / "history" / "marketing.json"

MAX_HISTORY_MESSAGES = 20   # max messages sent to API per call (keeps token cost down)
MAX_KNOWLEDGE_NOTES = 10    # max notes loaded from knowledge/marketing/


class MarketingAgent:
    def __init__(self):
        api_key = os.getenv("MARKETING_API_KEY")
        if not api_key:
            raise ValueError("MARKETING_API_KEY mangler i .env filen")

        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4o-mini"
        self.system_prompt = self._load_system_prompt()
        self.history = self._load_history()

    def _load_system_prompt(self):
        prompt_file = PROMPTS_DIR / "marketing.txt"
        if prompt_file.exists():
            return prompt_file.read_text(encoding="utf-8")
        return "Du er en marketing-assistent."

    def _load_knowledge(self):
        """Load notes from knowledge folders and inject into system prompt context."""
        notes = []

        # Load ALL files from shared/ — fælles viden alle agenter kan se
        shared_path = KNOWLEDGE_DIR / "shared"
        if shared_path.exists():
            for f in sorted(shared_path.glob("*.md")):
                notes.append(f"[Delt note: {f.name}]\n{f.read_text(encoding='utf-8')}")

        # Load the LAST 10 files from marketing/ sorted by filename (date prefix keeps order)
        marketing_path = KNOWLEDGE_DIR / "marketing"
        if marketing_path.exists():
            files = sorted(marketing_path.glob("*.md"))[-MAX_KNOWLEDGE_NOTES:]
            for f in files:
                notes.append(f"[Marketing note: {f.name}]\n{f.read_text(encoding='utf-8')}")

        return "\n\n---\n\n".join(notes) if notes else ""

    def _load_history(self):
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        if HISTORY_FILE.exists():
            try:
                return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
            except Exception:
                return []
        return []

    def _save_history(self):
        HISTORY_FILE.write_text(
            json.dumps(self.history, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )

    def _save_note(self, content):
        """Save content as a dated markdown note in knowledge/marketing/."""
        marketing_path = KNOWLEDGE_DIR / "marketing"
        marketing_path.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        note_file = marketing_path / f"{timestamp}-note.md"
        note_file.write_text(content, encoding="utf-8")
        return note_file.name

    def _is_save_command(self, text):
        triggers = ["gem det her", "husk det her", "gem dette", "husk dette", "gem det", "husk det"]
        return any(trigger in text.lower() for trigger in triggers)

    def _build_messages(self):
        """Build the full message list for the API call."""
        knowledge = self._load_knowledge()

        system = self.system_prompt
        if knowledge:
            system += f"\n\n═══ VIDENBASE ═══\n{knowledge}"

        messages = [{"role": "system", "content": system}]
        # Only send the last MAX_HISTORY_MESSAGES to keep token cost predictable
        messages.extend(self.history[-MAX_HISTORY_MESSAGES:])
        return messages

    def run(self):
        print("\nMarketing-agent er klar. Skriv 'exit' for at afslutte.\n")
        print("Tip: Sig 'gem det her' for at gemme agentens seneste svar som en note.\n")
        print("-" * 50)

        while True:
            try:
                user_input = input("\nDu: ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nSes næste gang.")
                self._save_history()
                break

            if not user_input:
                continue

            if user_input.lower() in ["exit", "quit", "afslut"]:
                print("Ses næste gang.")
                self._save_history()
                break

            # Handle save command — no API call needed
            if self._is_save_command(user_input):
                last_assistant = next(
                    (msg["content"] for msg in reversed(self.history) if msg["role"] == "assistant"),
                    None
                )
                if last_assistant:
                    filename = self._save_note(last_assistant)
                    print(f"\n[Gemt: knowledge/marketing/{filename}]")
                else:
                    print("\n[Ingen besked at gemme endnu — start en samtale først]")
                continue

            # Normal chat flow
            self.history.append({"role": "user", "content": user_input})

            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self._build_messages(),
                )
                reply = response.choices[0].message.content
                self.history.append({"role": "assistant", "content": reply})
                print(f"\nAgent: {reply}")
                self._save_history()

            except Exception as e:
                # Remove the user message we just added so history stays clean
                self.history.pop()
                print(f"\nFejl ved API-kald: {e}")
