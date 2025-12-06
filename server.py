from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from agent import answer_question

from datetime import datetime
from pathlib import Path
import csv
import smtplib
from email.message import EmailMessage
import os  # 🔹 NEW: for environment variables

app = FastAPI()

# Allow your browser (and later, real sites) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # later you can restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- CONFIG: EMAIL (NOW FROM ENV VARS) ----------

# These will come from environment variables (locally + Railway)
SENDER_EMAIL = os.environ.get("SENDER_EMAIL")
APP_PASSWORD = os.environ.get("APP_PASSWORD")
BUSINESS_EMAIL = os.environ.get("BUSINESS_EMAIL")

# CSV file where leads are stored
LEADS_CSV = Path("leads.csv")


# ---------- MODELS ----------

class ChatRequest(BaseModel):
    message: str


class LeadRequest(BaseModel):
    name: str
    email: str
    message: str


# ---------- CHAT ENDPOINT ----------

@app.post("/chat")
async def chat(req: ChatRequest):
    reply = answer_question(req.message)
    return {"reply": reply}


# ---------- HELPER: SAVE LEAD TO CSV ----------

def save_lead_to_csv(lead: LeadRequest) -> None:
    is_new_file = not LEADS_CSV.exists()

    with LEADS_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # If the file is new, write the header first
        if is_new_file:
            writer.writerow(["timestamp", "name", "email", "message"])

        writer.writerow([
            datetime.now().isoformat(timespec="seconds"),
            lead.name,
            lead.email,
            lead.message,
        ])


# ---------- HELPER: SEND LEAD EMAIL ----------

def send_lead_email(lead: LeadRequest) -> None:
    """
    Sends an email to BUSINESS_EMAIL with the lead details.
    Uses Gmail SMTP with app password.
    """
    # If email config is missing, just log and skip sending
    if not SENDER_EMAIL or not APP_PASSWORD or not BUSINESS_EMAIL:
        print("Email config missing (SENDER_EMAIL / APP_PASSWORD / BUSINESS_EMAIL). Skipping email send.")
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

    # Connect to Gmail SMTP and send
    with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
        smtp.starttls()
        smtp.login(SENDER_EMAIL, APP_PASSWORD)
        smtp.send_message(msg)


# ---------- LEAD ENDPOINT ----------

@app.post("/lead")
async def lead(req: LeadRequest):
    # Save to CSV file
    save_lead_to_csv(req)

    # Try to send email; if it fails, we still return status=ok
    try:
        send_lead_email(req)
        print("Lead email sent successfully.")
        return {"status": "ok", "emailed": True}
    except Exception as e:
        print("Error sending lead email:", e)
        return {"status": "ok", "emailed": False}


# ---------- MAIN ----------

if __name__ == "__main__":
    # For Railway (and locally): read PORT from env, default to 8000
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)