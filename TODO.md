<details><summary>Checkmark key</summary>
### Marks:
|   | Description
|:-:| :----------
|   | Not yet completed (generic)
| x | Completed and implemented, but still relevant to the list
| + | In development (partially implemented)
| = | Development not yet started but is planned for the near future
| - | Not planned for the near future
| ~ | Partially implemented, but not planned to be worked on in the near future

### Modifiers:
|   | Description
|:-:| :----------
| % | Difficult or confusing
| . | Lowest priority
| v | Low priority
| ^ | High priority
| ! | Highest priority

Note: priorities are relative to elements in the surrounding "container":
 - if a parent is "^", then all its children are as well
 - if a parent is "^" and a child is "v", then the child is considered roughly the same priority as the elements surrounding the parent
 - if a parent is unmodified and a child is "^", then the child is considered "^" compared to the elements surrounding the parent
Note: completed elements should have no modifiers
</details>

# TODO
|   | Date added | Date updated | Description
|:-:| :--------: | :----------: | :----------
|+ ^| 2024-01-03 |  2024-01-03  | [Implement frameworks (manifest, module, plugin)](#implement-frameworks)
|= .| 2024-01-03 |  2024-01-03  | [Refactor a lot of things](#refactor-a-lot-of-things)
| + | 2024-01-03 |  2024-01-03  | Implement entrypoint @ `__entrypoint__.py`
|- v| 2024-01-03 |  2024-01-03  | [Fix docstrings](#fixup-docstrings)

## Refactor a lot of things
|   | Date added | Date updated | Description
|:-:| :--------: | :----------: | :----------
|- v| 2024-01-03 |  2024-01-03  | Refactor libraries
| - | 2024-01-03 |  2024-01-03  | - Refactor `libraries/flexispacelib.py`
| - | 2024-01-03 |  2024-01-03  | - Refactor `libraries/loglib.py`
| + | 2024-01-03 |  2024-01-05  | Refactor manifest framework
## Fix docstrings
<details>
|   | Date added | Date updated | Description
|:-:| :--------: | :----------: | :----------
| - | 2024-01-03 |  2024-01-03  | Check current module docstrings
|- ^| 2024-01-03 |  2024-01-03  | - Add missing module docstrings
| - | 2024-01-03 |  2024-01-03  | Check current class docstrings
| - | 2024-01-03 |  2024-01-03  | - Add missing class docstrings
| - | 2024-01-03 |  2024-01-03  | Check current function docstrings
| - | 2024-01-03 |  2024-01-03  | - Add missing function docstrings
</details>

## Implement frameworks
<details>
|   | Date added | Date updated | Description
|:-:| :--------: | :----------: | :----------
| + | 2024-01-03 |  2024-01-03  | [Implement manifest framework](#implement-manifest-framework)
| = | 2024-01-03 |  2024-01-03  | [Implement module framework](#implement-module-framework)
| = | 2024-01-03 |  2024-01-03  | [Implement plugin framework](#implement-plugin-framework)

### Implement manifest framework
<details>
|   | Date added | Date updated | Description
|:-:| :--------: | :----------: | :----------
|+ ^| 2024-01-03 |  2024-01-03  | Implement installation
| + | 2024-01-03 |  2024-01-03  | - Implement content diffs
|+ !| 2024-01-05 |  2024-01-05  | Write manifest documentation / specification
|+ v| 2024-01-03 |  2024-01-03  | Implement store
| x | 2024-01-03 |  2024-01-03  | - Implement base store features (file discovery and manifest download by id)
| + | 2024-01-03 |  2024-01-05  | Traditional post-implementation major rethink / refactor
| x | 2024-01-03 |  2024-01-03  | Implement basic structure and formats
| x | 2024-01-03 |  2024-01-03  | Implement signing
| x | 2024-01-03 |  2024-01-03  | - Implement key remap cascades
| x | 2024-01-03 |  2024-01-03  | Implement generation
| x | 2024-01-03 |  2024-01-03  | Implement manifest self-updating
| x | 2024-01-03 |  2024-01-03  | Implement manifest uninstallation
</details>

### Implement module framework
<details>
|   | Date added | Date updated | Description
|:-:| :--------: | :----------: | :----------
| ^ | 2024-01-03 |  2024-01-03  | Implement basic module features
|   | 2024-01-03 |  2024-01-03  | Implement relationships
|   | 2024-01-03 |  2024-01-03  | - Implement `before` and `after`
|   | 2024-01-03 |  2024-01-03  | - Implement `depends`
| v | 2024-01-03 |  2024-01-03  | Implement module store
</details>

### Implement plugin framework
<details>
|   | Date added | Date updated | Description
|:-:| :--------: | :----------: | :----------
| ^ | 2024-01-03 |  2024-01-03  | Implement basic plugin features
|   | 2024-01-03 |  2024-01-03  | Implement relationships
|   | 2024-01-03 |  2024-01-03  | - Implement `before` and `after`
|   | 2024-01-03 |  2024-01-03  | - Implement `depends`
| v | 2024-01-03 |  2024-01-03  | Implement plugin store
</details>

</details>