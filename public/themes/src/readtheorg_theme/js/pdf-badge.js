// PDF Badge for ReadTheOrg Theme
(function() {
    'use strict';

    // Wait for DOM to be ready
    $(document).ready(function() {
        initPdfBadge();
    });

    function initPdfBadge() {
        // Check if badge already exists
        if ($('.pdf-badge-readtheorg').length > 0) {
            return;
        }

        // Get current page URL
        var currentUrl = window.location.pathname;

        // Check if we're on an HTML page
        if (!currentUrl.endsWith('.html')) {
            return;
        }

        // Convert to PDF path
        var pdfUrl = currentUrl.replace(/\.html$/, '.pdf');

        // Check if PDF exists
        checkPdfExists(pdfUrl, function(exists) {
            if (exists) {
                createPdfBadge(pdfUrl);
            }
        });
    }

    function createPdfBadge(pdfUrl) {
        // Create PDF badge element
        var badge = $('<a>')
            .attr('href', pdfUrl)
            .attr('target', '_blank')
            .attr('aria-label', 'Download PDF version')
            .attr('title', 'Download PDF version')
            .addClass('pdf-badge-readtheorg')
            .html('<i class="fa fa-file-pdf-o"></i> Download PDF');

        // Create a container for the badge
        var badgeContainer = $('<div>')
            .addClass('pdf-badge-container')
            .append(badge);

        // Try to find the TOC sidebar and append to bottom (use .first() to get only one)
        var toc = $('#text-table-of-contents').first();
        if (toc.length === 0) {
            toc = $('#table-of-contents').first();
        }

        if (toc.length > 0) {
            toc.append(badgeContainer);
        } else {
            // Fallback: try the sidebar
            var sidebar = $('#sidebar, .sidebar, nav').first();
            if (sidebar.length > 0) {
                sidebar.append(badgeContainer);
            }
        }
    }

    function checkPdfExists(url, callback) {
        $.ajax({
            type: 'HEAD',
            url: url,
            success: function() {
                callback(true);
            },
            error: function() {
                callback(false);
            }
        });
    }
})();
