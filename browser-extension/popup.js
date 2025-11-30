// popup.js - FIXED VERSION - Display only best qualities

let detectedStreams = null;

// Load detected streams from storage
async function loadStreams() {
  try {
    const response = await chrome.runtime.sendMessage({ action: 'getStreams' });
    
    if (response && response.videoQualities && response.videoQualities.length > 0) {
      detectedStreams = response;
      renderUI();
      return;
    }
    
    const result = await chrome.storage.local.get('detectedStreams');
    
    if (result.detectedStreams && result.detectedStreams.videoQualities.length > 0) {
      detectedStreams = result.detectedStreams;
      renderUI();
    } else {
      showEmptyState();
    }
  } catch (error) {
    console.error('Error loading streams:', error);
    showEmptyState();
  }
}

// Render the UI
function renderUI() {
  const content = document.getElementById('content');
  
  if (!detectedStreams || detectedStreams.videoQualities.length === 0) {
    showEmptyState();
    return;
  }
  
  const hasAudio = detectedStreams.audioUrl !== null;
  const qualityCount = detectedStreams.videoQualities.length;
  const subtitleCount = detectedStreams.subtitles.length;
  
  let html = `
    <div class="status-box ready">
      <div class="status-title">
        ✅ Streams Detected!
      </div>
      <div class="status-details">
        📊 Video Qualities: ${qualityCount} (best bitrate per resolution)<br>
        🔊 Audio Track: ${hasAudio ? 'Detected' : 'Not detected (embedded in video)'}<br>
        📝 Subtitles: ${subtitleCount}
      </div>
    </div>
  `;
  
  if (!hasAudio) {
    html += `
      <div class="status-box waiting">
        <div class="status-title">⚠️ No Separate Audio Track</div>
        <div class="status-details">
          Audio appears to be embedded in video streams. Download video only.
        </div>
      </div>
    `;
  }
  
  // Add Telegram URLs Box (for best quality)
  const bestVideoUrl = detectedStreams.videoQualities[0].url;
  const audioUrl = detectedStreams.audioUrl || '';
  const subtitleUrl = detectedStreams.subtitles.length > 0 ? detectedStreams.subtitles[0].url : '';

  // Build multi-line URLs format
  let telegramUrls = '';

  // NEW: Prepend TITLE= if page title was extracted
  if (detectedStreams.pageTitle) {
    telegramUrls = `TITLE=${detectedStreams.pageTitle}\n`;
  }

  // Add video URL (required)
  telegramUrls += bestVideoUrl;

  // Add audio URL if present
  if (audioUrl) telegramUrls += `\n${audioUrl}`;

  // Add subtitle URL if present
  if (subtitleUrl) telegramUrls += `\n${subtitleUrl}`;

  html += `
    <div class="status-box" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border: none; color: white;">
      <div class="status-title" style="color: white; font-size: 16px;">
        🤖 For Telegram Bot (Best Quality)
      </div>
      <div class="status-details" style="color: rgba(255,255,255,0.9); margin-top: 8px;">
        1️⃣ Send <code>/mindvalley</code> to your bot<br>
        2️⃣ Copy URLs below and paste them<br>
        3️⃣ Bot downloads ${detectedStreams.pageTitle ? 'with lesson name!' : 'automatically!'}<br>
        ${detectedStreams.pageTitle ? `📝 Title: <i>${detectedStreams.pageTitle}</i>` : ''}
      </div>
      <div class="command-box" style="margin-top: 12px; background: rgba(0,0,0,0.2); border: 1px solid rgba(255,255,255,0.3);">
        <div class="command-text" id="telegram-urls" style="color: #fff; font-size: 10px; word-break: break-all; white-space: pre-wrap; max-height: 120px; overflow-y: auto;">${telegramUrls}</div>
      </div>
      <button class="btn" id="copy-telegram-urls" style="margin-top: 12px; background: white; color: #667eea; font-weight: bold; width: 100%;">
        📋 Copy URLs for Telegram
      </button>
    </div>
  `;

  html += `<div class="section-title">📥 Manual Download Commands</div>`;

  // The qualities are already deduplicated in background.js
  // Just display them
  detectedStreams.videoQualities.forEach((quality, index) => {
    const isBest = index === 0;
    const videoCmd = `N_m3u8DL-RE.exe "${quality.url}" --save-name "video_${quality.label}" --log-level DEBUG`;
    const audioCmd = hasAudio ? `N_m3u8DL-RE.exe "${detectedStreams.audioUrl}" --save-name "audio" --log-level DEBUG` : '';
    const mergeCmd = hasAudio 
      ? `ffmpeg -i video_${quality.label}.mp4 -i audio.m4a -c:v copy -c:a copy final_${quality.label}.mp4`
      : `REM Audio is embedded - no merge needed`;
    
    html += `
      <div class="quality-card ${isBest ? 'best' : ''}">
        <div class="quality-header">
          <div class="quality-badge ${isBest ? '' : 'normal'}">
            ${isBest ? '🏆' : '📹'} ${quality.label}
          </div>
          <div class="quality-meta">
            ${quality.resolution || 'N/A'} • ${quality.bitrate}kbps
            ${isBest ? '• BEST QUALITY' : ''}
          </div>
        </div>
        
        <div class="command-box">
          <div class="command-label">📹 STEP 1: Download Video (${quality.label})</div>
          <div class="command-text" id="video-cmd-${index}">${videoCmd}</div>
        </div>
        <button class="btn copy-video-cmd" data-index="${index}">📋 Copy Video Command</button>

        ${hasAudio ? `
        <div class="command-box">
          <div class="command-label">🔊 STEP 2: Download Audio</div>
          <div class="command-text" id="audio-cmd-${index}">${audioCmd}</div>
        </div>
        <button class="btn copy-audio-cmd" data-index="${index}">📋 Copy Audio Command</button>

        <div class="command-box">
          <div class="command-label">🔧 STEP 3: Merge Video + Audio</div>
          <div class="command-text" id="merge-cmd-${index}">${mergeCmd}</div>
        </div>
        <button class="btn copy-merge-cmd" data-index="${index}">📋 Copy Merge Command</button>
        ` : `
        <div style="margin-top: 8px; padding: 8px; background: rgba(100, 100, 100, 0.2); border-radius: 4px; font-size: 11px; color: #888;">
          ℹ️ Video contains embedded audio - no merge needed
        </div>
        `}
      </div>
    `;
  });
  
  // Subtitles section
  if (detectedStreams.subtitles.length > 0) {
    html += `<div class="section-title">📝 Subtitles (${subtitleCount})</div>`;
    
    // Add download script info once at the top
    html += `
      <div style="margin-bottom: 15px; padding: 10px; background: rgba(0, 100, 200, 0.2); border: 2px solid #0088ff; border-radius: 6px; font-size: 11px;">
        <strong style="color: #00aaff;">💡 How to Download Subtitles:</strong><br>
        <div style="margin-top: 6px; color: #aaa;">
          1. Copy the URL below<br>
          2. Use the Python script or FFmpeg command<br>
          3. Get a clean .vtt file!<br>
          <a href="#" id="show-script-help" style="color: #00ff00; text-decoration: underline; cursor: pointer;">📖 Show Download Instructions</a>
        </div>
      </div>
    `;
    
    detectedStreams.subtitles.forEach((sub, index) => {
      // Clean filename
      const cleanName = sub.name.replace(/[^a-zA-Z0-9._-]/g, '_');
      const baseFilename = cleanName.replace('.vtt', '').replace('.srt', '').replace('.m3u8', '').replace('.webvtt', '');
      
      // Python script command
      const pythonCmd = `python subtitle_downloader.py "${sub.url}" "${baseFilename}.vtt"`;
      
      // FFmpeg command (alternative)
      const ffmpegCmd = `ffmpeg -i "${sub.url}" -c copy "${baseFilename}.vtt"`;
      
      html += `
        <div class="subtitle-item">
          <div class="subtitle-name">${sub.name} ${sub.lang ? `(${sub.lang})` : ''}</div>
          
          <div class="command-box" style="margin: 8px 0;">
            <div class="command-label">📝 Subtitle URL</div>
            <div class="command-text" id="sub-url-${index}">${sub.url}</div>
          </div>
          <button class="btn copy-sub-url" data-index="${index}">📋 Copy URL</button>
          
          <details style="margin-top: 10px;">
            <summary style="cursor: pointer; color: #888; font-size: 11px; user-select: none;">📥 Show Download Commands</summary>
            
            <div class="command-box" style="margin: 8px 0;">
              <div class="command-label">🐍 Python Script (Recommended)</div>
              <div class="command-text" id="sub-python-${index}">${pythonCmd}</div>
            </div>
            <button class="btn copy-sub-python" data-index="${index}">📋 Copy Python Command</button>
            
            <div class="command-box" style="margin: 8px 0;">
              <div class="command-label">🎬 FFmpeg (Alternative)</div>
              <div class="command-text" id="sub-ffmpeg-${index}">${ffmpegCmd}</div>
            </div>
            <button class="btn copy-sub-ffmpeg" data-index="${index}">📋 Copy FFmpeg Command</button>
          </details>
        </div>
      `;
    });
  }
  
  // Actions
  html += `
    <div class="actions">
      <button class="btn" onclick="clearDetections()" style="background: #666;">🔄 Clear & Rescan</button>
    </div>
  `;
  
  content.innerHTML = html;

  // Add event listener for Telegram URLs copy button
  const telegramUrlsBtn = document.getElementById('copy-telegram-urls');
  if (telegramUrlsBtn) {
    telegramUrlsBtn.addEventListener('click', function() {
      copyText('telegram-urls', this);
    });
  }

  // Add event listeners for video command copy buttons
  document.querySelectorAll('.copy-video-cmd').forEach(btn => {
    btn.addEventListener('click', function() {
      const index = this.getAttribute('data-index');
      const elementId = `video-cmd-${index}`;
      copyText(elementId, this);
    });
  });

  // Add event listeners for audio command copy buttons
  document.querySelectorAll('.copy-audio-cmd').forEach(btn => {
    btn.addEventListener('click', function() {
      const index = this.getAttribute('data-index');
      const elementId = `audio-cmd-${index}`;
      copyText(elementId, this);
    });
  });

  // Add event listeners for merge command copy buttons
  document.querySelectorAll('.copy-merge-cmd').forEach(btn => {
    btn.addEventListener('click', function() {
      const index = this.getAttribute('data-index');
      const elementId = `merge-cmd-${index}`;
      copyText(elementId, this);
    });
  });

  // Add event listeners for subtitle URL copy buttons
  document.querySelectorAll('.copy-sub-url').forEach(btn => {
    btn.addEventListener('click', function() {
      const index = this.getAttribute('data-index');
      const elementId = `sub-url-${index}`;
      copyText(elementId, this);
    });
  });

  // Add event listeners for Python command copy buttons
  document.querySelectorAll('.copy-sub-python').forEach(btn => {
    btn.addEventListener('click', function() {
      const index = this.getAttribute('data-index');
      const elementId = `sub-python-${index}`;
      copyText(elementId, this);
    });
  });

  // Add event listeners for FFmpeg command copy buttons
  document.querySelectorAll('.copy-sub-ffmpeg').forEach(btn => {
    btn.addEventListener('click', function() {
      const index = this.getAttribute('data-index');
      const elementId = `sub-ffmpeg-${index}`;
      copyText(elementId, this);
    });
  });

  // Add event listener for "Show Download Instructions" link
  const scriptHelpLink = document.getElementById('show-script-help');
  if (scriptHelpLink) {
    scriptHelpLink.addEventListener('click', (e) => {
      e.preventDefault();
      showScriptInstructions();
    });
  }
}

// Show script download instructions in a modal/alert
function showScriptInstructions() {
  const instructions = `
🎬 SUBTITLE DOWNLOAD GUIDE

📥 METHOD 1: Python Script (RECOMMENDED)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Most reliable - handles all subtitle formats
✅ Automatically merges segments
✅ Clean output with no duplicates

SETUP (one-time):
1. Install Python: https://python.org
2. Install requests library:
   pip install requests

3. The subtitle_downloader.py script should be in
   the same folder as this extension

USAGE:
python subtitle_downloader.py "SUBTITLE_URL" "output.vtt"

Example:
python subtitle_downloader.py "https://..." "english.vtt"


📥 METHOD 2: FFmpeg
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ No Python needed
✅ Handles HLS subtitles natively

SETUP (one-time):
1. Download FFmpeg: https://ffmpeg.org
2. Add to PATH or use full path

USAGE:
ffmpeg -i "SUBTITLE_URL" -c copy "output.vtt"


📋 QUICK START:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Click "Copy URL" for the subtitle you want
2. Use either Python script or FFmpeg command
3. Replace "SUBTITLE_URL" with the copied URL
4. Run the command in terminal/cmd
5. Get your clean .vtt file! 🎉
  `.trim();

  alert(instructions);
}

// Show empty state
function showEmptyState() {
  const content = document.getElementById('content');
  content.innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">🔍</div>
      <div class="empty-title">No Streams Detected</div>
      <div class="empty-desc">
        Go to a Mindvalley video page and play the video.<br>
        The extension will automatically detect all available qualities.<br><br>
        <strong>Then click this extension icon again!</strong>
      </div>
      <div style="margin-top: 20px;">
        <button class="btn" onclick="refreshDetection()">🔄 Check Again</button>
      </div>
    </div>
  `;
}

// Copy text to clipboard (for command boxes)
function copyText(elementId, button) {
  const element = document.getElementById(elementId);
  const text = element.textContent;

  // Try modern clipboard API first
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(() => {
      showCopySuccess(button);
    }).catch(err => {
      console.error('Clipboard API failed:', err);
      // Fallback to execCommand
      fallbackCopy(text, button);
    });
  } else {
    // Use fallback for older browsers or permission issues
    fallbackCopy(text, button);
  }
}

function fallbackCopy(text, button) {
  try {
    // Create temporary textarea
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.top = '0';
    textarea.style.left = '0';
    textarea.style.width = '2em';
    textarea.style.height = '2em';
    textarea.style.padding = '0';
    textarea.style.border = 'none';
    textarea.style.outline = 'none';
    textarea.style.boxShadow = 'none';
    textarea.style.background = 'transparent';

    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();

    const successful = document.execCommand('copy');
    document.body.removeChild(textarea);

    if (successful) {
      showCopySuccess(button);
    } else {
      alert('Failed to copy. Please copy manually.');
    }
  } catch (err) {
    console.error('Fallback copy failed:', err);
    alert('Failed to copy. Please select and copy the text manually.');
  }
}

function showCopySuccess(button) {
  const originalText = button.textContent;
  button.textContent = '✅ Copied!';
  button.classList.add('copied');

  setTimeout(() => {
    button.textContent = originalText;
    button.classList.remove('copied');
  }, 2000);
}

window.copyText = copyText;

// Open URL in new tab
window.openUrl = function(url) {
  chrome.tabs.create({ url: url });
};

// Clear detections
window.clearDetections = async function() {
  await chrome.runtime.sendMessage({ action: 'clearStreams' });
  showEmptyState();
};

// Refresh detection
window.refreshDetection = function() {
  loadStreams();
};

// Initialize
loadStreams();

// Listen for storage changes (live updates)
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === 'local' && changes.detectedStreams) {
    loadStreams();
  }
});