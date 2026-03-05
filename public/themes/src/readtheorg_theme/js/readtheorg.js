function collapse_toc_elements_on_click (nav_li_a){
    /*
      When an `a' element in the TOC is clicked, its parent
      `li' element's active attribute is toggled.  This causes
      the element to toggle between minimized and maximized
      states.  The active attribute is documented in bootstrap.
      https://getbootstrap.com/docs/4.0/components/navbar/#nav
    */
    $(nav_li_a).parent().toggleClass("active");
}

$( document ).ready(function() {
    // When the document is loaded and ready, bind the
    // function `collapse_toc_elements_on_click' to the
    // `a' elements in the table of contents.
    $("#text-table-of-contents a").click(function() {
        collapse_toc_elements_on_click(this);
    });
});

$(function() {
    function replace_admonition (tag, readable) {
        $(`span.${tag}:not(#table-of-contents *)`) .parent().parent()
            .replaceWith(`<p id='${this.id}' class='admonition-title ${tag}'>${readable}</p>`);
        $(`div.${tag}`).before(`<p class='admonition-title ${tag}'>${readable}</p>`)
    }
    replace_admonition('note', 'Note');
    replace_admonition('seealso', 'See also');
    replace_admonition('warning', 'Warning');
    replace_admonition('caution', 'Caution');
    replace_admonition('attention', 'Attention');
    replace_admonition('tip', 'Tip');
    replace_admonition('important', 'Important');
    replace_admonition('hint', 'Hint');
    replace_admonition('error', 'Error');
    replace_admonition('danger', 'Danger');
});

$( document ).ready(function() {

    // MOBILE ONLY: Close menu only when clicking leaf items (items with no sub-items)
    $(document).on('click', "#text-table-of-contents a", function(e) {
      // Only apply this behavior on mobile screens
      if ($(window).width() <= 768) {
        // Check if this item has no children (no nested ul)
        var hasChildren = $(this).parent().find('ul').length > 0;

        if (hasChildren) {
          // This is a parent item - prevent navigation, just expand/collapse
          e.preventDefault();
        } else {
          // This is a leaf item - allow navigation and close the sidebar
          window.location.hash = '';
        }
      }
    });

    // MOBILE ONLY: Close sidebar when clicking outside of it
    $(document).on('click', function(e) {
      if ($(window).width() <= 768) {
        var $toc = $('#table-of-contents');
        var $toggleBtn = $('#toggle-sidebar');

        // If click is outside TOC and toggle button, close the TOC
        if (!$toc.is(e.target) && $toc.has(e.target).length === 0 &&
            !$toggleBtn.is(e.target) && $toggleBtn.has(e.target).length === 0) {
          window.location.hash = '';
        }
      }
    });

    // Make tables responsive
    $("table.docutils:not(.field-list)").wrap("<div class='wy-table-responsive'></div>");
});

$( document ).ready(function() {
    // Theme init: apply saved theme immediately to prevent flash
    var savedTheme = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);

    $('#text-table-of-contents ul').first().addClass('nav');
                                        // ScrollSpy also requires that we use
                                        // a Bootstrap nav component.
    $('body').scrollspy({target: '#text-table-of-contents'});

    // set the height of tableOfContents
    var $postamble = $('#postamble');
    var $tableOfContents = $('#table-of-contents');
    $tableOfContents.css({paddingBottom: $postamble.outerHeight()});

    // add TOC button
    var toggleSidebar = $('<div id="toggle-sidebar"><a href="#table-of-contents"><h2>Table Of Contents</h2></a></div>');
    $('#content').prepend(toggleSidebar);

    // add close button when sidebar showed in mobile screen
    var closeBtn = $('<a class="close-sidebar" href="#">Close</a>');
    var tocTitle = $('#table-of-contents').find('h2');
    tocTitle.append(closeBtn);

    // add button container after title
    var buttonContainer = $('<div id="toc-buttons"></div>');
    tocTitle.after(buttonContainer);

    // add TOC hide button
    var tocHideBtn = $('<button id="toc-hide-btn">◀</button>');
    buttonContainer.append(tocHideBtn);

    // add font selector
    var fontSelect = $('<select id="font-selector"></select>');
    fontSelect.append('<option value="sans">Sans-serif</option>');
    fontSelect.append('<option value="serif">Serif</option>');
    fontSelect.append('<option value="noto-serif">Noto Serif</option>');
    fontSelect.append('<option value="gentium">Gentium</option>');
    fontSelect.append('<option value="monospace">Monospace</option>');

    // On desktop it sits in #toc-buttons, on mobile CSS repositions it fixed
    buttonContainer.append(fontSelect);

    // Also clone into body so mobile CSS can show it when #toc-buttons is hidden
    var fontSelectMobile = fontSelect.clone().attr('id', 'font-selector-mobile');
    $('body').append(fontSelectMobile);

    // restore saved font preference
    var savedFont = localStorage.getItem('bebliotheca_font') || 'gentium';
    $('body').attr('data-font', savedFont);
    fontSelect.val(savedFont);
    fontSelectMobile.val(savedFont);

    // sync both selectors
    function onFontChange() {
        var font = $(this).val();
        $('body').attr('data-font', font);
        localStorage.setItem('bebliotheca_font', font);
        fontSelect.val(font);
        fontSelectMobile.val(font);
    }
    fontSelect.on('change', onFontChange);
    fontSelectMobile.on('change', onFontChange);

    // add theme toggle button
    var themeBtn = $('<button id="theme-toggle-btn"></button>');
    themeBtn.text(savedTheme === 'dark' ? '\u2600' : '\u263E');
    buttonContainer.append(themeBtn);

    // mobile theme toggle
    var themeBtnMobile = $('<button id="theme-toggle-mobile"></button>');
    themeBtnMobile.text(savedTheme === 'dark' ? '\u2600' : '\u263E');
    $('body').append(themeBtnMobile);

    themeBtn.on('click', function() {
        var current = document.documentElement.getAttribute('data-theme');
        var next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
        themeBtn.text(next === 'dark' ? '\u2600' : '\u263E');
        themeBtnMobile.text(next === 'dark' ? '\u2600' : '\u263E');
    });

    themeBtnMobile.on('click', function() { themeBtn.click(); });

    // add home button independently (not in TOC)
    var homeButton = $('<a id="home-button" href="/index.html" title="Επιστροφή στην αρχική σελίδα">⌂</a>');
    $('body').append(homeButton);

    // TOC toggle functionality (desktop only)
    tocHideBtn.on('click', function() {
        // Only apply collapse behavior on desktop
        if ($(window).width() > 768) {
            var isHidden = $('body').hasClass('toc-hidden');
            $('body').toggleClass('toc-hidden');
            // Change icon based on state
            tocHideBtn.text(isHidden ? '◀' : '▶');
        }
    });

    // Handle window resize - remove toc-hidden class on mobile
    $(window).on('resize', function() {
        if ($(window).width() <= 768) {
            $('body').removeClass('toc-hidden');
            tocHideBtn.text('◀');
        }
    });
});

// Citation Feature
$(document).ready(function() {
    // Create citation popup element
    var citationPopup = $('<div id="citation-popup" style="display:none;">' +
        '<div id="citation-content"></div>' +
        '<button id="citation-copy-btn">Copy Citation</button>' +
        '<button id="citation-close-btn">×</button>' +
        '</div>');
    $('body').append(citationPopup);

    // Function to extract page metadata
    function getPageMetadata() {
        // Extract author
        var author = '';
        var authorElem = $('#postamble .author');
        if (authorElem.length > 0) {
            author = authorElem.text().replace('Author:', '').trim();
        }

        // Extract date
        var date = '';
        var dateElem = $('#postamble .date');
        if (dateElem.length > 0) {
            date = dateElem.text().replace('Created:', '').trim();
        }

        // Extract title
        var title = $('h1.title').first().text() || document.title;

        // Get URL
        var url = window.location.href;

        return {
            author: author,
            date: date,
            title: title,
            url: url
        };
    }

    // Function to format citation in APA style
    function formatAPACitation(selectedText, metadata) {
        var citation = '';

        // Author part
        if (metadata.author) {
            citation += metadata.author + '. ';
        }

        // Date part
        if (metadata.date) {
            // Try to parse and format the date
            citation += '(' + metadata.date + '). ';
        }

        // Title part
        if (metadata.title) {
            citation += metadata.title + '. ';
        }

        // URL part
        citation += 'Retrieved from ' + metadata.url;

        // Add the quoted text
        if (selectedText) {
            citation += '\n\nQuoted text: "' + selectedText + '"';
        }

        return citation;
    }

    // Function to show citation popup
    function showCitationPopup(x, y, citation) {
        $('#citation-content').text(citation);

        var $popup = $('#citation-popup');

        // Position popup
        $popup.css({
            left: x + 'px',
            top: (y + 10) + 'px',
            display: 'block'
        });

        // Ensure popup stays within viewport
        setTimeout(function() {
            var popup = $popup[0];
            var rect = popup.getBoundingClientRect();
            var viewportWidth = window.innerWidth;
            var viewportHeight = window.innerHeight;

            // Adjust horizontal position if off-screen
            if (rect.right > viewportWidth) {
                var newLeft = viewportWidth - rect.width - 20;
                $popup.css('left', Math.max(10, newLeft) + 'px');
            }

            // Adjust vertical position if off-screen
            if (rect.bottom > viewportHeight) {
                var newTop = y - rect.height - 10;
                if (newTop < 10) {
                    newTop = 10;
                }
                $popup.css('top', newTop + 'px');
            }
        }, 0);
    }

    // Function to hide citation popup
    function hideCitationPopup() {
        $('#citation-popup').hide();
    }

    // Function to handle selection (works for both mouse and touch)
    function handleSelection(e) {
        setTimeout(function() {
            var selectedText = window.getSelection().toString().trim();

            if (selectedText.length > 0) {
                var metadata = getPageMetadata();
                var citation = formatAPACitation(selectedText, metadata);

                // Get position (handle both mouse and touch events)
                var x, y;
                if (e.type === 'touchend') {
                    var touch = e.originalEvent.changedTouches[0];
                    x = touch.pageX;
                    y = touch.pageY;
                } else {
                    x = e.pageX;
                    y = e.pageY;
                }

                showCitationPopup(x, y, citation);
            } else {
                // Hide popup if no text is selected
                hideCitationPopup();
            }
        }, 10);
    }

    // Handle text selection for both mouse and touch
    $(document).on('mouseup touchend', '#content', handleSelection);

    // Copy citation to clipboard
    $('#citation-copy-btn').on('click', function() {
        var citation = $('#citation-content').text();

        // Modern clipboard API
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(citation).then(function() {
                // Visual feedback
                var originalText = $('#citation-copy-btn').text();
                $('#citation-copy-btn').text('Copied!');
                setTimeout(function() {
                    $('#citation-copy-btn').text(originalText);
                }, 1500);
            });
        } else {
            // Fallback for older browsers
            var textArea = document.createElement('textarea');
            textArea.value = citation;
            textArea.style.position = 'fixed';
            textArea.style.opacity = '0';
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                var originalText = $('#citation-copy-btn').text();
                $('#citation-copy-btn').text('Copied!');
                setTimeout(function() {
                    $('#citation-copy-btn').text(originalText);
                }, 1500);
            } catch (err) {
                console.error('Failed to copy citation:', err);
            }
            document.body.removeChild(textArea);
        }
    });

    // Close citation popup
    $('#citation-close-btn').on('click', function() {
        hideCitationPopup();
    });

    // Close popup when clicking outside
    $(document).on('click', function(e) {
        if (!$(e.target).closest('#citation-popup').length &&
            !$(e.target).closest('#content').length) {
            hideCitationPopup();
        }
    });
});
