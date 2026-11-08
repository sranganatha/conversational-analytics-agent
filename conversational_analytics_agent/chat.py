"""A local six-turn CLI over the pinned model and synthetic caller scope."""

import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from .agent import ConversationAgent
from .contracts import MAX_TURNS, Caller, ContractError
from .fixtures import load_json
from .model import OllamaModel
from .store import SessionStore
from .tools import EvidenceTools


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    config = load_json(root / "config" / "model.json")
    model = OllamaModel(os.environ.get("OLLAMA_URL", "http://ollama:11434"), config["name"])
    model.preflight(config["digest"])
    caller = Caller.parse({"subject": "local-analyst", "allowed_queues": ["intake", "review"]})
    with TemporaryDirectory() as temporary:
        store = SessionStore(Path(temporary) / "sessions.sqlite")
        session = store.create(caller, datetime.now(timezone.utc))
        agent = ConversationAgent(model, EvidenceTools(), store)
        version = 0
        print("Synthetic service analytics. Enter a question, or 'quit' to exit. Session limit: six turns.")
        while version < MAX_TURNS:
            try:
                message = input("> ")
            except (EOFError, KeyboardInterrupt):
                break
            if message.strip().lower() == "quit":
                break
            try:
                result = agent.run({"session_id": session.session_id, "expected_version": version,
                                    "message": message}, caller)
                version = result["version"]
                answer = result["answer"]
                print(f"{answer['status']}: {answer['message']}")
                if answer["evidence_ids"]:
                    print("Sources: " + ", ".join(answer["evidence_ids"]))
                if answer["error_code"]:
                    print("Error: " + answer["error_code"])
            except ContractError as exc:
                print("Error: " + exc.code)


if __name__ == "__main__":
    main()
