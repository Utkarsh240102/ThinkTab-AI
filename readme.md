# ThinkTab AI

ThinkTab AI is a contextual AI research assistant packaged as a Chrome Extension, powered by a local FastAPI backend and LangGraph.

ThinkTab AI acts as your personal research sidekick. You open the side panel while browsing any webpage or reading a PDF, and you can ask questions directly about the content. It scrapes the page, stores the information locally using vector embeddings, and answers your questions by cross-referencing the page text, uploaded documents, or falling back to live web searches if needed.

## Tech Stack
- **Frontend**: React 19, TypeScript 6, Vite 8, Chrome Extension Manifest V3
- **Backend**: Python 3.11, FastAPI, Uvicorn
- **AI Orchestration**: LangChain, LangGraph
- **Vector DB & Models**: FAISS (local), BAAI/bge-m3 (local embeddings), BAAI/bge-reranker-base (local reranker)
- **LLMs**: gpt-4o-mini (OpenRouter) for routing/logic, llama-3.3-70b (Groq) for final generation
- **Web Search**: Serper API

## Project Structure
```text
ThinkTab-AI/
├── AGENTS.md                  # Project brain and state tracker
├── bugs3.md                   # Comprehensive bug and issue registry
├── backend/                   # FastAPI Server
│   ├── app/
│   │   ├── api/endpoints.py   # REST and SSE routing
│   │   ├── core/config.py     # Environment configurations
│   │   ├── graph/             # LangGraph RAG pipeline logic
│   │   ├── services/          # Embeddings and FAISS LRU cache
│   │   └── main.py            # FastAPI application entrypoint
│   └── requirements.txt       # Python dependencies
├── frontend/                  # Chrome Extension Panel
│   ├── public/                # Manifest and background scripts
│   ├── src/                   # React components and hooks
│   ├── package.json           # Node dependencies
│   └── vite.config.ts         # Vite bundler configuration
└── models/                    # Local downloaded HuggingFace models
```

## Prerequisites
- **Node.js**: v18+
- **Python**: 3.11+
- **Chrome**: Version 114+ (for Side Panel API)

## Installation

### 1. Backend Setup
```bash
cd backend
python -m venv venv

# On Windows:
.\venv\Scripts\activate
# On Mac/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run build
```

### 3. Chrome Extension Installation
1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** in the top right.
3. Click **Load unpacked** and select the `frontend/dist` directory.

## Environment Variables
Create a `.env` file in the root directory.
- `OPENROUTER_API_KEY`: Key for routing LLMs (gpt-4o-mini).
- `GROQ_API_KEY`: Key for generation LLMs (llama-3.3-70b).
- `SERPER_API_KEY`: Key for Google Web Search fallback.

## How to Run

1. **Start the Backend**:
```bash
cd backend
.\venv\Scripts\activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
2. **Open the Extension**: Click the ThinkTab AI icon in your Chrome toolbar to open the side panel.

## Key Features
- **Multi-Mode Routing**: Fast Mode for latency-sensitive queries, Deep Mode with Self-RAG loops for extensive analysis.
- **Local Privacy-First Embeddings**: Uses BAAI/bge-m3 on your CPU to embed documents locally without sending raw text to third-party APIs.
- **Multi-Tab Research**: Pin multiple tabs and compare them.
- **Soft Human-in-the-Loop**: Seamlessly switch from a Fast answer to a Deep answer if you need more detail.

## Known Limitations
- The first request takes 30-60 seconds to automatically download the local embedding and re-ranker models.
- The local FAISS cache is in-memory only and resets when the backend server is restarted.
- Concurrent embedding requests currently suffer from a cache dogpile effect (will be fixed in future updates).

## Contributing Guide
1. Create a feature branch from `main`.
2. Ensure you run `npm run lint` on the frontend and `flake8 app` on the backend before submitting.
3. Review `bugs3.md` for known issues before opening a new PR.
