# STORY-5 Implementation Map

Last updated: 2026-05-24 by Developer (cycle 1)

## AC27 ("draft:true excluded by default: no HTML page, no index entry, no tag entry or count")
Implemented in:
- src/ssg/parser.py:143 (`_coerce_draft` -- normalizes the front-matter `draft` field to a bool; missing field or `false` -> False, `true` and the truthy spellings -> True)
- src/ssg/parser.py:72 (`parse_post` -- calls `_coerce_draft(front_matter.get("draft"), path)` and stores the result on `Post.draft`)
- src/ssg/builder.py:86 (`build_site` -- the parse loop does `if post.draft and not include_drafts: continue` (line 124), dropping each excluded draft from `entries` BEFORE tag grouping, so the draft produces no page, joins no index entry, and adds no tag-page entry or count)
- src/ssg/builder.py:147 (`_group_tags` -- iterates only the surviving `entries`; an excluded draft is absent, so its tags create no tag page and contribute no count)

## AC28 ("--include-drafts builds the draft, lists it on index and its tag pages, and prefixes its title with [DRAFT] on index, tag pages, post <title> and H1")
Implemented in:
- src/ssg/__main__.py:23 (`_run_build` -- accepts `include_drafts` and forwards it to `build_site`)
- src/ssg/__main__.py:99 (`main` -- maps the `build --include-drafts` argument to `_run_build(include_drafts=True)`)
- src/ssg/builder.py:86 (`build_site` -- with `include_drafts=True` the draft survives the parse loop, so it gets a `dist/<basename>.html` page, an index entry, and an entry on each of its tag pages)
- src/ssg/builder.py:176 (`_display_title` -- returns `"[DRAFT] " + post.title` for a draft post; the single helper used for the index and tag listings)
- src/ssg/builder.py:235 (`_index_line` -- builds the index `<li>` from `_display_title(entry.post)`, so a draft's index title carries the `[DRAFT]` prefix)
- src/ssg/builder.py:183 (`_tag_page_line` -- builds each tag-page `<li>` from `_display_title(entry.post)`, so a draft's tag-page title carries the `[DRAFT]` prefix)
- src/ssg/renderer.py:40 (`render_page` -- builds the page title as `"[DRAFT] " + post.title` for a draft (line 50), escapes it, and the `_PAGE_TEMPLATE` places that single value into both `<title>` and `<h1>`)

## AC29 ("draft: \"true\"/\"yes\"/\"1\" (truthy strings) -> treated as a draft, excluded by default")
Implemented in:
- src/ssg/parser.py:24 (`_DRAFT_TRUE_STRINGS` -- the frozenset {"true", "yes", "1"} of recognized truthy spellings)
- src/ssg/parser.py:143 (`_coerce_draft` -- lowercases/strips a string value and returns True when it is in `_DRAFT_TRUE_STRINGS`)
- src/ssg/builder.py:86 (`build_site` -- the parse-loop exclusion uses `post.draft`, so a truthy-string draft is dropped by default exactly like `draft: true`)

## AC30 ("draft: \"false\" (string) or no draft field -> published")
Implemented in:
- src/ssg/parser.py:25 (`_DRAFT_FALSE_STRINGS` -- the frozenset {"false", "no", "0"} of recognized falsey spellings)
- src/ssg/parser.py:143 (`_coerce_draft` -- returns False for a missing field (`value is None`), for boolean `false`, and for a string in `_DRAFT_FALSE_STRINGS` such as `"false"`)
- src/ssg/builder.py:86 (`build_site` -- a post whose `Post.draft` is False survives the parse loop unconditionally, so it builds and lists as a published post with no `[DRAFT]` marker)

## AC31 ("draft: \"maybe\" (unrecognized non-boolean string) -> nonzero exit, error names the offending file")
Implemented in:
- src/ssg/parser.py:143 (`_coerce_draft` -- a string that is in neither `_DRAFT_TRUE_STRINGS` nor `_DRAFT_FALSE_STRINGS` raises `FrontMatterError` whose message begins with `f"{path.name}: ..."`, naming the offending file)
- src/ssg/parser.py:72 (`parse_post` -- calls `_coerce_draft(front_matter.get("draft"), path)` during parsing, so the raise propagates out of `build_site`)
- src/ssg/__main__.py:23 (`_run_build` -- catches `FrontMatterError`, prints the file-naming message to stderr, returns exit code 1, and prints no success summary)

## AC32 ("every post is a draft and --include-drafts is unset -> build succeeds, index says 'No posts yet.'")
Implemented in:
- src/ssg/builder.py:86 (`build_site` -- when every post is an excluded draft the parse loop leaves `entries` empty; the build still completes and writes `dist/index.html`)
- src/ssg/builder.py:193 (`_render_index` -- emits `<p>No posts yet.</p>` when `entries` is empty, the same body as an empty content directory)
- src/ssg/builder.py:27 (`NO_POSTS_MESSAGE` -- the exact `"No posts yet."` string required by STORY-3 AC15)
