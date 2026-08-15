# Development agent instructions

1. Read README, feature specs and ADRs before non-trivial changes.
2. Core exclusively owns its domain model, PostgreSQL schema and `/api/v1` contracts.
3. Do not import sibling repositories or expose database credentials to consumers.
4. Write a User Story and executable Gherkin scenario before user-facing behavior.
5. Keep module, class and function docstrings factual and useful: explain contracts,
   side effects, failures, invariants and safety decisions without narrating syntax.
6. Run `make test` and relevant Docker smoke checks before declaring completion.
7. Use synthetic fixtures; never commit secrets, personal data or local AI history.
8. Commit only a completed green logical step; never push unless explicitly requested.

