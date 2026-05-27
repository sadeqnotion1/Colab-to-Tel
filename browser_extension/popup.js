// popup.js - Session capturing and GitHub Gist creation logic

let currentTab = null;
let capturedCookies = {};
let hasToken = false;

// 1. Initialize Extension Popup on Load
document.addEventListener('DOMContentLoaded', async () => {
  console.log('Initializing Leecher Session Capture...');

  // Set local User-Agent preview
  document.getElementById('ua-preview').textContent = navigator.userAgent;

  // Retrieve active tab details
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    if (tabs && tabs.length > 0) {
      currentTab = tabs[0];
      console.log('Active Tab:', currentTab.url);

      // Default the target URL to current tab URL
      document.getElementById('download-url').value = currentTab.url;
      // Default the referer URL to the current tab URL
      document.getElementById('referer-url').value = currentTab.url;

      // Extract cookies for this active tab immediately
      await fetchCookiesForUrl(currentTab.url);
    }
  } catch (error) {
    console.error('Error fetching current tab details:', error);
    document.getElementById('cookies-preview').textContent = '⚠️ Error capturing active tab details: ' + error.message;
  }

  // Check Gist Token status
  await checkTokenStatus();

  // Attach event listeners
  document.getElementById('btn-capture').addEventListener('click', captureAndCreateGist);
  document.getElementById('btn-copy').addEventListener('click', copyGistUrl);

  // Automatically update cookies when user edits/pastes a new download URL
  document.getElementById('download-url').addEventListener('input', async (e) => {
    const enteredUrl = e.target.value.trim();
    if (enteredUrl && enteredUrl.toLowerCase().startsWith('http')) {
      await fetchCookiesForUrl(enteredUrl);
    }
  });
});

// 2. Fetch and Format Cookies for a Given Domain URL
async function fetchCookiesForUrl(targetUrl) {
  const previewBox = document.getElementById('cookies-preview');
  previewBox.textContent = '🔄 Querying cookies...';

  try {
    const cookies = await chrome.cookies.getAll({ url: targetUrl });
    console.log(`Fetched ${cookies.length} cookies for:`, targetUrl);

    if (cookies && cookies.length > 0) {
      capturedCookies = {};
      const cookieLines = [];

      cookies.forEach(c => {
        capturedCookies[c.name] = c.value;
        cookieLines.push(`${c.name}=${c.value}`);
      });

      // Display formatted preview
      previewBox.textContent = cookieLines.join(';\n');
    } else {
      // Fallback: If no cookies are found for the specific download URL,
      // and we are looking at a different URL than the main tab, try pulling tab cookies.
      if (currentTab && targetUrl !== currentTab.url) {
        console.log('No direct cookies found for download URL. Falling back to active tab cookies.');
        const fallbackCookies = await chrome.cookies.getAll({ url: currentTab.url });
        if (fallbackCookies && fallbackCookies.length > 0) {
          capturedCookies = {};
          const cookieLines = [];
          fallbackCookies.forEach(c => {
            capturedCookies[c.name] = c.value;
            cookieLines.push(`${c.name}=${c.value}`);
          });
          previewBox.textContent = '⚠️ (Active Tab Fallback) ' + cookieLines.join(';\n');
          return;
        }
      }
      capturedCookies = {};
      previewBox.textContent = '📭 No cookies detected for this domain. Either cookies are empty or domain is not logged-in.';
    }
  } catch (error) {
    console.error('Error fetching cookies:', error);
    previewBox.textContent = '⚠️ Permission or API Error: ' + error.message;
  }
}

// 3. Verify and Display GitHub Gist Token Status
async function checkTokenStatus() {
  const dot = document.getElementById('token-dot');
  const label = document.getElementById('token-status');

  // Trigger background to reload token in case they just added it
  try {
    await chrome.runtime.sendMessage({ action: 'reloadToken' });
  } catch (err) {
    console.warn('Failed background token sync:', err);
  }

  const result = await chrome.storage.local.get('githubToken');
  const token = result.githubToken;

  if (token && token.length > 15) {
    hasToken = true;
    dot.className = 'badge-dot active';
    label.textContent = 'Token Loaded';
    label.style.color = 'var(--success)';
  } else {
    hasToken = false;
    dot.className = 'badge-dot inactive';
    label.textContent = 'No Token';
    label.style.color = 'var(--warning)';
  }
}

// 4. Capture Session details and push Gist to GitHub
async function captureAndCreateGist() {
  const btn = document.getElementById('btn-capture');
  const originalHTML = btn.innerHTML;
  const resultPanel = document.getElementById('result-panel');

  // Hide any existing result panel
  resultPanel.style.display = 'none';

  try {
    const downloadUrl = document.getElementById('download-url').value.trim();
    const refererUrl = document.getElementById('referer-url').value.trim();

    if (!downloadUrl) {
      throw new Error('Please enter a target download URL.');
    }

    if (!hasToken) {
      throw new Error(
        'GitHub Gist token is missing!\n\n' +
        'To configure it:\n' +
        '1. Generate a token at: https://github.com/settings/tokens\n' +
        '   (Ensure the ONLY permission checked is "gist")\n' +
        '2. Open the browser_extension/gist_token.txt file inside this extension folder\n' +
        '3. Replace the placeholder text with your GitHub token\n' +
        '4. Save the file and reload this extension!'
      );
    }

    // Set loading state on button
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> <span>Creating Gist...</span>';

    // Format filename / Title
    let title = 'Session_Capture';
    try {
      if (currentTab && currentTab.title) {
        title = currentTab.title.replace(/[^a-zA-Z0-9]/g, '_');
      } else {
        const parsed = new URL(downloadUrl);
        title = parsed.pathname.split('/').pop() || 'file';
        title = title.split('?')[0].replace(/[^a-zA-Z0-9._-]/g, '_');
      }
    } catch (e) {
      console.warn('Could not derive filename:', e);
    }
    const gistFileName = `${title}_capture.txt`;

    // Compile into standard template lines
    const gistLines = [];
    gistLines.push(`TITLE=${title}`);
    gistLines.push(`DOWNLOAD_TYPE=session-capture`);
    gistLines.push(`URL=${downloadUrl}`);

    // Build standard Cookie string
    const cookiePairs = Object.entries(capturedCookies).map(([k, v]) => `${k}=${v}`);
    if (cookiePairs.length > 0) {
      gistLines.push(`COOKIE=${cookiePairs.join('; ')}`);
    }

    gistLines.push(`USER_AGENT=${navigator.userAgent}`);

    if (refererUrl) {
      gistLines.push(`REFERER=${refererUrl}`);
    }

    const gistContent = gistLines.join('\n');
    console.log('Creating Gist content:\n', gistContent);

    // Call GitHub API to create Gist
    const storageResult = await chrome.storage.local.get('githubToken');
    const token = storageResult.githubToken;

    const gistResponse = await fetch('https://api.github.com/gists', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        'Accept': 'application/vnd.github.v3+json'
      },
      body: JSON.stringify({
        description: `Telegram Leecher Captured Session for ${title}`,
        public: false,
        files: {
          [gistFileName]: {
            content: gistContent
          }
        }
      })
    });

    if (!gistResponse.ok) {
      const errBody = await gistResponse.text();
      console.error('GitHub Gist API Error:', errBody);
      if (gistResponse.status === 401 || gistResponse.status === 403) {
        throw new Error('Unauthorized: GitHub token is invalid or does not have "gist" permission.');
      }
      throw new Error(`GitHub API Error (${gistResponse.status}): ${errBody}`);
    }

    const gistData = await gistResponse.json();
    const rawUrl = gistData.files[gistFileName].raw_url;
    console.log('Gist created successfully! Raw URL:', rawUrl);

    // Copy to clipboard using modern Navigator API
    await navigator.clipboard.writeText(rawUrl);

    // Show success panel
    document.getElementById('gist-url-display').value = rawUrl;
    resultPanel.style.display = 'block';

    // Reset button
    btn.disabled = false;
    btn.innerHTML = originalHTML;

  } catch (error) {
    console.error('Capture action failed:', error);
    alert('❌ Capture failed:\n\n' + error.message);
    btn.disabled = false;
    btn.innerHTML = originalHTML;
  }
}

// 5. Handle success clipboard copy click
async function copyGistUrl() {
  const input = document.getElementById('gist-url-display');
  const btn = document.getElementById('btn-copy');

  try {
    await navigator.clipboard.writeText(input.value);
    const originalText = btn.textContent;
    btn.textContent = 'Copied!';
    btn.style.background = 'var(--success)';
    setTimeout(() => {
      btn.textContent = originalText;
      btn.style.background = '';
    }, 2000);
  } catch (error) {
    console.error('Copy clicked error:', error);
    input.select();
    document.execCommand('copy');
  }
}
