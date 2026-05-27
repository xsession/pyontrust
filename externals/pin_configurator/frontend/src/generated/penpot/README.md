# Penpot generated surface

This folder is the only designer-owned frontend surface for the shell chrome.

## Ownership

- Safe to regenerate from Penpot:
  - `PenpotEditableShell.tsx`
  - `PenpotLegacyTopStrip.tsx`
  - `PenpotWorkspacePanel.tsx`
  - `penpotShellTokens.ts`
- Safe to treat as the generated public contract:
  - `index.ts`
- Do not overwrite from Penpot:
  - `src/views/*`
  - `src/workspace/*`
  - `src/presenters/*`
  - `src/project/*`

## Import convention

- Hand-coded containers import only from `src/generated/penpot/index.ts` when they need designer-owned shell chrome.
- Generated files accept plain props and render slots only.
- Generated files must not fetch data, read storage, dispatch commands directly, or own business rules.

## Export convention

- Penpot exports structure into the generated component files in this folder.
- Penpot exports visual values into `penpotShellTokens.ts`.
- Shared CSS should consume the exported token variables instead of hard-coding shell chrome values.
- `npm run export:penpot` packages the designer-owned surface into `dist/penpot-surface` for handoff.

## Slot contract

- `PenpotEditableShell`: frame and region slots only.
- `PenpotLegacyTopStrip`: visible top strip only.
- `PenpotWorkspacePanel`: shell panel header and body chrome only.

## Review rule

- If a Penpot change requires logic edits outside this folder, the change is crossing the ownership boundary and should be reviewed as an engineering change, not a design export.