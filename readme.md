# 🧠 ThinkTab AI — Intelligent Browser Assistant

> A production-ready Chrome Extension powered by a Hybrid RAG pipeline. Ask anything about the page you're reading — ThinkTab AI scrapes the active tab, retrieves the most relevant context, and streams a grounded, cited answer in real time.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Feature Breakdown](#feature-breakdown)
- [Project Structure](#project-structure)
- [Backend Deep Dive](#backend-deep-dive)
- [Frontend Deep Dive](#frontend-deep-dive)
- [Chrome Extension Integration](#chrome-extension-integration)
- [Installation & Setup](#installation--setup)
- [Environment Variables](#environment-variables)
- [How to Use](#how-to-use)
- [API Reference](#api-reference)
- [Design System](#design-system)

---

## Overview

ThinkTab AI is a Chrome Extension that acts as an intelligent assistant that lives in your browser's Side Panel. It reads the content of whatever webpage you are currently viewing and lets you ask natural language questions about it — powered by a Hybrid RAG (Retrieval-Augmented Generation) backend built with LangGraph.

**Key capabilities:**
- 🌐 Reads any webpage in any language
- ⚡ Two intelligence modes: Fast (low-latency) and Deep (high-accuracy)
- 🤖 Auto-routing: AI decides the best mode for each query
- 🔄 Soft HITL: Upgrade a Fast answer to Deep with one click mid-stream
- 📎 Cited answers: Every claim is backed by an evidence snippet
- 🔁 Error recovery: Retry failed queries with one click
- 📡 Real-time streaming: SSE-powered live token-by-token output

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Chrome Extension (UI)                   │
│   ┌──────────────┐      ┌────────────────────────────┐  │
│   │ content.js   │      │   React Side Panel (Vite)  │  │
│   │ (Tab Scraper)│──────│   ChatShell, ModeSelector  │  │
│   └──────────────┘      │   EvidenceAccordion, HITL  │  │
│                         └──────────┬───────────────────┘  │
└────────────────────────────────────┼───────────────────┘
                                     │ SSE Stream (POST /api/chat)
                                     ▼
┌─────────────────────────────────────────────────────────┐
│                  FastAPI Backend                          │
│                                                          │
│   ┌──────────────────────────────────────────────────┐  │
│   │  Auto Router → Fast Mode or Deep Mode             │  │
│   └──────────────────────────────────────────────────┘  │
│                                                          │
│  FAST MODE PIPELINE:                                     │
│   Contextualizer → Retrieval & Rerank → CRAG Filter     │
│   → Generation (structured output with evidence)         │
│                                                          │
│  DEEP MODE PIPELINE:                                     │
│   Contextualizer → Retrieval & Rerank → CRAG Evaluator  │
│   → Web Search Fallback → CRAG Refiner                  │
│   → Generation → Hallucination Grader → Answer Grader   │
│   → (Self-RAG retry loop if needed)                     │
│                                                          │
│  SERVICES:                                               │
│   HuggingFace Embeddings (Local CPU)                     │
│   FAISS Vector Store (LRU cache, SHA-256 keyed)         │
│   BAAI/bge-reranker-base (Cross-Encoder)                │
└─────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Backend
| Layer | Technology |
|---|---|
| Web Framework | FastAPI + Uvicorn |
| Streaming | Server-Sent Events (SSE) via `sse-starlette` |
| AI Orchestration | LangGraph (Directed Acyclic Graph of nodes) |
| LLM (Fast Brain / Router) | `gpt-4o-mini` via OpenRouter |
| LLM (Smart Brain / Generator) | `llama-3.3-70b-versatile` via Groq |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local CPU) |
| Vector Store | FAISS (in-memory, LRU cached per webpage) |
| Re-Ranking | `BAAI/bge-reranker-base` (local Cross-Encoder) |
| Web Search | Serper API (Google Search proxy) |
| Config | Pydantic Settings + python-dotenv |

### Frontend
| Layer | Technology |
|---|---|
| Framework | React 19 + TypeScript |
| Build Tool | Vite 8 |
| Styling | Vanilla CSS (Glassmorphism design system) |
| State Management | React Hooks (`useState`, `useCallback`, `useRef`) |
| Streaming | Custom `useSSEChat` hook (Fetch + ReadableStream) |
| Abort Logic | `AbortController` (Soft HITL mid-stream cancellation) |

### Chrome Extension
| Layer | Technology |
|---|---|
| Manifest | Manifest V3 |
| UI Mode | Chrome Side Panel API |
| Page Scraping | Content Script (injected into active tab) |
| Background | Service Worker (`background.js`) |

---

## Feature Breakdown

### ⚡ Fast Mode
The default low-latency pipeline. Best for quick factual questions.

1. **Contextualizer** — Rewrites the user's query as a standalone search query using chat history for reference resolution.
2. **Retrieval & Rerank** — Searches the per-source FAISS vector index and uses the `bge-reranker-base` cross-encoder to re-rank results.
3. **CRAG Filter** — Batches all retrieved chunks and filters out completely irrelevant ones using the Fast Brain LLM.
4. **Generation** — Generates a structured answer (answer, evidence, confidence score) using the Smart Brain LLM.

### 🧠 Deep Mode
A high-accuracy, multi-step reasoning pipeline. Best for complex analytical questions.

1. **Contextualizer** — Same as Fast Mode.
2. **Retrieval & Rerank** — Fetches more chunks (`DEEP_MODE_RETRIEVE_K=15`) and keeps more after reranking (`DEEP_MODE_RERANK_TOP_K=8`).
3. **CRAG Evaluator** — Grades each retrieved chunk on a 0.0–1.0 relevance scale.
4. **Web Search Fallback** — If local documents are insufficient (score below `LOWER_CRAG_THRESHOLD`), rewrites the query for web search and calls the Serper API.
5. **CRAG Refiner** — Sentence-level filtering. Splits all documents into individual sentences and uses the Fast Brain LLM to drop noise, outputting a high-density refined context.
6. **Generation** — Generates a structured answer using the Smart Brain LLM on the refined context.
7. **Hallucination Grader** — Validates whether the answer is strictly grounded in the provided context. If not, triggers a revision.
8. **Answer Grader** — Validates whether the answer actually resolves the user's original question. If not, triggers a re-retrieval with a rewritten query.

### 🤖 Auto Router
A cascading 3-stage routing system that decides Fast vs Deep before the pipeline runs:
- **Stage 1: Count** — Queries with >5 words or question marks are likely complex → Deep.
- **Stage 2: Keywords** — Checks for keyword signals like "explain", "compare", "why" → Deep.
- **Stage 3: LLM Intent** — Uses `gpt-4o-mini` to classify final ambiguous cases.

### 🔄 Soft HITL (Human-in-the-Loop)
After receiving a Fast Mode answer, a `[Switch to Deep Mode]` button appears. Clicking it:
1. Calls `abort()` on the `AbortController` to cancel the current SSE stream.
2. Immediately fires a new `sendQuery()` call with mode forced to `deep`.
3. The user gets a Deep Mode answer for the same question without re-typing.

### 📎 Evidence Accordion
Every AI answer renders an expandable `EvidenceAccordion`. Each accordion item shows:
- Source ID (e.g., "Active Tab")
- Full evidence snippet from the retrieved documents
- Confidence score badge

### ⚠️ Error Recovery
Failed queries render an `ErrorBubble` instead of a plain text error. The "Retry" button inside the bubble:
1. Cancels any broken stream.
2. Re-fires the exact last query silently, without the user needing to retype.

---

## Project Structure

```
ThinkTab-AI/
│
├── backend/                        # FastAPI backend server
│   ├── app/
│   │   ├── main.py                 # FastAPI app entry point + CORS
│   │   ├── api/
│   │   │   └── endpoints.py        # POST /api/chat — SSE event stream
│   │   ├── core/
│   │   │   └── config.py           # Pydantic settings (from .env)
│   │   ├── graph/
│   │   │   ├── state.py            # GraphState TypedDict (shared state)
│   │   │   ├── auto_router.py      # 3-stage cascade router
│   │   │   ├── fast_mode.py        # Fast Mode LangGraph pipeline
│   │   │   ├── deep_mode.py        # Deep Mode LangGraph pipeline
│   │   │   └── nodes/
│   │   │       ├── contextualizer.py     # Query rewriting
│   │   │       ├── retrieval.py          # FAISS search + cross-encoder rerank
│   │   │       ├── generation.py         # Structured LLM output generation
│   │   │       ├── crag_evaluator.py     # Relevance grading (0.0 – 1.0)
│   │   │       ├── crag_refiner.py       # Sentence-level noise filtering
│   │   │       ├── web_search.py         # Serper API web search fallback
│   │   │       ├── hallucination_grader.py  # Grounding validation
│   │   │       └── answer_grader.py      # Answer usefulness validation
│   │   └── services/
│   │       ├── embedder.py         # HuggingFace local embeddings + chunker
│   │       ├── vector_store.py     # FAISS LRU cache (SHA-256 keyed)
│   │       └── llm_service.py      # LLM client initialization
│   └── requirements.txt
│
├── frontend/                       # Vite + React Chrome Extension UI
│   ├── public/
│   │   ├── manifest.json           # Chrome Extension Manifest V3
│   │   ├── background.js           # Service Worker (opens Side Panel)
│   │   └── content.js              # Content Script (tab text scraper)
│   ├── src/
│   │   ├── main.tsx                # React root mount
│   │   ├── App.tsx                 # Root component
│   │   ├── index.css               # Glassmorphism design system tokens
│   │   ├── hooks/
│   │   │   └── useSSEChat.ts       # Custom SSE streaming hook
│   │   └── components/
│   │       ├── ChatShell.tsx       # Main chat layout + state orchestration
│   │       ├── Header.tsx          # App header + Reload Extension button
│   │       ├── QueryInput.tsx      # Auto-resizing textarea + Send button
│   │       ├── ModeSelector.tsx    # Claude-style mode picker dropdown
│   │       ├── StatusBubble.tsx    # Typing indicator for streaming status
│   │       ├── EvidenceAccordion.tsx  # Collapsible source citations
│   │       ├── SoftHITLButton.tsx  # "Switch to Deep" abort button
│   │       ├── ErrorBubble.tsx     # Error display with Retry action
│   │       └── EmptyState.tsx      # Welcome screen
│   ├── vite.config.ts
│   └── tsconfig.app.json
│
├── models/                         # Local HuggingFace model cache (git-ignored)
├── plan.md                         # Master implementation plan
├── .env                            # API keys (git-ignored)
└── .gitignore
```

---

## Backend Deep Dive

### GraphState (`state.py`)
The shared TypedDict that flows through every LangGraph node:
```python
query              # The user's current question
chat_history       # Previous messages for context resolution
contexts           # Scraped webpage paragraphs from content.js
mode               # "fast" | "deep" | "auto"
retrieved_docs     # Documents from FAISS retrieval
refined_context    # Post-CRAG-refiner high-density context
final_answer       # The LLM's structured output
# ... + grading flags, retry counters, web search docs
```

### FAISS Vector Store with LRU Cache (`vector_store.py`)
Each webpage paragraph is hashed with SHA-256. On first encounter, the text is chunked (500 char chunks, 50 char overlap) and embedded into a FAISS index. This index is stored in an in-memory LRU cache (max 20 pages). Subsequent queries against the same page hit the cache instantly without re-embedding.

### Structured Generation (`generation.py`)
The LLM is forced to output a strict Pydantic schema:
```python
class StructuredAnswer(BaseModel):
    answer:             str
    evidence:           List[EvidenceItem]  # source_id + snippet
    confidence_score:   float               # 0.0 – 1.0
    reasoning_summary:  str
```

---

## Frontend Deep Dive

### `useSSEChat.ts` Hook
The core streaming engine. It:
1. Opens a `POST` fetch to `http://127.0.0.1:8000/api/chat`
2. Reads the `ReadableStream` line-by-line with a `TextDecoder`
3. Parses each `data: {...}` SSE event by type:
   - `mode` → Updates the mode badge in the Header
   - `status` → Updates the `StatusBubble` typing indicator
   - `final` → Triggers the `AssistantMessage` to appear in chat
   - `error` → Triggers the `ErrorBubble`
4. Supports full `AbortController` cancellation for Soft HITL

### `content.js` — Tab Scraper
Injected into every webpage by Chrome. When the React side panel sends a `SCRAPE_PAGE_CONTEXT` message, it:
1. Grabs `document.title`
2. Selects all `<p>` tags, filters out snippets shorter than 40 characters
3. Merges the title + first 8 paragraphs into **one combined string**
4. Returns it as a single Context object (`source_id: "Active Tab"`)

> Merging into one string is critical — it ensures only **one FAISS embedding call** is made per query instead of one per paragraph.

---

## Chrome Extension Integration

### Manifest V3 Configuration
```json
{
  "manifest_version": 3,
  "side_panel": { "default_path": "index.html" },
  "permissions": ["sidePanel", "activeTab", "scripting", "storage"],
  "background": { "service_worker": "background.js" },
  "content_scripts": [{ "matches": ["<all_urls>"], "js": ["content.js"] }]
}
```

### Communication Flow
```
User visits webpage
       ↓
content.js is auto-injected into the tab by Chrome
       ↓
User opens Side Panel → background.js → chrome.sidePanel.toggle()
       ↓
User types question → ChatShell.tsx
       ↓
chrome.tabs.sendMessage("SCRAPE_PAGE_CONTEXT") → content.js
       ↓
content.js returns merged page text → ChatShell.tsx
       ↓
useSSEChat.sendQuery() → POST /api/chat with contexts
       ↓
FastAPI streams SSE events → React updates in real-time
```

---

## Installation & Setup

### Prerequisites
- Python 3.10+
- Node.js 18+
- Google Chrome browser

### 1. Clone the repository
```bash
git clone https://github.com/Utkarsh240102/ThinkTab-AI.git
cd ThinkTab-AI
```

### 2. Backend Setup
```bash
cd backend

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Start the backend server
uvicorn app.main:app --reload
```
The backend will be available at `http://127.0.0.1:8000`

> **First Run:** On startup, the server will automatically download the embedding model (~80MB) into `ThinkTab-AI/models/`. This only happens once.

### 3. Frontend Setup & Chrome Extension Loading
```bash
cd frontend

# Install dependencies
npm install

# Build the extension
npm run build
```

Then load it into Chrome:
1. Open **`chrome://extensions/`**
2. Enable **Developer mode** (top-right toggle)
3. Click **Load unpacked**
4. Select the `frontend/dist/` folder
5. The ThinkTab AI icon will appear in your Chrome toolbar

---

## Environment Variables

Create a `.env` file in the root `ThinkTab-AI/` directory:

```env
# LLM Providers
OPENROUTER_API_KEY=your_openrouter_key   # For gpt-4o-mini (router + filter)
GROQ_API_KEY=your_groq_key               # For llama-3.3-70b (generation)

# Embeddings (no longer needed — switched to local model)
GOOGLE_API_KEY=your_google_key           # Optional, kept for compatibility

# Web Search
SERPER_API_KEY=your_serper_key           # Google Search via Serper.dev

# LangSmith (optional tracing)
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=ThinkTab-AI
```

---

## How to Use

### Daily Startup (2 steps)
```bash
# Terminal 1 — Start backend
cd backend && venv\Scripts\activate && uvicorn app.main:app --reload

# Terminal 2 — (only needed during development)
cd frontend && npm run dev
```

### Using the Chrome Extension
1. Open any website (Wikipedia, news article, blog, etc.)
2. Click the **ThinkTab AI** icon in your Chrome toolbar
3. The Side Panel slides open on the right
4. Select your mode: **Auto**, **Fast ⚡**, or **Deep 🧠**
5. Type your question and press **Enter**
6. Watch the answer stream in real time with live status updates
7. Expand the **Evidence** accordion to verify sources
8. If in Fast Mode, click **Switch to Deep Mode** for a more thorough answer

### Reloading after a rebuild
Click the small **🔄 circular refresh button** in the top-right corner of the ThinkTab AI panel — it calls `chrome.runtime.reload()` instantly without navigating to `chrome://extensions/`.

---

## API Reference

### `POST /api/chat`

**Request Body:**
```json
{
  "query": "What is the main argument of this article?",
  "mode": "auto",
  "contexts": [
    {
      "source_id": "Active Tab",
      "content": "Page Title: ...\n\nParagraph 1...\n\nParagraph 2..."
    }
  ],
  "chat_history": [
    { "role": "user", "content": "Previous message" },
    { "role": "assistant", "content": "Previous answer" }
  ]
}
```

**Response:** Server-Sent Event stream
```
data: {"type": "mode",   "value": "Auto → Selected: Deep 🧠"}
data: {"type": "status", "value": "Evaluating document relevance..."}
data: {"type": "status", "value": "Searching the web for additional context..."}
data: {"type": "final",  "answer": "...", "evidence": [...], "confidence_score": 0.92}
```

---

## Design System

The UI uses a custom Glassmorphism design system defined in `index.css`:

```css
/* Core Tokens */
--bg-primary:       #0a0a0f     /* Deep space dark */
--bg-glass:         rgba(255,255,255,0.04)
--glass-border:     rgba(255,255,255,0.08)
--accent-primary:   #6366f1     /* Indigo */
--accent-secondary: #a855f7     /* Purple */
--text-primary:     #f1f5f9
--text-secondary:   rgba(241,245,249,0.5)
--status-success:   #22c55e
--status-warning:   #f59e0b
--status-error:     #ef4444
```

All cards and panels use `backdrop-filter: blur(20px)` with translucent backgrounds to create the premium glass effect.

---

## Git Commit History Summary

| Phase | Commits |
|---|---|
| Phase 1: Backend Foundation | Steps 1–5 (FastAPI, LangGraph, Fast Mode, Auto Router) |
| Phase 2: Deep Mode (CRAG + Self-RAG) | Steps 6–9 (CRAG nodes, Self-RAG graders, SSE integration) |
| Phase 3: Frontend Development | Steps 10–14 (Vite setup, useSSEChat, HITL, Evidence UI, Error handling) |
| Phase 4: Chrome Extension | Steps 15–18 (manifest.json, content.js, background.js, production build) |

---

*Built with ❤️ using LangGraph, FastAPI, React, and Vite.*