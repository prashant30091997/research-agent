"""Google Drive Operations — List folders, files, read content, create folders, upload files"""
import httpx, json

DRIVE_API = "https://www.googleapis.com/drive/v3/files"
UPLOAD_API = "https://www.googleapis.com/upload/drive/v3/files"

class DriveOps:
    def __init__(self, token: str):
        self.token = token
        self.headers = {"Authorization": f"Bearer {token}"}
    
    async def list_folders(self, query: str = "") -> list:
        q = "mimeType='application/vnd.google-apps.folder' and trashed=false"
        if query: q += f" and name contains '{query}'"
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(DRIVE_API, params={
                "q": q, "fields": "files(id,name,modifiedTime)",
                "pageSize": 30, "orderBy": "modifiedTime desc",
                "supportsAllDrives": "true", "includeItemsFromAllDrives": "true",
            }, headers=self.headers)
            return [{"id": f["id"], "name": f["name"], "modified": f.get("modifiedTime", "")[:10]}
                    for f in r.json().get("files", [])]
    
    async def list_files(self, folder_id: str) -> list:
        q = f"'{folder_id}' in parents and trashed=false"
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.get(DRIVE_API, params={
                "q": q, "fields": "files(id,name,mimeType,size,modifiedTime)",
                "pageSize": 100, "orderBy": "name",
                "supportsAllDrives": "true", "includeItemsFromAllDrives": "true",
            }, headers=self.headers)
            files = []
            for f in r.json().get("files", []):
                ext = "." + f["name"].rsplit(".", 1)[-1].lower() if "." in f["name"] else ""
                cat = "code" if ext in [".py",".ipynb",".m",".r",".js"] else \
                      "data" if ext in [".mat",".csv",".xlsx",".json",".hdf5",".npy",".edf",".parquet"] else \
                      "doc" if ext in [".pdf",".docx",".txt",".md",".pptx"] else "other"
                files.append({
                    "id": f["id"], "name": f["name"], "ext": ext, "cat": cat,
                    "size": int(f.get("size", 0)),
                    "size_str": self._fmt_size(int(f.get("size", 0))),
                    "mime": f.get("mimeType", ""),
                })
            return files
    
    async def read_file(self, file_id: str) -> dict:
        """Read file content — handles text files and Google Docs export"""
        async with httpx.AsyncClient(timeout=60) as c:
            # Try direct download first (for text files)
            try:
                r = await c.get(f"{DRIVE_API}/{file_id}?alt=media", headers=self.headers)
                if r.status_code == 200 and "text" in r.headers.get("content-type", ""):
                    return {"content": r.text[:10000], "chars": len(r.text)}
            except: pass
            # Try Google export (for Docs, Sheets, etc.)
            try:
                r = await c.get(f"{DRIVE_API}/{file_id}/export", params={"mimeType": "text/plain"}, headers=self.headers)
                if r.status_code == 200:
                    return {"content": r.text[:10000], "chars": len(r.text)}
            except: pass
            return {"content": None, "error": "Could not read file (may be binary)"}
    
    async def create_folder(self, name: str, parent_id: str = None) -> str:
        metadata = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent_id: metadata["parents"] = [parent_id]
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(DRIVE_API, json=metadata, headers={**self.headers, "Content-Type": "application/json"})
            d = r.json()
            return d.get("id")
    
    async def upload_file(self, name: str, content: str, mime_type: str = "text/plain",
                         convert_to: str = None, parent_id: str = None) -> dict:
        """Upload content as a file. If convert_to is set, creates a Google Workspace file."""
        metadata = {"name": name}
        if convert_to: metadata["mimeType"] = convert_to
        if parent_id: metadata["parents"] = [parent_id]
        
        boundary = f"----RA{id(content)}"
        body = (
            f"--{boundary}\r\n"
            f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{json.dumps(metadata)}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: {mime_type}; charset=UTF-8\r\n\r\n"
            f"{content}\r\n"
            f"--{boundary}--"
        )
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(
                f"{UPLOAD_API}?uploadType=multipart",
                content=body.encode(),
                headers={**self.headers, "Content-Type": f"multipart/related; boundary={boundary}"},
            )
            d = r.json()
            file_id = d.get("id")
            if not file_id: return {"error": d.get("error", {}).get("message", "Upload failed")}
            return {"id": file_id, "name": name}
    
    @staticmethod
    def _fmt_size(b):
        if b > 1e9: return f"{b/1e9:.1f} GB"
        if b > 1e6: return f"{b/1e6:.1f} MB"
        return f"{b/1e3:.1f} KB"
    
    async def upload_binary(self, name: str, content: bytes, mime_type: str = "application/pdf",
                            parent_id: str = None) -> str:
        """Upload binary content (PDFs, images) to Drive. Returns file ID."""
        import base64
        metadata = {"name": name}
        if parent_id: metadata["parents"] = [parent_id]
        
        boundary = f"----RAbin{id(content)}"
        meta_json = json.dumps(metadata)
        
        # Build multipart body with binary content
        body = (
            f"--{boundary}\r\n"
            f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
            f"{meta_json}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: {mime_type}\r\n"
            f"Content-Transfer-Encoding: binary\r\n\r\n"
        ).encode() + content + f"\r\n--{boundary}--".encode()
        
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(
                f"{UPLOAD_API}?uploadType=multipart",
                content=body,
                headers={**self.headers, "Content-Type": f"multipart/related; boundary={boundary}"},
            )
            d = r.json()
            return d.get("id")
