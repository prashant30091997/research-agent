"""PubMed Search — Real NCBI E-utilities API (free, no key needed)"""
import httpx

SEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
SUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

async def search_pubmed(query: str, max_results: int = 15) -> list:
    async with httpx.AsyncClient(timeout=30) as client:
        # Step 1: Search for IDs
        r = await client.get(SEARCH_URL, params={
            "db": "pubmed", "retmode": "json", "retmax": max_results,
            "sort": "relevance", "term": query
        })
        ids = r.json().get("esearchresult", {}).get("idlist", [])
        if not ids: return []
        
        # Step 2: Fetch details
        r2 = await client.get(SUMMARY_URL, params={
            "db": "pubmed", "retmode": "json", "id": ",".join(ids)
        })
        results = r2.json().get("result", {})
        
        papers = []
        for i, pmid in enumerate(ids):
            p = results.get(pmid)
            if not p: continue
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
            })
        return papers

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
