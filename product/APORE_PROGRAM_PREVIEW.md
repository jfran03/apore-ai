# Apore Program Preview

## What We Are Trying To Accomplish

Apore is being redesigned as a local-first desktop learning workspace.

The product direction combines:

- SEALION's workspace-style layout and grounded source interaction.
- The prototype's adaptive tutoring runtime, learner-state tracking, and curriculum graph ideas.
- Apore's current brand foundation: dark desktop surface, black/gold accent language, Socratic tutoring, grounded source compilation, and adaptive calibration.

The final product should feel closer to a desktop IDE for learning than a web dashboard. It will be compiled with React/Tauri, while a Python backend runs locally through localhost for ingestion, transcription, graph compilation, tutoring, and learner-state updates.

## Core Product Model

A top-level workspace is a **Learning Domain**.

The domain name is organizational. The semantic meaning comes from the user's one-line learning objective, selected teaching style, selected model, and imported sources.

Each domain is expected to map cleanly to local folders and files:

```text
domain/
  domain.json
  sessions/
  sources/
  knowledge/
```

The three primary subfolders are:

- **Session History**: mixed chat and scratchpad sessions, shown together with type-specific icons.
- **Sources**: raw PDFs, websites, YouTube/video links, transcripts, images, docs, copied text, and extracted markdown.
- **Curriculum Graph**: a compiled, editable curriculum map where nodes represent teachable concepts and edges represent prerequisite dependency.

The filesystem should remain inspectable. JSON and markdown should carry durable state wherever possible.

## Key Interaction Decisions

- Domain creation only scaffolds the domain. Adding sources happens after the domain opens.
- Source intake should function like NotebookLM, but extended for local desktop use and video transcription.
- Chat sessions should look like Cursor-style transcript sessions, not bubble chat.
- Scratchpads are drawable `tldraw` workspaces with user and AI layers.
- The AI can read selected scratchpad regions by receiving image crops.
- The floating scratchpad prompt is only an input capture surface. Submitted prompts are sent into the right-side assistant/chat panel.
- The AI can propose drawings or annotations using the same canvas object model, but its output should remain on a hideable AI layer.
- Curriculum graph editing happens in the center canvas. Curriculum-builder agent proposals live in the right assistant panel.
- In a full chat session, the right assistant panel should be hidden because the center panel is already the chat surface.

## Purpose Of The HTML Artifact

`product/artifacts/apore-program-preview.html` is a living design and product-architecture preview.

It is not intended to be production code. It is a visual schema for the app shell, information architecture, and interaction model.

The artifact currently demonstrates:

- Desktop-style app chrome inspired by Cursor's desktop app.
- A black/gold Apore theme aligned with the current site direction.
- A left domain sidebar with collapsible subfolders.
- Domain setup with editable teaching-style preset prompts.
- NotebookLM-style source intake for files, websites, YouTube/video, copied text, and transcripts.
- Cursor-like chat session formatting.
- Scratchpad canvas behavior with selection, floating prompt, and AI layer.
- Curriculum graph layout with right-sidebar curriculum-builder agent proposals.

The artifact should be used to review and refine product decisions before implementation begins.

## Current Design Principle

The preview should avoid generic SaaS or SEALION-specific styling.

It should feel like:

```text
Cursor desktop app
+ Apore black/yellow identity
+ local-first learning domains
+ adaptive Socratic tutoring
+ grounded curriculum compilation
```

The design should stay desktop-native, dark, sparse, and functional. Avoid decorative glow backgrounds, web-page navigation, redundant metadata pills, and placeholder controls that do not correspond to real product behavior.
