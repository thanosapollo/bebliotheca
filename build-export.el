;; build-export.el — export multiple .org files in a single Emacs session
;;
;; Usage: emacs --batch -Q --load build-export.el -- file1.org file2.org ...
;;
;; Loads Org once, then exports every file passed as a CLI argument.
;; This avoids paying the ~1s cold-start cost per file.

(require 'org)

(defvar bebliotheca--export-failed nil)

(defun bebliotheca--ensure-output-directory (file)
  "Create public language directory needed to export FILE."
  (let* ((language-dir (file-name-directory (expand-file-name file)))
         (language (file-name-nondirectory (directory-file-name language-dir)))
         (content-dir (file-name-directory (directory-file-name language-dir)))
         (project-dir (file-name-directory (directory-file-name content-dir))))
    (make-directory (expand-file-name (concat "public/" language) project-dir) t)))

(defun bebliotheca--available-languages (file)
  "Return comma-separated languages having FILE's stem in content."
  (let* ((lang-dir (file-name-directory (expand-file-name file)))
         (content-dir (file-name-directory (directory-file-name lang-dir)))
         (stem (file-name-base file))
         languages)
    (dolist (language '("gr" "la" "en"))
      (when (file-exists-p
             (expand-file-name (concat language "/" stem ".org") content-dir))
        (push language languages)))
    (mapconcat #'identity (nreverse languages) ",")))

(defun bebliotheca--inject-language-metadata (html-file source-file)
  "Embed sibling-language availability in HTML-FILE for SOURCE-FILE."
  (with-temp-buffer
    (insert-file-contents html-file)
    (goto-char (point-min))
    (when (search-forward "<head>" nil t)
      (insert (format "\n<meta name=\"bebliotheca-languages\" content=\"%s\">"
                      (bebliotheca--available-languages source-file)))
      (write-region (point-min) (point-max) html-file nil 'silent))))

(dolist (file command-line-args-left)
  (unless (string= file "--")
    (condition-case err
        (let ((buf (find-file-noselect file)))
          (with-current-buffer buf
            (bebliotheca--ensure-output-directory buffer-file-name)
            (let ((html-file (org-html-export-to-html)))
              (bebliotheca--inject-language-metadata html-file buffer-file-name)))
          (kill-buffer buf)
          (message "  %s" file))
      (error
       (setq bebliotheca--export-failed t)
       (message "  FAILED: %s — %s" file (error-message-string err))))))

;; Prevent Emacs from trying to process remaining args as files
(setq command-line-args-left nil)

(when bebliotheca--export-failed
  (kill-emacs 1))
