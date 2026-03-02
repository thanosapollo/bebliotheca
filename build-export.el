;; build-export.el — export multiple .org files in a single Emacs session
;;
;; Usage: emacs --batch -Q --load build-export.el -- file1.org file2.org ...
;;
;; Loads Org once, then exports every file passed as a CLI argument.
;; This avoids paying the ~1s cold-start cost per file.

(require 'org)

(dolist (file command-line-args-left)
  (unless (string= file "--")
    (condition-case err
        (let ((buf (find-file-noselect file)))
          (with-current-buffer buf
            (org-html-export-to-html))
          (kill-buffer buf)
          (message "  %s" file))
      (error
       (message "  FAILED: %s — %s" file (error-message-string err))))))

;; Prevent Emacs from trying to process remaining args as files
(setq command-line-args-left nil)
