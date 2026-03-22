"""Read files from Google Drive"""
from tools.drive_ops import DriveOps

async def read_drive_files(drive: DriveOps, folder_id: str) -> dict:
    files = await drive.list_files(folder_id)
    classified = {"code": [], "data": [], "doc": [], "other": []}
    for f in files:
        classified.get(f["cat"], classified["other"]).append(f)
    return {"files": files, "classified": classified, "total": len(files)}

async def read_file_content(drive: DriveOps, file_id: str, file_name: str = "") -> dict:
    result = await drive.read_file(file_id)
    return {"name": file_name, **result}
