// ============================================
// Simple Parallel Text View - Fresh Start
// ============================================

(function() {
    'use strict';

    // Global flag to check if we're in parallel view
    window.inParallelView = window.inParallelView || false;

    // Language dictionary mapping display name to directory
    var LANGUAGES = {
        'Ελληνικά': 'gr',
        'English': 'en',
	'Latin' : 'la'
    };

    var ParallelView = {
        init: function() {
            // Don't show button if we're inside an iframe
            if (window.self !== window.top) {
                console.log('Inside iframe, not showing parallel button');
                return;
            }

            // Don't show button if we're already in a parallel view
            if (window.inParallelView) {
                console.log('Already in parallel view, not showing button');
                return;
            }

            var path = window.location.pathname;
            var filename = path.substring(path.lastIndexOf('/') + 1);

            if (filename === 'index.html' || filename === '') return;

            // Detect current language from path (e.g., /en/, /gr/, /la/)
            var langMatch = path.match(/\/([a-z]{2})\//);
            if (!langMatch) return;

            var currentLangCode = langMatch[1];
            var currentLangName = null;

            // Find the display name for current language
            for (var langName in LANGUAGES) {
                if (LANGUAGES[langName] === currentLangCode) {
                    currentLangName = langName;
                    break;
                }
            }

            if (!currentLangName) return;

            // Build list of all possible translation paths to check
            var translationsToCheck = [];
            for (var langName in LANGUAGES) {
                var langCode = LANGUAGES[langName];
                if (langCode !== currentLangCode) {
                    var translationPath = path.replace('/' + currentLangCode + '/', '/' + langCode + '/');
                    translationsToCheck.push({
                        code: langCode,
                        name: langName,
                        path: translationPath
                    });
                }
            }

            if (translationsToCheck.length === 0) return;

            // Check all translations in parallel and collect which ones exist
            var availableTranslations = [];
            var checksCompleted = 0;

            translationsToCheck.forEach(function(translation) {
                $.ajax({
                    url: translation.path,
                    type: 'HEAD',
                    success: function() {
                        availableTranslations.push(translation);
                    },
                    complete: function() {
                        checksCompleted++;
                        // When all checks are done, setup if we found at least one translation
                        if (checksCompleted === translationsToCheck.length && availableTranslations.length > 0) {
                            // Sort available translations to have a consistent default
                            availableTranslations.sort(function(a, b) {
                                return a.name.localeCompare(b.name);
                            });

                            // Use the first available translation as default
                            var defaultTranslation = availableTranslations[0];
                            ParallelView.setup(
                                path,
                                defaultTranslation.path,
                                currentLangCode,
                                currentLangName,
                                availableTranslations
                            );
                        }
                    }
                });
            });
        },

        setup: function(currentFile, parallelFile, currentLangCode, currentLangName, availableTranslations) {
            // Add button
            var btn = $('<button id="parallel-view-btn">Translation</button>');
            $('body').append(btn);
            btn.css('display', 'block');

            // Store available translations for this file
            ParallelView.currentLangCode = currentLangCode;
            ParallelView.availableTranslations = availableTranslations;

            // Build language options - include current language + available translations
            var languageOptions = '<option value="' + currentLangCode + '">' + currentLangName + '</option>';
            availableTranslations.forEach(function(translation) {
                languageOptions += '<option value="' + translation.code + '">' + translation.name + '</option>';
            });

            var modal = $('<div id="parallel-modal">' +
                '<div id="parallel-modal-header">' +
                    '<div id="parallel-modal-controls">' +
                        '<button class="parallel-control-btn" id="sync-toggle">🔗 Sync: ON</button>' +
                        '<a href="/index.html" id="parallel-home-btn" class="parallel-control-btn" title="Home">⌂</a>' +
                    '</div>' +
                    '<button id="parallel-close-btn">×</button>' +
                '</div>' +
                '<div id="parallel-content">' +
                    '<div class="parallel-pane" id="left-pane">' +
                        '<div class="parallel-pane-header">' +
                            '<select id="left-lang-selector" class="lang-selector">' +
                                languageOptions +
                            '</select>' +
                            '<a href="' + currentFile + '" target="_blank" class="open-link">Open ↗</a>' +
                        '</div>' +
                        '<iframe id="left-frame" src="' + currentFile + '"></iframe>' +
                    '</div>' +
                    '<div class="parallel-pane" id="right-pane">' +
                        '<div class="parallel-pane-header">' +
                            '<select id="right-lang-selector" class="lang-selector">' +
                                languageOptions +
                            '</select>' +
                            '<a href="' + parallelFile + '" target="_blank" class="open-link">Open ↗</a>' +
                        '</div>' +
                        '<iframe id="right-frame" src="' + parallelFile + '"></iframe>' +
                    '</div>' +
                '</div>' +
                '<div id="parallel-sync-indicator"></div>' +
            '</div>');

            $('body').append(modal);

            // Set initial dropdown values based on current and parallel files
            var parallelLangCode = availableTranslations[0].code; // First available translation
            $('#left-lang-selector').val(currentLangCode);
            $('#right-lang-selector').val(parallelLangCode);

            // Store the base filename (without language directory) - matches any 2-letter language code
            var basePath = window.location.pathname.replace(/\/([a-z]{2})\//, '/LANG/');

            // Button click - open modal
            btn.on('click', function() {
                if (!$('#parallel-modal').hasClass('show')) {
                    ParallelView.open();
                }
            });

            // Close button
            $('#parallel-close-btn').on('click', function() {
                ParallelView.close();
            });

            // Left language selector
            $('#left-lang-selector').on('change', function() {
                var selectedLang = $(this).val();
                var newPath = basePath.replace('/LANG/', '/' + selectedLang + '/');

                $('#left-frame').attr('src', newPath);
                $('#left-pane .open-link').attr('href', newPath);
                console.log('Left pane changed to:', newPath);
            });

            // Right language selector
            $('#right-lang-selector').on('change', function() {
                var selectedLang = $(this).val();
                var newPath = basePath.replace('/LANG/', '/' + selectedLang + '/');

                $('#right-frame').attr('src', newPath);
                $('#right-pane .open-link').attr('href', newPath);
                console.log('Right pane changed to:', newPath);
            });

            // Sync toggle
            $('#sync-toggle').on('click', function() {
                ParallelView.syncEnabled = !ParallelView.syncEnabled;
                $(this).text(ParallelView.syncEnabled ? '🔗 Sync: ON' : '🔓 Sync: OFF');
            });

            // Escape to close
            $(document).on('keydown', function(e) {
                if (e.key === 'Escape' && $('#parallel-modal').hasClass('show')) {
                    ParallelView.close();
                }
            });

            // Watch parent for theme/font changes and propagate to iframes
            var settingsObserver = new MutationObserver(function() {
                ParallelView.syncSettingsToIframes();
            });
            settingsObserver.observe(document.documentElement, {
                attributes: true, attributeFilter: ['data-theme']
            });
            settingsObserver.observe(document.body, {
                attributes: true, attributeFilter: ['data-font']
            });

            // Wait for iframes to load
            var loadCount = 0;
            $('#left-frame, #right-frame').on('load', function() {
                loadCount++;

                try {
                    var iframe = this;
                    var iframeDoc = iframe.contentDocument || iframe.contentWindow.document;

                    // Propagate parent theme and font to iframe
                    var parentTheme = document.documentElement.getAttribute('data-theme') || 'dark';
                    var parentFont = document.body.getAttribute('data-font') || 'sans';
                    iframeDoc.documentElement.setAttribute('data-theme', parentTheme);
                    if (iframeDoc.body) {
                        iframeDoc.body.setAttribute('data-font', parentFont);
                    }

                    // Inject mobile styles into iframe with media query
                    var style = iframeDoc.createElement('style');
                    style.textContent = `
                        /* Hide home button and theme/font controls in iframes */
                        #home-button { display: none !important; }
                        #theme-toggle-mobile { display: none !important; }
                        #font-selector-mobile { display: none !important; }

                        @media (max-width: 768px) {
                            #content {
                                padding: 0.5em !important;
                                margin: 0 !important;
                                font-size: 13px !important;
                            }
                            #content h1 { font-size: 140% !important; margin-bottom: 0.5em !important; }
                            #content h2 { font-size: 120% !important; margin: 0.8em 0 0.5em 0 !important; }
                            #content h3 { font-size: 110% !important; margin: 0.6em 0 0.4em 0 !important; }
                            #content p { margin: 0.5em 0 !important; line-height: 1.4 !important; }
                            #table-of-contents {
                                font-size: 11px !important;
                                width: 250px !important;
                                top: 0 !important;
                                padding-top: 0 !important;
                            }
                            #table-of-contents h2 {
                                margin-top: 0 !important;
                                padding-top: 0.809em !important;
                            }
                            #table-of-contents a { padding: 0.3em 1em !important; font-size: 11px !important; }
                            #toc-buttons { display: none !important; }
                            #toc-hide-btn { display: none !important; }
                            #toc-show-btn { display: none !important; }
                        }
                    `;
                    iframeDoc.head.appendChild(style);
                    console.log('Injected styles and synced theme/font into iframe');
                } catch (e) {
                    console.log('Could not inject styles:', e);
                }

                if (loadCount === 2) {
                    ParallelView.setupTOCClickHandlers();
                    ParallelView.startSync();
                }
            });
        },

        // Propagate theme and font from parent to both iframes
        syncSettingsToIframes: function() {
            var theme = document.documentElement.getAttribute('data-theme') || 'dark';
            var font = document.body.getAttribute('data-font') || 'sans';

            ['left-frame', 'right-frame'].forEach(function(id) {
                try {
                    var iframe = document.getElementById(id);
                    if (!iframe) return;
                    var iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                    iframeDoc.documentElement.setAttribute('data-theme', theme);
                    if (iframeDoc.body) {
                        iframeDoc.body.setAttribute('data-font', font);
                    }
                } catch (e) {
                    // cross-origin or not loaded yet
                }
            });
        },

        syncEnabled: true,
        syncInterval: null,
        lastLeft: 0,
        lastRight: 0,
        syncing: false,

        open: function() {
            var modal = $('#parallel-modal');
            modal.css('display', 'block');
            $('body').addClass('parallel-view-open');

            // Set global flag
            window.inParallelView = true;

            setTimeout(function() { modal.addClass('show'); }, 10);
        },

        close: function() {
            var modal = $('#parallel-modal');
            modal.removeClass('show');
            $('body').removeClass('parallel-view-open');

            // Clear global flag
            window.inParallelView = false;

            if (ParallelView.syncInterval) {
                clearInterval(ParallelView.syncInterval);
            }

            setTimeout(function() { modal.css('display', 'none'); }, 300);
        },

        setupTOCClickHandlers: function() {
            var leftFrame = document.getElementById('left-frame');
            var rightFrame = document.getElementById('right-frame');

            if (!leftFrame || !rightFrame) return;

            try {
                var leftDoc = leftFrame.contentDocument || leftFrame.contentWindow.document;
                var rightDoc = rightFrame.contentDocument || rightFrame.contentWindow.document;

                // Add click handlers to TOC links in left frame
                $(leftDoc).find('#text-table-of-contents a').on('click', function(e) {
                    e.preventDefault();
                    var href = $(this).attr('href');
                    if (href && href.startsWith('#')) {
                        var headingId = href.substring(1);
                        console.log('Left TOC clicked:', headingId);
                        ParallelView.scrollBothToHeading(headingId);
                    }
                });

                // Add click handlers to TOC links in right frame
                $(rightDoc).find('#text-table-of-contents a').on('click', function(e) {
                    e.preventDefault();
                    var href = $(this).attr('href');
                    if (href && href.startsWith('#')) {
                        var headingId = href.substring(1);
                        console.log('Right TOC clicked:', headingId);
                        ParallelView.scrollBothToHeading(headingId);
                    }
                });

                console.log('TOC click handlers setup complete');
            } catch (e) {
                console.log('Error setting up TOC handlers:', e);
            }
        },

        scrollBothToHeading: function(headingId) {
            var leftFrame = document.getElementById('left-frame');
            var rightFrame = document.getElementById('right-frame');

            if (!leftFrame || !rightFrame) return;

            var leftWin = leftFrame.contentWindow;
            var rightWin = rightFrame.contentWindow;

            // Scroll left frame
            try {
                var leftDoc = leftWin.document;
                var leftHeading = leftDoc.getElementById(headingId);
                if (leftHeading) {
                    var rect = leftHeading.getBoundingClientRect();
                    var currentScroll = leftDoc.documentElement.scrollTop || leftDoc.body.scrollTop;
                    var targetScroll = currentScroll + rect.top - 50;

                    leftDoc.documentElement.scrollTop = targetScroll;
                    leftDoc.body.scrollTop = targetScroll;
                    ParallelView.lastLeft = targetScroll;

                    console.log('Scrolled left to:', headingId, targetScroll);
                } else {
                    console.log('Heading not found in left:', headingId);
                }
            } catch (e) {
                console.log('Error scrolling left:', e);
            }

            // Scroll right frame
            try {
                var rightDoc = rightWin.document;
                var rightHeading = rightDoc.getElementById(headingId);
                if (rightHeading) {
                    var rect = rightHeading.getBoundingClientRect();
                    var currentScroll = rightDoc.documentElement.scrollTop || rightDoc.body.scrollTop;
                    var targetScroll = currentScroll + rect.top - 50;

                    rightDoc.documentElement.scrollTop = targetScroll;
                    rightDoc.body.scrollTop = targetScroll;
                    ParallelView.lastRight = targetScroll;

                    console.log('Scrolled right to:', headingId, targetScroll);
                } else {
                    console.log('Heading not found in right:', headingId);
                }
            } catch (e) {
                console.log('Error scrolling right:', e);
            }
        },

        isCustomId: function(id) {
            // CUSTOM_IDs from .org files use patterns like:
            //   h1, h1-h1, h0-h3 (hand-curated)
            //   bk-1, ch-3, sec-5, bk-1-ch-2-sec-3 (auto-generated)
            // Org-mode auto-generates IDs starting with "org" (e.g., org9a81d0f)
            // and structural IDs like "content", "table-of-contents", etc.
            if (!id) return false;
            if (/^org[0-9a-f]/.test(id)) return false;
            if (/^(content|table-of-contents|text-table-of-contents|postamble|preamble)$/.test(id)) return false;
            if (/^(outline-container-|text-)/.test(id)) return false;
            return true;
        },

        getCurrentVisibleHeading: function(doc) {
            // Find all heading elements with CUSTOM_IDs
            var headings = doc.querySelectorAll('h2[id], h3[id], h4[id]');
            var filtered = [];

            for (var i = 0; i < headings.length; i++) {
                if (ParallelView.isCustomId(headings[i].id)) {
                    filtered.push(headings[i]);
                }
            }

            var scrollTop = doc.documentElement.scrollTop || doc.body.scrollTop;
            var currentHeading = null;

            // Find the last heading that's above the current scroll position
            for (var i = 0; i < filtered.length; i++) {
                var rect = filtered[i].getBoundingClientRect();
                var headingTop = scrollTop + rect.top;

                if (headingTop <= scrollTop + 100) { // 100px offset
                    currentHeading = filtered[i];
                }
            }

            return currentHeading;
        },

        getNextHeading: function(doc, currentHeading) {
            var headings = doc.querySelectorAll('h2[id], h3[id], h4[id]');
            var filtered = [];

            for (var i = 0; i < headings.length; i++) {
                if (ParallelView.isCustomId(headings[i].id)) {
                    filtered.push(headings[i]);
                }
            }

            var found = false;
            for (var i = 0; i < filtered.length; i++) {
                if (found) {
                    return filtered[i];
                }
                if (filtered[i].id === currentHeading.id) {
                    found = true;
                }
            }
            return null;
        },

        startSync: function() {
            var leftFrame = document.getElementById('left-frame');
            var rightFrame = document.getElementById('right-frame');
            var leftWin = leftFrame.contentWindow;
            var rightWin = rightFrame.contentWindow;

            console.log('Starting section-based sync...');

            // Section-based sync polling
            ParallelView.syncInterval = setInterval(function() {
                if (!ParallelView.syncEnabled || ParallelView.syncing) return;

                try {
                    var leftDoc = leftWin.document;
                    var rightDoc = rightWin.document;

                    var leftScroll = leftDoc.documentElement.scrollTop || leftDoc.body.scrollTop || 0;
                    var rightScroll = rightDoc.documentElement.scrollTop || rightDoc.body.scrollTop || 0;

                    // Left scrolled
                    if (Math.abs(leftScroll - ParallelView.lastLeft) > 20) {
                        console.log('Left scrolled to:', leftScroll);
                        ParallelView.lastLeft = leftScroll;
                        ParallelView.syncFromLeftToRight(leftWin, rightWin);
                    }
                    // Right scrolled
                    else if (Math.abs(rightScroll - ParallelView.lastRight) > 20) {
                        console.log('Right scrolled to:', rightScroll);
                        ParallelView.lastRight = rightScroll;
                        ParallelView.syncFromRightToLeft(rightWin, leftWin);
                    }
                } catch (e) {
                    console.log('Sync error:', e);
                }
            }, 200);
        },

        syncFromLeftToRight: function(leftWin, rightWin) {
            ParallelView.syncing = true;

            var leftDoc = leftWin.document;
            var rightDoc = rightWin.document;

            // Get current visible heading in left document
            var leftHeading = ParallelView.getCurrentVisibleHeading(leftDoc);

            if (!leftHeading) {
                ParallelView.syncing = false;
                return;
            }

            var headingId = leftHeading.id;
            var rightHeading = rightDoc.getElementById(headingId);

            if (!rightHeading) {
                console.log('Heading not found in right:', headingId);
                ParallelView.syncing = false;
                return;
            }

            // Get scroll positions
            var leftScroll = leftDoc.documentElement.scrollTop || leftDoc.body.scrollTop;
            var leftRect = leftHeading.getBoundingClientRect();
            var leftHeadingTop = leftScroll + leftRect.top;
            var scrollInSection = leftScroll - leftHeadingTop;

            // Find next heading to calculate section height
            var leftNextHeading = ParallelView.getNextHeading(leftDoc, leftHeading);
            var rightNextHeading = ParallelView.getNextHeading(rightDoc, rightHeading);

            var leftSectionHeight, rightSectionHeight;

            if (leftNextHeading) {
                var leftNextRect = leftNextHeading.getBoundingClientRect();
                var leftNextTop = leftScroll + leftNextRect.top;
                leftSectionHeight = leftNextTop - leftHeadingTop;
            } else {
                leftSectionHeight = (leftDoc.documentElement.scrollHeight || leftDoc.body.scrollHeight) - leftHeadingTop;
            }

            var rightScroll = rightDoc.documentElement.scrollTop || rightDoc.body.scrollTop;
            var rightRect = rightHeading.getBoundingClientRect();
            var rightHeadingTop = rightScroll + rightRect.top;

            if (rightNextHeading) {
                var rightNextRect = rightNextHeading.getBoundingClientRect();
                var rightNextTop = rightScroll + rightNextRect.top;
                rightSectionHeight = rightNextTop - rightHeadingTop;
            } else {
                rightSectionHeight = (rightDoc.documentElement.scrollHeight || rightDoc.body.scrollHeight) - rightHeadingTop;
            }

            // Calculate percentage within section
            var percentage = leftSectionHeight > 0 ? scrollInSection / leftSectionHeight : 0;

            // Apply to right section
            var targetScroll = rightHeadingTop + (percentage * rightSectionHeight);

            rightDoc.documentElement.scrollTop = targetScroll;
            rightDoc.body.scrollTop = targetScroll;
            ParallelView.lastRight = targetScroll;

            console.log('Synced to heading:', headingId, 'section %:', (percentage * 100).toFixed(1));

            setTimeout(function() {
                ParallelView.syncing = false;
            }, 100);
        },

        syncFromRightToLeft: function(rightWin, leftWin) {
            ParallelView.syncing = true;

            var leftDoc = leftWin.document;
            var rightDoc = rightWin.document;

            // Get current visible heading in right document
            var rightHeading = ParallelView.getCurrentVisibleHeading(rightDoc);

            if (!rightHeading) {
                ParallelView.syncing = false;
                return;
            }

            var headingId = rightHeading.id;
            var leftHeading = leftDoc.getElementById(headingId);

            if (!leftHeading) {
                console.log('Heading not found in left:', headingId);
                ParallelView.syncing = false;
                return;
            }

            // Get scroll positions
            var rightScroll = rightDoc.documentElement.scrollTop || rightDoc.body.scrollTop;
            var rightRect = rightHeading.getBoundingClientRect();
            var rightHeadingTop = rightScroll + rightRect.top;
            var scrollInSection = rightScroll - rightHeadingTop;

            // Find next heading to calculate section height
            var rightNextHeading = ParallelView.getNextHeading(rightDoc, rightHeading);
            var leftNextHeading = ParallelView.getNextHeading(leftDoc, leftHeading);

            var rightSectionHeight, leftSectionHeight;

            if (rightNextHeading) {
                var rightNextRect = rightNextHeading.getBoundingClientRect();
                var rightNextTop = rightScroll + rightNextRect.top;
                rightSectionHeight = rightNextTop - rightHeadingTop;
            } else {
                rightSectionHeight = (rightDoc.documentElement.scrollHeight || rightDoc.body.scrollHeight) - rightHeadingTop;
            }

            var leftScroll = leftDoc.documentElement.scrollTop || leftDoc.body.scrollTop;
            var leftRect = leftHeading.getBoundingClientRect();
            var leftHeadingTop = leftScroll + leftRect.top;

            if (leftNextHeading) {
                var leftNextRect = leftNextHeading.getBoundingClientRect();
                var leftNextTop = leftScroll + leftNextRect.top;
                leftSectionHeight = leftNextTop - leftHeadingTop;
            } else {
                leftSectionHeight = (leftDoc.documentElement.scrollHeight || leftDoc.body.scrollHeight) - leftHeadingTop;
            }

            // Calculate percentage within section
            var percentage = rightSectionHeight > 0 ? scrollInSection / rightSectionHeight : 0;

            // Apply to left section
            var targetScroll = leftHeadingTop + (percentage * leftSectionHeight);

            leftDoc.documentElement.scrollTop = targetScroll;
            leftDoc.body.scrollTop = targetScroll;
            ParallelView.lastLeft = targetScroll;

            console.log('Synced to heading:', headingId, 'section %:', (percentage * 100).toFixed(1));

            setTimeout(function() {
                ParallelView.syncing = false;
            }, 100);
        }
    };

    $(document).ready(function() {
        ParallelView.init();
    });

})();
