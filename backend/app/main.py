from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .graph import GraphRunner
from .schemas import ChatRequest, ChatResponse, ResumeFormRequest, ResumeFormResponse
from .settings import settings
from .supabase_repo import SupabaseRepo


app = FastAPI(title="AI Career Intelligence Platform", version="0.1.0")

# In development, allow the frontend from any origin (localhost / 127.0.0.1, etc.).
# If you want to lock this down later, replace ["*"] with [settings.frontend_origin].
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


repo = SupabaseRepo()
runner = GraphRunner(repo=repo)
graph = runner.build()

# Minimal in-memory session store for conversation state.
# In production you’d back this with DB/Redis and load by session_id.
SESSIONS: dict[str, dict[str, Any]] = {}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    try:
        session = SESSIONS.get(payload.session_id) or {"session_id": payload.session_id, "user_data": {}, "ai_output": {}}
        session["session_id"] = payload.session_id
        session["last_user_message"] = payload.message

        out = await graph.ainvoke(session)

        # Persist updated state in memory
        SESSIONS[payload.session_id] = dict(out)

        return ChatResponse(reply=str(out.get("reply", "")).strip() or "Could you rephrase that?")
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)  # Log to console
        return ChatResponse(reply=f"I encountered an error. Please try again. ({str(e)})")


@app.post("/resume/build", response_model=ResumeFormResponse)
async def build_resume(payload: ResumeFormRequest) -> ResumeFormResponse:
    """
    Direct endpoint for form-based resume building.
    Accepts all resume data at once and generates AI output immediately.
    """
    try:
        # Initialize session with all form data pre-filled
        session = SESSIONS.get(payload.session_id) or {
            "session_id": payload.session_id,
            "user_data": {},
            "ai_output": {},
        }
        session["session_id"] = payload.session_id
        session["agent_type"] = "resume"
        
        # Set all user data from form
        session["user_data"] = {
            "full_name": payload.full_name,
            "education_level": payload.education_level,
            "skills": payload.skills,
            "work_experience": payload.work_experience,
            "career_goal": payload.career_goal,
            "skills_list": [s.strip() for s in payload.skills.split(",") if s.strip()],
        }
        
        # Skip the question-asking phase and go straight to resume generation
        from .graph import resume_builder_agent, _ensure_defaults
        
        # Ensure defaults
        session = _ensure_defaults(session)
        
        # Call resume_builder_agent directly with all data
        state = resume_builder_agent(session)
        
        # Extract reply and preview
        reply = str(state.get("reply", "")).strip()
        
        # Extract preview from reply
        preview_start = reply.find("RESUME_PREVIEW_START")
        preview_end = reply.find("RESUME_PREVIEW_END")
        preview = ""
        if preview_start != -1 and preview_end != -1:
            preview = reply[preview_start + len("RESUME_PREVIEW_START"):preview_end].strip()
            # Remove preview markers from reply
            reply = reply[:preview_start].strip() + reply[preview_end + len("RESUME_PREVIEW_END"):].strip()
        
        # Persist session
        SESSIONS[payload.session_id] = dict(state)
        
        # Finalize (save to Supabase, send webhook if needed) - simplified version
        try:
            user_data = state.get("user_data", {})
            ai_output = state.get("ai_output", {})
            full_name = str(user_data.get("full_name", "")).strip() or None
            agent_type = "resume"
            
            # Check if complete (all fields + AI output generated)
            from .graph import _next_question
            complete = (
                (_next_question(agent_type, user_data) is None)
                and bool(ai_output)
                and (not state.get("webhook_sent", False))
            )
            
            if complete:
                from .webhook import send_webhook
                payload_webhook = {
                    "full_name": full_name or "",
                    "agent_type": agent_type,
                    "input_data": {
                        "skills": str(user_data.get("skills", "")),
                        "education": str(user_data.get("education_level", "")),
                        "location": "",
                    },
                    "ai_result": {
                        "summary": str(ai_output.get("summary", "")),
                        "recommendations": ai_output.get("recommendations", []),
                    },
                }
                ok, _err = await send_webhook(payload_webhook)
                state["webhook_sent"] = ok
            
            # Save to Supabase
            repo.upsert_session(
                session_id=payload.session_id,
                agent_type=agent_type,
                full_name=full_name,
                user_data=user_data,
                ai_output=ai_output,
                webhook_sent=state.get("webhook_sent", False),
            )
        except Exception as e:
            print(f"Finalize error (non-fatal): {e}")
        
        return ResumeFormResponse(reply=reply or "Could not generate resume guidance.", preview=preview)
        
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
        print(error_msg)  # Log to console
        return ResumeFormResponse(
            reply=f"⚠️ Error generating resume: {str(e)}\n\nMake sure Ollama is running (`ollama run llama3.2`).",
            preview=""
        )

