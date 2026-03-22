"""Scopus Search — Elsevier API (requires free academic API key)"""
import httpx

SCOPUS_URL = "https://api.elsevier.com/content/search/scopus"

async def search_scopus(query: str, api_key: str, max_results: int = 10) -> list:
    if not api_key: return []
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(SCOPUS_URL, params={
                "query": query, "count": max_results, "sort": "relevancy"
            }, headers={"X-ELS-APIKey": api_key, "Accept": "application/json"})
            entries = r.json().get("search-results", {}).get("entry", [])
            return [{
                "scopus_id": (e.get("dc:identifier") or "").replace("SCOPUS_ID:", ""),
                "title": e.get("dc:title", "Untitled"),
                "journal": e.get("prism:publicationName", ""),
                "year": (e.get("prism:coverDate") or "")[:4],
                "authors": e.get("dc:creator", ""),
                "citations": int(e.get("citedby-count", 0)),
                "doi": e.get("prism:doi", ""),
                "url": e.get("prism:url", ""),
                "db": "Scopus",
                "relevance": max(50, 98 - i * 4),
            } for i, e in enumerate(entries) if e.get("dc:title")]
    except Exception as e:
        return []
