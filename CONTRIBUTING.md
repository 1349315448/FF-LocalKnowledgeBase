# Contributing

## Development Setup

Use Python 3.11 or newer. The runtime implementation must remain standard-library
only unless a dependency proposal is approved with portability and security
evidence.

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
```

## Change Discipline

1. Open or reference a requirement for behavior changes.
2. Write a failing test through the public CLI or module seam.
3. Implement the smallest behavior that passes it.
4. Run the full test suite and portability checks.
5. Review the actual diff for secrets, private paths, generated state, and
   product-specific coupling.

Do not add private project fixtures. Tests must use temporary directories and
synthetic repositories.

## Skills

Keep `SKILL.md` concise and use relative references. Product-specific metadata
belongs under the matching adapter directory. Run the Agent Skills validator
and the repository Skill contract tests before submitting a change.
