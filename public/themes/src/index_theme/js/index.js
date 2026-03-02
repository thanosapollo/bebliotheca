/**
 * Bebliotheca Index Page JavaScript
 * Handles catalog loading, search, and rendering for the Byzantine Library
 */

(function() {
    'use strict';

    let catalog = [];
    let filteredWorks = [];
    let searchQuery = '';
    let translationFilter = 'all'; // all, translated, untranslated

    // Theme Management
    function initTheme() {
        // Default to dark mode
        const savedTheme = localStorage.getItem('theme') || 'dark';
        const themeToggle = document.getElementById('theme-toggle');
        const themeIcon = themeToggle.querySelector('.theme-toggle-icon');

        // Apply theme
        document.documentElement.setAttribute('data-theme', savedTheme);
        updateThemeIcon(savedTheme, themeIcon);

        // Toggle theme on click
        themeToggle.addEventListener('click', function() {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);
            updateThemeIcon(newTheme, themeIcon);
        });
    }

    function updateThemeIcon(theme, iconElement) {
        iconElement.textContent = theme === 'dark' ? '☀️' : '🌙';
    }

    const langNames = {
        'gr': 'Ἑλληνικά',
        'en': 'English',
        'la': 'Latin'
    };

    // Get recently viewed works from localStorage
    function getRecentlyViewed() {
        try {
            const recent = localStorage.getItem('recentlyViewed');
            return recent ? JSON.parse(recent) : {};
        } catch (e) {
            return {};
        }
    }

    // Save recently viewed work
    function saveRecentlyViewed(workId) {
        try {
            const recent = getRecentlyViewed();
            recent[workId] = Date.now();
            localStorage.setItem('recentlyViewed', JSON.stringify(recent));
        } catch (e) {
            console.error('Failed to save to localStorage:', e);
        }
    }

    // Get reading progress for a work (0-100)
    function getReadingProgress(workId) {
        try {
            // Read from the existing bebliotheca_reading_progress system
            const allProgress = localStorage.getItem('bebliotheca_reading_progress');
            if (!allProgress) {
                // No progress data stored yet
                return 0;
            }

            const progressData = JSON.parse(allProgress);

            // Debug: Log all stored paths on first call
            if (!getReadingProgress.logged) {
                console.log('Available progress data:', Object.keys(progressData));
                getReadingProgress.logged = true;
            }

            // Find progress for any translation of this work
            // Check all possible paths with and without leading slash
            const paths = [
                `/gr/${workId}.html`,
                `/en/${workId}.html`,
                `/la/${workId}.html`,
                `gr/${workId}.html`,
                `en/${workId}.html`,
                `la/${workId}.html`
            ];

            let candidates = [];
            for (const path of paths) {
                if (progressData[path] && typeof progressData[path].percentage === 'number') {
                    const timestamp = progressData[path].timestamp;
                    const date = timestamp ? new Date(timestamp) : new Date(0);

                    candidates.push({
                        path: path,
                        percentage: progressData[path].percentage,
                        date: date,
                        dateOnly: date.toISOString().split('T')[0] // Get YYYY-MM-DD only
                    });
                }
            }

            if (candidates.length === 0) {
                return 0;
            }

            // Sort by date (most recent first), then by percentage (highest first)
            candidates.sort((a, b) => {
                // Compare dates (day only)
                if (a.dateOnly !== b.dateOnly) {
                    return b.date - a.date; // Most recent first
                }
                // Same day, use highest progress
                return b.percentage - a.percentage;
            });

            const selected = candidates[0];
            console.log(`Selected progress for ${workId}: ${selected.percentage}% from ${selected.path} (${selected.dateOnly})`);

            return Math.round(selected.percentage);
        } catch (e) {
            console.error('Error reading progress:', e);
            return 0;
        }
    }

    async function loadCatalog() {
        try {
            const response = await fetch('catalog.json');
            const data = await response.json();
            catalog = data.works || [];
            applyFilters();
        } catch (error) {
            console.error('Error loading catalog:', error);
            document.getElementById('loading').textContent = 'Error loading catalog';
            document.getElementById('stats-text').textContent = 'Failed to load works';
        }
    }

    function normalizeGreek(text) {
        // Normalize Unicode to NFD (separates base chars from diacritics)
        // Then remove diacritical marks (combining diacritics in Unicode)
        // Then convert to lowercase
        return text.normalize('NFD')
                   .replace(/[\u0300-\u036f]/g, '') // Remove combining diacritical marks
                   .toLowerCase()
                   .normalize('NFC');
    }

    function hasGreekCharacters(text) {
        // Check if text contains Greek characters
        // Greek and Coptic: U+0370-U+03FF
        // Greek Extended: U+1F00-U+1FFF
        return /[\u0370-\u03FF\u1F00-\u1FFF]/.test(text);
    }

    function applyFilters() {
        filteredWorks = catalog.filter(work => {
            // Apply translation filter
            if (translationFilter !== 'all') {
                const hasGreek = work.translations.some(t => t.language === 'gr');
                const hasLatin = work.translations.some(t => t.language === 'la');
                const hasEnglish = work.translations.some(t => t.language === 'en');

                if (translationFilter === 'translated') {
                    // Work must have Greek OR Latin, AND must have English
                    if (!((hasGreek || hasLatin) && hasEnglish)) {
                        return false;
                    }
                } else if (translationFilter === 'untranslated') {
                    // Work must have Greek OR Latin, but NOT have English
                    if (!((hasGreek || hasLatin) && !hasEnglish)) {
                        return false;
                    }
                }
            }

            // Apply search filter
            if (!searchQuery) return true;

            // Check if searching for tags (starts with #)
            if (searchQuery.startsWith('#')) {
                const tagQuery = normalizeGreek(searchQuery.substring(1));
                return work.tags && work.tags.some(tag => {
                    const normalizedTag = normalizeGreek(tag);
                    return normalizedTag.includes(tagQuery);
                });
            }

            // Normal search in all fields
            const query = normalizeGreek(searchQuery);

            // Search in title and author
            const title = normalizeGreek(work.title || '');
            const author = normalizeGreek(work.author || '');

            // Search in all translation titles and authors
            const translationMatch = work.translations.some(trans => {
                const transTitle = normalizeGreek(trans.title || '');
                const transAuthor = normalizeGreek(trans.author || '');
                return transTitle.includes(query) || transAuthor.includes(query);
            });

            // Search in tags (without # prefix)
            const tagMatch = work.tags && work.tags.some(tag => {
                const normalizedTag = normalizeGreek(tag);
                return normalizedTag.includes(query);
            });

            return title.includes(query) || author.includes(query) || translationMatch || tagMatch;
        });

        // Sort by Greek titles first, then by recently viewed (only when not searching)
        if (!searchQuery) {
            const recentlyViewed = getRecentlyViewed();
            filteredWorks.sort((a, b) => {
                // Check if titles have Greek characters
                const aIsGreek = hasGreekCharacters(a.title);
                const bIsGreek = hasGreekCharacters(b.title);

                // Greek titles first
                if (aIsGreek && !bIsGreek) return -1;
                if (!aIsGreek && bIsGreek) return 1;

                // If both are Greek or both are not Greek, sort by recently viewed
                const aTime = recentlyViewed[a.id] || 0;
                const bTime = recentlyViewed[b.id] || 0;
                return bTime - aTime; // Most recent first
            });
        }

        renderWorks();
        updateStats();
    }

    function renderWorks() {
        const container = document.getElementById('works-container');
        const loading = document.getElementById('loading');
        loading.style.display = 'none';

        if (filteredWorks.length === 0) {
            container.innerHTML = '<li class="no-results">No works found matching your search.</li>';
            return;
        }

        const recentlyViewed = getRecentlyViewed();

        container.innerHTML = filteredWorks.map(work => {
            // Find original (Greek/Latin) and English translations
            const originalTrans = work.translations.find(t => t.language === 'gr' || t.language === 'la');
            const englishTrans = work.translations.find(t => t.language === 'en');

            // Check if recently viewed
            const isRecentlyViewed = recentlyViewed[work.id];
            const recentClass = isRecentlyViewed ? ' recently-viewed' : '';

            // Get reading progress
            const progress = getReadingProgress(work.id);
            const hasProgress = progress > 0;

            // Build title display
            const originalTitle = originalTrans ? originalTrans.title : work.title;
            let titleHtml = `<div class="work-title">${escapeHtml(originalTitle)}</div>`;

            // Add English translation title if it exists and is different
            if (englishTrans && englishTrans.title !== originalTitle) {
                titleHtml += `<div class="work-translation">${escapeHtml(englishTrans.title)}</div>`;
            }

            // Build progress bar if there's progress
            let progressHtml = '';
            if (hasProgress) {
                progressHtml = `
                    <div class="progress-container">
                        <div class="progress-bar" style="width: ${progress}%"></div>
                        <div class="progress-text">${progress}%</div>
                    </div>
                `;
            }

            // Build language buttons
            const languageButtons = work.translations.map(trans => {
                const langLabel = langNames[trans.language] || trans.language_name;
                return `<a href="${trans.html_path}" class="lang-btn" title="${trans.title}" data-work-id="${escapeHtml(work.id)}">${langLabel}</a>`;
            }).join('');

            // Build tags display
            let tagsHtml = '';
            if (work.tags && work.tags.length > 0) {
                const tagElements = work.tags.map(tag => `<span class="tag">#${escapeHtml(tag)}</span>`).join('');
                tagsHtml = `<div class="work-tags">${tagElements}</div>`;
            }

            return `
                <li class="work-item${recentClass}">
                    <div class="work-info">
                        ${titleHtml}
                        <div class="work-author">${escapeHtml(work.author)}</div>
                        ${progressHtml}
                        ${tagsHtml}
                    </div>
                    <div class="language-buttons">${languageButtons}</div>
                </li>
            `;
        }).join('');
    }

    function updateStats() {
        const statsText = document.getElementById('stats-text');
        const total = filteredWorks.length;
        if (searchQuery) {
            statsText.textContent = `${total} work${total !== 1 ? 's' : ''} found`;
        } else {
            statsText.textContent = `${total} work${total !== 1 ? 's' : ''}`;
        }
    }

    function initSearch() {
        const searchBox = document.getElementById('search-box');
        let debounceTimeout;
        searchBox.addEventListener('input', function() {
            clearTimeout(debounceTimeout);
            debounceTimeout = setTimeout(() => {
                searchQuery = this.value.trim();
                applyFilters();
            }, 200);
        });
    }

    function initFilters() {
        const filterButtons = document.querySelectorAll('.filter-btn');
        filterButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                // Remove active class from all buttons
                filterButtons.forEach(b => b.classList.remove('active'));
                // Add active class to clicked button
                this.classList.add('active');
                // Update filter
                translationFilter = this.getAttribute('data-filter');
                applyFilters();
            });
        });
    }

    function initClickTracking() {
        // Use event delegation to track clicks on language buttons
        const container = document.getElementById('works-container');
        container.addEventListener('click', function(e) {
            const langBtn = e.target.closest('.lang-btn');
            if (langBtn) {
                const workId = langBtn.getAttribute('data-work-id');
                if (workId) {
                    saveRecentlyViewed(workId);
                }
            }
        });
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    document.addEventListener('DOMContentLoaded', function() {
        initTheme();
        loadCatalog();
        initSearch();
        initFilters();
        initClickTracking();
    });
})();
