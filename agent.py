import os
from datetime import datetime
from pathlib import Path

from openai import OpenAI

# --- OpenAI client & model ---

client = OpenAI()  # uses OPENAI_API_KEY from your environment
MODEL = "gpt-4.1-mini"

# --- CONFIG: WHICH CLIENT IS THIS INSTANCE FOR? ---
# This lets the same codebase serve different businesses.
# Locally you can use the default; in Railway you set CLIENT_ID per service.
CLIENT_ID = os.getenv("CLIENT_ID", "summit_family_dental")

BASE_DIR = Path(__file__).parent
CLIENT_DIR = BASE_DIR / "clients" / CLIENT_ID

FAQ_FILE = CLIENT_DIR / "faq.txt"
TONE_FILE = CLIENT_DIR / "tone.txt"
LOG_FILE = CLIENT_DIR / "conversations.log"

# --- SIMPLE GLOBAL STATE FOR YES/NO LEAD CONFIRM ---
# NOTE: This is per backend process (fine for low-traffic demos).
AWAITING_LEAD_CONFIRM = False

YES_WORDS = [
    "yes",
    "yeah",
    "yep",
    "sure",
    "yes please",
    "please do",
    "that would be great",
    "ok",
    "okay",
    "sounds good",
]
NO_WORDS = [
    "no",
    "nope",
    "nah",
    "not now",
    "not yet",
    "i'm good",
    "im good",
    "i am good",
    "i'm okay",
    "im okay",
]


def load_faq() -> str:
    """
    Load FAQ / business info from the client's faq.txt.
    This is what you'll customize per client.
    """
    path = FAQ_FILE
    if not path.exists():
        return "No FAQ data found. The business owner has not provided any information yet."
    return path.read_text(encoding="utf-8")


def load_tone() -> str:
    """
    Load optional tone / voice guidelines from tone.txt.

    This lets you change how the assistant sounds per client
    without touching Python code.
    """
    path = TONE_FILE
    if not path.exists():
        return ""  # tone is optional
    return path.read_text(encoding="utf-8")


def is_brief_ack(message: str) -> bool:
    """
    Detect things like: "thanks", "ok", "got it", "that helps", etc.
    We don't need the LLM for these – just send a quick friendly reply.

    IMPORTANT: we ONLY treat it as an ack if the whole message is
    basically just that phrase (not mixed with other intent).
    """
    txt = message.strip().lower()
    if not txt:
        return False

    ack_phrases = [
        "thanks",
        "thank you",
        "thx",
        "ok",
        "okay",
        "got it",
        "that helps",
        "perfect",
        "sounds good",
        "awesome",
        "great",
        "cool",
        "sweet",
        "appreciate it",
    ]

    # Only treat as an ack if it's SHORT and basically just that phrase
    if len(txt) > 30:
        return False

    return txt in ack_phrases


def wants_handoff(message: str) -> bool:
    """
    Detect when the user clearly wants to leave contact info
    or ask for a human to reach out.

    This MUST be strict so normal questions don't trigger it.
    """
    txt = message.strip().lower()
    if not txt:
        return False

    # --- STRICT single-word triggers ---
    # Only when they literally type "info" or "my info"
    if txt in {"info", "my info"}:
        return True

    # --- Clear, explicit intent phrases ---
    explicit_triggers = [
        "can i leave my info",
        "can i give you my info",
        "can i give u my info",
        "take my info",
        "take my information",
        "i want to give you my info",
        "i want to leave my info",
        "i want to give u my info",
        "i want to give u info",
        "leave my info",
        "leave my information",
        "give you my info",
        "give u my info",
        "share my info",
        "pass my info",
        "give my info",
        "give my information",
        "here is my info",
        "here's my info",
        "talk to a human",
        "speak to a human",
        "have someone call me",
        "have somebody call me",
        "have the office call me",
        "call me back",
        "can someone call me",
        "can somebody call me",
    ]

    if any(p in txt for p in explicit_triggers):
        return True

    # --- DO NOT trigger handoff if it's clearly a normal question ---
    # If the message ends with a question mark, treat as a question, not a handoff.
    if txt.endswith("?"):
        return False

    # If it looks like a general inquiry (about services, pain, hours, etc.), don't trigger.
    inquiry_words = [
        "offer",
        "offers",
        "do you have",
        "do you do",
        "price",
        "prices",
        "cost",
        "hours",
        "open",
        "close",
        "location",
        "where are you",
        "emergency",
        "tooth",
        "pain",
        "insurance",
        "whitening",
        "cleaning",
        "cleanings",
    ]
    if any(w in txt for w in inquiry_words):
        return False

    # --- Looser trigger: mention info/details + a giving verb ---
    # Only if they combine both "info/details" AND a clear action verb.
    has_info_word = any(
        word in txt for word in ["info", "information", "details", "contact"]
    )
    if has_info_word:
        verbs = ["leave", "give", "share", "pass", "provide", "send", "take"]
        if any(v in txt for v in verbs):
            return True

    return False


def _looks_like_yes(txt: str) -> bool:
    txt = txt.strip().lower()
    if not txt:
        return False
    for w in YES_WORDS:
        if txt == w or txt.startswith(w + " "):
            return True
    return False


def _looks_like_no(txt: str) -> bool:
    txt = txt.strip().lower()
    if not txt:
        return False
    for w in NO_WORDS:
        if txt == w or txt.startswith(w + " "):
            return True
    return False


def answer_question(question: str) -> str:
    """
    Use OpenAI to answer a customer question
    using the FAQ & tone settings for this client.
    Includes a very simple "yes/no lead confirm" mode.
    """
    global AWAITING_LEAD_CONFIRM

    raw_txt = question or ""
    lower_txt = raw_txt.strip().lower()

    # 🔹 1) If we're waiting for a YES/NO about a call, handle that first.
    if AWAITING_LEAD_CONFIRM:
        if _looks_like_yes(lower_txt):
            AWAITING_LEAD_CONFIRM = False
            # Tell frontend to start lead flow (collect phone, etc.)
            return "__TRIGGER_LEAD_FLOW__"

        if _looks_like_no(lower_txt):
            AWAITING_LEAD_CONFIRM = False
            return (
                "No problem at all — if you change your mind later, just let me know and I can have the team reach out."
            )

        # If they said something else, drop the flag and continue normally.
        AWAITING_LEAD_CONFIRM = False

    # 🔹 2) Fast path: simple "thanks / ok / got it"
    if is_brief_ack(raw_txt):
        return "You’re very welcome! 😊 If you have any other questions, just ask."

    # 🔹 3) Direct handoff intent → start lead flow immediately
    if wants_handoff(raw_txt):
        return "__TRIGGER_LEAD_FLOW__"

    faq_text = load_faq()
    tone_text = load_tone()

    # 🔹 4) Upgraded, agency-grade system prompt
    prompt = f"""
You are the **AI assistant for this local business**, acting like a warm, professional front-desk person.

You ONLY answer based on the information below (FAQ).  
Do NOT invent:
- prices
- medical advice
- business policies
- anything that is not clearly supported by the FAQ.

---

FAQ / BUSINESS INFO (INTERNAL ONLY, DO NOT SHOW TO CUSTOMER):
--------------------
{faq_text}
--------------------

{"TONE / VOICE GUIDELINES (INTERNAL ONLY):\n" + tone_text + "\n--------------------" if tone_text else ""}

Customer message:
"{question}"

---

## GENERAL BEHAVIOR

- Be concise: usually **1–3 sentences**.
- Sound calm, friendly, and confident.
- Use simple language that a stressed or confused person can understand.
- If you truly don't know from the FAQ, say:
  > "That isn’t listed in the information I have, so the best next step is to contact the office directly."

---

## SPECIAL CASES YOU MUST HANDLE

### 1) Small talk / polite replies
If the customer says things like:
- "thanks", "thank you", "thx"
- "ok", "okay", "got it"
- "that helps", "sounds good", "perfect"

and nothing else important:
➡️ Respond with a **very short** friendly line, e.g.  
"Of course! Let me know if you need anything else."

(Do NOT repeat long explanations in this case.)

---

### 2) Pain / urgent issues
If they mention things like:
- "pain", "hurt", "emergency", "swelling", "can’t sleep from pain", "urgent"

➡️ Always:
1. Acknowledge the discomfort with empathy.
2. Mention that the business can help with urgent issues **only if** the FAQ supports that (for example, emergency visits).
3. Suggest contacting or calling the business as the best next step.

Example style (adapt, don’t copy):
"I'm sorry you're dealing with that. We can help with urgent concerns — the best next step is to contact the office so they can fit you in as soon as possible."

---

### 3) If they want someone to contact them / leave info
If the message clearly means:
- they want to **leave info**
- they say "take my info", "contact me", "have someone call me", or they type "info"

➡️ You **do NOT** answer normally.  
Instead you must return the exact special text:

__TRIGGER_LEAD_FLOW__

(That tells the website widget to start collecting their details.  
Do NOT add any extra words around it.)

---

### 4) List / bullet requests
If they ask:
- "Can you list your services?"
- "Can you summarize in bullet points?"
- "Can you give that to me in list form?"

➡️ Respond with:
- Short, clean bullet points
- Only the most relevant items
- No giant FAQ dump

Example style:
- Routine cleanings and checkups  
- X-rays and exams  
- Fillings and crowns

---

### 5) Tone
- Helpful, not pushy.
- Professional but relaxed.
- Talk like a real front-desk human, not a robot.
- Avoid big blocks of text — break things into short sentences.

---

Now, based on the FAQ, tone guidelines, and the message above, respond to the customer in a single, well-formatted answer (1–3 sentences).  
Do NOT show the FAQ or tone text itself.  
Do NOT mention that you are an AI or that you are using a prompt.
"""

    # ---- Call OpenAI Responses API ----
    resp = client.responses.create(
        model=MODEL,
        input=prompt,
    )

    # Extract plain text from the response object
    try:
        text = resp.output[0].content[0].text
    except Exception:
        return "I'm sorry, something went wrong generating a reply. Please try again."

    answer = text.strip()

    # 🔹 5) After generating an answer, decide if we should ask:
    #    "Want me to have the team call you? Just say yes."
    # We only set this when it sounds like a pain/appointment situation,
    # and only if they haven't already explicitly asked for a handoff.
    lower = lower_txt

    pain_keywords = [
        "pain",
        "hurts",
        "hurt",
        "ache",
        "aching",
        "injury",
        "injured",
        "emergency",
        "swollen",
        "swelling",
        "can't sleep",
        "cant sleep",
        "stiff",
        "spasm",
        "spasms",
        "numb",
        "numbness",
        "tingling",
        "tingly",
    ]
    appointment_keywords = [
        "appointment",
        "appt",
        "appts",
        "visit",
        "come in",
        "come by",
        "see someone",
        "see the doctor",
        "see the dentist",
        "see the chiropractor",
        "see the chiro",
        "schedule",
        "book",
    ]

    looks_like_pain_or_appt = any(k in lower for k in pain_keywords + appointment_keywords)

    if looks_like_pain_or_appt and not wants_handoff(raw_txt):
        # Set flag so the NEXT message can be a simple "yes/no".
        AWAITING_LEAD_CONFIRM = True
        answer += (
            "\n\nIf you'd like, I can have the team give you a call to help with this — "
            "just reply 'yes' and I'll collect your phone number."
        )

    return answer


def log_interaction(question: str, answer: str) -> None:
    """
    Append each Q&A to the client's conversations.log so the business
    can review what customers ask and what the AI replies.
    """
    timestamp = datetime.now().isoformat(timespec="seconds")
    line = (
        f"[{timestamp}]\n"
        f"Q: {question}\n"
        f"A: {answer}\n"
        f"{'-'*40}\n"
    )
    # Ensure the client directory exists
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line)


def main():
    print(f"AI FAQ Assistant Ready (OpenAI). Client: {CLIENT_ID}")
    print("Using clients/<CLIENT_ID>/faq.txt for business information.")
    print("Type 'exit' to quit.\n")

    while True:
        user_q = input("Customer: ").strip()
        if not user_q:
            continue

        if user_q.lower() == "exit":
            break

        answer = answer_question(user_q)
        print("\nAssistant:", answer, "\n")

        # save it for later review
        log_interaction(user_q, answer)


if __name__ == "__main__":
    main()