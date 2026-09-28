---
name: format-obsidian-notes
description: "Safely compact, repair, and validate explicit Obsidian Markdown (.md) files without rewriting their content. Use when the user asks to remove redundant blank lines, make notes denser, fix formulas that do not render in headings, convert heading \\(...\\) delimiters to $...$, preserve YAML/frontmatter, tables, callouts, lists, fenced code, and display math, or audit local Markdown links and images. Do not use for content rewriting or unscoped recursive vault-wide formatting."
---

# Format Obsidian Notes

Use the bundled deterministic formatter instead of reconstructing whitespace rules ad hoc. Resolve `scripts/format_obsidian_markdown.py` relative to this `SKILL.md`.

## Workflow

1. Resolve each requested Markdown file to an explicit path. Do not pass a directory or silently recurse through a vault.
2. Inspect without writing:

   ```bash
   python3 scripts/format_obsidian_markdown.py --check "/absolute/note.md"
   ```

   Add `--diff` only when a full diff will remain readable.
3. Read the report. Exit code `0` means clean, `1` means formatting is needed, and `2` means the file is unsafe to format.
4. If the user requested a change, write atomically:

   ```bash
   python3 scripts/format_obsidian_markdown.py --write "/absolute/note.md"
   ```

5. Run `--check` again. Confirm `OK`, then report the file changed and summarize the relevant counts or warnings.

## Formatting Contract

- Preserve YAML frontmatter content and keep one blank line after its closing delimiter.
- Convert balanced `\(...\)` only in ATX headings to Obsidian-compatible `$...$`.
- Leave inline-code spans, fenced code blocks, and `$$` display-math contents unchanged.
- Remove ordinary paragraph-spacing blank lines.
- Keep exactly the structural spacing needed around body `---` separators and Markdown tables.
- Keep a blank line after callouts/quotes so they do not absorb following prose.
- Keep a blank line after a list when unindented prose follows it; treat indented continuation lines as part of the list.
- Preserve prose, formulas, links, images, heading levels, and table cells.

## Safety Boundaries

- Use `--check` before `--write`.
- Stop on unclosed frontmatter, fenced code, display math, unbalanced heading math, or inconsistent table columns.
- Treat missing local Markdown links/images as warnings; the formatter does not invent replacement targets.
- Do not validate Obsidian wiki links such as `[[Note]]`, because their resolution depends on vault settings.
- Do not batch an entire directory unless the user explicitly identifies the scope; the script intentionally accepts files only.
- Do not use this skill to revise wording or mathematical content.

## Maintenance

After changing the formatter, run:

```bash
python3 -m unittest discover -s tests -v
```

Then validate the skill folder with the `skill-creator` validator.
