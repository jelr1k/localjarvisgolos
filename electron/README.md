# Jarvis UI prototype

This branch is the interface-only architecture phase. It intentionally does not connect to the real voice, AI, command-router, or file-system services from the application backend.

## Two presentations, one state

- Classic uses a conventional sidebar, pages, cards, and form-based settings.
- NEXUS uses a distinct workspace and a React Flow settings graph inspired by connected-note tools.
- Both views use the same React components for the actual application pages and the same typed settings model.
- Preferences are persisted locally in the Electron renderer. The active view is restricted to Classic or NEXUS; theme, density, corners, and motion are separate presentation preferences.

The NEXUS graph is a view of the shared settings catalog. Category nodes open all settings in that category; leaf nodes open one setting. Node positions are persisted independently of the settings values.

All statuses and values that would normally come from services are explicitly shown as disconnected or demo-only. Chat replies are local placeholders and never execute commands.

## Run

From this directory:

- npm install
- npm run dev — start Vite and Electron together
- npm test — run reducer and shared-state tests
- npm run typecheck — check TypeScript
- npm run build — type-check and build the renderer
- npm start — build the renderer and launch Electron

The compiled renderer is written to dist. Electron uses the Vite dev server during development and the compiled renderer for a normal launch.

## Architecture

- src/app — state, persistence, setting metadata, and navigation contracts.
- src/components — shared settings controls and prototype notices.
- src/pages — shared page content that works in either shell.
- src/layout — the Classic and NEXUS shells.
- src/nexus — graph model and graph presentation.
- main.js / preload.js — minimal Electron window and isolated bridge; no backend integration is attempted in this phase.

Use the settings catalog as the single source for classic forms and NEXUS nodes. Do not duplicate setting definitions in a layout.
