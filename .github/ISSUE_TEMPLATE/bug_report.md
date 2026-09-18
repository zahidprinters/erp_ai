name: Bug report
about: Report a bug in ERP AI
title: '[bug]'
labels: bug
body:
  - type: markdown
    attributes:
      value: |
        Thanks for taking the time to file a bug. Please fill in the details below.
        If this is a security issue, **do not use this template** — see SECURITY.md.
  - type: textarea
    id:title
    attributes:
      label: Problem
      description: Brief description of the bug.
    validations:
      required: true
  - type: textarea
    id:steps
    attributes:
      label: Steps to reproduce
      description: |
        1. What did you do?
        2. What did you expect to happen?
        3. What actually happened?
    validations:
      required: true
  - type: textarea
    id:environment
    attributes:
      label: Environment
      description: Frappe/ERPNext version, Python version, Ollama/model (if relevant), ERP AI commit (`git rev-parse HEAD`).
      render: shell
    validations:
      required: true
  - type: textarea
    id:logs
    attributes:
      label: Logs / error output
      description: Paste relevant terminal / bench logs / traceback. Redact secrets first.
      render: shell
    validations:
      required: false
