# 🧬 ResearchAgent v5.0

AI-powered research assistant with conversational interface, real PubMed/Scopus search, Google Drive integration, and automatic document creation.

## Quick Start (5 minutes)

### Step 1: Get API Keys
- **Anthropic**: https://console.anthropic.com → API Keys → Create
- **Google**: https://aistudio.google.com/apikey → Create API Key
- **ngrok** (free): https://ngrok.com/signup → Dashboard → Copy auth token
- **Scopus** (optional): https://dev.elsevier.com/apikey/manage

### Step 2: Run Backend on Colab
1. Open `ResearchAgent_v5_Backend.ipynb` in Google Colab
2. Cell 1: Clones repo + installs dependencies
3. Cell 2: Paste your API keys
4. Cell 3: Paste ngrok token → Run → Copy the public URL

### Step 3: Deploy Frontend on GitHub Pages
```bash
cd frontend
npm create vite@latest . -- --template react
npm install
# Replace src/App.jsx with the provided App.jsx
npm run dev  # Test locally first
```
Push to GitHub → Enable GitHub Pages → GitHub Actions auto-deploys.

### Step 4: Connect
Open your frontend → Settings → Paste the Colab ngrok URL → Save

## Architecture

```
GitHub Pages (React Chat UI) ←→ Colab Backend (Python FastAPI) ←→ AI APIs
                                      ↕
                               Google Drive API
                               PubMed / Scopus
```

## Tools Available (18 total)

| Tool | Description |
|------|-------------|
| `search_pubmed` | Real PubMed search with MeSH term generation |
| `search_scopus` | Scopus/Elsevier search with citations |
| `generate_mesh_terms` | AI-powered MeSH term optimization |
| `drive_list_folders` | Browse Google Drive folders |
| `drive_list_files` | List files in a folder |
| `drive_read_file` | Read text/code file content |
| `drive_create_folder` | Create folders in Drive |
| `fetch_site_documents` | ICMR/WHO/NIH/CDC/IEEE/arXiv documents |
| `query_site_info` | Info about institutional resources |
| `understand_code` | Analyze .py code: functions, pipeline, deps |
| `design_pipeline` | Design analysis pipeline for biosignals |
| `write_literature_review` | Comprehensive review from papers |
| `write_section` | Results, discussion, any paper section |
| `create_google_doc` | Create editable Google Doc in Drive |
| `create_google_sheet` | Create editable Google Sheet in Drive |
| `create_google_slides` | Create editable Google Slides in Drive |
| `generate_colab_notebook` | Generate .ipynb for data analysis |

## Example Conversations

```
You: Search PubMed for fNIRS cognitive impairment papers
AI: [searches with 3 MeSH strategies → finds 18 papers → presents list]
You: Use papers 1, 3, 5, 7. Also search with "near-infrared spectroscopy AND dementia"
AI: [searches again → adds 5 more → merged list]
You: Write a review using all selected papers
AI: [writes comprehensive review with real citations]
You: Make the methodology section longer
AI: [rewrites that section]
You: Save as Google Doc in my fNIRS folder
AI: [creates Google Doc → gives link]
```

## File Structure

```
research-agent/
├── ResearchAgent_v5_Backend.ipynb  ← Run this in Colab
├── backend/
│   ├── main.py                     ← FastAPI server
│   ├── ai_router.py                ← AI + tool routing
│   ├── requirements.txt
│   ├── .env.example
│   └── tools/
│       ├── search_pubmed.py        ← Real PubMed API
│       ├── search_scopus.py        ← Real Scopus API
│       ├── drive_ops.py            ← Google Drive CRUD
│       ├── create_doc.py           ← Google Workspace files
│       ├── code_analysis.py        ← Code understanding + pipeline
│       ├── site_fetch.py           ← Institutional site documents
│       ├── academic_write.py       ← Literature review, sections
│       ├── notebook_gen.py         ← Colab notebook generator
│       ├── session_mgr.py          ← Session persistence
│       └── read_files.py           ← File content reading
├── frontend/
│   └── src/App.jsx                 ← React chat UI
└── README.md
```
