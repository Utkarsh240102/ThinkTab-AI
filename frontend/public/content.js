/* ─────────────────────────────────────────────────────────────
   Content Script (content.js)
   
   Driven directly into the DOM of the active web page.
   It listens for requests from the React Side Panel, scrapes
   meaningful text from the page (title, paragraphs), and 
   returns it to power Contextual queries.
─────────────────────────────────────────────────────────────── */

// Listen for messages from the Chrome Extension UI (the React app)
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  
  if (request.action === "SCRAPE_PAGE_CONTEXT") {
    
    // 1. Grab the official page title
    const pageTitle = document.title || "Untitled Page";
    
    // 2. Grab text from ALL meaningful semantic elements — not just <p>.
    // Modern web apps (React, Vue, Angular, GitHub, Reddit, StackOverflow)
    // rarely put their content in <p> tags. We cast a wider net here so
    // we reliably capture content regardless of the site's HTML structure.
    const CONTENT_SELECTOR = "p, article, section, li, td, th, h1, h2, h3, h4, h5, h6, blockquote, pre, code";
    // BUG2-005 FIX: Leaf-node deduplication ─────────────────────────────────
    // querySelectorAll matches elements at every level of the DOM tree.
    // For a structure like <section><p>Text</p></section>, the old code
    // extracted "Text" twice: once from <section> and once from <p>.
    // On content-heavy pages (Wikipedia, docs sites) this wasted 30-50% of
    // the 15,000-char budget on near-identical repeated text blocks.
    //
    // Fix: build a Set of all matched nodes, then keep only "leaf" elements —
    // those that do NOT contain any other matched element as a descendant.
    // This ensures we always extract text from the most specific (deepest)
    // match, never from an ancestor that would duplicate its children's text.
    const allNodes = document.querySelectorAll(CONTENT_SELECTOR);
    const allMatched = new Set(allNodes);
    const leafElements = Array.from(allNodes).filter(el => {
      // querySelectorAll on the element itself finds all matched descendants.
      // If any exist in allMatched, this element is a parent — skip it.
      const children = el.querySelectorAll(CONTENT_SELECTOR);
      return !Array.from(children).some(child => allMatched.has(child));
    });

    const elements = leafElements
      .map(el => el.innerText.trim())
      // Filter out tiny snippets, empty tags, and nav/button labels (likely UI noise)
      .filter(text => text.length > 40);
    
    // 3. Assemble the payload — title first so the AI knows what site we are on
    const contextsArray = [`Page Title: ${pageTitle}`, ...elements];
    
    // Use a CHARACTER BUDGET instead of a hard entry count.
    // A budget of 15,000 chars is enough for the embedding model to work well
    // without overwhelming the FAISS index or the LLM context window.
    // Short pages may contribute 40+ entries; long pages maybe 10 — always ~15k chars.
    const MAX_CHARS = 15000;
    let totalChars = 0;
    const limitedContexts = [];
    for (const entry of contextsArray) {
      if (totalChars + entry.length > MAX_CHARS) break;
      limitedContexts.push(entry);
      totalChars += entry.length;
    }

    // IMPORTANT: Merge all entries into ONE string before sending.
    // The backend creates a separate FAISS embedding job per context item.
    // Sending N separate items = N API calls = quota exhausted instantly.
    // Merging into 1 item = 1 API call = safely within free tier limits.
    const mergedContext = limitedContexts.join("\n\n");


    // Send it back to React as a single-item array
    sendResponse({ contexts: [mergedContext] });
  }

});
