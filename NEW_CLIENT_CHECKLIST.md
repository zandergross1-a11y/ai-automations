# New Client Setup Checklist – LeadFlowHQ

## 1) Create a new Railway service for this client
- [ ] Duplicate an existing working service (Summit or Chiro) in Railway.
- [ ] Name it after the business (example: `bright_smiles_dental`).

### Required ENV vars (Railway)
- [ ] `OPENAI_API_KEY`      → my OpenAI key  
- [ ] `RESEND_API_KEY`      → my Resend key  
- [ ] `SENDER_EMAIL`        → `onboarding@resend.dev`  
- [ ] `BUSINESS_EMAIL`      → where leads go (client’s email or mine for testing)  
- [ ] `CLIENT_ID`           → folder name under `clients/` (e.g. `summit_family_dental`)

---

## 2) Create the client folder in the repo
In `clients/`:

- [ ] Make a new folder: `clients/CLIENT_ID`  
  (example: `clients/bright_smiles_dental`)
- [ ] Add:
  - [ ] `faq.txt`     → their FAQs / bullet points  
  - [ ] `tone.txt`    → how they talk (friendly, professional, etc.)  
  - [ ] `demo_chat.html` → frontend widget for this client

---

## 3) Update the HTML widget (`demo_chat.html`)
In `clients/CLIENT_ID/demo_chat.html`:

- [ ] Set `CONFIG.businessName` to the real business name  
- [ ] Set `CONFIG.baseUrl` to this Railway service URL (e.g. `https://xxx.up.railway.app`)
- [ ] Change header subtitle: `Summit Family Dental • Smart website chat` → client name
- [ ] Update greeting text:
  - “I’m your AI assistant for …”
  - What it can answer about (hours, services, insurance, etc.)
- [ ] Make sure lead flow copy matches what we collect:
  - We are asking for **name + phone + what this is about**
  - No references to email anymore

---

## 4) Test like a real patient
- [ ] Open the `demo_chat.html` in the browser.
- [ ] Ask 3–5 realistic questions (hours, pricing, services).
- [ ] Trigger the lead flow (“I want to book an appointment”, click “Request a call”, etc.).
- [ ] Enter **realistic test data**:
  - Name
  - Phone
  - Reason
- [ ] Confirm:
  - [ ] Chat shows “Thanks! I’m sending your details…”  
  - [ ] You get an email from Resend with:
    - Correct **clinic name** in subject/body
    - **Name**, **Phone**, **Message** all correct

---

## 5) Before showing anything to the client
- [ ] Read through FAQ/tone and fix typos.
- [ ] Make sure no other clinic’s name appears anywhere.
- [ ] Do one last test chat + lead and check your inbox.