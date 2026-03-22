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
        "description": "Download full-text PDFs of papers to the user's Google Drive folder. Uses PubMed Central, Unpaywall, and Europe PMC to find open-access versions. Has 4-second delay between downloads to avoid rate limiting. Papers that are NOT open-access are automatically saved to a separate Google Doc 'Papers_Without_Open_Access' with their titles, abstracts, and citations.",
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
    {
        "name": "search_and_download",
        "description": "ALL-IN-ONE: Search Europe PMC for papers AND download open-access PDFs in one step. This is the PREFERRED tool when user asks to search and download papers. It searches Europe PMC (which has the best open-access coverage), finds PDF URLs from fullTextUrlList, downloads them to Drive with retry logic, and creates a Compiled_Abstracts doc for non-downloadable papers. Use this instead of separate search_pubmed + download_papers calls.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for academic papers"},
                "folder_id": {"type": "string", "description": "Drive folder ID to save papers in"},
                "min_papers": {"type": "integer", "description": "Minimum number of papers to try to download (default 10)"}
            },
            "required": ["query"]
        }
    },
]

SYSTEM_PROMPT = """You are ResearchAgent — an AI research assistant that helps academics with literature search, paper writing, data analysis, and document creation.

You have access to these tools:
- search_pubmed: Search PubMed for papers (free, no key needed)
- search_scopus: Search Scopus for papers (needs API key)
- generate_mesh_terms: Generate optimized MeSH search terms from a topic
- download_papers: DOWNLOAD full-text PDFs from PubMed Central, Unpaywall, Europe PMC. Saves PDFs to user's Google Drive folder. USE THIS when user asks to download papers.
- search_and_download: ALL-IN-ONE tool — searches Europe PMC AND downloads open-access PDFs in one step. THIS IS THE PREFERRED TOOL when user asks to "search and download papers" or "find and download papers". Creates Compiled_Abstracts doc for non-downloadable papers.
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

CRITICAL WORKFLOW — When user asks to search AND download papers:
PREFERRED: Use search_and_download tool (does everything in one call)
OR step by step:
1. generate_mesh_terms → get MeSH terms for the topic
2. search_pubmed → find papers
3. PRESENT papers to user → let them select
4. download_papers → download selected papers
5. get_paper_full_text → read actual content
6. write_literature_review → write review using REAL paper content
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
        "search_and_download": lambda i: f"Searching & downloading papers for: \"{i.get('query','')[:50]}\"",
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
        # Auto-select default model based on available keys
        configured = os.getenv("DEFAULT_MODEL", "")
        if configured:
            self.default_model = configured
        elif self.anthropic_key:
            self.default_model = "claude-sonnet-4-20250514"
        elif self.google_key:
            self.default_model = "gemini-2.5-flash"
        else:
            self.default_model = "gemini-2.5-flash"
    
    async def chat(self, messages: List[Dict], session_id: str = "", model: str = None,
                   tool_models: Dict[str, str] = None, drive_token: str = None, working_folder_id: str = None,
                   selected_files: List[Dict] = None, event_queue=None) -> Dict:
        """
        Main chat loop with tool calling.
        Uses per-tool model routing when tool_models is provided.
        """
        model = model or self.default_model
        self._tool_models = tool_models or {}  # Store for use in _execute_tool
        
        # Add working folder context if set
        system = SYSTEM_PROMPT
        if working_folder_id:
            system += f"\n\nThe user has selected a working folder (Drive ID: {working_folder_id}). Use this folder_id for all file operations unless they specify otherwise."
        
        # Add selected files context
        if selected_files:
            file_list = "\n".join(f"- {f.get('name','')} ({f.get('cat','')}, {f.get('ext','')})" for f in selected_files)
            file_ids = ", ".join(f.get('id','') for f in selected_files)
            system += f"\n\nThe user has selected {len(selected_files)} specific files to work with:\n{file_list}\n\nFile IDs: {file_ids}\n\nWhen the user refers to 'my files', 'these files', 'selected files', or asks to analyze/review/process files, use THESE specific files. You can read them with drive_read_file using their IDs. For code files, use understand_code. For data files, use design_pipeline. For document files (.pdf, .docx, .txt), read their content for reviews."
        
        # Convert messages to API format
        api_messages = []
        for m in messages:
            if m["role"] in ("user", "assistant"):
                api_messages.append({"role": m["role"], "content": m["content"]})
        
        tool_results = []
        max_loops = 10  # prevent infinite tool loops
        
        for loop in range(max_loops):
            # Emit: thinking
            if event_queue:
                await event_queue.put({"type": "status", "data": {"step": "thinking", "message": f"AI is analyzing your request (loop {loop+1})...", "model": model}})
            
            # Call AI
            response = await self._call_ai(system, api_messages, model, use_tools=True)
            
            if not response:
                return {"message": "Error: No response from AI", "tool_results": tool_results}
            
            # Check if AI wants to use a tool
            tool_uses = [b for b in response.get("content", []) if b.get("type") == "tool_use"]
            text_blocks = [b.get("text", "") for b in response.get("content", []) if b.get("type") == "text"]
            
            if not tool_uses:
                final_text = "\n".join(text_blocks)
                if event_queue:
                    await event_queue.put({"type": "done", "data": {"message": final_text, "tool_results": tool_results}})
                return {"message": final_text, "tool_results": tool_results}
            
            # Execute each tool call
            tool_call_results = []
            for tool_use in tool_uses:
                tool_name = tool_use["name"]
                tool_input = tool_use["input"]
                tool_id = tool_use["id"]
                
                # Get per-tool model
                tool_model = self._tool_models.get(tool_name) or self._tool_models.get("chat") or self.default_model
                if tool_name.startswith("drive_"): tool_model = self._tool_models.get("drive_ops") or tool_model
                model_info = tool_model.split("-")
                model_short = tool_model
                
                # Emit: tool starting
                if event_queue:
                    await event_queue.put({"type": "tool_start", "data": {
                        "tool": tool_name, "model": tool_model,
                        "input_summary": _summarize_input(tool_name, tool_input),
                        "message": f"Running {tool_name}..."
                    }})
                
                # Execute the tool
                import time
                t0 = time.time()
                result = await self._execute_tool(tool_name, tool_input, drive_token, working_folder_id)
                elapsed = round(time.time() - t0, 1)
                
                tool_results.append({"tool": tool_name, "input": tool_input, "result": result, "model": tool_model, "time": elapsed})
                
                # Emit: tool done
                if event_queue:
                    await event_queue.put({"type": "tool_done", "data": {
                        "tool": tool_name, "model": tool_model, "time": elapsed,
                        "result_summary": _summarize_result(tool_name, result),
                    }})
                
                tool_call_results.append({
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": json.dumps(result) if isinstance(result, (dict, list)) else str(result)
                })
            
            # Add assistant response + tool results to conversation
            api_messages.append({"role": "assistant", "content": response["content"]})
            api_messages.append({"role": "user", "content": tool_call_results})
        
        return {"message": "Reached maximum tool call limit. Please continue the conversation.", "tool_results": tool_results}
    
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
                return await write_literature_review(
                    self, params.get("topic", ""), params.get("papers", []),
                    instructions=params.get("instructions", ""), model=tool_model
                )
            
            elif name == "write_section":
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
                return await download_papers_to_drive(drive, params.get("papers", []), target_folder)
            
            elif name == "search_and_download":
                if not drive_token: return {"error": "Drive not connected"}
                from tools.paper_download import search_and_download
                drive = DriveOps(drive_token)
                target_folder = params.get("folder_id") or folder_id
                if not target_folder: return {"error": "No working folder selected"}
                return await search_and_download(drive, params.get("query", ""), target_folder, params.get("min_papers", 10))
            
            elif name == "get_paper_full_text":
                from tools.paper_download import get_paper_full_text
                drive_obj = DriveOps(drive_token) if drive_token else None
                papers = params.get("papers", [])
                results = []
                for p in papers[:10]:
                    ft = await get_paper_full_text(drive_obj, p)
                    results.append(ft)
                    await asyncio.sleep(1)  # Gentle delay
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
