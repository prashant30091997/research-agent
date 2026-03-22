"""
Paper Downloader — Downloads full-text PDFs from open-access sources
Sources: PubMed Central (PMC), Unpaywall, Europe PMC, arXiv, bioRxiv
Saves to Google Drive folder
"""
import httpx
import json
from typing import List, Dict, Optional

# PMC provides free full-text articles
PMC_SEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi"
PMC_FETCH = "https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi"
UNPAYWALL_API = "https://api.unpaywall.org/v2"
EUROPMC_API = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


async def find_open_access_url(pmid: str = "", doi: str = "", title: str = "") -> Optional[str]:
    """Try multiple sources to find a free PDF URL for a paper"""
    
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        # Strategy 1: PubMed Central (PMC) — check if paper has free full text
        if pmid:
            try:
                r = await client.get(PMC_SEARCH, params={
                    "dbfrom": "pubmed", "db": "pmc", "id": pmid,
                    "retmode": "json", "linkname": "pubmed_pmc"
                })
                d = r.json()
                links = d.get("linksets", [{}])[0].get("linksetdbs", [])
                for ls in links:
                    pmc_ids = [l.get("id") for l in ls.get("links", [])]
                    if pmc_ids:
                        pmc_id = pmc_ids[0]
                        # Get PDF URL from PMC
                        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmc_id}/pdf/"
                        return pdf_url
            except:
                pass
        
        # Strategy 2: Unpaywall (finds legal open-access versions)
        if doi:
            try:
                r = await client.get(f"{UNPAYWALL_API}/{doi}", params={
                    "email": "research-agent@example.com"  # Unpaywall requires email
                })
                if r.status_code == 200:
                    d = r.json()
                    # Check for best open access location
                    best = d.get("best_oa_location", {})
                    if best:
                        url = best.get("url_for_pdf") or best.get("url_for_landing_page")
                        if url:
                            return url
                    # Check all OA locations
                    for loc in d.get("oa_locations", []):
                        url = loc.get("url_for_pdf")
                        if url:
                            return url
            except:
                pass
        
        # Strategy 3: Europe PMC (has many open access papers)
        if pmid or title:
            try:
                query = f"EXT_ID:{pmid}" if pmid else title[:100]
                r = await client.get(EUROPMC_API, params={
                    "query": query, "format": "json", "resultType": "core"
                })
                d = r.json()
                results = d.get("resultList", {}).get("result", [])
                for res in results:
                    if res.get("isOpenAccess") == "Y":
                        pmcid = res.get("pmcid")
                        if pmcid:
                            return f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf"
                        full_text_urls = res.get("fullTextUrlList", {}).get("fullTextUrl", [])
                        for ftu in full_text_urls:
                            if ftu.get("documentStyle") == "pdf" and ftu.get("availability") == "Open access":
                                return ftu.get("url")
            except:
                pass
    
    return None


async def download_paper_to_drive(drive, paper: dict, folder_id: str) -> dict:
    """Download a single paper's PDF and save to Drive folder"""
    pmid = paper.get("pmid", "")
    doi = paper.get("doi", "")
    title = paper.get("title", "Unknown")
    
    # Find open access URL
    pdf_url = await find_open_access_url(pmid=pmid, doi=doi, title=title)
    
    if not pdf_url:
        return {
            "pmid": pmid, "title": title, "status": "no_open_access",
            "message": f"No open-access version found for: {title[:60]}"
        }
    
    # Download the PDF
    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            r = await client.get(pdf_url)
            if r.status_code == 200:
                content_type = r.headers.get("content-type", "")
                
                if "pdf" in content_type or pdf_url.endswith(".pdf"):
                    # Save PDF to Drive
                    safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)[:60].strip()
                    filename = f"{safe_title}_{pmid or 'paper'}.pdf"
                    
                    # Upload as binary to Drive
                    import base64
                    file_id = await drive.upload_binary(filename, r.content, "application/pdf", folder_id)
                    
                    if file_id:
                        return {
                            "pmid": pmid, "title": title, "status": "downloaded",
                            "filename": filename, "file_id": file_id,
                            "url": f"https://drive.google.com/file/d/{file_id}/view",
                            "source_url": pdf_url
                        }
                
                # If not PDF, might be HTML full text — save as HTML
                if "html" in content_type:
                    safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in title)[:60].strip()
                    filename = f"{safe_title}_{pmid or 'paper'}.html"
                    
                    text_content = r.text[:50000]  # Limit size
                    result = await drive.upload_file(filename, text_content, "text/html", parent_id=folder_id)
                    
                    if result:
                        return {
                            "pmid": pmid, "title": title, "status": "downloaded_html",
                            "filename": filename, "file_id": result,
                            "source_url": pdf_url
                        }
    except Exception as e:
        return {
            "pmid": pmid, "title": title, "status": "download_failed",
            "message": f"Download failed: {str(e)[:100]}"
        }
    
    return {
        "pmid": pmid, "title": title, "status": "failed",
        "message": "Could not download file"
    }


async def download_papers_to_drive(drive, papers: List[dict], folder_id: str) -> dict:
    """Download multiple papers with delays. Creates a separate doc for non-open-access papers."""
    import asyncio
    
    results = {
        "downloaded": [],
        "no_access": [],
        "failed": [],
        "total": len(papers),
    }
    
    for i, paper in enumerate(papers):
        # Rate limiting: 4 second gap between downloads
        if i > 0:
            await asyncio.sleep(4)
        
        result = await download_paper_to_drive(drive, paper, folder_id)
        
        if result["status"] == "downloaded" or result["status"] == "downloaded_html":
            results["downloaded"].append(result)
        elif result["status"] == "no_open_access":
            results["no_access"].append({**result, **paper})  # include full paper metadata
        else:
            results["failed"].append({**result, **paper})
    
    # ── Create a Google Doc with non-open-access paper info ──
    unavailable = results["no_access"] + results["failed"]
    if unavailable and drive and folder_id:
        html_parts = [
            "<h1>Papers Without Open Access</h1>",
            f"<p><em>Generated by ResearchAgent — {len(unavailable)} papers that could not be downloaded as open-access PDFs. "
            "You may be able to access these through your institution's library.</em></p><hr/>",
        ]
        
        for j, p in enumerate(unavailable, 1):
            title = p.get("title", "Untitled")
            authors = p.get("authors", "")
            journal = p.get("journal", "")
            year = p.get("year", "")
            pmid = p.get("pmid", "")
            doi = p.get("doi", "")
            abstract = p.get("abstract", "")
            url = p.get("url", "")
            
            html_parts.append(f"<h2>{j}. {title}</h2>")
            html_parts.append(f"<p><strong>Authors:</strong> {authors}</p>")
            if journal: html_parts.append(f"<p><strong>Journal:</strong> {journal} ({year})</p>")
            if pmid: html_parts.append(f'<p><strong>PMID:</strong> <a href="https://pubmed.ncbi.nlm.nih.gov/{pmid}/">{pmid}</a></p>')
            if doi: html_parts.append(f'<p><strong>DOI:</strong> {doi}</p>')
            if url: html_parts.append(f'<p><strong>URL:</strong> <a href="{url}">{url}</a></p>')
            if abstract:
                html_parts.append(f"<h3>Abstract</h3><p>{abstract}</p>")
            html_parts.append("<hr/>")
        
        # Add references section
        html_parts.append("<h2>References</h2><ol>")
        for j, p in enumerate(unavailable, 1):
            ref = f"{p.get('authors', 'Unknown')}. {p.get('title', 'Untitled')}. <em>{p.get('journal', '')}</em>. {p.get('year', '')}."
            if p.get("doi"): ref += f" DOI: {p['doi']}"
            if p.get("pmid"): ref += f" PMID: {p['pmid']}"
            html_parts.append(f"<li>{ref}</li>")
        html_parts.append("</ol>")
        
        html_content = "\n".join(html_parts)
        
        try:
            # Use create_or_update pattern
            from tools.create_doc import create_google_doc
            doc_result = await create_google_doc(drive, "Papers_Without_Open_Access", html_content, folder_id)
            if doc_result.get("url"):
                results["metadata_doc"] = doc_result["url"]
                results["metadata_doc_action"] = doc_result.get("action", "created")
        except:
            pass
    
    results["summary"] = (
        f"Downloaded {len(results['downloaded'])} papers, "
        f"{len(results['no_access'])} not open-access"
        f"{' (saved to separate doc)' if results.get('metadata_doc') else ''}, "
        f"{len(results['failed'])} failed"
    )
    
    return results


async def get_paper_full_text(drive, paper: dict, folder_id: str = None) -> dict:
    """Get full text content of a paper — download if needed, then extract text"""
    pmid = paper.get("pmid", "")
    doi = paper.get("doi", "")
    title = paper.get("title", "")
    
    # Try Europe PMC for full text XML/text directly (no download needed)
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        if pmid:
            try:
                # Europe PMC provides full text for open access articles
                r = await client.get(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmid}/fullTextXML")
                if r.status_code == 200 and len(r.text) > 500:
                    # Extract text from XML (rough extraction)
                    import re
                    text = re.sub(r'<[^>]+>', ' ', r.text)
                    text = re.sub(r'\s+', ' ', text).strip()
                    return {
                        "pmid": pmid, "title": title, "has_full_text": True,
                        "content": text[:15000],  # Limit to ~15K chars for AI context
                        "source": "Europe PMC"
                    }
            except:
                pass
        
        # Try PubMed abstract as fallback
        if pmid:
            try:
                r = await client.get("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi", params={
                    "db": "pubmed", "id": pmid, "retmode": "xml"
                })
                if r.status_code == 200:
                    import re
                    # Extract abstract
                    abstract_match = re.search(r'<AbstractText[^>]*>(.*?)</AbstractText>', r.text, re.DOTALL)
                    abstract = abstract_match.group(1) if abstract_match else ""
                    abstract = re.sub(r'<[^>]+>', ' ', abstract).strip()
                    
                    if abstract:
                        return {
                            "pmid": pmid, "title": title, "has_full_text": False,
                            "content": abstract,
                            "source": "PubMed Abstract"
                        }
            except:
                pass
    
    return {
        "pmid": pmid, "title": title, "has_full_text": False,
        "content": f"[No text available for: {title}]",
        "source": "None"
    }
