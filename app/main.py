from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from app.db import init_db
from app.agents.buyer_agent import extract_intent
from app.agents.merchant_agent import search_and_rank

app = FastAPI()
init_db()

SESSIONS: dict[str, list] = {}  # in-memory, fine for a hackathon demo

class ChatIn(BaseModel):
    session_id: str
    message: str

@app.get("/")
def home():
    return FileResponse("app/static/chat.html")

@app.post("/chat")
def chat(payload: ChatIn):
    convo = SESSIONS.setdefault(payload.session_id, [])
    convo.append({"role": "user", "content": payload.message})

    intent = extract_intent(convo)
    convo.append({"role": "assistant", "content": str(intent)})

    if not intent.get("complete"):
        return {"reply": intent.get("clarifying_question", "Tell me more?"), "done": False}

    top, offer = search_and_rank(intent)
    return {"reply": "Here's what I found within your budget.", "done": True, "products": top, "offer": offer}