from pathlib import Path
import re

path = Path("config.yaml")
if not path.exists():
    raise SystemExit("config.yaml not found in current directory")

text = path.read_text(encoding="utf-8")

# Change telegram_chat_id schema to password while preserving indentation.
text_new = re.sub(
    r"^(\s*telegram_chat_id\s*:\s*)(str|string|int)\s*$",
    r"\1password",
    text,
    flags=re.MULTILINE,
)

if text_new == text:
    print("No telegram_chat_id schema line changed. Check config.yaml manually.")
else:
    path.write_text(text_new, encoding="utf-8")
    print("Updated telegram_chat_id schema to password.")
