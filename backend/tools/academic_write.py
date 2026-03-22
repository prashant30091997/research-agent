"""Academic Writing Tools — Literature review, results, discussion"""
from typing import List, Dict

async def write_literature_review(ai, topic: str, papers: List[Dict], 
                                   file_contents: List[Dict] = None, instructions: str = "", model: str = None) -> dict:
    sources = []
    for p in papers:
        entry = f"- {p.get('title','')} ({p.get('authors','')}; {p.get('journal','')}, {p.get('year','')})"
        if p.get("content"): entry += f"\n  Content: {p['content'][:2000]}"
        sources.append(entry)
    
    for fc in (file_contents or []):
        sources.append(f"- {fc.get('name','')}\n  Content: {fc.get('content','')[:2000]}")
    
    prompt = f"""Write a comprehensive literature review on: {topic}

Sources ({len(sources)} total):
{chr(10).join(sources)}

{f'Additional instructions: {instructions}' if instructions else ''}

Include: thematic synthesis, methodology overview, key findings, research gaps, future directions.
Use [Author et al., Year] citations. Only cite papers listed above."""
    
    result = await ai._call_ai(
        "You are an expert academic researcher writing a publication-ready literature review.",
        [{"role": "user", "content": prompt}],
        model or ai.default_model, use_tools=False
    )
    text = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text")
    return {"content": text, "paper_count": len(papers)}

async def write_results(ai, topic: str, context: str = "", instructions: str = "") -> dict:
    prompt = f"Write the Results section for: {topic}\nData/Findings:\n{context[:3000]}\n{f'Instructions: {instructions}' if instructions else ''}"
    result = await ai._call_ai("Expert academic writer. Results: precise, p-values, CIs, effect sizes, past tense.", 
                                [{"role": "user", "content": prompt}], ai.default_model, use_tools=False)
    text = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text")
    return {"section": "results", "content": text}

async def write_discussion(ai, topic: str, context: str = "", instructions: str = "") -> dict:
    prompt = f"Write the Discussion section for: {topic}\nContext:\n{context[:3000]}\n{f'Instructions: {instructions}' if instructions else ''}"
    result = await ai._call_ai("Expert academic writer. Discussion: interpret vs literature, limitations, implications, future.",
                                [{"role": "user", "content": prompt}], ai.default_model, use_tools=False)
    text = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text")
    return {"section": "discussion", "content": text}
