# Security Policy

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Use GitHub's
[private vulnerability reporting](../../security/advisories/new) instead.
Include steps to reproduce, affected version/commit, and impact.

## Handling secrets

- Never commit `.env`. Generate keys with `sh scripts/bootstrap.sh` or
  `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
- Use distinct values for `API_KEY` (reader) and `ADMIN_KEY` (curator).
