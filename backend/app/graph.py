from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph  # pyright: ignore[reportMissingImports]

from .supabase_repo import SupabaseRepo
from .webhook import send_webhook
from .llm import ollama_llm


AgentType = Literal["resume", "job_prediction"]


class GraphState(TypedDict, total=False):
    session_id: str
    last_user_message: str
    agent_type: AgentType
    user_data: dict[str, Any]
    ai_output: dict[str, Any]
    reply: str
    webhook_sent: bool


def _normalize_skills(skills: str) -> list[str]:
    return [s.strip() for s in skills.split(",") if s.strip()]


def _route_intent(message: str) -> AgentType:
    m = message.lower()
    resume_keywords = ["resume", "cv", "cover letter", "bullet", "summary", "skill gap", "career guidance"]
    job_keywords = ["job", "role", "predict", "opportunities", "openings", "salary", "industry", "position"]
    if any(k in m for k in resume_keywords) and not any(k in m for k in job_keywords):
        return "resume"
    if any(k in m for k in job_keywords) and not any(k in m for k in resume_keywords):
        return "job_prediction"
    # default to resume guidance if ambiguous
    return "resume"


def _ensure_defaults(state: GraphState) -> GraphState:
    state.setdefault("user_data", {})
    state.setdefault("ai_output", {})
    state.setdefault("webhook_sent", False)
    return state


def _missing_resume_fields(user_data: dict[str, Any]) -> list[str]:
    required = ["full_name", "education_level", "skills", "work_experience"]
    missing = [f for f in required if not str(user_data.get(f, "")).strip()]
    return missing


def _missing_job_fields(user_data: dict[str, Any]) -> list[str]:
    required = ["full_name", "skills", "location", "experience_level"]
    missing = [f for f in required if not str(user_data.get(f, "")).strip()]
    return missing


def _next_question(agent_type: AgentType, user_data: dict[str, Any]) -> str | None:
    if agent_type == "resume":
        missing = _missing_resume_fields(user_data)
        if not missing:
            return None
        field = missing[0]
        if field == "full_name":
            return "What is your **full name**?"
        if field == "education_level":
            return "What is your **highest education level** (e.g., High School, Diploma, Bachelor’s, Master’s, PhD)?"
        if field == "skills":
            return "List your **skills** (comma-separated), e.g., `Python, SQL, React`."
        if field == "work_experience":
            return "Describe your **work experience** (years or a short description)."
    else:
        missing = _missing_job_fields(user_data)
        if not missing:
            return None
        field = missing[0]
        if field == "full_name":
            return "What is your **full name**?"
        if field == "skills":
            return "List your **skills** (comma-separated), e.g., `Python, SQL, React`."
        if field == "location":
            return "What is your **location** (city / country)?"
        if field == "experience_level":
            return "What is your **experience level** (entry / mid / senior)?"
    return None


def _apply_user_message_to_expected_field(state: GraphState) -> None:
    """
    We only ask one missing field at a time; so we treat the latest user message
    as the answer to the next missing field for the current agent.
    """
    agent_type = state["agent_type"]
    user_data = state["user_data"]
    answer = (state.get("last_user_message") or "").strip()
    if not answer:
        return

    if agent_type == "resume":
        missing = _missing_resume_fields(user_data)
        if not missing:
            # optional career_goal can still be collected later; do nothing
            return
        field = missing[0]
        user_data[field] = answer
        if field == "skills":
            user_data["skills_list"] = _normalize_skills(answer)
    else:
        missing = _missing_job_fields(user_data)
        if not missing:
            return
        field = missing[0]
        user_data[field] = answer
        if field == "skills":
            user_data["skills_list"] = _normalize_skills(answer)


def start_node(state: GraphState) -> GraphState:
    state = _ensure_defaults(state)
    # If agent type isn't set yet, the user message is an "intent seed" not a field answer.
    if "agent_type" not in state:
        state["agent_type"] = _route_intent(state.get("last_user_message", ""))
        state["reply"] = (
            "I can help with **resume/career guidance** or **job role prediction**.\n"
            f"Detected intent: **{state['agent_type']}**.\n"
        )
        # Ask first required field
        q = _next_question(state["agent_type"], state["user_data"])
        if q:
            state["reply"] += "\n" + q
        return state

    # Otherwise, apply the latest user message as the answer to the previously asked field.
    _apply_user_message_to_expected_field(state)
    return state


def router_node(state: GraphState) -> str:
    # route by already-detected agent_type
    return "resume_builder_agent" if state["agent_type"] == "resume" else "job_prediction_agent"


def resume_builder_agent(state: GraphState) -> GraphState:
    user_data = state["user_data"]

    q = _next_question("resume", user_data)
    if q:
        state["reply"] = q
        return state

    # All required fields collected -> generate guidance via Ollama
    full_name = str(user_data.get("full_name", "")).strip()
    education = str(user_data.get("education_level", "")).strip()
    skills = str(user_data.get("skills", "")).strip()
    work_exp = str(user_data.get("work_experience", "")).strip()
    career_goal = str(user_data.get("career_goal", "")).strip()

    prompt = f"""
You are a career coach focused on decent work, fair opportunities, and lifelong learning.
Use inclusive, encouraging language and avoid promising guaranteed jobs.

User data:
- Full name: {full_name}
- Education: {education}
- Skills: {skills}
- Experience: {work_exp}
- Career goal: {career_goal}

Return clear, concise resume help:
1) A 3–4 sentence resume summary.
2) Three strong bullet points that could go under experience.
3) Three practical recommendations to improve employability and learning.

Format your answer as:
Summary:
...text...

Bullets:
- ...
- ...
- ...

Recommendations:
- ...
- ...
- ...
"""

    try:
        llm_text = ollama_llm.invoke(prompt)
        if not llm_text or not llm_text.strip():
            raise ValueError("Ollama returned empty response")
    except Exception as e:
        state["reply"] = (
            f"⚠️ **Ollama AI service is not available.**\n\n"
            f"Error: {str(e)}\n\n"
            "Please ensure Ollama is running (`ollama run llama3.2`) and try again.\n"
            "I cannot generate AI-powered resume guidance without Ollama."
        )
        return state

    # For now, store the whole LLM output as the summary; preview will show it in SUMMARY.
    state["ai_output"] = {
        "summary": llm_text,
        "resume_bullets": [],
        "recommendations": [],
        "work_experience_raw": work_exp,
    }

    preview = _render_resume_preview(user_data, state["ai_output"])
    state["reply"] = (
        "Here is AI-generated resume guidance, aligned with decent work and ethical career growth:\n\n"
        f"{llm_text}\n\n"
        "RESUME_PREVIEW_START\n"
        + preview
        + "\nRESUME_PREVIEW_END"
    )
    return state


def job_prediction_agent(state: GraphState) -> GraphState:
    user_data = state["user_data"]
    q = _next_question("job_prediction", user_data)
    if q:
        state["reply"] = q
        return state

    skills_list = user_data.get("skills_list") or _normalize_skills(str(user_data.get("skills", "")))
    location = str(user_data.get("location", "")).strip()
    exp_level = str(user_data.get("experience_level", "")).strip().lower()

    roles = _predict_roles(skills_list, location, exp_level)
    sector = _predict_sector(skills_list)
    level = exp_level if exp_level in ("entry", "mid", "senior") else "mid"

    state["ai_output"] = {
        "top_roles": roles[:3],
        "industry_sector": sector,
        "job_level": level,
        "recommendations": [
            "Validate roles by reading 10 job postings in your location and mapping skill gaps.",
            "Avoid relying on guarantees—use this as guidance and iterate with real market signals.",
            "Invest in one skill that increases mobility (communication, portfolio, or domain depth).",
        ],
    }

    state["reply"] = (
        f"Based on your skills and location (**{location}**), suitable roles include:\n"
        + "\n".join([f"- {r}" for r in roles[:3]])
        + f"\n\n**Industry alignment**: {sector}\n"
        + f"**Level fit**: {level}\n\n"
        + "I can also help you strengthen any missing skills for better access to decent work."
    )
    return state


def _predict_sector(skills: list[str]) -> str:
    s = " ".join([k.lower() for k in skills])
    if any(k in s for k in ["react", "frontend", "ui", "ux"]):
        return "Software / Web"
    if any(k in s for k in ["python", "sql", "ml", "data", "pandas"]):
        return "Data / Analytics"
    if any(k in s for k in ["aws", "azure", "gcp", "devops", "docker", "kubernetes"]):
        return "Cloud / DevOps"
    return "General Technology"


def _predict_roles(skills: list[str], location: str, exp_level: str) -> list[str]:
    s = " ".join([k.lower() for k in skills])
    roles: list[str] = []
    if any(k in s for k in ["python", "sql", "pandas", "excel", "tableau", "power bi"]):
        roles += ["Data Analyst", "Business Intelligence Analyst", "Junior Data Engineer"]
    if any(k in s for k in ["react", "javascript", "typescript", "html", "css"]):
        roles += ["Frontend Developer", "Full-Stack Developer", "UI Engineer"]
    if any(k in s for k in ["ml", "machine learning", "nlp"]):
        roles += ["Machine Learning Engineer", "Applied AI Engineer", "Data Scientist"]
    if not roles:
        roles = ["Operations Associate", "Customer Support Specialist", "Project Coordinator"]

    # light location flavor (no guarantees)
    if location:
        roles = [f"{r} (relevant in {location})" for r in roles]

    # de-duplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for r in roles:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _render_resume_preview(user_data: dict[str, Any], ai_output: dict[str, Any]) -> str:
    full_name = str(user_data.get("full_name", "")).strip()
    education = str(user_data.get("education_level", "")).strip()
    skills = user_data.get("skills_list") or _normalize_skills(str(user_data.get("skills", "")))
    work = str(user_data.get("work_experience", "")).strip()
    summary = str(ai_output.get("summary", "")).strip()
    bullets = ai_output.get("resume_bullets", []) or []

    lines: list[str] = []
    lines.append(full_name or "Full Name")
    lines.append("")
    lines.append("SUMMARY")
    lines.append(summary or "—")
    lines.append("")
    lines.append("SKILLS")
    lines.append(", ".join(skills) if skills else "—")
    lines.append("")
    lines.append("EDUCATION")
    lines.append(education or "—")
    lines.append("")
    lines.append("EXPERIENCE (RAW INPUT)")
    lines.append(work or "—")
    lines.append("")
    lines.append("BULLET IDEAS")
    for b in bullets:
        lines.append(f"- {b}")
    return "\n".join(lines)


@dataclass
class GraphRunner:
    repo: SupabaseRepo

    def build(self):
        g = StateGraph(GraphState)
        g.add_node("start_node", start_node)
        g.add_node("resume_builder_agent", resume_builder_agent)
        g.add_node("job_prediction_agent", job_prediction_agent)

        g.set_entry_point("start_node")
        g.add_conditional_edges("start_node", router_node)
        g.add_edge("resume_builder_agent", "finalize")
        g.add_edge("job_prediction_agent", "finalize")

        async def finalize(state: GraphState) -> GraphState:
            state = _ensure_defaults(state)
            # Persist session state
            user_data = state.get("user_data", {})
            ai_output = state.get("ai_output", {})
            full_name = str(user_data.get("full_name", "")).strip() or None
            agent_type = state["agent_type"]

            # Determine if complete -> webhook
            complete = (
                (_next_question(agent_type, user_data) is None)
                and bool(ai_output)
                and (not state.get("webhook_sent", False))
            )

            webhook_sent = bool(state.get("webhook_sent", False))
            if complete:
                payload = {
                    "full_name": full_name or "",
                    "agent_type": agent_type,
                    "input_data": {
                        "skills": str(user_data.get("skills", "")),
                        "education": str(user_data.get("education_level", "")) if agent_type == "resume" else "",
                        "location": str(user_data.get("location", "")) if agent_type == "job_prediction" else "",
                    },
                    "ai_result": {
                        "summary": str(ai_output.get("summary", "")) if agent_type == "resume" else "",
                        "recommendations": ai_output.get("recommendations", []),
                    },
                }
                ok, _err = await send_webhook(payload)
                webhook_sent = ok

            state["webhook_sent"] = webhook_sent
            self.repo.upsert_session(
                session_id=state["session_id"],
                agent_type=agent_type,
                full_name=full_name,
                user_data=user_data,
                ai_output=ai_output,
                webhook_sent=webhook_sent,
            )
            return state

        g.add_node("finalize", finalize)
        g.add_edge("finalize", END)
        return g.compile()

