# AI_CONTEXT.md

# DebugSQL Frontend AI Context

## Project Overview

DebugSQL is a human-in-the-loop NL2SQL debugging platform.

The system allows users to:
- write natural language database queries,
- visualize generated query plans,
- inspect/edit query nodes,
- simulate query execution,
- and debug AI-generated SQL workflows.

This frontend is primarily a DEMO-FIRST academic project focused on:
- modern UI/UX,
- professional presentation,
- interactive query visualization,
- and future backend extensibility.

The frontend should FEEL like:
- Cursor
- OpenAI internal tools
- Vercel dashboards
- modern AI research software

NOT like a generic CRUD dashboard.

---

# Frontend Stack

## Core
- React
- TypeScript
- Vite

## UI
- Bootstrap 5
- React Bootstrap
- Framer Motion
- React Icons

## Graph Visualization
- React Flow

## Routing
- React Router DOM

## Future State Management
- Zustand (optional later)

---

# Frontend Architecture Rules

## VERY IMPORTANT

- NEVER rewrite the entire application.
- NEVER modify unrelated files.
- ALWAYS preserve existing architecture.
- ALWAYS extend existing components carefully.
- DO NOT create giant monolithic files.
- Use modular reusable components.
- Use strict TypeScript typing.
- Preserve desktop-first responsive design.
- Maintain dark modern UI consistency.

---

# Folder Structure

```txt
src/
├── assets/
├── components/
│   ├── chat/
│   ├── layout/
│   ├── query-plan/
│   ├── inspector/
│   ├── results/
│   ├── ui/
│   └── animations/
├── pages/
├── router/
├── services/
│   ├── api/
│   ├── mocks/
│   └── adapters/
├── hooks/
├── store/
├── styles/
├── types/
├── utils/
└── App.tsx