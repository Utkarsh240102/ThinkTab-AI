# ThinkTab AI ⚡

ThinkTab AI is a contextual AI research assistant packaged as a Chrome Extension. It seamlessly integrates into your browser side panel, allowing you to ask questions about the active webpage or uploaded PDFs. 

Using a local embedding model and a powerful multi-tier RAG pipeline, ThinkTab AI delivers instant, accurate answers while keeping your API costs low.

## 🛠️ Tech Stack
- **Frontend:** React 19, TypeScript, Vite 8, Vanilla CSS
- **Backend:** FastAPI, Python 3.11+
- **RAG Orchestration:** LangChain & LangGraph
- **Vector Store:** Local FAISS (CPU)
- **Local Models:** BAAI/bge-m3 (Embeddings), BAAI/bge-reranker-base (Cross-Encoder)
- **LLMs:** gpt-4o-mini (Fast Brain via OpenRouter), llama-3.3-70b (Smart Brain via Groq)
- **Fallback:** Serper API (Google Search)

## 📁 Project Structure
```text
ThinkTab-AI/
├── backend/
│   ├── app/                # FastAPI application, Graph nodes, and LLM services
│   ├── tests/              # Backend test suites
│   ├── requirements.txt    # Python dependencies
├── frontend/
│   ├── public/             # Chrome Extension Manifest and Background Scripts
│   ├── src/                # React UI and SSE Hooks
│   ├── vite.config.ts      # Vite configuration
├── models/                 # Local HuggingFace cache for embeddings/reranker
├── .env.example            # Environment variables template
└── AGENTS.md               # Project tracking and architecture single-source-of-truth
```

## ⚙️ Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- A Chromium-based browser (Chrome, Edge, Brave)

## 🚀 Installation & Setup

### 1. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # Or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
```

### 2. Environment Variables
Copy the `.env.example` file to `.env` in the root directory:
```bash
cp .env.example .env
```
Populate it with your actual keys:
- `OPENROUTER_API_KEY`: Required for fast routing and CRAG scoring.
- `GROQ_API_KEY`: Required for Deep Mode generative answers.
- `SERPER_API_KEY`: Optional but recommended for web search fallback.

### 3. Frontend Setup
```bash
cd frontend
npm install
npm run build
```

### 4. Running the Project
**Start the Backend Server:**
```bash
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
**Load the Chrome Extension:**
1. Open Chrome and go to `chrome://extensions/`
2. Enable "Developer mode" in the top right.
3. Click "Load unpacked" and select the `frontend/dist` directory.
4. Pin the extension and open the side panel!

## ✨ Key Features
- **Active Tab Context:** Automatically scrapes and understands the webpage you are currently viewing.
- **PDF Uploads:** Extract and query local PDF documents natively.
- **Fast Mode:** Instant, cheap answers using lightweight LLMs and local FAISS similarity search.
- **Deep Mode (Self-RAG):** Advanced LangGraph pipeline that validates facts, handles multi-hop logic, and falls back to Google Search if local context is insufficient.
- **Thread-Safe Caching:** Near-instant subsequent queries on the same page using local LRU embedding caches with dogpile prevention.

## ⚠️ Known Limitations
- The first query will take ~30 seconds as the backend downloads the `bge-m3` and `bge-reranker-base` models locally.
- Chrome Extension cannot scrape `chrome://` or Chrome Web Store pages due to browser security policies.
- The FAISS cache is in-memory only and will be wiped upon server restart.
