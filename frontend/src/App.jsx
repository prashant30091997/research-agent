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

  // ── Sidebar ──
  const [showHistory, setShowHistory] = useState(false);
  const [sessions, setSessions] = useState([]);

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
  }, []);

  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

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

  // ── Send Message ──
  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    const userMsg = { role: "user", content: input.trim() };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setIsLoading(true);

    try {
      const result = await api("/api/chat", {
        session_id: sessionId,
        messages: newMessages.map(m => ({ role: m.role, content: m.content })),
        drive_token: driveToken,
        working_folder_id: workingFolder?.id,
      });

      const assistantMsg = {
        role: "assistant",
        content: result.message || "No response",
        tool_results: result.tool_results || [],
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (e) {
      setMessages(prev => [...prev, { role: "assistant", content: `⚠️ Error: ${e.message}\n\nMake sure the backend is running at: ${backendUrl}\n\nIf using Colab, check the ngrok URL in Settings.` }]);
    }
    setIsLoading(false);
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

  // ── Load Sessions ──
  const loadSessions = async () => {
    try {
      const r = await fetch(`${backendUrl}/api/session/list`);
      const d = await r.json();
      setSessions(d.sessions || []);
    } catch { }
  };

  const loadSession = async (sid) => {
    try {
      const r = await api("/api/session/load", { session_id: sid });
      if (r.messages) {
        setSessionId(sid);
        setMessages(r.messages);
        setShowHistory(false);
      }
    } catch { }
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

    return null; // Don't render unknown tool results
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
          {sessions.map(s => (
            <div key={s.id} onClick={() => loadSession(s.id)} style={{
              padding: "8px", borderRadius: "6px", marginBottom: "3px", cursor: "pointer",
              background: sessionId === s.id ? "#00e5a010" : "#0f1520",
              border: `1px solid ${sessionId === s.id ? "#00e5a030" : "#1a2540"}`,
            }}>
              <div style={{ fontSize: "10px", fontWeight: 600, color: sessionId === s.id ? "#00e5a0" : "#c8d4e0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{s.preview}</div>
              <div style={{ fontSize: "9px", color: "#4e6380", marginTop: "2px" }}>{s.message_count} messages {s.pinned && "📌"}</div>
            </div>
          ))}
        </div>

        {/* Settings Button */}
        <div style={{ padding: "8px 16px", borderTop: "1px solid #1a2540" }}>
          <button onClick={() => setShowSettings(!showSettings)} style={{ width: "100%", padding: "6px", borderRadius: "4px", border: "1px solid #1a2540", background: "transparent", color: "#4e6380", fontSize: "10px", cursor: "pointer" }}>⚙️ Settings</button>
        </div>
      </div>

      {/* ── MAIN CHAT AREA ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        {/* Header */}
        <div style={{ padding: "10px 20px", borderBottom: "1px solid #1a2540", display: "flex", justifyContent: "space-between", alignItems: "center", background: "#0a0f18" }}>
          <div style={{ fontSize: "12px", color: "#8899b0" }}>Session: <span style={{ color: "#00e5a0", fontFamily: "monospace" }}>{sessionId?.slice(0, 20)}</span></div>
          <div style={{ fontSize: "10px", color: "#4e6380" }}>Backend: <span style={{ color: backendUrl.includes("localhost") ? "#fbbf24" : "#34d399" }}>{backendUrl.slice(0, 40)}</span></div>
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
                  maxWidth: "85%", padding: "12px 16px", borderRadius: "12px",
                  background: msg.role === "user" ? "#1a3560" : "#0f1520",
                  border: `1px solid ${msg.role === "user" ? "#253560" : "#1a2540"}`,
                  lineHeight: "1.6",
                }}>
                  {msg.role === "assistant" && <div style={{ fontSize: "10px", color: "#00e5a0", fontWeight: 600, marginBottom: "4px" }}>🧬 ResearchAgent</div>}
                  <MessageContent content={msg.content} />
                  {msg.tool_results?.map((tr, j) => <ToolResult key={j} result={tr} />)}
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

        {/* Input */}
        <div style={{ padding: "12px 20px", borderTop: "1px solid #1a2540", background: "#0a0f18" }}>
          <div style={{ maxWidth: "800px", margin: "0 auto", display: "flex", gap: "8px" }}>
            <input value={input} onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
              placeholder={workingFolder ? `Ask about "${workingFolder.name}" or anything else...` : "Describe your research task..."}
              style={{ flex: 1, padding: "12px 16px", borderRadius: "8px", border: "1px solid #1a2540", background: "#0f1520", color: "#e0e8f4", fontSize: "13px", outline: "none", fontFamily: "inherit" }}
            />
            {isLoading ? (
              <button onClick={() => { /* TODO: abort */ }} style={{ padding: "12px 20px", borderRadius: "8px", border: "none", background: "#f87171", color: "#fff", fontWeight: 700, cursor: "pointer" }}>■ Stop</button>
            ) : (
              <button onClick={sendMessage} disabled={!input.trim()} style={{ padding: "12px 20px", borderRadius: "8px", border: "none", background: input.trim() ? "#00e5a0" : "#1a2540", color: input.trim() ? "#000" : "#4e6380", fontWeight: 700, cursor: input.trim() ? "pointer" : "default" }}>Send</button>
            )}
          </div>
        </div>
      </div>

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

      <style>{`@keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.3; } }`}</style>
    </div>
  );
}
