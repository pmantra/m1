# Python Static Analysis

## Overview

In our ongoing efforts to enhance code quality and proactively detect type-related issues during the development process, we've made the decision to introduce `mypy` as an additional static analysis tool into our Python codebase. This document provides insights into the rationale behind this choice and the advantages it offers to our project.

## Current Toolset

### `flake8`

- Our primary tool for linting, `flake8`, focuses on enforcing consistent code style and identifying common surface-level issues.
- While it can flag certain potential programming errors, it lacks the ability to perform deep introspection for correctness.

### `black`

- `black` has played a crucial role in standardizing our code formatting, resulting in a codebase that is not only uniform but also visually pleasing.
- It excels at enforcing code formatting guidelines but doesn't delve into the realm of type-related issues.

## Why Introduce `mypy`

### What is `mypy`

Mypy is a static type checker for Python that aims to combine the benefits of dynamic (or "duck") typing and static typing. Mypy combines the expressive power and convenience of Python with a powerful type system and compile-time type checking. Mypy type checks standard Python programs; run them using any Python VM with basically no runtime overhead.

### Type Safety and Early Error Detection

- Python is a dynamically typed language, which can lead to runtime errors caused by type mismatches.
- `mypy` introduces static type checking, allowing us to catch type-related
  errors at the development stage rather than during runtime.
- This improves code robustness and helps prevent subtle issues reducing the number of bugs that make it to production.
- It improves the power of our intellisense tools by providing more type information

### Improving Code Quality

- `mypy` (can) enforce type annotations, making our codebase more self-documenting
  and understandable.
- It encourages better variable naming and more explicit function signatures,
  enhancing overall code quality.

### Streamlining Collaboration and Maintenance

- With `mypy`, code contributions become more straightforward to review, as
  type-related issues are highlighted early.
- It simplifies onboarding for new team members, as they can rely on type hints
  for understanding code behavior.
- Maintenance becomes easier, as changes in one part of the codebase won't
  unknowingly affect other areas.


## Rules and Rollout

### Rollout
#### Tool Introduction
`mypy` is being introduced as a **non-blocking** step in the `pre-commit` script that runs prior to each commit. The tool will emit warnings and errors if they are discovered but will not prevent our team from operating as normal. After we have gathered feedback and worked out any configuration errors we will move `mypy` to block on error. 

#### Per-team Rollout
Each team may opt-in, at their own pace, to mypy analysis. In the `mypy.ini` file, each team may isolate the modules they own with glob patterns and adopt rules at the pace that works for them. 

### Rules
We will begin with the default rule set provided by mypy. We prioritize the value this tool provides to our teams above the specific opinions its developers made. If a particular rule is found to not match with our current or goal culture or style we should all feel empowered to open an MR to make the change. 
