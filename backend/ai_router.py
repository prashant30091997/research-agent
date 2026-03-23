"""
AI Router — The Brain of ResearchAgent
Sends messages to Claude/Gemini with tool definitions.
AI decides which tools to use. Router executes them and loops.
"""
import os, json, httpx, asyncio
from typing import List, Dict, Any, Optional

ANTHROPIC_API = "https://api.anthropic.com/v1/messages"
GEMINI_API = "https://generativelanguage.googleapis.com/v1beta/models"

# Tool definitions for Claude's function calling
TOOLS = [
    {
        "name": "search_pubmed",
        "description": "Search PubMed academic database for research papers. Returns titles, authors, journal, year, PMID. Use when user asks to find papers, search literature, or do academic search.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "PubMed search query. Can use MeSH terms like: \"fNIRS\"[MeSH] AND \"cognitive impairment\"[MeSH]"},
                "max_results": {"type": "integer", "description": "Max papers to return (default 15)", "default": 15}
            },
            "required": ["query"]
        }
    },
    {
        "name": "search_scopus",
        "description": "Search Scopus/Elsevier academic database. Provides citation counts. Use alongside PubMed for comprehensive search.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Scopus query. Use TITLE-ABS-KEY(term1 AND term2) format."},
                "max_results": {"type": "integer", "default": 10}
            },
            "required": ["query"]
        }
    },
    {
        "name": "generate_mesh_terms",
        "description": "Generate optimized PubMed MeSH terms and multiple search strategies from a research topic. Use BEFORE search_pubmed to get better results.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The research topic to generate MeSH terms for"}
            },
            "required": ["topic"]
        }
    },
    {
        "name": "drive_list_folders",
        "description": "List folders in user's Google Drive. Use when user asks to browse, navigate, or find a folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term to filter folders (optional)", "default": ""}
            }
        }
    },
    {
        "name": "drive_list_files",
        "description": "List all files in a specific Google Drive folder. Returns file names, types, sizes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "folder_id": {"type": "string", "description": "Google Drive folder ID"}
            },
            "required": ["folder_id"]
        }
    },
    {
        "name": "drive_read_file",
        "description": "Read the text content of a file from Google Drive. Works for .py, .txt, .csv, .md, .json files. For .pdf/.docx, extracts text via Google export.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {"type": "string", "description": "Google Drive file ID"},
                "file_name": {"type": "string", "description": "File name (for context)"}
            },
            "required": ["file_id"]
        }
    },
    {
        "name": "drive_create_folder",
        "description": "Create a new folder in Google Drive.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Folder name"},
                "parent_id": {"type": "string", "description": "Parent folder ID (optional, defaults to root)"}
            },
            "required": ["name"]
        }
    },
    {
        "name": "write_literature_review",
        "description": "Write a comprehensive academic literature review based on selected papers and/or file contents. Use after papers have been found and selected.",
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Research topic"},
                "papers": {"type": "array", "items": {"type": "object"}, "description": "List of paper objects with title, authors, journal, year, content"},
                "instructions": {"type": "string", "description": "Additional instructions from user (e.g., 'focus on methodology', 'make introduction longer')"}
            },
            "required": ["topic"]
        }
    },
    {
        "name": "write_section",
        "description": "Write a specific section of a research paper: abstract, introduction, methodology, results, discussion, conclusion.",
        "input_schema": {
            "type": "object",
            "properties": {
                "section": {"type": "string", "enum": ["abstract", "introduction", "methodology", "results", "discussion", "conclusion"]},
                "topic": {"type": "string"},
                "context": {"type": "string", "description": "Previous sections content, paper data, findings"},
                "instructions": {"type": "string", "description": "User's specific instructions"}
            },
            "required": ["section", "topic"]
        }
    },
    {
        "name": "create_google_doc",
        "description": "Create OR UPDATE a Google Doc in the user's Drive folder. If a file with the same name already exists, it UPDATES that file instead of creating a duplicate. ALWAYS use the SAME name when refining a document. Always include a References section at the end.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Document name"},
                "content": {"type": "string", "description": "HTML content of the document"},
                "folder_id": {"type": "string", "description": "Drive folder ID to save in"}
            },
            "required": ["name", "content"]
        }
    },
    {
        "name": "create_google_sheet",
        "description": "Create OR UPDATE a Google Sheet. If same name exists, updates it instead of duplicating.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Sheet name"},
                "data": {"type": "string", "description": "CSV formatted data"},
                "folder_id": {"type": "string", "description": "Drive folder ID"}
            },
            "required": ["name", "data"]
        }
    },
    {
        "name": "create_google_slides",
        "description": "Create OR UPDATE Google Slides. If same name exists, updates it instead of duplicating.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Presentation name"},
                "content": {"type": "string", "description": "HTML content with <section> tags for each slide"},
                "folder_id": {"type": "string", "description": "Drive folder ID"}
            },
            "required": ["name", "content"]
        }
    },
    {
        "name": "generate_colab_notebook",
        "description": "Generate a Google Colab notebook (.ipynb) for data analysis. Use when user has data files (.mat, .csv, .xlsx) that need computational processing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What analysis to perform"},
                "data_files": {"type": "array", "items": {"type": "object"}, "description": "List of data file info"},
                "code_files": {"type": "array", "items": {"type": "object"}, "description": "Existing code files to reuse"},
                "drive_path": {"type": "string", "description": "Drive path for data"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "fetch_site_documents",
        "description": "Search for guidelines, policies, and reports from institutional sites (ICMR, WHO, NIH, CDC, IEEE, arXiv, etc.). Use when user mentions specific institutions or asks for government/organizational documents.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Research topic to find documents for"},
                "sites": {"type": "array", "items": {"type": "string"}, "description": "Site keys: icmr, who, nih, cdc, mohfw, lancet, nature, ieee, arxiv, biorxiv, dbt, csir"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "query_site_info",
        "description": "Get information about what a specific institutional site provides — databases, resources, access methods. Use when user asks 'what does ICMR provide' or 'tell me about NIH resources'.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sites": {"type": "array", "items": {"type": "string"}, "description": "Site keys to get info about"}
            },
            "required": ["sites"]
        }
    },
    {
        "name": "understand_code",
        "description": "Read .py/.ipynb code files from Drive and analyze their purpose, functions, pipeline logic, and dependencies. Use after drive_list_files to understand existing code in a project folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code_files": {"type": "array", "items": {"type": "object"}, "description": "List of code file objects with id, name, content fields"},
                "data_files": {"type": "array", "items": {"type": "object"}, "description": "Data files in the same folder (for context)"},
                "query": {"type": "string", "description": "Research context"}
            },
            "required": ["code_files"]
        }
    },
    {
        "name": "design_pipeline",
        "description": "Design a complete data analysis pipeline — preprocessing steps, analysis methods, statistical tests, output figures. Use before generating a Colab notebook.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What analysis to design"},
                "signal_types": {"type": "array", "items": {"type": "string"}, "description": "Signal types: eeg, ecg, emg, fnirs, auto"},
                "custom_signal": {"type": "string", "description": "Description of custom/unconventional signal type"},
                "data_files": {"type": "array", "items": {"type": "object"}, "description": "Available data files"},
                "code_analysis": {"type": "string", "description": "Output from understand_code (if available)"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "download_papers",
        "description": "Download PDFs of selected papers to Drive. For each paper, tries 5 strategies to find PDF: (1) PMC direct URL, (2) NCBI PMC URL, (3) Europe PMC fullTextUrlList, (4) Unpaywall, (5) DOI-based. Also creates a Paper_Compilation Google Doc with abstracts and clickable download links for ALL papers (both downloaded and not). Pass the paper objects from the user's selection.",
        "input_schema": {
            "type": "object",
            "properties": {
                "papers": {"type": "array", "items": {"type": "object"}, "description": "List of paper objects with pmid, doi, title fields"},
                "folder_id": {"type": "string", "description": "Drive folder ID to save papers in"}
            },
            "required": ["papers"]
        }
    },
    {
        "name": "get_paper_full_text",
        "description": "Retrieve full text content of a paper for analysis. Tries Europe PMC full text, then PubMed abstract. Use this BEFORE write_literature_review to get actual paper content for a better review.",
        "input_schema": {
            "type": "object",
            "properties": {
                "papers": {"type": "array", "items": {"type": "object"}, "description": "List of paper objects with pmid, doi, title"},
            },
            "required": ["papers"]
        }
    },
]

SYSTEM_PROMPT = """You are ResearchAgent — an AI research assistant that helps academics with literature search, paper writing, data analysis, and document creation.

You have access to these tools:
- search_pubmed: Search PubMed for papers (free, no key needed)
- search_scopus: Search Scopus for papers (needs API key)
- generate_mesh_terms: Generate optimized MeSH search terms from a topic
- download_papers: Download PDFs to Drive. Finds PDF URLs using 5 strategies (PMC direct, NCBI PMC, fullTextUrlList, Unpaywall, DOI). Creates Paper_Compilation doc with ALL abstracts + clickable links for manual download.
- get_paper_full_text: READ the actual full text of papers from Europe PMC and PubMed. Use this BEFORE writing a review so you have real paper content.
- drive_list_folders / drive_list_files / drive_read_file / drive_create_folder: Browse and manage Google Drive
- write_literature_review: Write comprehensive lit review from papers (use AFTER get_paper_full_text)
- write_section: Write specific paper sections (abstract, intro, methods, results, discussion, conclusion)
- understand_code: Read and analyze .py code files — functions, pipeline, dependencies
- design_pipeline: Design analysis pipeline for biosignal/data processing
- create_google_doc: Create a Google Doc in Drive
- create_google_sheet: Create a Google Sheet in Drive
- create_google_slides: Create Google Slides in Drive
- generate_colab_notebook: Generate analysis notebook
- fetch_site_documents: Find documents from ICMR, WHO, NIH, CDC, IEEE, arXiv, etc.
- query_site_info: Get info about institutional resources

CRITICAL WORKFLOW — When user asks to search, download, and review papers:
1. generate_mesh_terms → get MeSH terms
2. search_pubmed (and search_scopus if available) → find papers (fast, no PDF lookup)
3. PRESENT papers → let user select
4. download_papers → finds PDF URLs (5 strategies: PMC direct, NCBI PMC, fullTextUrlList, Unpaywall, DOI) → downloads to Drive → creates Paper_Compilation doc with ALL abstracts + clickable links
5. get_paper_full_text → reads downloaded PDFs text + abstracts. Papers with PDFs AND abstracts will appear in both — the AI should deduplicate by title when writing.
6. write_literature_review → write review using ALL content. Deduplicate: if a paper has full text from PDF, use that; if only abstract, use abstract. ONLY cite papers from the user's selected list.
7. create_google_doc → save the review to Drive

CRITICAL RULES:
- You CAN download papers. Use the download_papers tool. NEVER say "I cannot download papers".
- You CAN read full paper text. Use get_paper_full_text. NEVER say "I only have metadata".
- ALWAYS download papers when user asks for download or review.
- ALWAYS get full text before writing reviews.
- ALWAYS add a References section at the end of every document you create (Google Doc, review, report, etc.). Use proper academic citation format.
- When creating Google Docs/Sheets/Slides: if a file with the SAME NAME already exists in the folder, it will be UPDATED (not duplicated). So when the user asks to refine or modify, use the SAME file name to update the existing file.
- When user asks to "refine", "modify", "edit", "improve", "change" a document — generate the COMPLETE updated content with the changes incorporated, using the SAME file name. The system will automatically update the existing file.
- Present paper lists in numbered format so user can say "use papers 1,3,5,7".
- When user says "search more" or "different terms", search again with new terms.
- If user selected a working folder, use that folder_id for all file operations.
- Be conversational — explain what you're doing and ask for guidance.
- Paper downloads have a 4-second delay between each paper to avoid rate limiting.
- For papers that cannot be downloaded (not open-access), a separate Google Doc "Papers_Without_Open_Access" is automatically created in the folder with their titles, abstracts, and citations.

NEVER:
- Say you cannot download papers (you CAN, use download_papers)
- Say you only have metadata/abstracts (use get_paper_full_text for full content)
- Ask the user for a folder ID or where to save files — the working folder is ALREADY SET, just use it
- Ask the user to provide a Drive folder — you already have it
- Run all tasks automatically without user input
- Create files without confirming with user
- Hallucinate paper titles or citations"""


def _summarize_input(tool_name, tool_input):
    """Create a human-readable summary of what a tool is about to do"""
    summaries = {
        "search_pubmed": lambda i: f"Searching PubMed for: \"{i.get('query','')[:60]}\"",
        "search_scopus": lambda i: f"Searching Scopus for: \"{i.get('query','')[:60]}\"",
        "generate_mesh_terms": lambda i: f"Generating MeSH terms for: \"{i.get('topic','')[:60]}\"",
        "download_papers": lambda i: f"Downloading {len(i.get('papers',[]))} papers to Drive",
        "get_paper_full_text": lambda i: f"Reading full text of {len(i.get('papers',[]))} papers",
        "drive_list_folders": lambda i: f"Listing Drive folders{': '+i['query'] if i.get('query') else ''}",
        "drive_list_files": lambda i: f"Listing files in folder",
        "drive_read_file": lambda i: f"Reading: {i.get('file_name','file')}",
        "drive_create_folder": lambda i: f"Creating folder: {i.get('name','')}",
        "write_literature_review": lambda i: f"Writing review on: \"{i.get('topic','')[:50]}\"",
        "write_section": lambda i: f"Writing {i.get('section','section')} section",
        "understand_code": lambda i: f"Analyzing {len(i.get('code_files',[]))} code files",
        "design_pipeline": lambda i: f"Designing pipeline for: \"{i.get('query','')[:50]}\"",
        "create_google_doc": lambda i: f"Creating Google Doc: {i.get('name','')}",
        "create_google_sheet": lambda i: f"Creating Google Sheet: {i.get('name','')}",
        "create_google_slides": lambda i: f"Creating Google Slides: {i.get('name','')}",
        "generate_colab_notebook": lambda i: f"Generating Colab notebook",
        "fetch_site_documents": lambda i: f"Fetching documents from {', '.join(i.get('sites',['sites']))}",
        "query_site_info": lambda i: f"Getting info about: {', '.join(i.get('sites',[]))}",
    }
    fn = summaries.get(tool_name)
    return fn(tool_input) if fn else f"Running {tool_name}"

def _summarize_result(tool_name, result):
    """Create a human-readable summary of what a tool returned"""
    if isinstance(result, dict):
        if result.get("error"): return f"❌ Error: {result['error'][:80]}"
        if result.get("summary"): return f"✅ {result['summary']}"
        if result.get("url"): return f"✅ Created: {result['url'][:60]}"
        if result.get("content"): return f"✅ {len(result['content'])} chars of content"
        if result.get("analysis"): return f"✅ Analysis complete"
        if result.get("pipeline"): return f"✅ Pipeline designed"
    if isinstance(result, list):
        return f"✅ {len(result)} results"
    return "✅ Done"


class AIRouter:
    def __init__(self):
        self.anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.google_key = os.getenv("GOOGLE_API_KEY", "")
        # Session memory: text history + structured data (papers, analysis, etc.)
        self._session_history = {}   # session_id → [{"role":"user","content":"..."}, ...]
        self._session_context = {}   # session_id → {"papers": [...], "review": "...", ...}
        # Auto-select default model
        configured = os.getenv("DEFAULT_MODEL", "")
        if configured:
            self.default_model = configured
        elif self.anthropic_key:
            self.default_model = "claude-sonnet-4-20250514"
        elif self.google_key:
            self.default_model = "gemini-2.5-flash"
        else:
            self.default_model = "gemini-2.5-flash"
    
    def _build_context_prompt(self, session_id: str) -> str:
        """Build a context string from session data (papers found, files analyzed, etc.)"""
        ctx = self._session_context.get(session_id, {})
        parts = []
        
        if ctx.get("papers"):
            papers = ctx["papers"]
            parts.append(f"\n\nSESSION CONTEXT — {len(papers)} papers found in this session:")
            for i, p in enumerate(papers, 1):
                line = f"{i}. {p.get('title','')} ({p.get('authors','')}, {p.get('year','')}) PMID:{p.get('pmid','')} DOI:{p.get('doi','')}"
                if p.get("pdf_url"): line += " [PDF AVAILABLE]"
                else: line += " [NO PDF]"
                parts.append(line)
            parts.append("\nWhen user says 'download all' or 'use all papers', pass these EXACT paper objects to the download_papers tool. They already have pdf_url attached.")
        
        if ctx.get("downloaded"):
            parts.append(f"\nDOWNLOADED: {len(ctx['downloaded'])} papers saved to Drive folder.")
        
        if ctx.get("review"):
            parts.append(f"\nLITERATURE REVIEW: Already written ({len(ctx['review'])} chars). User may ask to modify it.")
        
        if ctx.get("code_analysis"):
            parts.append(f"\nCODE ANALYSIS: Done. {ctx['code_analysis'][:200]}...")
        
        if ctx.get("pipeline"):
            parts.append(f"\nPIPELINE: Designed. User may ask to generate notebook.")
        
        return "\n".join(parts) if parts else ""
    
    def _store_tool_result(self, session_id: str, tool_name: str, result):
        """Store structured data from tool results in session context."""
        ctx = self._session_context.setdefault(session_id, {})
        
        if tool_name == "search_pubmed" and isinstance(result, list):
            existing = {p.get("pmid") for p in ctx.get("papers", [])}
            for p in result:
                if p.get("pmid") not in existing:
                    ctx.setdefault("papers", []).append(p)
        
        elif tool_name == "search_scopus" and isinstance(result, list):
            ctx.setdefault("papers", []).extend(result)
        
        elif tool_name == "download_papers" and isinstance(result, dict):
            ctx["downloaded"] = result.get("downloaded", [])
            ctx["download_summary"] = result.get("summary", "")
        
        elif tool_name == "write_literature_review" and isinstance(result, dict):
            ctx["review"] = result.get("content", "")[:500]
        
        elif tool_name == "understand_code" and isinstance(result, dict):
            ctx["code_analysis"] = result.get("analysis", "")[:500]
        
        elif tool_name == "design_pipeline" and isinstance(result, dict):
            ctx["pipeline"] = result.get("pipeline", {})
        
        elif tool_name == "create_google_doc" and isinstance(result, dict):
            ctx["last_doc"] = result.get("url", "")
        
        elif tool_name == "generate_mesh_terms" and isinstance(result, dict):
            ctx["mesh_terms"] = result.get("mesh_terms", [])
    
    async def chat(self, messages: List[Dict], session_id: str = "", model: str = None,
                   tool_models: Dict[str, str] = None, drive_token: str = None, working_folder_id: str = None,
                   selected_files: List[Dict] = None, event_queue=None) -> Dict:
        """
        Main chat loop. Uses TEXT-ONLY conversation history (works with both Anthropic and Gemini).
        Structured data (papers, analysis) stored separately and injected as context.
        """
        model = model or self.default_model
        self._tool_models = tool_models or {}
        
        # Build system prompt with all context
        system = SYSTEM_PROMPT
        if working_folder_id:
            system += f"\n\nACTIVE WORKING FOLDER (Drive ID): {working_folder_id}. Use this for ALL file operations. NEVER ask user for folder ID."
        if selected_files:
            file_list = ", ".join(f"{f.get('name','')}" for f in selected_files)
            system += f"\n\nSELECTED FILES: {file_list}"
        
        # Inject session context (papers found, analysis done, etc.)
        system += self._build_context_prompt(session_id)
        
        # Build API messages from text-only history + new message
        history = self._session_history.get(session_id, [])
        
        new_user_content = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                new_user_content = m.get("content", "")
                break
        if not new_user_content:
            return {"message": "No message received", "tool_results": []}
        
        # Build clean API messages: text history + new user message
        api_messages = []
        for h in history:
            api_messages.append({"role": h["role"], "content": h["content"]})
        api_messages.append({"role": "user", "content": new_user_content})
        
        tool_results = []
        max_loops = 10
        
        for loop in range(max_loops):
            if event_queue:
                await event_queue.put({"type": "status", "data": {"step": "thinking", "message": f"AI analyzing request (loop {loop+1})...", "model": model}})
            
            response = await self._call_ai(system, api_messages, model, use_tools=True)
            
            if not response:
                return {"message": "Error: No response from AI", "tool_results": tool_results}
            
            tool_uses = [b for b in response.get("content", []) if b.get("type") == "tool_use"]
            text_blocks = [b.get("text", "") for b in response.get("content", []) if b.get("type") == "text"]
            
            if not tool_uses:
                # Final text response — save to history and return
                final_text = "\n".join(text_blocks)
                history.append({"role": "user", "content": new_user_content})
                history.append({"role": "assistant", "content": final_text})
                self._session_history[session_id] = history
                
                if event_queue:
                    await event_queue.put({"type": "done", "data": {"message": final_text, "tool_results": tool_results}})
                return {"message": final_text, "tool_results": tool_results}
            
            # Execute each tool call
            tool_call_results = []
            for tool_use in tool_uses:
                tool_name = tool_use["name"]
                tool_input = tool_use["input"]
                tool_id = tool_use["id"]
                
                tool_model = self._tool_models.get(tool_name) or self._tool_models.get("chat") or self.default_model
                if tool_name.startswith("drive_"): tool_model = self._tool_models.get("drive_ops") or tool_model
                
                if event_queue:
                    await event_queue.put({"type": "tool_start", "data": {
                        "tool": tool_name, "model": tool_model,
                        "input_summary": _summarize_input(tool_name, tool_input),
                        "message": f"Running {tool_name}..."
                    }})
                
                import time as _time
                t0 = _time.time()
                result = await self._execute_tool(tool_name, tool_input, drive_token, working_folder_id)
                elapsed = round(_time.time() - t0, 1)
                
                # Store structured data from this tool result
                self._store_tool_result(session_id, tool_name, result)
                
                tool_results.append({"tool": tool_name, "input": tool_input, "result": result, "model": tool_model, "time": elapsed})
                
                if event_queue:
                    await event_queue.put({"type": "tool_done", "data": {
                        "tool": tool_name, "model": tool_model, "time": elapsed,
                        "result_summary": _summarize_result(tool_name, result),
                    }})
                
                # Truncate result for API message (keep under 4KB per tool result)
                result_str = json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                if len(result_str) > 4000:
                    result_str = result_str[:4000] + "...[truncated]"
                
                tool_call_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": result_str
                })
            
            # Add this exchange to api_messages for the current turn's tool loop
            api_messages.append({"role": "assistant", "content": response["content"]})
            api_messages.append({"role": "user", "content": tool_call_results})
        
        # Hit max loops — save what we have
        history.append({"role": "user", "content": new_user_content})
        history.append({"role": "assistant", "content": "Reached maximum tool call limit."})
        self._session_history[session_id] = history
        return {"message": "Reached maximum tool call limit. Please continue.", "tool_results": tool_results}

    async def chat_stream(self, messages, session_id="", model=None, tool_models=None, drive_token=None, working_folder_id=None, selected_files=None):
        """Streaming version — yields SSE events as tools execute"""
        import asyncio
        queue = asyncio.Queue()
        
        async def run_chat():
            await self.chat(messages, session_id, model, tool_models, drive_token, working_folder_id, selected_files, event_queue=queue)
            await queue.put(None)  # Signal end
        
        task = asyncio.create_task(run_chat())
        
        while True:
            event = await queue.get()
            if event is None:
                break
            yield event
        
        await task
    
    async def _call_ai(self, system: str, messages: List[Dict], model: str, use_tools: bool = True) -> Optional[Dict]:
        """Call Anthropic or Gemini API"""
        if "claude" in model or "anthropic" in model:
            return await self._call_anthropic(system, messages, model, use_tools)
        elif "gemini" in model:
            return await self._call_gemini(system, messages, model, use_tools)
        else:
            # Default: try Gemini if no Anthropic key, otherwise Anthropic
            if self.anthropic_key:
                return await self._call_anthropic(system, messages, model, use_tools)
            elif self.google_key:
                return await self._call_gemini(system, messages, "gemini-2.5-flash", use_tools)
            return {"content": [{"type": "text", "text": "No API keys configured. Add ANTHROPIC_API_KEY or GOOGLE_API_KEY to .env"}]}
    
    async def _call_anthropic(self, system: str, messages: List[Dict], model: str, use_tools: bool) -> Optional[Dict]:
        """Call Anthropic Claude API with tool use"""
        if not self.anthropic_key:
            return {"content": [{"type": "text", "text": "Anthropic API key not configured. Add ANTHROPIC_API_KEY to .env"}]}
        
        payload = {
            "model": model,
            "max_tokens": 4096,
            "system": system,
            "messages": messages,
        }
        if use_tools:
            payload["tools"] = TOOLS
        
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                ANTHROPIC_API,
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.anthropic_key,
                    "anthropic-version": "2023-06-01",
                },
                json=payload,
            )
            if r.status_code == 200:
                return r.json()
            else:
                return {"content": [{"type": "text", "text": f"API Error {r.status_code}: {r.text[:500]}"}]}
    
    async def _call_gemini(self, system: str, messages: List[Dict], model: str, use_tools: bool = True) -> Optional[Dict]:
        """Call Google Gemini API with full conversation and tool calling support"""
        if not self.google_key:
            return {"content": [{"type": "text", "text": "Google API key not configured. Add GOOGLE_API_KEY to .env"}]}
        
        # Convert messages to Gemini format
        contents = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            
            # Gemini uses "user" and "model" roles
            gemini_role = "model" if role == "assistant" else "user"
            
            if isinstance(content, str):
                contents.append({"role": gemini_role, "parts": [{"text": content}]})
            elif isinstance(content, list):
                # Tool results — convert to text for Gemini
                parts = []
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "tool_result":
                            parts.append({"text": f"[Tool Result]: {item.get('content', '')}"})
                        elif item.get("type") == "text":
                            parts.append({"text": item.get("text", "")})
                        elif item.get("type") == "tool_use":
                            parts.append({"text": f"[Calling tool: {item.get('name', '')}]"})
                        else:
                            parts.append({"text": str(item)})
                    else:
                        parts.append({"text": str(item)})
                if parts:
                    contents.append({"role": gemini_role, "parts": parts})
        
        # Build request
        payload = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system}]},
            "generationConfig": {"maxOutputTokens": 8192, "temperature": 0.7},
        }
        
        # Add tool definitions in Gemini format
        if use_tools and TOOLS:
            gemini_tools = []
            for tool in TOOLS:
                gemini_tools.append({
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("input_schema", {"type": "object", "properties": {}}),
                })
            payload["tools"] = [{"functionDeclarations": gemini_tools}]
        
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(
                f"{GEMINI_API}/{model}:generateContent?key={self.google_key}",
                json=payload,
            )
            if r.status_code != 200:
                return {"content": [{"type": "text", "text": f"Gemini Error ({r.status_code}): {r.text[:500]}"}]}
            
            d = r.json()
            candidate = d.get("candidates", [{}])[0]
            parts = candidate.get("content", {}).get("parts", [])
            
            # Convert Gemini response to Anthropic-compatible format
            content_blocks = []
            for part in parts:
                if "text" in part:
                    content_blocks.append({"type": "text", "text": part["text"]})
                elif "functionCall" in part:
                    fc = part["functionCall"]
                    content_blocks.append({
                        "type": "tool_use",
                        "id": f"gemini_{fc['name']}_{id(fc)}",
                        "name": fc["name"],
                        "input": fc.get("args", {}),
                    })
            
            if not content_blocks:
                # Fallback: check for blocked or empty response
                block_reason = candidate.get("finishReason", "")
                if block_reason == "SAFETY":
                    content_blocks = [{"type": "text", "text": "Response blocked by safety filters. Try rephrasing your request."}]
                else:
                    content_blocks = [{"type": "text", "text": "No response generated. Try again."}]
            
            return {"content": content_blocks}
    
    async def _execute_tool(self, name: str, params: Dict, drive_token: str = None, folder_id: str = None) -> Any:
        """Execute a tool and return results. Uses per-tool model routing."""
        from tools.search_pubmed import search_pubmed
        from tools.search_scopus import search_scopus
        from tools.drive_ops import DriveOps
        
        # Get the model assigned to this tool (fall back to default)
        tool_model = self._tool_models.get(name) or self._tool_models.get("chat") or self.default_model
        # Map drive-related tools to their shared key
        if name.startswith("drive_"): tool_model = self._tool_models.get("drive_ops") or tool_model
        
        try:
            if name == "search_pubmed":
                return await search_pubmed(params.get("query", ""), params.get("max_results", 15))
            
            elif name == "search_scopus":
                scopus_key = os.getenv("SCOPUS_API_KEY", "")
                return await search_scopus(params.get("query", ""), scopus_key, params.get("max_results", 10))
            
            elif name == "generate_mesh_terms":
                return await self.generate_mesh_terms(params.get("topic", ""))
            
            elif name == "drive_list_folders":
                if not drive_token: return {"error": "Drive not connected"}
                drive = DriveOps(drive_token)
                return await drive.list_folders(params.get("query", ""))
            
            elif name == "drive_list_files":
                if not drive_token: return {"error": "Drive not connected"}
                drive = DriveOps(drive_token)
                return await drive.list_files(params.get("folder_id"))
            
            elif name == "drive_read_file":
                if not drive_token: return {"error": "Drive not connected"}
                drive = DriveOps(drive_token)
                return await drive.read_file(params.get("file_id"))
            
            elif name == "drive_create_folder":
                if not drive_token: return {"error": "Drive not connected"}
                drive = DriveOps(drive_token)
                return await drive.create_folder(params.get("name"), params.get("parent_id") or folder_id)
            
            elif name == "write_literature_review":
                from tools.academic_write import write_literature_review
                return await write_literature_review(
                    self, params.get("topic", ""), params.get("papers", []),
                    instructions=params.get("instructions", ""), model=tool_model
                )
            
            elif name == "write_section":
                from tools.academic_write import write_results, write_discussion
                section = params.get("section", "results")
                topic = params.get("topic", "")
                context = params.get("context", "")
                instructions = params.get("instructions", "")
                if section == "results":
                    return await write_results(self, topic, context, instructions)
                elif section == "discussion":
                    return await write_discussion(self, topic, context, instructions)
                else:
                    return await self._write_generic_section(section, topic, context, instructions)
            
            elif name == "create_google_doc":
                if not drive_token: return {"error": "Drive not connected"}
                from tools.create_doc import create_google_doc
                drive = DriveOps(drive_token)
                return await create_google_doc(drive, params.get("name", "Document"), params.get("content", ""), params.get("folder_id") or folder_id)
            
            elif name == "create_google_sheet":
                if not drive_token: return {"error": "Drive not connected"}
                from tools.create_sheet import create_google_sheet
                drive = DriveOps(drive_token)
                return await create_google_sheet(drive, params.get("name", "Data"), params.get("data", ""), params.get("folder_id") or folder_id)
            
            elif name == "create_google_slides":
                if not drive_token: return {"error": "Drive not connected"}
                from tools.create_slides import create_google_slides
                drive = DriveOps(drive_token)
                return await create_google_slides(drive, params.get("name", "Presentation"), params.get("content", ""), params.get("folder_id") or folder_id)
            
            elif name == "generate_colab_notebook":
                from tools.notebook_gen import generate_notebook
                return await generate_notebook(self, params.get("query", ""), params.get("data_files", []), params.get("code_files", []), params.get("drive_path", ""))
            
            elif name == "fetch_site_documents":
                from tools.site_fetch import search_site_documents
                return await search_site_documents(self, params.get("query", ""), params.get("sites"))
            
            elif name == "query_site_info":
                from tools.site_fetch import fetch_site_info
                return await fetch_site_info(params.get("sites", []))
            
            elif name == "understand_code":
                from tools.code_analysis import understand_code
                return await understand_code(self, params.get("code_files", []), params.get("data_files", []), params.get("query", ""), model=tool_model)
            
            elif name == "design_pipeline":
                from tools.code_analysis import design_pipeline, get_signal_config
                sig = get_signal_config(params.get("signal_types"), params.get("custom_signal", ""))
                return await design_pipeline(self, params.get("query", ""), sig, params.get("data_files", []), params.get("code_analysis", ""), model=tool_model)
            
            elif name == "download_papers":
                if not drive_token: return {"error": "Drive not connected — cannot download papers"}
                from tools.paper_download import download_papers_to_drive
                drive = DriveOps(drive_token)
                target_folder = params.get("folder_id") or folder_id
                if not target_folder: return {"error": "No working folder selected — select a folder first"}
                
                # Enrich AI's paper objects with full data from session context
                # (AI often passes minimal objects like {title, pmid} — we need authors, abstract, pdf_url)
                ai_papers = params.get("papers", [])
                ctx_papers = self._session_context.get(session_id, {}).get("papers", [])
                ctx_by_pmid = {p.get("pmid"): p for p in ctx_papers if p.get("pmid")}
                ctx_by_title = {p.get("title", "").lower()[:50]: p for p in ctx_papers}
                
                enriched = []
                for ap in ai_papers:
                    # Try to find the full paper in session context
                    full = ctx_by_pmid.get(ap.get("pmid")) or ctx_by_title.get(ap.get("title", "").lower()[:50])
                    if full:
                        # Merge: use session context data, but let AI overrides win
                        merged = {**full}
                        for k, v in ap.items():
                            if v and v != "Unknown" and v != "":
                                merged[k] = v
                        enriched.append(merged)
                    else:
                        enriched.append(ap)
                
                return await download_papers_to_drive(drive, enriched, target_folder)
            
            elif name == "get_paper_full_text":
                from tools.paper_download import get_paper_full_text
                drive_obj = DriveOps(drive_token) if drive_token else None
                papers = params.get("papers", [])
                # Enrich with session context data
                ctx_papers = self._session_context.get(session_id, {}).get("papers", [])
                ctx_by_pmid = {p.get("pmid"): p for p in ctx_papers if p.get("pmid")}
                enriched = []
                for p in papers[:10]:
                    full = ctx_by_pmid.get(p.get("pmid"))
                    enriched.append({**(full or {}), **{k:v for k,v in p.items() if v}})
                results = []
                for p in enriched:
                    ft = await get_paper_full_text(drive_obj, p)
                    results.append(ft)
                    await asyncio.sleep(1)
                return results
            
            else:
                return {"error": f"Unknown tool: {name}"}
        
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}
    
    async def generate_mesh_terms(self, topic: str) -> Dict:
        """Use AI to generate MeSH terms for PubMed search"""
        messages = [{"role": "user", "content": f"Generate PubMed MeSH search queries for: {topic}\n\nReturn ONLY JSON: {{\"mesh_terms\":[],\"queries\":[\"query1\",\"query2\",\"query3\"]}}"}]
        system = "You are a PubMed search expert. Generate 3 queries from most specific (MeSH terms) to broadest. Return ONLY valid JSON."
        result = await self._call_ai(system, messages, self.default_model, use_tools=False)
        text = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text")
        try:
            return json.loads(text.replace("```json", "").replace("```", "").strip())
        except:
            return {"mesh_terms": [topic], "queries": [topic]}
    
    async def _write_generic_section(self, section: str, topic: str, context: str, instructions: str) -> Dict:
        """Write any section of a paper"""
        messages = [{"role": "user", "content": f"Write the {section} section for a paper on: {topic}\n\nContext:\n{context[:3000]}\n\nInstructions: {instructions}"}]
        system = f"You are an expert academic writer. Write a thorough {section} section. Use formal academic tone."
        result = await self._call_ai(system, messages, self.default_model, use_tools=False)
        text = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text")
        return {"section": section, "content": text}
