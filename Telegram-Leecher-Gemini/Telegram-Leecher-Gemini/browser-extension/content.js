// content.js - Floating button on Mindvalley pages

// Create floating button
function createFloatingButton() {
  // Check if button already exists
  if (document.getElementById('mv-downloader-btn')) return;
  
  const button = document.createElement('div');
  button.id = 'mv-downloader-btn';
  button.innerHTML = '🎬';
  button.title = 'Mindvalley Downloader Pro - Click to view detected streams';
  
  // Styles
  button.style.cssText = `
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 60px;
    height: 60px;
    background: linear-gradient(135deg, #00ff00 0%, #00cc00 100%);
    color: #000;
    border: 3px solid #0f0;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 30px;
    cursor: pointer;
    z-index: 999999;
    box-shadow: 0 4px 15px rgba(0, 255, 0, 0.5);
    transition: all 0.3s ease;
    font-family: sans-serif;
  `;
  
  // Hover effects
  button.addEventListener('mouseenter', () => {
    button.style.transform = 'scale(1.1)';
    button.style.boxShadow = '0 6px 20px rgba(0, 255, 0, 0.7)';
  });
  
  button.addEventListener('mouseleave', () => {
    button.style.transform = 'scale(1)';
    button.style.boxShadow = '0 4px 15px rgba(0, 255, 0, 0.5)';
  });
  
  // Click handler - open extension popup
  button.addEventListener('click', () => {
    // Send message to background to show badge
    chrome.runtime.sendMessage({ action: 'getStreams' }, (response) => {
      if (response && response.videoQualities && response.videoQualities.length > 0) {
        // Streams detected - show success notification
        showNotification('✅ Streams detected! Click the extension icon to view.', 'success');
      } else {
        // No streams yet - show waiting notification
        showNotification('⏳ Play the video to detect streams...', 'info');
      }
    });
  });
  
  document.body.appendChild(button);
  console.log('✅ Mindvalley Downloader button added to page');
}

// Show notification
function showNotification(message, type = 'info') {
  const notification = document.createElement('div');
  notification.style.cssText = `
    position: fixed;
    bottom: 90px;
    right: 20px;
    background: ${type === 'success' ? 'rgba(0, 255, 0, 0.95)' : 'rgba(255, 255, 0, 0.95)'};
    color: #000;
    padding: 12px 20px;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    z-index: 999999;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    font-family: sans-serif;
    max-width: 300px;
    animation: slideIn 0.3s ease;
  `;
  
  notification.textContent = message;
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.style.animation = 'slideOut 0.3s ease';
    setTimeout(() => notification.remove(), 300);
  }, 3000);
}

// Add animations
const style = document.createElement('style');
style.textContent = `
  @keyframes slideIn {
    from {
      transform: translateX(400px);
      opacity: 0;
    }
    to {
      transform: translateX(0);
      opacity: 1;
    }
  }
  
  @keyframes slideOut {
    from {
      transform: translateX(0);
      opacity: 1;
    }
    to {
      transform: translateX(400px);
      opacity: 0;
    }
  }
`;
document.head.appendChild(style);

// Initialize
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', createFloatingButton);
} else {
  createFloatingButton();
}

console.log('✅ Mindvalley Downloader content script loaded');