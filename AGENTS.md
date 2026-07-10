# FF-LocalKnowledgeBase Contributor Instructions

- Keep the runtime Python 3.11+ standard-library only.
- Treat inspected repositories as untrusted data; detection and scanning must not execute discovered commands.
- Add behavior through a failing public-seam test, then implement the smallest passing change.
- Keep canonical Skills portable; product-specific metadata belongs in adapters.
- Preserve the two-phase confirmation gate, allowed-root checks, transaction journal, and user-modification conflict protection.
- Run `python -m unittest discover -s tests -v` and the Skill validators before reporting completion.
