"""Allow ``python -m ff_local_knowledge`` to invoke the CLI."""

from .cli import main

raise SystemExit(main())
