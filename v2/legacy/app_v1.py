from __future__ import annotations

import io
import os
import re
from typing import Any, Dict, List, TypedDict

import streamlit as st

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - lets the UI run before optional install
    StateGraph = None
    END = "__end__"


class CareerState(TypedDict, total=False):
    resume_text: str
    preferences: Dict[str, Any]
    profile: Dict[str, Any]
    recommendations: List[Dict[str, Any]]
    jobs: List[Dict[str, Any]]
    matches: List[Dict[str, Any]]
    tailored_resume: str
    skill_gaps: List[Dict[str, Any]]
    interview_prep: Dict[str, Any]
    application: Dict[str, Any]
    logs: List[str]
    demo_mode: bool


MOCK_JOBS = [
    {"title": "AI Product Analyst", "company": "Northstar Labs", "location": "Bengaluru, India", "type": "Full-time", "salary": "₹12–18 LPA", "url": "https://example.com/northstar-ai-product-analyst", "description": "Analyze product behavior, run experiments, and turn customer signals into AI roadmap decisions.", "skills": ["Python", "SQL", "Product Analytics", "A/B Testing", "LLMs"]},
    {"title": "Machine Learning Engineer", "company": "Orbit Systems", "location": "Remote, India", "type": "Full-time", "salary": "₹18–28 LPA", "url": "https://example.com/orbit-ml-engineer", "description": "Build production ML pipelines and deploy retrieval-augmented AI experiences for enterprise teams.", "skills": ["Python", "PyTorch", "Docker", "MLOps", "RAG"]},
    {"title": "Data Analyst — Growth", "company": "BrightCart", "location": "Hyderabad, India", "type": "Full-time", "salary": "₹8–14 LPA", "url": "https://example.com/brightcart-growth-analyst", "description": "Own growth dashboards, cohort analysis, and recommendations that improve activation and retention.", "skills": ["SQL", "Python", "Tableau", "Statistics", "Communication"]},
    {"title": "Associate Product Manager", "company": "GreenGrid", "location": "Mumbai, India", "type": "Hybrid", "salary": "₹10–16 LPA", "url": "https://example.com/greengrid-apm", "description": "Work with engineering and design to ship climate intelligence tools used by real businesses.", "skills": ["Product Strategy", "User Research", "Analytics", "Agile", "Communication"]},
]


def parse_resume(uploaded_file) -> str:
    if not uploaded_file:
        return ""
    raw = uploaded_file.getvalue()
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        try:
            from pypdf import PdfReader
            return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(raw)).pages)
        except Exception:
            return "PDF uploaded. Parser unavailable; using filename and preferences in demo mode."
    if name.endswith(".docx"):
        try:
            from docx import Document
            return "\n".join(p.text for p in Document(io.BytesIO(raw)).paragraphs)
        except Exception:
            return "DOCX uploaded. Parser unavailable; using filename and preferences in demo mode."
    return raw.decode("utf-8", errors="ignore")


def tokens(text: str) -> set[str]:
    return {x.lower() for x in re.findall(r"[a-zA-Z][a-zA-Z+#.-]{1,}", text)}


def career_profile_agent(state: CareerState) -> CareerState:
    text = state.get("resume_text", "")
    found = tokens(text)
    known = ["python", "sql", "java", "javascript", "react", "pytorch", "tableau", "docker", "aws", "llms", "rag", "statistics", "analytics", "product"]
    skills = [s.upper() if s in {"sql", "aws"} else s.title() for s in known if s in found]
    if not skills:
        skills = ["Python", "SQL", "Analytics"]
    return {"profile": {"headline": "Emerging AI and analytics professional", "skills": skills, "experience_level": state["preferences"].get("experience", "Entry level"), "strengths": ["Structured problem solving", "Learning agility", "Cross-functional communication"]}, "logs": state.get("logs", []) + ["Career Profile Agent extracted a structured candidate profile."]}


def role_recommendation_agent(state: CareerState) -> CareerState:
    prefs = state["preferences"]
    roles = prefs.get("roles", []) or ["AI Product Analyst", "Data Analyst"]
    recs = [{"role": role, "why": f"Strong overlap with your {', '.join(state['profile']['skills'][:3])} foundation and stated interests."} for role in roles[:4]]
    return {"recommendations": recs, "logs": state.get("logs", []) + ["Role Recommendation Agent prioritized target roles."]}


def job_discovery_agent(state: CareerState) -> CareerState:
    jobs = list(MOCK_JOBS)
    query = os.getenv("TAVILY_API_KEY")
    if query:
        try:
            from tavily import TavilyClient
            result = TavilyClient(api_key=query).search(query=f"jobs {' '.join(state['preferences'].get('roles', []))}", max_results=5)
            jobs = [{"title": item.get("title", "Open role"), "company": "Public source", "location": "See listing", "type": "Unknown", "salary": "Not listed", "url": item.get("url", ""), "description": item.get("content", ""), "skills": []} for item in result.get("results", [])]
        except Exception:
            state["demo_mode"] = True
    return {"jobs": jobs, "demo_mode": state.get("demo_mode", False), "logs": state.get("logs", []) + [f"Job Discovery Agent found {len(jobs)} source-agnostic listings."]}


def job_match_agent(state: CareerState) -> CareerState:
    profile_skills = {x.lower() for x in state["profile"]["skills"]}
    matches = []
    for job in state.get("jobs", []):
        job_skills = {x.lower() for x in job.get("skills", [])}
        overlap = profile_skills & job_skills
        score = min(98, 55 + len(overlap) * 9)
        matches.append({**job, "score": score, "overlap": sorted(overlap), "missing": sorted(job_skills - profile_skills)[:4]})
    return {"matches": sorted(matches, key=lambda x: x["score"], reverse=True), "logs": state.get("logs", []) + ["Job Match Agent scored opportunities against the profile."]}


def resume_tailoring_agent(state: CareerState) -> CareerState:
    top = state.get("matches", [{}])[0]
    skills = ", ".join(state["profile"]["skills"])
    return {"tailored_resume": f"TARGET: {top.get('title', 'AI / Data role')} at {top.get('company', 'your target company')}\n\nSUMMARY\n{state['profile']['headline']} with hands-on experience in {skills}. Brings structured problem solving and a product-minded approach to measurable outcomes.\n\nTAILORING NOTES\n• Lead with evidence of {', '.join(top.get('overlap', []) or ['analytics'])}.\n• Add one quantified project outcome.\n• Address the priority gap: {', '.join(top.get('missing', []) or ['domain context'])}.", "logs": state.get("logs", []) + ["Resume Tailoring Agent drafted a target-specific version."]}


def skill_gap_agent(state: CareerState) -> CareerState:
    top = state.get("matches", [{}])[0]
    gaps = [{"skill": skill, "priority": "High" if i < 2 else "Medium", "action": f"Build a small portfolio project demonstrating {skill}."} for i, skill in enumerate(top.get("missing", [])[:4])]
    return {"skill_gaps": gaps or [{"skill": "Quantified impact", "priority": "Medium", "action": "Add metrics to two resume bullets."}], "logs": state.get("logs", []) + ["Skill Gap Agent suggested focused next steps."]}


def interview_prep_agent(state: CareerState) -> CareerState:
    top = state.get("matches", [{}])[0]
    return {"interview_prep": {"role": top.get("title", "Target role"), "questions": [f"Walk me through a project relevant to {top.get('title', 'this role')}.", "How did you measure the impact of your work?", f"How would you ramp up on {', '.join(top.get('missing', [])[:2]) or 'our domain'}?"], "pitch": "I combine analytical thinking with practical AI and product execution, and I enjoy turning ambiguous problems into measurable outcomes."}, "logs": state.get("logs", []) + ["Interview Prep Agent generated a focused practice set."]}


def application_agent(state: CareerState) -> CareerState:
    top = state.get("matches", [{}])[0]
    return {"application": {"status": "Approval required", "job": top, "message": "A prepared application is ready. Review it and approve before sending.", "auto_apply_supported": False}, "logs": state.get("logs", []) + ["Application flow stopped at the human approval gate."]}


def build_graph():
    if StateGraph is None:
        return None
    graph = StateGraph(CareerState)
    graph.add_node("profile", career_profile_agent)
    graph.add_node("roles", role_recommendation_agent)
    graph.add_node("discover", job_discovery_agent)
    graph.add_node("match", job_match_agent)
    graph.add_node("tailor", resume_tailoring_agent)
    graph.add_node("gaps", skill_gap_agent)
    graph.add_node("interview", interview_prep_agent)
    graph.add_node("application", application_agent)
    graph.set_entry_point("profile")
    graph.add_edge("profile", "roles"); graph.add_edge("roles", "discover"); graph.add_edge("discover", "match"); graph.add_edge("match", "tailor"); graph.add_edge("tailor", "gaps"); graph.add_edge("gaps", "interview"); graph.add_edge("interview", "application"); graph.add_edge("application", END)
    return graph.compile()


def run_career_manager(resume_text: str, preferences: Dict[str, Any]) -> CareerState:
    state: CareerState = {"resume_text": resume_text, "preferences": preferences, "logs": [], "demo_mode": not bool(os.getenv("TAVILY_API_KEY"))}
    graph = build_graph()
    if graph:
        return graph.invoke(state)
    for agent in [career_profile_agent, role_recommendation_agent, job_discovery_agent, job_match_agent, resume_tailoring_agent, skill_gap_agent, interview_prep_agent, application_agent]:
        state.update(agent(state))
    return state


st.set_page_config(page_title="CareerPilot AI", page_icon="✦", layout="wide")
st.markdown("<style> .block-container{max-width:1200px;padding-top:2rem} .hero{padding:2rem;border-radius:22px;background:linear-gradient(135deg,#16213e,#2d5b8e);color:white;margin-bottom:1.4rem} .hero h1{font-size:3rem;margin:0 0 .4rem} .tag{display:inline-block;padding:.3rem .65rem;border-radius:99px;background:#e9f3ff;color:#1d4f91;margin:.15rem;font-size:.85rem} </style>", unsafe_allow_html=True)
st.markdown("<div class='hero'><h1>✦ CareerPilot AI</h1><p>Your personal AI career team — discover better-fit roles, close skill gaps, and prepare with confidence.</p></div>", unsafe_allow_html=True)

with st.sidebar:
    st.header("Candidate setup")
    uploaded = st.file_uploader("Upload resume", type=["pdf", "docx", "txt"])
    roles = st.multiselect("Target roles", ["AI Product Analyst", "Data Analyst", "Machine Learning Engineer", "Product Manager", "Software Engineer"], default=["AI Product Analyst", "Data Analyst"])
    interests = st.text_input("Interests", "AI, analytics, product building")
    cities = st.multiselect("Preferred cities", ["Bengaluru", "Hyderabad", "Mumbai", "Delhi NCR", "Remote"], default=["Bengaluru", "Remote"])
    experience = st.selectbox("Experience", ["Student / fresher", "0–2 years", "3–5 years", "5+ years"])
    salary = st.text_input("Salary target (optional)", placeholder="e.g. ₹12–18 LPA")
    run = st.button("Run my career team", type="primary", use_container_width=True)

if run:
    prefs = {"roles": roles, "interests": interests, "cities": cities, "experience": experience, "salary": salary}
    with st.spinner("Your agents are collaborating..."):
        st.session_state["results"] = run_career_manager(parse_resume(uploaded), prefs)

results = st.session_state.get("results")
if not results:
    st.info("Upload a resume, set your preferences, and run the career team to generate your personalized workspace.")
else:
    if results.get("demo_mode"):
        st.warning("Demo mode is active. Showing reliable mock jobs because TAVILY_API_KEY is not configured or the live search was unavailable.")
    profile, recs = results["profile"], results["recommendations"]
    st.subheader("Your career snapshot")
    a, b, c = st.columns(3)
    a.metric("Profile readiness", "Ready")
    b.metric("Roles prioritized", len(recs))
    c.metric("Jobs matched", len(results["matches"]))
    st.write(profile["headline"])
    st.markdown("".join(f"<span class='tag'>{s}</span>" for s in profile["skills"]), unsafe_allow_html=True)
    tabs = st.tabs(["Recommendations", "Matched jobs", "Resume tailor", "Skill gaps", "Interview prep", "Apply"])
    with tabs[0]:
        for rec in recs: st.markdown(f"**{rec['role']}**  \n{rec['why']}")
    with tabs[1]:
        for job in results["matches"]:
            with st.container(border=True):
                st.markdown(f"### {job['title']} · {job['company']}")
                st.caption(f"{job['location']} · {job['type']} · {job['salary']} · Match {job['score']}%")
                st.write(job["description"])
                st.write("Skills:", ", ".join(job.get("skills", [])))
                st.link_button("View source listing", job["url"])
    with tabs[2]: st.text_area("Tailored resume draft", results["tailored_resume"], height=300)
    with tabs[3]:
        for gap in results["skill_gaps"]: st.markdown(f"**{gap['skill']}** · {gap['priority']} priority  \n{gap['action']}")
    with tabs[4]:
        st.markdown(f"**30-second pitch**  \n{results['interview_prep']['pitch']}")
        for i, question in enumerate(results["interview_prep"]["questions"], 1): st.markdown(f"{i}. {question}")
    with tabs[5]:
        app = results["application"]
        st.markdown(f"**{app['job'].get('title')} at {app['job'].get('company')}**")
        st.info(app["message"])
        st.checkbox("I reviewed the job and prepared materials", key="approval")
        if st.button("Prepare application package"):
            if st.session_state.get("approval"): st.success("Application package prepared. Auto-apply is intentionally unsupported; you remain in control of submission.")
            else: st.error("Please review and approve the package first.")
    with st.expander("Agent activity log"):
        for log in results["logs"]: st.write("✓", log)
