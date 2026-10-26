"""Secure GPT: a private, ChatGPT/Claude-style chat app on the organisation's own Azure OpenAI resource.

Why it exists: employees were pasting company data into public AI tools. This app gives them the same kind of
experience, but prompts go only to the company's Azure OpenAI deployment (no training on your data), access is
limited to approved staff, a data-leak guard checks prompts, and conversations are NOT stored by the app.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dlp import scan

log = logging.getLogger("secure-gpt")
logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT = (Path(__file__).parent / "agent.md").read_text(encoding="utf-8")
DLP_MODE = os.getenv("DLP_MODE", "redact")  # off | warn | redact | block

app = FastAPI(title="Secure GPT")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=20000)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=40)


def current_user(x_ms_client_principal_name: str | None = Header(default=None)) -> str:
    """Easy Auth (Entra ID) puts the signed-in user in this header. Allow-list is optional."""
    if os.getenv("REQUIRE_AUTH", "false").lower() != "true":
        return x_ms_client_principal_name or "anonymous-dev"
    allowed = {u.strip().lower() for u in os.getenv("ALLOWED_USERS", "").split(",") if u.strip()}
    if not x_ms_client_principal_name:
        raise HTTPException(401, "Sign-in required")
    if allowed and x_ms_client_principal_name.lower() not in allowed:
        raise HTTPException(403, "You are not approved to use this tool")
    return x_ms_client_principal_name


def _client():
    from openai import AsyncAzureOpenAI
    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
    key = os.getenv("AZURE_OPENAI_API_KEY")
    if key:
        return AsyncAzureOpenAI(azure_endpoint=endpoint, api_key=key, api_version=version)
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
    return AsyncAzureOpenAI(azure_endpoint=endpoint, azure_ad_token_provider=provider, api_version=version)


async def complete(messages: list[dict]) -> tuple[str, int | None]:
    if not os.getenv("AZURE_OPENAI_ENDPOINT"):  # offline demo mode
        last = next(m["content"] for m in reversed(messages) if m["role"] == "user")
        return f"(offline demo mode) I would send this to your private Azure OpenAI deployment:\n\n{last}", None
    resp = await _client().chat.completions.create(model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"), messages=messages, temperature=0.3)
    return resp.choices[0].message.content or "", resp.usage.total_tokens if resp.usage else None


@app.get("/")
def index():
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/health")
def health():
    return {"status": "ok", "mode": "azure" if os.getenv("AZURE_OPENAI_ENDPOINT") else "offline-demo", "dlp": DLP_MODE}


@app.post("/api/chat")
async def chat(req: ChatRequest, user: str = Depends(current_user)):
    msgs = [m.model_dump() for m in req.messages]
    notice = None
    if DLP_MODE != "off":
        findings: list[str] = []
        for m in msgs:
            if m["role"] != "user":
                continue
            s = scan(m["content"])
            if s.findings:
                findings += [f for f in s.findings if f not in findings]
                if DLP_MODE == "redact":
                    m["content"] = s.redacted
        if findings and DLP_MODE == "block":
            log.info("blocked user=%s findings=%s", user, findings)
            raise HTTPException(422, f"Message blocked: it appears to contain sensitive data ({', '.join(findings)}). Remove it and try again.")
        if findings:
            notice = f"Sensitive data detected ({', '.join(findings)})" + (" and removed before sending." if DLP_MODE == "redact" else ".")
    answer, tokens = await complete([{"role": "system", "content": SYSTEM_PROMPT}] + msgs)
    log.info("chat user=%s turns=%d tokens=%s dlp=%s", user, len(msgs), tokens, notice is not None)  # metadata only, never content
    return {"answer": answer, "notice": notice}
