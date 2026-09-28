from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "format_obsidian_markdown.py"
)
SPEC = importlib.util.spec_from_file_location("format_obsidian_markdown", SCRIPT)
assert SPEC and SPEC.loader
FORMATTER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = FORMATTER
SPEC.loader.exec_module(FORMATTER)


MESSY_NOTE = r"""---
title: Demo

tags:
  - test
---


# 观察 \(g^{(2)}\)


第一段。


第二段。

- 项目一
- 项目二
列表后的正文。


| 量 | 值 |
|---|---|
| z | 2 |


> [!note] 提示
> 内容
引用后的正文。


---


## 动力学 \(z\)
公式：
$$

x = 1

$$
```md

# 代码中的 \(x\)

```
"""


EXPECTED_NOTE = r"""---
title: Demo

tags:
  - test
---

# 观察 $g^{(2)}$
第一段。
第二段。
- 项目一
- 项目二

列表后的正文。

| 量 | 值 |
|---|---|
| z | 2 |

> [!note] 提示
> 内容

引用后的正文。

---

## 动力学 $z$
公式：
$$

x = 1

$$
```md

# 代码中的 \(x\)

```
"""


class FormatMarkdownTests(unittest.TestCase):
    def test_compacts_and_repairs_obsidian_blocks(self) -> None:
        result = FORMATTER.format_markdown(MESSY_NOTE)
        self.assertEqual(result.text, EXPECTED_NOTE)
        self.assertEqual(result.heading_math_converted, 2)

    def test_is_idempotent(self) -> None:
        first = FORMATTER.format_markdown(MESSY_NOTE).text
        second = FORMATTER.format_markdown(first).text
        self.assertEqual(second, first)

    def test_preserves_indented_math_inside_a_list(self) -> None:
        source = "- 激活弛豫\n  $$\n  x=1\n  $$\n- 下一项\n正文\n"
        expected = "- 激活弛豫\n  $$\n  x=1\n  $$\n- 下一项\n\n正文\n"
        self.assertEqual(FORMATTER.format_markdown(source).text, expected)

    def test_rejects_unclosed_math_and_malformed_tables(self) -> None:
        with self.assertRaises(FORMATTER.FormatError):
            FORMATTER.format_markdown("正文\n$$\nx=1\n")
        with self.assertRaises(FORMATTER.FormatError):
            FORMATTER.format_markdown(
                "| A | B |\n|---|---|\n| one cell |\n"
            )

    def test_cli_check_then_atomic_write_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            note = Path(directory) / "note.md"
            note.write_text(
                "# 标题 \\(z\\)\n\n\n正文一。\n\n正文二。\n",
                encoding="utf-8",
            )

            check = subprocess.run(
                [sys.executable, str(SCRIPT), "--check", str(note)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(check.returncode, 1)
            self.assertIn("NEEDS_FORMAT", check.stdout)
            self.assertIn(r"\(z\)", note.read_text(encoding="utf-8"))

            write = subprocess.run(
                [sys.executable, str(SCRIPT), "--write", str(note)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(write.returncode, 0)
            self.assertIn("FORMATTED", write.stdout)
            self.assertEqual(
                note.read_text(encoding="utf-8"),
                "# 标题 $z$\n正文一。\n正文二。\n",
            )

            clean = subprocess.run(
                [sys.executable, str(SCRIPT), "--check", str(note)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(clean.returncode, 0)
            self.assertIn("OK", clean.stdout)

    def test_local_link_audit_ignores_urls_and_code_examples(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            note = root / "note.md"
            (root / "exists.png").write_bytes(b"image")
            text = (
                "![ok](exists.png)\n"
                "[web](https://example.com)\n"
                "[missing](missing.md)\n"
                "```md\n"
                "[example only](also-missing.md)\n"
                "```\n"
            )
            report = FORMATTER.validate_markdown(text, note)
            self.assertEqual(report.errors, ())
            self.assertEqual(
                report.warnings,
                ("missing local link or image: missing.md",),
            )


if __name__ == "__main__":
    unittest.main()
