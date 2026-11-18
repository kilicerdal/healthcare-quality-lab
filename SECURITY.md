# Security policy and demonstration boundary

## Report a vulnerability privately

Email [erdal@eai.engineering](mailto:erdal@eai.engineering) with subject `Security: healthcare-quality-lab`. Include the affected commit/version, synthetic reproduction steps, expected and observed behavior, and likely impact. Do not put exploit details, credentials, patient information or raw sensitive traces in a public issue. Redact secrets before sending; do not email an API key.

The current default branch is the maintenance target. Historical release assets preserve their original state and are not automatically patched. There is no guaranteed response or remediation SLA.

## Runtime boundary

This is a synthetic local teaching application, not a production payer service. Bind to loopback and use invented data only. Demo actor headers and reviewer labels do not authenticate distinct humans. Do not expose the application to the internet or enter real health information.

Review gates, source hashes and transactional controls support the demonstration; they do not establish clinical validation, regulatory compliance, tamper-proof audit history or production authorization. Public source availability is not approval to deploy it with real records.

Normal tests and proof-page scenarios use authored fixtures/provider doubles and make no paid API requests. Optional live generation and the explicit evaluation CLI have separate credential, provenance and spending requirements. Keep credentials server-side/local, out of browser assets, logs, reports and Git history.

Dependency updates follow [the maintenance guide](docs/DEPENDENCY_MAINTENANCE.md). A passing test suite or automated dependency proposal is not a security certification.
