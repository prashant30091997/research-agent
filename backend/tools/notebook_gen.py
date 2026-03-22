"""Colab Notebook Generator"""
import json

async def generate_notebook(ai, query: str, data_files: list = None, code_files: list = None, drive_path: str = "", analysis: dict = None) -> dict:
    cells = [
        {"cell_type": "markdown", "metadata": {}, "source": [f"# Research Analysis Pipeline\n**Query:** {query}\n---\n"], "outputs": [], "execution_count": None},
        {"cell_type": "code", "metadata": {}, "source": ["# Cell 1: Install dependencies\n!pip install -q scipy numpy pandas matplotlib seaborn scikit-learn statsmodels\nimport warnings; warnings.filterwarnings('ignore')\nprint('✅ Ready')"], "outputs": [], "execution_count": None},
    ]
    if drive_path:
        cells.append({"cell_type": "code", "metadata": {}, "source": [f"# Cell 2: Mount Drive\nfrom google.colab import drive\nimport os\ndrive.mount('/content/drive')\nDATA_PATH='{drive_path}'\nprint('📁 Data path:', DATA_PATH)"], "outputs": [], "execution_count": None})
    
    # Ask AI for analysis code
    prompt = f"Generate Python code for: {query}\nData files: {json.dumps(data_files or [])}\nCode files: {json.dumps(code_files or [])}"
    result = await ai._call_ai("Expert data scientist. Write clean Python code.", [{"role": "user", "content": prompt}], ai.default_model, use_tools=False)
    code = "".join(b.get("text", "") for b in result.get("content", []) if b.get("type") == "text").replace("```python", "").replace("```", "").strip()
    cells.append({"cell_type": "code", "metadata": {}, "source": [f"# Cell 3: Analysis\n{code}"], "outputs": [], "execution_count": None})
    
    nb = {"nbformat": 4, "nbformat_minor": 5, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python", "version": "3.10.0"}, "colab": {"provenance": []}}, "cells": cells}
    return nb
