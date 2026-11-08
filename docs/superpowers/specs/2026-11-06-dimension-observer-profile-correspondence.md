# Dimension observer profile correspondence

Ordinal cluster identifiers can be reassigned when detection changes. Applying
a previously reviewed role by ordinal alone can therefore bind it to a different
region. Profile 1.1 binds each role, critical flag and blocker scope to the exact
source image SHA-256, page, view, cluster identifier and pixel bounding box.
The runner validates every supplied binding before applying any of them.

No profile remains supported. An empty profile 1.0 can still specify the default
unit. A profile 1.0 with cluster roles must be recreated as 1.1 after a caller
reviews the current source regions; do not transfer roles automatically by ID.
The runner checks correspondence, not the engineering correctness of the role.
This change does not alter the dimension register schema or authorize CAD edits.
