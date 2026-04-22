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
    
    // Limit to 8 entries (title + 7 paragraphs).
    // The Gemini free tier allows 100 embedding requests/min — 
    // sending too many paragraphs exhausts this quota instantly.
    const limitedContexts = contextsArray.slice(0, 8);
    
    // Send it back to React
    sendResponse({ contexts: limitedContexts });
  }

  // Return true to indicate we will send a response asynchronously 
  // (though in this specific synchronous case it's just good practice)
  return true; 
});
