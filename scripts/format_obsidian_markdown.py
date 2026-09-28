#!/usr/bin/env python3
"""Compact and validate explicit Obsidian Markdown files."""

from __future__ import annotations

import argparse
import difflib
import os
import re
import stat
import sys
import tempfile
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


ATX_HEADING_RE = re.compile(r"^#{1,6}\s")
FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE_RE = re.compile(r"(?P<ticks>`+).*?(?P=ticks)")
LIST_MARKER_RE = re.compile(r"^\s*(?:[-+*]|\d+[.)])\s+")
TABLE_LINE_RE = re.compile(r"^\|.*\|$")
YAML_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+:\s*")
HEADING_PAREN_MATH_RE = re.compile(r"\\\((.+?)\\\)")
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")


class FormatError(ValueError):
    """Raised when safe formatting cannot be guaranteed."""


@dataclass(frozen=True)
class Chunk:
    kind: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class FormatResult:
    text: str
    heading_math_converted: int
    blank_lines_before: int
    blank_lines_after: int


@dataclass(frozen=True)
class ValidationReport:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


def _blank_count(lines: Iterable[str]) -> int:
    return sum(1 for line in lines if not line.strip())


def _transform_outside_inline_code(
    line: str, transform
) -> tuple[str, int]:
    pieces: list[str] = []
    converted = 0
    cursor = 0
    for match in INLINE_CODE_RE.finditer(line):
        transformed, count = transform(line[cursor : match.start()])
        pieces.extend((transformed, match.group(0)))
        converted += count
        cursor = match.end()
    transformed, count = transform(line[cursor:])
    pieces.append(transformed)
    return "".join(pieces), converted + count


def _convert_heading_math(line: str) -> tuple[str, int]:
    def replace(segment: str) -> tuple[str, int]:
        return HEADING_PAREN_MATH_RE.subn(
            lambda match: f"${match.group(1)}$", segment
        )

    return _transform_outside_inline_code(line, replace)


def _heading_text_outside_code(line: str) -> str:
    pieces: list[str] = []
    cursor = 0
    for match in INLINE_CODE_RE.finditer(line):
        pieces.append(line[cursor : match.start()])
        cursor = match.end()
    pieces.append(line[cursor:])
    return "".join(pieces)


def _validate_heading(line: str) -> None:
    visible = _heading_text_outside_code(line)
    if r"\(" in visible or r"\)" in visible:
        raise FormatError(
            f"heading still contains unsupported \\(...\\) delimiters: {line}"
        )
    without_escaped = visible.replace(r"\$", "")
    without_display = without_escaped.replace("$$", "")
    if without_display.count("$") % 2:
        raise FormatError(f"heading has unbalanced $ delimiters: {line}")


def _frontmatter_end(lines: Sequence[str]) -> int | None:
    if not lines or lines[0].strip() != "---":
        return None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            return index
    if len(lines) > 1 and YAML_KEY_RE.match(lines[1]):
        raise FormatError("YAML frontmatter starts with --- but is not closed")
    return None


def _fence_end(lines: Sequence[str], start: int) -> int:
    match = FENCE_RE.match(lines[start])
    assert match
    marker = match.group(1)
    char = re.escape(marker[0])
    closing = re.compile(rf"^\s*{char}{{{len(marker)},}}\s*$")
    for index in range(start + 1, len(lines)):
        if closing.match(lines[index]):
            return index
    raise FormatError(f"unclosed fenced code block starting at line {start + 1}")


def _math_end(lines: Sequence[str], start: int) -> int:
    for index in range(start + 1, len(lines)):
        if lines[index].strip() == "$$":
            return index
    raise FormatError(f"unclosed $$ math block starting at line {start + 1}")


def _tokenize(lines: Sequence[str]) -> tuple[list[Chunk], int]:
    chunks: list[Chunk] = []
    converted = 0
    index = 0

    yaml_end = _frontmatter_end(lines)
    if yaml_end is not None:
        chunks.append(Chunk("yaml", tuple(lines[: yaml_end + 1])))
        index = yaml_end + 1

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        if FENCE_RE.match(line):
            end = _fence_end(lines, index)
            chunks.append(Chunk("code", tuple(lines[index : end + 1])))
            index = end + 1
            continue

        if stripped == "$$":
            end = _math_end(lines, index)
            chunks.append(Chunk("math", tuple(lines[index : end + 1])))
            index = end + 1
            continue

        if stripped == "---":
            chunks.append(Chunk("hr", (line,)))
            index += 1
            continue

        if TABLE_LINE_RE.match(line):
            end = index + 1
            while end < len(lines) and TABLE_LINE_RE.match(lines[end]):
                end += 1
            chunks.append(Chunk("table", tuple(lines[index:end])))
            index = end
            continue

        if line.startswith(">"):
            end = index + 1
            while end < len(lines) and lines[end].startswith(">"):
                end += 1
            chunks.append(Chunk("quote", tuple(lines[index:end])))
            index = end
            continue

        if LIST_MARKER_RE.match(line):
            list_lines = [line]
            index += 1
            while index < len(lines):
                candidate = lines[index]
                if not candidate.strip():
                    lookahead = index + 1
                    while (
                        lookahead < len(lines)
                        and not lines[lookahead].strip()
                    ):
                        lookahead += 1
                    if (
                        lookahead < len(lines)
                        and (
                            LIST_MARKER_RE.match(lines[lookahead])
                            or lines[lookahead][:1].isspace()
                        )
                    ):
                        if list_lines[-1] != "":
                            list_lines.append("")
                        index = lookahead
                        continue
                    break
                if LIST_MARKER_RE.match(candidate) or candidate[:1].isspace():
                    list_lines.append(candidate)
                    index += 1
                    continue
                break
            chunks.append(Chunk("list", tuple(list_lines)))
            continue

        if ATX_HEADING_RE.match(line):
            line, count = _convert_heading_math(line)
            converted += count
            _validate_heading(line)
            chunks.append(Chunk("heading", (line,)))
            index += 1
            continue

        chunks.append(Chunk("text", (line,)))
        index += 1

    return chunks, converted


def _append_blank(output: list[str]) -> None:
    if output and output[-1] != "":
        output.append("")


def _render(chunks: Sequence[Chunk]) -> list[str]:
    output: list[str] = []
    for index, chunk in enumerate(chunks):
        next_kind = chunks[index + 1].kind if index + 1 < len(chunks) else None

        if chunk.kind == "yaml":
            output.extend(chunk.lines)
            if next_kind is not None:
                _append_blank(output)
            continue

        if chunk.kind == "hr":
            _append_blank(output)
            output.extend(chunk.lines)
            if next_kind is not None:
                _append_blank(output)
            continue

        if chunk.kind == "table":
            _append_blank(output)
            output.extend(chunk.lines)
            if next_kind is not None:
                _append_blank(output)
            continue

        output.extend(chunk.lines)

        if chunk.kind == "quote" and next_kind is not None:
            _append_blank(output)
        elif (
            chunk.kind == "list"
            and next_kind is not None
            and next_kind not in {"heading", "hr"}
        ):
            _append_blank(output)

    while output and output[-1] == "":
        output.pop()
    return output


def _split_table_row(line: str) -> list[str]:
    content = line.strip()
    if content.startswith("|"):
        content = content[1:]
    if content.endswith("|"):
        content = content[:-1]
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", content)]


def _validate_tables(chunks: Sequence[Chunk]) -> tuple[str, ...]:
    errors: list[str] = []
    for chunk in chunks:
        if chunk.kind != "table":
            continue
        widths = [len(_split_table_row(line)) for line in chunk.lines]
        if widths and len(set(widths)) != 1:
            errors.append(
                "table has inconsistent column counts: "
                + ", ".join(str(width) for width in widths)
            )
    return tuple(errors)


def _local_link_warnings(
    chunks: Sequence[Chunk], source_path: Path | None
) -> tuple[str, ...]:
    if source_path is None:
        return ()
    searchable = "\n".join(
        line
        for chunk in chunks
        if chunk.kind not in {"code", "math"}
        for line in chunk.lines
    )
    warnings: list[str] = []
    for match in MARKDOWN_LINK_RE.finditer(searchable):
        target = match.group(1).strip()
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        if (
            not target
            or target.startswith("#")
            or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target)
        ):
            continue
        target = urllib.parse.unquote(target.split("#", 1)[0])
        if not target:
            continue
        candidate = Path(target)
        if not candidate.is_absolute():
            candidate = source_path.parent / candidate
        if not candidate.exists():
            warnings.append(f"missing local link or image: {target}")
    return tuple(dict.fromkeys(warnings))


def validate_markdown(
    text: str, source_path: Path | None = None
) -> ValidationReport:
    lines = text.splitlines()
    chunks, _ = _tokenize(lines)
    return ValidationReport(
        errors=_validate_tables(chunks),
        warnings=_local_link_warnings(chunks, source_path),
    )


def format_markdown(text: str) -> FormatResult:
    """Return a compact, renderable Obsidian representation of *text*."""
    lines = text.splitlines()
    chunks, converted = _tokenize(lines)
    table_errors = _validate_tables(chunks)
    if table_errors:
        raise FormatError("; ".join(table_errors))
    rendered = _render(chunks)
    formatted = "\n".join(rendered) + "\n"
    return FormatResult(
        text=formatted,
        heading_math_converted=converted,
        blank_lines_before=_blank_count(lines),
        blank_lines_after=_blank_count(rendered),
    )


def _atomic_write(path: Path, text: str) -> None:
    original_mode = stat.S_IMODE(path.stat().st_mode)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_name = handle.name
            handle.write(text)
        os.chmod(temp_name, original_mode)
        os.replace(temp_name, path)
    finally:
        if temp_name and os.path.exists(temp_name):
            os.unlink(temp_name)


def _format_summary(path: Path, result: FormatResult) -> str:
    return (
        f"{path}: heading_math={result.heading_math_converted}, "
        f"blank_lines={result.blank_lines_before}->{result.blank_lines_after}"
    )


def _process_path(
    path: Path, *, write: bool, show_diff: bool
) -> tuple[bool, bool]:
    if not path.exists():
        raise FormatError(f"file does not exist: {path}")
    if not path.is_file():
        raise FormatError(f"only explicit files are supported: {path}")
    if path.suffix.lower() != ".md":
        raise FormatError(f"expected a .md file: {path}")

    original = path.read_text(encoding="utf-8")
    result = format_markdown(original)
    report = validate_markdown(result.text, path)
    if report.errors:
        raise FormatError("; ".join(report.errors))
    for warning in report.warnings:
        print(f"WARN {path}: {warning}", file=sys.stderr)

    changed = result.text != original
    if show_diff and changed:
        sys.stdout.writelines(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                result.text.splitlines(keepends=True),
                fromfile=str(path),
                tofile=f"{path} (formatted)",
            )
        )

    if write and changed:
        _atomic_write(path, result.text)
        print(f"FORMATTED {_format_summary(path, result)}")
    elif changed:
        print(f"NEEDS_FORMAT {_format_summary(path, result)}")
    else:
        print(f"OK {_format_summary(path, result)}")
    return changed, bool(report.warnings)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compact explicit Obsidian Markdown files while preserving YAML, "
            "code fences, math blocks, tables, callouts, and list boundaries."
        )
    )
    parser.add_argument("paths", nargs="+", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="report whether formatting is needed (default)",
    )
    mode.add_argument(
        "--write",
        action="store_true",
        help="atomically write the formatted content",
    )
    parser.add_argument(
        "--diff",
        action="store_true",
        help="show a unified diff when changes are needed",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    needs_format = False
    try:
        for path in args.paths:
            changed, _ = _process_path(
                path, write=args.write, show_diff=args.diff
            )
            needs_format = needs_format or (changed and not args.write)
    except (OSError, UnicodeError, FormatError) as exc:
        print(f"ERROR {exc}", file=sys.stderr)
        return 2
    return 1 if needs_format else 0


if __name__ == "__main__":
    raise SystemExit(main())
