from __future__ import annotations

import io
import json
import os
import re
from typing import Any, Dict, List, TypedDict
from urllib.parse import urlparse
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import streamlit as st

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

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
    discovery_note: str
    agent_insights: List[Dict[str, str]]


MOCK_JOBS = [
    {"title": "AI Product Analyst", "company": "Northstar Labs", "location": "Bengaluru, India", "type": "Full-time", "salary": "₹12–18 LPA", "url": "https://example.com/northstar-ai-product-analyst", "description": "Analyze product behavior, run experiments, and turn customer signals into AI roadmap decisions.", "skills": ["Python", "SQL", "Product Analytics", "A/B Testing", "LLMs"]},
    {"title": "Machine Learning Engineer", "company": "Orbit Systems", "location": "Remote, India", "type": "Full-time", "salary": "₹18–28 LPA", "url": "https://example.com/orbit-ml-engineer", "description": "Build production ML pipelines and deploy retrieval-augmented AI experiences for enterprise teams.", "skills": ["Python", "PyTorch", "Docker", "MLOps", "RAG"]},
    {"title": "Data Analyst — Growth", "company": "BrightCart", "location": "Hyderabad, India", "type": "Full-time", "salary": "₹8–14 LPA", "url": "https://example.com/brightcart-growth-analyst", "description": "Own growth dashboards, cohort analysis, and recommendations that improve activation and retention.", "skills": ["SQL", "Python", "Tableau", "Statistics", "Communication"]},
    {"title": "Associate Product Manager", "company": "GreenGrid", "location": "Mumbai, India", "type": "Hybrid", "salary": "₹10–16 LPA", "url": "https://example.com/greengrid-apm", "description": "Work with engineering and design to ship climate intelligence tools used by real businesses.", "skills": ["Product Strategy", "User Research", "Analytics", "Agile", "Communication"]},
    {"title": "Business Analyst", "company": "FinPeak", "location": "Bengaluru, India", "type": "Full-time", "salary": "₹7–12 LPA", "url": "https://example.com/finpeak-business-analyst", "description": "Partner with business teams to define requirements, analyze operational data, and improve customer journeys.", "skills": ["SQL", "Excel", "Requirements Gathering", "Process Mapping", "Stakeholder Management"]},
    {"title": "Business Intelligence Analyst", "company": "PulseWorks", "location": "Remote, India", "type": "Full-time", "salary": "₹9–15 LPA", "url": "https://example.com/pulseworks-bi-analyst", "description": "Create decision-ready dashboards and turn performance data into practical business recommendations.", "skills": ["SQL", "Power BI", "Excel", "Data Visualization", "Communication"]},
    {"title": "Business Analyst", "company": "Nexora Consulting", "location": "Hyderabad, India", "type": "Full-time", "salary": "₹7–11 LPA", "url": "https://example.com/nexora-business-analyst", "description": "Gather requirements, map business processes, and partner with delivery teams to improve client operations.", "skills": ["SQL", "Excel", "Requirements Gathering", "Process Mapping", "Stakeholder Management"]},
    {"title": "Data Analyst", "company": "InsightLoop", "location": "Hyderabad, India", "type": "Hybrid", "salary": "₹8–13 LPA", "url": "https://example.com/insightloop-data-analyst", "description": "Build dashboards, analyze operational data, and communicate actionable insights to business stakeholders.", "skills": ["SQL", "Python", "Power BI", "Excel", "Statistics"]},
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


def openai_text(instructions: str, prompt: str) -> str | None:
    """Optional reasoning layer. Deterministic fallbacks keep the demo reliable."""
    if not os.getenv("OPENAI_API_KEY"):
        return None
    try:
        from openai import OpenAI
        response = OpenAI().responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            instructions=instructions,
            input=prompt,
        )
        return response.output_text.strip()
    except Exception:
        return None


def openai_json(instructions: str, prompt: str) -> Dict[str, Any] | None:
    text = openai_text(instructions, f"{prompt}\nReturn valid JSON only, with no markdown.")
    if not text:
        return None
    try:
        return json.loads(text.removeprefix("```json").removesuffix("```").strip())
    except json.JSONDecodeError:
        return None


def extract_json_object(text: str) -> Dict[str, Any] | None:
    """Recover the first JSON object even if a model wraps it in prose or fences."""
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            continue
    return None


def openai_web_jobs(roles: List[str], cities: List[str]) -> List[Dict[str, Any]]:
    """Fetch current, query-matched jobs through OpenAI web search; never invent listings."""
    if not os.getenv("OPENAI_API_KEY"):
        return []
    try:
        from openai import OpenAI
        client = OpenAI()
        jobs, seen_urls = [], set()
        for role in roles[:3]:
            for city in cities[:3]:
                prompt = f"""Find current public job listings for the exact role '{role}' in '{city}', India.
Only return a listing when the page explicitly states both the role and location. Do not invent companies, links, salaries, or job details.
Return JSON only in this shape: {{"jobs":[{{"title":"","company":"","location":"","url":"","description":"","skills":[]}}]}}.
Use direct listing/careers URLs where possible."""
                response = client.responses.create(
                    model=os.getenv("OPENAI_SEARCH_MODEL", os.getenv("OPENAI_MODEL", "gpt-5-mini")),
                    tools=[{"type": "web_search"}],
                    input=prompt,
                )
                payload = extract_json_object(response.output_text) or {}
                for item in payload.get("jobs", []):
                    title = str(item.get("title", "")).strip()
                    company = str(item.get("company", "")).strip()
                    location = str(item.get("location", "")).strip()
                    url = str(item.get("url", "")).strip()
                    description = str(item.get("description", "")).strip()
                    listing_text = f"{title} {location} {description}"
                    if not url.startswith("http") or url in seen_urls:
                        continue
                    if role.lower() not in listing_text.lower() or city.lower() not in listing_text.lower():
                        continue
                    seen_urls.add(url)
                    jobs.append({"title": title, "company": company or company_from_url(url), "location": location, "type": "Live listing", "salary": "See source", "url": url, "description": description or "Open the source listing for details.", "skills": item.get("skills", []), "source": "Live public result via OpenAI web search"})
        return jobs
    except Exception:
        return []


def role_matches_title(role: str, title: str) -> bool:
    """Require every meaningful target-role word in the returned job title."""
    required = tokens(role) - {"and", "the", "of"}
    title_words = tokens(title)
    if required and required.issubset(title_words):
        return True
    # Public listings commonly write UX as UI/UX, UI UX, or User Experience.
    if "ux" in required and ("designer" in required or "design" in required):
        return "ux" in title_words and bool({"designer", "design"} & title_words)
    if "ui" in required and "ux" in required:
        return {"ui", "ux"}.issubset(title_words)
    return False


def city_matches_job(city: str, location: str, is_remote: bool = False) -> bool:
    if city.lower() == "remote":
        return is_remote or "remote" in location.lower()
    return city.lower() in location.lower()


def jsearch_jobs(roles: List[str], cities: List[str]) -> List[Dict[str, Any]]:
    """Retrieve structured jobs from JSearch/RapidAPI and validate role + city locally."""
    api_key = os.getenv("RAPIDAPI_KEY")
    if not api_key:
        return []
    jobs, seen_urls = [], set()
    try:
        for role in roles[:3]:
            for city in cities[:3]:
                params = urlencode({"query": f"{role} in {city}, India", "country": "in", "language": "en"})
                request = Request(
                    f"https://jsearch.p.rapidapi.com/search-v2?{params}",
                    headers={"x-rapidapi-key": api_key, "x-rapidapi-host": "jsearch.p.rapidapi.com"},
                )
                with urlopen(request, timeout=20) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                data = payload.get("data", {})
                records = data.get("jobs", []) if isinstance(data, dict) else data
                for item in records:
                    title = str(item.get("job_title", "")).strip()
                    company = str(item.get("employer_name", "")).strip()
                    location = ", ".join(part for part in [item.get("job_city") or item.get("job_location"), item.get("job_state"), item.get("job_country")] if part)
                    is_remote = bool(item.get("job_is_remote"))
                    url = str(item.get("job_apply_link", "")).strip()
                    if not url.startswith("http") or url in seen_urls:
                        continue
                    if not role_matches_title(role, title) or not city_matches_job(city, location, is_remote):
                        continue
                    seen_urls.add(url)
                    skills = item.get("job_required_skills") or []
                    if isinstance(skills, str):
                        skills = [skills]
                    salary_min, salary_max = item.get("job_min_salary"), item.get("job_max_salary")
                    salary = f"{salary_min}–{salary_max}" if salary_min and salary_max else "See source"
                    jobs.append({"title": title, "company": company or "Company listed on source", "location": "Remote" if is_remote else location, "type": item.get("job_employment_type") or "See source", "salary": salary, "url": url, "description": str(item.get("job_description", ""))[:900] or "Open the source listing for details.", "skills": skills[:8], "source": "Live structured result via JSearch"})
        return jobs
    except Exception:
        return []


def location_matches(text: str, cities: List[str]) -> bool:
    return not cities or any(city.lower() in text.lower() for city in cities)


def fallback_jobs(target_roles: List[str], cities: List[str]) -> List[Dict[str, Any]]:
    """Return demos that honour both target roles and preferred locations."""
    role_phrases = [role.lower().strip() for role in target_roles if role.strip()]
    relevant = [
        job for job in MOCK_JOBS
        if any(phrase in (job["title"] + " " + job["description"]).lower() for phrase in role_phrases)
        and location_matches(job["location"], cities)
    ]
    if relevant:
        return [{**job, "source": "CareerPilot scenario data (illustrative)"} for job in relevant]
    role = target_roles[0] if target_roles else "Business Analyst"
    city = cities[0] if cities else "Remote"
    return [{
        "title": role,
        "company": "DemoWorks",
        "location": f"{city}, India" if city.lower() != "remote" else "Remote, India",
        "type": "Full-time",
        "salary": "Competitive",
        "url": "https://example.com/careerpilot-demo-role",
        "description": f"Demo listing for a {role} in {city}. Use live discovery with Tavily for current public opportunities.",
        "skills": ["Communication", "Problem Solving", "Analytics", "Stakeholder Management"],
        "source": "CareerPilot scenario data (illustrative)",
    }]


def company_from_search_title(title: str, roles: List[str]) -> str:
    """Best-effort company extraction from common public job-listing title formats."""
    lowered = title.lower()
    for separator in (" at ", " | ", " - "):
        if separator in lowered:
            left, right = title.split(separator, 1)
            return right.strip() if any(role.lower() in left.lower() for role in roles) else left.strip()
    return "Company listed on source"


def company_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    first = host.split(".")[0]
    if first and first not in {"jobs", "careers", "boards", "apply", "myworkdayjobs", "linkedin", "indeed"}:
        return first.replace("-", " ").title()
    return "Company listed on source"


def career_profile_agent(state: CareerState) -> CareerState:
    text = state.get("resume_text", "")
    found = tokens(text)
    known = ["python", "sql", "java", "javascript", "react", "pytorch", "tableau", "docker", "aws", "llms", "rag", "statistics", "analytics", "product"]
    skills = [s.upper() if s in {"sql", "aws"} else s.title() for s in known if s in found]
    if not skills:
        skills = ["Python", "SQL", "Analytics"]
    profile = {"headline": "Emerging AI and analytics professional", "skills": skills, "experience_level": state["preferences"].get("experience", "Entry level"), "strengths": ["Structured problem solving", "Learning agility", "Cross-functional communication"]}
    ai = openai_json("You are a careful career coach. Never invent experience. Build a concise candidate profile from the provided resume text and preferences.", f"Resume: {text[:6000]}\nPreferences: {state['preferences']}\nFallback profile: {profile}\nReturn keys: headline (string), skills (max 8 strings), strengths (max 3 strings).")
    if ai:
        profile.update({key: ai[key] for key in ("headline", "skills", "strengths") if key in ai and ai[key]})
    insight = "Profile inferred from resume and preferences" + (" with OpenAI reasoning." if ai else " using the reliable local fallback.")
    return {"profile": profile, "agent_insights": state.get("agent_insights", []) + [{"agent": "Career Profile Agent", "conclusion": profile["headline"], "evidence": ", ".join(profile["skills"])}], "logs": state.get("logs", []) + [insight]}


def fallback_role_fit(role: str, profile: Dict[str, Any]) -> str:
    """Give honest, role-aware guidance when live model reasoning is unavailable."""
    role_name = role.lower()
    skills = {skill.lower() for skill in profile.get("skills", [])}
    if any(word in role_name for word in ("ux", "ui", "designer", "design")):
        has_design_evidence = skills & {"figma", "user research", "wireframing", "prototyping", "visual design"}
        if has_design_evidence:
            return "You have some design evidence. Strengthen this path with two end-to-end case studies that show research, decisions, and outcomes."
        return "This is a transition target, not a proven match yet. Build a Figma portfolio, show user-research thinking, and document 2–3 UX case studies."
    if "business analyst" in role_name:
        return "Good foundation for this path: your analytical skills can transfer. Add requirements-gathering and stakeholder-management examples."
    if "data analyst" in role_name or "analytics" in role_name:
        return "This is a credible near-term target: your current analytical foundation is relevant. Prioritise dashboard projects and quantified insights."
    if "product" in role_name:
        return "This is a possible adjacent path. Strengthen it with user problem framing, prioritisation examples, and one product case study."
    if "machine learning" in role_name or "ai " in role_name:
        return "This role needs demonstrated model-building or AI project evidence. Prioritise one deployed project and clear technical documentation."
    return "Treat this as an exploratory target. Compare its required skills with your resume, then build evidence for the largest gaps."


def role_recommendation_agent(state: CareerState) -> CareerState:
    prefs = state["preferences"]
    roles = prefs.get("roles", []) or ["AI Product Analyst", "Data Analyst"]
    recs = [{"role": role, "why": fallback_role_fit(role, state["profile"])} for role in roles[:4]]
    ai = openai_json("You are a precise career advisor. Assess role fit honestly. If the candidate lacks role-specific evidence, say so and name the most useful next proof. Never claim generic technical skills prove fit for a different discipline. Keep each assessment under 32 words.", f"Candidate profile: {state['profile']}\nRequested roles: {roles}\nReturn {{\"recommendations\": [{{\"role\": string, \"why\": string}}]}} and preserve only requested roles.")
    if ai and isinstance(ai.get("recommendations"), list):
        recs = [item for item in ai["recommendations"] if item.get("role") in roles and item.get("why")][:4] or recs
    return {"recommendations": recs, "agent_insights": state.get("agent_insights", []) + [{"agent": "Role Recommendation Agent", "conclusion": ", ".join(item["role"] for item in recs), "evidence": "; ".join(item["why"] for item in recs)}], "logs": state.get("logs", []) + ["Role Recommendation Agent prioritized target roles."]}


def job_discovery_agent(state: CareerState) -> CareerState:
    roles = state["preferences"].get("roles", []) or ["Data Analyst"]
    cities = state["preferences"].get("cities", [])
    jobs = fallback_jobs(roles, cities)
    discovery_note = "Scenario mode: illustrative opportunities are tailored to your selected role and city."
    live_mode = False
    structured_jobs = jsearch_jobs(roles, cities)
    if structured_jobs:
        jobs = structured_jobs
        live_mode = True
        discovery_note = f"Live JSearch found {len(jobs)} exact role- and location-matched listings."
    openai_jobs = openai_web_jobs(roles, cities) if not live_mode else []
    if openai_jobs:
        jobs = openai_jobs
        live_mode = True
        discovery_note = f"Live OpenAI web search found {len(jobs)} exact role- and location-matched public listings."
    api_key = os.getenv("TAVILY_API_KEY")
    if api_key and not live_mode:
        try:
            from tavily import TavilyClient
            live_jobs = []
            seen_urls = set()
            for role in roles[:3]:
                for city in (cities or ["India"])[:3]:
                    search_query = f'"{role}" "{city}" India job opening apply company careers'
                    result = TavilyClient(api_key=api_key).search(query=search_query, search_depth="advanced", max_results=5)
                    for item in result.get("results", []):
                        title = item.get("title", "Open role")
                        description = item.get("content", "")
                        url = item.get("url", "")
                        listing_text = f"{title} {description}"
                        looks_like_listing = any(word in listing_text.lower() for word in ("job", "career", "apply", "opening", "vacancy"))
                        if url in seen_urls or role.lower() not in listing_text.lower() or not location_matches(listing_text, [city]) or not looks_like_listing:
                            continue
                        seen_urls.add(url)
                        company = company_from_search_title(title, [role])
                        if company == "Company listed on source":
                            company = company_from_url(url)
                        live_jobs.append({"title": title, "company": company, "location": f"{city}, India" if city.lower() != "remote" else "Remote", "type": "See source", "salary": "Not listed", "url": url, "description": description, "skills": [], "source": "Live public result via Tavily"})
            if live_jobs:
                jobs = live_jobs
                live_mode = True
                discovery_note = f"Live mode: {len(live_jobs)} role- and location-matched public listings found."
            else:
                discovery_note = "No exact public listing was found for this role and city right now, so CareerPilot switched to a clearly labeled scenario." 
        except Exception:
            discovery_note = "Live search was unavailable, so CareerPilot switched to a clearly labeled scenario."
    return {"jobs": jobs, "demo_mode": not live_mode, "discovery_note": discovery_note, "agent_insights": state.get("agent_insights", []) + [{"agent": "Job Discovery Agent", "conclusion": discovery_note, "evidence": ", ".join(f"{job['title']} — {job['location']}" for job in jobs[:3])}], "logs": state.get("logs", []) + [f"Job Discovery Agent found {len(jobs)} source-agnostic listings."]}


def job_match_agent(state: CareerState) -> CareerState:
    profile_skills = {x.lower() for x in state["profile"]["skills"]}
    matches = []
    for job in state.get("jobs", []):
        job_skills = {x.lower() for x in job.get("skills", [])}
        overlap = profile_skills & job_skills
        score = min(98, 55 + len(overlap) * 9)
        matches.append({**job, "score": score, "overlap": sorted(overlap), "missing": sorted(job_skills - profile_skills)[:4]})
    ranked = sorted(matches, key=lambda x: x["score"], reverse=True)
    top = ranked[0] if ranked else {}
    return {"matches": ranked, "agent_insights": state.get("agent_insights", []) + [{"agent": "Job Match Agent", "conclusion": f"Top match: {top.get('title', 'No role')} at {top.get('company', '—')} ({top.get('score', 0)}%)", "evidence": f"Matched skills: {', '.join(top.get('overlap', [])) or 'No explicit skill overlap found'}"}], "logs": state.get("logs", []) + ["Job Match Agent scored opportunities against the profile."]}


def resume_tailoring_agent(state: CareerState) -> CareerState:
    top = state.get("matches", [{}])[0]
    skills = ", ".join(state["profile"]["skills"])
    tailored = f"TARGET: {top.get('title', 'AI / Data role')} at {top.get('company', 'your target company')}\n\nSUMMARY\n{state['profile']['headline']} with hands-on experience in {skills}. Brings structured problem solving and a product-minded approach to measurable outcomes.\n\nTAILORING NOTES\n• Lead with evidence of {', '.join(top.get('overlap', []) or ['analytics'])}.\n• Add one quantified project outcome.\n• Address the priority gap: {', '.join(top.get('missing', []) or ['domain context'])}."
    ai = openai_text("You are a resume coach. Write only a concise tailored professional summary plus three tailoring notes. Do not invent employers, degrees, metrics, or skills.", f"Candidate profile: {state['profile']}\nTarget job: {top}\nCurrent draft: {tailored}")
    if ai:
        tailored = ai
    return {"tailored_resume": tailored, "agent_insights": state.get("agent_insights", []) + [{"agent": "Resume Tailoring Agent", "conclusion": f"Tailored resume prepared for {top.get('title', 'target role')}", "evidence": f"Emphasises: {', '.join(top.get('overlap', []) or state['profile']['skills'][:3])}"}], "logs": state.get("logs", []) + ["Resume Tailoring Agent drafted a target-specific version."]}


def skill_gap_agent(state: CareerState) -> CareerState:
    top = state.get("matches", [{}])[0]
    gaps = [{"skill": skill, "priority": "High" if i < 2 else "Medium", "action": f"Build a small portfolio project demonstrating {skill}."} for i, skill in enumerate(top.get("missing", [])[:4])]
    gaps = gaps or [{"skill": "Quantified impact", "priority": "Medium", "action": "Add metrics to two resume bullets."}]
    return {"skill_gaps": gaps, "agent_insights": state.get("agent_insights", []) + [{"agent": "Skill Gap Agent", "conclusion": f"Priority gap: {gaps[0]['skill']}", "evidence": gaps[0]['action']}], "logs": state.get("logs", []) + ["Skill Gap Agent suggested focused next steps."]}


def interview_prep_agent(state: CareerState) -> CareerState:
    top = state.get("matches", [{}])[0]
    prep = {"role": top.get("title", "Target role"), "questions": [f"Walk me through a project relevant to {top.get('title', 'this role')}.", "How did you measure the impact of your work?", f"How would you ramp up on {', '.join(top.get('missing', [])[:2]) or 'our domain'}?"], "pitch": "I combine analytical thinking with practical AI and product execution, and I enjoy turning ambiguous problems into measurable outcomes."}
    return {"interview_prep": prep, "agent_insights": state.get("agent_insights", []) + [{"agent": "Interview Prep Agent", "conclusion": f"Prepared a pitch and {len(prep['questions'])} practice questions", "evidence": prep['questions'][0]}], "logs": state.get("logs", []) + ["Interview Prep Agent generated a focused practice set."]}


def application_agent(state: CareerState) -> CareerState:
    top = state.get("matches", [{}])[0]
    application = {"status": "Approval required", "job": top, "message": "A prepared application is ready. Review it and approve before sending.", "auto_apply_supported": False}
    return {"application": application, "agent_insights": state.get("agent_insights", []) + [{"agent": "Application Agent", "conclusion": "Application stops for human approval", "evidence": "No auto-apply occurs; the candidate controls final submission."}], "logs": state.get("logs", []) + ["Application flow stopped at the human approval gate."]}


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
    state: CareerState = {"resume_text": resume_text, "preferences": preferences, "logs": [], "agent_insights": [], "demo_mode": not bool(os.getenv("TAVILY_API_KEY"))}
    graph = build_graph()
    if graph:
        return graph.invoke(state)
    for agent in [career_profile_agent, role_recommendation_agent, job_discovery_agent, job_match_agent, resume_tailoring_agent, skill_gap_agent, interview_prep_agent, application_agent]:
        state.update(agent(state))
    return state


st.set_page_config(page_title="CareerPilot AI", page_icon="✦", layout="wide")
st.markdown("<style> .block-container{max-width:1200px;padding-top:2rem} .hero{padding:2rem;border-radius:22px;background:linear-gradient(135deg,#16213e,#2d5b8e);color:white;margin-bottom:1.4rem} .hero h1{font-size:3rem;margin:0 0 .4rem} .tag{display:inline-block;padding:.3rem .65rem;border-radius:99px;background:#e9f3ff;color:#1d4f91;margin:.15rem;font-size:.85rem} </style>", unsafe_allow_html=True)
st.markdown("<div class='hero'><h1>✦ CareerPilot AI</h1><p>Your personal AI career team — discover better-fit roles, close skill gaps, and prepare with confidence.</p></div>", unsafe_allow_html=True)


def clear_stale_results():
    st.session_state.pop("results", None)


with st.sidebar:
    st.header("Candidate setup")
    uploaded = st.file_uploader("Upload resume", type=["pdf", "docx", "txt"])
    roles = st.multiselect(
        "Target roles",
        ["AI Product Analyst", "Data Analyst", "Machine Learning Engineer", "Product Manager", "Software Engineer"],
        default=[],
        accept_new_options=True,
        key="target_roles_v2",
        on_change=clear_stale_results,
        placeholder="Choose a suggestion or type any role and press Enter",
        help="Only the roles selected here are searched. Type any role and press Enter—for example, UX Designer, Business Analyst, or Cybersecurity Engineer.",
    )
    interests = st.text_input("Interests", "AI, analytics, product building")
    cities = st.multiselect(
        "Preferred cities",
        ["Bengaluru", "Hyderabad", "Mumbai", "Delhi NCR", "Pune", "Chennai", "Remote"],
        default=[],
        accept_new_options=True,
        key="preferred_cities_v2",
        on_change=clear_stale_results,
        placeholder="Choose a suggestion or type any city and press Enter",
    )
    experience = st.selectbox("Experience", ["Student / fresher", "0–2 years", "3–5 years", "5+ years"])
    salary = st.text_input("Salary target (optional)", placeholder="e.g. ₹12–18 LPA")
    run = st.button("Run my career team", type="primary", use_container_width=True)

if run:
    if not roles or not cities:
        st.warning("Add at least one target role and one preferred city before running the career team.")
    else:
        prefs = {"roles": roles, "interests": interests, "cities": cities, "experience": experience, "salary": salary}
        with st.spinner("Your agents are collaborating..."):
            st.session_state["results"] = run_career_manager(parse_resume(uploaded), prefs)

results = st.session_state.get("results")
if not results:
    st.info("Upload a resume, set your preferences, and run the career team to generate your personalized workspace.")
else:
    st.info(f"Showing results for: **{', '.join(results['preferences']['roles'])}** in **{', '.join(results['preferences']['cities'])}**")
    if os.getenv("OPENAI_API_KEY"):
        st.caption("OpenAI reasoning is enabled for profile, role-fit explanations, and resume tailoring.")
    else:
        st.caption("Deterministic mode is active. Add OPENAI_API_KEY to enable personalised reasoning.")
    if results.get("demo_mode"):
        st.warning(results["discovery_note"])
    else:
        st.success(results["discovery_note"])
    profile, recs = results["profile"], results["recommendations"]
    st.subheader("Your career snapshot")
    a, b, c = st.columns(3)
    a.metric("Profile readiness", "Ready")
    b.metric("Roles assessed", len(recs))
    c.metric("Jobs matched", len(results["matches"]))
    st.write(profile["headline"])
    st.markdown("".join(f"<span class='tag'>{s}</span>" for s in profile["skills"]), unsafe_allow_html=True)
    tabs = st.tabs(["Role fit", "Matched jobs", "Resume tailor", "Skill gaps", "Interview prep", "Why these results?", "Apply"])
    with tabs[0]:
        for rec in recs: st.markdown(f"**{rec['role']}**  \n{rec['why']}")
    with tabs[1]:
        for job in results["matches"]:
            with st.container(border=True):
                st.markdown(f"### {job['title']} · {job['company']}")
                st.caption(f"{job['location']} · {job['type']} · {job['salary']} · Match {job['score']}%")
                st.write(job["description"])
                st.write("Skills:", ", ".join(job.get("skills", [])))
                st.caption(job.get("source", "Source unavailable"))
                st.link_button("View source listing", job["url"])
    with tabs[2]: st.text_area("Tailored resume draft", results["tailored_resume"], height=300)
    with tabs[3]:
        for gap in results["skill_gaps"]: st.markdown(f"**{gap['skill']}** · {gap['priority']} priority  \n{gap['action']}")
    with tabs[4]:
        st.markdown(f"**30-second pitch**  \n{results['interview_prep']['pitch']}")
        for i, question in enumerate(results["interview_prep"]["questions"], 1): st.markdown(f"{i}. {question}")
    with tabs[5]:
        st.subheader("Career Manager decision trail")
        st.caption("Each agent adds a conclusion and the evidence it used. This is your explainable personal reference.")
        for insight in results.get("agent_insights", []):
            with st.container(border=True):
                st.markdown(f"**{insight['agent']}**")
                st.write(insight["conclusion"])
                st.caption(f"Evidence: {insight['evidence']}")
    with tabs[6]:
        app = results["application"]
        st.markdown(f"**{app['job'].get('title')} at {app['job'].get('company')}**")
        st.info(app["message"])
        st.checkbox("I reviewed the job and prepared materials", key="approval")
        if st.button("Prepare application package"):
            if st.session_state.get("approval"): st.success("Application package prepared. Auto-apply is intentionally unsupported; you remain in control of submission.")
            else: st.error("Please review and approve the package first.")
    with st.expander("Agent activity log"):
        for log in results["logs"]: st.write("✓", log)

