# Runway

Photograph a syllabus, timetable or assignment sheet (or just type your dates) and Runway pulls out every deadline, ranks them by urgency, tells you when to start each one, and emails you a digest with a calendar file.

Built with Streamlit, Gemini (chat + vision) and Gmail SMTP.

## What makes it different

- **Countdown cards**: every deadline shows days left, colour-coded from overdue to comfortable.
- **Start-by dates**: estimates effort per task and tells you when to begin.
- **Crunch-week detector**: warns you when one week has 3+ deadlines or 10+ hours of work.
- **Calendar file**: the email includes an `.ics` file with a one-day-before reminder on every event, so all deadlines go into Google Calendar in one tap.
- **Study plans**: ask for a plan for a subject and get a day-by-day schedule (units, topics, hours) with tick-off days, included in the email and calendar file.
- **Multi-photo upload and chat history**: send several photos in one message. Every chat is saved under your email, so after logging in again you see your History in the sidebar and can reopen any chat. Data lives in a local `data/` folder, which is git-ignored.
- **Two calendar files**: deadlines (with a reminder the day before) and the study plan are attached separately.
- **Date-aware AI**: knows today's date, so "next Friday" and dates without a year resolve correctly.
- **Fails gracefully**: if a photo has no dates, it asks for a better photo instead of guessing.
- **Scoped prompt**: only talks about deadlines, schedules and study planning.

## Run locally

1. Python 3.9+ and a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate        # Windows: .\venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```
2. Get a Gemini API key from [Google AI Studio](https://aistudio.google.com).
3. On the sending Gmail account, turn on 2-Step Verification, then create an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
4. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml` and fill in the three values.
5. Run:
   ```
   streamlit run app.py
   ```

## Deploy

Push to GitHub (never commit `secrets.toml`), create the app on [share.streamlit.io](https://share.streamlit.io) with `app.py` as the entry point, and paste your secrets into Settings > Secrets.

## Files

- `app.py`: UI, Gemini calls, email and calendar builders
- `prompts.py`: system prompt, welcome message, sample text
- `requirements.txt`, `.gitignore`, `.streamlit/secrets.toml.example`