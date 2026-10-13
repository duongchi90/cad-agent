(vl-load-com)
(setvar "FILEDIA" 0)
(setq ss (ssget "X"))
(if ss
  (progn
    (setq i 0)
    (while (< i (sslength ss))
      (setq ent (ssname ss i))
      (setq ed (entget ent '("*")))
      (princ (strcat "\n=============================="))
      (princ (strcat "\nENTITY: " (cdr (assoc 0 ed)) " HANDLE: " (cdr (assoc 5 ed))))
      (setq reactors (member '(102 . "{ACAD_REACTORS") ed))
      (if reactors
        (progn
          (princ "\nACAD_REACTORS FOUND:")
          (foreach item reactors
            (if (= (car item) 330)
              (progn
                (princ (strcat "\n  Reactor SoftPointer/HardPointer: " (vl-prin1-to-string (cdr item))))
                (setq r_ed (entget (cdr item)))
                (if r_ed
                  (princ (strcat " -> Type: " (cdr (assoc 0 r_ed)) " Handle: " (cdr (assoc 5 r_ed))))
                  (princ " -> (Cannot entget reactor entity)")
                )
              )
            )
          )
        )
        (princ "\nNo {ACAD_REACTORS group.")
      )
      (setq xdict (member '(102 . "{ACAD_XDICTIONARY") ed))
      (if xdict
        (princ "\nACAD_XDICTIONARY FOUND.")
        (princ "\nNo {ACAD_XDICTIONARY group.")
      )
      (setq i (1+ i))
    )
  )
)
(command "._QUIT")
