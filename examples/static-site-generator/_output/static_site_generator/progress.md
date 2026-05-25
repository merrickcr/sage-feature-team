# Feature: static_site_generator

_Stories: 8/8 DONE  |  Epics: 3/3 VERIFIED_

## EPIC-1: Build pipeline — Markdown to dist/ HTML with index   [VERIFIED  3/3]
  - [DONE        ] STORY-1    Parse front-matter and convert Markdown body to HTML
  - [DONE        ] STORY-2    Render a parsed post into a full HTML page  (deps: STORY-1)
  - [DONE        ] STORY-3    Build command — walk content/, write dist/, generate index, print summary  (deps: STORY-1, STORY-2)

## EPIC-2: Content organization — tags and drafts   [VERIFIED  2/2]  (depends_on: EPIC-1)
  - [DONE        ] STORY-4    Tags — per-tag pages, index Tags section, per-post tag display
  - [DONE        ] STORY-5    Drafts — exclude by default, --include-drafts with [DRAFT] marker  (deps: STORY-4)

## EPIC-3: Local preview — serve dist/ over HTTP   [VERIFIED  3/3]  (depends_on: EPIC-1)
  - [DONE        ] STORY-6    Serve — serve dist/ over HTTP with request logging and clean shutdown
  - [DONE        ] STORY-7    Serve --port flag including --port 0 (pick-any-free)  (deps: STORY-6)
  - [DONE        ] STORY-8    Serve preconditions — missing/empty dist and busy-port errors  (deps: STORY-6)

