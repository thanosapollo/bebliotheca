/** Search-first, bounded, static Bebliotheca catalog. */
(function() {
    'use strict';

    const PAGE_SIZE = 50;
    const SUGGESTION_LIMIT = 8;
    const langNames = { gr: 'Ἑλληνικά', en: 'English', la: 'Latin' };
    const LANG_ALIASES = { greek: 'gr', english: 'en', latin: 'la', el: 'gr' };
    const COLLECTIONS = { classical: 'Classical', imperial: 'Imperial', patristic: 'Church Fathers', byzantine: 'Byzantine', scripture: 'Scripture' };
    const AVAILABILITY = { all: 'Any availability', 'with-en': 'English available', 'without-en': 'Without English' };
    const ORIGINALS = { any: 'Any', 'has-gr': 'Greek', 'has-la': 'Latin' };
    let catalog = [], filteredWorks = [], authors = [], tags = [];
    let searchQuery = '', authorFilter = '', authorIdFilter = null, workFilter = '', languageFilter = '', collectionFilter = '';
    let availabilityFilter = 'all', originalFilter = 'any', currentPage = 1;
    let catalogStatus = 'loading', debounceTimeout, suggestions = [], activeIndex = -1;
    const $ = id => document.getElementById(id);

    function normalizeGreek(text) {
        return String(text || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/ς/g, 'σ').normalize('NFC');
    }
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text == null ? '' : String(text);
        return div.innerHTML;
    }
    function escapeAttribute(text) { return escapeHtml(text).replace(/"/g, '&quot;'); }
    function readStorage(key, fallback) {
        try { return localStorage.getItem(key) || fallback; } catch (_) { return fallback; }
    }
    function writeStorage(key, value) {
        try { localStorage.setItem(key, value); } catch (_) { /* Storage is optional. */ }
    }
    function readObject(key) {
        try {
            const value = JSON.parse(readStorage(key, '{}'));
            return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
        } catch (_) { return {}; }
    }
    function initTheme() {
        const toggle = $('theme-toggle');
        function setTheme(theme) {
            document.documentElement.setAttribute('data-theme', theme);
            const label = theme === 'dark' ? 'Use light theme' : 'Use dark theme';
            toggle.setAttribute('aria-label', label);
            toggle.title = label;
        }
        setTheme(readStorage('theme', 'dark') === 'light' ? 'light' : 'dark');
        toggle.addEventListener('click', () => {
            const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
            setTheme(theme);
            writeStorage('theme', theme);
        });
    }
    function getReadingProgress(work, progressData) {
        const entries = work.translations.flatMap(trans => [trans.html_path, '/' + trans.html_path])
            .map(path => progressData[path]).filter(entry => entry && Number.isFinite(entry.percentage))
            .map(entry => ({ percentage: entry.percentage, time: Date.parse(entry.timestamp) || 0 }));
        // Match the reader's most recent day, then the furthest position that day.
        entries.sort((a, b) => Math.floor(b.time / 86400000) - Math.floor(a.time / 86400000) || b.percentage - a.percentage);
        return entries.length ? Math.max(0, Math.min(100, Math.round(entries[0].percentage))) : 0;
    }
    function buildIndexes(works) {
        const authorMap = new Map(), tagSet = new Set();
        works.forEach(work => {
            work.authorKey = work.author_id ? 'id:' + work.author_id : 'name:' + normalizeGreek(work.author);
            work.names = [...new Set([work.author, work.author_latin, ...(work.author_aliases || [])].filter(Boolean))];
            work.authorWords = new Set(normalizeGreek(work.names.join(' ')).match(/[\p{L}\p{N}]+/gu) || []);
            work.titles = [...new Set([work.title, ...work.translations.map(t => t.title)].filter(Boolean))];
            work.searchText = normalizeGreek([...work.names, ...work.titles, ...(work.tags || [])].join(' '));
            if (!authorMap.has(work.authorKey)) authorMap.set(work.authorKey, { key: work.authorKey, id: work.author_id || '', label: work.author, names: new Set(), count: 0 });
            const author = authorMap.get(work.authorKey);
            work.names.forEach(name => author.names.add(name));
            author.count++;
            (work.tags || []).forEach(tag => tagSet.add(tag));
        });
        authors = [...authorMap.values()].filter(author => author.label);
        tags = [...tagSet].sort();
    }
    function safeReadingPath(path) {
        // Catalog links are local reader documents, never executable or remote URLs.
        return typeof path === 'string' && /^(gr|en|la)\/[\p{L}\p{N}\p{M}_.-]+\.html$/u.test(path) && !path.includes('..');
    }
    async function loadCatalog() {
        catalogStatus = 'loading';
        const loading = $('loading');
        loading.classList.remove('catalog-error');
        loading.style.display = '';
        loading.textContent = 'Loading the archives…';
        $('works-container').setAttribute('aria-busy', 'true');
        $('stats-text').textContent = 'Loading catalog…';
        try {
            const response = await fetch('catalog.json');
            if (!response.ok) throw new Error('HTTP ' + response.status);
            const data = await response.json();
            if (!Array.isArray(data.works)) throw new Error('Invalid catalog');
            if (data.works.some(work => !work || typeof work.id !== 'string' || !Array.isArray(work.translations) ||
                !work.translations.length || work.translations.some(trans => !safeReadingPath(trans.html_path)))) {
                throw new Error('Invalid catalog work or reader path');
            }
            catalog = data.works;
            buildIndexes(catalog);
            catalogStatus = 'ready';
            applyFilters(false);
            if (document.activeElement === $('search-box')) updateSuggestions();
        } catch (error) {
            console.error('Error loading catalog:', error);
            showCatalogFailure();
        }
    }
    function showCatalogFailure() {
        catalogStatus = 'error';
        closeSuggestions();
        const loading = $('loading');
        loading.classList.add('catalog-error');
        loading.style.display = '';
        loading.innerHTML = '<p>The catalog could not be loaded. Check your connection and try again.</p>' +
            '<p><button type="button" id="retry-catalog">Try again</button></p>' +
            '<p>Or browse the <a href="catalog-static.html">static catalog</a>, <a href="catalog.json">catalog.json</a> or ' +
            '<a href="https://git.thanosapollo.org/bebliotheca">upstream source</a>.</p>';
        $('retry-catalog').addEventListener('click', loadCatalog);
        $('stats-text').textContent = 'Catalog unavailable';
        $('works-container').innerHTML = '';
        $('works-container').setAttribute('aria-busy', 'false');
        $('pagination').hidden = true;
    }
    function parseQuery(query) {
        const words = [], languages = [], queryTags = [];
        normalizeGreek(query).split(/\s+/).filter(Boolean).forEach(token => {
            if (token.startsWith('lang:')) languages.push(LANG_ALIASES[token.slice(5)] || token.slice(5));
            else if (token.startsWith('#')) queryTags.push(token.slice(1));
            else words.push(token);
        });
        return { words, languages, tags: queryTags };
    }
    function matchesTag(tag, query) {
        if (normalizeGreek(tag).includes(query)) return true;
        const pg = query.match(/^pg(\d+)$/), range = tag.match(/^pg(\d+)-(\d+)$/);
        return !!(pg && range && Number(pg[1]) >= Number(range[1]) && Number(pg[1]) <= Number(range[2]));
    }
    function matchesScope(work) {
        const hasGreek = work.translations.some(t => t.language === 'gr');
        const hasLatin = work.translations.some(t => t.language === 'la');
        const hasEnglish = work.translations.some(t => t.language === 'en');
        const hasOriginal = hasGreek || hasLatin;
        if (availabilityFilter === 'with-en' && (!hasOriginal || !hasEnglish)) return false;
        if (availabilityFilter === 'without-en' && (!hasOriginal || hasEnglish)) return false;
        if (originalFilter === 'has-gr' && !hasGreek) return false;
        if (originalFilter === 'has-la' && !hasLatin) return false;

        if (languageFilter && !work.translations.some(t => t.language === languageFilter)) return false;
        if (collectionFilter && !(work.tags || []).includes(collectionFilter)) return false;
        // An explicit empty id scopes a legacy author without absorbing namesakes with canonical ids.
        if (authorIdFilter !== null && (work.author_id || '') !== authorIdFilter) return false;
        if (!authorIdFilter && authorFilter && !work.names.some(name => normalizeGreek(name) === normalizeGreek(authorFilter))) return false;
        if (workFilter && work.id !== workFilter) return false;
        return true;
    }
    function matchesQuery(work, query) {
        return query.words.every(word => work.searchText.includes(word)) &&
            query.languages.every(language => work.translations.some(t => t.language === language)) &&
            query.tags.every(tag => (work.tags || []).some(value => matchesTag(value, tag)));
    }
    function applyFilters(updateHistory) {
        if (catalogStatus !== 'ready') {
            // Accepted search state must survive reload even before data arrives.
            if (updateHistory) updateURL('push');
            return;
        }
        const query = parseQuery(searchQuery);
        filteredWorks = catalog.filter(work => matchesScope(work) && matchesQuery(work, query));
        const ranks = new Map(filteredWorks.map(work => [work.id, titleRank(work, query.words.join(' '))]));
        filteredWorks.sort((a, b) => ranks.get(a.id) - ranks.get(b.id) ||
            normalizeGreek(a.title).localeCompare(normalizeGreek(b.title)) || a.id.localeCompare(b.id));
        const pageCount = Math.max(1, Math.ceil(filteredWorks.length / PAGE_SIZE));
        currentPage = Math.min(Math.max(currentPage, 1), pageCount);
        renderWorks();
        updateContext();
        updatePagination();
        const total = filteredWorks.length, start = (currentPage - 1) * PAGE_SIZE;
        $('stats-text').textContent = `${total.toLocaleString()} work${total !== 1 ? 's' : ''}` +
            (total > PAGE_SIZE ? ` · ${start + 1}–${Math.min(start + PAGE_SIZE, total)} shown` : '');
        $('reset-filters').hidden = !(searchQuery || authorFilter || authorIdFilter || workFilter || languageFilter || collectionFilter || availabilityFilter !== 'all' || originalFilter !== 'any');
        if (updateHistory) updateURL('push');
    }
    function renderWorks() {
        const container = $('works-container');
        $('loading').style.display = 'none';
        container.setAttribute('aria-busy', 'false');
        if (!filteredWorks.length) {
            container.innerHTML = '<li class="no-results"><p>No works found.</p><p>Try fewer words, another spelling, or reset the search and filters.</p></li>';
            return;
        }
        const progressData = readObject('bebliotheca_reading_progress');
        const start = (currentPage - 1) * PAGE_SIZE;
        container.innerHTML = filteredWorks.slice(start, start + PAGE_SIZE).map(work => {
            const original = work.translations.find(t => t.language === 'gr') || work.translations.find(t => t.language === 'la') || work.translations[0];
            const english = work.translations.find(t => t.language === 'en');
            const title = original.title || work.title;
            const progress = getReadingProgress(work, progressData);
            const languages = work.translations.map(trans =>
                `<a class="lang-btn" href="${escapeAttribute(trans.html_path)}" data-work-id="${escapeAttribute(work.id)}" ` +
                `hreflang="${trans.language === 'gr' ? 'el' : escapeAttribute(trans.language)}" aria-label="${escapeAttribute('Read ' + trans.title + ' in ' + (trans.language_name || langNames[trans.language]))}">${escapeHtml(langNames[trans.language] || trans.language_name)}</a>`
            ).join('');
            return `<li class="work-item" data-work-id="${escapeAttribute(work.id)}"><div class="work-info">` +
                `<h2 class="work-title">${escapeHtml(title)}</h2>` +
                (english && english.title !== title ? `<div class="work-translation">${escapeHtml(english.title)}</div>` : '') +
                `<button type="button" class="work-author" data-author="${escapeAttribute(work.author)}" data-author-id="${escapeAttribute(work.author_id || '')}" aria-label="${escapeAttribute('Find works by ' + work.author)}">${escapeHtml(work.author)}</button>` +
                (progress ? `<div class="reading-progress">${progress}% read</div>` : '') +
                `</div><div class="language-links" role="group" aria-label="Reading languages">${languages}</div></li>`;
        }).join('');
    }
    function updatePagination() {
        const pageCount = Math.max(1, Math.ceil(filteredWorks.length / PAGE_SIZE));
        $('pagination').hidden = filteredWorks.length <= PAGE_SIZE;
        $('previous-page').disabled = currentPage <= 1;
        $('next-page').disabled = currentPage >= pageCount;
        $('page-status').textContent = `Page ${currentPage} of ${pageCount}`;
    }
    function updateContext() {
        const entries = [];
        const authorLabel = authorIdFilter ? (authors.find(author => author.id === authorIdFilter)?.label || authorIdFilter) : authorFilter;
        if (authorLabel) entries.push(['author', 'Author: ' + authorLabel]);
        if (workFilter) entries.push(['work', 'Work: ' + (catalog.find(work => work.id === workFilter)?.title || workFilter)]);
        if (languageFilter) entries.push(['lang', 'Reading: ' + langNames[languageFilter]]);
        if (collectionFilter) entries.push(['collection', COLLECTIONS[collectionFilter]]);
        if (availabilityFilter !== 'all') entries.push(['availability', AVAILABILITY[availabilityFilter]]);
        if (originalFilter !== 'any') entries.push(['original', ORIGINALS[originalFilter]]);
        $('search-context').hidden = !entries.length;
        $('search-context').innerHTML = entries.map(([key, label]) => `<button type="button" data-remove="${key}" aria-label="${escapeAttribute('Remove ' + label)}">${escapeHtml(label)}<span class="context-remove" aria-hidden="true">Remove</span></button>`).join('');
        $('search-box').placeholder = (authorFilter || authorIdFilter) ? 'Search this author’s titles…' : 'Search titles and authors…';
        $('search-clear').hidden = !$('search-box').value;
        $('language-filter').value = languageFilter;
        $('collection-filter').value = collectionFilter;
        $('availability-filter').value = availabilityFilter;
        $('original-filter').value = originalFilter;
    }
    function rankTitle(label, query) {
        if (!query) return 0;
        const value = normalizeGreek(label).replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
        const phrase = query.replace(/[^\p{L}\p{N}]+/gu, ' ').trim();
        if (!phrase) return 99;
        // Ignore leading English articles for known-title lookups in either direction.
        const withoutArticle = text => text.replace(/^(the|an|a)\s+/, '');
        if (withoutArticle(value) === withoutArticle(phrase)) return 0;
        if ((' ' + value + ' ').includes(' ' + phrase + ' ')) return 1;
        const tokens = value.split(' '), words = phrase.split(' ');
        if (words.every(word => tokens.includes(word))) return 2;
        if (words.every(word => value.includes(word))) return 3;
        return 99;
    }
    function rankWorkTitle(work, title, query) {
        const rank = rankTitle(title, query);
        const words = query.match(/[\p{L}\p{N}]+/gu) || [];
        const titleWords = words.filter(word => !work.authorWords.has(word));
        // Exact trusted author words can qualify a title query; an author-only query stays unchanged.
        if (!titleWords.length || titleWords.length === words.length) return rank;
        return Math.min(rank, rankTitle(title, titleWords.join(' ')));
    }
    function titleRank(work, query) {
        return Math.min(...work.titles.map(title => rankWorkTitle(work, title, query)));
    }
    function rankMatch(label, query) {
        const value = normalizeGreek(label);
        if (value === query) return 0;
        if (value.startsWith(query)) return 1;
        if (value.split(/\s+/).some(word => word.startsWith(query))) return 2;
        if (query.split(/\s+/).every(word => value.includes(word))) return 3;
        return 99;
    }
    function matchingSuggestions() {
        const raw = $('search-box').value.trim(), query = normalizeGreek(raw);
        if (!query || catalogStatus !== 'ready') return [];
        const tokens = raw.split(/\s+/), last = tokens[tokens.length - 1];
        const prefix = tokens.slice(0, -1).join(' ');
        function tokenSuggestion(value, label, description) { return { type: 'query', value: (prefix ? prefix + ' ' : '') + value + ' ', label, description }; }
        if (last.startsWith('#')) return tags.filter(tag => normalizeGreek(tag).startsWith(normalizeGreek(last.slice(1))))
            .slice(0, SUGGESTION_LIMIT).map(tag => tokenSuggestion('#' + tag, '#' + tag, COLLECTIONS[tag] || 'Catalog tag'));
        if (normalizeGreek(last).startsWith('lang:')) return Object.entries(langNames)
            .filter(([language]) => language.startsWith(normalizeGreek(last.slice(5))) || language === LANG_ALIASES[normalizeGreek(last.slice(5))])
            .map(([language, label]) => tokenSuggestion('lang:' + language, label, 'Reading language'));
        const matches = [];
        if (!authorFilter && !authorIdFilter && !workFilter) {
            const availableAuthors = new Set(catalog.filter(matchesScope).map(work => work.authorKey));
            authors.filter(author => availableAuthors.has(author.key)).forEach(author => {
                const name = [...author.names].sort((a, b) => rankMatch(a, query) - rankMatch(b, query))[0];
                const rank = rankMatch(name, query);
                if (rank < 99) matches.push({ type: 'author', value: author.label, authorId: author.id, label: author.label,
                    description: `Author · ${author.count} work${author.count === 1 ? '' : 's'}` + (name !== author.label ? ' · ' + name : ''), rank });
            });
        }
        catalog.filter(matchesScope).forEach(work => {
            const title = [...work.titles].sort((a, b) => rankWorkTitle(work, a, query) - rankWorkTitle(work, b, query))[0];
            const rank = rankWorkTitle(work, title, query);
            if (rank < 99) matches.push({ type: 'work', value: work.id, label: title, description: 'Work · ' + work.author, rank: rank + 0.25 });
        });
        // Ordinary language/collection names are suggestions, not promised natural-language parsing.
        Object.entries(langNames).forEach(([value, label]) => {
            if (rankMatch(label + ' ' + (value === 'gr' ? 'Greek' : ''), query) < 99)
                matches.push({ type: 'language', value, label, description: 'Reading language', rank: 4 });
        });
        Object.entries(COLLECTIONS).forEach(([value, label]) => {
            if (rankMatch(label + ' ' + value, query) < 99)
                matches.push({ type: 'collection', value, label, description: 'Collection', rank: 4 });
        });
        return matches.sort((a, b) => a.rank - b.rank || a.label.localeCompare(b.label)).slice(0, SUGGESTION_LIMIT);
    }
    function closeSuggestions() {
        suggestions = [];
        activeIndex = -1;
        $('search-dropdown').hidden = true;
        $('search-dropdown').innerHTML = '';
        $('search-box').setAttribute('aria-expanded', 'false');
        $('search-box').removeAttribute('aria-activedescendant');
    }
    function updateSuggestions() {
        closeSuggestions();
        suggestions = matchingSuggestions();
        if (!suggestions.length) return;
        $('search-dropdown').innerHTML = suggestions.map((item, i) => `<li id="suggestion-${i}" role="option" aria-selected="false" data-index="${i}">` +
            `<span class="suggestion-label">${escapeHtml(item.label)}</span><span class="suggestion-desc">${escapeHtml(item.description)}</span></li>`).join('');
        $('search-dropdown').hidden = false;
        $('search-box').setAttribute('aria-expanded', 'true');
    }
    function cancelPendingSearch() { clearTimeout(debounceTimeout); }
    function commitSearch() {
        cancelPendingSearch();
        searchQuery = $('search-box').value.trim();
        currentPage = 1;
        applyFilters(true);
    }
    function selectSuggestion(item) {
        if (!item) return;
        cancelPendingSearch();
        searchQuery = '';
        if (item.type === 'author') { authorFilter = item.value; authorIdFilter = item.authorId || ''; workFilter = ''; }
        if (item.type === 'work') workFilter = item.value;
        if (item.type === 'language') languageFilter = item.value;
        if (item.type === 'collection') collectionFilter = item.value;
        if (item.type === 'query') searchQuery = item.value;
        $('search-box').value = searchQuery;
        searchQuery = searchQuery.trim();
        currentPage = 1;
        closeSuggestions();
        applyFilters(true);
        $('search-box').focus();
    }
    function updateURL(mode) {
        const params = new URLSearchParams();
        if (searchQuery) params.set('q', searchQuery);
        if (authorFilter) params.set('author', authorFilter);
        if (authorIdFilter !== null) params.set('author_id', authorIdFilter);
        if (workFilter) params.set('work', workFilter);
        if (languageFilter) params.set('lang', languageFilter);
        if (collectionFilter) params.set('collection', collectionFilter);
        if (availabilityFilter !== 'all') params.set('availability', availabilityFilter);
        if (originalFilter !== 'any') params.set('original', originalFilter);
        if (currentPage > 1) params.set('page', String(currentPage));
        const next = window.location.pathname + (params.size ? '?' + params.toString() : '') + window.location.hash;
        if (next !== window.location.pathname + window.location.search + window.location.hash) window.history[mode + 'State']({}, '', next);
    }
    function restoreStateFromURL() {
        cancelPendingSearch();
        closeSuggestions();
        const params = new URLSearchParams(window.location.search);
        const page = Number(params.get('page'));
        searchQuery = params.get('q') || '';
        authorFilter = params.get('author') || '';
        authorIdFilter = params.get('author_id');
        workFilter = params.get('work') || '';
        languageFilter = Object.hasOwn(langNames, params.get('lang')) ? params.get('lang') : '';
        collectionFilter = Object.hasOwn(COLLECTIONS, params.get('collection')) ? params.get('collection') : '';
        availabilityFilter = Object.hasOwn(AVAILABILITY, params.get('availability')) ? params.get('availability') : 'all';
        const original = { 'gr-only': 'has-gr', 'la-only': 'has-la' }[params.get('original')] || params.get('original');
        originalFilter = Object.hasOwn(ORIGINALS, original) ? original : 'any';
        currentPage = Number.isInteger(page) && page > 0 ? page : 1;
        $('search-box').value = searchQuery;
        updateContext();
    }
    function resetSearch() {
        cancelPendingSearch();
        searchQuery = authorFilter = workFilter = languageFilter = collectionFilter = '';
        authorIdFilter = null;
        availabilityFilter = 'all'; originalFilter = 'any'; currentPage = 1;
        $('search-box').value = '';
        closeSuggestions();
        updateContext();
        applyFilters(true);
        $('search-box').focus();
    }
    function initSearch() {
        const searchBox = $('search-box');
        searchBox.addEventListener('input', event => {
            cancelPendingSearch();
            searchQuery = searchBox.value.trim();
            workFilter = ''; // A new query replaces a selected work, not deliberate author/facet scopes.
            currentPage = 1;
            $('search-clear').hidden = !searchBox.value;
            if (event.isComposing) { closeSuggestions(); return; }
            updateSuggestions();
            debounceTimeout = setTimeout(() => applyFilters(true), 180);
        });
        searchBox.addEventListener('compositionend', () => { updateSuggestions(); debounceTimeout = setTimeout(commitSearch, 180); });
        searchBox.addEventListener('focus', updateSuggestions);
        searchBox.addEventListener('blur', closeSuggestions);
        searchBox.addEventListener('keydown', event => {
            if (event.isComposing) return;
            if (event.key === 'Escape') {
                event.preventDefault(); // Do not let native search inputs silently clear the query.
                closeSuggestions();
            } else if (event.key === 'Tab') {
                closeSuggestions(); // Normal Tab navigation, never selection or a focus trap.
            } else if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
                if (!suggestions.length) updateSuggestions();
                if (!suggestions.length) return;
                event.preventDefault();
                activeIndex = event.key === 'ArrowDown' ? (activeIndex + 1) % suggestions.length : (activeIndex <= 0 ? suggestions.length - 1 : activeIndex - 1);
                [...$('search-dropdown').children].forEach((item, i) => item.setAttribute('aria-selected', String(i === activeIndex)));
                const active = $('suggestion-' + activeIndex);
                searchBox.setAttribute('aria-activedescendant', active.id);
                active.scrollIntoView({ block: 'nearest' });
            } else if (event.key === 'Enter') {
                event.preventDefault();
                if (activeIndex >= 0) selectSuggestion(suggestions[activeIndex]);
                else { commitSearch(); closeSuggestions(); }
            }
        });
        // Keep combobox focus until click selects, including touch-generated pointer events.
        $('search-dropdown').addEventListener('pointerdown', event => event.preventDefault());
        $('search-dropdown').addEventListener('click', event => {
            const option = event.target.closest('[data-index]');
            if (option) selectSuggestion(suggestions[Number(option.dataset.index)]);
        });
        $('search-clear').addEventListener('click', () => {
            cancelPendingSearch(); searchBox.value = ''; searchQuery = ''; currentPage = 1;
            closeSuggestions(); updateContext(); applyFilters(true); searchBox.focus();
        });
        $('reset-filters').addEventListener('click', resetSearch);
        const setters = {
            language: value => { languageFilter = value; }, collection: value => { collectionFilter = value; },
            availability: value => { availabilityFilter = value; }, original: value => { originalFilter = value; }
        };
        Object.entries(setters).forEach(([key, setter]) => $(key + '-filter').addEventListener('change', event => {
            cancelPendingSearch(); setter(event.target.value); currentPage = 1; closeSuggestions(); applyFilters(true);
        }));
        $('search-context').addEventListener('click', event => {
            const button = event.target.closest('[data-remove]');
            if (!button) return;
            cancelPendingSearch();
            switch (button.dataset.remove) {
            case 'author': authorFilter = ''; authorIdFilter = null; break;
            case 'work': workFilter = ''; break;
            case 'lang': languageFilter = ''; break;
            case 'collection': collectionFilter = ''; break;
            case 'availability': availabilityFilter = 'all'; break;
            case 'original': originalFilter = 'any'; break;
            }
            currentPage = 1; closeSuggestions(); applyFilters(true); searchBox.focus();
        });
        $('works-container').addEventListener('click', event => {
            const link = event.target.closest('a[data-work-id]');
            if (link) {
                // Persist the current query before following a reader link, even inside the debounce window.
                cancelPendingSearch(); updateURL('push');
                const recent = readObject('recentlyViewed');
                recent[link.dataset.workId] = Date.now();
                writeStorage('recentlyViewed', JSON.stringify(recent));
            }
            const author = event.target.closest('button[data-author]');
            if (author) selectSuggestion({ type: 'author', value: author.dataset.author, authorId: author.dataset.authorId });
        });
        ['previous', 'next'].forEach(direction => $(direction + '-page').addEventListener('click', () => {
            cancelPendingSearch();
            currentPage += direction === 'next' ? 1 : -1;
            closeSuggestions(); applyFilters(true);
            const title = document.querySelector('.work-title');
            if (title) { title.tabIndex = -1; title.focus(); }
            $('stats').scrollIntoView({ block: 'start' });
        }));
        window.addEventListener('popstate', function() {
            restoreStateFromURL();
            applyFilters(false);
        });
        window.addEventListener('pageshow', event => {
            if (event.persisted) { restoreStateFromURL(); applyFilters(false); }
        });
    }
    document.addEventListener('DOMContentLoaded', function() {
        initTheme();
        initSearch();
        restoreStateFromURL();
        loadCatalog();
        $('copyright').textContent = '\u00A9 ' + new Date().getFullYear() + ' Bebliotheca Project';
    });
})();
