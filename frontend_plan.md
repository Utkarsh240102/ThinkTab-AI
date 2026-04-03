# ThinkTab AI — Frontend Implementation Plan

> A complete, detailed technical blueprint for the React + Vite Chrome Extension (Manifest V3) powering the ThinkTab AI sidebar.

---

## 🎯 Frontend Goals

- Inject a beautiful, non-intrusive sidebar panel into any Chrome tab.
- Allow users to ask questions about the active page and uploaded documents.
- Let users manage which tabs and PDFs to include as context.
- Render streaming AI responses with live status updates.
- Show a rich, expandable Evidence Layer with sourcing and confidence.
- Support Human-in-the-Loop (HITL) mode overrides mid-conversation.

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| Framework | React 18 + TypeScript |
| Build Tool | Vite + `@crxjs/vite-plugin` (Manifest V3 hot-reload) |
| Styling | Vanilla CSS with CSS Variables (design tokens) |
| State Management | Zustand (lightweight, no Redux boilerplate) |
| Streaming | Native browser `EventSource` API (SSE) |
| PDF Extraction | `pdfjs-dist` (browser-side PDF text extraction) |
| Page Extraction | Mozilla `Readability.js` (in content script) |
| Icons | Lucide React |
| Typography | Inter (Google Fonts) |

---

## 📁 Full Project Folder Structure

```text
frontend/
├── public/
│   ├── manifest.json            # Chrome Extension Manifest V3
│   └── icons/
│       ├── icon16.png
│       ├── icon48.png
│       └── icon128.png
├── src/
│   ├── background/
│   │   └── background.ts        # Service worker: manages tab tracking
│   ├── content/
│   │   └── content.ts           # Content script: reads page, injects sidebar
│   ├── sidebar/                 # The main React app (the UI)
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx   # The full conversation list
│   │   │   ├── MessageBubble.tsx  # A single AI/User message
│   │   │   ├── EvidencePanel.tsx  # Expandable evidence snippets
│   │   │   ├── StatusTracker.tsx  # "Evaluating chunks..." live status
│   │   │   ├── ContextManager.tsx # Tab picker + PDF uploader
│   │   │   ├── ModeSelector.tsx   # Fast / Deep / Auto toggle
│   │   │   ├── InputBar.tsx     # Text input + send button
│   │   │   └── ConfidenceBadge.tsx
│   │   ├── store/
│   │   │   ├── chatStore.ts     # Zustand: chat history, messages
│   │   │   └── contextStore.ts  # Zustand: active tabs, uploaded docs
│   │   ├── hooks/
│   │   │   ├── useSSE.ts        # SSE connection hook
│   │   │   └── usePDFExtract.ts # PDF text extraction hook
│   │   ├── utils/
│   │   │   ├── api.ts           # FastAPI request helpers
│   │   │   └── formatters.ts    # Markdown rendering, confidence colors
│   │   ├── styles/
│   │   │   ├── global.css       # CSS reset + design tokens (CSS vars)
│   │   │   └── components.css   # Component-specific styles
│   │   ├── App.tsx              # Root component
│   │   └── main.tsx             # React entry point
│   └── types/
│       └── index.ts             # Shared TypeScript interfaces
├── vite.config.ts
├── tsconfig.json
└── package.json
```

---

## 🔑 Chrome Extension Manifest V3 (`manifest.json`)

```json
{
  "manifest_version": 3,
  "name": "ThinkTab AI",
  "version": "1.0.0",
  "description": "Smart Browser AI Assistant",
  "icons": {
    "16": "icons/icon16.png",
    "48": "icons/icon48.png",
    "128": "icons/icon128.png"
  },
  "permissions": [
    "activeTab",
    "tabs",
    "sidePanel",
    "storage"
  ],
  "host_permissions": [
    "http://localhost:8000/*"
  ],
  "background": {
    "service_worker": "background.js",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": ["<all_urls>"],
      "js": ["content.js"],
      "run_at": "document_idle"
    }
  ],
  "side_panel": {
    "default_path": "index.html"
  },
  "action": {
    "default_title": "Open ThinkTab AI"
  }
}
```

---

## 📜 Content Script (`content.ts`)

The Content Script does all the heavy work of extracting meaningful text from the DOM.

### What it does:
1. **Inject Readability.js**: Mozilla's library that strips out ads, navbars, footers, and cookie banners. Returns clean article/body text.
2. **Convert to Markdown**: We convert the extracted text into clean markdown (using `turndown`) so the LLM receives structured, token-efficient text.
3. **Hash the Content**: Computes a SHA-256 hash of the markdown text.
4. **Communicate to Sidebar**: Posts the `{url, content, hash}` to the sidebar via `chrome.runtime.sendMessage`.

```typescript
// Example message structure to sidebar
chrome.runtime.sendMessage({
  type: "PAGE_CONTENT",
  payload: {
    source_id: window.location.href,
    content: extractedMarkdown,
    hash: contentHash
  }
});
```

---

## 🔵 Background Service Worker (`background.ts`)

The background worker manages the multi-tab awareness of the extension.

- Listens for tab updates and maintains a list of `{tabId, url, title}` for all open tabs.
- When the sidebar requests the list of open tabs, the background worker responds.
- Manages the `chrome.sidePanel` API to open/close the sidebar when the extension icon is clicked.

---

## 🏪 State Management with Zustand

### `chatStore.ts`
```typescript
interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  status?: string[];           // Running list of status updates
  evidence?: EvidenceItem[];
  confidence_score?: number;
  reasoning_summary?: string;
  mode_selected?: string;      // "Fast ⚡" | "Deep 🧠"
  is_loading: boolean;
}

interface ChatStore {
  messages: Message[];
  selectedMode: "fast" | "deep" | "auto";
  addMessage: (message: Message) => void;
  updateMessage: (id: string, updates: Partial<Message>) => void;
  setMode: (mode: "fast" | "deep" | "auto") => void;
}
```

### `contextStore.ts`
```typescript
interface TabContext {
  source_id: string;
  url: string;
  title: string;
  content: string;             // Extracted markdown from content script
  is_selected: boolean;
}

interface UploadedDoc {
  source_id: string;
  filename: string;
  content: string;             // Text extracted from PDF/DOC
}

interface ContextStore {
  activePageContext: TabContext | null;   // Current tab (always included)
  availableTabs: TabContext[];            // Other open tabs user can add
  uploadedDocs: UploadedDoc[];
  setActivePage: (context: TabContext) => void;
  toggleTab: (source_id: string) => void;
  addDocument: (doc: UploadedDoc) => void;
  removeDocument: (source_id: string) => void;
  getSelectedContexts: () => Array<TabContext | UploadedDoc>;
}
```

---

## 📡 SSE Streaming Hook (`useSSE.ts`)

The core hook that manages the streaming connection to our FastAPI backend.

### 🔴 AbortController (Memory Leak Prevention)
Instead of calling `reader.cancel()` to stop a stream, we use the proper `AbortController` pattern. This ensures:
- No **hanging fetch requests** in memory if the component unmounts.
- No **zombie streams** running in the background after a HITL mode switch.
- The browser correctly cleans up the TCP connection to FastAPI.

```typescript
import { useRef, useCallback } from 'react';
import { useChatStore } from '../store/chatStore';

const useSSE = () => {
  const updateMessage = useChatStore(s => s.updateMessage);
  
  // Store the AbortController so we can cancel ANY active request at any time
  const controllerRef = useRef<AbortController | null>(null);

  const cancelStream = () => {
    if (controllerRef.current) {
      controllerRef.current.abort();   // Kills the fetch request immediately
      controllerRef.current = null;
    }
  };

  const sendQuery = useCallback(async (messageId: string, payload: ChatRequest) => {
    // Cancel any existing stream before starting a new one (HITL override support)
    cancelStream();

    const controller = new AbortController();
    controllerRef.current = controller;

    try {
      const response = await fetch("http://localhost:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
        signal: controller.signal    // 👈 Attach the abort signal here
      });

      const reader = response.body!.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const lines = decoder.decode(value).split("\n");
        for (const line of lines) {
          if (!line.startsWith("data:")) continue;
          const event = JSON.parse(line.replace("data:", "").trim());
          handleSSEEvent(messageId, event);
        }
      }
    } catch (err: any) {
      // AbortError is expected when user switches modes (HITL). Ignore it silently.
      if (err.name === 'AbortError') return;
      // Any other real network error should be surfaced to the user
      updateMessage(messageId, { content: "Connection error. Please try again.", is_loading: false });
    } finally {
      controllerRef.current = null;
    }
  }, []);

  const handleSSEEvent = (messageId: string, event: SSEEvent) => {
    switch (event.type) {
      case "mode":
        updateMessage(messageId, { mode_selected: event.value });
        break;
      case "status":
        updateMessage(messageId, (prev) => ({
          status: [...(prev.status ?? []), event.value]
        }));
        break;
      case "token":
        // Fast mode: word-by-word append to content
        updateMessage(messageId, (prev) => ({ content: prev.content + event.value }));
        break;
      case "final":
        updateMessage(messageId, {
          content: event.answer,
          evidence: event.evidence,
          confidence_score: event.confidence_score,
          reasoning_summary: event.reasoning_summary,
          is_loading: false
        });
        break;
    }
  };

  return { sendQuery, cancelStream };
};
```

---

## 🎨 UI Components

### `ModeSelector.tsx` — Mode Toggle
A pill-style toggle button group at the top of the input area:
```
[ 🤖 Auto ]  [ ⚡ Fast ]  [ 🧠 Deep ]
```
- The selected mode is highlighted with the matching color (green for Fast, blue for Deep, purple for Auto).
- State is stored in `chatStore.selectedMode`.

### `InputBar.tsx` — Text Input + Send Button

The input component handles text entry and query submission.

#### 🟡 Debounce (UX Fix — Prevent Accidental Multi-Send)
Without debouncing, a user rapidly double-clicking the send button or pressing Enter twice will fire two completely separate API requests to FastAPI. This wastes LLM tokens and creates duplicate messages in the chat.

**The Fix:** We wrap `sendQuery` in a 300ms debounce. The first click fires instantly, and any subsequent clicks within 300ms are silently ignored.

```typescript
import { useCallback, useRef } from 'react';

const useDebounce = <T extends (...args: any[]) => void>(fn: T, delay: number): T => {
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  return useCallback((...args: Parameters<T>) => {
    if (timer.current) return;  // Already triggered within the delay window — ignore
    fn(...args);
    timer.current = setTimeout(() => {
      timer.current = null;     // Reset after delay so next click can fire
    }, delay);
  }, [fn, delay]) as T;
};

// Usage inside InputBar.tsx:
const { sendQuery } = useSSE();
const debouncedSend = useDebounce(sendQuery, 300);

// Attach to both the Enter key handler and the Send button's onClick:
<button onClick={() => debouncedSend(messageId, payload)} id="send-btn">
  Send
</button>
```

**Why 300ms?** It's imperceptibly fast to a human (they will never feel the delay) but long enough to prevent a double-send from a quick finger slip on Enter.

### `ContextManager.tsx` — Multi-Source Manager
Displayed at the top of the sidebar. Shows a horizontal scrollable row of **pills** representing included sources:
- **Active Tab Pill** (always shown, not removable): `🌐 stripe.com ✓`
- **Add Tab Button**: Opens a dropdown listing all open Chrome tabs. User can tick checkboxes to include them.
- **Upload Button** (paperclip icon): Opens a file picker for PDF/DOC files. Shows a progress bar while `pdfjs-dist` extracts the text.
- **Uploaded Doc Pills**: `📄 report.pdf ✕` with a remove button.

### `MessageBubble.tsx` — AI Response Component
The most complex component. A single chat bubble has **multiple internal states**:

**State 1: Loading (Deep Mode)**
```
[ThinkTab AI Avatar]
┌─────────────────────────────────────────┐
│  ✓ Reading 3 sources...                 │
│  ✓ Evaluating chunk relevance...        │
│  ⟳ Context missing. Searching Google... │
│  [Animated loading skeleton]            │
└─────────────────────────────────────────┘
```

**State 2: Streaming (Fast Mode)**
```
[ThinkTab AI Avatar]
┌─────────────────────────────────────────┐
│  Mode: Auto → Selected: Fast ⚡          │
│  [Switch to Deep 🧠]                    │
│                                         │
│  Stripe charges 2.9% + 30c per         │
│  transaction for online payments. They  │
│  also offer...  | (blinking cursor)     │
└─────────────────────────────────────────┘
```

**State 3: Final Answer**
```
[ThinkTab AI Avatar]
┌─────────────────────────────────────────┐
│  Mode: Auto → Deep 🧠   🟢 91%          │
│  ─────────────────────────────────────  │
│  💡 Compared 3 sources + web search     │
│                                         │
│  **Stripe vs PayPal Pricing:**          │
│  - Stripe: 2.9% + $0.30 per txn        │
│  - PayPal: 3.49% + $0.49 per txn       │
│                                         │
│  [▶ View Sources (3)]                   │
└─────────────────────────────────────────┘
```

### `EvidencePanel.tsx` — Expandable Sources Accordion

Clicking `[▶ View Sources (3)]` expands the accordion below the answer:

```
▼ Sources Used

🔗 stripe.com
   "Stripe charges 2.9% + 30¢ for successful card charges."

🔗 paypal.com
   "PayPal's standard rate is 3.49% + fixed fee per transaction."

🌐 Web Search (Tavily)
   "PayPal limits free transfers to $10,000 per transaction."
```

Each snippet links back to the original source (clickable `<a>` tag that opens the URL in a new tab).

### `ConfidenceBadge.tsx`

A small floating badge in the top-right corner of the AI bubble:
- `🟢 92%` — Green (high confidence, local sources)
- `🟡 65%` — Yellow (medium, may include web fallback)
- `🔴 38%` — Red (low, lots of rewrites or web-only information)

### `StatusTracker.tsx`

Maps the `message.status` array into a vertical step-by-step tracker shown inside the loading bubble. Each step shows a ✓ checkmark once confirmed. The latest step shows a spinning animation.

---

## 🔄 Complete User Flow (End-to-End)

1. User opens Chrome Extension (sidebar appears).
2. Content Script on the current tab immediately reads the page via Readability.js and sends the clean markdown to the sidebar.
3. Sidebar receives `PAGE_CONTENT` message and stores it in `contextStore.activePageContext`.
4. User optionally:
   - Picks **more tabs** from the Context Manager dropdown.
   - **Uploads a PDF** (extracted browser-side with pdfjs-dist).
5. User picks a **Mode** (`Auto`, `Fast`, `Deep`) from the toggle.
6. User types a question and hits Enter.
7. **Sidebar packages the request:**
   ```json
   {
     "query": "Compare pricing on all three",
     "mode": "auto",
     "contexts": [
       {"source_id": "stripe.com", "content": "..."},
       {"source_id": "paypal.com", "content": "..."},
       {"source_id": "my_doc.pdf", "content": "..."}
     ],
     "chat_history": [...]
   }
   ```
8. A new loading `MessageBubble` appears in the chat window.
9. The `useSSE` hook opens a connection to `POST /api/chat`.
10. Events are handled live:
    - `mode` event → updates the bubble header with selected mode.
    - `status` events → tick off the `StatusTracker` steps one by one.
    - `token` events → stream words (Fast Mode).
    - `final` event → renders the full answer, evidence accordion, and confidence badge.
11. **HITL Override**: If the user is unsatisfied, they click `[Switch to Deep]` or `[Switch to Fast]`. The hook calls `cancelStream()` which triggers `controller.abort()` — this cleanly kills the FastAPI SSE connection with no memory leaks — and immediately POSTs the same query with the new `mode`.

---

## 🎨 Design System (`global.css`)

```css
:root {
  /* Color Palette */
  --color-bg: #0f0f13;
  --color-surface: #1a1a24;
  --color-surface-2: #23232f;
  --color-border: #2e2e3e;
  --color-text-primary: #f0f0f5;
  --color-text-secondary: #8888aa;
  --color-accent-fast: #22c55e;   /* Green for Fast mode */
  --color-accent-deep: #3b82f6;   /* Blue for Deep mode */
  --color-accent-auto: #a855f7;   /* Purple for Auto mode */

  /* Confidence Colors */
  --color-confidence-high: #22c55e;
  --color-confidence-mid: #f59e0b;
  --color-confidence-low: #ef4444;

  /* Typography */
  --font-family: 'Inter', sans-serif;
  --font-size-sm: 12px;
  --font-size-md: 14px;
  --font-size-lg: 16px;

  /* Spacing */
  --radius-sm: 6px;
  --radius-md: 12px;
  --radius-lg: 18px;

  /* Transitions */
  --transition: all 0.2s ease;
}
```

---

## 🚀 Build Order (Step-by-Step Coding Plan)

| Phase | Task |
|---|---|
| Phase 1 | Init Vite project with `@crxjs/vite-plugin`, configure `manifest.json`, add TypeScript |
| Phase 2 | Build `global.css` design system tokens |
| Phase 3 | Build `background.ts` service worker (tab tracking) |
| Phase 4 | Build `content.ts` script (Readability.js extraction + messaging) |
| Phase 5 | Set up Zustand stores (`chatStore`, `contextStore`) |
| Phase 6 | Build `useSSE.ts` hook with **AbortController** + wire to mock API for testing |
| Phase 7 | Build `ModeSelector.tsx` and `InputBar.tsx` with **Debounce (300ms)** |
| Phase 8 | Build `ContextManager.tsx` (tab picker + PDF upload) |
| Phase 9 | Build `MessageBubble.tsx` with all 3 states (loading, streaming, final) |
| Phase 10 | Build `StatusTracker.tsx`, `EvidencePanel.tsx`, `ConfidenceBadge.tsx` |
| Phase 11 | Build `ChatWindow.tsx` (full conversation rendering) |
| Phase 12 | Assemble `App.tsx` with all components |
| Phase 13 | Implement HITL override using `cancelStream()` from `useSSE.ts` |
| Phase 14 | Test with live backend |
| Phase 15 | Polish animations, loading states, and responsive layout |
