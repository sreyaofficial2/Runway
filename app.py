import hashlib
import json
import math
import re
import smtplib
import uuid
from datetime import date, datetime, timedelta, timezone
from email.message import EmailMessage
from html import escape
from pathlib import Path

import streamlit as st
from google import genai
from google.genai import types

from prompts import SAMPLE_TEXT, SYSTEM_PROMPT_TEMPLATE, WELCOME_MESSAGE_TEMPLATE

MODEL_NAME = "gemini-3.5-flash"
TIMEZONE = "Asia/Kolkata"
HOURS_PER_DAY = 2  # assumed study hours per day, used for the "start by" date
MAX_PHOTOS = 6  # photos per message
DATA_DIR = Path("data")  # per-user saved data (git-ignored)

st.set_page_config(page_title="Runway", page_icon="✈️", layout="centered")

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
GMAIL_ADDRESS = st.secrets["GMAIL_ADDRESS"]
GMAIL_APP_PASSWORD = st.secrets["GMAIL_APP_PASSWORD"]

# ---------------------------------------------------------------- styling
# Palette: paper #F5F2EA, ink navy #14213D, saffron gold #FCA311.
# Urgency colours: overdue red, critical orange, soon amber, later teal.

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:wght@500;700;800&family=Source+Sans+3:wght@400;600;700&display=swap');

/* Fonts: set on text elements only, so Streamlit's icon font keeps working. */
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button {
    font-family: 'Source Sans 3', sans-serif;
}
[data-testid="stIconMaterial"], .material-symbols-rounded {
    font-family: 'Material Symbols Rounded' !important;
}
h1, h2, h3, .rw-display, .rw-section, .rw-title, .rw-num {
    font-family: 'Bricolage Grotesque', sans-serif !important;
    letter-spacing: -0.02em;
}

.stApp { background: #F5F2EA; }
div.block-container { padding-top: 2rem; max-width: 820px; }

/* Hero banner with a runway centre line */
.rw-hero { background: #14213D; border-radius: 16px; padding: 1.3rem 1.6rem 1rem 1.6rem; margin: 0 0 1.1rem 0; color: #F5F2EA; }
.rw-display { font-weight: 800; font-size: 2.5rem; line-height: 1; color: #F5F2EA; }
.rw-tag { margin-top: 0.45rem; color: #cfd6e6; font-size: 1.05rem; }
.rw-strip { position: relative; height: 26px; margin-top: 1rem; }
.rw-strip::before { content: ""; position: absolute; left: 0; right: 0; top: 50%; border-top: 3px dashed #FCA311; opacity: 0.9; }
.rw-plane { position: absolute; top: -2px; font-size: 1.5rem; line-height: 26px; }

/* Onboarding feature row */
.rw-features { display: flex; gap: 0.7rem; margin: 0 0 1rem 0; }
.rw-feature { flex: 1; background: #fff; border: 1px solid #e3ddd0; border-radius: 12px; padding: 0.8rem 0.9rem; color: #14213D; }
.rw-feature .rw-title { font-weight: 700; font-size: 1.05rem; }
.rw-feature .rw-desc { font-size: 0.9rem; color: #6b7280; margin-top: 2px; }
[data-testid="stForm"] { background: #fff; border: 1px solid #e3ddd0; border-radius: 12px; padding: 1.2rem; }

/* Buttons: gold primary action */
button[kind="primary"], button[kind="primaryFormSubmit"],
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primaryFormSubmit"] {
    background: #FCA311; border: 1px solid #FCA311; color: #14213D; font-weight: 700; border-radius: 10px;
}
button[kind="primary"] p, button[kind="primaryFormSubmit"] p,
[data-testid="stBaseButton-primary"] p, [data-testid="stBaseButton-primaryFormSubmit"] p { color: #14213D; font-weight: 700; }
button[kind="primary"]:hover, button[kind="primaryFormSubmit"]:hover,
[data-testid="stBaseButton-primary"]:hover, [data-testid="stBaseButton-primaryFormSubmit"]:hover {
    background: #e8930a; border-color: #e8930a; color: #14213D;
}
.stButton > button, .stDownloadButton > button { border-radius: 10px; }

/* Tabs */
.stTabs [data-baseweb="tab"] p { font-weight: 600; font-size: 1.02rem; }
[data-baseweb="tab-highlight"] { background-color: #FCA311 !important; height: 3px; }

/* Chat */
[data-testid="stChatMessage"] { background: #fff; border: 1px solid #e3ddd0; border-radius: 14px; padding: 0.8rem 1rem; }
[data-testid="stChatMessage"] p { font-size: 1rem; line-height: 1.6; }

/* Metrics */
[data-testid="stMetric"] { background: #fff; border: 1px solid #e3ddd0; border-radius: 12px; padding: 0.6rem 0.8rem; }
[data-testid="stMetricValue"] { font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800; font-size: 1.7rem; color: #14213D; }
[data-testid="stMetricLabel"] p { font-size: 0.85rem; color: #6b7280; }

/* Deadline sections and ticket cards */
.rw-section { font-weight: 700; font-size: 1.15rem; color: #14213D; margin: 1.1rem 0 0.5rem 0; }
.rw-count { background: #14213D; color: #F5F2EA; border-radius: 999px; padding: 1px 9px; font-size: 0.8rem; margin-left: 6px; font-family: 'Source Sans 3', sans-serif; }
.rw-card { display: flex; background: #fff; border: 1px solid #e3ddd0; border-radius: 12px; overflow: hidden; margin: 0 0 0.55rem 0; }
.rw-card.done { opacity: 0.45; }
.rw-stub { position: relative; min-width: 84px; display: flex; flex-direction: column; align-items: center; justify-content: center;
           color: #fff; padding: 0.6rem 0.3rem; border-right: 2px dashed rgba(255,255,255,0.65); }
.rw-stub::before, .rw-stub::after { content: ""; position: absolute; right: -7px; width: 14px; height: 14px; border-radius: 50%; background: #F5F2EA; }
.rw-stub::before { top: -7px; }
.rw-stub::after { bottom: -7px; }
.rw-num { font-weight: 800; font-size: 1.9rem; line-height: 1; }
.rw-unit { font-size: 0.75rem; margin-top: 3px; }
.rw-body { padding: 0.7rem 1rem; flex: 1; }
.rw-card-title { font-family: 'Bricolage Grotesque', sans-serif; font-weight: 700; font-size: 1.1rem; color: #14213D; }
.rw-sub { color: #6b7280; font-size: 0.9rem; }
.rw-chips { margin-top: 0.4rem; }
.rw-chips span { display: inline-block; background: #F5F2EA; color: #14213D; border-radius: 6px; padding: 1px 9px; font-size: 0.82rem; margin: 0 6px 4px 0; }
.rw-note { color: #4a5568; font-size: 0.88rem; margin-top: 2px; }
.rw-crunch { background: #fff4e5; border: 1px solid #f3c581; border-left: 5px solid #E76F00; border-radius: 10px; padding: 0.7rem 1rem; color: #14213D; margin: 0.8rem 0; }
.rw-plan { background: #eaf4f2; border: 1px solid #b9ddd8; border-left: 5px solid #2A9D8F; border-radius: 10px; padding: 0.7rem 1rem; color: #14213D; margin: 0.8rem 0; }

/* Sidebar */
[data-testid="stSidebar"] { background: #14213D; }
[data-testid="stSidebarCollapseButton"] * { color: #F5F2EA !important; }
.rw-profile { display: flex; align-items: center; gap: 0.7rem; margin: 0.4rem 0 1rem 0; }
.rw-avatar { width: 46px; height: 46px; border-radius: 50%; background: #FCA311; color: #14213D; display: flex; align-items: center;
             justify-content: center; font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800; font-size: 1.3rem; }
.rw-side-name { color: #F5F2EA; font-weight: 700; font-size: 1.05rem; line-height: 1.2; }
.rw-side-mail { color: #aab4cb; font-size: 0.82rem; word-break: break-all; }
.rw-side-card { background: rgba(245,242,234,0.08); border: 1px solid rgba(245,242,234,0.15); border-radius: 12px; padding: 0.7rem 0.9rem;
                color: #F5F2EA; font-size: 0.95rem; line-height: 1.7; margin-bottom: 1rem; }
.rw-side-head { color: #aab4cb; font-weight: 700; font-size: 0.9rem; margin: 1rem 0 0.4rem 0; }
[class*="st-key-hist_"] button { justify-content: flex-start; }
[class*="st-key-hist_"] button p { text-align: left; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
[data-testid="stSidebar"] .stButton > button { background: transparent; border: 1px solid rgba(245,242,234,0.35); }
[data-testid="stSidebar"] .stButton > button p { color: #F5F2EA; }
[data-testid="stSidebar"] .stButton > button:hover { border-color: #FCA311; }
[data-testid="stSidebar"] .stButton > button:hover p { color: #FCA311; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

COLORS = {
    "overdue": "#C1121F",
    "critical": "#E76F00",
    "soon": "#C99700",
    "later": "#2A9D8F",
}

# ---------------------------------------------------------------- helpers


def today_local():
    try:
        from zoneinfo import ZoneInfo

        return datetime.now(ZoneInfo(TIMEZONE)).date()
    except Exception:
        return date.today()


@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


gemini_client = get_gemini_client()


def next_id():
    st.session_state.counter += 1
    return st.session_state.counter


def urgency(days_left):
    """Return (bucket, number shown on the stub, unit text)."""
    if days_left < 0:
        return "overdue", abs(days_left), "day late" if days_left == -1 else "days late"
    if days_left == 0:
        return "critical", "Today", ""
    if days_left <= 3:
        return "critical", days_left, "day left" if days_left == 1 else "days left"
    if days_left <= 7:
        return "soon", days_left, "days left"
    return "later", days_left, "days left"


def when_phrase(days_left):
    if days_left < 0:
        return f"was due {abs(days_left)} day{'s' if days_left != -1 else ''} ago"
    if days_left == 0:
        return "is due today"
    if days_left == 1:
        return "is due tomorrow"
    return f"is due in {days_left} days"


def start_by(due, hours, today):
    if due < today:
        return None
    days_needed = max(1, math.ceil(hours / HOURS_PER_DAY))
    return max(today, due - timedelta(days=days_needed))


def fmt_date(d):
    return f"{d.strftime('%a')}, {d.day} {d.strftime('%b')}"


def pending_items():
    items = [i for i in st.session_state.deadlines if not i["done"]]
    return sorted(items, key=lambda i: (i["date"], i["time"] or "99:99"))


def find_crunch(items, today):
    """Find the busiest upcoming week. Flags it when it has 3+ deadlines or 10+ hours of work."""
    weeks = {}
    for it in items:
        d = date.fromisoformat(it["date"])
        if d >= today:
            monday = d - timedelta(days=d.weekday())
            weeks.setdefault(monday, []).append(it)
    if not weeks:
        return None
    monday, group = max(weeks.items(), key=lambda kv: (sum(i["effort_hours"] for i in kv[1]), len(kv[1])))
    hours = sum(i["effort_hours"] for i in group)
    if len(group) >= 3 or hours >= 10:
        return {
            "start": monday,
            "end": monday + timedelta(days=6),
            "count": len(group),
            "hours": hours,
            "titles": [i["title"] for i in group],
        }
    return None


def crunch_text(c):
    span = f"{fmt_date(c['start'])} to {fmt_date(c['end'])}"
    if c["count"] == 1:
        return f"Heavy week: {span} needs about {c['hours']:g} hours of work for {c['titles'][0]}. Start early."
    return f"Crunch week: {span} has {c['count']} deadlines and roughly {c['hours']:g} hours of work. Start early."


# ---------------------------------------------------------------- Gemini

def parse_response(raw):
    """Read the first JSON object in the reply and ignore anything after it. Never show raw JSON to the user."""
    text = (raw or "").strip()
    start = text.find("{")
    if start != -1:
        try:
            data, _ = json.JSONDecoder().raw_decode(text[start:])
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass
        match = re.search(r'"reply"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if match:
            try:
                return {"reply": json.loads(f'"{match.group(1)}"'), "deadlines": [], "remove_titles": [], "plan": ""}
            except json.JSONDecodeError:
                pass
        return {
            "reply": "I couldn't read my own answer properly. Please send that again.",
            "deadlines": [],
            "remove_titles": [],
            "plan": "",
        }
    return {"reply": text or "I couldn't read that. Try again?", "deadlines": [], "remove_titles": [], "plan": ""}


def ask_gemini(parts):
    try:
        raw = st.session_state.chat.send_message(parts).text
        return parse_response(raw)
    except Exception as error:
        return {
            "reply": f"Something went wrong talking to Gemini: {error}",
            "deadlines": [],
            "remove_titles": [],
            "plan": "",
        }


def sanitize(raw):
    if not isinstance(raw, dict):
        return None
    try:
        due = date.fromisoformat(str(raw.get("date", "")).strip())
    except ValueError:
        return None
    title = str(raw.get("title", "")).strip()
    if not title:
        return None
    time_text = str(raw.get("time") or "").strip()
    try:
        datetime.strptime(time_text, "%H:%M")
    except ValueError:
        time_text = ""
    try:
        hours = min(max(float(raw.get("effort_hours") or 1), 0.5), 40)
    except (TypeError, ValueError):
        hours = 1.0
    return {
        "id": next_id(),
        "title": title[:120],
        "course": str(raw.get("course") or "")[:60],
        "type": str(raw.get("type") or "other")[:20],
        "date": due.isoformat(),
        "time": time_text,
        "effort_hours": hours,
        "notes": str(raw.get("notes") or "")[:160],
        "done": False,
    }


def sanitize_plan(raw):
    if not isinstance(raw, dict):
        return None
    days = []
    for entry in raw.get("days") or []:
        if not isinstance(entry, dict):
            continue
        try:
            day = date.fromisoformat(str(entry.get("date", "")).strip())
        except ValueError:
            continue
        focus = str(entry.get("focus", "")).strip()
        if not focus:
            continue
        topics_raw = entry.get("topics")
        topics = [str(t).strip()[:80] for t in topics_raw if str(t).strip()][:6] if isinstance(topics_raw, list) else []
        try:
            hours = min(max(float(entry.get("hours") or 1), 0.5), 12)
        except (TypeError, ValueError):
            hours = 1.0
        days.append({
            "id": next_id(),
            "date": day.isoformat(),
            "focus": focus[:100],
            "topics": topics,
            "hours": hours,
            "tip": str(entry.get("tip") or "")[:140],
            "done": False,
        })
    if not days:
        return None
    days.sort(key=lambda d: d["date"])
    try:
        exam = date.fromisoformat(str(raw.get("exam_date") or "").strip()).isoformat()
    except ValueError:
        exam = ""
    return {"subject": str(raw.get("subject") or "Study plan")[:60], "exam_date": exam, "days": days[:31]}


def apply_result(result):
    removed = {str(t).strip().lower() for t in result.get("remove_titles", []) or []}
    if removed:
        st.session_state.deadlines = [
            i for i in st.session_state.deadlines if i["title"].lower() not in removed
        ]
    existing = {(i["title"].lower(), i["date"]) for i in st.session_state.deadlines}
    added = 0
    for raw in result.get("deadlines", []) or []:
        item = sanitize(raw)
        if item and (item["title"].lower(), item["date"]) not in existing:
            st.session_state.deadlines.append(item)
            existing.add((item["title"].lower(), item["date"]))
            added += 1
    plan = str(result.get("plan") or "").strip()
    if plan:
        st.session_state.plan = plan
    plan_info = None
    study_plan = sanitize_plan(result.get("study_plan"))
    if study_plan:
        st.session_state.study_plans[study_plan["subject"].lower()] = study_plan
        plan_info = (study_plan["subject"], len(study_plan["days"]))
    return added, plan_info


# ---------------------------------------------------------------- email + calendar

def ics_escape(text):
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold_line(line):
    """Fold long calendar lines at 75 bytes (RFC 5545) without splitting a multi-byte character."""
    data = line.encode("utf-8")
    parts, limit = [], 75
    while len(data) > limit:
        cut = limit
        while cut > 0 and (data[cut] & 0xC0) == 0x80:
            cut -= 1
        parts.append(data[:cut].decode("utf-8"))
        data = data[cut:]
        limit = 74
    parts.append(data.decode("utf-8"))
    return "\r\n ".join(parts)


def wrap_calendar(event_lines):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Runway//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    lines += event_lines + ["END:VCALENDAR"]
    return "\r\n".join(fold_line(line) for line in lines) + "\r\n"


def build_ics(items):
    """Calendar file for deadlines, with a reminder the day before each one."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = []
    for it in items:
        due = date.fromisoformat(it["date"])
        summary = it["title"] + (f" ({it['course']})" if it["course"] else "")
        description = " | ".join(x for x in [it["type"], f"~{it['effort_hours']:g}h of work", it["notes"]] if x)
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uuid.uuid4()}@runway",
            f"DTSTAMP:{stamp}",
            f"SUMMARY:{ics_escape(summary)}",
            f"DESCRIPTION:{ics_escape(description)}",
        ]
        if it["time"]:
            start = datetime.combine(due, datetime.strptime(it["time"], "%H:%M").time())
            end = start + timedelta(hours=1)
            lines += [f"DTSTART:{start:%Y%m%dT%H%M%S}", f"DTEND:{end:%Y%m%dT%H%M%S}"]
        else:
            lines += [f"DTSTART;VALUE=DATE:{due:%Y%m%d}", f"DTEND;VALUE=DATE:{due + timedelta(days=1):%Y%m%d}"]
        lines += [
            "BEGIN:VALARM",
            "TRIGGER:-P1D",
            "ACTION:DISPLAY",
            "DESCRIPTION:Due tomorrow",
            "END:VALARM",
            "END:VEVENT",
        ]
    return wrap_calendar(lines)


def build_study_ics(plans, today):
    """Separate calendar file for study sessions. Returns an empty string when there are none."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = []
    for plan in plans:
        for day in plan["days"]:
            if day["done"] or day["date"] < today.isoformat():
                continue
            due = date.fromisoformat(day["date"])
            description = " | ".join(
                x for x in [f"{day['hours']:g}h", "; ".join(day["topics"]), day["tip"]] if x
            )
            lines += [
                "BEGIN:VEVENT",
                f"UID:{uuid.uuid4()}@runway",
                f"DTSTAMP:{stamp}",
                f"SUMMARY:{ics_escape('Study: ' + day['focus'] + ' (' + plan['subject'] + ')')}",
                f"DESCRIPTION:{ics_escape(description)}",
                f"DTSTART;VALUE=DATE:{due:%Y%m%d}",
                f"DTEND;VALUE=DATE:{due + timedelta(days=1):%Y%m%d}",
                "END:VEVENT",
            ]
    return wrap_calendar(lines) if lines else ""


def build_plans_email(plans, today):
    html, text = "", ""
    for plan in plans:
        rows = ""
        heading = f"Study plan: {plan['subject']}"
        if plan["exam_date"]:
            heading += f" (exam {fmt_date(date.fromisoformat(plan['exam_date']))})"
        text += f"\n\n{heading}"
        for day in plan["days"]:
            if day["done"] or day["date"] < today.isoformat():
                continue
            when = fmt_date(date.fromisoformat(day["date"]))
            topics = "; ".join(day["topics"])
            tip = f"<div style='font-size:13px;color:#2A9D8F;margin-top:2px'>Tip: {escape(day['tip'])}</div>" if day["tip"] else ""
            rows += (
                "<tr><td style='padding:8px 10px;background:#fff;border-bottom:1px solid #eee;vertical-align:top;"
                f"white-space:nowrap;font-weight:700;color:#14213D'>{escape(when)}</td>"
                "<td style='padding:8px 10px;background:#fff;border-bottom:1px solid #eee;color:#14213D'>"
                f"<div style='font-weight:700'>{escape(day['focus'])}</div>"
                f"<div style='font-size:13px;color:#4a5568'>{escape(topics)}</div>{tip}</td>"
                "<td style='padding:8px 10px;background:#fff;border-bottom:1px solid #eee;text-align:right;"
                f"white-space:nowrap;font-weight:700;color:#2A9D8F'>{day['hours']:g}h</td></tr>"
            )
            text += f"\n- {when}: {day['focus']} ({day['hours']:g}h) - {topics}"
        if rows:
            html += (
                f"<h3 style='color:#14213D;margin:22px 0 8px'>{escape(heading)}</h3>"
                f"<table width='100%' cellspacing='0' cellpadding='0'>{rows}</table>"
            )
    return html, text


def build_email(name, items, today, crunch, plan, plans=()):
    rows_html, rows_text = [], []
    for it in items:
        due = date.fromisoformat(it["date"])
        days_left = (due - today).days
        bucket, num, unit = urgency(days_left)
        color = COLORS[bucket]
        when = fmt_date(due) + (f", {it['time']}" if it["time"] else "")
        sb = start_by(due, it["effort_hours"], today)
        start_line = f"Start by {fmt_date(sb)}" if sb else "Past due"
        label = f"{num} {unit}".strip()
        sub = " - ".join(x for x in [it["course"], it["type"]] if x)
        rows_html.append(
            f"<tr><td style='padding:10px 12px;border-left:6px solid {color};background:#fff;"
            f"border-bottom:1px solid #eee'>"
            f"<div style='font-size:16px;font-weight:700;color:#14213D'>{escape(it['title'])}</div>"
            f"<div style='font-size:13px;color:#6b7280'>{escape(sub)}</div>"
            f"<div style='font-size:13px;color:#14213D;margin-top:4px'>{escape(when)} &nbsp;|&nbsp; "
            f"~{it['effort_hours']:g}h &nbsp;|&nbsp; {escape(start_line)}</div></td>"
            f"<td style='padding:10px 12px;background:#fff;border-bottom:1px solid #eee;text-align:right;"
            f"white-space:nowrap;font-weight:700;color:{color}'>{escape(label)}</td></tr>"
        )
        rows_text.append(f"- {it['title']} ({sub}) | {when} | {label} | {start_line}")

    crunch_html = (
        f"<div style='background:#fff4e5;border-left:5px solid #E76F00;padding:10px 12px;margin:12px 0;"
        f"color:#14213D'>{escape(crunch_text(crunch))}</div>" if crunch else ""
    )
    plan_html = (
        f"<div style='background:#eaf4f2;border-left:5px solid #2A9D8F;padding:10px 12px;margin:12px 0;"
        f"color:#14213D'>{escape(plan)}</div>" if plan else ""
    )
    deadlines_html = (
        f"<table width='100%' cellspacing='0' cellpadding='0'>{''.join(rows_html)}</table>" if rows_html else ""
    )
    plans_html, plans_text = build_plans_email(plans, today)
    intro = (
        f"{len(items)} pending, nearest first. " if items else "Your study plan is below. "
    ) + "The attached .ics file adds everything to your calendar."
    html_body = (
        "<div style='font-family:Arial,sans-serif;max-width:620px;margin:auto;background:#F5F2EA;padding:20px'>"
        f"<h2 style='margin:0;color:#14213D'>Your deadlines, {escape(name)}</h2>"
        f"<p style='color:#4a5568;margin:4px 0 12px'>{escape(intro)}</p>"
        f"{crunch_html}{plan_html}{deadlines_html}{plans_html}"
        "<p style='color:#6b7280;font-size:12px;margin-top:16px'>Sent by Runway.</p></div>"
    )
    text_body = f"Your deadlines, {name}\n\n" + "\n".join(rows_text)
    if crunch:
        text_body += "\n\n" + crunch_text(crunch)
    if plan:
        text_body += "\n\n" + plan
    text_body += plans_text
    return html_body, text_body


def send_email(to_address, subject, text_body, html_body, attachments):
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"Runway <{GMAIL_ADDRESS}>"
    message["To"] = to_address
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")
    for filename, ics_text in attachments:
        message.add_attachment(ics_text.encode("utf-8"), maintype="text", subtype="calendar", filename=filename)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(message)
        return True, ""
    except Exception as error:
        return False, str(error)


# ---------------------------------------------------------------- saved data and chat history

def user_file(email):
    digest = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()[:24]
    return DATA_DIR / f"{digest}.json"


def blank_chat():
    return {
        "title": "New chat",
        "created": datetime.now().isoformat(timespec="seconds"),
        "messages": [],
        "deadlines": [],
        "study_plans": {},
        "plan": "",
    }


def load_state(email):
    try:
        path = user_file(email)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if "chats" not in data:  # saved by an older version: keep it as one chat
        legacy = {**blank_chat(), **{k: data.get(k) for k in ("messages", "deadlines", "study_plans", "plan") if data.get(k)}}
        data = {"counter": data.get("counter") or 0, "chats": {uuid.uuid4().hex[:8]: legacy}}
    return data


def new_gemini_chat():
    today = today_local()
    system_prompt = SYSTEM_PROMPT_TEMPLATE.replace("__TODAY__", f"{today.strftime('%A')}, {today.isoformat()}")
    return gemini_client.chats.create(
        model=MODEL_NAME,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
        ),
    )


def chat_is_empty(chat):
    return not chat["deadlines"] and not chat["study_plans"] and not any(m["role"] == "user" for m in chat["messages"])


def saved_messages(messages):
    """Photos are not stored, so they become a short note."""
    out = []
    for m in messages[-60:]:
        if m["kind"] == "image":
            out.append({"role": m["role"], "kind": "text", "content": "📷 Photo sent"})
        else:
            out.append(m)
    return out


def auto_title(chat, messages):
    for m in messages:
        if m["role"] == "user" and m["kind"] == "text" and m["content"].strip():
            text = " ".join(m["content"].split())
            return text[:30] + ("…" if len(text) > 30 else "")
    if chat["deadlines"]:
        extra = len(chat["deadlines"]) - 1
        return chat["deadlines"][0]["title"][:30] + (f" +{extra}" if extra else "")
    if any(m["role"] == "user" and m["kind"] == "image" for m in messages):
        return "📷 Photo upload"
    return "New chat"


def snapshot_current():
    """Copy the chat on screen into the chat history."""
    chat_id = st.session_state.get("chat_id")
    if not chat_id or chat_id not in st.session_state.chats:
        return
    chat = st.session_state.chats[chat_id]
    chat["messages"] = saved_messages(st.session_state.messages)
    chat["deadlines"] = st.session_state.deadlines
    chat["study_plans"] = st.session_state.study_plans
    chat["plan"] = st.session_state.plan
    if chat["title"] == "New chat":
        chat["title"] = auto_title(chat, st.session_state.messages)


def load_into_working(chat_id):
    chat = st.session_state.chats[chat_id]
    st.session_state.chat_id = chat_id
    st.session_state.messages = list(chat["messages"])
    st.session_state.deadlines = chat["deadlines"]
    st.session_state.study_plans = chat["study_plans"]
    st.session_state.plan = chat["plan"]
    st.session_state.chat = new_gemini_chat()


def start_new_chat():
    """Open a fresh chat. An existing empty chat is reused so blank chats don't pile up."""
    snapshot_current()
    for chat_id, chat in st.session_state.chats.items():
        if chat_is_empty(chat):
            load_into_working(chat_id)
            return
    chat_id = uuid.uuid4().hex[:8]
    st.session_state.chats[chat_id] = blank_chat()
    load_into_working(chat_id)


def clear_everything():
    st.session_state.chats = {}
    st.session_state.chat_id = None
    try:
        user_file(st.session_state.email).unlink(missing_ok=True)
    except Exception:
        pass
    start_new_chat()


def save_state():
    """Save all of this user's chats. Failures are ignored."""
    try:
        snapshot_current()
        active = st.session_state.chat_id
        payload = {
            "name": st.session_state.name,
            "counter": st.session_state.counter,
            "active": active,
            "chats": {
                cid: c for cid, c in st.session_state.chats.items() if cid == active or not chat_is_empty(c)
            },
        }
        DATA_DIR.mkdir(exist_ok=True)
        user_file(st.session_state.email).write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def toggle_done(key, item_id):
    """Checkbox callback: runs before the page redraws, so a tick never renders a card twice."""
    value = bool(st.session_state.get(key, False))
    for item in st.session_state.deadlines:
        if item["id"] == item_id:
            item["done"] = value
    for plan in st.session_state.study_plans.values():
        for day in plan["days"]:
            if day["id"] == item_id:
                day["done"] = value


# ---------------------------------------------------------------- UI helpers

AVATARS = {"assistant": "✈️", "user": "🎓"}


def render_message(message):
    with st.chat_message(message["role"], avatar=AVATARS.get(message["role"])):
        if message["kind"] == "image":
            st.image(message["content"])
        else:
            st.write(message["content"])


def add_message(role, kind, content):
    st.session_state.messages.append({"role": role, "kind": kind, "content": content})


def render_hero(tagline, progress=None):
    """Navy banner. The takeoff emoji moves along the runway as the next deadline gets closer."""
    pct = min(max(progress if progress is not None else 0.0, 0.0), 0.94) * 100
    st.markdown(
        "<div class='rw-hero'><div class='rw-display'>✈️ Runway</div>"
        f"<div class='rw-tag'>{escape(tagline)}</div>"
        f"<div class='rw-strip'><span class='rw-plane' style='left:{pct:.0f}%'>🛫</span></div></div>",
        unsafe_allow_html=True,
    )


def render_card(item, today):
    due = date.fromisoformat(item["date"])
    bucket, num, unit = urgency((due - today).days)
    color = COLORS[bucket]
    when = fmt_date(due) + (f", {item['time']}" if item["time"] else "")
    sb = start_by(due, item["effort_hours"], today)
    chips = f"<span>📅 {escape(when)}</span><span>⏱️ about {item['effort_hours']:g}h</span>"
    if sb and not item["done"]:
        chips += f"<span>🚦 Start by {escape(fmt_date(sb))}</span>"
    sub = " - ".join(x for x in [item["course"], item["type"]] if x)
    note = f"<div class='rw-note'>💡 {escape(item['notes'])}</div>" if item["notes"] else ""
    st.markdown(
        f"<div class='rw-card{' done' if item['done'] else ''}'>"
        f"<div class='rw-stub' style='background:{color}'><span class='rw-num'>{num}</span>"
        f"<span class='rw-unit'>{unit}</span></div>"
        f"<div class='rw-body'><div class='rw-card-title'>{escape(item['title'])}</div>"
        f"<div class='rw-sub'>{escape(sub)}</div><div class='rw-chips'>{chips}</div>{note}</div></div>",
        unsafe_allow_html=True,
    )


def render_group(heading, group, today):
    if not group:
        return
    st.markdown(
        f"<div class='rw-section'>{heading}<span class='rw-count'>{len(group)}</span></div>",
        unsafe_allow_html=True,
    )
    for item in group:
        check_col, card_col = st.columns([1, 12], vertical_alignment="center")
        with check_col:
            key = f"done_{item['id']}"
            st.checkbox(
                "Done", value=item["done"], key=key, on_change=toggle_done, args=(key, item["id"]),
                label_visibility="collapsed",
            )
        with card_col:
            render_card(item, today)


def render_day(day, plan, today):
    due = date.fromisoformat(day["date"])
    is_today = due == today
    if is_today:
        stub_style = "background:#FCA311;color:#14213D"
    elif due < today and not day["done"]:
        stub_style = "background:#8d99ae"
    else:
        stub_style = "background:#14213D"
    chips = "".join(f"<span>{escape(t)}</span>" for t in day["topics"])
    chips += f"<span>⏱️ {day['hours']:g}h</span>"
    if is_today:
        chips += "<span>👉 Today</span>"
    tip = f"<div class='rw-note'>💡 {escape(day['tip'])}</div>" if day["tip"] else ""
    st.markdown(
        f"<div class='rw-card{' done' if day['done'] else ''}'>"
        f"<div class='rw-stub' style='{stub_style}'><span class='rw-num'>{due.day}</span>"
        f"<span class='rw-unit'>{due.strftime('%b')}</span></div>"
        f"<div class='rw-body'><div class='rw-card-title'>{escape(day['focus'])}</div>"
        f"<div class='rw-sub'>{escape(due.strftime('%A'))}</div><div class='rw-chips'>{chips}</div>{tip}</div></div>",
        unsafe_allow_html=True,
    )


EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# ---------------------------------------------------------------- onboarding

if "onboarded" not in st.session_state:
    render_hero("Photograph your syllabus. Get every deadline, ranked, with a start-by date.")
    st.markdown(
        "<div class='rw-features'>"
        "<div class='rw-feature'><div class='rw-title'>📸 Snap it</div>"
        "<div class='rw-desc'>Photo or typed dates</div></div>"
        "<div class='rw-feature'><div class='rw-title'>🚦 Rank it</div>"
        "<div class='rw-desc'>Countdowns and start-by dates</div></div>"
        "<div class='rw-feature'><div class='rw-title'>📧 Email it</div>"
        "<div class='rw-desc'>Digest plus calendar file</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    with st.form("onboarding_form"):
        name = st.text_input("👤 Your name")
        email = st.text_input("📧 Email address", placeholder="you@example.com", help="Your digest is sent here.")
        submitted = st.form_submit_button("🚀 Start tracking", type="primary", use_container_width=True)
    if submitted:
        if not name.strip() or not email.strip():
            st.warning("Enter both your name and email address.")
        elif not EMAIL_PATTERN.match(email.strip()):
            st.warning("That email address doesn't look right. Check it and try again.")
        else:
            saved = load_state(email.strip())
            st.session_state.name = name.strip()
            st.session_state.email = email.strip()
            st.session_state.counter = 0
            st.session_state.chats = {}
            st.session_state.chat_id = None
            st.session_state.messages = []
            st.session_state.deadlines = []
            st.session_state.study_plans = {}
            st.session_state.plan = ""
            if saved:
                chats = {
                    cid: {**blank_chat(), **c}
                    for cid, c in (saved.get("chats") or {}).items()
                    if isinstance(c, dict)
                }
                ids = [int(saved.get("counter") or 0)]
                for c in chats.values():
                    ids += [i["id"] for i in c["deadlines"]]
                    ids += [d["id"] for p in c["study_plans"].values() for d in p["days"]]
                st.session_state.chats = chats
                st.session_state.counter = max(ids)
                past = sum(1 for c in chats.values() if not chat_is_empty(c))
                if past:
                    st.session_state.flash = f"Welcome back! {past} saved chat{'s' if past != 1 else ''} in your history."
            start_new_chat()
            st.session_state.onboarded = True
            st.rerun()
    st.stop()

# ---------------------------------------------------------------- main screen

today = today_local()
flash = st.session_state.pop("flash", None)
if flash:
    st.toast(flash, icon="👋")

if not st.session_state.messages:
    add_message("assistant", "text", WELCOME_MESSAGE_TEMPLATE.format(name=st.session_state.name))

# Handle new input first, so everything below shows fresh data.
user_input = st.chat_input(
    "📸 Attach photos of your syllabus or timetable, or type your dates",
    accept_file="multiple",
    file_type=["jpg", "jpeg", "png"],
)
pending_text = st.session_state.pop("pending_text", None)

photos, text = [], ""
if pending_text:
    text = pending_text
elif user_input:
    photos = list(user_input.files or [])
    text = user_input.text or ""
    if len(photos) > MAX_PHOTOS:
        st.toast(f"Using the first {MAX_PHOTOS} photos. Send the rest in another message.", icon="📸")
        photos = photos[:MAX_PHOTOS]

if photos or text:
    parts = []
    for photo in photos:
        photo_bytes = photo.getvalue()
        add_message("user", "image", photo_bytes)
        parts.append(types.Part.from_bytes(data=photo_bytes, mime_type=photo.type))
    if text:
        add_message("user", "text", text)
        parts.append(text)
    else:
        parts.append("Extract every deadline from " + ("these images." if len(photos) > 1 else "this image."))

    tracked = [
        {k: i[k] for k in ("title", "course", "type", "date", "time")} for i in pending_items()
    ]
    if tracked:
        parts.append(f"(Deadlines already tracked: {json.dumps(tracked)})")

    with st.spinner("✈️ Reading your dates..."):
        result = ask_gemini(parts)
    added, plan_info = apply_result(result)
    reply = str(result.get("reply") or "Done.")
    if plan_info:
        reply += (
            f"\n\n📚 Saved a {plan_info[1]}-day study plan for {plan_info[0]}. "
            "Open the Study plan tab. It is included when you email your digest."
        )
    add_message("assistant", "text", reply)
    if plan_info:
        st.toast(f"Study plan ready: {plan_info[0]}", icon="📚")
    if added:
        st.toast(f"Added {added} deadline{'s' if added != 1 else ''}", icon="📅")

items = pending_items()
plans = list(st.session_state.study_plans.values())
week_count = sum(1 for i in items if 0 <= (date.fromisoformat(i["date"]) - today).days <= 7)

# Sidebar
with st.sidebar:
    initial = st.session_state.name[:1].upper() or "R"
    st.markdown(
        f"<div class='rw-profile'><div class='rw-avatar'>{escape(initial)}</div>"
        f"<div><div class='rw-side-name'>👋 {escape(st.session_state.name)}</div>"
        f"<div class='rw-side-mail'>{escape(st.session_state.email)}</div></div></div>"
        f"<div class='rw-side-card'>📆 {escape(fmt_date(today))}<br>"
        f"🎯 {len(items)} pending<br>⚡ {week_count} due in 7 days</div>",
        unsafe_allow_html=True,
    )
    if st.button("➕ New chat", use_container_width=True, help="Start fresh. Your current chat stays in History."):
        start_new_chat()
        st.rerun()

    snapshot_current()
    history = sorted(
        ((cid, c) for cid, c in st.session_state.chats.items() if not chat_is_empty(c)),
        key=lambda kv: kv[1]["created"],
        reverse=True,
    )
    if history:
        st.markdown("<div class='rw-side-head'>🕘 History</div>", unsafe_allow_html=True)
        for cid, c in history[:12]:
            is_active = cid == st.session_state.chat_id
            if st.button(("● " if is_active else "") + c["title"], key=f"hist_{cid}", use_container_width=True):
                if not is_active:
                    load_into_working(cid)
                    st.rerun()

    st.markdown("<div class='rw-side-head'>⚙️ Account</div>", unsafe_allow_html=True)
    if st.session_state.get("confirm_clear"):
        st.markdown("<div class='rw-side-card'>Delete all chats and saved data?</div>", unsafe_allow_html=True)
        yes_col, no_col = st.columns(2)
        if yes_col.button("Yes, delete", key="clear_yes", use_container_width=True):
            clear_everything()
            st.session_state.confirm_clear = False
            st.rerun()
        if no_col.button("Cancel", key="clear_no", use_container_width=True):
            st.session_state.confirm_clear = False
            st.rerun()
    elif st.button("🧹 Clear everything", use_container_width=True, help="Deletes all your chats and saved data."):
        st.session_state.confirm_clear = True
        st.rerun()
    if st.button("🚪 Log out", use_container_width=True, help="Everything is saved. Log in with the same email to see your History."):
        save_state()
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

# Hero
if items:
    nearest = items[0]
    days_to_next = (date.fromisoformat(nearest["date"]) - today).days
    render_hero(
        f"Next takeoff: {nearest['title']} {when_phrase(days_to_next)}.",
        progress=1 - min(max(days_to_next, 0), 14) / 14,
    )
else:
    render_hero("Every deadline, ranked by how soon it hurts.")

send_clicked = st.button(
    "📧 Email my digest",
    type="primary",
    disabled=not items and not plans,
    use_container_width=True,
    help="Sends the list and a calendar file to " + st.session_state.email,
)
if send_clicked:
    crunch = find_crunch(items, today)
    html_body, text_body = build_email(st.session_state.name, items, today, crunch, st.session_state.plan, plans)
    attachments = [("runway-deadlines.ics", build_ics(items))] if items else []
    study_ics = build_study_ics(plans, today)
    if study_ics:
        attachments.append(("runway-study-plan.ics", study_ics))
    with st.spinner("📨 Sending..."):
        ok, info = send_email(
            st.session_state.email,
            (f"Your {len(items)} upcoming deadline{'s' if len(items) != 1 else ''}" if items else "Your study plan")
            + (" + study plan" if items and plans else "")
            + " (Runway)",
            text_body,
            html_body,
            attachments,
        )
    if ok:
        st.success(f"Sent to {st.session_state.email}. Check your inbox, and spam if it's not there.")
    else:
        st.error(f"Couldn't send the email: {info}. Check the Gmail address and App Password in your secrets.")

chat_tab, deadlines_tab, study_tab = st.tabs(
    ["💬 Chat", f"📅 Deadlines ({len(items)})", f"📚 Study plan ({len(plans)})" if plans else "📚 Study plan"]
)

with chat_tab:
    for message in st.session_state.messages:
        render_message(message)
    if not st.session_state.deadlines:
        if st.button("✨ No syllabus handy? Try a sample"):
            st.session_state.pending_text = SAMPLE_TEXT
            st.rerun()

with deadlines_tab:
    if not st.session_state.deadlines:
        st.info("Nothing tracked yet. Attach a photo or type your dates in the Chat tab.")
    else:
        overdue_count = sum(1 for i in items if date.fromisoformat(i["date"]) < today)
        hours = sum(i["effort_hours"] for i in items)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("🎯 Pending", len(items))
        m2.metric("⚡ Next 7 days", week_count)
        m3.metric("🔥 Overdue", overdue_count)
        m4.metric("🧠 Work ahead", f"{hours:g}h")

        crunch = find_crunch(items, today)
        if crunch:
            st.markdown(f"<div class='rw-crunch'>🔥 {escape(crunch_text(crunch))}</div>", unsafe_allow_html=True)
        if st.session_state.plan:
            st.markdown(f"<div class='rw-plan'>🧭 {escape(st.session_state.plan)}</div>", unsafe_allow_html=True)

        def days_left(item):
            return (date.fromisoformat(item["date"]) - today).days

        render_group("🔥 Overdue", [i for i in items if days_left(i) < 0], today)
        render_group("⚡ This week", [i for i in items if 0 <= days_left(i) <= 7], today)
        render_group("🌱 Coming up", [i for i in items if days_left(i) > 7], today)
        done_items = sorted(
            (i for i in st.session_state.deadlines if i["done"]), key=lambda i: (i["date"], i["time"] or "99:99")
        )
        render_group("✅ Done", done_items, today)

        st.download_button(
            "📆 Download deadlines (.ics)",
            data=build_ics(items) if items else "",
            file_name="runway-deadlines.ics",
            mime="text/calendar",
            disabled=not items,
            key="ics_deadlines",
        )

with study_tab:
    if not plans:
        st.info(
            "No study plan yet. Upload a photo of your syllabus in the Chat tab and ask, for example: "
            "\"Make a 10-day study plan for Machine Learning, exam on 15 Oct.\""
        )
    for plan in plans:
        total = len(plan["days"])
        finished = sum(1 for d in plan["days"] if d["done"])
        st.markdown(
            f"<div class='rw-section'>📚 {escape(plan['subject'])}<span class='rw-count'>{total} days</span></div>",
            unsafe_allow_html=True,
        )
        if plan["exam_date"]:
            exam_day = date.fromisoformat(plan["exam_date"])
            gap = (exam_day - today).days
            status = f"{gap} days to go" if gap > 1 else "tomorrow" if gap == 1 else "today" if gap == 0 else "passed"
            st.caption(f"🎯 Exam on {fmt_date(exam_day)} ({status})")
        st.progress(finished / total, text=f"{finished} of {total} days done")
        for day in plan["days"]:
            check_col, card_col = st.columns([1, 12], vertical_alignment="center")
            with check_col:
                key = f"sd_{day['id']}"
                st.checkbox(
                    "Done", value=day["done"], key=key, on_change=toggle_done, args=(key, day["id"]),
                    label_visibility="collapsed",
                )
            with card_col:
                render_day(day, plan, today)
    if plans:
        st.download_button(
            "📆 Download study plan (.ics)",
            data=build_study_ics(plans, today),
            file_name="runway-study-plan.ics",
            mime="text/calendar",
            key="ics_plans",
        )

save_state()