# 2.6.15 config.yaml change

# In your add-on config.yaml, change telegram_chat_id in the schema section
# from a visible string field to a password field.

# BEFORE:
schema:
  telegram_bot_token: password
  telegram_chat_id: str

# AFTER:
schema:
  telegram_bot_token: password
  telegram_chat_id: password

# Keep the options value as a string:
options:
  telegram_bot_token: ""
  telegram_chat_id: ""

# Notes:
# - This only changes how the native Home Assistant add-on Options screen displays the field.
# - The Telegram chat ID will be masked/redacted like the bot token.
# - The Python code can still read it normally as text.
# - Do not change this to int if you want it masked.
