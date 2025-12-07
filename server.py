import os
import csv
import json
from datetime import datetime
from pathlib import Path
from urllib import request, error  # <-- for Resend HTTP call

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from agent import answer_question

# ---------- ENV VARS (SET IN RAILWAY) ----------

# These should be set in Railway for EACH service:
#
# OPENAI_API_KEY   = your OpenAI key (already working)
# RESEND_API_KEY   = your key from Resend
# SENDER_EMAIL     = e.g. onboarding@resend.dev  (recommended)
# BUSINESS_EMAIL   = where the lead should go (your Gmail, client email, etc.)

SENDER_EMAIL = os.getenv("SENDER_EMAIL", "onboarding@resend.dev")
BUSINESS_EMAIL = os.getenv("BUSINESS_EMAIL", "zander.gross1@gmail.com")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")

# CSV file where leads are stored (per service/client)
LEADS_CSV = Path("leads.csv")

# ---------- FASTAPI APP SETUP ----------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # You can lock this down later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- REQUEST MODELS ----------

class ChatRequest(BaseModel):
    message: str


class LeadRequest(BaseModel):
    name: str
    email: str
    message: str


# ---------- CHAT ENDPOINT ----------

@app.post("/chat")
async def chat(req: ChatRequest):
    """
    Main chat endpoint.
    Forwards the message to agent.answer_question and returns the reply.
    """
    reply = answer_question(req.message)
    return {"reply": reply}


# ---------- LEAD HELPERS ----------

def save_lead_to_csv(lead: LeadRequest) -> None:
    """
    Append the lead to leads.csv with a timestamp.
    Creates the file with a header row if it doesn't exist yet.
    """
    is_new_file = not LEADS_CSV.exists()

    with LEADS_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if is_new_file:
            writer.writerow(["timestamp", "name", "email", "message"])

        writer.writerow(
            [
                datetime.now().isoformat(timespec="seconds"),
                lead.name,
                lead.email,
                lead.message,
            ]
        )


def send_lead_email(lead: LeadRequest) -> None:
    """
    Sends an email to BUSINESS_EMAIL with the lead details using Resend's HTTP API.
    Runs as a background task so it never blocks the API response.
    """
    if not RESEND_API_KEY:
        print("⚠️ RESEND_API_KEY is not set; skipping email send.")
        return

    subject = f"New website lead from {lead.name}"
    html_body = f"""
      <p>New lead from your website:</p>
      <ul>
        <li><strong>Name:</strong> {lead.name}</li>
        <li><strong>Email:</strong> {lead.email}</li>
      </ul>
      <p><strong>Message:</strong></p>
      <p>{lead.message}</p>
      <p>Received at: {datetime.now().isoformat(timespec="seconds")}</p>
    """

    payload = {
        "from": f"LeadFlowHQ <{SENDER_EMAIL}>",
        "to": [BUSINESS_EMAIL],
        "subject": subject,
        "html": html_body,
    }

    data_bytes = json.dumps(payload).encode("utf-8")

    req_obj = request.Request(
        "https://api.resend.com/emails",
        data=data_bytes,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {RESEND_API_KEY}",
        },
    )

    try:
        with request.urlopen(req_obj, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            print("✅ Resend email sent. Status:", resp.status, "Body:", body)
    except error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        print("❌ Resend HTTPError:", e.code, err_body)
    except Exception as e:
        print("❌ Error sending lead email via Resend:", repr(e))


# ---------- LEAD ENDPOINT ----------

@app.post("/lead")
async def lead(req: LeadRequest, background_tasks: BackgroundTasks):
    """
    Receive a lead from the frontend widget.

    - Save immediately to CSV so nothing is lost.
    - Queue email sending as a background task (non-blocking).
    - Return a fast JSON response so the widget can instantly say "Got it".
    """
    # 1) Save to CSV synchronously (very fast)
    save_lead_to_csv(req)

    # 2) Email in the background
    background_tasks.add_task(send_lead_email, req)

    # 3) Respond immediately
    return {
        "status": "ok",
        "received": True,
        "emailed": True,  # "we tried to email"; actual failures are only logged
        "message": "Lead captured successfully.",
    }


# ---------- LOCAL DEV ENTRYPOINT ----------

if __name__ == "__main__":
    # For running locally: python server.py
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)