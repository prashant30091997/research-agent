"""
Paper Downloader — Based on proven Europe PMC approach.
Uses Europe PMC fullTextUrlList for open-access PDFs.
Creates compiled abstracts doc for non-downloadable papers.
Exponential backoff for Drive uploads. 4-sec delay between downloads.
"""
import httpx
import json
import asyncio
import time
import random
from typing import List, Dict

EUROPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


async def search_and_download(drive, query: str, folder_id: str, min_papers: int = 10) -> dict:
    """
    All-in-one: Search Europe PMC → find open-access PDFs → download to Drive.
    This mirrors the proven working approach from the user's original tool.
    """
    # Step 1: Search Europe PMC with core results (includes fullTextUrlList)
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(EUROPMC_SEARCH, params={
            "query": query, "format": "json", "resultType": "core", "pageSize": 50
        })
        results = r.json().get("resultList", {}).get("result", [])
    
    if not results:
        return {"error": "No papers found", "downloaded": [], "no_access": [], "total": 0}
    
    # Step 2: Separate open-access from non-open-access
    download_queue = []
    no_access_queue = []
    
    for paper in results[:min_papers * 3]:  # search more, filter down
        title = paper.get("title", "No Title")
        abstract = paper.get("abstractText", "")
        authors = paper.get("authorString", "Unknown")
        year = paper.get("pubYear", "")
        journal = paper.get("journalTitle", "")
        doi = paper.get("doi", "")
        pmid = paper.get("pmid", "")
        pmcid = paper.get("pmcid", "")
        
        # Build safe filename
        first_author = "".join(c for c in authors.split(",")[0].split(" ")[0] if c.isalnum()) or "Author"
        filename = f"{first_author}_{year}.pdf"
        
        paper_info = {
            "title": title, "abstract": abstract, "authors": authors,
            "year": year, "journal": journal, "doi": doi, "pmid": pmid,
            "pmcid": pmcid, "filename": filename,
        }
        
        # Check for open-access PDF URL
        pdf_url = None
        if paper.get("isOpenAccess") == "Y":
            full_text_list = paper.get("fullTextUrlList", {}).get("fullTextUrl", [])
            # Prefer PDF, then any available format
            for ft in full_text_list:
                if ft.get("documentStyle") == "pdf" and ft.get("availability") == "Open access":
                    pdf_url = ft.get("url")
                    break
            # Fallback: try PMC PDF URL
            if not pdf_url and pmcid:
                pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf"
        
        if pdf_url:
            paper_info["pdf_url"] = pdf_url
            download_queue.append(paper_info)
        else:
            no_access_queue.append(paper_info)
    
    # Step 3: Download PDFs with delays and retry
    downloaded = []
    failed = []
    
    for i, paper in enumerate(download_queue):
        # Rate limiting: 4 second gap
        if i > 0:
            await asyncio.sleep(4)
        
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                r = await client.get(paper["pdf_url"])
                if r.status_code == 200 and len(r.content) > 1000:
                    # Upload to Drive with retry
                    file_id = await upload_with_retry(drive, paper["filename"], r.content, "application/pdf", folder_id)
                    if file_id:
                        downloaded.append({
                            **paper, "status": "downloaded", "file_id": file_id,
                            "drive_url": f"https://drive.google.com/file/d/{file_id}/view",
                        })
                        continue
            # If we get here, download failed
            failed.append(paper)
            no_access_queue.append(paper)
        except Exception as e:
            failed.append({**paper, "error": str(e)[:100]})
            no_access_queue.append(paper)
    
    # Step 4: Create compiled abstracts doc for non-downloadable papers
    metadata_doc_url = None
    if no_access_queue:
        html_parts = [
            "<h1>Compiled Abstracts</h1>",
            f"<p><em>Papers where full-text PDF was not available as open-access. "
            f"You may access these through your institution's library.</em></p>",
            f"<p>Query: {query}</p><hr/>",
        ]
        
        for j, p in enumerate(no_access_queue, 1):
            html_parts.append(f"<h2>{j}. {p.get('title', 'Untitled')}</h2>")
            html_parts.append(f"<p><strong>Authors:</strong> {p.get('authors', '')}</p>")
            if p.get("journal"): html_parts.append(f"<p><strong>Journal:</strong> {p['journal']} ({p.get('year', '')})</p>")
            if p.get("pmid"): html_parts.append(f'<p><strong>PMID:</strong> <a href="https://pubmed.ncbi.nlm.nih.gov/{p["pmid"]}/">{p["pmid"]}</a></p>')
            if p.get("doi"): html_parts.append(f"<p><strong>DOI:</strong> {p['doi']}</p>")
            if p.get("abstract"):
                html_parts.append(f"<h3>Abstract</h3><p>{p['abstract']}</p>")
            html_parts.append("<hr/>")
        
        # References
        html_parts.append("<h2>References</h2><ol>")
        for p in no_access_queue:
            ref = f"{p.get('authors', 'Unknown')}. {p.get('title', '')}. <em>{p.get('journal', '')}</em>. {p.get('year', '')}."
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
        "no_access": [{"title": p["title"], "authors": p["authors"], "pmid": p.get("pmid", "")} for p in no_access_queue],
        "total_searched": len(results),
        "total_downloaded": len(downloaded),
        "total_no_access": len(no_access_queue),
        "metadata_doc": metadata_doc_url,
        "summary": f"Downloaded {len(downloaded)} open-access papers. {len(no_access_queue)} papers without open access"
            + (f" (abstracts saved to Compiled_Abstracts doc)" if metadata_doc_url else ""),
    }


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
    """Download specific papers by their PMIDs/DOIs. Uses Europe PMC to find PDFs."""
    downloaded = []
    no_access = []
    
    for i, paper in enumerate(papers):
        if i > 0:
            await asyncio.sleep(4)  # Rate limiting
        
        pmid = paper.get("pmid", "")
        pmcid = paper.get("pmcid", "")
        doi = paper.get("doi", "")
        title = paper.get("title", "Unknown")
        authors = paper.get("authors", "Unknown")
        abstract = paper.get("abstract", "")
        
        # Search Europe PMC for this specific paper
        pdf_url = None
        try:
            query = f"EXT_ID:{pmid}" if pmid else (f"DOI:{doi}" if doi else title[:80])
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                r = await client.get(EUROPMC_SEARCH, params={
                    "query": query, "format": "json", "resultType": "core", "pageSize": 3
                })
                results = r.json().get("resultList", {}).get("result", [])
                
                for res in results:
                    if res.get("isOpenAccess") == "Y":
                        ftl = res.get("fullTextUrlList", {}).get("fullTextUrl", [])
                        for ft in ftl:
                            if ft.get("documentStyle") == "pdf":
                                pdf_url = ft.get("url")
                                break
                        if not pdf_url and res.get("pmcid"):
                            pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={res['pmcid']}&blobtype=pdf"
                        if not abstract:
                            abstract = res.get("abstractText", "")
                        if pdf_url:
                            break
        except:
            pass
        
        if pdf_url:
            try:
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    r = await client.get(pdf_url)
                    if r.status_code == 200 and len(r.content) > 1000:
                        first_author = "".join(c for c in authors.split(",")[0].split(" ")[0] if c.isalnum()) or "Author"
                        filename = f"{first_author}_{paper.get('year', 'XXXX')}.pdf"
                        file_id = await upload_with_retry(drive, filename, r.content, "application/pdf", folder_id)
                        if file_id:
                            downloaded.append({
                                "title": title, "filename": filename, "file_id": file_id, "status": "downloaded",
                                "drive_url": f"https://drive.google.com/file/d/{file_id}/view",
                            })
                            continue
            except:
                pass
        
        no_access.append({"title": title, "authors": authors, "abstract": abstract, "pmid": pmid, "doi": doi,
                          "journal": paper.get("journal", ""), "year": paper.get("year", "")})
    
    # Create compiled abstracts for non-downloadable
    metadata_doc_url = None
    if no_access and drive and folder_id:
        html_parts = ["<h1>Compiled Abstracts</h1>",
            "<p><em>Papers where full-text PDF was not available as open-access.</em></p><hr/>"]
        for j, p in enumerate(no_access, 1):
            html_parts.append(f"<h2>{j}. {p['title']}</h2>")
            html_parts.append(f"<p><strong>Authors:</strong> {p['authors']}</p>")
            if p.get("journal"): html_parts.append(f"<p><strong>Journal:</strong> {p['journal']} ({p.get('year','')})</p>")
            if p.get("pmid"): html_parts.append(f'<p><strong>PMID:</strong> {p["pmid"]}</p>')
            if p.get("abstract"): html_parts.append(f"<h3>Abstract</h3><p>{p['abstract']}</p>")
            html_parts.append("<hr/>")
        html_parts.append("<h2>References</h2><ol>")
        for p in no_access:
            html_parts.append(f"<li>{p['authors']}. {p['title']}. <em>{p.get('journal','')}</em>. {p.get('year','')}. PMID: {p.get('pmid','N/A')}</li>")
        html_parts.append("</ol>")
        try:
            from tools.create_doc import create_google_doc
            doc_result = await create_google_doc(drive, "Compiled_Abstracts", "\n".join(html_parts), folder_id)
            metadata_doc_url = doc_result.get("url")
        except:
            pass
    
    return {
        "downloaded": downloaded,
        "no_access": no_access,
        "total": len(papers),
        "total_downloaded": len(downloaded),
        "total_no_access": len(no_access),
        "metadata_doc": metadata_doc_url,
        "summary": f"Downloaded {len(downloaded)} papers. {len(no_access)} not open-access"
            + (f" (abstracts compiled in doc)" if metadata_doc_url else ""),
    }


async def get_paper_full_text(drive, paper: dict, folder_id: str = None) -> dict:
    """Get full text of a paper from Europe PMC."""
    pmid = paper.get("pmid", "")
    title = paper.get("title", "")
    
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        # Try Europe PMC full text XML
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
        
        # Try PubMed abstract
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
            "content": paper.get("abstract", f"[No text available for: {title}]"), "source": "None"}
