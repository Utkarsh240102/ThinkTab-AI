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
    
    // 2. Grab all paragraph text on the page
    // We target <p> tags instead of document.body.innerText to avoid 
    // scraping hidden script tags, raw HTML, or massive ad blocks.
    const paragraphs = Array.from(document.querySelectorAll("p"))
      .map(p => p.innerText.trim())
      // Filter out tiny snippets or empty tags (likely UI elements)
      .filter(text => text.length > 40);
    
    // 3. Assemble the payload
    // We push the Title in first so the AI knows exactly what site we are on
    const contextsArray = [`Page Title: ${pageTitle}`, ...paragraphs];
    
    // Limit to 8 entries before merging
    const limitedContexts = contextsArray.slice(0, 8);

    // IMPORTANT: Merge all paragraphs into ONE string before sending.
    // The backend creates a separate FAISS embedding job per context item.
    // Sending 8 separate items = 8 API calls = quota exhausted instantly.
    // Merging into 1 item = 1 API call = safely within free tier limits.
    const mergedContext = limitedContexts.join("\n\n");

    // Send it back to React as a single-item array
    sendResponse({ contexts: [mergedContext] });
  }

  // Return true to indicate we will send a response asynchronously 
  // (though in this specific synchronous case it's just good practice)
  return true; 
});
