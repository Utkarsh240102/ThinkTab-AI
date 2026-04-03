# ThinkTab AI — Step-by-Step Build Plan

> This is the master task list. We will work through one step at a time. Each step has clear substeps. Mark them off as we go.

---

## 🗂️ STEP 1 — Project Setup & Environment

### 1.1 Create folder structure
- [ ] Create `backend/` folder inside `d:\PROJECTS\ThinkTab-AI\`
- [ ] Create `frontend/` folder inside `d:\PROJECTS\ThinkTab-AI\`
- [ ] Create `backend/app/api/`, `backend/app/core/`, `backend/app/graph/nodes/`, `backend/app/services/` folders

### 1.2 Setup Python environment (Backend)
- [ ] Create a Python virtual environment inside `backend/`
- [ ] Install all dependencies from `requirements.txt`
- [ ] Verify all packages import correctly

### 1.3 Setup `.env` file
- [ ] Add `OPENROUTER_API_KEY` (for `gpt-4o-mini`)
- [ ] Add `GROQ_API_KEY` (for `GPT OSS 120B`)
- [ ] Add `GOOGLE_API_KEY` (for Gemini embeddings)
- [ ] Add `TAVILY_API_KEY` (for web search fallback)
- [ ] Add `LANGSMITH_API_KEY` (for tracing)

### 1.4 Create `config.py`
- [ ] Use `pydantic-settings` to load all `.env` values
- [ ] Define all global constants (model names, thresholds, max cache size)

### 1.5 Create `main.py`
- [ ] Initialize FastAPI app
- [ ] Add basic health check route `GET /health`
- [ ] Run server with Uvicorn and confirm it works

---

## 🧠 STEP 2 — LLM & Embedding Services

### 2.1 Build `llm_service.py`
- [ ] Configure `gpt-4o-mini` via LangChain + OpenRouter (for routing, filtering, scoring)
- [ ] Configure `GPT OSS 120B` via LangChain + Groq (for final generation)
- [ ] Test both models with a simple `.invoke("Hello")` call

### 2.2 Build `embedder.py`
- [ ] Configure Google Generative AI Embeddings (`models/gemini-embedding-001`)
- [ ] Write `chunk_and_embed(content: str)` function using `RecursiveCharacterTextSplitter`
  - Chunk size: 500 characters, overlap: 50
- [ ] Test: embed a short paragraph and confirm it returns a vector

### 2.3 Build `vector_store.py` — LRU Embedding Cache
- [ ] Implement `LRUEmbeddingCache` class with `OrderedDict`
- [ ] Implement `get_key(content)` → `sha256` hash of content
- [ ] Implement `get(key)` → returns existing FAISS index or `None`
- [ ] Implement `set(key, faiss_index)` → evicts oldest if `max_size=20` is hit
- [ ] Test: embed a page, retrieve it by hash, confirm it skips re-embedding

---

## 🏗️ STEP 3 — LangGraph State + API Skeleton

### 3.1 Build `state.py`
- [ ] Define `GraphState` TypedDict with all fields:
  - `query`, `original_query`, `mode`, `selected_mode`, `chat_history`, `contexts`
  - `docs`, `good_docs`, `refined_context`
  - `crag_verdict`, `web_query`, `web_docs`
  - `draft_answer`, `final_answer`, `evidence`, `confidence_score`, `reasoning_summary`
  - `is_supported`, `is_useful`, `revision_retries`, `retrieval_retries`

### 3.2 Build `endpoints.py` — SSE Streaming Skeleton
- [ ] Create `POST /api/chat` route
- [ ] Implement Server-Sent Events (SSE) response using `sse-starlette`
- [ ] Add a test that streams 5 fake events: `{"type": "status", "value": "Thinking..."}`
- [ ] Confirm Chrome / Postman can read the live SSE stream

### 3.3 Connect endpoint to `main.py`
- [ ] Register the router from `endpoints.py` in `main.py`
- [ ] Test full request-response cycle with a mock payload

---

## ⚡ STEP 4 — Fast Mode Pipeline

### 4.1 Build the Query Contextualizer (`contextualizer.py`)
- [ ] Write `contextualize_query(query, chat_history)` function
- [ ] Use `gpt-4o-mini` to rewrite vague follow-up questions into standalone questions
- [ ] Test: pass `"explain the second one"` with a chat history → confirm it rewrites correctly

### 4.2 Build Retrieval + Re-Ranking (`retrieval.py`)
- [ ] Write `retrieve_chunks(query, faiss_index, k=10)` → returns top 10 chunks
- [ ] Integrate Re-Ranker (`bge-reranker-base` or Cohere Rerank) to sort and keep top 3
- [ ] Test: retrieve from a cached page and confirm top 3 are the most relevant

### 4.3 Build Batch CRAG Filter for Fast Mode
- [ ] Write a single-prompt filter using `gpt-4o-mini` that accepts 3 numbered chunks
- [ ] Return only the indices of relevant chunks as JSON: `{"keep": [1, 3]}`
- [ ] Test: send 3 chunks (one clearly irrelevant) and confirm it drops the right one

### 4.4 Build Fast Mode Generator (`generation.py`)
- [ ] Write `generate_fast(query, chunks)` using `GPT OSS 120B` via Groq
- [ ] Use strict system prompt: answer only from provided context, cite sources in brackets
- [ ] Use `.with_structured_output()` to return `FinalOutput` Pydantic model
- [ ] Test: generate an answer and confirm `evidence` and `confidence_score` fields are populated

### 4.5 Assemble `fast_mode.py`
- [ ] Wire all steps together: Contextualize → Cache Check → Retrieve → Re-rank → Filter → Generate
- [ ] Add Safety Net: if answer is `"I cannot find the answer"`, set flag for auto-upgrade to Deep Mode
- [ ] Stream each step status via SSE: `"Retrieving chunks..."`, `"Filtering..."`, `"Generating..."`
- [ ] End-to-end test: send a real question about a real webpage and get a structured answer back

---

## 🧠 STEP 5 — Auto Mode Router

### 5.1 Build `auto_router.py`
- [ ] Implement Document Count Check: if `len(contexts) > 1` → force Deep Mode
- [ ] Implement Keyword Rule Check with the list: `["compare", "analyze", "why", "evaluate", "difference", "between", "across", "validate"]`
- [ ] Implement LLM Intent Classifier using `gpt-4o-mini` (returns `"simple"` or `"complex"`)
- [ ] Return the selected mode + stream SSE event: `{"type": "mode", "value": "Auto → Fast ⚡"}`

### 5.2 Wire Auto Router into `endpoints.py`
- [ ] Call `auto_router(payload)` before invoking Fast or Deep pipeline
- [ ] Based on result, call either `fast_mode.run()` or `deep_mode.run()`
- [ ] Implement Safety Net: catch `"cannot find answer"` from Fast Mode and rerun as Deep Mode
  - Stream: `{"type": "status", "value": "Upgrading to Deep Search... 🧠"}`

---

## 🔬 STEP 6 — Deep Mode: CRAG Nodes

### 6.1 Build `crag_evaluator.py`
- [ ] Write `eval_docs(query, docs)` → score each chunk 0.0 to 1.0 using `gpt-4o-mini`
- [ ] Classify result: `CORRECT` (any > 0.7), `INCORRECT` (all < 0.3), `AMBIGUOUS` (else)
- [ ] Store verdict in `GraphState.crag_verdict`
- [ ] Test with 4 chunks of mixed quality

### 6.2 Build `web_search.py`
- [ ] Write `rewrite_for_web(query)` → generates a short Google-friendly search string using `gpt-4o-mini`
- [ ] Write `search_web(query)` → calls Tavily API, returns up to 5 `Document` objects tagged with `source_id = "web_tavily"`
- [ ] Test: rewrite a complex query and verify Tavily returns relevant snippets

### 6.3 Build `crag_refiner.py`
- [ ] Split all incoming documents into individual sentences
- [ ] Build one batched prompt with all sentences indexed (e.g., `[0] sentence`, `[1] sentence`)
- [ ] Use `gpt-4o-mini` to return `{"keep": [0, 3, 7]}` — indices of relevant sentences only
- [ ] Reconstruct `refined_context` from the kept sentences
- [ ] Test: pass a chunk with 10 sentences (including 3 clearly off-topic) and confirm those 3 are dropped

---

## 🔍 STEP 7 — Deep Mode: Self-RAG Nodes

### 7.1 Build `self_rag.py` — IsSUP (Grounding Check)
- [ ] Write `is_supported(draft_answer, refined_context)` using `gpt-4o-mini`
- [ ] Prompt: "Does this answer contain ANY claim not found in the context? Return JSON: `{"supported": true/false, "issue": "..."}`"
- [ ] If `false`: increment `revision_retries`, trigger `revise_answer` (max 2 loops)
- [ ] Test: inject a hallucinated fact and confirm it catches it

### 7.2 Build `self_rag.py` — IsUSE (Usefulness Check)
- [ ] Write `is_useful(query, answer)` using `gpt-4o-mini`
- [ ] Prompt: "Does this answer actually help the user with their question? Return JSON: `{"useful": true/false, "reason": "..."}`"
- [ ] If `false`: increment `retrieval_retries`, trigger `rewrite_question` (max 2 loops)
- [ ] Test: give it an off-topic answer and confirm it flags it

### 7.3 Build Revision + Rewrite Nodes
- [ ] `revise_answer(draft, refined_context)` → rewrites draft using Groq, constrained strictly to context
- [ ] `rewrite_question(query, reason)` → rewrites question from a different angle using `gpt-4o-mini`

---

## 🔗 STEP 8 — Deep Mode: Full LangGraph Assembly

### 8.1 Build `deep_mode.py` — Wire all nodes into StateGraph
- [ ] Define all nodes: `check_cache`, `decide_retrieval`, `retrieve_chunks`, `crag_evaluator`, `crag_refiner`, `web_search`, `generate_draft`, `is_sup`, `revise_answer`, `is_use`, `rewrite_question`, `generate_direct`
- [ ] Define all conditional edges (routing logic between nodes)
- [ ] Add safety guards: `revision_retries <= 2`, `retrieval_retries <= 2`
- [ ] Compile the graph with `StateGraph.compile()`

### 8.2 Connect LangSmith Observability
- [ ] Set `LANGCHAIN_TRACING_V2=true` in `.env`
- [ ] Confirm traces appear on LangSmith dashboard for each graph run
- [ ] Identify the slowest node in a sample run

### 8.3 Stream Deep Mode status events via SSE
- [ ] After each node completes, yield a status SSE event to the frontend
- [ ] Order: `"Reading sources..."` → `"Evaluating chunks..."` → `"Searching web..."` → `"Filtering sentences..."` → `"Generating draft..."` → `"Checking for hallucinations..."` → `"Verifying usefulness..."`
- [ ] End-to-end test: ask a complex multi-source question and watch all status events fire correctly

---

## 📡 STEP 9 — Full API Integration & Testing

### 9.1 Finalize `POST /api/chat` endpoint
- [ ] Accept full request body: `query`, `mode`, `contexts[]`, `chat_history[]`
- [ ] Route to Auto Router → Fast Mode or Deep Mode based on result
- [ ] Return a full SSE stream including mode event, status events, and final JSON payload

### 9.2 Build `POST /api/embed` endpoint
- [ ] Accept a single `{source_id, content}` payload
- [ ] Pre-embed the page content and store it in LRU cache
- [ ] Return `{"status": "cached", "hash": "..."}` response

### 9.3 Build `DELETE /api/cache/{source_id}` endpoint
- [ ] Remove the matching FAISS index from the LRU cache
- [ ] Return `{"status": "evicted"}`

### 9.4 Manual End-to-End API Tests
- [ ] Test Fast Mode with a single-tab simple question
- [ ] Test Deep Mode with a multi-tab comparison question
- [ ] Test Auto Mode routing (simple → Fast, complex → Deep)
- [ ] Test Safety Net (Fast Mode fails → auto upgrades to Deep)
- [ ] Test HITL override (user manually switches mode mid-stream)
- [ ] Test LRU cache eviction after 20 pages

---

## 🌐 STEP 10 — Frontend: Project Init & Core

### 10.1 Init Vite + React + TypeScript
- [ ] Run `npm create vite@latest frontend -- --template react-ts`
- [ ] Install `@crxjs/vite-plugin` for Manifest V3 hot-reload
- [ ] Configure `vite.config.ts` for the Chrome Extension build

### 10.2 Setup `manifest.json`
- [ ] Set permissions: `activeTab`, `tabs`, `sidePanel`, `storage`
- [ ] Configure `content_scripts` and `background.service_worker`
- [ ] Configure `side_panel.default_path`

### 10.3 Setup Design System (`global.css`)
- [ ] Define all CSS variables: colors, typography, spacing, border-radius
- [ ] Import Inter font from Google Fonts
- [ ] Apply dark mode base styles to `body`

### 10.4 Setup Zustand Stores
- [ ] Build `chatStore.ts`: messages array, selected mode, `addMessage`, `updateMessage`
- [ ] Build `contextStore.ts`: active tab, available tabs, uploaded docs, `getSelectedContexts()`

---

## 📜 STEP 11 — Frontend: Chrome Extension Scripts

### 11.1 Build `content.ts`
- [ ] Inject Mozilla `Readability.js` to extract clean article text from DOM
- [ ] Convert extracted text to Markdown using `turndown`
- [ ] Compute `sha256` hash of the markdown text
- [ ] Send `PAGE_CONTENT` message to sidebar via `chrome.runtime.sendMessage`

### 11.2 Build `background.ts`
- [ ] Track all open tabs via `chrome.tabs.onUpdated` and `chrome.tabs.onRemoved`
- [ ] Respond to `GET_ALL_TABS` message from sidebar with list of `{tabId, url, title}`
- [ ] Handle `chrome.action.onClicked` to open/close side panel

---

## 💬 STEP 12 — Frontend: Core UI Components

### 12.1 Build `ModeSelector.tsx`
- [ ] Three pill buttons: Auto, Fast, Deep
- [ ] Active state styling with mode-specific color (purple, green, blue)
- [ ] On click: update `chatStore.selectedMode`

### 12.2 Build `InputBar.tsx` with Debounce
- [ ] Textarea that expands up to 4 lines
- [ ] Send button (disabled while AI is loading)
- [ ] `useDebounce(sendQuery, 300ms)` hook to prevent accidental double-sends
- [ ] Handle Enter key (send) vs Shift+Enter (new line)

### 12.3 Build `ContextManager.tsx`
- [ ] Display active page pill (always pinned, cannot remove)
- [ ] Add Tab dropdown: shows all open Chrome tabs as checkboxes
- [ ] PDF upload button: triggers file picker, extracts text with `pdfjs-dist`, adds pill
- [ ] Show context count: `3 sources selected`

### 12.4 Build `useSSE.ts` hook
- [ ] Implement `AbortController` with `useRef` to prevent memory leaks
- [ ] Implement `cancelStream()` function
- [ ] Implement `sendQuery(messageId, payload)` with `fetch + signal`
- [ ] Implement `handleSSEEvent()` for: `mode`, `status`, `token`, `final`, `error` events

---

## 💬 STEP 13 — Frontend: Chat UI Components

### 13.1 Build `StatusTracker.tsx`
- [ ] Renders a vertical list of status steps
- [ ] Completed steps: show green ✓ checkmark
- [ ] Current step: show spinning animation
- [ ] Animate in each new step as it arrives via SSE

### 13.2 Build `ConfidenceBadge.tsx`
- [ ] Accepts a `score: number` prop (0.0 to 1.0)
- [ ] `>= 0.75` → 🟢 Green badge
- [ ] `>= 0.5` → 🟡 Yellow badge
- [ ] `< 0.5` → 🔴 Red badge

### 13.3 Build `EvidencePanel.tsx`
- [ ] Collapsible accordion component
- [ ] Renders each `EvidenceItem` as: source icon + source name + quoted snippet
- [ ] Web sources (Tavily) show 🌐 globe icon
- [ ] PDF sources show 📄 icon, local tabs show 🔗 icon
- [ ] Each snippet is a clickable link that opens the source URL

### 13.4 Build `MessageBubble.tsx`
- [ ] State 1 (Loading / Deep): renders `StatusTracker` inside bubble, no text yet
- [ ] State 2 (Streaming / Fast): renders token-by-token text with blinking cursor + HITL override buttons
- [ ] State 3 (Final): renders full markdown answer + `ConfidenceBadge` + `EvidencePanel` accordion
- [ ] Show `mode_selected` pill in top-left corner of bubble

### 13.5 Build `ChatWindow.tsx`
- [ ] Renders a scrollable list of all `Message` objects from `chatStore`
- [ ] Auto-scroll to bottom on new message
- [ ] Empty state: show a welcome card with example questions

---

## 🔗 STEP 14 — Frontend: Assemble & Wire

### 14.1 Build `App.tsx`
- [ ] Layout: `ContextManager` at top, `ChatWindow` in middle, `InputBar + ModeSelector` at bottom
- [ ] Listen for `PAGE_CONTENT` messages from content script, update `contextStore`

### 14.2 Implement HITL Override
- [ ] Fast Mode bubble shows `[Switch to Deep 🧠]` button
- [ ] Deep Mode bubble shows `[Switch to Fast ⚡]` button
- [ ] On click: call `cancelStream()` then `sendQuery()` with the new mode
- [ ] Bubble resets to loading state instantly

### 14.3 Wire Frontend to Backend
- [ ] Confirm all SSE events are received correctly from `POST /api/chat`
- [ ] Confirm pre-embedding fires correctly via `POST /api/embed`
- [ ] Test stress: switch modes rapidly, confirm no memory leaks or duplicate messages

---

## 🎨 STEP 15 — Polish & Final Testing

### 15.1 Animations & Micro-interactions
- [ ] Smooth fade-in for new chat bubbles
- [ ] Evidence accordion expand/collapse animation
- [ ] Status tracker step-in animation
- [ ] Confidence badge color transition animation

### 15.2 Edge Case Handling
- [ ] Empty page (extension opened on a `chrome://` tab) → show friendly error
- [ ] Backend unreachable → show `"Could not connect to ThinkTab AI server"` error bubble
- [ ] PDF upload fails to extract text → show warning toast
- [ ] All CRAG/Self-RAG retries exhausted → show low-confidence answer with warning

### 15.3 Full End-to-End QA
- [ ] Test Fast Mode on a simple factual page
- [ ] Test Deep Mode on a complex comparison across 2 tabs + 1 PDF
- [ ] Test Auto Mode on both simple and complex queries
- [ ] Test HITL override from Fast → Deep and Deep → Fast
- [ ] Test Safety Net (Fast Mode failure upgrades to Deep)
- [ ] Test LRU cache (20+ pages, confirm oldest is evicted)
- [ ] Test Chat History (follow-up question resolves correctly via contextualizer)

---

## ✅ Done!
Once Step 15 is complete, the ThinkTab AI Chrome Extension backend and frontend will be fully functional and ready for use!
