"""Code Understanding & Pipeline Design Tools"""
from typing import List, Dict

async def understand_code(ai_router, code_files: List[Dict], data_files: List[Dict] = None, query: str = "", model: str = None) -> dict:
    """Read actual code file contents and analyze with AI"""
    code_text = []
    for cf in code_files[:5]:
        content = cf.get("content", "")
        if content:
            code_text.append(f"=== {cf.get('name', 'file')} ===\n{content[:3000]}")
    
    data_list = "\n".join(f"- {f.get('name','')} ({f.get('ext','')}, {f.get('size_str','')})" for f in (data_files or []))
    
    prompt = f"""Analyze this research project code.

ACTUAL SOURCE CODE:
{chr(10).join(code_text) if code_text else "No code content available — only filenames provided."}

DATA FILES IN FOLDER:
{data_list or "None listed"}

Research context: {query}

Explain:
1. Each file's purpose and key functions
2. How files connect to each other (imports, data flow)  
3. The overall processing pipeline
4. Key algorithms and methods used
5. External library dependencies
6. Which existing functions can be reused for new analysis"""
    
    result = await ai_router._call_ai(
        "Expert code analyst. Provide thorough analysis of research code.",
        [{"role": "user", "content": prompt}],
        model or ai_router.default_model, use_tools=False
    )
    text = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text")
    return {"analysis": text, "files_analyzed": len(code_text)}


async def design_pipeline(ai_router, query: str, signal_config: dict = None, 
                          data_files: list = None, code_analysis: str = "", model: str = None) -> dict:
    """Design an analysis pipeline based on data and query"""
    sig_info = ""
    if signal_config:
        sig_info = f"\nSignal types: {signal_config.get('label','Auto')}\nLibraries: {signal_config.get('libs','')}\nMethods: {signal_config.get('methods','')}"
        if signal_config.get("custom_desc"):
            sig_info += f"\nCustom signal: {signal_config['custom_desc']}"
    
    data_info = "\n".join(f"- {f.get('name','')} ({f.get('ext','')}, {f.get('size_str','')})" for f in (data_files or []))
    
    prompt = f"""Design a complete analysis pipeline for:
Query: "{query}"
{sig_info}

Data files available:
{data_info or "Not specified yet"}

{f"Existing code analysis: {code_analysis[:500]}" if code_analysis else ""}

Return a JSON object with:
{{
  "data_types": ["list of data types to handle"],
  "preprocessing_steps": ["step1", "step2", ...],
  "analysis_methods": ["method1", "method2", ...],
  "statistical_tests": ["test1", "test2", ...],
  "output_figures": ["figure1", "figure2", ...],
  "reuse_existing_code": ["function/file names to reuse"],
  "libraries_needed": ["lib1", "lib2", ...]
}}
Return ONLY valid JSON."""
    
    result = await ai_router._call_ai(
        "Expert data scientist and signal processing engineer. Design thorough analysis pipelines.",
        [{"role": "user", "content": prompt}],
        model or ai_router.default_model, use_tools=False
    )
    text = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text")
    
    import json
    try:
        pipeline = json.loads(text.replace("```json", "").replace("```", "").strip())
        return {"pipeline": pipeline}
    except:
        return {"pipeline": {
            "data_types": ["auto-detect"],
            "preprocessing_steps": ["Load data", "Clean/filter", "Normalize"],
            "analysis_methods": ["Statistical analysis", "Visualization"],
            "statistical_tests": ["t-test", "ANOVA"],
            "output_figures": ["Summary plots", "Comparison charts"],
            "reuse_existing_code": [],
            "libraries_needed": ["scipy", "numpy", "pandas", "matplotlib"]
        }}


# Signal type configurations
SIGNAL_TYPES = {
    "eeg": {"label": "EEG", "icon": "🧠", "libs": "mne, mne-connectivity, fooof, antropy, yasa", "methods": "Band-power, ERP, ICA, connectivity, CSP"},
    "ecg": {"label": "ECG", "icon": "❤️", "libs": "neurokit2, biosppy, heartpy, hrv-analysis, wfdb", "methods": "R-peak, HRV, QRS, arrhythmia"},
    "emg": {"label": "EMG", "icon": "💪", "libs": "emgdecompy, scipy.signal", "methods": "RMS, MVC, median freq, fatigue, MUAP"},
    "fnirs": {"label": "fNIRS", "icon": "🔴", "libs": "mne, mne-nirs, nilearn", "methods": "HbO/HbR, GLM, connectivity, beer-lambert"},
    "auto": {"label": "Auto-Detect", "icon": "🤖", "libs": "scipy, numpy, pandas", "methods": "Auto-detect from file structure"},
}

def get_signal_config(signal_types: list = None, custom_desc: str = "") -> dict:
    """Build merged signal config from selected types + custom description"""
    types = signal_types or ["auto"]
    libs = set()
    methods = set()
    label_parts = []
    
    for t in types:
        if t in SIGNAL_TYPES and t != "auto":
            s = SIGNAL_TYPES[t]
            label_parts.append(s["label"])
            for l in s["libs"].split(","): libs.add(l.strip())
            for m in s["methods"].split(","): methods.add(m.strip())
    
    if not label_parts:
        label_parts = ["Auto-Detect"]
        libs = {"scipy", "numpy", "pandas", "matplotlib"}
        methods = {"Auto-detect"}
    
    return {
        "label": "+".join(label_parts),
        "libs": ", ".join(sorted(libs)),
        "methods": ", ".join(sorted(methods)),
        "custom_desc": custom_desc,
        "is_multi": len(label_parts) > 1,
        "is_custom": bool(custom_desc),
    }
