"""
Paper Downloader — Uses Europe PMC fullTextUrlList approach (proven working).
Called AFTER search_pubmed/search_scopus finds papers and user selects them.
Downloads open-access PDFs to Drive. Creates compiled abstracts for the rest.
"""
import httpx
import asyncio
import random
from typing import List, Dict

EUROPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


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
    Download papers that were found by search_pubmed/search_scopus.
    For each paper: search Europe PMC by PMID/DOI → check isOpenAccess → get PDF from fullTextUrlList → download.
    Creates Compiled_Abstracts doc for non-downloadable papers.
    """
    downloaded = []
    no_access = []

    for i, paper in enumerate(papers):
        # Rate limiting: 4-second gap between each paper
        if i > 0:
            await asyncio.sleep(4)

        pmid = paper.get("pmid", "")
        doi = paper.get("doi", "")
        title = paper.get("title", "Unknown")
        authors = paper.get("authors", "Unknown")
        abstract = paper.get("abstract", "")
        year = paper.get("year", "")
        journal = paper.get("journal", "")

        # Build safe filename: FirstAuthor_Year.pdf
        first_author = "".join(c for c in authors.split(",")[0].split(" ")[0] if c.isalnum()) or "Author"
        filename = f"{first_author}_{year}.pdf"

        # ── Search Europe PMC for this paper to find PDF URL ──
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
                        # Get PDF URL from fullTextUrlList (proven approach)
                        ftl = res.get("fullTextUrlList", {}).get("fullTextUrl", [])
                        for ft in ftl:
                            if ft.get("documentStyle") == "pdf" and ft.get("availability") == "Open access":
                                pdf_url = ft.get("url")
                                break
                        # Fallback: PMC render URL
                        if not pdf_url and res.get("pmcid"):
                            pdf_url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={res['pmcid']}&blobtype=pdf"
                        # Grab abstract if we don't have one
                        if not abstract:
                            abstract = res.get("abstractText", "")
                        if pdf_url:
                            break
        except:
            pass

        # ── Download the PDF if URL found ──
        if pdf_url:
            try:
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    r = await client.get(pdf_url)
                    if r.status_code == 200 and len(r.content) > 1000:
                        file_id = await upload_with_retry(drive, filename, r.content, "application/pdf", folder_id)
                        if file_id:
                            downloaded.append({
                                "title": title, "filename": filename, "file_id": file_id,
                                "status": "downloaded",
                                "drive_url": f"https://drive.google.com/file/d/{file_id}/view",
                            })
                            continue
            except:
                pass

        # If we get here, paper could not be downloaded
        no_access.append({
            "title": title, "authors": authors, "abstract": abstract,
            "pmid": pmid, "doi": doi, "journal": journal, "year": year,
        })

    # ── Create Compiled Abstracts doc for non-downloadable papers ──
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

        # References section
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
