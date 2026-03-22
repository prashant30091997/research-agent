"""Session Manager — Local storage + Drive sync"""
import os, json, time, uuid
from typing import Optional

SESSIONS_DIR = os.path.join(os.path.dirname(__file__), "..", "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)

class SessionManager:
    def create(self) -> str:
        sid = f"session_{int(time.time())}_{uuid.uuid4().hex[:6]}"
        path = os.path.join(SESSIONS_DIR, f"{sid}.json")
        data = {"id": sid, "created": time.time(), "messages": [], "metadata": {}}
        with open(path, "w") as f: json.dump(data, f)
        return sid
    
    def get(self, sid: str) -> Optional[dict]:
        path = os.path.join(SESSIONS_DIR, f"{sid}.json")
        if not os.path.exists(path): return None
        with open(path) as f: return json.load(f)
    
    def save_message(self, sid: str, message: dict):
        session = self.get(sid)
        if not session:
            sid = self.create()
            session = self.get(sid)
        session["messages"].append({**message, "timestamp": time.time()})
        path = os.path.join(SESSIONS_DIR, f"{sid}.json")
        with open(path, "w") as f: json.dump(session, f)
    
    def list_all(self) -> list:
        sessions = []
        for f in sorted(os.listdir(SESSIONS_DIR), reverse=True):
            if f.endswith(".json"):
                try:
                    with open(os.path.join(SESSIONS_DIR, f)) as fh:
                        d = json.load(fh)
                        msgs = d.get("messages", [])
                        first_user = next((m["content"][:80] for m in msgs if m.get("role") == "user"), "Empty")
                        sessions.append({
                            "id": d["id"], "created": d.get("created", 0),
                            "message_count": len(msgs), "preview": first_user,
                            "pinned": d.get("metadata", {}).get("pinned", False),
                        })
                except: pass
        return sessions
    
    def pin(self, sid: str, pinned: bool = True):
        session = self.get(sid)
        if session:
            session.setdefault("metadata", {})["pinned"] = pinned
            path = os.path.join(SESSIONS_DIR, f"{sid}.json")
            with open(path, "w") as f: json.dump(session, f)
    
    def delete(self, sid: str):
        path = os.path.join(SESSIONS_DIR, f"{sid}.json")
        if os.path.exists(path): os.remove(path)
    
    async def save_to_drive(self, sid: str, drive) -> dict:
        session = self.get(sid)
        if not session: return {"error": "Session not found"}
        folder_id = await drive.create_folder(f"ResearchAgent_{sid[:20]}")
        if folder_id:
            await drive.upload_file("session.json", json.dumps(session, indent=2), "application/json", parent_id=folder_id)
        return {"folder_id": folder_id, "status": "saved"}
    
    async def load_from_drive(self, sid: str, drive) -> Optional[dict]:
        folders = await drive.list_folders(f"ResearchAgent_{sid[:20]}")
        if not folders: return None
        files = await drive.list_files(folders[0]["id"])
        for f in files:
            if f["name"] == "session.json":
                content = await drive.read_file(f["id"])
                if content.get("content"):
                    try: return json.loads(content["content"])
                    except: pass
        return None
