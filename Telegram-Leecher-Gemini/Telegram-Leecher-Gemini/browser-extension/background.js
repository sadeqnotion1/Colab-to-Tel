// background.js - FIXED VERSION - Network interceptor with proper filtering

const detectedStreams = {
  masterUrl: null,
  videoQualities: [],
  audioUrl: null,
  subtitles: [],
  currentTab: null,
  pageTitle: null  // NEW: Store page title for auto-naming
};

// Track processed URLs to avoid duplicates
const processedUrls = new Set();

// Clean page title for use as filename
function cleanTitle(title) {
  if (!title) return null;

  // Remove Mindvalley branding
  let clean = title.replace(/\s*\|\s*Mindvalley.*$/i, '');

  // Remove "- Mindvalley" or similar
  clean = clean.replace(/\s*-\s*Mindvalley.*$/i, '');

  // Remove special characters that are invalid in filenames
  clean = clean.replace(/[<>:"/\\|?*]/g, '_');

  // Replace multiple spaces/underscores with single underscore
  clean = clean.replace(/\s+/g, ' ').replace(/_+/g, '_');

  // Trim whitespace and underscores
  clean = clean.trim().replace(/^[_\s]+|[_\s]+$/g, '');

  // Return null if empty after cleaning
  return clean.length > 0 ? clean : null;
}

// Listen for M3U8 requests at network level
chrome.webRequest.onBeforeRequest.addListener(
  function(details) {
    const url = details.url;
    
    // Skip if already processed
    if (processedUrls.has(url)) {
      return;
    }
    
    console.log('🔍 Network request:', url);
    
    // CRITICAL: Only process actual M3U8 playlists and VTT/SRT subtitle files
    // IGNORE .ts video segments completely!
    const isM3U8 = url.includes('.m3u8');
    const isVTT = url.endsWith('.vtt') && !url.includes('.ts');
    const isSRT = url.endsWith('.srt') && !url.includes('.ts');
    
    if (!isM3U8 && !isVTT && !isSRT) {
      return; // Ignore everything else (including .ts segments!)
    }
    
    // Store the tab ID
    detectedStreams.currentTab = details.tabId;

    // Extract page title on first detection (if not already set)
    if (!detectedStreams.pageTitle && details.tabId) {
      chrome.tabs.get(details.tabId, (tab) => {
        if (tab && tab.title) {
          const cleaned = cleanTitle(tab.title);
          if (cleaned) {
            detectedStreams.pageTitle = cleaned;
            chrome.storage.local.set({ detectedStreams });
            console.log('📝 Page title extracted:', cleaned);
          }
        }
      });
    }

    // Handle M3U8 files
    if (isM3U8) {
      processedUrls.add(url);
      console.log('📹 M3U8 detected:', url);
      
      // Check if this is a master playlist
      if (url.includes('master') || url.includes('playlist') || !url.match(/h264_\d+p_\d+/)) {
        console.log('🎯 Potential master playlist:', url);
        detectedStreams.masterUrl = url;
        
        // Fetch and parse the master playlist
        fetch(url, { credentials: 'include' })
          .then(r => r.text())
          .then(text => {
            if (text.includes('#EXT-X-STREAM-INF')) {
              parseMasterPlaylist(url, text);
            }
          })
          .catch(err => console.log('Could not fetch master:', err));
      }
      
      // Check if this is a quality variant URL
      const qualityMatch = url.match(/h264_(\d+)p_(\d+)/);
      if (qualityMatch) {
        const height = parseInt(qualityMatch[1]);
        const bitrate = qualityMatch[2];
        
        // Check if we already have this resolution
        const existingQuality = detectedStreams.videoQualities.find(q => 
          q.height === height
        );
        
        // Only add if:
        // 1. We don't have this resolution yet, OR
        // 2. This bitrate is higher than existing one
        if (!existingQuality || parseInt(bitrate) > parseInt(existingQuality.bitrate)) {
          // Remove old quality with lower bitrate
          if (existingQuality) {
            const index = detectedStreams.videoQualities.indexOf(existingQuality);
            detectedStreams.videoQualities.splice(index, 1);
          }
          
          detectedStreams.videoQualities.push({
            label: `${height}p`,
            height: height,
            bitrate: bitrate,
            bandwidth: parseInt(bitrate) * 1000,
            url: url,
            detected: true
          });
          
          console.log(`✅ Added/Updated quality: ${height}p @ ${bitrate}kbps`);
          
          // Sort by height (highest first)
          detectedStreams.videoQualities.sort((a, b) => b.height - a.height);
          
          // Save to storage
          chrome.storage.local.set({ detectedStreams });
        }
      }
      
      // Check for audio tracks
      if (url.includes('audio') || url.includes('-audio-')) {
        detectedStreams.audioUrl = url;
        console.log('🔊 Audio track detected:', url);
        chrome.storage.local.set({ detectedStreams });
      }
    }
    
    // Handle REAL subtitle files only (VTT or SRT)
    if (isVTT || isSRT) {
      processedUrls.add(url);
      
      const filename = url.split('/').pop().split('?')[0];
      
      // Additional check: must have subtitle-related keywords OR be from subtitle path
      const isRealSubtitle = 
        url.includes('/subtitle') || 
        url.includes('/caption') || 
        url.includes('/sub/') ||
        filename.toLowerCase().includes('sub') ||
        filename.toLowerCase().includes('caption') ||
        filename.toLowerCase().includes('_en') || // Language codes
        filename.toLowerCase().includes('_es') ||
        filename.includes('TEM_EN') || // Mindvalley subtitle pattern
        filename.includes('TEM_ES');
      
      if (isRealSubtitle && !detectedStreams.subtitles.find(s => s.url === url)) {
        // Extract language from filename if possible
        const langMatch = filename.match(/[_-](en|es|fr|de|pt|it|ja|zh|ko|ar|hi)[_-]/i);
        const lang = langMatch ? langMatch[1].toUpperCase() : '';
        
        detectedStreams.subtitles.push({
          name: filename,
          lang: lang,
          url: url
        });
        
        console.log('📝 Subtitle detected:', filename, lang);
        chrome.storage.local.set({ detectedStreams });
      }
    }
  },
  { urls: ["https://*.mindvalley.com/*", "https://otfp.mindvalley.com/*"] }
);

// Parse master M3U8 playlist
function parseMasterPlaylist(masterUrl, text) {
  console.log('🎯 Parsing master playlist...');
  
  const lines = text.split(/\r?\n/);
  const qualities = new Map(); // Use Map to track best bitrate per resolution
  let audioUrl = null;
  const subtitles = [];
  let pendingStreamInf = null;
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    
    if (line.startsWith('#EXT-X-STREAM-INF')) {
      pendingStreamInf = parseAttributes(line);
      continue;
    }
    
    if (pendingStreamInf && line && !line.startsWith('#')) {
      const url = line.startsWith('http') ? line : new URL(line, masterUrl).toString();
      const res = pendingStreamInf.RESOLUTION || '';
      let height = 0;
      
      if (res.includes('x')) {
        height = parseInt(res.split('x')[1]);
      }
      
      const bandwidth = pendingStreamInf.BANDWIDTH ? parseInt(pendingStreamInf.BANDWIDTH) : 0;
      const bitrate = Math.round(bandwidth / 1000);
      
      // Only keep the highest bitrate for each resolution
      if (!qualities.has(height) || bitrate > qualities.get(height).bitrate) {
        qualities.set(height, {
          label: height ? `${height}p` : `${bitrate}kbps`,
          height: height,
          bitrate: bitrate.toString(),
          bandwidth: bandwidth,
          resolution: res,
          codecs: pendingStreamInf.CODECS || '',
          url: url
        });
      }
      
      pendingStreamInf = null;
      continue;
    }
    
    if (line.startsWith('#EXT-X-MEDIA')) {
      const attrs = parseAttributes(line);
      const type = (attrs.TYPE || '').toUpperCase();
      
      if (type === 'AUDIO' && attrs.URI) {
        audioUrl = attrs.URI.startsWith('http') ? attrs.URI : new URL(attrs.URI, masterUrl).toString();
      }
      
      if (type === 'SUBTITLES' && attrs.URI) {
        const subUrl = attrs.URI.startsWith('http') ? attrs.URI : new URL(attrs.URI, masterUrl).toString();
        
        // Only add if it's a real subtitle URL
        if (subUrl.includes('.vtt') || subUrl.includes('.srt') || subUrl.includes('.m3u8')) {
          subtitles.push({
            name: attrs.NAME || attrs.LANGUAGE || 'subtitle',
            lang: attrs.LANGUAGE || '',
            url: subUrl
          });
        }
      }
    }
  }
  
  // Convert Map to Array and sort
  const qualitiesArray = Array.from(qualities.values());
  qualitiesArray.sort((a, b) => b.height - a.height);
  
  detectedStreams.videoQualities = qualitiesArray;
  detectedStreams.audioUrl = audioUrl;
  detectedStreams.subtitles = [...detectedStreams.subtitles, ...subtitles];
  
  console.log(`✅ Parsed master: ${qualitiesArray.length} qualities (best bitrate each), audio: ${audioUrl ? 'yes' : 'no'}, subtitles: ${subtitles.length}`);
  
  chrome.storage.local.set({ detectedStreams });
}

// Parse M3U8 attribute list
function parseAttributes(line) {
  const attrs = {};
  const re = /([A-Z0-9-]+)=("(?:[^"\\]|\\.)*"|[^,]*)/gi;
  let m;
  
  while ((m = re.exec(line))) {
    const key = m[1];
    let val = m[2];
    if (val && val.startsWith('"') && val.endsWith('"')) {
      val = val.slice(1, -1);
    }
    attrs[key] = val;
  }
  
  return attrs;
}

// Listen for messages from popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'getStreams') {
    sendResponse(detectedStreams);
  } else if (request.action === 'clearStreams') {
    detectedStreams.masterUrl = null;
    detectedStreams.videoQualities = [];
    detectedStreams.audioUrl = null;
    detectedStreams.subtitles = [];
    detectedStreams.pageTitle = null;  // NEW: Clear page title too
    processedUrls.clear();
    chrome.storage.local.set({ detectedStreams });
    sendResponse({ success: true });
  }
  return true;
});

// Clear detected streams when navigating to a new page
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === 'loading' && tab.url?.includes('mindvalley.com')) {
    if (detectedStreams.currentTab === tabId) {
      detectedStreams.masterUrl = null;
      detectedStreams.videoQualities = [];
      detectedStreams.audioUrl = null;
      detectedStreams.subtitles = [];
      detectedStreams.pageTitle = null;  // NEW: Clear page title for new page
      processedUrls.clear();
      chrome.storage.local.set({ detectedStreams });
      console.log('🔄 Cleared detections for new page');
    }
  }
});

console.log('✅ Mindvalley Downloader Extension loaded (FIXED VERSION)!');