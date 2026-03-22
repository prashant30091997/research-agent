import { useState, useEffect, useRef, useCallback } from "react";

// ═══════════════════════════════════════════════════════════════
// ResearchAgent v5.0 — Conversational Chat Frontend
// ═══════════════════════════════════════════════════════════════

const BACKEND = localStorage.getItem("ra_backend_url") || "http://localhost:8000";

export default function App() {
  // ── Chat State ──
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState("");
  const chatEndRef = useRef(null);

  // ── Settings ──
  const [showSettings, setShowSettings] = useState(false);
  const [backendUrl, setBackendUrl] = useState(BACKEND);
  const [driveToken, setDriveToken] = useState("");
  const [driveConnected, setDriveConnected] = useState(false);
  const [workingFolder, setWorkingFolder] = useState(null);

  // Available models
  const MODELS = [
    { id: "claude-opus-4-6", name: "Opus 4.6", full: "Claude Opus 4.6", icon: "◆", color: "#a78bfa", tier: "Flagship", provider: "Anthropic" },
    { id: "claude-sonnet-4-20250514", name: "Sonnet 4", full: "Claude Sonnet 4", icon: "●", color: "#34d399", tier: "Balanced", provider: "Anthropic" },
    { id: "claude-haiku-4-5-20251001", name: "Haiku 4.5", full: "Claude Haiku 4.5", icon: "▲", color: "#60a5fa", tier: "Fast", provider: "Anthropic" },
    { id: "gemini-3.1-pro-preview", name: "Gem 3.1 Pro", full: "Gemini 3.1 Pro", icon: "◇", color: "#4285F4", tier: "Flagship", provider: "Google" },
    { id: "gemini-3-flash-preview", name: "Gem 3 Flash", full: "Gemini 3 Flash", icon: "◇", color: "#EA4335", tier: "Balanced", provider: "Google" },
    { id: "gemini-2.5-flash", name: "Gem 2.5 Flash", full: "Gemini 2.5 Flash", icon: "◇", color: "#FBBC04", tier: "Fast", provider: "Google" },
    { id: "gemini-2.5-flash-lite", name: "Gem 2.5 Lite", full: "Gemini 2.5 Flash Lite", icon: "◇", color: "#FBBC04", tier: "Budget", provider: "Google" },
    { id: "gemini-3.1-flash-lite-preview", name: "Gem 3.1 Lite", full: "Gemini 3.1 Flash Lite", icon: "◇", color: "#34A853", tier: "Cheapest", provider: "Google" },
  ];

  // ── PER-TOOL MODEL ROUTING ──
  const TOOL_LIST = [
    { key: "chat", label: "💬 Chat / General", desc: "Default model for conversation" },
    { key: "search_pubmed", label: "🔬 PubMed Search", desc: "MeSH terms + paper search" },
    { key: "search_scopus", label: "🔬 Scopus Search", desc: "Elsevier database search" },
    { key: "download_papers", label: "⬇️ Download Papers", desc: "Download open-access PDFs via Europe PMC" },
    { key: "get_paper_full_text", label: "📖 Read Full Text", desc: "Extract full text from papers" },
    { key: "write_literature_review", label: "📝 Literature Review", desc: "Write comprehensive review" },
    { key: "write_section", label: "✍️ Write Section", desc: "Results, discussion, methodology" },
    { key: "understand_code", label: "🧠 Understand Code", desc: "Analyze .py files and pipeline" },
    { key: "design_pipeline", label: "🏗️ Design Pipeline", desc: "Design analysis pipeline" },
    { key: "create_google_doc", label: "📄 Google Doc", desc: "Create document in Drive" },
    { key: "create_google_sheet", label: "📊 Google Sheet", desc: "Create spreadsheet in Drive" },
    { key: "create_google_slides", label: "📑 Google Slides", desc: "Create presentation in Drive" },
    { key: "generate_colab_notebook", label: "📓 Colab Notebook", desc: "Generate analysis notebook" },
    { key: "fetch_site_documents", label: "🌐 Site Documents", desc: "ICMR/WHO/NIH documents" },
    { key: "drive_ops", label: "📁 Drive Operations", desc: "List folders, files, create folders" },
  ];

  const DEFAULT_TOOL_MODELS = {
    chat: "gemini-2.5-flash",
    search_pubmed: "gemini-2.5-flash",
    search_scopus: "gemini-2.5-flash",
    download_papers: "gemini-2.5-flash-lite",
    get_paper_full_text: "gemini-2.5-flash-lite",
    write_literature_review: "gemini-3.1-pro-preview",
    write_section: "gemini-3.1-pro-preview",
    understand_code: "gemini-3.1-pro-preview",
    design_pipeline: "gemini-3.1-pro-preview",
    create_google_doc: "gemini-2.5-flash",
    create_google_sheet: "gemini-2.5-flash",
    create_google_slides: "gemini-2.5-flash",
    generate_colab_notebook: "gemini-2.5-flash",
    fetch_site_documents: "gemini-2.5-flash",
    drive_ops: "gemini-2.5-flash-lite",
  };

  const [toolModels, setToolModels] = useState(() => {
    try {
      const cached = JSON.parse(localStorage.getItem("ra_tool_models"));
      // Reset if cached models contain old wrong IDs
      if (cached && JSON.stringify(cached).includes("gemini-3.1-pro\"")) {
        localStorage.removeItem("ra_tool_models");
        return DEFAULT_TOOL_MODELS;
      }
      return cached || DEFAULT_TOOL_MODELS;
    }
    catch { return DEFAULT_TOOL_MODELS; }
  });

  // ── READER PANEL (full response viewer) ──
  const [readerOpen, setReaderOpen] = useState(false);
  const [readerIndex, setReaderIndex] = useState(-1);

  // ── TOOL ACTIVITY PANEL ──
  const [toolActivity, setToolActivity] = useState([]); // [{tool, status, model, message, time, result_summary}]
  const [showActivity, setShowActivity] = useState(true); // visible by default during execution // index in messages array

  // ── FILE PICKER (choose files from working folder) ──
  const [showFilePicker, setShowFilePicker] = useState(false);
  const [pickerFiles, setPickerFiles] = useState([]); // all files in working folder
  const [selectedFiles, setSelectedFiles] = useState([]); // chosen files [{id, name, ext, cat, size_str}]
  const [fileSearch, setFileSearch] = useState("");
  const [pickerLoading, setPickerLoading] = useState(false);

  const assistantMessages = messages.filter(m => m.role === "assistant");
  const readerMsg = readerIndex >= 0 && readerIndex < assistantMessages.length ? assistantMessages[readerIndex] : null;

  const readerPrev = () => setReaderIndex(i => Math.max(0, i - 1));
  const readerNext = () => setReaderIndex(i => Math.min(assistantMessages.length - 1, i + 1));
  const openReader = (msgIndex) => {
    const aiIdx = assistantMessages.indexOf(messages[msgIndex]);
    if (aiIdx >= 0) { setReaderIndex(aiIdx); setReaderOpen(true); }
  };

  // Summary: first 200 chars of assistant response
  const summarize = (content) => {
    if (!content) return "";
    const clean = content.replace(/[#*_`>]/g, "").trim();
    return clean.length > 200 ? clean.slice(0, 200) + "..." : clean;
  };

  // ── Sidebar ──
  const [showHistory, setShowHistory] = useState(false);
  const [sessions, setSessions] = useState([]);
  const [historyFolder, setHistoryFolder] = useState(() => {
    try { return JSON.parse(localStorage.getItem("ra_history_folder")); } catch { return null; }
  });
  const [showHistoryFolderPicker, setShowHistoryFolderPicker] = useState(false);
  const [historyFolders, setHistoryFolders] = useState([]);
  const [historySearch, setHistorySearch] = useState("");
  const [sessionFolderIds, setSessionFolderIds] = useState({});  // sessionId → Drive folder ID
  const [sessionFileIds, setSessionFileIds] = useState({});       // sessionId → session.json file ID

  // ── Drive Browser ──
  const [showDrive, setShowDrive] = useState(false);
  const [driveFolders, setDriveFolders] = useState([]);
  const [driveFiles, setDriveFiles] = useState([]);
  const [drivePath, setDrivePath] = useState([{ id: "root", name: "My Drive" }]);
  const [driveLoading, setDriveLoading] = useState(false);
  const [driveSearch, setDriveSearch] = useState("");
  const [newFolderName, setNewFolderName] = useState("");

  // ── Google Identity Services ──
  const [gisReady, setGisReady] = useState(false);

  useEffect(() => {
    const s = document.createElement("script");
    s.src = "https://accounts.google.com/gsi/client";
    s.onload = () => setGisReady(true);
    document.head.appendChild(s);
    // Create initial session
    createSession();
    // Load session history from backend
    fetch(`${backendUrl}/api/session/list`).then(r => r.json()).then(d => setSessions(d.sessions || [])).catch(() => {});
  }, []);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // Reload sessions whenever Drive token changes (user connects Drive)
  useEffect(() => { if (driveToken) loadSessions(); }, [driveToken]);

  // ── API Helpers ──
  const api = async (path, body = {}) => {
    const r = await fetch(`${backendUrl}${path}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return r.json();
  };

  const createSession = async () => {
    try {
      const r = await api("/api/session/new");
      setSessionId(r.session_id);
      setMessages([]);
    } catch { setSessionId(`local_${Date.now()}`); }
  };

  // ── Send Message (with SSE streaming for live tool activity) ──
  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    const userMsg = { role: "user", content: input.trim() };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setIsLoading(true);
    setToolActivity([]);
    setShowActivity(true);

    try {
      const response = await fetch(`${backendUrl}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          messages: newMessages.map(m => ({ role: m.role, content: m.content })),
          model: toolModels.chat,
          tool_models: toolModels,
          drive_token: driveToken,
          working_folder_id: workingFolder?.id,
          selected_files: selectedFiles.map(f => ({ id: f.id, name: f.name, ext: f.ext, cat: f.cat })),
        }),
      });

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let finalResult = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const event = JSON.parse(line.slice(6));

              if (event.type === "status") {
                setToolActivity(prev => [...prev, {
                  tool: "ai_thinking", status: "running", model: event.data.model,
                  message: event.data.message, time: null, icon: "🧠",
                }]);
              } else if (event.type === "tool_start") {
                setToolActivity(prev => {
                  // Mark previous thinking as done
                  const updated = prev.map(a => a.tool === "ai_thinking" && a.status === "running" ? { ...a, status: "done" } : a);
                  return [...updated, {
                    tool: event.data.tool, status: "running", model: event.data.model,
                    message: event.data.input_summary || event.data.message,
                    time: null, icon: TOOL_ICONS[event.data.tool] || "⚙️",
                  }];
                });
              } else if (event.type === "tool_done") {
                setToolActivity(prev => prev.map(a =>
                  a.tool === event.data.tool && a.status === "running"
                    ? { ...a, status: "done", time: event.data.time, result_summary: event.data.result_summary }
                    : a
                ));
              } else if (event.type === "done") {
                finalResult = event.data;
              } else if (event.type === "error") {
                finalResult = { message: `⚠️ Error: ${event.data.message}`, tool_results: [] };
              }
            } catch { }
          }
        }
      }

      // If SSE completed with final result
      if (finalResult) {
        setMessages(prev => [...prev, {
          role: "assistant", content: finalResult.message || "No response",
          tool_results: finalResult.tool_results || [],
        }]);
      } else {
        // Fallback: try regular endpoint
        const result = await api("/api/chat", {
          session_id: sessionId,
          messages: newMessages.map(m => ({ role: m.role, content: m.content })),
          model: toolModels.chat, tool_models: toolModels,
          drive_token: driveToken, working_folder_id: workingFolder?.id,
          selected_files: selectedFiles.map(f => ({ id: f.id, name: f.name, ext: f.ext, cat: f.cat })),
        });
        setMessages(prev => [...prev, { role: "assistant", content: result.message || "No response", tool_results: result.tool_results || [] }]);
      }
    } catch (e) {
      // Full fallback to non-streaming
      try {
        const result = await api("/api/chat", {
          session_id: sessionId,
          messages: newMessages.map(m => ({ role: m.role, content: m.content })),
          model: toolModels.chat, tool_models: toolModels,
          drive_token: driveToken, working_folder_id: workingFolder?.id,
          selected_files: selectedFiles.map(f => ({ id: f.id, name: f.name, ext: f.ext, cat: f.cat })),
        });
        setMessages(prev => [...prev, { role: "assistant", content: result.message || "No response", tool_results: result.tool_results || [] }]);
      } catch (e2) {
        setMessages(prev => [...prev, { role: "assistant", content: `⚠️ Error: ${e2.message}\n\nBackend: ${backendUrl}` }]);
      }
    }
    setIsLoading(false);
    setToolActivity(prev => prev.map(a => ({ ...a, status: "done" })));
    // Auto-save session to Drive directly from frontend (bypasses backend — works after Colab restart)
    saveSessionToDrive();
    // Refresh history
    loadSessions();
  };

  // ── SAVE SESSION DIRECTLY TO DRIVE (not through backend) ──
  const saveSessionToDrive = async () => {
    if (!driveToken || !historyFolder?.id || messages.length === 0) return;
    try {
      // Build session data
      const firstUserMsg = messages.find(m => m.role === "user");
      const title = firstUserMsg ? firstUserMsg.content.slice(0, 80) : "Untitled";
      const sessionData = {
        id: sessionId,
        title: title,
        created: Date.now() / 1000,
        created_str: new Date().toLocaleString(),
        updated_str: new Date().toLocaleString(),
        messages: messages,
        metadata: {},
      };
      const sessionJson = JSON.stringify(sessionData, null, 2);

      // Check if session folder already exists
      const existingFolderId = sessionFolderIds[sessionId];
      const existingFileId = sessionFileIds[sessionId];

      if (existingFileId) {
        // UPDATE existing session.json
        const boundary = "----RAses" + Date.now();
        const body = `--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{}\r\n--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${sessionJson}\r\n--${boundary}--`;
        await fetch(`https://www.googleapis.com/upload/drive/v3/files/${existingFileId}?uploadType=multipart`, {
          method: "PATCH",
          headers: { "Authorization": `Bearer ${driveToken}`, "Content-Type": `multipart/related; boundary=${boundary}` },
          body: body,
        });
      } else {
        // CREATE new session folder + session.json
        const safeTitle = title.replace(/[^a-zA-Z0-9 _-]/g, "").slice(0, 40).trim();
        const dateStr = new Date().toISOString().slice(0, 10);
        const folderName = `${safeTitle}_${dateStr}`;

        // Create folder
        const fr = await fetch("https://www.googleapis.com/drive/v3/files", {
          method: "POST",
          headers: { "Authorization": `Bearer ${driveToken}`, "Content-Type": "application/json" },
          body: JSON.stringify({ name: folderName, mimeType: "application/vnd.google-apps.folder", parents: [historyFolder.id] }),
        });
        const folder = await fr.json();
        if (!folder.id) return;

        // Upload session.json inside folder
        const boundary = "----RAses" + Date.now();
        const metadata = JSON.stringify({ name: "session.json", parents: [folder.id] });
        const body = `--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${metadata}\r\n--${boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n${sessionJson}\r\n--${boundary}--`;
        const ur = await fetch("https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart", {
          method: "POST",
          headers: { "Authorization": `Bearer ${driveToken}`, "Content-Type": `multipart/related; boundary=${boundary}` },
          body: body,
        });
        const uploaded = await ur.json();
        if (uploaded.id) {
          setSessionFolderIds(prev => ({ ...prev, [sessionId]: folder.id }));
          setSessionFileIds(prev => ({ ...prev, [sessionId]: uploaded.id }));
        }
      }
    } catch (e) { console.error("Drive save error:", e); }
  };

  const TOOL_ICONS = {
    search_pubmed: "🔬", search_scopus: "🔬", generate_mesh_terms: "🧬",
    download_papers: "⬇️", get_paper_full_text: "📖",
    drive_list_folders: "📁", drive_list_files: "📂", drive_read_file: "📄", drive_create_folder: "📁",
    write_literature_review: "📝", write_section: "✍️",
    understand_code: "🧠", design_pipeline: "🏗️",
    create_google_doc: "📄", create_google_sheet: "📊", create_google_slides: "📑",
    generate_colab_notebook: "📓",
    fetch_site_documents: "🌐", query_site_info: "🔎",
    ai_thinking: "🧠",
  };

  // ── Google Drive Connection ──
  const connectDrive = () => {
    if (!gisReady) { alert("Google APIs loading..."); return; }
    const clientId = localStorage.getItem("ra_google_client_id") || "YOUR_CLIENT_ID.apps.googleusercontent.com";
    const tc = window.google.accounts.oauth2.initTokenClient({
      client_id: clientId,
      scope: "https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/drive.file",
      callback: (r) => {
        if (r.access_token) { setDriveToken(r.access_token); setDriveConnected(true); }
      },
    });
    tc.requestAccessToken();
  };

  // ── Drive Browser Functions ──
  const browseDrive = async (folderId = "root") => {
    if (!driveToken) { connectDrive(); return; }
    setDriveLoading(true);
    try {
      let q = `mimeType='application/vnd.google-apps.folder' and trashed=false`;
      q += folderId === "root" ? ` and 'root' in parents` : ` and '${folderId}' in parents`;
      const r = await fetch(`https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(q)}&fields=files(id,name,modifiedTime)&pageSize=50&orderBy=name&supportsAllDrives=true&includeItemsFromAllDrives=true`, {
        headers: { "Authorization": `Bearer ${driveToken}` },
      });
      const d = await r.json();
      setDriveFolders(d.files || []);

      let fq = `mimeType!='application/vnd.google-apps.folder' and trashed=false`;
      fq += folderId === "root" ? ` and 'root' in parents` : ` and '${folderId}' in parents`;
      const fr = await fetch(`https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(fq)}&fields=files(id,name,size,mimeType)&pageSize=50&orderBy=name&supportsAllDrives=true&includeItemsFromAllDrives=true`, {
        headers: { "Authorization": `Bearer ${driveToken}` },
      });
      const fd = await fr.json();
      setDriveFiles(fd.files || []);
    } catch (e) { console.error(e); }
    setDriveLoading(false);
  };

  const navigateInto = (folder) => {
    setDrivePath(prev => [...prev, { id: folder.id, name: folder.name }]);
    browseDrive(folder.id);
  };

  const navigateTo = (index) => {
    setDrivePath(prev => prev.slice(0, index + 1));
    browseDrive(drivePath[index].id);
  };

  const selectFolder = (folder) => {
    setWorkingFolder(folder);
    setShowDrive(false);
  };

  const searchDrive = async () => {
    if (!driveSearch.trim() || !driveToken) return;
    setDriveLoading(true);
    try {
      const q = `mimeType='application/vnd.google-apps.folder' and name contains '${driveSearch}' and trashed=false`;
      const r = await fetch(`https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(q)}&fields=files(id,name,modifiedTime)&pageSize=30&supportsAllDrives=true&includeItemsFromAllDrives=true&corpora=allDrives`, {
        headers: { "Authorization": `Bearer ${driveToken}` },
      });
      const d = await r.json();
      setDriveFolders(d.files || []);
      setDriveFiles([]);
    } catch (e) { console.error(e); }
    setDriveLoading(false);
  };

  const createFolder = async () => {
    if (!newFolderName.trim() || !driveToken) return;
    const parentId = drivePath[drivePath.length - 1]?.id;
    const metadata = { name: newFolderName, mimeType: "application/vnd.google-apps.folder" };
    if (parentId && parentId !== "root") metadata.parents = [parentId];
    await fetch("https://www.googleapis.com/drive/v3/files", {
      method: "POST", headers: { "Authorization": `Bearer ${driveToken}`, "Content-Type": "application/json" },
      body: JSON.stringify(metadata),
    });
    setNewFolderName("");
    browseDrive(parentId);
  };

  // ── FILE PICKER FUNCTIONS ──
  const openFilePicker = async () => {
    if (!driveToken || !workingFolder?.id) { alert("Select a working folder first"); return; }
    setShowFilePicker(true);
    setPickerLoading(true);
    setFileSearch("");
    try {
      const q = `'${workingFolder.id}' in parents and trashed=false`;
      const r = await fetch(`https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(q)}&fields=files(id,name,mimeType,size)&pageSize=100&orderBy=name&supportsAllDrives=true&includeItemsFromAllDrives=true`, {
        headers: { "Authorization": `Bearer ${driveToken}` },
      });
      const d = await r.json();
      const files = (d.files || []).map(f => {
        const ext = f.name.includes(".") ? "." + f.name.rsplit ? f.name.split(".").pop().toLowerCase() : "" : "";
        const cat = [".py",".ipynb",".m",".r",".js",".sh",".sql"].includes("." + ext) ? "code" :
                    [".mat",".csv",".xlsx",".json",".hdf5",".npy",".edf",".parquet",".tsv",".pkl"].includes("." + ext) ? "data" :
                    [".pdf",".docx",".txt",".md",".pptx"].includes("." + ext) ? "doc" : "other";
        return { id: f.id, name: f.name, ext: "." + ext, cat, size: parseInt(f.size || 0), size_str: f.size ? `${(parseInt(f.size)/1024).toFixed(0)} KB` : "", mime: f.mimeType || "" };
      });
      setPickerFiles(files);
    } catch (e) { console.error(e); }
    setPickerLoading(false);
  };

  const searchFilesInDrive = async () => {
    if (!driveToken || !fileSearch.trim()) return;
    setPickerLoading(true);
    try {
      const q = `name contains '${fileSearch}' and '${workingFolder?.id || "root"}' in parents and trashed=false`;
      const r = await fetch(`https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(q)}&fields=files(id,name,mimeType,size)&pageSize=50&supportsAllDrives=true&includeItemsFromAllDrives=true`, {
        headers: { "Authorization": `Bearer ${driveToken}` },
      });
      const d = await r.json();
      setPickerFiles((d.files || []).map(f => {
        const ext = f.name.includes(".") ? f.name.split(".").pop().toLowerCase() : "";
        const cat = [".py",".ipynb",".m",".r"].includes("." + ext) ? "code" : [".mat",".csv",".xlsx",".json",".hdf5",".npy",".edf"].includes("." + ext) ? "data" : [".pdf",".docx",".txt",".md"].includes("." + ext) ? "doc" : "other";
        return { id: f.id, name: f.name, ext: "." + ext, cat, size: parseInt(f.size || 0), size_str: f.size ? `${(parseInt(f.size)/1024).toFixed(0)} KB` : "", mime: f.mimeType || "" };
      }));
    } catch (e) { console.error(e); }
    setPickerLoading(false);
  };

  const toggleFileSelect = (file) => {
    setSelectedFiles(prev => {
      const exists = prev.find(f => f.id === file.id);
      if (exists) return prev.filter(f => f.id !== file.id);
      return [...prev, file];
    });
  };

  const isFileSelected = (fileId) => selectedFiles.some(f => f.id === fileId);

  const FILE_CAT_ICONS = { code: "🐍", data: "📊", doc: "📄", other: "📎" };
  const FILE_CAT_COLORS = { code: "#34d399", data: "#60a5fa", doc: "#fbbf24", other: "#8899b0" };

  // ── HISTORY FOLDER BROWSER ──
  const browseHistoryFolders = async (folderId = "root") => {
    if (!driveToken) { connectDrive(); return; }
    try {
      let q = `mimeType='application/vnd.google-apps.folder' and trashed=false`;
      q += folderId === "root" ? ` and 'root' in parents` : ` and '${folderId}' in parents`;
      const r = await fetch(`https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(q)}&fields=files(id,name)&pageSize=50&orderBy=name&supportsAllDrives=true&includeItemsFromAllDrives=true`, {
        headers: { "Authorization": `Bearer ${driveToken}` },
      });
      const d = await r.json();
      setHistoryFolders(d.files || []);
    } catch { }
  };

  const searchHistoryFolders = async () => {
    if (!driveToken || !historySearch.trim()) return;
    try {
      const q = `mimeType='application/vnd.google-apps.folder' and name contains '${historySearch}' and trashed=false`;
      const r = await fetch(`https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(q)}&fields=files(id,name)&pageSize=30&supportsAllDrives=true&includeItemsFromAllDrives=true&corpora=allDrives`, {
        headers: { "Authorization": `Bearer ${driveToken}` },
      });
      const d = await r.json();
      setHistoryFolders(d.files || []);
    } catch { }
  };

  const selectHistoryFolder = (folder) => {
    setHistoryFolder(folder);
    localStorage.setItem("ra_history_folder", JSON.stringify(folder));
    setShowHistoryFolderPicker(false);
    // Load sessions from this folder
    loadSessions();
  };

  // ── Load Sessions ──
  const loadSessions = async () => {
    let allSessions = [];

    // Load sessions from Drive history folder (the PERSISTENT source)
    if (driveToken && historyFolder?.id) {
      try {
        const q = `'${historyFolder.id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false`;
        const r = await fetch(`https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(q)}&fields=files(id,name,createdTime)&pageSize=50&orderBy=createdTime desc&supportsAllDrives=true&includeItemsFromAllDrives=true`, {
          headers: { "Authorization": `Bearer ${driveToken}` },
        });
        const folders = (await r.json()).files || [];

        for (const folder of folders.slice(0, 30)) {
          const fq = `'${folder.id}' in parents and name='session.json' and trashed=false`;
          const fr = await fetch(`https://www.googleapis.com/drive/v3/files?q=${encodeURIComponent(fq)}&fields=files(id)&pageSize=1`, {
            headers: { "Authorization": `Bearer ${driveToken}` },
          });
          const files = (await fr.json()).files || [];
          if (files.length > 0) {
            const fileId = files[0].id;
            try {
              const cr = await fetch(`https://www.googleapis.com/drive/v3/files/${fileId}?alt=media`, {
                headers: { "Authorization": `Bearer ${driveToken}` },
              });
              const session = await cr.json();

              // Extract title from first user message if not set
              let title = session.title || "";
              if (!title && session.messages) {
                const firstUser = session.messages.find(m => m.role === "user");
                if (firstUser) title = firstUser.content.slice(0, 80);
              }
              if (!title) title = folder.name;

              // Track Drive IDs for this session
              setSessionFolderIds(prev => ({ ...prev, [session.id || folder.name]: folder.id }));
              setSessionFileIds(prev => ({ ...prev, [session.id || folder.name]: fileId }));

              allSessions.push({
                id: session.id || folder.name,
                title: title,
                created: session.created || new Date(folder.createdTime).getTime() / 1000,
                created_str: session.created_str || folder.createdTime?.slice(0, 10) || "",
                updated_str: session.updated_str || "",
                message_count: (session.messages || []).length,
                drive_file_id: fileId,
                drive_folder_id: folder.id,
                source: "drive",
              });
            } catch { }
          }
        }
      } catch (e) { console.error("Drive session load error:", e); }
    }

    // Also load local sessions from backend (for current Colab session)
    try {
      const r = await fetch(`${backendUrl}/api/session/list`);
      const d = await r.json();
      const localIds = new Set(allSessions.map(s => s.id));
      for (const s of (d.sessions || [])) {
        if (!localIds.has(s.id)) {
          allSessions.push({ ...s, source: "local" });
        }
      }
    } catch { }

    allSessions.sort((a, b) => (b.created || 0) - (a.created || 0));
    setSessions(allSessions);
  };

  const loadSession = async (session) => {
    try {
      // Always try Drive first (persistent across Colab restarts)
      const fileId = session.drive_file_id || sessionFileIds[session.id];
      if (fileId && driveToken) {
        const r = await fetch(`https://www.googleapis.com/drive/v3/files/${fileId}?alt=media`, {
          headers: { "Authorization": `Bearer ${driveToken}` },
        });
        if (r.ok) {
          const data = await r.json();
          if (data.messages && data.messages.length > 0) {
            setSessionId(data.id || session.id);
            setMessages(data.messages);
            return;
          }
        }
      }
      // Fallback: try backend local
      const data = await api("/api/session/load", { session_id: session.id });
      if (data && data.messages && data.messages.length > 0) {
        setSessionId(data.id || session.id);
        setMessages(data.messages);
      }
    } catch (e) { console.error("Load session error:", e); }
  };

  // ── Render Tool Results Inline ──
  const ToolResult = ({ result }) => {
    const t = result.tool;
    const data = result.result;
    if (!data) return null;

    if ((t === "search_pubmed" || t === "search_scopus") && Array.isArray(data)) {
      return (<div style={{ margin: "8px 0", padding: "10px", borderRadius: "8px", background: "#0f1a2e", border: "1px solid #1e3a5f" }}>
        <div style={{ fontSize: "11px", fontWeight: 700, color: "#60a5fa", marginBottom: "6px" }}>📚 {data.length} papers found ({t === "search_pubmed" ? "PubMed" : "Scopus"})</div>
        {data.slice(0, 8).map((p, i) => (
          <div key={i} style={{ padding: "6px 8px", marginBottom: "3px", borderRadius: "4px", background: "#0a1220", border: "1px solid #1a2a45", fontSize: "11px" }}>
            <div style={{ fontWeight: 600, color: "#e0e8f4", lineHeight: "1.3" }}>{i + 1}. {p.title}</div>
            <div style={{ color: "#8899b0", fontSize: "10px", marginTop: "2px" }}>{p.authors} — {p.journal}, {p.year} {p.pmid && <a href={p.url} target="_blank" rel="noreferrer" style={{ color: "#60a5fa", marginLeft: "6px" }}>PMID:{p.pmid}</a>}</div>
          </div>
        ))}
        {data.length > 8 && <div style={{ fontSize: "10px", color: "#8899b0", marginTop: "4px" }}>+ {data.length - 8} more papers</div>}
      </div>);
    }

    if (t === "create_google_doc" || t === "create_google_sheet" || t === "create_google_slides") {
      const url = data.url;
      const type = t.replace("create_google_", "");
      return (<div style={{ margin: "8px 0", padding: "10px", borderRadius: "8px", background: "#0a1a10", border: "1px solid #1a5f3a" }}>
        <div style={{ fontSize: "11px", fontWeight: 700, color: "#34d399" }}>✅ Google {type.charAt(0).toUpperCase() + type.slice(1)} created</div>
        {url && <a href={url} target="_blank" rel="noreferrer" style={{ color: "#60a5fa", fontSize: "11px", wordBreak: "break-all" }}>📎 {url}</a>}
      </div>);
    }

    if (t === "drive_list_folders" && Array.isArray(data)) {
      return (<div style={{ margin: "8px 0", padding: "8px", borderRadius: "6px", background: "#0f1520", border: "1px solid #1a2540", fontSize: "11px" }}>
        <div style={{ fontWeight: 600, color: "#fbbf24", marginBottom: "4px" }}>📁 {data.length} folders</div>
        {data.map((f, i) => <div key={i} style={{ color: "#8899b0", padding: "2px 0" }}>📁 {f.name}</div>)}
      </div>);
    }

    if (t === "download_papers" && data.summary) {
      return (<div style={{ margin: "8px 0", padding: "10px", borderRadius: "8px", background: "#0f1a20", border: "1px solid #1a4040" }}>
        <div style={{ fontSize: "11px", fontWeight: 700, color: "#22d3ee", marginBottom: "6px" }}>⬇️ Paper Downloads</div>
        <div style={{ fontSize: "11px", color: "#c8d4e0", marginBottom: "4px" }}>{data.summary}</div>
        {(data.downloaded || []).map((p, i) => (
          <div key={i} style={{ fontSize: "10px", color: "#34d399", padding: "2px 0" }}>
            ✅ {p.filename} {p.url && <a href={p.url} target="_blank" rel="noreferrer" style={{ color: "#60a5fa", marginLeft: "4px" }}>Open ↗</a>}
          </div>
        ))}
        {(data.no_access || []).map((p, i) => (
          <div key={i} style={{ fontSize: "10px", color: "#fbbf24", padding: "2px 0" }}>⚠️ No open-access: {p.title?.slice(0, 60)}</div>
        ))}
      </div>);
    }

    if (t === "get_paper_full_text" && Array.isArray(data)) {
      const withText = data.filter(p => p.has_full_text);
      const abstracts = data.filter(p => !p.has_full_text && p.content && !p.content.startsWith("[No"));
      return (<div style={{ margin: "8px 0", padding: "8px", borderRadius: "6px", background: "#0f1520", border: "1px solid #1a3540", fontSize: "11px" }}>
        <div style={{ fontWeight: 600, color: "#22d3ee", marginBottom: "4px" }}>📖 Paper Content Retrieved</div>
        <div style={{ color: "#8899b0" }}>{withText.length} full-text, {abstracts.length} abstracts, {data.length - withText.length - abstracts.length} unavailable</div>
      </div>);
    }

    return null;
  };

  // ── Render Message Content (with Markdown-ish formatting) ──
  const MessageContent = ({ content }) => {
    if (!content) return null;
    const lines = content.split("\n");
    return (<div>{lines.map((line, i) => {
      if (line.startsWith("# ")) return <h3 key={i} style={{ fontSize: "15px", fontWeight: 700, margin: "12px 0 4px", color: "#e0e8f4" }}>{line.slice(2)}</h3>;
      if (line.startsWith("## ")) return <h4 key={i} style={{ fontSize: "13px", fontWeight: 700, margin: "10px 0 4px", color: "#c8d4e0" }}>{line.slice(3)}</h4>;
      if (line.startsWith("### ")) return <h5 key={i} style={{ fontSize: "12px", fontWeight: 600, margin: "8px 0 3px", color: "#a0b0c4" }}>{line.slice(4)}</h5>;
      if (line.startsWith("- ")) return <div key={i} style={{ paddingLeft: "12px", position: "relative", margin: "2px 0" }}><span style={{ position: "absolute", left: 0 }}>•</span>{line.slice(2)}</div>;
      if (line.match(/^\d+\. /)) return <div key={i} style={{ paddingLeft: "16px", margin: "2px 0" }}>{line}</div>;
      if (line.startsWith("```")) return null;
      if (line.startsWith(">")) return <div key={i} style={{ borderLeft: "3px solid #3a5070", paddingLeft: "10px", color: "#8899b0", fontStyle: "italic", margin: "4px 0" }}>{line.slice(1).trim()}</div>;
      if (line.trim() === "") return <div key={i} style={{ height: "6px" }} />;
      return <div key={i} style={{ margin: "2px 0", lineHeight: "1.6" }}>{line}</div>;
    })}</div>);
  };

  // ═══════════════════════════════════════════════════════════════
  // RENDER
  // ═══════════════════════════════════════════════════════════════

  return (
    <div style={{ display: "flex", height: "100vh", background: "#06090f", color: "#c8d4e0", fontFamily: "'DM Sans', 'Segoe UI', sans-serif", fontSize: "13px" }}>

      {/* ── LEFT SIDEBAR ── */}
      <div style={{ width: "260px", borderRight: "1px solid #1a2540", background: "#0a0f18", display: "flex", flexDirection: "column", flexShrink: 0 }}>
        {/* Logo */}
        <div style={{ padding: "16px", borderBottom: "1px solid #1a2540" }}>
          <div style={{ fontSize: "16px", fontWeight: 800, fontFamily: "'Space Mono', monospace" }}>🧬 <span style={{ color: "#00e5a0" }}>Research</span>Agent</div>
          <div style={{ fontSize: "10px", color: "#4e6380", marginTop: "2px" }}>v5.0 — Conversational AI Research</div>
        </div>

        {/* New Session Button */}
        <div style={{ padding: "10px 16px" }}>
          <button onClick={createSession} style={{ width: "100%", padding: "8px", borderRadius: "6px", border: "1px solid #00e5a030", background: "#00e5a010", color: "#00e5a0", fontWeight: 600, fontSize: "12px", cursor: "pointer" }}>+ New Session</button>
        </div>

        {/* Working Folder */}
        <div style={{ padding: "8px 16px", borderBottom: "1px solid #1a2540" }}>
          <div style={{ fontSize: "10px", fontWeight: 600, color: "#4e6380", textTransform: "uppercase", marginBottom: "4px" }}>📁 Working Folder</div>
          {workingFolder ? (
            <div style={{ fontSize: "11px", fontWeight: 600, color: "#e0e8f4" }}>{workingFolder.name}</div>
          ) : (
            <div style={{ fontSize: "11px", color: "#4e6380" }}>None selected</div>
          )}
          <button onClick={() => { setShowDrive(true); if (driveToken) browseDrive("root"); else connectDrive(); }}
            style={{ marginTop: "6px", width: "100%", padding: "6px", borderRadius: "4px", border: "1px solid #4285f430", background: "#4285f410", color: "#4285f4", fontSize: "10px", fontWeight: 600, cursor: "pointer" }}>
            📂 Navigate Drive
          </button>
        </div>

        {/* Drive Connection Status */}
        <div style={{ padding: "8px 16px", borderBottom: "1px solid #1a2540", display: "flex", alignItems: "center", gap: "6px" }}>
          <div style={{ width: 8, height: 8, borderRadius: "50%", background: driveConnected ? "#00e5a0" : "#f87171" }} />
          <span style={{ fontSize: "10px", color: driveConnected ? "#00e5a0" : "#f87171" }}>
            {driveConnected ? "Drive connected" : "Drive not connected"}
          </span>
          {!driveConnected && <button onClick={connectDrive} style={{ marginLeft: "auto", fontSize: "9px", color: "#60a5fa", background: "none", border: "none", cursor: "pointer", textDecoration: "underline" }}>Connect</button>}
        </div>

        {/* Session History */}
        <div style={{ flex: 1, overflow: "auto", padding: "8px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "4px 8px", marginBottom: "4px" }}>
            <span style={{ fontSize: "10px", fontWeight: 600, color: "#4e6380", textTransform: "uppercase" }}>History</span>
            <button onClick={loadSessions} style={{ fontSize: "9px", color: "#60a5fa", background: "none", border: "none", cursor: "pointer" }}>Refresh</button>
          </div>

          {/* History Folder */}
          <div style={{ padding: "4px 8px", marginBottom: "6px" }}>
            {historyFolder ? (
              <div style={{ fontSize: "10px", display: "flex", alignItems: "center", gap: "4px" }}>
                <span style={{ color: "#34d399" }}>☁️</span>
                <span style={{ color: "#34d399", fontWeight: 600, flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{historyFolder.name}</span>
                <button onClick={() => { setHistoryFolder(null); localStorage.removeItem("ra_history_folder"); }} style={{ fontSize: "8px", color: "#f87171", background: "none", border: "none", cursor: "pointer" }}>×</button>
              </div>
            ) : (
              <button onClick={() => { setShowHistoryFolderPicker(true); if (driveToken) browseHistoryFolders(); else connectDrive(); }}
                style={{ width: "100%", padding: "5px", borderRadius: "4px", border: "1px dashed #1a2540", background: "transparent", color: "#4e6380", fontSize: "9px", cursor: "pointer" }}>
                📂 Set History Folder in Drive
              </button>
            )}
          </div>

          {sessions.length === 0 && <div style={{ padding: "12px 8px", textAlign: "center", color: "#2a3550", fontSize: "10px" }}>No sessions yet. Start chatting!</div>}

          {sessions.map(s => (
            <div key={s.id + (s.fromDrive ? "_d" : "")} onClick={() => loadSession(s)} style={{
              padding: "8px", borderRadius: "6px", marginBottom: "3px", cursor: "pointer",
              background: sessionId === s.id ? "#00e5a010" : "#0f1520",
              border: `1px solid ${sessionId === s.id ? "#00e5a030" : "#1a2540"}`,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "4px" }}>
                {s.fromDrive && <span style={{ fontSize: "8px" }}>☁️</span>}
                {s.drive_synced && <span style={{ fontSize: "8px" }}>✅</span>}
                <div style={{ fontSize: "10px", fontWeight: 600, color: sessionId === s.id ? "#00e5a0" : "#c8d4e0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>{s.title || s.preview || "Empty"}</div>
                {s.pinned && <span style={{ fontSize: "8px" }}>📌</span>}
              </div>
              <div style={{ fontSize: "9px", color: "#4e6380", marginTop: "2px" }}>
                {s.message_count || 0} msgs {s.updated_str || s.created_str || ""}
              </div>
            </div>
          ))}
        </div>

        {/* Settings Button */}
        <div style={{ padding: "8px 16px", borderTop: "1px solid #1a2540" }}>
          <button onClick={() => setShowSettings(!showSettings)} style={{ width: "100%", padding: "6px", borderRadius: "4px", border: "1px solid #1a2540", background: "transparent", color: "#4e6380", fontSize: "10px", cursor: "pointer" }}>⚙️ Settings</button>
        </div>
      </div>

      {/* ── TOOL ACTIVITY PANEL ── */}
      {showActivity && <div style={{ width: "240px", borderRight: "1px solid #1a2540", background: "#080c14", display: "flex", flexDirection: "column", flexShrink: 0, overflow: "hidden" }}>
        {/* Header */}
        <div style={{ padding: "10px 12px", borderBottom: "1px solid #1a2540", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: "11px", fontWeight: 700, color: "#00e5a0" }}>⚡ Tool Activity</div>
          <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
            {isLoading && <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#00e5a0", animation: "pulse 1s infinite" }} />}
            <button onClick={() => setShowActivity(false)} style={{ background: "none", border: "none", color: "#4e6380", cursor: "pointer", fontSize: "14px", lineHeight: 1 }}>×</button>
          </div>
        </div>

        {/* Activity List */}
        <div style={{ flex: 1, overflow: "auto", padding: "6px" }}>
          {toolActivity.length === 0 && isLoading && (
            <div style={{ padding: "16px 8px", textAlign: "center", color: "#4e6380", fontSize: "10px" }}>
              <div style={{ fontSize: "16px", marginBottom: "6px", animation: "pulse 1s infinite" }}>🧠</div>
              Waiting for AI to decide which tools to use...
            </div>
          )}

          {toolActivity.length === 0 && !isLoading && (
            <div style={{ padding: "16px 8px", textAlign: "center", color: "#4e6380", fontSize: "10px" }}>
              <div style={{ fontSize: "16px", marginBottom: "6px", opacity: 0.4 }}>⚡</div>
              Tool activity will appear here<br />when the AI processes your request.
              <div style={{ marginTop: "8px", fontSize: "9px", color: "#2a3550" }}>Each tool shows: what it's doing, which model, and time taken</div>
            </div>
          )}

          {toolActivity.map((act, i) => {
            const m = MODELS.find(x => x.id === act.model);
            return (
              <div key={i} style={{
                padding: "8px 10px", borderRadius: "6px", marginBottom: "3px",
                background: act.status === "running" ? "#00e5a008" : "#0a0f18",
                border: `1px solid ${act.status === "running" ? "#00e5a025" : "#1a254020"}`,
                transition: "all .3s",
              }}>
                {/* Tool header */}
                <div style={{ display: "flex", alignItems: "center", gap: "6px", marginBottom: "3px" }}>
                  <span style={{ fontSize: "12px" }}>{act.icon || "⚙️"}</span>
                  <span style={{ fontSize: "10px", fontWeight: 700, color: act.status === "running" ? "#00e5a0" : "#c8d4e0", flex: 1 }}>
                    {act.tool === "ai_thinking" ? "AI Thinking" : act.tool}
                  </span>
                  {act.status === "running" ? (
                    <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#00e5a0", animation: "pulse 1s infinite" }} />
                  ) : (
                    <span style={{ fontSize: "9px", color: "#34d399" }}>✓</span>
                  )}
                </div>

                {/* What it's doing */}
                <div style={{ fontSize: "9px", color: "#8899b0", lineHeight: "1.4", paddingLeft: "18px" }}>
                  {act.message}
                </div>

                {/* Model + time */}
                <div style={{ display: "flex", gap: "6px", alignItems: "center", paddingLeft: "18px", marginTop: "3px" }}>
                  {m && <span style={{ fontSize: "8px", color: m.color, fontWeight: 600 }}>{m.icon} {m.name}</span>}
                  {act.time && <span style={{ fontSize: "8px", color: "#4e6380" }}>{act.time}s</span>}
                </div>

                {/* Result summary */}
                {act.result_summary && <div style={{ fontSize: "9px", color: "#34d399", paddingLeft: "18px", marginTop: "2px" }}>
                  {act.result_summary}
                </div>}
              </div>
            );
          })}
        </div>

        {/* Footer stats */}
        <div style={{ padding: "6px 12px", borderTop: "1px solid #1a2540", fontSize: "9px", color: "#4e6380", display: "flex", justifyContent: "space-between" }}>
          <span>{toolActivity.filter(a => a.status === "done").length} / {toolActivity.length} done</span>
          <span>{toolActivity.filter(a => a.tool !== "ai_thinking").reduce((s, a) => s + (a.time || 0), 0).toFixed(1)}s total</span>
        </div>
      </div>}

      {/* ── MAIN CHAT AREA ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Header */}
        <div style={{ padding: "10px 20px", borderBottom: "1px solid #1a2540", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#0a0f18" }}>
          <div style={{ fontSize: "12px", color: "#8899b0" }}>Session: <span style={{ color: "#00e5a0", fontFamily: "monospace" }}>{sessionId?.slice(0, 20)}</span></div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            {/* Show unique models in use */}
            {[...new Set(Object.values(toolModels))].slice(0, 3).map(mid => {
              const m = MODELS.find(x => x.id === mid);
              return m ? <span key={mid} style={{ fontSize: "9px", display: "flex", alignItems: "center", gap: "2px", color: m.color }}>{m.icon} {m.name}</span> : null;
            })}
            <button onClick={openFilePicker} style={{ padding: "3px 8px", borderRadius: "4px", border: `1px solid ${selectedFiles.length > 0 ? "#fbbf2440" : "#1a2540"}`, background: selectedFiles.length > 0 ? "#fbbf2410" : "transparent", color: selectedFiles.length > 0 ? "#fbbf24" : "#4e6380", fontSize: "10px", cursor: "pointer", fontWeight: 600, display: "flex", alignItems: "center", gap: "4px" }}>
              📎 Files {selectedFiles.length > 0 && <span style={{ background: "#fbbf24", color: "#000", borderRadius: "8px", padding: "0 5px", fontSize: "9px", fontWeight: 800 }}>{selectedFiles.length}</span>}
            </button>
            <button onClick={() => setShowActivity(!showActivity)} style={{ padding: "3px 8px", borderRadius: "4px", border: `1px solid ${showActivity ? "#00e5a040" : "#1a2540"}`, background: showActivity ? "#00e5a010" : "transparent", color: showActivity ? "#00e5a0" : "#4e6380", fontSize: "10px", cursor: "pointer", fontWeight: 600 }}>
              ⚡ {toolActivity.filter(a => a.status === "running").length > 0 ? `${toolActivity.filter(a => a.status === "running").length} running` : "Tools"}
            </button>
            <button onClick={() => setReaderOpen(!readerOpen)} style={{ padding: "3px 8px", borderRadius: "4px", border: `1px solid ${readerOpen ? "#00e5a040" : "#1a2540"}`, background: readerOpen ? "#00e5a010" : "transparent", color: readerOpen ? "#00e5a0" : "#4e6380", fontSize: "10px", cursor: "pointer", fontWeight: 600 }}>
              {readerOpen ? "✕ Close Reader" : "📖 Reader"}
            </button>
          </div>
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflow: "auto", padding: "16px 20px" }}>
          <div style={{ maxWidth: "800px", margin: "0 auto" }}>
            {messages.length === 0 && (
              <div style={{ textAlign: "center", padding: "60px 20px", color: "#4e6380" }}>
                <div style={{ fontSize: "36px", marginBottom: "12px" }}>🧬</div>
                <div style={{ fontSize: "18px", fontWeight: 700, color: "#e0e8f4", marginBottom: "8px" }}>ResearchAgent v5.0</div>
                <div style={{ fontSize: "13px", lineHeight: "1.6", maxWidth: "500px", margin: "0 auto" }}>
                  Ask me to search papers, review literature, analyze code, create documents, or manage your Google Drive files.
                  <br /><br />
                  Select a working folder from the sidebar, then describe what you need.
                </div>
                <div style={{ display: "flex", gap: "8px", justifyContent: "center", marginTop: "20px", flexWrap: "wrap" }}>
                  {["Search PubMed for fNIRS papers on cognitive impairment",
                    "Review all papers in my folder",
                    "Scan my data files and explain my code",
                    "Create a presentation from my review"].map(ex => (
                      <button key={ex} onClick={() => { setInput(ex); }}
                        style={{ padding: "8px 14px", borderRadius: "6px", border: "1px solid #1a2540", background: "#0f1520", color: "#8899b0", fontSize: "11px", cursor: "pointer", textAlign: "left", maxWidth: "220px" }}>
                        {ex}
                      </button>
                    ))}
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} style={{
                display: "flex", justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
                marginBottom: "12px",
              }}>
                <div style={{
                  maxWidth: msg.role === "assistant" && !readerOpen ? "85%" : "85%",
                  padding: "12px 16px", borderRadius: "12px",
                  background: msg.role === "user" ? "#1a3560" : "#0f1520",
                  border: `1px solid ${msg.role === "user" ? "#253560" : "#1a2540"}`,
                  lineHeight: "1.6",
                }}>
                  {msg.role === "assistant" && <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "4px" }}>
                    <div style={{ fontSize: "10px", color: "#00e5a0", fontWeight: 600 }}>🧬 ResearchAgent</div>
                    <button onClick={() => openReader(i)} style={{ fontSize: "9px", color: "#60a5fa", background: "none", border: "1px solid #60a5fa30", borderRadius: "4px", padding: "2px 8px", cursor: "pointer" }}>📖 Read Full</button>
                  </div>}
                  {/* Show summary for assistant, full for user */}
                  {msg.role === "assistant" ? (
                    <div>
                      <div style={{ fontSize: "12px", color: "#c8d4e0" }}>{summarize(msg.content)}</div>
                      {msg.tool_results?.length > 0 && <div style={{ fontSize: "10px", color: "#8899b0", marginTop: "4px" }}>
                        🔧 Used {msg.tool_results.length} tool{msg.tool_results.length > 1 ? "s" : ""}: {msg.tool_results.map(tr => tr.tool).join(", ")}
                      </div>}
                    </div>
                  ) : (
                    <MessageContent content={msg.content} />
                  )}
                </div>
              </div>
            ))}

            {isLoading && (
              <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: "12px" }}>
                <div style={{ padding: "12px 16px", borderRadius: "12px", background: "#0f1520", border: "1px solid #1a2540" }}>
                  <div style={{ fontSize: "10px", color: "#00e5a0", fontWeight: 600, marginBottom: "4px" }}>🧬 ResearchAgent</div>
                  <div style={{ display: "flex", gap: "4px", alignItems: "center" }}>
                    <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#00e5a0", animation: "pulse 1s infinite" }} />
                    <span style={{ color: "#8899b0", fontSize: "12px" }}>Thinking & using tools...</span>
                  </div>
                </div>
              </div>
            )}
            <div ref={chatEndRef} />
          </div>
        </div>

        {/* Input — expandable textarea */}
        <div style={{ padding: "12px 20px", borderTop: "1px solid #1a2540", background: "#0a0f18" }}>
          <div style={{ maxWidth: "800px", margin: "0 auto" }}>
            {/* Selected files tags */}
            {selectedFiles.length > 0 && <div style={{ display: "flex", gap: "4px", flexWrap: "wrap", marginBottom: "8px" }}>
              {selectedFiles.map(f => (
                <span key={f.id} onClick={() => toggleFileSelect(f)} style={{
                  display: "inline-flex", alignItems: "center", gap: "3px", padding: "2px 8px", borderRadius: "4px", fontSize: "10px", cursor: "pointer",
                  background: FILE_CAT_COLORS[f.cat] + "15", border: `1px solid ${FILE_CAT_COLORS[f.cat]}25`, color: FILE_CAT_COLORS[f.cat],
                }}>
                  {FILE_CAT_ICONS[f.cat]} {f.name.length > 20 ? f.name.slice(0, 17) + "..." : f.name} <span style={{ opacity: 0.5, marginLeft: "2px" }}>×</span>
                </span>
              ))}
              <span style={{ fontSize: "9px", color: "#4e6380", alignSelf: "center" }}>Working with {selectedFiles.length} file{selectedFiles.length > 1 ? "s" : ""} — click to remove</span>
            </div>}
            <div style={{ display: "flex", gap: "8px", alignItems: "flex-end" }}>
            <textarea value={input} onChange={e => { setInput(e.target.value); e.target.style.height = "auto"; e.target.style.height = Math.min(e.target.scrollHeight, 200) + "px"; }}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
              placeholder={workingFolder ? `Ask about "${workingFolder.name}" or anything else...` : "Describe your research task..."}
              rows={1}
              style={{ flex: 1, padding: "12px 16px", borderRadius: "8px", border: "1px solid #1a2540", background: "#0f1520", color: "#e0e8f4", fontSize: "13px", outline: "none", fontFamily: "inherit", resize: "none", minHeight: "44px", maxHeight: "200px", overflowY: "auto", lineHeight: "1.5" }}
            />
            {isLoading ? (
              <button onClick={() => { /* TODO: abort */ }} style={{ padding: "12px 20px", borderRadius: "8px", border: "none", background: "#f87171", color: "#fff", fontWeight: 700, cursor: "pointer", flexShrink: 0, height: "44px" }}>■ Stop</button>
            ) : (
              <button onClick={sendMessage} disabled={!input.trim()} style={{ padding: "12px 20px", borderRadius: "8px", border: "none", background: input.trim() ? "#00e5a0" : "#1a2540", color: input.trim() ? "#000" : "#4e6380", fontWeight: 700, cursor: input.trim() ? "pointer" : "default", flexShrink: 0, height: "44px" }}>Send</button>
            )}
          </div>
          </div>
        </div>
      </div>

      {/* ═══ READER PANEL (overlay on right half of chat) ═══ */}
      {readerOpen && <div style={{ position: "fixed", top: 0, right: 0, width: "50vw", height: "100vh", background: "#0a0f18", borderLeft: "2px solid #00e5a040", zIndex: 90, display: "flex", flexDirection: "column", boxShadow: "-4px 0 30px rgba(0,0,0,0.5)" }}>
        {/* Reader Header with arrows */}
        <div style={{ padding: "12px 16px", borderBottom: "1px solid #1a2540", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#080c14" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
            <button onClick={readerPrev} disabled={readerIndex <= 0} style={{ width: 32, height: 32, borderRadius: "6px", border: "1px solid #1a2540", background: readerIndex > 0 ? "#0f1520" : "transparent", color: readerIndex > 0 ? "#e0e8f4" : "#2a3550", fontSize: "16px", cursor: readerIndex > 0 ? "pointer" : "default", display: "flex", alignItems: "center", justifyContent: "center" }}>←</button>
            <span style={{ fontSize: "13px", color: "#8899b0", fontFamily: "monospace", fontWeight: 600 }}>{assistantMessages.length > 0 ? `${readerIndex + 1} / ${assistantMessages.length}` : "0 / 0"}</span>
            <button onClick={readerNext} disabled={readerIndex >= assistantMessages.length - 1} style={{ width: 32, height: 32, borderRadius: "6px", border: "1px solid #1a2540", background: readerIndex < assistantMessages.length - 1 ? "#0f1520" : "transparent", color: readerIndex < assistantMessages.length - 1 ? "#e0e8f4" : "#2a3550", fontSize: "16px", cursor: readerIndex < assistantMessages.length - 1 ? "pointer" : "default", display: "flex", alignItems: "center", justifyContent: "center" }}>→</button>
          </div>
          <div style={{ fontSize: "14px", fontWeight: 700, color: "#00e5a0" }}>📖 Full Response Reader</div>
          <button onClick={() => setReaderOpen(false)} style={{ width: 32, height: 32, borderRadius: "6px", background: "#f8717120", border: "none", color: "#f87171", cursor: "pointer", fontSize: "18px", display: "flex", alignItems: "center", justifyContent: "center" }}>×</button>
        </div>

        {/* Reader Content */}
        <div style={{ flex: 1, overflow: "auto", padding: "24px 28px" }}>
          {readerMsg ? (
            <div style={{ maxWidth: "700px" }}>
              <div style={{ fontSize: "12px", color: "#00e5a0", fontWeight: 600, marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                🧬 Response {readerIndex + 1}
                {readerMsg.tool_results?.length > 0 && <span style={{ fontSize: "10px", color: "#60a5fa", background: "#60a5fa15", padding: "2px 8px", borderRadius: "4px" }}>🔧 {readerMsg.tool_results.length} tools used</span>}
              </div>
              
              {/* Full content */}
              <div style={{ fontSize: "14px", lineHeight: "1.8", color: "#c8d4e0" }}>
                <MessageContent content={readerMsg.content} />
              </div>

              {/* Tool results */}
              {readerMsg.tool_results?.map((tr, j) => <ToolResult key={j} result={tr} />)}
            </div>
          ) : (
            <div style={{ textAlign: "center", padding: "60px 20px", color: "#4e6380" }}>
              <div style={{ fontSize: "32px", marginBottom: "12px", opacity: 0.3 }}>📖</div>
              <div style={{ fontSize: "14px" }}>Click "Read Full" on any response<br />or use ← → arrows to navigate</div>
            </div>
          )}
        </div>

        {/* Reader footer with quick actions */}
        {readerMsg && <div style={{ padding: "10px 16px", borderTop: "1px solid #1a2540", display: "flex", gap: "8px", background: "#080c14" }}>
          <button onClick={() => navigator.clipboard?.writeText(readerMsg.content)} style={{ flex: 1, padding: "8px", borderRadius: "6px", border: "1px solid #1a2540", background: "transparent", color: "#8899b0", fontSize: "11px", cursor: "pointer" }}>📋 Copy Text</button>
          <button onClick={() => { setInput(`Modify the above response: `); setReaderOpen(false); }} style={{ flex: 1, padding: "8px", borderRadius: "6px", border: "1px solid #00e5a030", background: "#00e5a010", color: "#00e5a0", fontSize: "11px", cursor: "pointer" }}>✏️ Modify</button>
        </div>}
      </div>}

      {/* ═══ SETTINGS PANEL (overlay) ═══ */}
      {showSettings && <>
        <div onClick={() => setShowSettings(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 100 }} />
        <div style={{ position: "fixed", top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: "480px", maxHeight: "80vh", background: "#0a0f18", border: "1px solid #1a2540", borderRadius: "12px", zIndex: 101, overflow: "auto", padding: "24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "16px" }}>
            <h2 style={{ fontSize: "16px", fontWeight: 700, margin: 0 }}>⚙️ Settings</h2>
            <button onClick={() => setShowSettings(false)} style={{ background: "none", border: "none", color: "#8899b0", cursor: "pointer", fontSize: "18px" }}>×</button>
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label style={{ fontSize: "11px", fontWeight: 600, color: "#8899b0", display: "block", marginBottom: "4px" }}>Backend URL</label>
            <input value={backendUrl} onChange={e => setBackendUrl(e.target.value)}
              placeholder="http://localhost:8000 or ngrok URL"
              style={{ width: "100%", padding: "8px 12px", borderRadius: "6px", border: "1px solid #1a2540", background: "#0f1520", color: "#e0e8f4", fontSize: "12px", outline: "none", boxSizing: "border-box", fontFamily: "monospace" }}
            />
            <div style={{ fontSize: "10px", color: "#4e6380", marginTop: "4px" }}>For Colab: paste the ngrok URL here</div>
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label style={{ fontSize: "11px", fontWeight: 600, color: "#8899b0", display: "block", marginBottom: "4px" }}>Google OAuth Client ID</label>
            <input defaultValue={localStorage.getItem("ra_google_client_id") || ""} onChange={e => localStorage.setItem("ra_google_client_id", e.target.value)}
              placeholder="123456-abc.apps.googleusercontent.com"
              style={{ width: "100%", padding: "8px 12px", borderRadius: "6px", border: "1px solid #1a2540", background: "#0f1520", color: "#e0e8f4", fontSize: "12px", outline: "none", boxSizing: "border-box", fontFamily: "monospace" }}
            />
          </div>

          {/* Per-Tool Model Routing */}
          <div style={{ marginBottom: "16px" }}>
            <label style={{ fontSize: "11px", fontWeight: 600, color: "#8899b0", display: "block", marginBottom: "4px" }}>🤖 Model per Tool</label>
            <div style={{ fontSize: "10px", color: "#4e6380", marginBottom: "8px" }}>Each tool uses its assigned model. Heavy tasks → Opus/Pro, quick tasks → Haiku/Flash.</div>
            <div style={{ maxHeight: "320px", overflow: "auto", border: "1px solid #1a2540", borderRadius: "6px" }}>
              {TOOL_LIST.map(tool => {
                const mid = toolModels[tool.key] || DEFAULT_TOOL_MODELS[tool.key];
                const m = MODELS.find(x => x.id === mid);
                return (
                  <div key={tool.key} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "6px 10px", borderBottom: "1px solid #1a254020", background: "#0a0f18" }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: "11px", fontWeight: 600, color: "#e0e8f4" }}>{tool.label}</div>
                      <div style={{ fontSize: "9px", color: "#4e6380" }}>{tool.desc}</div>
                    </div>
                    <select value={mid} onChange={e => {
                      const next = { ...toolModels, [tool.key]: e.target.value };
                      setToolModels(next);
                      localStorage.setItem("ra_tool_models", JSON.stringify(next));
                    }} style={{ padding: "4px 6px", borderRadius: "4px", border: "1px solid #1a2540", background: "#0f1520", color: m?.color || "#c8d4e0", fontSize: "10px", fontFamily: "monospace", outline: "none", cursor: "pointer", minWidth: "130px" }}>
                      <optgroup label="Claude (Anthropic)">
                        {MODELS.filter(x => x.provider === "Anthropic").map(x => <option key={x.id} value={x.id}>{x.icon} {x.name}</option>)}
                      </optgroup>
                      <optgroup label="Gemini (Google)">
                        {MODELS.filter(x => x.provider === "Google").map(x => <option key={x.id} value={x.id}>{x.icon} {x.name}</option>)}
                      </optgroup>
                    </select>
                  </div>
                );
              })}
            </div>
            <div style={{ display: "flex", gap: "6px", marginTop: "8px" }}>
              <button onClick={() => { setToolModels({ ...DEFAULT_TOOL_MODELS }); localStorage.setItem("ra_tool_models", JSON.stringify(DEFAULT_TOOL_MODELS)); }} style={{ padding: "5px 10px", borderRadius: "4px", border: "1px solid #1a2540", background: "transparent", color: "#8899b0", fontSize: "9px", cursor: "pointer" }}>↩ Reset Defaults</button>
              <button onClick={() => { const m = {}; TOOL_LIST.forEach(t => m[t.key] = "gemini-2.5-flash"); setToolModels(m); localStorage.setItem("ra_tool_models", JSON.stringify(m)); }} style={{ padding: "5px 10px", borderRadius: "4px", border: "1px solid #FBBC0430", background: "transparent", color: "#FBBC04", fontSize: "9px", cursor: "pointer" }}>◇ All Gem Flash</button>
              <button onClick={() => { const m = {}; TOOL_LIST.forEach(t => m[t.key] = "gemini-3.1-pro-preview"); setToolModels(m); localStorage.setItem("ra_tool_models", JSON.stringify(m)); }} style={{ padding: "5px 10px", borderRadius: "4px", border: "1px solid #4285F430", background: "transparent", color: "#4285F4", fontSize: "9px", cursor: "pointer" }}>◇ All Gem Pro</button>
              <button onClick={() => { const m = {}; TOOL_LIST.forEach(t => m[t.key] = "claude-opus-4-6"); setToolModels(m); localStorage.setItem("ra_tool_models", JSON.stringify(m)); }} style={{ padding: "5px 10px", borderRadius: "4px", border: "1px solid #a78bfa30", background: "transparent", color: "#a78bfa", fontSize: "9px", cursor: "pointer" }}>◆ All Opus</button>
            </div>
          </div>

          <button onClick={() => { localStorage.setItem("ra_backend_url", backendUrl); setShowSettings(false); alert("Settings saved!"); }}
            style={{ padding: "10px 20px", borderRadius: "6px", border: "none", background: "#00e5a0", color: "#000", fontWeight: 700, cursor: "pointer" }}>
            Save Settings
          </button>
        </div>
      </>}

      {/* ═══ DRIVE BROWSER MODAL ═══ */}
      {showDrive && <>
        <div onClick={() => setShowDrive(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 200 }} />
        <div style={{ position: "fixed", top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: "560px", maxHeight: "80vh", background: "#0a0f18", border: "1px solid #1a2540", borderRadius: "12px", zIndex: 201, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ padding: "14px 16px", borderBottom: "1px solid #1a2540", display: "flex", justifyContent: "space-between" }}>
            <div style={{ fontWeight: 700, fontSize: "14px" }}>📂 Google Drive</div>
            <button onClick={() => setShowDrive(false)} style={{ background: "none", border: "none", color: "#8899b0", cursor: "pointer", fontSize: "18px" }}>×</button>
          </div>

          {/* Breadcrumb */}
          <div style={{ padding: "6px 16px", borderBottom: "1px solid #1a2540", display: "flex", gap: "4px", flexWrap: "wrap", fontSize: "11px" }}>
            {drivePath.map((p, i) => (
              <span key={p.id}>
                {i > 0 && <span style={{ color: "#4e6380" }}> / </span>}
                <button onClick={() => navigateTo(i)} style={{ background: "none", border: "none", color: i === drivePath.length - 1 ? "#00e5a0" : "#8899b0", cursor: "pointer", fontWeight: i === drivePath.length - 1 ? 700 : 400, fontSize: "11px" }}>{p.name}</button>
              </span>
            ))}
          </div>

          {/* Search + Create */}
          <div style={{ padding: "8px 16px", borderBottom: "1px solid #1a2540", display: "flex", gap: "6px" }}>
            <input value={driveSearch} onChange={e => setDriveSearch(e.target.value)} onKeyDown={e => e.key === "Enter" && searchDrive()} placeholder="Search folders..." style={{ flex: 1, padding: "6px 10px", borderRadius: "4px", border: "1px solid #1a2540", background: "#0f1520", color: "#e0e8f4", fontSize: "11px", outline: "none" }} />
            <button onClick={searchDrive} style={{ padding: "6px 10px", borderRadius: "4px", border: "none", background: "#4285f4", color: "#fff", fontSize: "10px", fontWeight: 600, cursor: "pointer" }}>🔍</button>
          </div>
          <div style={{ padding: "6px 16px", borderBottom: "1px solid #1a2540", display: "flex", gap: "6px" }}>
            <input value={newFolderName} onChange={e => setNewFolderName(e.target.value)} onKeyDown={e => e.key === "Enter" && createFolder()} placeholder="New folder name..." style={{ flex: 1, padding: "6px 10px", borderRadius: "4px", border: "1px solid #1a2540", background: "#0f1520", color: "#e0e8f4", fontSize: "11px", outline: "none" }} />
            <button onClick={createFolder} disabled={!newFolderName.trim()} style={{ padding: "6px 10px", borderRadius: "4px", border: "none", background: newFolderName.trim() ? "#00e5a0" : "#1a2540", color: newFolderName.trim() ? "#000" : "#4e6380", fontSize: "10px", fontWeight: 600, cursor: newFolderName.trim() ? "pointer" : "default" }}>+ Create</button>
          </div>

          {/* Listing */}
          <div style={{ flex: 1, overflow: "auto", padding: "8px 12px" }}>
            {driveLoading && <div style={{ textAlign: "center", padding: "20px", color: "#4e6380" }}>Loading...</div>}
            {driveFolders.map(f => (
              <div key={f.id} style={{ padding: "8px 10px", borderRadius: "6px", marginBottom: "2px", cursor: "pointer", background: "#0f1520", border: "1px solid #1a2540", display: "flex", alignItems: "center", gap: "8px" }}
                onClick={() => selectFolder(f)} onDoubleClick={() => navigateInto(f)}>
                <span style={{ fontSize: "16px" }}>📁</span>
                <div style={{ flex: 1 }}><div style={{ fontSize: "11px", fontWeight: 600, color: "#e0e8f4" }}>{f.name}</div></div>
                <button onClick={e => { e.stopPropagation(); navigateInto(f); }} style={{ padding: "2px 8px", borderRadius: "4px", border: "1px solid #1a2540", background: "transparent", color: "#8899b0", fontSize: "10px", cursor: "pointer" }}>Open →</button>
              </div>
            ))}
            {driveFiles.slice(0, 20).map(f => (
              <div key={f.id} style={{ padding: "4px 10px", borderRadius: "4px", marginBottom: "1px", background: "#0a0f18", display: "flex", alignItems: "center", gap: "6px", fontSize: "10px", color: "#4e6380" }}>
                <span>📄</span> {f.name} <span style={{ marginLeft: "auto" }}>{f.size ? `${(parseInt(f.size) / 1024).toFixed(0)} KB` : ""}</span>
              </div>
            ))}
          </div>

          <div style={{ padding: "10px 16px", borderTop: "1px solid #1a2540", fontSize: "10px", color: "#4e6380" }}>
            Click folder to select as working directory • Double-click to open
          </div>
        </div>
      </>}

      {/* ═══ FILE PICKER MODAL ═══ */}
      {showFilePicker && <>
        <div onClick={() => setShowFilePicker(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 200 }} />
        <div style={{ position: "fixed", top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: "560px", maxHeight: "80vh", background: "#0a0f18", border: "1px solid #1a2540", borderRadius: "12px", zIndex: 201, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          {/* Header */}
          <div style={{ padding: "14px 16px", borderBottom: "1px solid #1a2540", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: "14px" }}>📎 Choose Files</div>
              <div style={{ fontSize: "10px", color: "#4e6380", marginTop: "2px" }}>
                {workingFolder?.name || "Working folder"} • {selectedFiles.length} selected
              </div>
            </div>
            <button onClick={() => setShowFilePicker(false)} style={{ background: "none", border: "none", color: "#8899b0", cursor: "pointer", fontSize: "18px" }}>×</button>
          </div>

          {/* Search */}
          <div style={{ padding: "8px 16px", borderBottom: "1px solid #1a2540", display: "flex", gap: "6px" }}>
            <input value={fileSearch} onChange={e => setFileSearch(e.target.value)} onKeyDown={e => e.key === "Enter" && searchFilesInDrive()}
              placeholder="Search files in folder..."
              style={{ flex: 1, padding: "6px 10px", borderRadius: "4px", border: "1px solid #1a2540", background: "#0f1520", color: "#e0e8f4", fontSize: "11px", outline: "none" }} />
            <button onClick={searchFilesInDrive} style={{ padding: "6px 10px", borderRadius: "4px", border: "none", background: "#4285f4", color: "#fff", fontSize: "10px", fontWeight: 600, cursor: "pointer" }}>🔍</button>
            <button onClick={openFilePicker} style={{ padding: "6px 10px", borderRadius: "4px", border: "1px solid #1a2540", background: "transparent", color: "#8899b0", fontSize: "10px", cursor: "pointer" }}>↻ All</button>
          </div>

          {/* Selected files bar */}
          {selectedFiles.length > 0 && <div style={{ padding: "6px 16px", borderBottom: "1px solid #1a2540", display: "flex", gap: "4px", flexWrap: "wrap" }}>
            {selectedFiles.map(f => (
              <span key={f.id} onClick={() => toggleFileSelect(f)} style={{
                display: "inline-flex", alignItems: "center", gap: "4px", padding: "2px 8px", borderRadius: "4px", fontSize: "10px", cursor: "pointer",
                background: FILE_CAT_COLORS[f.cat] + "15", border: `1px solid ${FILE_CAT_COLORS[f.cat]}30`, color: FILE_CAT_COLORS[f.cat],
              }}>
                {FILE_CAT_ICONS[f.cat]} {f.name.length > 25 ? f.name.slice(0, 22) + "..." : f.name} ×
              </span>
            ))}
            <button onClick={() => setSelectedFiles([])} style={{ padding: "2px 8px", borderRadius: "4px", border: "1px solid #f8717130", background: "transparent", color: "#f87171", fontSize: "9px", cursor: "pointer" }}>Clear all</button>
          </div>}

          {/* File list */}
          <div style={{ flex: 1, overflow: "auto", padding: "6px 12px" }}>
            {pickerLoading && <div style={{ textAlign: "center", padding: "20px", color: "#4e6380" }}>Loading files...</div>}

            {/* Group by category */}
            {["code", "data", "doc", "other"].map(cat => {
              const catFiles = (fileSearch.trim() ? pickerFiles : pickerFiles).filter(f => f.cat === cat);
              if (catFiles.length === 0) return null;
              return (
                <div key={cat} style={{ marginBottom: "8px" }}>
                  <div style={{ fontSize: "10px", fontWeight: 700, color: FILE_CAT_COLORS[cat], padding: "4px 8px", textTransform: "uppercase" }}>
                    {FILE_CAT_ICONS[cat]} {cat} ({catFiles.length})
                  </div>
                  {catFiles.map(f => (
                    <div key={f.id} onClick={() => toggleFileSelect(f)} style={{
                      display: "flex", alignItems: "center", gap: "8px", padding: "6px 10px", borderRadius: "6px", marginBottom: "2px", cursor: "pointer",
                      background: isFileSelected(f.id) ? FILE_CAT_COLORS[f.cat] + "10" : "#0f1520",
                      border: `1px solid ${isFileSelected(f.id) ? FILE_CAT_COLORS[f.cat] + "40" : "#1a254020"}`,
                    }}>
                      <div style={{ width: 16, height: 16, borderRadius: "3px", border: `2px solid ${isFileSelected(f.id) ? FILE_CAT_COLORS[f.cat] : "#2a3550"}`, background: isFileSelected(f.id) ? FILE_CAT_COLORS[f.cat] : "transparent", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "10px", color: "#fff", flexShrink: 0 }}>
                        {isFileSelected(f.id) && "✓"}
                      </div>
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: "11px", fontWeight: 600, color: "#e0e8f4", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{f.name}</div>
                      </div>
                      <div style={{ fontSize: "9px", color: "#4e6380", flexShrink: 0 }}>{f.size_str}</div>
                    </div>
                  ))}
                </div>
              );
            })}

            {!pickerLoading && pickerFiles.length === 0 && (
              <div style={{ textAlign: "center", padding: "20px", color: "#4e6380", fontSize: "11px" }}>No files found in this folder</div>
            )}
          </div>

          {/* Footer */}
          <div style={{ padding: "10px 16px", borderTop: "1px solid #1a2540", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div style={{ fontSize: "10px", color: "#8899b0" }}>{selectedFiles.length} files selected</div>
            <button onClick={() => setShowFilePicker(false)} style={{ padding: "8px 20px", borderRadius: "6px", border: "none", background: "#00e5a0", color: "#000", fontWeight: 700, fontSize: "11px", cursor: "pointer" }}>
              ✓ Done
            </button>
          </div>
        </div>
      </>}

      {/* ═══ HISTORY FOLDER PICKER MODAL ═══ */}
      {showHistoryFolderPicker && <>
        <div onClick={() => setShowHistoryFolderPicker(false)} style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.6)", zIndex: 200 }} />
        <div style={{ position: "fixed", top: "50%", left: "50%", transform: "translate(-50%,-50%)", width: "440px", maxHeight: "70vh", background: "#0a0f18", border: "1px solid #1a2540", borderRadius: "12px", zIndex: 201, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ padding: "14px 16px", borderBottom: "1px solid #1a2540", display: "flex", justifyContent: "space-between" }}>
            <div>
              <div style={{ fontWeight: 700, fontSize: "14px" }}>📂 Choose History Folder</div>
              <div style={{ fontSize: "10px", color: "#4e6380", marginTop: "2px" }}>Sessions will be auto-saved here as JSON</div>
            </div>
            <button onClick={() => setShowHistoryFolderPicker(false)} style={{ background: "none", border: "none", color: "#8899b0", cursor: "pointer", fontSize: "18px" }}>×</button>
          </div>
          <div style={{ padding: "8px 16px", borderBottom: "1px solid #1a2540", display: "flex", gap: "6px" }}>
            <input value={historySearch} onChange={e => setHistorySearch(e.target.value)} onKeyDown={e => e.key === "Enter" && searchHistoryFolders()}
              placeholder="Search folders..." style={{ flex: 1, padding: "6px 10px", borderRadius: "4px", border: "1px solid #1a2540", background: "#0f1520", color: "#e0e8f4", fontSize: "11px", outline: "none" }} />
            <button onClick={searchHistoryFolders} style={{ padding: "6px 10px", borderRadius: "4px", border: "none", background: "#4285f4", color: "#fff", fontSize: "10px", fontWeight: 600, cursor: "pointer" }}>🔍</button>
            <button onClick={() => browseHistoryFolders("root")} style={{ padding: "6px 10px", borderRadius: "4px", border: "1px solid #1a2540", background: "transparent", color: "#8899b0", fontSize: "10px", cursor: "pointer" }}>Root</button>
          </div>
          <div style={{ flex: 1, overflow: "auto", padding: "6px 12px" }}>
            {historyFolders.map(f => (
              <div key={f.id} onClick={() => selectHistoryFolder(f)} style={{ display: "flex", alignItems: "center", gap: "8px", padding: "8px 10px", borderRadius: "6px", marginBottom: "2px", cursor: "pointer", background: "#0f1520", border: "1px solid #1a2540" }}>
                <span>📁</span>
                <div style={{ fontSize: "11px", fontWeight: 600, color: "#e0e8f4" }}>{f.name}</div>
              </div>
            ))}
            {historyFolders.length === 0 && <div style={{ textAlign: "center", padding: "20px", color: "#4e6380", fontSize: "11px" }}>Search for a folder or browse from root</div>}
          </div>
          <div style={{ padding: "10px 16px", borderTop: "1px solid #1a2540", fontSize: "10px", color: "#4e6380" }}>
            Click a folder to set it as your history folder. Each session saves as a subfolder with session.json inside.
          </div>
        </div>
      </>}

      <style>{`@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }`}</style>
    </div>
  );
}
