"""PubMed Search + Europe PMC PDF URL enrichment.
Step 1: Search PubMed for papers (titles, authors, abstracts)
Step 2: For each paper, check Europe PMC for open-access PDF URL
Step 3: Return papers WITH pdf_url already attached (no re-searching needed later)
"""
import httpx
import asyncio

SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
FETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
EUROPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


async def search_pubmed(query: str, max_results: int = 15) -> list:
    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: Search PubMed for IDs
        r = await client.get(SEARCH_URL, params={
            "db": "pubmed", "retmode": "json", "retmax": max_results,
            "sort": "relevance", "term": query
        })
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []

        # Step 2: Get paper details from PubMed
        r2 = await client.get(SUMMARY_URL, params={
            "db": "pubmed", "retmode": "json", "id": ",".join(ids)
        })
        results = r2.json().get("result", {})

        # Step 3: Fetch abstracts from PubMed
        abstracts = {}
        try:
            import re
            r3 = await client.get(FETCH_URL, params={
                "db": "pubmed", "id": ",".join(ids[:15]), "retmode": "xml"
            })
            xml = r3.text
            # Extract each PubmedArticle block
            articles = re.findall(r'<PubmedArticle>.*?</PubmedArticle>', xml, re.DOTALL)
            for article in articles:
                pmid_match = re.search(r'<PMID[^>]*>(\d+)</PMID>', article)
                abstract_match = re.search(r'<AbstractText[^>]*>(.*?)</AbstractText>', article, re.DOTALL)
                if pmid_match and abstract_match:
                    pmid_val = pmid_match.group(1)
                    abstract_text = re.sub(r'<[^>]+>', ' ', abstract_match.group(1)).strip()
                    abstracts[pmid_val] = abstract_text[:2000]
        except:
            pass

        papers = []
        for i, pmid in enumerate(ids):
            p = results.get(pmid)
            if not p:
                continue
            authors = [a.get("name", "") for a in (p.get("authors") or [])]
            papers.append({
                "pmid": pmid,
                "title": p.get("title", "Untitled"),
                "journal": p.get("source") or p.get("fulljournalname", ""),
                "year": (p.get("pubdate") or "")[:4],
                "authors": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                "doi": (p.get("elocationid") or "").replace("doi: ", ""),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "db": "PubMed",
                "relevance": max(50, 99 - i * 3),
                "abstract": abstracts.get(pmid, ""),
                "pdf_url": None,  # Will be filled by Europe PMC check
                "pmcid": None,
            })

        # Step 4: Check Europe PMC for PDF URLs (batch — one query for all PMIDs)
        await _enrich_with_europmc(client, papers)

        return papers


async def _enrich_with_europmc(client, papers: list):
    """For each paper, check Europe PMC if open-access PDF exists. Attaches pdf_url directly."""
    for paper in papers:
        pmid = paper.get("pmid", "")
        if not pmid:
            continue
        try:
            # Search Europe PMC by exact PMID
            r = await client.get(EUROPMC_SEARCH, params={
                "query": f"EXT_ID:{pmid} SRC:MED",
                "format": "json", "resultType": "core", "pageSize": 1
            })
            results = r.json().get("resultList", {}).get("result", [])
            if not results:
                continue

            res = results[0]
            # Verify PMID matches exactly
            if str(res.get("pmid", "")) != str(pmid):
                continue

            paper["pmcid"] = res.get("pmcid", "")

            if res.get("isOpenAccess") == "Y":
                ftl = res.get("fullTextUrlList", {}).get("fullTextUrl", [])
                for ft in ftl:
                    if ft.get("documentStyle") == "pdf" and ft.get("availability") == "Open access":
                        paper["pdf_url"] = ft.get("url")
                        break
                # Fallback: PMC render
                if not paper["pdf_url"] and res.get("pmcid"):
                    paper["pdf_url"] = f"https://europepmc.org/backend/ptpmcrender.fcgi?accid={res['pmcid']}&blobtype=pdf"

            # Fill abstract if missing
            if not paper["abstract"] and res.get("abstractText"):
                paper["abstract"] = res["abstractText"][:2000]

            await asyncio.sleep(0.5)  # Be polite to Europe PMC
        except:
            continue


async def search_pubmed_mesh(topic: str, ai_router, max_results: int = 15) -> dict:
    """Generate MeSH terms then search with multiple strategies"""
    mesh = await ai_router.generate_mesh_terms(topic)
    all_papers = []
    seen_pmids = set()

    for query in mesh.get("queries", [topic]):
        papers = await search_pubmed(query, max_results)
        for p in papers:
            if p["pmid"] not in seen_pmids:
                seen_pmids.add(p["pmid"])
                all_papers.append(p)

    return {
        "papers": all_papers,
        "mesh_terms": mesh.get("mesh_terms", []),
        "queries_used": mesh.get("queries", []),
        "total": len(all_papers),
    }
