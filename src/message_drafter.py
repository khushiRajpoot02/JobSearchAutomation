"""
Referral message drafter using Google Gemini 2.5 Pro.

The prompt is carefully engineered to produce messages that are:
  • Warm and personalised (mentions the recipient's role + company)
  • Brief (< 200 words — ideal for LinkedIn messages)
  • Polite but not forgettable — avoids clichés like "I hope this finds you well"
  • Ends gracefully regardless of whether the referral is given
"""

import google.generativeai as genai

from config import (
    GEMINI_API_KEY,
    CANDIDATE_NAME,
    CANDIDATE_LINKEDIN,
    YEARS_OF_EXPERIENCE,
)

# ---------------------------------------------------------------------------
# Gemini client (initialised once per process)
# ---------------------------------------------------------------------------

_model = None   # lazy-initialised


def _get_model():
    global _model
    if _model is None:
        genai.configure(api_key=GEMINI_API_KEY)
        _model = genai.GenerativeModel("gemini-3.1-pro")
    return _model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def draft_referral_message(connection: dict) -> str:
    """
    Generates a personalised LinkedIn referral-request message for one
    accepted connection.

    `connection` is a row-dict from the Connections sheet, so keys match
    CONNECTION_COLUMNS (e.g. "Connection Name", "Their Role", "Company Name").
    It may also carry a "snippet" key from the SerpAPI profile-search result.
    """
    name         = connection.get("Connection Name") or connection.get("name", "")
    their_role   = connection.get("Their Role")      or connection.get("job_title", "")
    company      = connection.get("Company Name")    or connection.get("company_name", "")
    snippet      = connection.get("snippet", "")

    first_name   = name.split()[0] if name else "there"
    role_context = f"as {their_role}" if their_role else "at the company"

    prompt = f"""You are helping {CANDIDATE_NAME}, a Senior Flutter Developer with {YEARS_OF_EXPERIENCE} years of experience, draft a LinkedIn message to request a referral.

About {CANDIDATE_NAME}:
- {YEARS_OF_EXPERIENCE} years of Flutter / Dart / FlutterFlow experience
- Built cross-platform apps (Android + iOS) for clients in the US, France, Switzerland, and Ireland
- Domains: AI, healthcare, ERP, e-commerce, education
- IIT Mandi graduate (B.Tech Computer Science, CGPA 8.23)
- Currently a Flutter Developer at Unico Connect, Mumbai
- LinkedIn: {CANDIDATE_LINKEDIN}

Recipient: {name}
Recipient works {role_context} at {company}.
Additional context from their profile: {snippet if snippet else "Not available."}

Write a LinkedIn direct message (NOT an email, no subject line) that:
1. Opens with "Hi {first_name}," — no generic openers like "I hope this message finds you well"
2. Has a genuine, human opening line (maybe a brief compliment on their work or company — don't be sycophantic)
3. Introduces {CANDIDATE_NAME} in 2-3 lines — focus on what makes him interesting, not a resume dump
4. Mentions that he noticed an open Flutter developer role at {company} and is very interested
5. Politely asks if they'd be comfortable referring him — makes it easy to say no
6. Closes warmly — open to connecting regardless of the referral outcome
7. Stays under 180 words
8. Sounds like a real person wrote it, not an AI or a template

Output only the message text. No quotes, no subject line, no preamble."""

    try:
        model    = _get_model()
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        print(f"    [Gemini] Error drafting message for {name}: {exc}")
        return _fallback_message(first_name, company, their_role)


# ---------------------------------------------------------------------------
# Fallback (used when the API call fails)
# ---------------------------------------------------------------------------

def _fallback_message(first_name: str, company: str, their_role: str) -> str:
    """
    A high-quality hand-crafted template used only when Gemini is unavailable.
    Still feels personal enough to send after a quick read-through.
    """
    role_line = (
        f"Given your role {their_role} at {company}, I thought you might be a great person to reach out to."
        if their_role
        else f"I thought you'd be a great person to reach out to at {company}."
    )

    return f"""Hi {first_name},

I've been following {company}'s work and it genuinely stands out — which is why I was excited to see an open Flutter developer role there.

I'm Arpit, a Flutter developer with 5 years of experience building cross-platform apps for clients across the US, Europe, and India. I've led teams, worked on AI-integrated mobile products, and have a solid grasp of Flutter architecture (BLoC, GetX, FlutterFlow). I'm an IIT Mandi grad and currently at Unico Connect.

{role_line}

Would you be comfortable referring me for the Flutter role? I completely understand if it's not something you can do — either way, I'd love to stay connected.

Thanks so much for your time, {first_name}!

Arpit
{CANDIDATE_LINKEDIN}"""
