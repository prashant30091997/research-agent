"""
Paper Downloader — Downloads PDFs using URLs already found by search_pubmed.
DOES NOT re-search. Uses pdf_url from the paper object directly.
Creates Compiled_Abstracts doc for papers without open-access PDFs.
"""
import httpx
import asyncio
import random
from typing import List, Dict


async def upload_with_retry(drive, filename: str, content: bytes, mime_type: str, folder_id: str, max_retries: int = 5) -> str:
    """Upload to Drive with exponential backoff (handles sync collisions)."""
    for n in range(max_retries):
        try:
            file_id = await drive.upload_binary(filename, content, mime_type, folder_id)
            if file_id:
                return file_id
        except Exception as e:
            if n == max_retries - 1:
                raise e
            wait = (2 ** n) + random.random()
            await asyncio.sleep(wait)
    return None


async def download_papers_to_drive(drive, papers: List[dict], folder_id: str) -> dict:
    """
    Download papers using pdf_url already attached by search_pubmed.
    NO RE-SEARCHING. Just downloads from the URL in each paper object.
    Papers without pdf_url go into Compiled_Abstracts doc.
    """
    downloaded = []
    no_access = []

    for i, paper in enumerate(papers):
        # Rate limiting: 4-second gap
        if i > 0:
            await asyncio.sleep(4)

        title = paper.get("title", "Unknown")
        authors = paper.get("authors", "Unknown")
        pmid = paper.get("pmid", "")
        doi = paper.get("doi", "")
        year = paper.get("year", "")
        journal = paper.get("journal", "")
        abstract = paper.get("abstract", "")
        pdf_url = paper.get("pdf_url")  # Already set by search_pubmed

        # Build safe filename
        first_author = "".join(c for c in authors.split(",")[0].split(" ")[0] if c.isalnum()) or "Author"
        filename = f"{first_author}_{year}.pdf"

        if pdf_url:
            # Download the PDF directly — no searching
            try:
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    r = await client.get(pdf_url)
                    if r.status_code == 200 and len(r.content) > 1000:
                        file_id = await upload_with_retry(drive, filename, r.content, "application/pdf", folder_id)
                        if file_id:
                            downloaded.append({
                                "title": title, "filename": filename, "file_id": file_id,
                                "status": "downloaded", "pmid": pmid,
                                "drive_url": f"https://drive.google.com/file/d/{file_id}/view",
                            })
                            continue
            except:
                pass

        # Paper could not be downloaded — add to no_access list
        no_access.append({
            "title": title, "authors": authors, "abstract": abstract,
            "pmid": pmid, "doi": doi, "journal": journal, "year": year,
        })

    # Create Compiled_Abstracts Google Doc for non-downloadable papers
    metadata_doc_url = None
    if no_access and drive and folder_id:
        html_parts = [
            "<h1>Compiled Abstracts</h1>",
            "<p><em>Papers where full-text PDF was not available as open-access. "
            "You may access these through your institution's library.</em></p><hr/>",
        ]
        for j, p in enumerate(no_access, 1):
            html_parts.append(f"<h2>{j}. {p['title']}</h2>")
            html_parts.append(f"<p><strong>Authors:</strong> {p['authors']}</p>")
            if p.get("journal"):
                html_parts.append(f"<p><strong>Journal:</strong> {p['journal']} ({p.get('year', '')})</p>")
            if p.get("pmid"):
                html_parts.append(f'<p><strong>PMID:</strong> <a href="https://pubmed.ncbi.nlm.nih.gov/{p["pmid"]}/">{p["pmid"]}</a></p>')
            if p.get("doi"):
                html_parts.append(f"<p><strong>DOI:</strong> {p['doi']}</p>")
            if p.get("abstract"):
                html_parts.append(f"<h3>Abstract</h3><p>{p['abstract']}</p>")
            html_parts.append("<hr/>")

        html_parts.append("<h2>References</h2><ol>")
        for p in no_access:
            ref = f"{p['authors']}. {p['title']}. <em>{p.get('journal', '')}</em>. {p.get('year', '')}."
            if p.get("doi"): ref += f" DOI: {p['doi']}."
            if p.get("pmid"): ref += f" PMID: {p['pmid']}."
            html_parts.append(f"<li>{ref}</li>")
        html_parts.append("</ol>")

        try:
            from tools.create_doc import create_google_doc
            doc_result = await create_google_doc(drive, "Compiled_Abstracts", "\n".join(html_parts), folder_id)
            metadata_doc_url = doc_result.get("url")
        except:
            pass

    return {
        "downloaded": downloaded,
        "no_access": [{"title": p["title"], "authors": p["authors"], "pmid": p.get("pmid", "")} for p in no_access],
        "total": len(papers),
        "total_downloaded": len(downloaded),
        "total_no_access": len(no_access),
        "metadata_doc": metadata_doc_url,
        "summary": f"Downloaded {len(downloaded)} papers. {len(no_access)} not open-access"
            + (f" (abstracts compiled in doc)" if metadata_doc_url else ""),
    }


async def get_paper_full_text(drive, paper: dict, folder_id: str = None) -> dict:
    """Get full text of a paper from Europe PMC. NO re-searching."""
    pmid = paper.get("pmid", "")
    title = paper.get("title", "")

    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        if pmid:
            try:
                r = await client.get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmid}/fullTextXML")
                if r.status_code == 200 and len(r.text) > 500:
                    import re
                    text = re.sub(r'<[^>]+>', ' ', r.text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    return {"pmid": pmid, "title": title, "has_full_text": True,
                            "content": text[:15000], "source": "Europe PMC"}
            except:
                pass

        if pmid:
            try:
                r = await client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
                                     params={"db": "pubmed", "id": pmid, "retmode": "xml"})
                if r.status_code == 200:
                    import re
                    match = re.search(r'<AbstractText[^>]*>(.*?)</AbstractText>', r.text, re.DOTALL)
                    if match:
                        abstract = re.sub(r'<[^>]+>', ' ', match.group(1)).strip()
                        return {"pmid": pmid, "title": title, "has_full_text": False,
                                "content": abstract, "source": "PubMed Abstract"}
            except:
                pass

    return {"pmid": pmid, "title": title, "has_full_text": False,
            "content": paper.get("abstract", f"[No text for: {title}]"), "source": "Cached abstract"}
