# Security Policy

## Supported development line

CAD Agent does not currently publish a supported production release series. Security
maintenance targets the latest main development line. Historical branches, stale pull
request heads, and superseded evidence snapshots are not supported release lines.

## Reporting a vulnerability

Do not post exploit details, secrets, private/customer CAD data, authentication material,
or a sensitive reproduction in a public Issue, pull request, discussion, or log.

Use GitHub Private Vulnerability Reporting when that private repository channel is
available. If it is not available, contact the repository owner `@duongchi90` without
sensitive details to establish a private reporting channel before sharing the report.

A useful private report includes the affected exact commit, affected boundary, expected
versus observed behavior, minimal non-sensitive reproduction when possible, and whether
any secret/private/customer material may have been exposed.

## Security boundaries

Treat findings involving path containment, symlink/reparse handling, File-IPC trust,
authorization/replay, candidate or publication mutation, evidence/hash currentness,
secret disclosure, or unsafe file replacement as security-sensitive until independently
reviewed.

Never treat `SKIP`, `NOT RUN`, stale evidence, or a non-matching commit as security PASS.
