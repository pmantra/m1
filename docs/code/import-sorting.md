# Import Sorting

## Why Sort Imports

### Improved Readability:
Sorted imports make your code easier to visually scan. When imports are
organized consistently, it's simpler to identify and locate specific modules or
functions.

See [A Foolish Consistency is the Hobgoblin of Little
Minds](https://peps.python.org/pep-0008/#a-foolish-consistency-is-the-hobgoblin-of-little-minds)
from [PEP 8](https://peps.python.org/pep-0008/#introduction) for additional
context on the balance of reading/writing code and the priority level we should
apply to improving readability.

### Reduced Cognitive Load: 
Consistent import organization makes it easier to grasp the code's structure and
dependencies. Instead of relying on search (+f), developers can quickly
decipher the code's flow and relationships.

### Enhanced Maintainability: 
Sorting imports promotes code maintainability, especially for larger projects
with many contributors. Consistent formatting provides a lower barrier of
entry for the addition of more tools, such as cyclical and directional imports.
Additionally it standardizes the expectations of code structure when opening any
source file in the project.

### Error Prevention: 
Properly sorted imports can help prevent errors related to duplicate imports or
missing modules. By grouping similar imports together, it's easier to spot
potential conflicts or omissions. Our current tools catch these issues but it is
still up to us to resolve them. Sorted imports make the resolution much more
efficient.


### Consistency with Style Guides: 
Sorting imports aligns with widely accepted style guides like PEP 8, which
provides recommendations for writing clear, maintainable, and consistent Python
code. 


# Per module configuration 

https://pycqa.github.io/isort/index.html

#### From the documentation 
> isort will traverse up to 25 parent directories until it finds a suitable config
file. Note that isort will not leave a git or Mercurial repository (checking for
a .git or .hg directory). As soon as it finds a file, it stops looking. The
config file search is done relative to the current directory if isort . or a
file stream is passed in, or relative to the first path passed in if multiple
paths are passed in. isort never merges config files together due to the
confusion it can cause.

#### Override options

https://pycqa.github.io/isort/docs/configuration/action_comments.html

If absolutely necessary the global isort configuration may be overridden by placing a `.isort.cfg` file in your module dir and applying the necessary options. This should ONLY be done if all attempts to address the issue from the global scope have been exhausted.
