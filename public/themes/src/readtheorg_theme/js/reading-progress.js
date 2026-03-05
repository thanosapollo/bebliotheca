/**
 * Reading Progress Tracker for Bebliotheca
 * Tracks and restores reading position across sessions using localStorage
 */

(function() {
    'use strict';

    // Configuration
    const CONFIG = {
        storageKey: 'bebliotheca_reading_progress',
        scrollDebounceMs: 500,
        headingSelectors: 'h1[id], h2[id], h3[id], h4[id], h5[id], h6[id]',
        viewportThreshold: 200, // Pixels from top to consider "in view"
    };

    // State
    let scrollTimeout = null;
    let currentPageKey = null;
    let headings = [];
    let promptDismissed = false;

    /**
     * Initialize the reading progress tracker
     */
    function init() {
        // Only run on content pages (not index)
        if (window.location.pathname === '/' || window.location.pathname === '/index.html') {
            return;
        }

        currentPageKey = window.location.pathname;

        // Wait for DOM to be ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', setup);
        } else {
            setup();
        }
    }

    /**
     * Setup after DOM is ready
     */
    function setup() {
        // Cache all headings with IDs (CUSTOM_ID properties)
        headings = Array.from(document.querySelectorAll(CONFIG.headingSelectors));

        if (headings.length === 0) {
            return;
        }

        // Restore previous progress
        restoreProgress();

        // Setup scroll tracking
        window.addEventListener('scroll', handleScroll);

        // Save progress before leaving page
        window.addEventListener('beforeunload', saveCurrentProgress);

    }

    /**
     * Handle scroll events (debounced)
     */
    function handleScroll() {
        clearTimeout(scrollTimeout);
        scrollTimeout = setTimeout(() => {
            saveCurrentProgress();
        }, CONFIG.scrollDebounceMs);
    }

    /**
     * Find the heading currently in viewport
     */
    function getCurrentHeading() {
        let current = null;
        let minDistance = Infinity;

        headings.forEach(heading => {
            const rect = heading.getBoundingClientRect();
            const distance = Math.abs(rect.top);

            // Heading is in viewport or just above
            if (rect.top <= CONFIG.viewportThreshold && distance < minDistance) {
                current = heading;
                minDistance = distance;
            }
        });

        return current;
    }

    /**
     * Calculate reading progress percentage
     */
    function calculateProgress() {
        const totalHeight = document.documentElement.scrollHeight - window.innerHeight;
        if (totalHeight <= 0) return 0;

        const currentScroll = window.scrollY;
        const percentage = (currentScroll / totalHeight) * 100;

        return Math.min(100, Math.max(0, Math.round(percentage)));
    }

    /**
     * Get heading hierarchy (breadcrumb path) for a heading element
     * Works with Org-mode's outline-container structure
     */
    function getHeadingHierarchy(heading) {
        if (!heading) return '';

        const hierarchy = [];
        let currentHeading = heading;

        // Build hierarchy by traversing up through outline containers
        while (currentHeading && currentHeading.id) {
            // Add current heading text to hierarchy
            hierarchy.unshift(currentHeading.textContent.trim());

            // Find the outline-container that wraps this heading
            let currentContainer = currentHeading.closest('[class*="outline-"]');

            if (!currentContainer) break;

            // Find parent outline-container
            let parentContainer = currentContainer.parentElement;
            if (!parentContainer) break;

            parentContainer = parentContainer.closest('[class*="outline-"]');
            if (!parentContainer) break;

            // Find the heading in the parent container (direct child heading)
            currentHeading = parentContainer.querySelector(':scope > h1[id], :scope > h2[id], :scope > h3[id], :scope > h4[id], :scope > h5[id], :scope > h6[id]');
        }

        return hierarchy.join(' : ');
    }

    /**
     * Save current reading progress
     */
    function saveCurrentProgress() {
        const currentHeading = getCurrentHeading();
        if (!currentHeading) return;

        const headingId = currentHeading.getAttribute('id');
        const scrollPosition = window.scrollY;
        const percentage = calculateProgress();
        const headingHierarchy = getHeadingHierarchy(currentHeading);

        const progressData = getAllProgress();

        progressData[currentPageKey] = {
            lastHeading: headingId,
            headingText: headingHierarchy.substring(0, 200), // Store hierarchy (up to 200 chars)
            scrollPosition: scrollPosition,
            percentage: percentage,
            timestamp: new Date().toISOString()
        };

        localStorage.setItem(CONFIG.storageKey, JSON.stringify(progressData));
    }

    /**
     * Get all saved progress data
     */
    function getAllProgress() {
        try {
            const data = localStorage.getItem(CONFIG.storageKey);
            return data ? JSON.parse(data) : {};
        } catch (e) {
            console.error('ReadingProgress: Error reading localStorage', e);
            return {};
        }
    }

    /**
     * Get progress for current page
     */
    function getCurrentPageProgress() {
        const allProgress = getAllProgress();
        return allProgress[currentPageKey];
    }

    /**
     * Restore reading progress for current page
     */
    function restoreProgress() {
        const progress = getCurrentPageProgress();

        if (!progress) {
            return;
        }

        // Check if progress is recent (within last 30 days)
        const savedDate = new Date(progress.timestamp);
        const daysSince = (Date.now() - savedDate.getTime()) / (1000 * 60 * 60 * 24);

        if (daysSince > 30) {
            return;
        }

        // Regenerate hierarchy if old format detected (no colons)
        try {
            if (progress.lastHeading && !progress.headingText.includes(' : ')) {
                const heading = document.getElementById(progress.lastHeading);
                if (heading) {
                    const newHierarchy = getHeadingHierarchy(heading);
                    if (newHierarchy) {
                        progress.headingText = newHierarchy;
                    }
                }
            }
        } catch (e) {
            console.error('ReadingProgress: Error generating hierarchy', e);
        }

        // Only restore if user is at top of page
        if (window.scrollY < 100) {
            // Automatically scroll to previous position
            scrollToProgress(progress);
            // Show notification after scrolling
            setTimeout(() => {
                showRestoredNotification(progress);
            }, 600); // Wait for scroll animation to complete
        }
    }

    /**
     * Show restored position notification
     */
    function showRestoredNotification(progress) {
        if (promptDismissed) return;

        const notification = document.createElement('div');
        notification.id = 'reading-progress-notification';
        notification.innerHTML = `
            <div class="reading-progress-notification-content">
                <span class="reading-progress-icon">📖</span>
                <div class="reading-progress-text">
                    <strong>Returned to previous position</strong>
                    <p>${progress.headingText}</p>
                    <small>${formatTimestamp(progress.timestamp)} • ${progress.percentage}% complete</small>
                </div>
                <button id="dismiss-notification-btn" class="btn-dismiss">✕</button>
            </div>
        `;

        // Add to page
        document.body.appendChild(notification);

        // Setup dismiss button
        document.getElementById('dismiss-notification-btn').addEventListener('click', () => {
            removeNotification();
        });

        // Auto-hide after 5 seconds
        setTimeout(() => {
            if (document.getElementById('reading-progress-notification')) {
                removeNotification();
            }
        }, 5000);
    }

    /**
     * Scroll to saved progress
     */
    function scrollToProgress(progress) {
        const targetHeading = document.getElementById(progress.lastHeading);

        if (targetHeading) {
            targetHeading.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        } else {
            // Fallback to scroll position if heading not found
            window.scrollTo({
                top: progress.scrollPosition,
                behavior: 'smooth'
            });
        }
    }

    /**
     * Remove the notification from DOM
     */
    function removeNotification() {
        const notification = document.getElementById('reading-progress-notification');
        if (notification) {
            notification.style.opacity = '0';
            setTimeout(() => notification.remove(), 300);
        }
    }

    /**
     * Clear progress for current page
     */
    function clearCurrentPageProgress() {
        const allProgress = getAllProgress();
        delete allProgress[currentPageKey];
        localStorage.setItem(CONFIG.storageKey, JSON.stringify(allProgress));
    }

    /**
     * Format timestamp as relative time
     */
    function formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 60) {
            return diffMins <= 1 ? 'Just now' : `${diffMins} minutes ago`;
        } else if (diffHours < 24) {
            return diffHours === 1 ? '1 hour ago' : `${diffHours} hours ago`;
        } else if (diffDays < 7) {
            return diffDays === 1 ? 'Yesterday' : `${diffDays} days ago`;
        } else {
            return date.toLocaleDateString();
        }
    }

    // Public API (if needed)
    window.ReadingProgress = {
        clearAll: function() {
            localStorage.removeItem(CONFIG.storageKey);
        },
        getAllProgress: getAllProgress,
        getCurrentProgress: getCurrentPageProgress,
        clearCurrent: clearCurrentPageProgress
    };

    // Initialize
    init();

})();
