// background.js - Leecher Session Capture background script
// Automatically loads the GitHub Gist token from local gist_token.txt file on extension startup

async function loadTokenFromFile() {
  try {
    const url = chrome.runtime.getURL('gist_token.txt');
    console.log('Fetching token from:', url);
    const response = await fetch(url);
    const tokenText = await response.text();
    const token = tokenText.trim();

    if (token && token !== 'PUT_YOUR_GITHUB_TOKEN_HERE' && token.length > 20) {
      await chrome.storage.local.set({ githubToken: token });
      console.log('✅ GitHub token successfully loaded from gist_token.txt and stored.');
      return token;
    } else {
      console.log('⚠️ No valid token found in gist_token.txt. Please update your token.');
      return null;
    }
  } catch (error) {
    console.error('⚠️ Could not read gist_token.txt:', error.message);
    return null;
  }
}

// Initialize on installation or startup
chrome.runtime.onInstalled.addListener(async () => {
  console.log('🚀 Leecher Session Capture installed!');
  await loadTokenFromFile();
});

chrome.runtime.onStartup.addListener(async () => {
  console.log('🚀 Browser started, reloading token...');
  await loadTokenFromFile();
});

// Allow the popup to trigger a reload of the token dynamically
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'reloadToken') {
    loadTokenFromFile().then((token) => {
      sendResponse({ success: !!token, token: token });
    });
    return true; // Keep message channel open for async response
  }
});
