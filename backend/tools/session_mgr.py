"""Session Manager — Auto-saves to Google Drive folder
Each session = a subfolder with session.json inside
Format: JSON with messages, metadata, timestamps"""
import os, json, time, uuid
from typing import Optional, List

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)


class SessionManager:
    def create(self) -> str:
        sid = f"session_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        data = {
            "id": sid,
            "created": time.time(),
            "created_str": time.strftime("%Y-%m-%d %H:%M"),
            "title": "",
            "messages": [],
            "metadata": {"pinned": False},
        }
        path = os.path.join(SESSIONS_DIR, f"{sid}.json")
        with open(path, "w") as f:
            json.dump(data, f)
        return sid
    
    def get(self, sid: str) -> Optional[dict]:
        path = os.path.join(SESSIONS_DIR, f"{sid}.json")
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return json.load(f)
    
    def save_message(self, sid: str, message: dict):
        session = self.get(sid)
        if not session:
            self.create()
            session = self.get(sid)
            if not session:
                return
        session["messages"].append({**message, "timestamp": time.time()})
        # Auto-set title from first user message
        if not session.get("title"):
            for m in session["messages"]:
                if m.get("role") == "user":
                    session["title"] = m["content"][:80]
                    break
        session["updated"] = time.time()
        session["updated_str"] = time.strftime("%Y-%m-%d %H:%M")
        path = os.path.join(SESSIONS_DIR, f"{sid}.json")
        with open(path, "w") as f:
            json.dump(session, f)
    
    def list_all(self) -> list:
        sessions = []
        for f in sorted(os.listdir(SESSIONS_DIR), reverse=True):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(SESSIONS_DIR, f)) as fh:
                        d = json.load(fh)
                        msgs = d.get("messages", [])
                        first_user = d.get("title") or next(
                            (m["content"][:80] for m in msgs if m.get("role") == "user"), "Empty session"
                        )
                        sessions.append({
                            "id": d["id"],
                            "title": first_user,
                            "created": d.get("created", 0),
                            "created_str": d.get("created_str", ""),
                            "updated_str": d.get("updated_str", ""),
                            "message_count": len(msgs),
                            "pinned": d.get("metadata", {}).get("pinned", False),
                            "drive_synced": d.get("metadata", {}).get("drive_folder_id") is not None,
                        })
                except:
                    pass
        return sessions
    
    def pin(self, sid: str, pinned: bool = True):
        session = self.get(sid)
        if session:
            session.setdefault("metadata", {})["pinned"] = pinned
            path = os.path.join(SESSIONS_DIR, f"{sid}.json")
            with open(path, "w") as f:
                json.dump(session, f)
    
    def delete(self, sid: str):
        path = os.path.join(SESSIONS_DIR, f"{sid}.json")
        if os.path.exists(path):
            os.remove(path)
    
    # ══════════════════════════════════════════════════
    # GOOGLE DRIVE SYNC
    # ══════════════════════════════════════════════════
    
    async def save_to_drive(self, sid: str, drive, history_folder_id: str) -> dict:
        """Save a session to Drive inside the history folder.
        Creates: history_folder / session_title_date / session.json"""
        session = self.get(sid)
        if not session:
            return {"error": "Session not found"}
        
        title = session.get("title", "Untitled")[:40]
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title).strip()
        date_str = time.strftime("%Y%m%d_%H%M")
        folder_name = f"{safe_title}_{date_str}"
        
        # Check if session folder already exists (for updates)
        existing_folder_id = session.get("metadata", {}).get("drive_folder_id")
        
        if existing_folder_id:
            # Update existing session file
            try:
                await drive.update_file(
                    session["metadata"]["drive_file_id"],
                    json.dumps(session, indent=2, default=str),
                    "application/json"
                )
                return {
                    "status": "updated",
                    "folder_id": existing_folder_id,
                    "folder_name": folder_name,
                }
            except:
                pass  # Fall through to create new
        
        # Create new session folder inside history folder
        session_folder_id = await drive.create_folder(folder_name, history_folder_id)
        if not session_folder_id:
            return {"error": "Could not create session folder in Drive"}
        
        # Upload session.json
        result = await drive.upload_file(
            "session.json",
            json.dumps(session, indent=2, default=str),
            "application/json",
            parent_id=session_folder_id
        )
        
        file_id = result.get("id") if isinstance(result, dict) else result
        
        # Store Drive IDs in local session for future updates
        session.setdefault("metadata", {})["drive_folder_id"] = session_folder_id
        session["metadata"]["drive_file_id"] = file_id
        path = os.path.join(SESSIONS_DIR, f"{sid}.json")
        with open(path, "w") as f:
            json.dump(session, f)
        
        return {
            "status": "saved",
            "folder_id": session_folder_id,
            "folder_name": folder_name,
            "file_id": file_id,
        }
    
    async def list_drive_sessions(self, drive, history_folder_id: str) -> list:
        """List all sessions saved in the Drive history folder"""
        folders = await drive.list_files(history_folder_id)
        sessions = []
        
        for f in folders:
            if f.get("mime") == "application/vnd.google-apps.folder":
                # Look for session.json inside
                files = await drive.list_files(f["id"])
                for sf in files:
                    if sf["name"] == "session.json":
                        try:
                            content = await drive.read_file(sf["id"])
                            if content.get("content"):
                                data = json.loads(content["content"])
                                sessions.append({
                                    "id": data.get("id", f["name"]),
                                    "title": data.get("title", f["name"]),
                                    "created_str": data.get("created_str", ""),
                                    "updated_str": data.get("updated_str", ""),
                                    "message_count": len(data.get("messages", [])),
                                    "drive_folder_id": f["id"],
                                    "drive_file_id": sf["id"],
                                    "source": "drive",
                                })
                        except:
                            sessions.append({
                                "id": f["name"],
                                "title": f["name"],
                                "drive_folder_id": f["id"],
                                "source": "drive",
                            })
                        break
        
        return sessions
    
    async def load_from_drive(self, drive, drive_file_id: str) -> Optional[dict]:
        """Load a session from Drive by its session.json file ID"""
        content = await drive.read_file(drive_file_id)
        if content.get("content"):
            try:
                session = json.loads(content["content"])
                # Also save locally
                sid = session.get("id", f"drive_{int(time.time())}")
                path = os.path.join(SESSIONS_DIR, f"{sid}.json")
                with open(path, "w") as f:
                    json.dump(session, f)
                return session
            except:
                pass
        return None
