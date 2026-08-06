```markdown
# debugsql Development Patterns

> Auto-generated skill from repository analysis

## Overview
This skill covers the development patterns and conventions found in the `debugsql` Python codebase. It provides guidance on file naming, import/export styles, and testing patterns, helping contributors maintain consistency and quality in their work. While no specific workflows were detected, this guide also suggests useful commands for common development tasks.

## Coding Conventions

### File Naming
- Use **snake_case** for all file names.
  - Example: `debug_utils.py`, `sql_parser.py`

### Import Style
- Prefer **relative imports** within the package.
  - Example:
    ```python
    from .utils import parse_query
    ```

### Export Style
- Use **named exports** (explicitly listing exported functions/classes).
  - Example:
    ```python
    __all__ = ['parse_query', 'DebugSQL']
    ```

### Commit Patterns
- Commit messages are freeform, often very short (average length: 3 chars).
  - Example:
    ```
    fix
    upd
    add
    ```

## Workflows

_No explicit workflows detected in the repository. Below are suggested workflows for common development tasks._

### Running Tests
**Trigger:** When you want to verify code correctness.
**Command:** `/run-tests`

1. Identify test files (pattern: `*.test.*`).
2. Run tests using your preferred Python test runner (e.g., `pytest` or `unittest`).
   - Example:
     ```bash
     pytest
     ```
3. Review test results for failures or errors.

### Adding a New Module
**Trigger:** When you need to add new functionality.
**Command:** `/add-module`

1. Create a new Python file using snake_case naming.
2. Implement your functions/classes.
3. Use relative imports to reference other modules.
4. Add your exports to the `__all__` list if applicable.
5. Write corresponding test files following the `*.test.*` pattern.

### Writing a Test
**Trigger:** When adding or updating code that requires testing.
**Command:** `/write-test`

1. Create a test file named with the pattern `module_name.test.py`.
2. Write test functions using your preferred testing framework.
   - Example:
     ```python
     def test_parse_query():
         assert parse_query("SELECT 1") == expected_result
     ```
3. Run tests to ensure correctness.

## Testing Patterns

- **Test File Pattern:** Files are named using the pattern `*.test.*` (e.g., `sql_parser.test.py`).
- **Framework:** Not explicitly specified; use your preferred Python testing framework (e.g., `pytest`, `unittest`).
- **Test Example:**
  ```python
  def test_example():
      assert some_function() == expected_value
  ```

## Commands

| Command        | Purpose                                 |
|----------------|-----------------------------------------|
| /run-tests     | Run all test files in the codebase      |
| /add-module    | Add a new module following conventions  |
| /write-test    | Create and run a new test file          |
```