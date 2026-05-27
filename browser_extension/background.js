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

// --- NEW: Intercept direct downloads (like IDM) ---
chrome.downloads.onCreated.addListener(async (downloadItem) => {
  console.log('📥 Download intercepted:', downloadItem);

  const downloadUrl = downloadItem.url;
  const refererUrl = downloadItem.referrer || '';
  const filename = downloadItem.filename || '';

  // Skip temporary or non-http downloads
  if (!downloadUrl || !downloadUrl.toLowerCase().startsWith('http')) {
    return;
  }

  // Derive simple file title
  let title = 'Session_Capture';
  if (filename) {
    title = filename.split(/[/\\]/).pop().split('?')[0];
  } else {
    try {
      const parsed = new URL(downloadUrl);
      title = parsed.pathname.split('/').pop().split('?')[0] || 'file';
    } catch (e) {}
  }
  
  // Clean up title
  title = title.replace(/[^a-zA-Z0-9._-]/g, '_');

  // Fetch cookies for the target download domain and the referer domain (where premium session is logged in)
  let cookieStr = '';
  try {
    let cookies = await chrome.cookies.getAll({ url: downloadUrl });
    if (refererUrl && refererUrl.toLowerCase().startsWith('http')) {
      const refCookies = await chrome.cookies.getAll({ url: refererUrl });
      if (refCookies && refCookies.length > 0) {
        const cookieMap = new Map();
        cookies.forEach(c => cookieMap.set(c.name, c.value));
        refCookies.forEach(c => cookieMap.set(c.name, c.value));
        cookies = Array.from(cookieMap.entries()).map(([name, value]) => ({ name, value }));
      }
    }
    if (cookies && cookies.length > 0) {
      cookieStr = cookies.map(c => `${c.name}=${c.value}`).join('; ');
    }
  } catch (error) {
    console.error('Failed to get cookies for download session:', error);
  }

  // Create captured session object
  const capturedSession = {
    url: downloadUrl,
    referer: refererUrl,
    cookies: cookieStr,
    title: title,
    timestamp: Date.now()
  };

  // Store in extension local storage
  await chrome.storage.local.set({ capturedSession: capturedSession });
  console.log('✅ Captured session stored successfully:', capturedSession);
});
