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
    let catalogStatus = 'loading'; // loading | ready | error

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

    // Tag suggestions - built dynamically from catalog after load
    let tagSuggestions = [];

    const ERA_DESCRIPTIONS = {
        'classical': 'Pre-Christian Greek & Latin',
        'imperial': 'Roman-era secular literature',
        'patristic': 'Church Fathers & theology',
        'byzantine': 'Medieval Roman/Byzantine',
        'scripture': 'Biblical texts'
    };

    const ERA_ORDER = ['classical', 'imperial', 'patristic', 'byzantine', 'scripture'];

    function describeTag(tag, count) {
        const suffix = ' (' + count + (count === 1 ? ' work)' : ' works)');

        // Era tags
        if (ERA_DESCRIPTIONS[tag]) {
            return ERA_DESCRIPTIONS[tag] + suffix;
        }

        // Century tags: e.g. 5c-bc, 4c-ad
        var centuryMatch = tag.match(/^(\d+)c-(bc|ad)$/);
        if (centuryMatch) {
            var n = parseInt(centuryMatch[1], 10);
            var era = centuryMatch[2].toUpperCase();
            var ordinal = n === 1 ? '1st' : n === 2 ? '2nd' : n === 3 ? '3rd' : n + 'th';
            return ordinal + ' century ' + era + suffix;
        }

        // PG range tags: e.g. pg47-64
        var pgRange = tag.match(/^pg(\d+)-(\d+)$/);
        if (pgRange) {
            return 'Patrologia Graeca vols. ' + pgRange[1] + '-' + pgRange[2] + suffix;
        }

        // PG single volume tags: e.g. pg88
        var pgSingle = tag.match(/^pg(\d+)$/);
        if (pgSingle) {
            return 'Patrologia Graeca vol. ' + pgSingle[1] + suffix;
        }

        // Unknown tag type
        return count + (count === 1 ? ' work' : ' works');
    }

    function tagSortOrder(a, b) {
        var aTag = a.value.substring(1); // strip #
        var bTag = b.value.substring(1);

        var aEra = ERA_ORDER.indexOf(aTag);
        var bEra = ERA_ORDER.indexOf(bTag);

        // Era tags first, in fixed order
        if (aEra !== -1 && bEra !== -1) return aEra - bEra;
        if (aEra !== -1) return -1;
        if (bEra !== -1) return 1;

        var aCentury = aTag.match(/^(\d+)c-(bc|ad)$/);
        var bCentury = bTag.match(/^(\d+)c-(bc|ad)$/);
        var aPg = aTag.match(/^pg(\d+)/);
        var bPg = bTag.match(/^pg(\d+)/);

        // Century tags before PG tags
        if (aCentury && !bCentury) return -1;
        if (!aCentury && bCentury) return 1;

        // Sort centuries chronologically: BC descending, then AD ascending
        if (aCentury && bCentury) {
            var aVal = parseInt(aCentury[1], 10) * (aCentury[2] === 'bc' ? -1 : 1);
            var bVal = parseInt(bCentury[1], 10) * (bCentury[2] === 'bc' ? -1 : 1);
            return aVal - bVal;
        }

        // Sort PG tags numerically
        if (aPg && bPg) {
            return parseInt(aPg[1], 10) - parseInt(bPg[1], 10);
        }

        // Fallback: alphabetical
        return aTag.localeCompare(bTag);
    }

    function buildTagSuggestions(works) {
        var tagCounts = {};
        works.forEach(function(work) {
            (work.tags || []).forEach(function(tag) {
                tagCounts[tag] = (tagCounts[tag] || 0) + 1;
            });
        });

        var suggestions = [];
        for (var tag in tagCounts) {
            if (tagCounts.hasOwnProperty(tag)) {
                suggestions.push({
                    label: '#' + tag,
                    description: describeTag(tag, tagCounts[tag]),
                    value: '#' + tag
                });
            }
        }

        suggestions.sort(tagSortOrder);
        return suggestions;
    }

    const LANG_SUGGESTIONS = [
        { label: 'lang:gr', description: 'Ἑλληνικά - Greek texts', value: 'lang:gr' },
        { label: 'lang:en', description: 'English translations', value: 'lang:en' },
        { label: 'lang:la', description: 'Latin texts', value: 'lang:la' },
    ];

    const LANG_ALIASES = { greek: 'gr', english: 'en', latin: 'la', el: 'gr' };

    // PG range matching: check if a numeric PG query falls within a range tag
    function matchesPgRange(tag, queryNum) {
        var rangeMatch = tag.match(/^pg(\d+)-(\d+)$/);
        if (!rangeMatch) return false;
        var lo = parseInt(rangeMatch[1], 10);
        var hi = parseInt(rangeMatch[2], 10);
        return queryNum >= lo && queryNum <= hi;
    }

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

            return Math.round(candidates[0].percentage);
        } catch (e) {
            console.error('Error reading progress:', e);
            return 0;
        }
    }

    function showCatalogFailure(message) {
        const loading = document.getElementById('loading');
        const statsText = document.getElementById('stats-text');
        const container = document.getElementById('works-container');

        catalogStatus = 'error';
        loading.classList.add('catalog-error');
        loading.style.display = '';
        loading.innerHTML =
            '<p>' + escapeHtml(message) + '</p>' +
            '<p>Open <a href="catalog.json">catalog.json</a> or the ' +
            '<a href="https://git.thanosapollo.org/bebliotheca">upstream source</a>.</p>';
        statsText.textContent = 'Catalog unavailable';
        container.innerHTML = '';
    }

    async function loadCatalog() {
        try {
            const response = await fetch('catalog.json');
            if (!response.ok) {
                throw new Error('HTTP ' + response.status);
            }
            const data = await response.json();
            catalog = data.works || [];
            tagSuggestions = buildTagSuggestions(catalog);
            catalogStatus = 'ready';
            applyFilters();
        } catch (error) {
            console.error('Error loading catalog:', error);
            showCatalogFailure(
                'The interactive catalog failed to load. JavaScript is available, but catalog.json could not be read.'
            );
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
        if (catalogStatus !== 'ready') {
            return;
        }

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

            // Check if searching by language (starts with lang:)
            if (searchQuery.startsWith('lang:')) {
                const langQuery = searchQuery.substring(5).trim().toLowerCase();
                const lang = LANG_ALIASES[langQuery] || langQuery;
                return work.translations.some(t => t.language === lang);
            }

            // Check if searching for tags (starts with #)
            if (searchQuery.startsWith('#')) {
                const tagQuery = normalizeGreek(searchQuery.substring(1));
                // Check if this is a pure numeric PG query (e.g. #pg50)
                const pgNumMatch = tagQuery.match(/^pg(\d+)$/);
                const pgQueryNum = pgNumMatch ? parseInt(pgNumMatch[1], 10) : null;

                return work.tags && work.tags.some(tag => {
                    const normalizedTag = normalizeGreek(tag);
                    if (normalizedTag.includes(tagQuery)) return true;
                    // Range match: #pg50 should match tag pg47-64
                    if (pgQueryNum !== null) return matchesPgRange(normalizedTag, pgQueryNum);
                    return false;
                });
            }

            // Normal search in all fields
            const query = normalizeGreek(searchQuery);

            // Search in title and author
            const title = normalizeGreek(work.title || '');
            const author = normalizeGreek(work.author || '');
            const authorLatin = (work.author_latin || '').toLowerCase();

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

            return title.includes(query) || author.includes(query) || authorLatin.includes(query) || translationMatch || tagMatch;
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
                const tagElements = work.tags.map(tag => `<span class="tag" data-tag="${escapeHtml(tag)}">#${escapeHtml(tag)}</span>`).join('');
                tagsHtml = `<div class="work-tags">${tagElements}</div>`;
            }

            return `
                <li class="work-item${recentClass}">
                    <div class="work-info">
                        ${titleHtml}
                        <div class="work-author" data-author="${escapeHtml(work.author)}">${escapeHtml(work.author)}</div>
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

    // Show/hide the clear button based on search box content
    function updateClearButton() {
        const searchBox = document.getElementById('search-box');
        const clearBtn = document.getElementById('search-clear');
        clearBtn.style.display = searchBox.value.length > 0 ? 'block' : 'none';
    }

    function initSearch() {
        const searchBox = document.getElementById('search-box');
        const dropdown = document.getElementById('search-dropdown');
        const clearBtn = document.getElementById('search-clear');
        let debounceTimeout;
        let activeIndex = -1;

        // Clear button
        updateClearButton();
        clearBtn.addEventListener('click', function() {
            searchBox.value = '';
            searchQuery = '';
            updateClearButton();
            dropdown.classList.remove('visible');
            dropdown.innerHTML = '';
            activeIndex = -1;
            applyFilters();
            searchBox.focus();
        });

        function getMatchingSuggestions(value) {
            const val = value.trim().toLowerCase();
            if (val.startsWith('#')) {
                const partial = val.substring(1);
                return tagSuggestions.filter(s =>
                    s.value.substring(1).toLowerCase().startsWith(partial)
                );
            }
            if (val.startsWith('lang:')) {
                const partial = val.substring(5);
                return LANG_SUGGESTIONS.filter(s =>
                    s.value.substring(5).startsWith(partial)
                );
            }
            return [];
        }

        function showSuggestions(suggestions) {
            if (suggestions.length === 0) {
                dropdown.classList.remove('visible');
                dropdown.innerHTML = '';
                activeIndex = -1;
                return;
            }
            var capped = suggestions.slice(0, 15);
            dropdown.innerHTML = capped.map((s, i) =>
                `<li data-value="${escapeHtml(s.value)}" class="${i === activeIndex ? 'active' : ''}">` +
                `<span class="suggestion-label">${escapeHtml(s.label)}</span>` +
                `<span class="suggestion-desc">${escapeHtml(s.description)}</span>` +
                `</li>`
            ).join('');
            dropdown.classList.add('visible');
        }

        function selectSuggestion(value) {
            searchBox.value = value;
            searchQuery = value.trim();
            dropdown.classList.remove('visible');
            dropdown.innerHTML = '';
            activeIndex = -1;
            applyFilters();
        }

        function updateDropdown() {
            const value = searchBox.value;
            if (!value.trim()) {
                dropdown.classList.remove('visible');
                dropdown.innerHTML = '';
                activeIndex = -1;
                return;
            }
            const suggestions = getMatchingSuggestions(value);
            // Hide if the value exactly matches a single suggestion (already selected)
            if (suggestions.length === 1 && suggestions[0].value === value.trim().toLowerCase()) {
                dropdown.classList.remove('visible');
                dropdown.innerHTML = '';
                activeIndex = -1;
                return;
            }
            activeIndex = -1;
            showSuggestions(suggestions);
        }

        searchBox.addEventListener('input', function() {
            updateClearButton();
            updateDropdown();
            clearTimeout(debounceTimeout);
            debounceTimeout = setTimeout(() => {
                searchQuery = this.value.trim();
                applyFilters();
            }, 200);
        });

        searchBox.addEventListener('keydown', function(e) {
            const items = dropdown.querySelectorAll('li');
            if (!dropdown.classList.contains('visible') || items.length === 0) return;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                activeIndex = Math.min(activeIndex + 1, items.length - 1);
                items.forEach((li, i) => li.classList.toggle('active', i === activeIndex));
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                activeIndex = Math.max(activeIndex - 1, 0);
                items.forEach((li, i) => li.classList.toggle('active', i === activeIndex));
            } else if (e.key === 'Enter' || e.key === 'Tab') {
                if (activeIndex >= 0 && activeIndex < items.length) {
                    e.preventDefault();
                    selectSuggestion(items[activeIndex].getAttribute('data-value'));
                }
            } else if (e.key === 'Escape') {
                dropdown.classList.remove('visible');
                dropdown.innerHTML = '';
                activeIndex = -1;
            }
        });

        dropdown.addEventListener('click', function(e) {
            const li = e.target.closest('li');
            if (li && li.dataset.value) {
                selectSuggestion(li.dataset.value);
            }
        });

        document.addEventListener('click', function(e) {
            if (!e.target.closest('.search-container')) {
                dropdown.classList.remove('visible');
                activeIndex = -1;
            }
        });
    }

    function updateFilterUI(selectedBtn, filterButtons) {
        filterButtons.forEach(function(btn) {
            const selected = btn === selectedBtn;
            btn.classList.toggle('active', selected);
            btn.setAttribute('aria-checked', selected ? 'true' : 'false');
            btn.tabIndex = selected ? 0 : -1;
        });
        translationFilter = selectedBtn.getAttribute('data-filter') || 'all';
    }

    function setFilterSelection(selectedBtn, filterButtons) {
        updateFilterUI(selectedBtn, filterButtons);
        applyFilters();
    }

    function initFilters() {
        const filterButtons = Array.from(document.querySelectorAll('.filter-btn'));
        if (filterButtons.length === 0) {
            return;
        }

        // Initialize exclusive selected state from markup without rendering yet.
        let initial = filterButtons.find(function(btn) {
            return btn.classList.contains('active') || btn.getAttribute('aria-checked') === 'true';
        }) || filterButtons[0];
        updateFilterUI(initial, filterButtons);

        filterButtons.forEach(function(btn) {
            btn.addEventListener('click', function() {
                setFilterSelection(btn, filterButtons);
            });

            btn.addEventListener('keydown', function(e) {
                const currentIndex = filterButtons.indexOf(btn);
                let nextIndex = -1;

                if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                    nextIndex = (currentIndex + 1) % filterButtons.length;
                } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                    nextIndex = (currentIndex - 1 + filterButtons.length) % filterButtons.length;
                } else if (e.key === 'Home') {
                    nextIndex = 0;
                } else if (e.key === 'End') {
                    nextIndex = filterButtons.length - 1;
                } else if (e.key === ' ' || e.key === 'Enter') {
                    e.preventDefault();
                    setFilterSelection(btn, filterButtons);
                    return;
                }

                if (nextIndex >= 0) {
                    e.preventDefault();
                    setFilterSelection(filterButtons[nextIndex], filterButtons);
                    filterButtons[nextIndex].focus();
                }
            });
        });
    }

    function initClickTracking() {
        const container = document.getElementById('works-container');
        const searchBox = document.getElementById('search-box');

        container.addEventListener('click', function(e) {
            // Track clicks on language buttons
            const langBtn = e.target.closest('.lang-btn');
            if (langBtn) {
                const workId = langBtn.getAttribute('data-work-id');
                if (workId) {
                    saveRecentlyViewed(workId);
                }
                return;
            }

            // Click on tag => search by that tag
            const tagEl = e.target.closest('.tag');
            if (tagEl && tagEl.dataset.tag) {
                searchBox.value = '#' + tagEl.dataset.tag;
                searchQuery = searchBox.value.trim();
                updateClearButton();
                applyFilters();
                return;
            }

            // Click on author => search by that author
            const authorEl = e.target.closest('.work-author');
            if (authorEl && authorEl.dataset.author) {
                searchBox.value = authorEl.dataset.author;
                searchQuery = searchBox.value.trim();
                updateClearButton();
                applyFilters();
                return;
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
        document.getElementById('copyright').textContent =
            '\u00A9 ' + new Date().getFullYear() + ' Bebliotheca Project';
    });
})();
