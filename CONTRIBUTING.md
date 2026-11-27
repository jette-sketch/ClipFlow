# Contributing

This is an engineering preview. Improvements to isolated logic, docs, and offline tests are welcome.

1. Keep exactly two **inactive** n8n workflow definitions until runtime integration has been qualified.
2. Add regression tests for retry, retention, authentication, and idempotency changes.
3. Do not include `.env`, real credentials, logs, personal records, Drive IDs, database dumps, or copyrighted source media.
4. Do not enable automatic third-party publication or deletion as part of a pull request without a documented authorization gate and acceptance evidence.
5. Run `python -m unittest discover -s tests -v` before proposing changes.
