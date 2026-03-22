"""
ResearchAgent v5.0 Backend — FastAPI Server
Handles: AI chat routing, tool execution, session management, Drive integration
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os, json, time
from dotenv import load_dotenv

load_dotenv()

from ai_router import AIRouter
from tools.search_pubmed import search_pubmed, search_pubmed_mesh
from tools.search_scopus import search_scopus
from tools.drive_ops import DriveOps
from tools.create_doc import create_google_doc
from tools.create_sheet import create_google_sheet
from tools.create_slides import create_google_slides
from tools.read_files import read_drive_files, read_file_content
from tools.notebook_gen import generate_notebook
from tools.academic_write import write_literature_review, write_results, write_discussion
from tools.session_mgr import SessionManager

app = FastAPI(title="ResearchAgent API", version="5.0")

# CORS — allow frontend from any origin during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
ai = AIRouter()
sessions = SessionManager()

# ══════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ══════════════════════════════════════════════════════════

class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    tool_results: Optional[List[Dict]] = None  # inline tool results

class ChatRequest(BaseModel):
    session_id: str
    messages: List[ChatMessage]
    model: Optional[str] = None  # default chat model
    tool_models: Optional[Dict[str, str]] = None  # per-tool model mapping
    drive_token: Optional[str] = None  # Google OAuth token from frontend
    working_folder_id: Optional[str] = None

class ToolRequest(BaseModel):
    tool: str
    params: Dict[str, Any]
    session_id: Optional[str] = None
    drive_token: Optional[str] = None

class SessionRequest(BaseModel):
    session_id: str
    drive_token: Optional[str] = None

# ══════════════════════════════════════════════════════════
# CHAT ENDPOINT — The Brain
# ══════════════════════════════════════════════════════════

@app.post("/api/chat")
async def chat(req: ChatRequest):
    """
    Main conversational endpoint.
    1. Receives user message + conversation history
    2. Sends to AI with tool definitions
    3. AI decides: respond directly OR call a tool
    4. If tool call: execute tool, send result back to AI
    5. AI generates final response
    6. Return response + any tool results to frontend
    """
    try:
        result = await ai.chat(
            messages=[m.dict() for m in req.messages],
            session_id=req.session_id,
            model=req.model,
            tool_models=req.tool_models,
            drive_token=req.drive_token,
            working_folder_id=req.working_folder_id,
        )
        
        # Auto-save session
        sessions.save_message(req.session_id, req.messages[-1].dict())
        if result.get("message"):
            sessions.save_message(req.session_id, {
                "role": "assistant",
                "content": result["message"],
                "tool_results": result.get("tool_results"),
            })
        
        return result
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    SSE streaming version of /api/chat.
    Sends real-time events as tools execute:
    - status: AI is thinking
    - tool_start: A tool is about to run
    - tool_done: A tool finished
    - done: Final response ready
    """
    async def event_generator():
        try:
            async for event in ai.chat_stream(
                messages=[m.dict() for m in req.messages],
                session_id=req.session_id,
                model=req.model,
                tool_models=req.tool_models,
                drive_token=req.drive_token,
                working_folder_id=req.working_folder_id,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': str(e)}})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# ══════════════════════════════════════════════════════════
# DIRECT TOOL ENDPOINTS (callable independently from chat)
# ══════════════════════════════════════════════════════════

@app.post("/api/tools/search_pubmed")
async def api_search_pubmed(req: ToolRequest):
    """Search PubMed with MeSH terms or free text"""
    query = req.params.get("query", "")
    max_results = req.params.get("max_results", 15)
    use_mesh = req.params.get("use_mesh", True)
    
    if use_mesh:
        # AI generates MeSH terms first
        mesh_result = await ai.generate_mesh_terms(query)
        results = []
        for q in mesh_result.get("queries", [query]):
            papers = await search_pubmed(q, max_results)
            results.extend(papers)
        # Deduplicate
        seen = set()
        unique = []
        for p in results:
            if p["pmid"] not in seen:
                seen.add(p["pmid"])
                unique.append(p)
        return {"papers": unique, "mesh_terms": mesh_result.get("mesh_terms", []), "queries": mesh_result.get("queries", [])}
    else:
        papers = await search_pubmed(query, max_results)
        return {"papers": papers}

@app.post("/api/tools/search_scopus")
async def api_search_scopus(req: ToolRequest):
    """Search Scopus with query"""
    query = req.params.get("query", "")
    max_results = req.params.get("max_results", 10)
    scopus_key = os.getenv("SCOPUS_API_KEY", "")
    if not scopus_key:
        return {"papers": [], "error": "Scopus API key not configured"}
    papers = await search_scopus(query, scopus_key, max_results)
    return {"papers": papers}

@app.post("/api/tools/drive/list_folders")
async def api_drive_list_folders(req: ToolRequest):
    """List folders in Google Drive"""
    drive = DriveOps(req.drive_token)
    query = req.params.get("query", "")
    return {"folders": await drive.list_folders(query)}

@app.post("/api/tools/drive/list_files")
async def api_drive_list_files(req: ToolRequest):
    """List files in a Drive folder"""
    drive = DriveOps(req.drive_token)
    folder_id = req.params.get("folder_id")
    return {"files": await drive.list_files(folder_id)}

@app.post("/api/tools/drive/read_file")
async def api_drive_read_file(req: ToolRequest):
    """Read text content of a Drive file"""
    drive = DriveOps(req.drive_token)
    file_id = req.params.get("file_id")
    return {"content": await drive.read_file(file_id)}

@app.post("/api/tools/drive/create_folder")
async def api_drive_create_folder(req: ToolRequest):
    """Create a folder in Drive"""
    drive = DriveOps(req.drive_token)
    name = req.params.get("name")
    parent_id = req.params.get("parent_id")
    return {"folder_id": await drive.create_folder(name, parent_id)}

@app.post("/api/tools/create_doc")
async def api_create_doc(req: ToolRequest):
    """Create a Google Doc"""
    drive = DriveOps(req.drive_token)
    name = req.params.get("name", "Research_Paper")
    content = req.params.get("content", "")
    folder_id = req.params.get("folder_id")
    result = await create_google_doc(drive, name, content, folder_id)
    return result

@app.post("/api/tools/create_sheet")
async def api_create_sheet(req: ToolRequest):
    """Create a Google Sheet"""
    drive = DriveOps(req.drive_token)
    name = req.params.get("name", "Research_Data")
    data = req.params.get("data", "")
    folder_id = req.params.get("folder_id")
    result = await create_google_sheet(drive, name, data, folder_id)
    return result

@app.post("/api/tools/create_slides")
async def api_create_slides(req: ToolRequest):
    """Create Google Slides"""
    drive = DriveOps(req.drive_token)
    name = req.params.get("name", "Research_Presentation")
    content = req.params.get("content", "")
    folder_id = req.params.get("folder_id")
    result = await create_google_slides(drive, name, content, folder_id)
    return result

@app.post("/api/tools/write_review")
async def api_write_review(req: ToolRequest):
    """Write a literature review from papers"""
    topic = req.params.get("topic", "")
    papers = req.params.get("papers", [])
    file_contents = req.params.get("file_contents", [])
    model = req.params.get("model")
    result = await write_literature_review(ai, topic, papers, file_contents, model)
    return result

@app.post("/api/tools/generate_notebook")
async def api_generate_notebook(req: ToolRequest):
    """Generate a Colab notebook"""
    query = req.params.get("query", "")
    data_files = req.params.get("data_files", [])
    code_files = req.params.get("code_files", [])
    analysis = req.params.get("analysis", {})
    nb = await generate_notebook(ai, query, data_files, code_files, analysis)
    return {"notebook": nb}

# ══════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ══════════════════════════════════════════════════════════

@app.post("/api/session/save")
async def api_session_save(req: SessionRequest):
    """Save session to Drive"""
    session = sessions.get(req.session_id)
    if not session:
        return {"error": "Session not found"}
    if req.drive_token:
        drive = DriveOps(req.drive_token)
        result = await sessions.save_to_drive(req.session_id, drive)
        return result
    return {"status": "saved_locally"}

@app.post("/api/session/load")
async def api_session_load(req: SessionRequest):
    """Load session from local or Drive"""
    session = sessions.get(req.session_id)
    if session:
        return session
    if req.drive_token:
        drive = DriveOps(req.drive_token)
        session = await sessions.load_from_drive(req.session_id, drive)
        return session or {"error": "Session not found"}
    return {"error": "Session not found"}

@app.get("/api/session/list")
async def api_session_list():
    """List all local sessions"""
    return {"sessions": sessions.list_all()}

@app.post("/api/session/new")
async def api_session_new():
    """Create a new session"""
    session_id = sessions.create()
    return {"session_id": session_id}

# ══════════════════════════════════════════════════════════
# HEALTH CHECK
# ══════════════════════════════════════════════════════════

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "version": "5.0",
        "anthropic_key": bool(os.getenv("ANTHROPIC_API_KEY")),
        "google_key": bool(os.getenv("GOOGLE_API_KEY")),
        "scopus_key": bool(os.getenv("SCOPUS_API_KEY")),
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
