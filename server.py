import os
import csv
import smtplib
from datetime import datetime
from pathlib import Path
from email.message import EmailMessage

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from agent import answer_question

# ---------- ENV VARS (SET IN RAILWAY) ----------

SENDER_EMAIL = os.getenv("SENDER_EMAIL")         # e.g. theaiplugtiktok@gmail.com
APP_PASSWORD = os.getenv("APP_PASSWORD")         # Gmail app password
BUSINESS_EMAIL = os.getenv("BUSINESS_EMAIL")     # Where leads should be sent

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
    Sends an email to BUSINESS_EMAIL with the lead details.
    Runs as a background task so it never blocks the API response.
    """
    # If env vars are missing, just log and skip sending
    if not SENDER_EMAIL or not APP_PASSWORD or not BUSINESS_EMAIL:
        print("⚠️ Missing email configuration; skipping email send.")
        return

    msg = EmailMessage()
    msg["Subject"] = f"New website lead from {lead.name}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = BUSINESS_EMAIL

    body = (
        f"New lead from your website:\n\n"
        f"Name: {lead.name}\n"
        f"Email: {lead.email}\n"
        f"Message:\n{lead.message}\n\n"
        f"Received at: {datetime.now().isoformat(timespec='seconds')}"
    )
    msg.set_content(body)

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(SENDER_EMAIL, APP_PASSWORD)
            smtp.send_message(msg)
        print("✅ Lead email sent successfully.")
    except Exception as e:
        # Don't crash the app if email fails
        print("❌ Error sending lead email:", e)


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