"""Create or UPDATE Google Docs/Sheets/Slides via Drive API.
If a file with the same name already exists in the folder, it UPDATES that file.
Otherwise it creates a new one."""

async def create_google_doc(drive, name: str, html_content: str, folder_id: str = None) -> dict:
    """Create or update a Google Doc. If name exists in folder, updates it."""
    # Check if file already exists
    existing_id = await drive.find_file(name, folder_id) if folder_id else None
    
    if existing_id:
        # UPDATE existing file
        result = await drive.update_file(existing_id, html_content, "text/html")
        result["url"] = f"https://docs.google.com/document/d/{existing_id}/edit"
        result["type"] = "google_doc"
        result["action"] = "updated"
        return result
    else:
        # CREATE new file
        result = await drive.upload_file(name, html_content, "text/html",
                                          convert_to="application/vnd.google-apps.document",
                                          parent_id=folder_id)
        if result.get("id"):
            result["url"] = f"https://docs.google.com/document/d/{result['id']}/edit"
            result["type"] = "google_doc"
            result["action"] = "created"
        return result

async def create_google_sheet(drive, name: str, csv_data: str, folder_id: str = None) -> dict:
    """Create or update a Google Sheet."""
    existing_id = await drive.find_file(name, folder_id) if folder_id else None
    
    if existing_id:
        result = await drive.update_file(existing_id, csv_data, "text/csv")
        result["url"] = f"https://docs.google.com/spreadsheets/d/{existing_id}/edit"
        result["type"] = "google_sheet"
        result["action"] = "updated"
        return result
    else:
        result = await drive.upload_file(name, csv_data, "text/csv",
                                          convert_to="application/vnd.google-apps.spreadsheet",
                                          parent_id=folder_id)
        if result.get("id"):
            result["url"] = f"https://docs.google.com/spreadsheets/d/{result['id']}/edit"
            result["type"] = "google_sheet"
            result["action"] = "created"
        return result

async def create_google_slides(drive, name: str, html_content: str, folder_id: str = None) -> dict:
    """Create or update Google Slides."""
    existing_id = await drive.find_file(name, folder_id) if folder_id else None
    
    if existing_id:
        result = await drive.update_file(existing_id, html_content, "text/html")
        result["url"] = f"https://docs.google.com/presentation/d/{existing_id}/edit"
        result["type"] = "google_slides"
        result["action"] = "updated"
        return result
    else:
        result = await drive.upload_file(name, html_content, "text/html",
                                          convert_to="application/vnd.google-apps.presentation",
                                          parent_id=folder_id)
        if result.get("id"):
            result["url"] = f"https://docs.google.com/presentation/d/{result['id']}/edit"
            result["type"] = "google_slides"
            result["action"] = "created"
        return result
