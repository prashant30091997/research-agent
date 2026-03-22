# ResearchAgent v5.0 — Architecture

## The Problem with v4.0
- Everything crammed into one 2600-line JSX file
- Fixed pipeline: can't go back, can't modify, can't chat
- No real backend: tools are fake simulations or browser-only hacks
- User can't interact during execution or after completion

## v5.0 Architecture: Conversational Agent + Python Backend

```
┌─────────────────────────────────────────────────────┐
│  FRONTEND (React)                                    │
│  ┌───────────────────────────────────────────────┐  │
│  │  Chat Interface (like ChatGPT)                │  │
│  │  - User types naturally                       │  │
│  │  - AI responds with text + tool results       │  │
│  │  - Paper selection cards render inline         │  │
│  │  - Drive browser popup available anytime       │  │
│  │  - Session sidebar with history/pin/resume     │  │
│  └───────────────────────────────────────────────┘  │
│  Communicates via: POST /api/chat                    │
│                    POST /api/tools/*                  │
│                    POST /api/session/*                │
└──────────────────────┬──────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────┐
│  BACKEND (Python FastAPI)                            │
│                                                      │
│  /api/chat ──→ AI Router ──→ Decides which tools     │
│                    │                                 │
│  ┌─────────────────▼─────────────────────────────┐  │
│  │  TOOLS (Python modules)                       │  │
│  │                                               │  │
│  │  search_pubmed.py   ─── PubMed E-utilities    │  │
│  │  search_scopus.py   ─── Elsevier API          │  │
│  │  drive_ops.py       ─── Google Drive API      │  │
│  │  create_doc.py      ─── Google Docs creation  │  │
│  │  create_sheet.py    ─── Google Sheets creation │  │
│  │  create_slides.py   ─── Google Slides creation │  │
│  │  read_files.py      ─── Read .py .csv .txt    │  │
│  │  notebook_gen.py    ─── Colab notebook builder │  │
│  │  academic_write.py  ─── Lit review, results    │  │
│  │  session_mgr.py     ─── Save/load sessions    │  │
│  └───────────────────────────────────────────────┘  │
│                                                      │
│  AI calls Anthropic/Gemini from backend (no CORS!)   │
│  API keys stored server-side in .env (never exposed) │
└──────────────────────────────────────────────────────┘
```

## Key Differences from v4.0

| Feature | v4.0 (broken) | v5.0 (proper) |
|---------|---------------|---------------|
| AI calls | Browser → API (CORS issues) | Backend → API (no CORS) |
| API keys | In browser localStorage | In server .env file |
| Tools | Fake/simulated in JS | Real Python implementations |
| Chat | Fixed pipeline, no interaction | Conversational, back-and-forth |
| Paper search | Browser fetch only | Server-side with retry/pagination |
| File creation | HTML→Drive conversion hack | Proper Google Workspace API |
| Sessions | localStorage + Drive hack | Server session files + Drive sync |
| Modify results | Impossible | Chat: "add more papers" "change intro" |

## How Chat Works

User: "Search for fNIRS cognitive impairment papers"
→ Backend sends to AI with tool definitions
→ AI says: use search_pubmed tool
→ Backend runs search_pubmed.py → gets real results
→ Returns results to AI
→ AI presents: "Found 15 papers. Here they are: [list]"
→ User: "Search with different terms: near-infrared spectroscopy AND dementia"
→ AI calls search_pubmed again with new terms
→ User: "Good, now write a review using papers 1,3,5,7,9"
→ AI calls academic_write.py with selected papers
→ User: "Make the introduction longer and add more about methodology"
→ AI modifies the review
→ User: "Save this as a Google Doc in my fNIRS folder"
→ AI calls create_doc.py → real Google Doc created
→ User: "Also make a presentation with 10 slides"
→ AI calls create_slides.py → real Google Slides created

## Deployment

```
GitHub Repository:
├── backend/
│   ├── main.py              ← FastAPI server
│   ├── ai_router.py         ← Routes chat to AI + tools
│   ├── requirements.txt
│   ├── .env.example
│   └── tools/
│       ├── search_pubmed.py
│       ├── search_scopus.py
│       ├── drive_ops.py
│       ├── create_doc.py
│       ├── create_sheet.py
│       ├── create_slides.py
│       ├── read_files.py
│       ├── notebook_gen.py
│       ├── academic_write.py
│       └── session_mgr.py
├── frontend/
│   ├── src/App.jsx           ← Chat UI
│   ├── package.json
│   └── vite.config.js
├── .github/workflows/deploy.yml
└── README.md

Deploy options:
- Backend: Railway.app (free tier) or Render.com (free tier)
- Frontend: GitHub Pages (free)
- Or both on Railway/Render together
```
