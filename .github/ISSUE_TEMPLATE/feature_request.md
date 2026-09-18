name: Feature request
about: Suggest a feature for ERP AI
title: '[feature]'
labels: enhancement
body:
  - type: markdown
    attributes:
      value: |
        Thanks for the suggestion. Please describe what you want and why.
        If this is a security issue, see SECURITY.md.
  - type: textarea
    id:problem
    attributes:
      label: Problem
      description: What are you trying to do? What is hard right now?
    validations:
      required: true
  - type: textarea
    id:solution
    attributes:
      label: Proposed solution
      description: How should this work? Include example prompts/API calls if relevant.
    validations:
      required: true
  - type: textarea
    id:alternatives
    attributes:
      label: Alternatives
      description: What else did you consider?
      render: markdown
    validations:
      required: false
  - type: textarea
    id:context
    attributes:
      label: Additional context
      description: Anything else (links, related issues, security impact, etc.).
      render: markdown
    validations:
      required: false
