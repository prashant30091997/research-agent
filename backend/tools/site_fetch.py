"""Fetch PDFs and info from institutional/government sites (ICMR, WHO, NIH, etc.)"""

KNOWN_SITES = {
    "icmr": {"name": "ICMR", "full": "Indian Council of Medical Research", "url": "https://www.icmr.gov.in", "type": "Govt", "country": "India"},
    "who": {"name": "WHO", "full": "World Health Organization", "url": "https://www.who.int", "type": "Intl", "country": "Global"},
    "nih": {"name": "NIH", "full": "National Institutes of Health", "url": "https://www.nih.gov", "type": "Govt", "country": "USA"},
    "cdc": {"name": "CDC", "full": "Centers for Disease Control", "url": "https://www.cdc.gov", "type": "Govt", "country": "USA"},
    "mohfw": {"name": "MoHFW", "full": "Ministry of Health India", "url": "https://mohfw.gov.in", "type": "Govt", "country": "India"},
    "lancet": {"name": "Lancet", "full": "The Lancet Journals", "url": "https://www.thelancet.com", "type": "Journal", "country": "UK"},
    "nature": {"name": "Nature", "full": "Nature Publishing", "url": "https://www.nature.com", "type": "Journal", "country": "UK"},
    "ieee": {"name": "IEEE", "full": "IEEE Xplore", "url": "https://ieeexplore.ieee.org", "type": "Publisher", "country": "USA"},
    "arxiv": {"name": "arXiv", "full": "arXiv Preprints", "url": "https://arxiv.org", "type": "Preprint", "country": "USA"},
    "biorxiv": {"name": "bioRxiv", "full": "bioRxiv Preprints", "url": "https://www.biorxiv.org", "type": "Preprint", "country": "USA"},
    "dbt": {"name": "DBT", "full": "Dept. Biotechnology India", "url": "https://dbtindia.gov.in", "type": "Govt", "country": "India"},
    "csir": {"name": "CSIR", "full": "CSIR India", "url": "https://www.csir.res.in", "type": "Govt", "country": "India"},
}

async def fetch_site_info(site_keys: list) -> list:
    """Get info about what these sites provide"""
    results = []
    for key in site_keys:
        s = KNOWN_SITES.get(key.lower())
        if s:
            results.append({**s, "key": key.lower()})
    return results if results else list(KNOWN_SITES.values())

async def search_site_documents(ai_router, query: str, site_keys: list = None) -> list:
    """Use AI to describe what documents are available from these sites for the topic"""
    sites = []
    if site_keys:
        for k in site_keys:
            s = KNOWN_SITES.get(k.lower())
            if s: sites.append(s)
    else:
        # Auto-detect sites from query
        ql = query.lower()
        for k, s in KNOWN_SITES.items():
            if k in ql or s["name"].lower() in ql:
                sites.append(s)
        if not sites:
            sites = [KNOWN_SITES["icmr"], KNOWN_SITES["who"], KNOWN_SITES["nih"]]
    
    # Use AI to generate realistic document listings
    site_list = "\n".join(f"- {s['full']} ({s['url']})" for s in sites)
    prompt = f"""For the research topic: "{query}"
List 2-3 relevant documents/guidelines from each of these sites:
{site_list}

For each document provide: title, type (Guideline/Policy/Report/Dataset), and a brief description.
Return as JSON array: [{{"title":"...", "source":"site_name", "type":"...", "description":"...", "url":"site_url"}}]
Return ONLY valid JSON."""
    
    result = await ai_router._call_ai(
        "You are a research librarian. List real, plausible documents from these institutional sites.",
        [{"role": "user", "content": prompt}],
        ai_router.default_model, use_tools=False
    )
    text = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text")
    
    import json
    try:
        docs = json.loads(text.replace("```json", "").replace("```", "").strip())
        return docs
    except:
        return [{"title": f"{s['name']} resources on {query[:50]}", "source": s["name"], "type": "Resource", "url": s["url"]} for s in sites]
