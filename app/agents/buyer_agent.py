import os, json
from groq import Groq

client = Groq(api_key=os.environ["GROQ_API_KEY"])

SYSTEM = """You are a shopping intent extraction agent. Given the conversation so far,
output ONLY valid JSON, nothing else, matching this schema:
{"product": str|null, "budget": int|null, "wireless": bool|null, "noise_cancellation": bool|null,
 "allow_bundle": bool|null, "complete": bool, "clarifying_question": str|null}
Set "allow_bundle": false if the user explicitly declines bundles, packages, accessories, or extras (e.g. "no bundle", "dont want bundle", "just the product", "no accessories"). Otherwise set "allow_bundle": true.
Set "complete": true once you have at least product and budget, or after 3 clarifying
questions have already been asked in this conversation.
If not complete, set "clarifying_question" to ONE short question to ask next, and leave
other unknown fields null."""

def extract_intent(conversation: list[dict]) -> dict:
    messages = [{"role": "system", "content": SYSTEM}] + conversation

    resp = client.chat.completions.create(
        model=os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b"),
        max_tokens=500,
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=messages,
    )
    text = resp.choices[0].message.content

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"product": None, "budget": None, "wireless": None,
                "noise_cancellation": None, "allow_bundle": True, "complete": False,
                "clarifying_question": "Sorry, could you rephrase that?"}