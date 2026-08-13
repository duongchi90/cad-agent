; Canonical File IPC dispatcher for the repository-owned Python client.
; Python owns root validation, request identity, polling, transport, and cleanup.
(vl-load-com)

(setq *mcp-max-json-bytes* 1048576)
(setq *mcp-request-prefix* "autocad_mcp_cmd_")
(setq *mcp-result-prefix* "autocad_mcp_result_")

(setq *mcp-error-root* "IPC_ROOT_INVALID")
(setq *mcp-error-missing* "IPC_REQUEST_MISSING")
(setq *mcp-error-ambiguous* "IPC_REQUEST_AMBIGUOUS")
(setq *mcp-error-request* "IPC_REQUEST_INVALID")
(setq *mcp-error-request-id* "IPC_REQUEST_ID_INVALID")
(setq *mcp-error-oversized* "IPC_REQUEST_OVERSIZED")
(setq *mcp-error-json* "IPC_JSON_INVALID")
(setq *mcp-error-command* "IPC_COMMAND_UNSUPPORTED")
(setq *mcp-error-failed* "IPC_COMMAND_FAILED")
(setq *mcp-error-result-conflict* "IPC_RESULT_CONFLICT")

(defun mcp-string-prefix-p (prefix value / n)
  (setq n (strlen prefix))
  (and (>= (strlen value) n) (= (substr value 1 n) prefix))
)

(defun mcp-string-suffix-p (suffix value / n m)
  (setq n (strlen suffix)
        m (strlen value))
  (and (>= m n) (= (substr value (+ (- m n) 1) n) suffix))
)

(defun mcp-root-valid-p (root)
  (and
    (= (type root) 'STR)
    (> (strlen root) 0)
    (vl-file-directory-p root)
  )
)

(defun mcp-path (root name)
  (strcat root "/" name)
)

(defun mcp-hex-char-p (ch / code)
  (setq code (ascii ch))
  (or
    (and (>= code 48) (<= code 57))
    (and (>= code 65) (<= code 70))
    (and (>= code 97) (<= code 102))
  )
)

(defun mcp-hex-string-p (value / i ok)
  (setq i 1
        ok (= (strlen value) 12))
  (while (and ok (<= i 12))
    (if (not (mcp-hex-char-p (substr value i 1)))
      (setq ok nil)
    )
    (setq i (+ i 1))
  )
  ok
)

(defun mcp-request-id-from-name (name / id)
  (if
    (and
      (= (strlen name) 33)
      (mcp-string-prefix-p *mcp-request-prefix* name)
      (mcp-string-suffix-p ".json" name)
    )
    (progn
      (setq id (substr name 17 12))
      (if (mcp-hex-string-p id) id nil)
    )
    nil
  )
)

(defun mcp-request-candidates (root)
  (vl-directory-files root "autocad_mcp_cmd_*.json" 1)
)

(defun mcp-request-part-candidates (root)
  (vl-directory-files root "autocad_mcp_cmd_*.json.part" 1)
)

(defun mcp-result-part-candidates (root)
  (vl-directory-files root "autocad_mcp_result_*.json.part" 1)
)

(defun mcp-file-size-valid-p (path / size)
  (setq size (vl-file-size path))
  (and size (<= size *mcp-max-json-bytes*))
)

(defun mcp-join-lines (lines / out first)
  (setq out ""
        first T)
  (foreach item lines
    (if first
      (setq first nil)
      (setq out (strcat out "\n"))
    )
    (setq out (strcat out item))
  )
  out
)

(defun mcp-read-bounded-file (path / handle line pieces failed)
  (if (not (mcp-file-size-valid-p path))
    nil
    (progn
      (setq handle (open path "r")
            pieces nil
            failed nil)
      (if (not handle)
        nil
        (progn
          (setq line (vl-catch-all-apply 'read-line (list handle)))
          (while (and (not (vl-catch-all-error-p line)) line)
            (setq pieces (cons line pieces)
                  line (vl-catch-all-apply 'read-line (list handle)))
          )
          (if (vl-catch-all-error-p line) (setq failed T))
          (close handle)
          (if failed nil (mcp-join-lines (reverse pieces)))
        )
      )
    )
  )
)

(defun mcp-json-state-init (text)
  (setq *mcp-json-text* text
        *mcp-json-pos* 1
        *mcp-json-len* (strlen text))
)

(defun mcp-json-peek ()
  (if (<= *mcp-json-pos* *mcp-json-len*)
    (substr *mcp-json-text* *mcp-json-pos* 1)
    nil
  )
)

(defun mcp-json-take (/ ch)
  (setq ch (mcp-json-peek))
  (if ch (setq *mcp-json-pos* (+ *mcp-json-pos* 1)))
  ch
)

(defun mcp-json-ws-p (ch)
  (and ch (member (ascii ch) '(9 10 13 32)))
)

(defun mcp-json-skip-ws ()
  (while (mcp-json-ws-p (mcp-json-peek))
    (mcp-json-take)
  )
)

(defun mcp-json-hex-value (ch / code)
  (if ch
    (progn
      (setq code (ascii ch))
      (cond
        ((and (>= code 48) (<= code 57)) (- code 48))
        ((and (>= code 65) (<= code 70)) (+ 10 (- code 65)))
        ((and (>= code 97) (<= code 102)) (+ 10 (- code 97)))
        (T nil)
      )
    )
    nil
  )
)

(defun mcp-json-unicode-char (/ i digit code ok)
  (setq i 0
        code 0
        ok T)
  (while (and ok (< i 4))
    (setq digit (mcp-json-hex-value (mcp-json-take)))
    (if (numberp digit)
      (setq code (+ (* code 16) digit))
      (setq ok nil)
    )
    (setq i (+ i 1))
  )
  (if
    (and ok (> code 0) (<= code 65536) (not (and (>= code 55296) (<= code 57343))))
    (chr code)
    nil
  )
)

(defun mcp-json-parse-string (/ ch esc out done ok decoded)
  (setq out ""
        done nil
        ok (= (mcp-json-take) "\""))
  (while (and ok (not done))
    (setq ch (mcp-json-take))
    (cond
      ((not ch) (setq ok nil))
      ((= ch "\"") (setq done T))
      ((< (ascii ch) 32) (setq ok nil))
      ((= ch "\\")
        (setq esc (mcp-json-take))
        (cond
          ((member esc '("\"" "\\" "/")) (setq out (strcat out esc)))
          ((= esc "b") (setq out (strcat out (chr 8))))
          ((= esc "f") (setq out (strcat out (chr 12))))
          ((= esc "n") (setq out (strcat out (chr 10))))
          ((= esc "r") (setq out (strcat out (chr 13))))
          ((= esc "t") (setq out (strcat out (chr 9))))
          ((= esc "u")
            (setq decoded (mcp-json-unicode-char))
            (if decoded
              (setq out (strcat out decoded))
              (setq ok nil)
            )
          )
          (T (setq ok nil))
        )
      )
      (T (setq out (strcat out ch)))
    )
  )
  (if (and ok done) (list T out) nil)
)

(defun mcp-json-digit-p (ch / code)
  (if ch
    (progn
      (setq code (ascii ch))
      (and (>= code 48) (<= code 57))
    )
    nil
  )
)

(defun mcp-json-nonzero-digit-p (ch / code)
  (if ch
    (progn
      (setq code (ascii ch))
      (and (>= code 49) (<= code 57))
    )
    nil
  )
)

(defun mcp-json-scan-digits (/ start)
  (setq start *mcp-json-pos*)
  (while (mcp-json-digit-p (mcp-json-peek))
    (mcp-json-take)
  )
  (> *mcp-json-pos* start)
)

(defun mcp-json-parse-number (/ start ch is-real token ok)
  (setq start *mcp-json-pos*
        is-real nil
        ok T)
  (if (= (mcp-json-peek) "-") (mcp-json-take))
  (setq ch (mcp-json-peek))
  (cond
    ((= ch "0") (mcp-json-take))
    ((mcp-json-nonzero-digit-p ch) (mcp-json-scan-digits))
    (T (setq ok nil))
  )
  (if (and ok (= (mcp-json-peek) "."))
    (progn
      (setq is-real T)
      (mcp-json-take)
      (if (not (mcp-json-scan-digits)) (setq ok nil))
    )
  )
  (setq ch (mcp-json-peek))
  (if (and ok ch (member ch '("e" "E")))
    (progn
      (setq is-real T)
      (mcp-json-take)
      (setq ch (mcp-json-peek))
      (if (and ch (member ch '("+" "-"))) (mcp-json-take))
      (if (not (mcp-json-scan-digits)) (setq ok nil))
    )
  )
  (if ok
    (progn
      (setq token (substr *mcp-json-text* start (- *mcp-json-pos* start)))
      (if is-real
        (list T (atof token))
        (list T (atoi token))
      )
    )
    nil
  )
)

(defun mcp-json-literal (token value / n)
  (setq n (strlen token))
  (if (= (substr *mcp-json-text* *mcp-json-pos* n) token)
    (progn
      (setq *mcp-json-pos* (+ *mcp-json-pos* n))
      (list T value)
    )
    nil
  )
)

(defun mcp-json-parse-array (/ items item done ok ch)
  (setq items nil
        done nil
        ok (= (mcp-json-take) "["))
  (mcp-json-skip-ws)
  (if (= (mcp-json-peek) "]")
    (progn
      (mcp-json-take)
      (setq done T)
    )
  )
  (while (and ok (not done))
    (setq item (mcp-json-parse-value))
    (if item
      (setq items (cons (cadr item) items))
      (setq ok nil)
    )
    (if ok
      (progn
        (mcp-json-skip-ws)
        (setq ch (mcp-json-take))
        (cond
          ((= ch "]") (setq done T))
          ((= ch ",") (mcp-json-skip-ws))
          (T (setq ok nil))
        )
      )
    )
  )
  (if (and ok done) (list T (cons 'MCP_JSON_ARRAY (reverse items))) nil)
)

(defun mcp-json-parse-object (/ pairs key colon value done ok ch)
  (setq pairs nil
        done nil
        ok (= (mcp-json-take) "{"))
  (mcp-json-skip-ws)
  (if (= (mcp-json-peek) "}")
    (progn
      (mcp-json-take)
      (setq done T)
    )
  )
  (while (and ok (not done))
    (if (= (mcp-json-peek) "\"")
      (setq key (mcp-json-parse-string))
      (setq key nil)
    )
    (if
      (and key (not (assoc (cadr key) pairs)))
      (progn
        (mcp-json-skip-ws)
        (setq colon (mcp-json-take))
        (if (= colon ":")
          (progn
            (mcp-json-skip-ws)
            (setq value (mcp-json-parse-value))
            (if value
              (setq pairs (cons (cons (cadr key) (cadr value)) pairs))
              (setq ok nil)
            )
          )
          (setq ok nil)
        )
      )
      (setq ok nil)
    )
    (if ok
      (progn
        (mcp-json-skip-ws)
        (setq ch (mcp-json-take))
        (cond
          ((= ch "}") (setq done T))
          ((= ch ",") (mcp-json-skip-ws))
          (T (setq ok nil))
        )
      )
    )
  )
  (if (and ok done) (list T (cons 'MCP_JSON_OBJECT (reverse pairs))) nil)
)

(defun mcp-json-parse-value (/ ch)
  (mcp-json-skip-ws)
  (setq ch (mcp-json-peek))
  (cond
    ((= ch "\"") (mcp-json-parse-string))
    ((= ch "{") (mcp-json-parse-object))
    ((= ch "[") (mcp-json-parse-array))
    ((or (= ch "-") (mcp-json-digit-p ch)) (mcp-json-parse-number))
    ((= ch "t") (mcp-json-literal "true" 'MCP_JSON_TRUE))
    ((= ch "f") (mcp-json-literal "false" 'MCP_JSON_FALSE))
    ((= ch "n") (mcp-json-literal "null" 'MCP_JSON_NULL))
    (T nil)
  )
)

(defun mcp-json-parse-document (text / value)
  (mcp-json-state-init text)
  (setq value (mcp-json-parse-value))
  (mcp-json-skip-ws)
  (if (and value (> *mcp-json-pos* *mcp-json-len*))
    value
    nil
  )
)

(defun mcp-json-object-p (value)
  (and (listp value) (= (car value) 'MCP_JSON_OBJECT))
)

(defun mcp-json-array-p (value)
  (and (listp value) (= (car value) 'MCP_JSON_ARRAY))
)

(defun mcp-json-get (object key / pair)
  (if (mcp-json-object-p object)
    (progn
      (setq pair (assoc key (cdr object)))
      (if pair (cdr pair) nil)
    )
    nil
  )
)

(defun mcp-json-object-keys (object / out)
  (setq out nil)
  (if (mcp-json-object-p object)
    (foreach pair (cdr object)
      (setq out (cons (car pair) out))
    )
  )
  (reverse out)
)

(defun mcp-request-object-valid-p (request / keys id command params)
  (setq keys (mcp-json-object-keys request)
        id (mcp-json-get request "request_id")
        command (mcp-json-get request "command")
        params (mcp-json-get request "params"))
  (and
    (mcp-json-object-p request)
    (= (length keys) 3)
    (member "request_id" keys)
    (member "command" keys)
    (member "params" keys)
    (= (type id) 'STR)
    (= (type command) 'STR)
    (mcp-json-object-p params)
  )
)

(defun mcp-hex-digit (value)
  (substr "0123456789ABCDEF" (+ value 1) 1)
)

(defun mcp-hex-byte (value)
  (strcat (mcp-hex-digit (fix (/ value 16))) (mcp-hex-digit (rem value 16)))
)

(defun mcp-json-escape (value / i ch code out)
  (setq i 1
        out "")
  (while (<= i (strlen value))
    (setq ch (substr value i 1)
          code (ascii ch))
    (cond
      ((= ch "\"") (setq out (strcat out "\\\"")))
      ((= ch "\\") (setq out (strcat out "\\\\")))
      ((= code 8) (setq out (strcat out "\\b")))
      ((= code 9) (setq out (strcat out "\\t")))
      ((= code 10) (setq out (strcat out "\\n")))
      ((= code 12) (setq out (strcat out "\\f")))
      ((= code 13) (setq out (strcat out "\\r")))
      ((< code 32) (setq out (strcat out "\\u00" (mcp-hex-byte code))))
      (T (setq out (strcat out ch)))
    )
    (setq i (+ i 1))
  )
  out
)

(defun mcp-json-encode-number (value)
  (if (= (type value) 'INT)
    (itoa value)
    (vl-princ-to-string value)
  )
)

(defun mcp-json-encode-array (items / out first)
  (setq out "["
        first T)
  (foreach value items
    (if first
      (setq first nil)
      (setq out (strcat out ","))
    )
    (setq out (strcat out (mcp-json-encode value)))
  )
  (strcat out "]")
)

(defun mcp-json-encode-object (pairs / out first)
  (setq out "{"
        first T)
  (foreach pair pairs
    (if first
      (setq first nil)
      (setq out (strcat out ","))
    )
    (setq out
      (strcat
        out
        "\""
        (mcp-json-escape (car pair))
        "\":"
        (mcp-json-encode (cdr pair))
      )
    )
  )
  (strcat out "}")
)

(defun mcp-json-encode (value)
  (cond
    ((= value 'MCP_JSON_TRUE) "true")
    ((= value 'MCP_JSON_FALSE) "false")
    ((= value 'MCP_JSON_NULL) "null")
    ((mcp-json-object-p value) (mcp-json-encode-object (cdr value)))
    ((mcp-json-array-p value) (mcp-json-encode-array (cdr value)))
    ((= (type value) 'STR) (strcat "\"" (mcp-json-escape value) "\""))
    ((member (type value) '(INT REAL)) (mcp-json-encode-number value))
    ((= value T) "true")
    ((not value) "null")
    ((listp value) (mcp-json-encode-array value))
    (T "null")
  )
)

(defun mcp-object (pairs)
  (cons 'MCP_JSON_OBJECT pairs)
)

(defun mcp-array (items)
  (cons 'MCP_JSON_ARRAY items)
)

(defun mcp-success (request-id payload)
  (mcp-object
    (list
      (cons "request_id" request-id)
      (cons "ok" 'MCP_JSON_TRUE)
      (cons "payload" payload)
    )
  )
)

(defun mcp-failure (request-id code)
  (mcp-object
    (list
      (cons "request_id" request-id)
      (cons "ok" 'MCP_JSON_FALSE)
      (cons "error" code)
    )
  )
)

(defun mcp-write-result (root request-id envelope / final part handle encoded renamed)
  (setq final (mcp-path root (strcat *mcp-result-prefix* request-id ".json"))
        part (mcp-path root (strcat *mcp-result-prefix* request-id ".json.part")))
  (if (or (vl-file-size final) (vl-file-size part))
    nil
    (progn
      (setq encoded (mcp-json-encode envelope))
      (if (> (strlen encoded) *mcp-max-json-bytes*)
        nil
        (progn
          (setq handle (open part "w"))
          (if (not handle)
            nil
            (progn
              (write-line encoded handle)
              (close handle)
              (if
                (and
                  (mcp-file-size-valid-p part)
                  (setq renamed (vl-file-rename part final))
                )
                renamed
                nil
              )
            )
          )
        )
      )
    )
  )
)

(defun mcp-param (params key)
  (mcp-json-get params key)
)

(defun mcp-valid-handle-p (value / i ok)
  (setq ok (and (= (type value) 'STR) (> (strlen value) 0))
        i 1)
  (while (and ok (<= i (strlen value)))
    (if (not (mcp-hex-char-p (substr value i 1)))
      (setq ok nil)
    )
    (setq i (+ i 1))
  )
  ok
)

(defun mcp-entity-from-handle (value)
  (if (mcp-valid-handle-p value) (handent value) nil)
)

(defun mcp-vla-point (x y)
  (vlax-3d-point (list x y 0.0))
)

(defun mcp-set-layer-if-present (object params / layer)
  (setq layer (mcp-param params "layer"))
  (if (= (type layer) 'STR)
    (vla-put-Layer object layer)
  )
  object
)

(defun mcp-entity-record (ename / data type handle layer)
  (setq data (entget ename)
        type (cdr (assoc 0 data))
        handle (cdr (assoc 5 data))
        layer (cdr (assoc 8 data)))
  (mcp-object
    (list
      (cons "type" type)
      (cons "handle" handle)
      (cons "layer" layer)
    )
  )
)

(defun mcp-op-ping (params)
  (mcp-object (list (cons "ready" 'MCP_JSON_TRUE)))
)

(defun mcp-op-entity-list (params / layer filter set index ename entities)
  (setq layer (mcp-param params "layer")
        filter (if (= (type layer) 'STR) (list (cons 8 layer)) nil)
        set (if filter (ssget "_X" filter) (ssget "_X"))
        entities nil)
  (if set
    (progn
      (setq index 0)
      (while (< index (sslength set))
        (setq ename (ssname set index)
              entities (cons (mcp-entity-record ename) entities)
              index (+ index 1))
      )
    )
  )
  (mcp-object (list (cons "entities" (mcp-array (reverse entities)))))
)

(defun mcp-op-drawing-open (params / path docs doc)
  (setq path (mcp-param params "path"))
  (if (not (= (type path) 'STR))
    (mcp-object nil)
    (progn
      (setq docs (vla-get-Documents (vlax-get-acad-object))
            doc (vla-Open docs path))
      (vla-Activate doc)
      (mcp-object (list (cons "path" path)))
    )
  )
)

(defun mcp-op-drawing-save (params / path doc)
  (setq path (mcp-param params "path")
        doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (if (= (type path) 'STR)
    (vla-SaveAs doc path)
    (vla-Save doc)
  )
  (mcp-object nil)
)

(defun mcp-op-drawing-close (params)
  ; Close only after the bound success envelope is durably committed.
  (mcp-object nil)
)

(defun mcp-op-drawing-list-open-paths (params / docs paths)
  (setq docs (vla-get-Documents (vlax-get-acad-object))
        paths nil)
  (vlax-for doc docs
    (setq paths (cons (vla-get-FullName doc) paths))
  )
  (mcp-object (list (cons "paths" (mcp-array (reverse paths)))))
)

(defun mcp-op-drawing-save-as-dxf (params / path doc)
  (setq path (mcp-param params "path")
        doc (vla-get-ActiveDocument (vlax-get-acad-object)))
  (if (not (= (type path) 'STR))
    (mcp-object nil)
    (progn
      (vla-SaveAs doc path)
      (mcp-object nil)
    )
  )
)

(defun mcp-variable-name-p (name / i ch code ok)
  (setq ok (and (= (type name) 'STR) (> (strlen name) 0) (<= (strlen name) 64))
        i 1)
  (while (and ok (<= i (strlen name)))
    (setq ch (substr name i 1)
          code (ascii ch))
    (if
      (not
        (or
          (and (>= code 48) (<= code 57))
          (and (>= code 65) (<= code 90))
          (and (>= code 97) (<= code 122))
          (= ch "_")
        )
      )
      (setq ok nil)
    )
    (setq i (+ i 1))
  )
  ok
)

(defun mcp-split-semicolon (value / out start index ch)
  (setq out nil
        start 1
        index 1)
  (while (<= index (+ (strlen value) 1))
    (setq ch (if (<= index (strlen value)) (substr value index 1) ";"))
    (if (= ch ";")
      (progn
        (setq out (cons (substr value start (- index start)) out)
              start (+ index 1))
      )
    )
    (setq index (+ index 1))
  )
  (reverse out)
)

(defun mcp-runtime-value (value)
  (cond
    ((= value T) 'MCP_JSON_TRUE)
    ((not value) 'MCP_JSON_NULL)
    ((= (type value) 'STR) value)
    ((member (type value) '(INT REAL)) value)
    ((listp value) (mcp-array value))
    (T (vl-princ-to-string value))
  )
)

(defun mcp-op-drawing-get-variables (params / names-str names pairs valid)
  (setq names-str (mcp-param params "names_str")
        pairs nil
        valid (= (type names-str) 'STR))
  (if valid
    (progn
      (setq names (mcp-split-semicolon names-str))
      (foreach name names
        (if (mcp-variable-name-p name)
          (setq pairs (cons (cons name (mcp-runtime-value (getvar name))) pairs))
          (setq valid nil)
        )
      )
    )
  )
  (if valid (mcp-object (reverse pairs)) (mcp-object nil))
)

(defun mcp-op-block-get-attributes (params / ename object attrs index upper attr pairs)
  (setq ename (mcp-entity-from-handle (mcp-param params "entity_id"))
        pairs nil)
  (if ename
    (progn
      (setq object (vlax-ename->vla-object ename)
            attrs (vlax-variant-value (vla-GetAttributes object))
            index 0
            upper (vlax-safearray-get-u-bound attrs 1))
      (while (<= index upper)
        (setq attr (vlax-safearray-get-element attrs index)
              pairs
                (cons
                  (cons (vla-get-TagString attr) (vla-get-TextString attr))
                  pairs
                )
              index (+ index 1))
      )
    )
  )
  (mcp-object (list (cons "attributes" (mcp-object (reverse pairs)))))
)

(defun mcp-op-block-update-attribute (params / ename object attrs index upper attr tag value)
  (setq ename (mcp-entity-from-handle (mcp-param params "entity_id"))
        tag (mcp-param params "tag")
        value (mcp-param params "value"))
  (if (and ename (= (type tag) 'STR) (= (type value) 'STR))
    (progn
      (setq object (vlax-ename->vla-object ename)
            attrs (vlax-variant-value (vla-GetAttributes object))
            index 0
            upper (vlax-safearray-get-u-bound attrs 1))
      (while (<= index upper)
        (setq attr (vlax-safearray-get-element attrs index))
        (if (= (strcase (vla-get-TagString attr)) (strcase tag))
          (vla-put-TextString attr value)
        )
        (setq index (+ index 1))
      )
    )
  )
  (mcp-object nil)
)

(defun mcp-angle-degrees (value)
  (* value (/ 180.0 pi))
)

(defun mcp-op-entity-get (params / ename data type pairs)
  (setq ename (mcp-entity-from-handle (mcp-param params "entity_id")))
  (if (not ename)
    (mcp-object nil)
    (progn
      (setq data (entget ename)
            type (cdr (assoc 0 data))
            pairs
              (list
                (cons "handle" (cdr (assoc 5 data)))
                (cons "type" type)
                (cons "layer" (cdr (assoc 8 data)))
              ))
      (cond
        ((= type "LINE")
          (setq pairs
            (append pairs
              (list
                (cons "start" (mcp-array (cdr (assoc 10 data))))
                (cons "end" (mcp-array (cdr (assoc 11 data))))
              )
            )
          )
        )
        ((= type "CIRCLE")
          (setq pairs
            (append pairs
              (list
                (cons "center" (mcp-array (cdr (assoc 10 data))))
                (cons "radius" (cdr (assoc 40 data)))
              )
            )
          )
        )
        ((= type "ARC")
          (setq pairs
            (append pairs
              (list
                (cons "center" (mcp-array (cdr (assoc 10 data))))
                (cons "radius" (cdr (assoc 40 data)))
                (cons "start_angle_deg" (mcp-angle-degrees (cdr (assoc 50 data))))
                (cons "end_angle_deg" (mcp-angle-degrees (cdr (assoc 51 data))))
              )
            )
          )
        )
        ((member type '("TEXT" "MTEXT"))
          (setq pairs
            (append pairs
              (list
                (cons "insert" (mcp-array (cdr (assoc 10 data))))
                (cons "content" (cdr (assoc 1 data)))
              )
            )
          )
        )
      )
      (mcp-object pairs)
    )
  )
)

(defun mcp-op-entity-erase (params / ename object)
  (setq ename (mcp-entity-from-handle (mcp-param params "entity_id")))
  (if ename
    (progn
      (setq object (vlax-ename->vla-object ename))
      (vla-Delete object)
    )
  )
  (mcp-object nil)
)

(defun mcp-op-create-line (params / object model)
  (setq model (vla-get-ModelSpace (vla-get-ActiveDocument (vlax-get-acad-object)))
        object
          (vla-AddLine
            model
            (mcp-vla-point (mcp-param params "x1") (mcp-param params "y1"))
            (mcp-vla-point (mcp-param params "x2") (mcp-param params "y2"))
          ))
  (mcp-set-layer-if-present object params)
  (mcp-object
    (list
      (cons "entity_type" "LINE")
      (cons "handle" (vla-get-Handle object))
    )
  )
)

(defun mcp-op-create-circle (params / object model)
  (setq model (vla-get-ModelSpace (vla-get-ActiveDocument (vlax-get-acad-object)))
        object
          (vla-AddCircle
            model
            (mcp-vla-point (mcp-param params "cx") (mcp-param params "cy"))
            (mcp-param params "radius")
          ))
  (mcp-set-layer-if-present object params)
  (mcp-object
    (list
      (cons "entity_type" "CIRCLE")
      (cons "handle" (vla-get-Handle object))
    )
  )
)

(defun mcp-degrees-radians (value)
  (* value (/ pi 180.0))
)

(defun mcp-op-create-arc (params / object model)
  (setq model (vla-get-ModelSpace (vla-get-ActiveDocument (vlax-get-acad-object)))
        object
          (vla-AddArc
            model
            (mcp-vla-point (mcp-param params "cx") (mcp-param params "cy"))
            (mcp-param params "radius")
            (mcp-degrees-radians (mcp-param params "start_angle"))
            (mcp-degrees-radians (mcp-param params "end_angle"))
          ))
  (mcp-set-layer-if-present object params)
  (mcp-object
    (list
      (cons "entity_type" "ARC")
      (cons "handle" (vla-get-Handle object))
    )
  )
)

(defun mcp-op-create-text (params / object model height rotation)
  (setq model (vla-get-ModelSpace (vla-get-ActiveDocument (vlax-get-acad-object)))
        height (mcp-param params "height")
        rotation (mcp-param params "rotation"))
  (if (not (member (type height) '(INT REAL))) (setq height 1.0))
  (setq object
    (vla-AddText
      model
      (mcp-param params "text")
      (mcp-vla-point (mcp-param params "x") (mcp-param params "y"))
      height
    )
  )
  (if (member (type rotation) '(INT REAL))
    (vla-put-Rotation object (mcp-degrees-radians rotation))
  )
  (mcp-set-layer-if-present object params)
  (mcp-object
    (list
      (cons "entity_type" "TEXT")
      (cons "handle" (vla-get-Handle object))
    )
  )
)

(defun mcp-dispatch-command (operation params / result)
  (cond
    ((= operation "ping") (vl-catch-all-apply 'mcp-op-ping (list params)))
    ((= operation "entity-list") (vl-catch-all-apply 'mcp-op-entity-list (list params)))
    ((= operation "drawing-open") (vl-catch-all-apply 'mcp-op-drawing-open (list params)))
    ((= operation "drawing-save") (vl-catch-all-apply 'mcp-op-drawing-save (list params)))
    ((= operation "drawing-close") (vl-catch-all-apply 'mcp-op-drawing-close (list params)))
    ((= operation "drawing-list-open-paths") (vl-catch-all-apply 'mcp-op-drawing-list-open-paths (list params)))
    ((= operation "drawing-save-as-dxf") (vl-catch-all-apply 'mcp-op-drawing-save-as-dxf (list params)))
    ((= operation "drawing-get-variables") (vl-catch-all-apply 'mcp-op-drawing-get-variables (list params)))
    ((= operation "block-get-attributes") (vl-catch-all-apply 'mcp-op-block-get-attributes (list params)))
    ((= operation "block-update-attribute") (vl-catch-all-apply 'mcp-op-block-update-attribute (list params)))
    ((= operation "entity-get") (vl-catch-all-apply 'mcp-op-entity-get (list params)))
    ((= operation "entity-erase") (vl-catch-all-apply 'mcp-op-entity-erase (list params)))
    ((= operation "create-line") (vl-catch-all-apply 'mcp-op-create-line (list params)))
    ((= operation "create-circle") (vl-catch-all-apply 'mcp-op-create-circle (list params)))
    ((= operation "create-arc") (vl-catch-all-apply 'mcp-op-create-arc (list params)))
    ((= operation "create-text") (vl-catch-all-apply 'mcp-op-create-text (list params)))
    (T 'MCP_COMMAND_UNSUPPORTED_SENTINEL)
  )
)

(defun mcp-dispatch-core (root request-name / request-id request-path request-text parsed request params command result envelope final-path part-path)
  (setq request-id (mcp-request-id-from-name request-name))
  (if (not request-id)
    (list nil *mcp-error-request-id*)
    (progn
      (setq request-path (mcp-path root request-name))
      (if (not (mcp-file-size-valid-p request-path))
        (list request-id *mcp-error-oversized*)
        (progn
          (setq request-text (mcp-read-bounded-file request-path))
          (if (not request-text)
            (list request-id *mcp-error-request*)
            (progn
              (setq parsed (mcp-json-parse-document request-text))
              (if (not parsed)
                (list request-id *mcp-error-json*)
                (progn
                  (setq request (cadr parsed))
                  (if (not (mcp-request-object-valid-p request))
                    (list request-id *mcp-error-request*)
                    (if (not (= (mcp-json-get request "request_id") request-id))
                      (list request-id *mcp-error-request-id*)
                      (progn
                        (setq final-path
                          (mcp-path root (strcat *mcp-result-prefix* request-id ".json"))
                              part-path
                          (mcp-path root (strcat *mcp-result-prefix* request-id ".json.part")))
                        (if (or (vl-file-size final-path) (vl-file-size part-path))
                          (list request-id *mcp-error-result-conflict*)
                          (progn
                            (setq command (mcp-json-get request "command")
                                  params (mcp-json-get request "params")
                                  result (mcp-dispatch-command command params))
                            (cond
                              ((= result 'MCP_COMMAND_UNSUPPORTED_SENTINEL)
                                (list request-id *mcp-error-command*)
                              )
                              ((vl-catch-all-error-p result)
                                (list request-id *mcp-error-failed*)
                              )
                              (T
                                (setq envelope (mcp-success request-id result))
                                (if (mcp-write-result root request-id envelope)
                                  (progn
                                    (if (= command "drawing-close")
                                      (vl-catch-all-apply
                                        'command-s
                                        (list
                                          "_.CLOSE"
                                          (if
                                            (=
                                              (mcp-param params "save_changes")
                                              'MCP_JSON_TRUE
                                            )
                                            "_Y"
                                            "_N"
                                          )
                                        )
                                      )
                                    )
                                    (list request-id nil)
                                  )
                                  (list request-id *mcp-error-result-conflict*)
                                )
                              )
                            )
                          )
                        )
                      )
                    )
                  )
                )
              )
            )
          )
        )
      )
    )
  )
)

(defun c:mcp-dispatch (/ root candidates request-parts result-parts request-name outcome request-id error-code)
  (setq root
    (if (boundp '*cad-agent-file-ipc-root*)
      *cad-agent-file-ipc-root*
      nil
    )
  )
  (cond
    ((not (mcp-root-valid-p root))
      (princ (strcat "\n" *mcp-error-root*))
    )
    (T
      (setq request-parts (mcp-request-part-candidates root)
            result-parts (mcp-result-part-candidates root))
      (cond
        (request-parts
          (princ (strcat "\n" *mcp-error-request*))
        )
        (result-parts
          (princ (strcat "\n" *mcp-error-result-conflict*))
        )
        (T
          (setq candidates (mcp-request-candidates root))
          (cond
            ((not candidates)
              (princ (strcat "\n" *mcp-error-missing*))
            )
            ((> (length candidates) 1)
              (princ (strcat "\n" *mcp-error-ambiguous*))
            )
            (T
              (setq request-name (car candidates)
                    outcome (mcp-dispatch-core root request-name)
                    request-id (car outcome)
                    error-code (cadr outcome))
              (if error-code
                (progn
                  (if
                    (and
                      request-id
                      (mcp-hex-string-p request-id)
                      (not
                        (vl-file-size
                          (mcp-path root (strcat *mcp-result-prefix* request-id ".json"))
                        )
                      )
                    )
                    (mcp-write-result root request-id (mcp-failure request-id error-code))
                  )
                  (princ (strcat "\n" error-code))
                )
              )
            )
          )
        )
      )
    )
  )
  (princ)
)
