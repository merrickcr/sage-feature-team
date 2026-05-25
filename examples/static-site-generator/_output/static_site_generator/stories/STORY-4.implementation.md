# STORY-4 Implementation Map

Last updated: 2026-05-24 by Developer (cycle 1)

## AC20 ("per-unique-tag dist/tags/<slug>.html page listing every post with that tag, sorted date desc then date-less alpha, slug via shared slugify")
Implemented in:
- src/ssg/parser.py:79 (`slugify` -- the single shared slugify function reused for tag slugs: lowercase, each non-alnum run -> a single `-`, no stripping)
- src/ssg/builder.py:137 (`_group_tags` -- builds one `_TagGroup` per UNIQUE tag slug across all entries, keyed by `slugify(tag)`; returns groups sorted by slug)
- src/ssg/builder.py:126 (`build_site` -- when tag groups exist, creates `dist/tags/` and writes `dist/tags/<slug>.html` for each group)
- src/ssg/builder.py:157 (`_render_tag_page` -- renders each tag page; orders its posts via `_sorted_for_index`, the same date-desc-then-date-less-alpha rule as the main index)
- src/ssg/builder.py:205 (`_sorted_for_index` -- dated descending, all dated before date-less, date-less alphabetical by lowercased title -- shared ordering rule)
- src/ssg/builder.py:166 (`_tag_page_line` -- emits each `<li>` on the tag page linking the post via `../<basename>.html` since tag pages live one level below dist/)

## AC21 ("index gains a Tags section listing each tag with its post count, linking to tags/<slug>.html")
Implemented in:
- src/ssg/builder.py:176 (`_render_index` -- appends the Tags section to the index body only when `tag_groups` is non-empty)
- src/ssg/builder.py:192 (`_render_index_tags_section` -- emits the `<h2>Tags</h2>` heading and a `<ul>` of tag entries)
- src/ssg/builder.py:198 (`_index_tag_line` -- builds one `<li>` linking the tag label to `tags/<slug>.html` and showing `(count)` where count is `len(group.entries)`)

## AC22 ("a post with tags [python, learning] displays both on its own page, each linked to its tags/<slug>.html page")
Implemented in:
- src/ssg/renderer.py:59 (`_render_tags` -- renders each of the post's tags as `<a href="tags/<slug>.html">tag</a>` links, joined into a `<p class="tags">` paragraph)
- src/ssg/renderer.py:56 (`render_page` -- inserts the rendered tag markup into the page via the `{tags}` template field)
- src/ssg/renderer.py:31 (`_PAGE_TEMPLATE` -- the `{tags}` template field sits between the date region and `<article>`)

## AC23 ("a post with no tags field or 'tags: []' appears on no tag page and contributes nothing to the index Tags section")
Implemented in:
- src/ssg/parser.py:119 (`_coerce_tags` -- a missing `tags` field or `tags: []` yields an empty list, so the post carries zero tags)
- src/ssg/builder.py:137 (`_group_tags` -- iterates only `entry.post.tags`; an empty list adds the post to no group, so it joins no tag page and no index Tags entry)
- src/ssg/renderer.py:59 (`_render_tags` -- returns the empty string for an untagged post, so its page links to no tag page)

## AC24 ("when every post has 'tags: []' or no tags, no dist/tags/ directory is created and the index omits the Tags section entirely")
Implemented in:
- src/ssg/builder.py:126 (`build_site` -- `if tag_groups:` guards `dist/tags/` creation, so with zero groups the directory is never made)
- src/ssg/builder.py:176 (`_render_index` -- `if tag_groups:` guards the Tags section append, so with zero groups the index emits no Tags heading at all -- byte-identical to the pre-tags index)
- src/ssg/builder.py:154 (`_group_tags` -- returns an empty list when no entry carries any tag)

## AC25 ("'tags: foo' (a string instead of a list) -> nonzero exit; error names the offending file and states tags must be a list")
Implemented in:
- src/ssg/parser.py:119 (`_coerce_tags` -- when the `tags` value is not a list, raises `FrontMatterError` with the message `<file>: tags must be a list, got <type>`, naming the offending file)
- src/ssg/parser.py:67 (`parse_post` -- calls `_coerce_tags(front_matter.get("tags"), path)` during parsing, so the raise propagates out of `build_site`)
- src/ssg/__main__.py:34 (`main` -- catches `FrontMatterError`, prints the file-naming message to stderr, returns exit code 1, and prints no success summary)

## AC26 ("two posts with tags that slugify to the same value share one dist/tags/<slug>.html page listing both posts")
Implemented in:
- src/ssg/parser.py:79 (`slugify` -- 'c++' and 'c--' both map to 'c-'; 'node.js' and 'node-js' both map to 'node-js' under the shared rule)
- src/ssg/builder.py:144 (`_group_tags` -- groups entries into `by_slug` keyed by `slugify(tag)`, so colliding tags collapse into ONE `_TagGroup` whose `entries` accumulate every post carrying any colliding tag)
- src/ssg/builder.py:130 (`build_site` -- writes exactly one `dist/tags/<slug>.html` per group, so the shared slug yields a single page listing both posts)
