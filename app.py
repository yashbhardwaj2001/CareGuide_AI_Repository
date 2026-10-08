import os, re, json
from pathlib import Path
import streamlit as st

try:
    from google import genai
    from google.genai import types
except Exception:
    genai = None
    types = None

APP_TITLE = "CareGuide AI — Symptom Triage & Health FAQ"
DISCLAIMER = ("CareGuide AI is an educational triage assistant, not a doctor. It does not diagnose, "
              "prescribe medicines, or replace professional medical care. If you may have a medical emergency, "
              "contact your local emergency service now.")

EMERGENCY_PATTERNS = {
    "severe breathing difficulty": [r"can't breathe", r"cannot breathe", r"can't catch my breath", r"gasping", r"choking", r"not able to speak", r"severe shortness of breath"],
    "possible heart emergency": [r"severe chest pain", r"crushing chest pain", r"pressure in (my )?chest", r"tightness in (my )?chest", r"chest pain.*sweat", r"chest pain.*shortness of breath"],
    "possible stroke": [r"face droop", r"face dropping", r"can't lift.*arm", r"cannot lift.*arm", r"slurred speech", r"speech.*sudden", r"sudden weakness.*one side", r"one side.*weakness", r"sudden confusion"],
    "unconsciousness": [r"unconscious", r"not responding", r"won't wake", r"cannot wake", r"passed out and.*not"],
    "severe bleeding": [r"heavy bleeding", r"bleeding.*won't stop", r"blood.*soaking", r"spurting blood", r"bleeding heavily"],
    "seizure emergency": [r"seizure.*more than 5 minutes", r"fit.*more than 5 minutes", r"repeated seizures", r"several seizures", r"first seizure"],
    "severe allergic reaction": [r"throat.*swelling", r"tongue.*swelling", r"lips.*swelling.*breath", r"anaphylaxis"],
    "poisoning/overdose": [r"overdose", r"poisoned", r"swallowed.*poison", r"took too many", r"toxic ingestion"],
    "major injury": [r"serious head injury", r"major accident", r"fall from height", r"severe burn", r"major trauma"],
    "self-harm emergency": [r"want to kill myself", r"suicide attempt", r"i tried to kill myself", r"overdosed on purpose", r"hurt myself intentionally"],
}

URGENT_PATTERNS = [
    r"coughing up blood", r"shortness of breath", r"difficulty breathing", r"severe abdominal pain",
    r"persistent vomiting", r"dehydrated", r"high fever.*confusion", r"new severe headache", r"sudden vision loss",
    r"black stool", r"blood in stool", r"blood in vomit", r"severe allergic", r"pregnant.*bleeding", r"pregnant.*severe pain"
]

FAQ = {
    "What should I do if I have chest pain?": "Chest pain can have many causes. If it is severe, persistent, pressure-like, or comes with sweating, faintness, or breathing difficulty, seek emergency care now. Otherwise, arrange prompt medical assessment rather than self-diagnosing.",
    "When is a headache an emergency?": "A sudden, unusually severe headache, especially with weakness, confusion, fainting, seizures, vision changes, or trouble speaking, needs urgent medical assessment. A new or persistent headache should also be discussed with a clinician.",
    "What if I have trouble breathing?": "Severe difficulty breathing, gasping, choking, inability to speak normally, blue/grey lips or skin, or sudden confusion is an emergency. Seek emergency care immediately.",
    "Should I see a doctor for a fever?": "A fever can occur with many illnesses. Seek urgent care if it is accompanied by severe breathing problems, confusion, a seizure, severe dehydration, or a rapidly worsening condition. Persistent or concerning fever should be assessed by a clinician.",
    "Can this bot diagnose me?": "No. CareGuide AI does not diagnose conditions. It only helps identify urgency and suggests an appropriate next step, with a clear recommendation to seek professional care when needed.",
    "Can I rely on the bot instead of a doctor?": "No. The bot is a support tool, not a substitute for a doctor, nurse, pharmacist, or emergency service. When symptoms are severe, new, worsening, or worrying, seek professional care.",
    "What information should I provide?": "Useful details include the main symptom, when it started, whether it is getting better or worse, severity, age group, relevant medical conditions, pregnancy status when relevant, and important associated symptoms.",
}


def normalize(text):
    return re.sub(r"\s+", " ", text.lower().strip())


def triage(text):
    t = normalize(text)
    hits = []
    for label, patterns in EMERGENCY_PATTERNS.items():
        for p in patterns:
            if re.search(p, t):
                hits.append(label)
                break
    if hits:
        return {
            "level": "EMERGENCY",
            "label": "Emergency warning",
            "reason": "Your message contains a symptom or situation that can require immediate medical attention.",
            "action": "Call your local emergency service or go to the nearest emergency department now. Do not wait for this chatbot to assess you further.",
            "hits": hits,
        }
    if any(re.search(p, t) for p in URGENT_PATTERNS):
        return {
            "level": "URGENT",
            "label": "Prompt medical assessment",
            "reason": "Your message includes a symptom that can sometimes need timely clinical assessment.",
            "action": "Contact a doctor, urgent-care service, or local health helpline promptly. If symptoms become severe or rapidly worsen, seek emergency care.",
            "hits": [],
        }
    return {
        "level": "ROUTINE",
        "label": "General guidance",
        "reason": "No clear emergency trigger was detected from the information provided.",
        "action": "If symptoms persist, worsen, recur, or concern you, arrange a medical assessment. The absence of an emergency trigger does not mean the condition is safe.",
        "hits": [],
    }


def gemini_reply(user_text, history):
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key or genai is None:
        return None
    try:
        client = genai.Client(api_key=key)
        system = f"""You are CareGuide AI, a healthcare symptom-triage FAQ assistant. {DISCLAIMER}
Rules: never diagnose; never claim certainty; never prescribe or recommend specific prescription drugs; do not tell a user that a symptom is harmless; prioritize emergency escalation when red flags are present; ask concise follow-up questions only when they could change urgency; use plain English; if emergency red flags appear, tell the user to contact local emergency services immediately and stop. You may provide general educational information and explain why a professional assessment is appropriate. Do not invent medical facts. If uncertain, recommend professional care.
"""
        contents = []
        for role, msg in history[-8:]:
            contents.append(types.Content(role=role, parts=[types.Part(text=msg)]))
        contents.append(types.Content(role="user", parts=[types.Part(text=user_text)]))
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0.2, max_output_tokens=500),
        )
        return response.text if response and response.text else None
    except Exception as e:
        return None


def safe_response(user_text, history):
    result = triage(user_text)
    if result["level"] == "EMERGENCY":
        return (f"🚨 **{result['label']}**\n\n{result['reason']}\n\n**What to do now:** {result['action']}\n\n{DISCLAIMER}")
    ai = gemini_reply(user_text, history)
    if ai:
        # Emergency rules always override model output.
        return f"{ai}\n\n---\n⚠️ {DISCLAIMER}"
    return (f"**{result['label']}**\n\n{result['reason']}\n\n**Suggested next step:** {result['action']}\n\n"
            "I can also help you structure the symptoms: what is the main symptom, when did it start, and is it getting better or worse?\n\n"
            f"⚠️ {DISCLAIMER}")


st.set_page_config(page_title=APP_TITLE, page_icon="🩺", layout="wide")

st.markdown("""
<style>
:root { --blue:#2563eb; --navy:#0f172a; --bg:#f5f9ff; --card:#ffffff; --muted:#64748b; --danger:#b91c1c; --warn:#b45309; --green:#047857; }
.stApp { background: var(--bg); }
.block-container { max-width: 1180px; padding-top: 1.5rem; }
.hero { background: linear-gradient(135deg,#0f2b5b,#2563eb); color:white; border-radius:24px; padding:28px 32px; margin-bottom:20px; box-shadow:0 12px 30px rgba(37,99,235,.16); }
.hero h1 { margin:0 0 8px 0; font-size:2.2rem; }
.hero p { margin:0; opacity:.92; font-size:1.03rem; }
.badge { display:inline-block; background:#dbeafe; color:#1d4ed8; padding:5px 10px; border-radius:999px; font-weight:700; font-size:.78rem; margin-bottom:8px; }
.card { background:white; border:1px solid #dbeafe; border-radius:18px; padding:18px; margin:10px 0; }
.small { color:#64748b; font-size:.9rem; }
.warning { background:#fff7ed; border-left:5px solid #f59e0b; padding:14px 16px; border-radius:12px; }
.emergency { background:#fef2f2; border-left:5px solid #dc2626; padding:16px; border-radius:12px; }
.safe { background:#ecfdf5; border-left:5px solid #059669; padding:14px 16px; border-radius:12px; }
</style>
""", unsafe_allow_html=True)

st.markdown(f"<div class='hero'><div class='badge'>AI-ASSISTED HEALTHCARE TRIAGE</div><h1>🩺 CareGuide AI</h1><p>Describe what you are experiencing. The assistant focuses on urgency, safe next steps, and escalation — not diagnosis.</p></div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("Safety first")
    st.markdown(f"<div class='warning'>⚠️ {DISCLAIMER}</div>", unsafe_allow_html=True)
    st.divider()
    st.caption("AI mode")
    if os.getenv("GEMINI_API_KEY"):
        st.success("Gemini API configured")
    else:
        st.info("Demo-safe mode: no API key is required. Add GEMINI_API_KEY to enable Gemini conversational refinement.")
    st.caption("This app is designed for academic demonstration, not clinical deployment.")

chat_tab, faq_tab, defense_tab = st.tabs(["💬 Symptom Triage", "📚 FAQ", "🎓 Project Defense"])

if "messages" not in st.session_state:
    st.session_state.messages = []

with chat_tab:
    st.markdown("### Tell me what you are experiencing")
    st.markdown("<div class='small'>Example: “I have had a headache since yesterday and feel slightly nauseous.”</div>", unsafe_allow_html=True)
    for role, msg in st.session_state.messages:
        with st.chat_message("user" if role == "user" else "assistant"):
            st.markdown(msg)
    prompt = st.chat_input("Describe your symptoms or ask a health FAQ…")
    if prompt:
        st.session_state.messages.append(("user", prompt))
        reply = safe_response(prompt, st.session_state.messages[:-1])
        st.session_state.messages.append(("assistant", reply))
        st.rerun()
    if st.button("Start new assessment", type="secondary"):
        st.session_state.messages = []
        st.rerun()

with faq_tab:
    st.markdown("### Frequently asked health questions")
    for q, a in FAQ.items():
        with st.expander(q):
            st.write(a)
            st.caption("This is general information, not a diagnosis or individualized medical advice.")

with defense_tab:
    st.markdown("### End-Term Project Defense")
    st.caption("The Question Bank from the supplied project workbook is built into this section. These answers are also included in the project document.")
    questions = json.loads(Path(__file__).with_name("question_bank.json").read_text(encoding="utf-8"))
    for section, items in questions.items():
        st.markdown(f"#### {section}")
        for q in items:
            with st.expander(q["question"]):
                st.markdown(q["answer"])

st.divider()
st.caption("CareGuide AI • Academic prototype • No diagnosis • No prescription • Escalate when uncertain")
