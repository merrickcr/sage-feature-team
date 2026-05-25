---
title: Hello World
date: 2026-05-24
tags: [python, tools]
---

This is my first post built with `ssg`.

## Features tested here

- Front-matter parsing (title, date, tags)
- Markdown to HTML conversion
- Tag page generation

Here's a simple code block:

```python
python -m ssg build
```

And a list of things ssg can do:

1. Parse Markdown files from `content/`
2. Generate HTML pages in `dist/`
3. Build an index with date-sorted posts
4. Create per-tag pages
5. Serve locally with `python -m ssg serve`
