# Security Policy

`sec-capsules` is designed for authorized security work only.

Please do not report issues based on scanning third-party targets without permission. If you find a vulnerability in this project, open a private advisory or contact the maintainer through the repository security channel once available.

Default runtime behavior should remain conservative:

- Scope checks before execution
- Explicit `--execute` for real subprocess execution
- Raw artifacts hidden from model context by default
- Sensitive data redaction before observations

