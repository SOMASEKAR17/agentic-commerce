import os, json
from anthropic import Anthropic

client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM = """You are a shopping intent extraction agent. Given the conversation so far,
output ONLY valid JSON, nothing else, matching this schema:
{"product": str|null, "budget": int|null, "wireless": bool|null, "noise_cancellation": bool|null,
 "complete": bool, "clarifying_question": str|null}
Set "complete": true once you have at least product and budget, or after 3 clarifying
questions have already been asked in this conversation.
If not complete, set "clarifying_question" to ONE short question to ask next, and leave
other unknown fields null."""

def extract_intent(conversation: list[dict]) -> dict:
    resp = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        system=SYSTEM,
        messages=conversation,
    )
    text = resp.content[0].text
    return json.loads(text)