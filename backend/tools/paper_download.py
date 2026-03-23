"""
Paper Downloader — All PDF finding + downloading logic lives here.
Called AFTER user selects papers. Does NOT re-search PubMed.
For each paper: finds PDF URL (5 strategies) → downloads → saves to Drive.
Creates Compiled_Abstracts doc for all papers (downloaded or not) for the review step.
"""
import httpx
import asyncio
import random
from typing import List, Dict

EUROPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


async def upload_with_retry(drive, filename: str, content: bytes, mime_type: str, folder_id: str, max_retries: int = 5) -> str:
    """Upload to Drive with exponential backoff."""
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


async def _find_pdf_url(client, paper: dict) -> str:
    """Try 5 strategies to find a PDF URL for a single paper. Returns URL or None."""
    doi = paper.get("doi", "")
    pmid = paper.get("pmid", "")
    pmcid = paper.get("pmcid", "")

    # If we don't have PMCID yet, do a quick Europe PMC lookup
    if not pmcid and (doi or pmid):
        try:
            query = f"DOI:{doi}" if doi else f"EXT_ID:{pmid} SRC:MED"
            r = await client.get(EUROPMC_SEARCH, params={
                "query": query, "format": "json", "resultType": "core", "pageSize": 1
            })
            results = r.json().get("resultList", {}).get("result", [])
            if results:
                res = results[0]
                pmcid = res.get("pmcid", "")
                paper["pmcid"] = pmcid
                # Also grab authors/abstract if missing
                if res.get("authorString") and (not paper.get("authors") or paper["authors"] == "Unknown"):
                    paper["authors"] = res["authorString"][:200]
                if not paper.get("abstract") and res.get("abstractText"):
                    paper["abstract"] = res["abstractText"][:2000]
                # Save fullTextUrlList for Strategy 3
                paper["_ftl"] = res.get("fullTextUrlList", {}).get("fullTextUrl", [])
        except:
            pass

    # ── Strategy 1: Europe PMC direct render by PMCID ──
    if pmcid:
        url = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={pmcid}&blobtype=pdf"
        try:
            r = await client.head(url, follow_redirects=True)
            ct = r.headers.get("content-type", "")
            if r.status_code == 200 and ("pdf" in ct or "octet" in ct):
                return url
        except:
            pass

    # ── Strategy 2: NCBI PMC PDF by PMCID ──
    if pmcid:
        url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
        try:
            r = await client.head(url, follow_redirects=True)
            ct = r.headers.get("content-type", "")
            if r.status_code == 200 and ("pdf" in ct or "octet" in ct):
                return url
        except:
            pass

    # ── Strategy 3: Europe PMC fullTextUrlList ──
    for ft in paper.get("_ftl", []):
        if ft.get("documentStyle") == "pdf":
            url = ft.get("url")
            if url:
                return url

    # ── Strategy 4: Unpaywall by DOI ──
    if doi:
        try:
            r = await client.get(f"https://api.unpaywall.org/v2/{doi}", params={
                "email": "research-agent@example.com"
            })
            if r.status_code == 200:
                d = r.json()
                best = d.get("best_oa_location") or {}
                url = best.get("url_for_pdf") or best.get("url_for_landing_page")
                if url:
                    return url
                for loc in d.get("oa_locations", []):
                    if loc.get("url_for_pdf"):
                        return loc["url_for_pdf"]
        except:
            pass

    # ── Strategy 5: Europe PMC fulltext XML URL (as last resort — not a PDF but has content) ──
    # We don't return this as pdf_url — it's for full text reading, not downloading.
    
    return None


async def download_papers_to_drive(drive, papers: List[dict], folder_id: str) -> dict:
    """
    For each paper:
    1. Find PDF URL (5 strategies)
    2. Download PDF → save to Drive
    3. Create Compiled_Abstracts doc for ALL papers (with clickable links for non-downloaded ones)
    """
    downloaded = []
    no_access = []

    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for i, paper in enumerate(papers):
            if i > 0:
                await asyncio.sleep(4)  # Rate limiting

            title = paper.get("title", "Unknown")
            authors = paper.get("authors", "Unknown")
            pmid = paper.get("pmid", "")
            doi = paper.get("doi", "")
            year = paper.get("year", "")
            journal = paper.get("journal", "")
            abstract = paper.get("abstract", "")

            # Build filename
            first_author = "".join(c for c in authors.split(",")[0].split(" ")[0] if c.isalnum()) or "Author"
            filename = f"{first_author}_{year}.pdf"

            # Find PDF URL
            pdf_url = await _find_pdf_url(client, paper)

            if pdf_url:
                try:
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

            # Not downloaded
            no_access.append({
                "title": title, "authors": paper.get("authors", authors),
                "abstract": paper.get("abstract", abstract),
                "pmid": pmid, "doi": doi, "journal": journal, "year": year,
                "pmcid": paper.get("pmcid", ""),
            })

    # ── Create Compiled_Abstracts doc for ALL papers ──
    # This includes BOTH downloaded and non-downloaded papers
    # The review step reads this + downloaded PDFs, deduplicating by title
    all_papers = []
    for p in downloaded:
        # Find full data from original papers list
        match = next((pp for pp in papers if pp.get("pmid") == p.get("pmid") or pp.get("title") == p.get("title")), {})
        all_papers.append({**match, "downloaded": True})
    for p in no_access:
        all_papers.append({**p, "downloaded": False})

    metadata_doc_url = None
    if all_papers and drive and folder_id:
        html_parts = [
            "<h1>Paper Compilation — Abstracts &amp; Download Links</h1>",
            f"<p><em>{len(downloaded)} papers downloaded as PDF. "
            f"{len(no_access)} papers need manual download. "
            f"{len(all_papers)} total papers compiled below.</em></p>",
            "<hr/>",
        ]

        # Section 1: Downloaded papers
        if downloaded:
            html_parts.append("<h2>Section A: Downloaded Papers (PDFs in folder)</h2>")
            for j, p in enumerate(downloaded, 1):
                match = next((pp for pp in papers if pp.get("pmid") == p.get("pmid") or pp.get("title") == p.get("title")), {})
                t = p.get("title", "")
                a = match.get("authors", p.get("authors", "Unknown"))
                ab = match.get("abstract", "")
                html_parts.append(f"<h3>{j}. {t} ✅</h3>")
                html_parts.append(f"<p><strong>Authors:</strong> {a}</p>")
                if match.get("journal"): html_parts.append(f"<p><strong>Journal:</strong> {match['journal']} ({match.get('year','')})</p>")
                html_parts.append(f'<p><strong>PDF:</strong> <a href="{p.get("drive_url","")}">Open in Drive</a></p>')
                if ab: html_parts.append(f"<h4>Abstract</h4><p>{ab}</p>")
                html_parts.append("<hr/>")

        # Section 2: Papers needing manual download
        if no_access:
            html_parts.append("<h2>Section B: Papers Requiring Manual Download</h2>")
            for j, p in enumerate(no_access, 1):
                title_text = p.get("title", "Untitled")
                authors_text = p.get("authors", "Unknown")
                abstract_text = p.get("abstract", "")
                html_parts.append(f"<h3>{j}. {title_text} ⚠️</h3>")
                html_parts.append(f"<p><strong>Authors:</strong> {authors_text}</p>")
                if p.get("journal"): html_parts.append(f"<p><strong>Journal:</strong> {p['journal']} ({p.get('year','')})</p>")
                html_parts.append("<p><strong>Download Links:</strong></p><ul>")
                if p.get("pmid"):
                    html_parts.append(f'<li><a href="https://pubmed.ncbi.nlm.nih.gov/{p["pmid"]}/">PubMed (PMID: {p["pmid"]})</a></li>')
                if p.get("pmcid"):
                    html_parts.append(f'<li><a href="https://www.ncbi.nlm.nih.gov/pmc/articles/{p["pmcid"]}/pdf/">PMC PDF</a></li>')
                    html_parts.append(f'<li><a href="https://www.ncbi.nlm.nih.gov/pmc/articles/{p["pmcid"]}/">PMC Page</a></li>')
                if p.get("doi"):
                    html_parts.append(f'<li><a href="https://doi.org/{p["doi"]}">Publisher (DOI)</a></li>')
                    html_parts.append(f'<li><a href="https://sci-hub.se/{p["doi"]}">Sci-Hub</a></li>')
                if not p.get("pmid") and not p.get("doi"):
                    html_parts.append(f'<li><a href="https://scholar.google.com/scholar?q={title_text[:80].replace(" ", "+")}">Google Scholar</a></li>')
                html_parts.append("</ul>")
                if abstract_text:
                    html_parts.append(f"<h4>Abstract</h4><p>{abstract_text}</p>")
                else:
                    html_parts.append("<p><em>Abstract not available — visit links above.</em></p>")
                html_parts.append("<hr/>")

        # References
        html_parts.append("<h2>References</h2><ol>")
        for p_data in all_papers:
            a = p_data.get("authors", "Unknown")
            ref = f"{a}. {p_data.get('title', '')}. <em>{p_data.get('journal', '')}</em>. {p_data.get('year', '')}."
            if p_data.get("doi"): ref += f" DOI: {p_data['doi']}."
            if p_data.get("pmid"): ref += f" PMID: {p_data['pmid']}."
            html_parts.append(f"<li>{ref}</li>")
        html_parts.append("</ol>")

        try:
            from tools.create_doc import create_google_doc
            doc_result = await create_google_doc(drive, "Paper_Compilation", "\n".join(html_parts), folder_id)
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
        "summary": f"Downloaded {len(downloaded)} PDFs. {len(no_access)} need manual download. Paper_Compilation doc created with all abstracts and links.",
    }


async def get_paper_full_text(drive, paper: dict, folder_id: str = None) -> dict:
    """Get full text of a paper from Europe PMC."""
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
