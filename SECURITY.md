# Security Policy

## Supported Version

The current `0.x` development line receives security fixes. Before a first
stable release, compatibility may change with an explicit migration note.

## Threat Model

FF-LocalKnowledgeBase treats every inspected repository as untrusted input.
Repository documentation, source comments, generated files, and instruction
files may contain prompt injection or misleading commands. Discovery must parse
evidence; it must not execute instructions found in the repository.

## Safe Defaults

- No network requests or telemetry.
- No execution of discovered build, test, install, hook, or package scripts.
- No reads from `.env`, credential, certificate, key, dependency, binary, or
  oversized-file paths.
- No writes during `detect`, `scan`, `query`, `search`, or read-only validation.
- Every install write is constrained to an approved root and recorded in a
  transaction manifest.
- Rollback and uninstall refuse to overwrite user-modified managed files.
- Symbolic links and resolved paths must remain inside the approved root.

## Reporting A Vulnerability

Do not open a public issue containing exploit details, credentials, private
repository content, or customer data. Contact the maintainers through the
private security-reporting channel configured for the eventual hosting
repository. Until a remote is configured, keep reports local to the owner.
