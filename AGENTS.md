# DebugSQL — Agent Guide

This file is the primary source of truth for AI-assisted development in the DebugSQL repository. It documents the existing architecture, conventions, and patterns derived directly from the current codebase. Do not treat it as a wishlist; follow the patterns that are already present.

DebugSQL is a human-in-the-loop NL2SQL debugging system. The repository contains a FastAPI backend, a React + Vite frontend, PostgreSQL (production) / SQLite (local dev) persistence, and Docker Compose orchestration.

---

## Architecture

### High-level flow

```text
Browser -> Frontend (React/Vite) -> Backend (FastAPI) -> PostgreSQL
                                    |                    |
                                    +-- SQLite benchmark databases (BIRD/Spider)
```

### Services

| Service | Technology | Key files |
|---|---|---|
| Frontend | React 18, TypeScript, Vite | `frontend/src/` |
| Backend | FastAPI, Python 3.11+ (synchronous route handlers) | `backend/app/` |
| Database | PostgreSQL 16 (Docker) or SQLite (local dev) | `backend/app/database.py`, `backend/alembic/` |
| Benchmark data | BIRD and Spider SQLite databases | `data/benchmarks/` |

### Backend modules

- `app/main.py` — FastAPI app factory, CORS, router inclusion, health endpoints.
- `app/config.py` — Pydantic Settings (`Settings`, `get_settings()`), `.env` discovery.
- `app/database.py` — SQLAlchemy `Base`, engine factory, `session_scope()` context manager.
- `app/request_auth.py` — cookie-based auth helpers used by route handlers.
- `app/auth.py` — user/session business logic, dev auto-login fallback.
- `app/persistence.py` — best-effort persistence for chat, plans, executions, operation logs.
- `app/*_routes.py` — FastAPI routers (auth, chat, execution, history, benchmarks, etc.).
- `app/conversation/` — chat intent classification, SQL resolution, proposed actions.
- `app/tools/` — tool schemas, registry, connectors, executor, capabilities.
- `app/nl2ir/`, `app/planning/`, `app/gemini/` — provider abstractions for NL-to-IR, IR-to-plan, and LLM SQL generation.
- `app/models/` — SQLAlchemy models (`auth.py`, `history.py`).
- `app/demo_pipeline.py` — legacy monolithic path for plan generation, editing, execution, and step runs. Today the active execution path is `tools/executor.py`; `demo_pipeline.py` remains for legacy evaluation endpoints and the `POST /execute` demo route.
- `app/benchmark_registry.py` — benchmark metadata loading and schema context access.
- `app/simple_nl2sql.py` — deterministic schema-aware NL2SQL fallback.
- `app/email_sender.py` — SMTP / dev-log email login codes.

### Frontend modules

- `src/App.tsx`, `src/main.tsx` — root mount, global CSS imports.
- `src/router/AppRouter.tsx` — `BrowserRouter` with lazy-loaded pages.
- `src/components/` — feature components grouped by domain (`chat/`, `capabilities/`, `results/`, `query-plan/`, `inspector/`, `layout/`, `ui/`, `animations/`).
- `src/store/` — React Context providers: `DatasetContext`, `ExecutionContext`, `QueryPlanContext`.
- `src/services/api/` — typed API client and endpoint modules.
- `src/services/adapters/` — single injection points that switch between real API and mocks.
- `src/services/mocks/` — isolated frontend-only mock implementations.
- `src/types/` — shared TypeScript types.
- `src/styles/global.css` — design-system CSS variables and base reset.

---

## Folder Structure

```text
debugsql/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── auth.py
│   │   ├── request_auth.py
│   │   ├── persistence.py
│   │   ├── demo_pipeline.py
│   │   ├── benchmark_registry.py
│   │   ├── simple_nl2sql.py
│   │   ├── email_sender.py
│   │   ├── *_routes.py
│   │   ├── conversation/
│   │   ├── gemini/
│   │   ├── models/
│   │   ├── nl2ir/
│   │   ├── planning/
│   │   └── tools/
│   │       └── connectors/
│   ├── alembic/
│   ├── tests/
│   ├── pyproject.toml
│   ├── requirements.txt
│   ├── uv.lock
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── pages/
│   │   ├── router/
│   │   ├── services/
│   │   ├── store/
│   │   ├── styles/
│   │   ├── types/
│   │   └── utils/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── Dockerfile
│   └── nginx.conf
├── data/
│   ├── benchmarks/
│   │   ├── bird/{raw,processed,sqlite}
│   │   └── spider/{raw,processed,sqlite}
│   ├── dev/
│   └── postgres/
├── scripts/
├── docker-compose.yml
├── .env.example
├── .env.server.example
└── README.md
```

### Notes on external / vendored code

- `backend/vendor/` exists but is outside the active application code path. Do not modify files under `backend/vendor/` unless you are explicitly instructed to upgrade or patch the vendored package. New features should not depend on it.

---

## Coding Conventions

### Backend (Python)

- Target Python 3.11+. Use `from __future__ import annotations` in modules that reference forward-declared types or complex generics; otherwise it is optional.
- Use `snake_case` for modules, functions, and variables; `PascalCase` for classes.
- Type hints are expected on function signatures. Use `|` union syntax (`str | None`). Do not use `Optional[...]`.
- Pydantic models for API payloads/responses; SQLAlchemy 2.0 `Mapped` / `mapped_column` for ORM.
- Public API JSON uses `camelCase` field names for frontend compatibility (e.g., `sessionId`, `datasetContext`). Either define the field with a `camelCase` name directly or use Pydantic `Field(alias=...)` / `alias_generator` and serialize with `model_dump(by_alias=True)`.
- Private helpers are prefixed with `_`.
- Standard library imports first, then third-party, then `app.*` modules.
- Use local imports inside functions when necessary to avoid circular dependencies (common in `demo_pipeline.py` and `persistence.py`).
- Logging uses `logging.getLogger(__name__)`. Some defensive paths use `print(f"[module] ...")`.
- **Route handlers are synchronous.** Use `def`, not `async def`. Do not introduce `await` in route handlers without explicit approval and a plan for session management.

### Frontend (TypeScript/React)

- Strict TypeScript (`strict: true`). Use interfaces for data models and component props.
- Functional components with named exports. Default exports are used only for lazy-loaded pages in `src/pages/`. The one exception is `src/App.tsx`, which uses a default export because it is imported by `src/main.tsx` as the application root.
- Components and their styles are co-located: `Component.tsx` + `Component.css` in the same folder.
- File naming:
  - Component files and their co-located CSS: `PascalCase.tsx` / `PascalCase.css`.
  - Standalone types, API modules, utilities, and hooks: `camelCase.ts`.
  - Component-local type files may use `PascalCase.types.ts` (e.g., `chat.types.ts`, `queryPlan.types.ts`).
- Hooks and contexts go in `src/hooks/` and `src/store/`.
- Utility functions go in `src/utils/`.
- Use `React.ReactNode` for children, explicit prop interfaces, and `React.CSSProperties` for inline dynamic styles.
- Prefer `const` callbacks with `useCallback` for event handlers passed to children.
- Use `void fn()` when calling async functions from event handlers to explicitly ignore the returned promise.

---

## React Best Practices

- Use functional components only. Class components are not used in this codebase.
- Export components as named exports unless the file is a lazy-loaded page in `src/pages/` (or `src/App.tsx`).
- Keep components focused on one responsibility. If a component exceeds ~250 lines, split it into smaller sub-components in the same folder.
- Co-locate sub-components that are not reused elsewhere in the same file or folder (e.g., `InspectorPanel.tsx` with `InspectorHeader`, `FieldRow`).
- Use React Context for global state (`DatasetContext`, `ExecutionContext`, `QueryPlanContext`). Do not add Zustand, Redux, or MobX without explicit approval. (Zustand is a transitive dependency of `reactflow`; do not import it directly.)
- Wrap context provider values with `useMemo` when they contain objects or arrays passed to many consumers.
- Use `useCallback` for event handlers and callbacks passed to `memo`-wrapped children (e.g., React Flow node components).
- Use `memo` for expensive leaf components that re-render often with the same props, especially custom React Flow nodes (`OperationNode`, `DataNode`, `IntentNode`).
- Call async functions from event handlers with `void fn()`; do not make event handlers themselves async.
- Clean up side effects in `useEffect` return callbacks (event listeners, timers, `isMounted` flags for async data fetching).
- Prefer controlled inputs. Use native HTML form controls styled with CSS rather than React Bootstrap form components for new UI.
- Set `type="button"` on all `<button>` elements inside forms unless they intentionally submit.
- Lazy-load pages in `AppRouter` with `React.lazy(() => import('./pages/PageName'))`.

---

## TypeScript Best Practices

- `strict: true` is enabled. Do not disable it or use `@ts-ignore` to bypass errors. Prefer `@ts-expect-error` with a reason if absolutely necessary.
- Use `interface` for component props and data models. Use `type` for unions, aliases, and mapped types.
- Avoid `any`. Use `unknown` with type guards when the type is not known at compile time.
- Use discriminated unions for node/entity variants (e.g., `FlowNodeData` discriminated by `kind`).
- Prefer explicit return types on public API functions and context hooks.
- Use `import type { ... }` for type-only imports to avoid unnecessary runtime imports.
- Keep shared types in `src/types/` or next to their primary consumer. Re-export from `src/types/index.ts` when used across multiple features.
- Do not use enums; use string literal unions or `as const` objects instead.
- Type event handlers explicitly (e.g., `React.MouseEvent<HTMLButtonElement>`) when the event type matters.
- Use `React.CSSProperties` for any inline `style` prop.

---

## Refactoring Guidelines

- Make the smallest change that achieves the goal. Preserve existing behavior, file names, and module boundaries.
- Do not rewrite the entire application or modify unrelated files to implement a single feature.
- When renaming a symbol, update every call site, type reference, and test. Use `replaceAll` only after confirming all occurrences refer to the same symbol.
- Extract shared logic into a `src/utils/` helper or `src/hooks/` hook rather than copying it.
- Preserve existing API contracts. If a route response shape must change, update the frontend types and adapter layer in the same PR.
- Preserve the adapter/mock split. If you change a real API function, update the mock and adapter accordingly.
- When moving files, update all imports. Do not leave broken relative paths.
- Run `npm run build` and `tsc -b` after frontend refactors; run `pytest` after backend refactors.
- If a refactor touches the database schema, provide an Alembic migration.

---

## Component Reuse Guidelines

- Place truly reusable UI primitives in `src/components/ui/` (e.g., `StatusBadge`, `SkeletonLoader`).
- Place domain-shared components in the appropriate domain folder (e.g., query-plan nodes in `src/components/query-plan/nodes/`).
- Extract a new component when **any** of the following is true:
  - The same JSX/logic is used in three or more places.
  - A component file exceeds ~250 lines and a section has a clear, independent responsibility.
  - The component has distinct prop-driven variants that are easier to test in isolation.
- Keep CSS co-located with the component. Do not reuse CSS by moving it to a shared stylesheet unless it is part of the global design system.
- Define explicit, typed props. Avoid prop spreading (`{...props}`) unless wrapping a native element where extra props are expected.
- Do not over-abstract. Prefer mild duplication over a premature abstraction that forces unrelated features to share an API.

---

## Accessibility Guidelines

- Use semantic HTML first. A `<button>` should be a `<button>`, not a `div` with a click handler.
- Add `aria-label` to every icon-only button or link (e.g., copy buttons, refresh buttons).
- Use `role`, `aria-selected`, and `aria-current` for interactive lists, tabs, and selectable nodes.
- Ensure custom clickable elements are keyboard operable. If you must use a non-button with `role="button"`, handle `Enter` and `Space` keys.
- Do not override `outline: none` globally. Use `:focus-visible` for focused styling; it is already defined in `global.css`.
- Use `aria-live="polite"` for dynamic status regions (e.g., chat message list, execution status updates).
- Do not rely on color alone to convey state. Pair color with an icon, label, or text change (e.g., `ExecutionStatus` uses both color and icon).
- Preserve visible focus indicators on all interactive elements.
- Test tab order after adding new interactive elements in panels.

---

## UI Consistency Rules

- Use CSS variables from `frontend/src/styles/global.css` as the only source of truth for colors, spacing, typography, radius, and shadows.
- Do not hardcode colors, `px`/`rem` sizes, `font-family`, or `font-size` values in component CSS.
- Use the spacing scale: `--sp-1` (4px), `--sp-2` (8px), `--sp-3` (12px), `--sp-4` (16px), `--sp-5` (20px), `--sp-6` (24px), etc.
- Use the border-radius scale: `--r-xs`, `--r-sm`, `--r-md`, `--r-lg`, `--r-xl`, `--r-full`.
- Use the type scale: `--text-2xs` through `--text-3xl`, `--text-hero`.
- Use the color semantic variables: `--bg-*`, `--text-*`, `--border-*`, `--accent-*`. Do not introduce new hex codes.
- Use `--font-sans` for UI text and `--font-mono` for code, SQL, metrics, and timestamps.
- Maintain the dark theme. The UI is always dark; do not add light-mode-only styles.
- Use `StatusBadge` for status labels, `SkeletonLoader` for async placeholders, and `FadeIn` for entrance animations.
- Keep borders thin and subtle; prefer `--border-default` and `--border-subtle`.
- Avoid glow effects. Use `box-shadow` tokens for elevation only.
- Keep the three-panel layout stable. Do not change the `AppShell` structure without a strong reason.

### CSS class naming

- New components should use a full descriptor prefix matching the component name, in BEM-like form: `.component-name`, `.component-name__element`, `.component-name--modifier` (e.g., `.results-table__th`, `.chat-msg--user`).
- Some existing components use abbreviated legacy prefixes (`sbadge`, `qplan`, `sp-card`, `ptree`, `exec-panel`). Do not replicate these patterns for new components.

---

## Animation Patterns

- Use `FadeIn` for one-time entrance animations of static sections (e.g., panels on initial render).
- Use `AnimatePresence mode="wait"` with raw `motion.div` wrappers for state-driven content swaps (e.g., idle → running → success → failed in `ExecutionPanel`).
- Use `motion.button` / `motion.div` micro-interactions (`whileHover`, `whileTap`, `transition`) for interactive elements.
- Keep transitions short (100–350ms) and use `transform`/`opacity` for GPU-friendly animation.

---

## Performance Guidelines

### Frontend

- Lazy-load pages in `AppRouter`. Only the current page should be in the initial bundle.
- Wrap context provider values with `useMemo` when they contain objects or arrays.
- Use `useCallback` for handlers passed to `memo` children or React Flow node components.
- Wrap React Flow custom nodes (`OperationNode`, `DataNode`, `IntentNode`) with `memo`.
- Avoid creating new objects/arrays inside render for props of memoized children.
- Use dynamic imports for heavy libraries if they are not needed on initial render.
- Keep animation transitions short (100–350ms) and use `transform`/`opacity` for GPU-friendly animation.
- Do not fetch data inside render. Fetch in `useEffect` or event handlers.
- Cancel in-flight requests on unmount or fast user actions using `AbortController` or `AbortSignal.timeout`.

### Backend

- Cache engines and session factories with `@lru_cache` (already done in `app/database.py`).
- Keep route handlers thin. Move heavy logic to modules like `conversation/`, `tools/`, `demo_pipeline.py`.
- Use `session_scope()` for transactional work; do not hold sessions open longer than necessary.
- Avoid N+1 queries by eager loading relationships when needed.
- Validate SQL safety in `app/tools/policy.py` before execution; do not bypass it.
- Return errors quickly for invalid input; do not perform expensive work after validation fails.

---

## Code Review Guidelines

Before finishing a change, verify:

- TypeScript compiles with `npm run build` or `tsc -b` in `frontend/`.
- Python type hints are present and consistent with existing code.
- New CSS uses design-system variables only; no hardcoded colors or sizes.
- New API routes use the `{ "success": True, "data": ... }` envelope and correct HTTP status codes.
- Auth helpers from `request_auth.py` are used where required.
- Frontend API calls go through the adapter layer, not directly to `services/api/*` or `services/mocks/*`.
- All interactive elements have accessible labels or roles.
- No secrets, API keys, or `.env` files are added to Git.
- Backend tests pass with `pytest` from the `backend/` directory.
- A migration is included if the SQLAlchemy schema changed.
- The change does not expose PostgreSQL or add unsafe defaults.
- The execution path you touched is the intended one (see Chat / tool flow and Execution paths below).

---

## Testing Guidelines

### Backend

- Tests live in `backend/tests/` and run with `pytest` from the `backend/` directory.
- Use `pytest` fixtures for reusable setup. Keep tests independent and deterministic.
- Test provider logic, tool execution, auth flows, and SQL safety policy at the unit level.
- For database-dependent tests, prefer using a temporary SQLite file or mocking the session.
- Add tests when fixing bugs to prevent regression.
- Run `pytest` from the `backend/` directory before considering backend changes complete.

### Frontend

- Run `npm run build` (which includes `tsc -b`) to verify type correctness.
- Add unit tests for pure utility functions in `src/utils/` when logic is non-trivial.
- Keep component tests lightweight and isolated. Prefer testing logic hooks over deep component trees.
- Verify UI changes manually in the browser when visual or animation behavior is involved.
- Run the dev server and exercise the changed flow end-to-end before opening a PR.

### End-to-end

- For chat/execution changes, test against a real backend with a loaded BIRD/Spider database.
- For auth changes, test both `DEBUGSQL_AUTO_LOGIN=1` and email-code flows.

---

## Database Conventions

### SQLAlchemy

- Declarative base: `app.database.Base`.
- Models use SQLAlchemy 2.0 style:

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
```

- Table names are `snake_case` plural (`users`, `conversations`, `query_plans`).
- Primary keys are typically 64–128 char strings, often generated as `{prefix}_{hash}` or UUIDs.
- Flexible/hierarchical data is stored in `JSON` columns (`dataset_context`, `extra`, `graph_json`, `metrics`, etc.).
- Timestamps use `DateTime(timezone=True)` with `utc_now`.

### Session management

- Always use the provided context manager:

```python
from app.database import session_scope

with session_scope() as session:
    ...
```

### Migrations

- Use Alembic for all schema changes. Do not modify production schemas manually.
- Create a new migration with `alembic revision -m "description"` from the `backend/` directory.
- Name migration files with a date/serial prefix (e.g., `20260521_0001_core_persistence.py`).
- Ensure `alembic/env.py` imports `Base` and `app.models` so new models are discovered automatically.
- Write both `upgrade()` and `downgrade()` operations.
- Add explicit indexes for columns used in filters, especially foreign keys and lookup columns.
- Test migrations locally against SQLite (`data/dev/debugsql.sqlite`) and, when possible, against PostgreSQL.
- Never edit an existing migration file after it has been applied to a shared database.
- For destructive changes (column drops, renames), stage them in a separate migration and document the impact.
- Run `alembic upgrade head` before starting the backend in local development and in deployment scripts.

### Local development

- Local development defaults to a SQLite file at `data/dev/debugsql.sqlite`.
- The helper scripts `scripts/start_backend.ps1` / `scripts/start_backend.sh` set `DATABASE_URL` to this SQLite file if it is not already set.

### Persistence best-effort semantics

- `app/persistence.py` provides fire-and-forget persistence for chat interactions, plans, executions, and operation logs.
- Route handlers wrap persistence calls in `try/except` and log failures; the user-facing response never depends on a successful persistence write.
- Do not read data in the same request that was written via `persistence.py`. For transactional reads that must see the latest state, use `session_scope()` directly.

---

## API Patterns

### Backend routes

- Routes are defined with `APIRouter` and explicit prefixes/tags:

```python
router = APIRouter(prefix="/execute", tags=["execution"])
```

- Routers are imported and included in `app/main.py`.
- Request/response models are Pydantic `BaseModel`s.
- Success responses use a `{ "success": True, "data": ... }` envelope.
- Errors are raised as `HTTPException`:
  - `400` for validation/bad request (`ValueError`).
  - `401` / `403` for auth.
  - `404` for missing resources.
  - `500` for unexpected/database failures.
- Auth is cookie-based (`debugsql_session`). `request_auth.py` provides `request_user_id()`, `request_current_user()`, and `request_admin_user()`.
- FastAPI `Depends()` is not heavily used; route handlers pass the `Request` object to auth helpers, which open their own `session_scope()`.
- **Exception:** `POST /query` (`chat_routes.py`) catches all exceptions and returns them inside the success envelope with `intentType: "error"`. Do not raise `HTTPException` from inside this route; construct a `ConversationResponse` with `intentType='error'` instead.

### Frontend API client

- Centralized client: `src/services/api/client.ts`.
- Uses `fetch` with `credentials: 'include'` for cookie auth.
- All backend responses are expected in the `{ data, success, message? }` envelope.
- Method helpers: `apiGet`, `apiPost`, `apiPatch`, `apiDelete`.
- Errors throw `ApiClientError` with the HTTP status code.

### Adapter / mock pattern

- Each major feature has an adapter in `src/services/adapters/`:
  - `chatAdapter.ts`
  - `executionAdapter.ts`
  - `queryPlanAdapter.ts`
- Adapters check `import.meta.env.VITE_USE_MOCK_SERVICES === 'true'`.
- When mock mode is enabled, they call functions in `src/services/mocks/`.
- When mock mode is disabled, they dynamically import the real API module.
- Components and contexts import only from the adapter, never directly from `services/api/*` or `services/mocks/*`.

### Proxy

- In development, Vite proxies `/api/*` to `VITE_DEV_API_TARGET` (default `http://127.0.0.1:8000`).
- The backend base URL at build time is `VITE_API_BASE_URL` (default `/api`).
- In production (Docker), the nginx container in the frontend image proxies `/api` to the backend service. The Vite dev proxy is not used in production.

---

## API Development Guidelines

### Adding a new endpoint

- Create or extend an `APIRouter` in the relevant `*_routes.py` file. Use explicit `prefix` and `tags`.
- Register the router in `app/main.py`.
- Define Pydantic `BaseModel` request and response classes.
- Use `camelCase` field names for frontend-facing JSON. Use `alias_generator` or explicit aliases if needed.
- Return responses in the `{ "success": True, "data": ... }` envelope.
- Raise `HTTPException` with appropriate status codes:
  - `400` for validation failures (usually from `ValueError`).
  - `401` / `403` for auth failures.
  - `404` for missing resources.
  - `500` for unexpected/database failures.
- Use `request_user_id(request)`, `request_current_user(request)`, or `request_admin_user(request)` from `request_auth.py` for auth.
- Do not expose stack traces or sensitive internal details in error responses.
- Log unexpected failures with `logger.exception(...)` or `print(f"[module] ...")` in defensive paths.

### Changing an existing endpoint

- Preserve backward compatibility when possible. If the response shape changes, update the frontend types and adapters.
- Update the README endpoint list if the route is part of the public MVP surface.
- Ensure mock services still compile if the contract changes.

### Tool/capability endpoints

- Tool execution must go through `app/tools/executor.py`.
- New tools must be registered in the `TOOL_CATALOG` in `app/tools/executor.py` and added to capabilities via `app/tools/capabilities_service.py`.
- Read-only safety is enforced by `app/tools/policy.py`. Any new SQL-running tool must respect it.

### Adding a new database connector

To add support for a new `dbType` value:

1. Implement `app/tools/connectors/<your_connector>.py` inheriting from `app/tools/connector_base.py`.
2. Register the connector in `app/tools/registry.py`.
3. Add the new value to the `DbType` literal in `app/tools/schemas.py`.
4. Add the corresponding frontend `DbType` literal in `src/services/api/capabilitiesApi.ts`.
5. Add a UI option in the dataset selector (`CapabilitiesPanel.tsx`, `ChatPanel.tsx`).
6. Add schema context support in `app/benchmark_registry.py` if the connector reads benchmark-style metadata.
7. Add a backend test that exercises the connector's `execute_readonly()` and `capabilities()` methods.

---

## Security Considerations

- Never commit `.env` files, secrets, API keys, or database credentials to Git.
- Keep `DEBUGSQL_AUTO_LOGIN=1` for local development only. Always set it to `0` on remote servers.
- Authentication uses cookie-based sessions (`debugsql_session`). Cookies are `httponly`, `samesite="lax"`, and `secure` is controlled by `AUTH_COOKIE_SECURE`.
- Hash verification codes and session tokens before storing them. Do not store plaintext codes.
- SQL execution is read-only by policy (`app/tools/policy.py`). Any SQL path must validate that only `SELECT`/`WITH` queries run and dangerous keywords are rejected.
- Use parameterized queries wherever possible. Do not concatenate user input into SQL strings.
- Validate and normalize email addresses before storage and before issuing login codes.
- PostgreSQL is bound to `127.0.0.1` in `docker-compose.yml`. Do not change this to `0.0.0.0`.
- Limit CORS origins to known frontends via `CORS_ORIGINS`.
- Do not return raw exception traces or internal file paths in API error responses.
- Sanitize any user content rendered in the UI. The chat UI renders markdown-like text and fenced code blocks; do not render arbitrary HTML from user input.
- Keep dependencies pinned in `pyproject.toml`/`requirements.txt` and `package.json`. Review security advisories before major upgrades.

---

## Reusable Components

### Animation

- `FadeIn` — configurable direction (`up`, `down`, `left`, `right`, `none`), delay, duration. Uses Framer Motion.

### UI primitives

- `StatusBadge` — small colored label/chip with optional dot. Variants: `blue`, `cyan`, `green`, `orange`, `red`, `purple`, `gray`.
- `SkeletonLoader` — shimmer placeholder with configurable line widths and sizes.

### Layout

- `AppShell` — root three-panel workspace.
- `AppRouter` — lazy-loaded routes with `Suspense` fallback.

### Domain components

- `ChatPanel` / `ChatMessage` / `ChatInput` / `TypingIndicator` / `SuggestedPrompts` / `ProposedActions` — chat UI.
- `CapabilitiesPanel` — database selector, schema preview, tool list, example prompts.
- `ExecutionPanel` / `ExecutionStatus` / `ResultsTable` / `SQLPreview` — execution results.
- `QueryPlanArea` / `QueryPlanFlow` / `PlanNode` / `IntentNode` / `OperationNode` / `DataNode` — query plan graph (React Flow).
- `InspectorPanel` — node property editor.
- `AuthGate` — login screen and authenticated app frame.

### Visualization note

- `QueryPlanArea` and `PlanNode` render a legacy static CSS tree with mock data. The active query-plan visualization is `QueryPlanFlow` with React Flow custom nodes (`OperationNode`, `DataNode`, `IntentNode`). Do not extend the legacy tree for new features.

---

## Existing Project Patterns

### Provider pattern (backend)

The backend uses config-driven provider slots:

- `NL2IR_PROVIDER` — `stub` (currently returns `None`).
- `IR_TO_PLAN_PROVIDER` — `internal` / `stub` / `http`.
- `QUERY_PLAN_PROVIDER` — `openai_compatible` or `gemini`.

Providers are selected in factory functions (`app/nl2ir/provider.py`, `app/planning/provider.py`) and return a normalized internal schema.

### Chat / tool flow

This is the primary user-facing path for natural-language queries:

1. User sends a message from `ChatPanel` via `sendChatMessage` (`services/adapters/chatAdapter.ts`).
2. `POST /query` (`chat_routes.py`) receives the request and calls `handle_chat_message`.
3. `conversation/handlers.py` classifies intent.
4. `conversation/tool_assistant.py` resolves SQL (LLM if configured, benchmark gold SQL, or schema fallback).
5. Proposed tool actions are returned (`introspect_schema`, `run_sql_preview`, `run_sql`).
6. Frontend renders `ProposedActions`; execution requires approval for `run_sql`.
7. `POST /tools/execute` runs the tool via `app/tools/executor.py`.
8. Read-only safety is enforced by `app/tools/policy.py`.
9. Results flow back through `ProposedActions` into `ExecutionContext` and are displayed in `ExecutionPanel`.

### Execution paths

There are two backend endpoints that can run SQL. Know which one you are touching:

| Path | Endpoint | Backend entry | Frontend caller | Purpose |
|---|---|---|---|---|
| **Active** | `POST /tools/execute` | `tools/capabilities_routes.py` → `tools/executor.py` | `ProposedActions.tsx` via `executeTool()` | Tool-assisted chat execution with approval and policy enforcement. |
| **Legacy/demo** | `POST /execute` | `execution_routes.py` → `demo_pipeline.py` | `ExecutionPanel.tsx` via `executeQuery()` in `executionAdapter.ts` | Direct SQL execution for the execution panel demo path. |

When fixing execution bugs or adding execution features, prefer the `/tools/execute` path. Only use `POST /execute` for features explicitly scoped to the execution panel demo path.

### Message rendering

- `ChatMessage.tsx` parses assistant content into `ContentSegment[]` (text vs. fenced code blocks) using a custom regex in `parseContent`.
- Supported content is plain text plus triple-backtick code blocks. Other markdown-like features are not supported; do not introduce a full markdown renderer for chat messages without explicit approval.
- Code blocks render with a copy button and lightweight SQL token highlighting in `SQLPreview.tsx`.

### Dataset context

- `DatasetContext` (`dbType`, `benchmark`, `dbId`) is passed through chat, capabilities, and tool execution.
- `dbType` is either `sqlite_benchmark` or `postgres`.
- For SQLite benchmarks, `benchmark` is `bird` or `spider`, and `dbId` is the database ID.

### State management

- React Context is used for global state:
  - `DatasetContext` — selected benchmark/database.
  - `ExecutionContext` — execution status, result, error, plan run state.
  - `QueryPlanContext` — loaded plan graph, selected node, node edits.
- Local component state uses `useState` and `useCallback`.

### Adding a React Flow node type

To add a new node type to the query plan graph:

1. Add the node data shape to the `FlowNodeData` discriminated union in `src/components/query-plan/queryPlan.types.ts`.
2. Create the node component in `src/components/query-plan/nodes/` and wrap it with `memo`.
3. Register it in `NODE_TYPES` in `src/components/query-plan/QueryPlanFlow.tsx`.
4. Add a minimap color entry in `getMinimapColor` in the same file.
5. Update `src/components/inspector/inspectorFields.utils.ts` if the node needs inspector fields.
6. Update the backend graph mapper (`app/gemini/graph_mapper.py`) if the node can be produced by the backend plan generator.

### Naming conventions

- Frontend file names:
  - Component files and co-located CSS: `PascalCase.tsx` / `PascalCase.css`.
  - Standalone types, API modules, utilities, hooks: `camelCase.ts`.
  - Component-local type files: `PascalCase.types.ts`.
- Backend file names: `snake_case.py`.
- API field names: `camelCase` in JSON, `snake_case` in Python models.

### Dev user lifecycle

- When `DEBUGSQL_AUTO_LOGIN=1`, the backend creates or reuses a database user (`dev@debugsql.local`) on first request.
- If the system database is unavailable, `/auth/me` falls back to an ephemeral user dict. In that mode, persistence of conversations and history will not work.
- Always set `DEBUGSQL_AUTO_LOGIN=0` on remote servers and use email-code login.

### Scripts

- `scripts/start_backend.ps1` / `.sh` — start backend locally with SQLite.
- `scripts/start_frontend.ps1` / `.sh` — start frontend dev server.
- `scripts/deploy_server.sh` — remote server deployment via `docker compose`.
- `scripts/clean_bird.py`, `scripts/clean_spider.py` — preprocess benchmark data.

### Environment variables

- Copy `.env.example` to `.env` for local development; `.env.server.example` for server deployment.
- Key variables: `DATABASE_URL`, `DEBUGSQL_AUTO_LOGIN`, `SESSION_SECRET`, `CORS_ORIGINS`, `QUERY_PLAN_PROVIDER`, `LLM_API_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `BENCHMARK_DATA_DIR`, `VITE_API_BASE_URL`, `VITE_USE_MOCK_SERVICES`.

---

## Deployment Architecture

### Local development

- Backend runs on `http://127.0.0.1:8000`.
- Frontend dev server runs on `http://127.0.0.1:5173`.
- Vite proxies `/api/*` to the backend via `VITE_DEV_API_TARGET`.
- PostgreSQL is optional; local backend uses SQLite by default.

### Production (Docker Compose)

- The frontend image is a multi-stage build:
  - Build stage runs Vite with build args injected from `.env`.
  - Runtime stage copies the built static files into nginx and uses `frontend/nginx.conf` for routing.
- The nginx configuration forwards `/api` to the backend service over the Docker network; the Vite dev proxy is not used.
- The backend image installs dependencies from `requirements.txt` via `uv` and runs `uvicorn` on port 8000.
- PostgreSQL data is persisted in `data/postgres/` and is bound to `127.0.0.1` on the host.
- Benchmark data is mounted read-only into the backend container from `BENCHMARK_HOST_DATA_DIR`.

### Deployment checklist

- Ensure `.env` is present and `DEBUGSQL_AUTO_LOGIN=0` on remote servers.
- Run `docker compose up -d --build`.
- Run `docker compose exec backend alembic upgrade head`.
- Verify health via `GET /health`, `GET /db-health`, and a smoke test of `POST /query`.
- Do not expose PostgreSQL on `0.0.0.0`.

---

## What to Avoid

- Do not rewrite the entire application or modify unrelated files.
- Do not create giant monolithic files; keep components modular.
- Do not introduce new state-management libraries; Context is sufficient today.
- Do not add CSS-in-JS or CSS Modules; continue using global CSS variables and co-located CSS files.
- Do not expose PostgreSQL on `0.0.0.0`; the Compose mapping is intentionally localhost-only.
- Do not commit raw benchmark data or `.env` files.
- Do not enable `DEBUGSQL_AUTO_LOGIN=1` on remote servers.
- Do not raise `HTTPException` inside `POST /query`; return a `ConversationResponse` with `intentType='error'` instead.
- Do not bypass `app/tools/policy.py` for any new SQL-executing code path.
- Do not render arbitrary HTML from user input in the chat UI.
