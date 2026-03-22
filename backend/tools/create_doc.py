"""Create Google Docs/Sheets/Slides via Drive API conversion"""

async def create_google_doc(drive, name: str, html_content: str, folder_id: str = None) -> dict:
    result = await drive.upload_file(name, html_content, "text/html",
                                      convert_to="application/vnd.google-apps.document",
                                      parent_id=folder_id)
    if result.get("id"):
        result["url"] = f"https://docs.google.com/document/d/{result['id']}/edit"
        result["type"] = "google_doc"
    return result

async def create_google_sheet(drive, name: str, csv_data: str, folder_id: str = None) -> dict:
    result = await drive.upload_file(name, csv_data, "text/csv",
                                      convert_to="application/vnd.google-apps.spreadsheet",
                                      parent_id=folder_id)
    if result.get("id"):
        result["url"] = f"https://docs.google.com/spreadsheets/d/{result['id']}/edit"
        result["type"] = "google_sheet"
    return result

async def create_google_slides(drive, name: str, html_content: str, folder_id: str = None) -> dict:
    result = await drive.upload_file(name, html_content, "text/html",
                                      convert_to="application/vnd.google-apps.presentation",
                                      parent_id=folder_id)
    if result.get("id"):
        result["url"] = f"https://docs.google.com/presentation/d/{result['id']}/edit"
        result["type"] = "google_slides"
    return result
