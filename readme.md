# ThinkTab AI

> **Your Contextual Web Assistant**

ThinkTab AI is a powerful, contextual AI research assistant packaged as a Google Chrome Extension. It seamlessly integrates into your browsing experience via the Chrome side panel, allowing you to ask complex questions, extract insights, and summarize the content of the webpages you are currently reading. ThinkTab AI operates with a **Soft Human-in-the-Loop (HITL)** design, providing instant responses with the option to escalate complex tasks to a deeper, self-evaluating reasoning pipeline.

---

## 🌟 Advanced Features

- **Multi-Tab Context Awareness:** ThinkTab is not limited to just your active tab. You can "pin" multiple tabs, and ThinkTab will seamlessly aggregate and search across all pinned tabs plus your current active tab to answer cross-reference queries.
- **Dynamic PDF Attachment Support:** Upload a local PDF file, and ThinkTab will extract the text entirely on the client side (using `pdfjs-dist`) and inject it into your context window alongside your web pages. 
- **Intelligent UI Label Resolution:** ThinkTab understands that when you type "this tab", "the pdf", or "the pinned tab", you are referring to a specific loaded document. It uses a structured LLM router to map these UI terms to the exact document IDs deterministically, preventing confusing general knowledge hallucinations.
- **Soft Human-in-the-Loop (HITL):** Need a quick answer? Use Fast Mode. If the answer isn't detailed enough, you can seamlessly escalate to Deep Mode with a single click, allowing the AI to re-read the context and perform rigorous self-evaluation.

---

## 🛠️ Tech Stack & Architecture

ThinkTab AI uses a robust split architecture, pairing a fast client-side Chrome Extension with a heavy-duty Python local backend.

**Frontend (Chrome Extension)**
- **React 19 & TypeScript 6**
- **Vite 8**
- **Tailwind-inspired Vanilla CSS** (Glassmorphism & Dark Mode)
- **Client-Side PDF Extraction** (`pdfjs-dist`)
- **Chrome Extension APIs** (`sidePanel`, `activeTab`, `scripting`)

**Backend (Local Python Server)**
- **FastAPI & Uvicorn** for Server-Sent Events (SSE) streaming
- **LangChain & LangGraph** for orchestrating the multi-agent RAG pipeline
- **ChromaDB** for persistent local vector caching
- **BAAI/bge-m3** (runs on CPU) for 1024-dimensional document embeddings
- **BAAI/bge-reranker-base** for cross-encoder search re-ranking
- **GPT-4o-mini** (via OpenRouter) as the "Fast Brain" for routing, CRAG scoring, and evaluation
- **Llama-3.3-70B** (via Groq) as the "Smart Brain" for final answer generation
- **Serper API** for Google Search fallback

---

## 🧠 Fast Mode vs. Deep Mode (The RAG Pipeline)

When you ask a question, ThinkTab's **Auto Router** analyzes your intent and determines the best RAG (Retrieval-Augmented Generation) pipeline for the job.

### ⚡ Fast Mode
Designed for speed and simple factual extraction. 
1. **Contextualization**: Resolves pronouns (e.g. "summarize *it*").
2. **Retrieve & Rerank**: Fetches relevant chunks from ChromaDB and cross-encodes them.
3. **Batch CRAG Filter**: Swiftly drops irrelevant chunks.
4. **Generate**: Streams the answer directly to the UI.

### 🕵️ Deep Mode (Self-RAG)
Designed for complex comparisons, evaluations, and ambiguous queries. LangGraph orchestrates a multi-step Directed Acyclic Graph (DAG) with self-correction loops.
1. **Contextualization & Retrieval**: Same initial steps as Fast Mode.
2. **CRAG Evaluation**: Critiques the quality of the retrieved context. If the context is ambiguous or insufficient, it triggers a **Web Search Fallback** via Google.
3. **CRAG Refiner**: Condenses all gathered context (local + web) into a hyper-dense knowledge block.
4. **Generate Draft**: Llama 3 generates a draft answer.
5. **Hallucination Grader**: Checks if the draft is strictly grounded in the provided context. If not, it forces a rewrite.
6. **Usefulness Grader**: Checks if the answer actually resolves your original question.
7. **Automated Rewriting**: If the answer fails the Usefulness check, the **Question Rewriter** dynamically rephrases your original query and triggers a full **Re-Retrieval** loop to try again from a new angle.

---

## 🚀 Getting Started

*(Instructions for local setup, installing the unpacked extension in Chrome, and starting the FastAPI server go here).*
