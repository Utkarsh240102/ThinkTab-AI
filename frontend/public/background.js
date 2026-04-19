/* ─────────────────────────────────────────────────────────────
   Background Service Worker (background.js)
   
   This script runs invisibly in the Chrome Extension background.
   Its primary role in Manifest V3 is to listen for the user clicking 
   the extension's icon in the toolbar, and directing Chrome to 
   open our React application as a Side Panel.
─────────────────────────────────────────────────────────────── */

// Listen for when the user clicks the extension icon
chrome.action.onClicked.addListener((tab) => {
  // Instruct Chrome to toggle open the side panel in the current window
  chrome.sidePanel.toggle({ windowId: tab.windowId });
});

// Ensures the side panel is allowed to open on any website the user visits
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch((error) => console.error(error));
