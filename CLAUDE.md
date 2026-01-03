# tap-pingdom Development Guidelines

## Project Overview
This is a Singer tap for the Pingdom API, built with the Meltano Singer SDK. It extracts data from Pingdom monitoring services including checks, actions, contacts, and results.

## Technology Stack
- **Python Version**: 3.12+ (main development on 3.14)
- **Package Manager**: uv (>=0.8 required)
- **Build System**: hatchling with hatch-vcs for versioning
- **Testing**: pytest with syrupy for snapshot testing
- **Type Checking**: mypy and ty
- **Linting**: ruff with preview features enabled
- **Task Runner**: tox with uv runner

## Development Commands

### Setup and Installation
```bash
# Sync dependencies
uv sync

# Run the tap directly
uv run tap-pingdom --about --format=json
uv run tap-pingdom --discover > ./catalog.json
uv run tap-pingdom --config ENV --catalog ./catalog.json
```

### Testing
```bash
# Run all tests for a specific Python version
tox -e py314

# Run specific test files
tox -e py314 -- tests/test_core.py

# Run dependency checks
tox -e dependencies

# Run type checking
tox -e typing
```

### Meltano Integration
```bash
# Install all Meltano plugins
meltano lock --update --all

# Test the tap via Meltano
meltano invoke tap-pingdom --version

# Run ELT pipeline
meltano run tap-pingdom target-jsonl
```

## Code Style and Conventions

### Required Imports
- **CRITICAL**: All Python files MUST include `from __future__ import annotations` as the first import
- Use `TYPE_CHECKING` blocks for type-only imports to avoid circular dependencies

### Docstrings
- Use Google-style docstrings (enforced by ruff)
- Include Args, Returns, and Raises sections where applicable
- Example:
  ```python
  def get_url_params(
      self,
      context: Context | None,
      next_page_token: int | None,
  ) -> dict[str, Any]:
      """Get URL query parameters.

      Args:
          context: Stream sync context.
          next_page_token: Next offset for pagination.

      Returns:
          Mapping of URL query parameters.
      """
  ```

### Type Annotations
- Use modern type syntax: `dict[str, Any]` not `Dict[str, Any]`
- Use union syntax: `str | None` not `Optional[str]`
- Use `@override` decorator for methods that override parent class methods
- All functions should have complete type annotations

### Code Quality
- Line length: 88 characters
- Use ruff for linting (select = ["ALL"] with specific ignores)
- Tests are exempt from certain rules (see pyproject.toml per-file-ignores)

## Project Structure

### Stream Implementation
- Base class: `PingdomStream` in `tap_pingdom/client.py`
- Stream definitions: `tap_pingdom/streams.py`
- Schema utilities: `tap_pingdom/schema_utils.py` (for patching OpenAPI schemas)
- All streams inherit from `PingdomStream` which extends `singer_sdk.RESTStream`

### Schema Definitions

**OpenAPI vs Manual Schemas:**
- OpenAPI schemas loaded from `tap_pingdom/openapi/openapi.json`
- Some streams use `StreamSchema(OPENAPI_SCHEMA, key="...")` for OpenAPI-based schemas
- Many streams define schemas manually using `th.PropertiesList` - see NOTE comments in code for detailed explanations

**Why Manual Schemas Are Required:**

1. **Inline Definitions**: Most response schemas in the OpenAPI spec define item schemas inline within response wrappers (e.g., `actions_alerts_entry` contains `actions.alerts[*]` items), not as standalone reusable components that `StreamSchema` can reference.

2. **Type Mismatches**: The OpenAPI spec has incorrect types in several places:
   - **Actions**: `userid`, `checkid`, `time` defined as strings but API returns integers
   - **Actions**: `charged` defined as string but should be boolean

3. **Missing Properties**: Some schemas are incomplete:
   - **Results**: Missing `probedesc` property that API actually returns

4. **Complex Types**: Some schemas use complex `anyOf` references that may not work well with Singer SDK:
   - **Contacts**: `notification_targets` uses anyOf with multiple schema refs (SMSes, Emails, APNS, AGCM)

5. **Injected Properties**: Child streams add properties from parent context:
   - **Results**: `checkid` is injected via `post_process()` from Checks parent stream

**Streams Using OpenAPI Schemas:**
- `Checks` → `CheckWithStringType` (direct)
- `Probes` → `Probe` (direct)
- `Teams` → `AlertingTeams` (direct)
- `TMSChecks` → `CheckGeneral` (direct)
- `Contacts` → `ContactTargets` (with `effective_schema` patches)

**Streams Using Manual Schemas (with NOTE comments):**
- `Actions` (type errors + inline definition)
- `Maintenance` (inline definition + extra properties)
- `MaintenanceOccurrences` (inline definition)
- `Results` (inline definition + missing property + injected property)

**Schema Patching with `effective_schema`:**
Some streams use OpenAPI schemas but need adjustments. Instead of redefining schemas from scratch, these streams:
1. Use `StreamSchema(OPENAPI_SCHEMA, key="ComponentName")` for the base schema
2. Override the `effective_schema` property to apply patches via `apply_schema_patch()`
3. Patches can fix types, remove complex structures, or add missing properties

Example (from `Contacts` stream):
```python
from tap_pingdom.schema_utils import apply_schema_patch

class MyStream(PingdomStream):
    schema = StreamSchema(OPENAPI_SCHEMA, key="MyComponent")

    @property
    @override
    def effective_schema(self) -> dict:
        base_schema = super().effective_schema
        patches = {
            "properties": {
                "field_name": {
                    "anyOf": None,  # Remove key with None
                    "type": ["string", "null"],  # Set new type
                }
            }
        }
        return apply_schema_patch(base_schema, patches)
```

### Stream Types
Active streams (in `STREAM_TYPES`):
- `Checks`: Monitors configured in Pingdom (parent stream for Results)
- `Actions`: Alert history
- `Contacts`: Alerting contacts
- `Results`: Raw test results (child stream of Checks)

Commented-out streams (require special permissions):
- `Probes`, `Maintenance`, `MaintenanceOccurrences`, `Teams`, `TMSChecks`

## API and Authentication

### Configuration
Required environment variables for testing:
- `TAP_PINGDOM_TOKEN`: API bearer token
- `TAP_PINGDOM_START_DATE` (optional): Earliest datetime to get data from

Load from `.env` file:
```bash
source /Users/edgarramirez/reservoir/tap-pingdom/.env
```

### API Details
- Base URL: `https://api.pingdom.com/api/3.1`
- Authentication: Bearer token via `BearerTokenAuthenticator`
- User-Agent header: `tap-pingdom/{version}`
- Pagination: Offset-based via `offset` and `limit` parameters

### Pagination Implementation
The tap uses a custom `PingdomPaginator` class that extends `BaseOffsetPaginator`:
- **Automatic pagination**: Fetches all pages until fewer records than page size are returned
- **JSONPath-based detection**: Uses `singer_sdk.helpers.jsonpath.extract_jsonpath()` to count records using each stream's `records_jsonpath` to determine if more pages exist
- **Stream-specific page sizes**: Each stream can configure its own page size based on API limits
- The paginator checks if the response contains a full page of results - if yes, it continues; if not, pagination stops
- **No external dependencies**: Uses Singer SDK's built-in JSONPath helper instead of external libraries

### Stream-Specific Details
- **Checks**: Page size 25000 (API max), includes tags, automatic pagination
- **Actions**: Page size 100 (API max), supports time filtering via `from` parameter, automatic pagination
- **Contacts**: Page size 100 (default), automatic pagination
- **Results**: Page size 1000 (API max), child stream requiring `checkid` from parent context, automatic pagination

## Testing Guidelines

### Snapshot Testing
- Uses syrupy for schema snapshot tests
- Snapshots stored in `tests/__snapshots__/`
- Test schema evolution in `tests/test_schema_evolution.py`
- Update snapshots when schemas intentionally change

### Test Configuration
- pytest runs with `-vvv --durations=10`
- Environment variables passed via tox (see `pass_env` in pyproject.toml)
- Use `pytest-subtests` for parameterized tests

## OpenAPI Schema Management

### Updating OpenAPI Schema
Use the script in `scripts/update_openapi.py` to fetch and update the OpenAPI specification from Pingdom's API documentation.

When updating:
1. Run the update script
2. Verify stream schemas still match
3. Update any manual schema definitions if needed
4. Run schema evolution tests to catch breaking changes

### Known OpenAPI Schema Issues

The current OpenAPI spec has several issues that prevent using it for all streams (see NOTE comments in `tap_pingdom/streams.py` for detailed explanations):

**Type Errors to Report/Fix:**
- `actions_alerts_entry`: Fields `userid`, `checkid`, `time` should be integers (not strings)
- `actions_alerts_entry`: Field `charged` should be boolean (not string)
- `results_resp_attrs`: Missing `probedesc` string property

**Structural Issues:**
- Most item schemas are defined inline within response wrappers rather than as reusable components
- This prevents using `StreamSchema(OPENAPI_SCHEMA, key="ComponentName")`
- To fix: Extract inline schemas into standalone components (e.g., `AlertItem`, `MaintenanceWindow`, `ResultItem`)

**Testing OpenAPI Schema Changes:**
After updating the OpenAPI spec, test if any manual schemas can be replaced:
1. Check if new reusable components were added
2. Try using `StreamSchema(OPENAPI_SCHEMA, key="NewComponent")`
3. If the component has minor issues (wrong types, complex structures), use `effective_schema` with patches instead of manual schemas
4. Run `uv run tap-pingdom --discover > catalog.json` to verify schema generation
5. Run schema snapshot tests: `tox -e py314 -- tests/test_schema_evolution.py`
6. Compare generated schema with manual/expected schema to ensure they match
7. If successful, replace manual schema with OpenAPI + patches (if needed) and update/remove NOTE comments

## Pre-commit Hooks
The project uses pre-commit hooks (see `.pre-commit-config.yaml`). Ensure they pass before committing:
```bash
pre-commit run --all-files
```

## Common Tasks

### Adding a New Stream
1. Define the stream class in `tap_pingdom/streams.py` inheriting from `PingdomStream`
2. Set required attributes: `name`, `path`, `primary_keys`, `replication_key`, `records_jsonpath`
3. Define schema:
   - **Preferred**: Use `StreamSchema(OPENAPI_SCHEMA, key="ComponentName")` if available
   - **If patches needed**: Override `effective_schema` with `apply_schema_patch()`
   - **Last resort**: Define manual schema with `th.PropertiesList` and add NOTE comment explaining why
4. Override `get_url_params()` if custom parameters needed (e.g., limit, filters)
5. Override `get_new_paginator()` if custom page size needed (default is 100)
6. Add to `STREAM_TYPES` list in `tap_pingdom/tap.py` (or comment out if requires special permissions)
7. Add schema snapshot test in `tests/test_schema_evolution.py`
8. Run tests and update snapshots

### Debugging Stream Issues
1. Use `uv run tap-pingdom --config CONFIG --discover` to check schema discovery
2. Check API responses by running with `--log-level DEBUG`
3. Verify authentication token has required permissions
4. Check Pingdom API documentation at https://docs.pingdom.com

### Debugging Pagination
If pagination seems to stop early or loop infinitely:
1. Check that the stream's `records_jsonpath` correctly matches the API response structure
2. Verify the `limit` parameter in `get_url_params()` matches the paginator's `page_size`
3. Run with `--log-level DEBUG` to see offset values and record counts
4. Test the paginator's `has_more()` logic - it returns `True` if `record_count >= page_size`
5. Verify the API is returning the expected number of records per page

## Important Notes
- This tap was generated from a Copier template (v0.5.9)
- Repository is currently private
- Do NOT update `.copier-answers.yml` manually
- Version is managed automatically via hatch-vcs from git tags
- The project requires uv 0.8+ and Python 3.12+
