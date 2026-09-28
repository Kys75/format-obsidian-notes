# format-obsidian-notes · Obsidian 笔记格式整理

针对明确指定的 Markdown 文件整理空行、修复标题中的数学分隔符，并检查部分结构与本地链接。用于排版整理，不用于改写正文。

由 [Kys75](https://github.com/Kys75) 维护，初始内容整理自作者本机使用的 Skill。仓库根目录就是完整 Skill；核心规则见 [SKILL.md](SKILL.md)。这是独立的 Agent Skill，不是 Obsidian 应用插件。

## 在 Codex 中安装

先确保 Codex 能正常工作，再把下面这段话复制给 Agent。如果仓库为私有，你的 GitHub 账号还需要具备读取权限，并在本机完成相应认证。

```text
请从 https://github.com/Kys75/format-obsidian-notes 安装 format-obsidian-notes。
Skill 位于仓库根目录；如果使用 skill-installer，请指定仓库内路径 .，并把安装名称设为 format-obsidian-notes。
安装到当前用户的 .agents/skills/format-obsidian-notes 目录。
先阅读仓库说明并检查已有同名 Skill；已有时先比较差异，不要直接覆盖。
保留 SKILL.md、agents 以及仓库附带的 scripts、references、assets 等目录。
完成后报告来源版本和实际安装位置，并检查 Skill 能否被识别。
```

此方式适用于 Mac 和 Windows，由 Agent 根据当前系统处理路径。新 Skill 未出现时，先开一个新对话；仍未出现再重启客户端。

### 手动安装（可选，需要 Git）

Mac 终端：

```sh
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/Kys75/format-obsidian-notes.git "$HOME/.agents/skills/format-obsidian-notes"
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force "$HOME/.agents/skills" | Out-Null
git clone https://github.com/Kys75/format-obsidian-notes.git "$HOME/.agents/skills/format-obsidian-notes"
```

最终应直接存在 `.agents/skills/format-obsidian-notes/SKILL.md`。已有同名目录时先比较版本，不要删除或覆盖已有改动。

## 使用示例

```text
请使用 $format-obsidian-notes，先检查我指定的 note.md，说明需要修改的格式问题，再整理它的排版。不要改写正文或数学内容，不要扫描其他文件。完成后重新检查并报告结果。
```

脚本先检查，再按用户要求原子写入。它保留 YAML、围栏代码和显示公式的内容，处理表格、列表与 callout 所需的边界空行。建议第一次使用时先对测试副本操作。

## 依赖

附带脚本和测试需要 Python 3.10 或更新版本，仅使用标准库。运行脚本不需要启动 Obsidian；是否符合你的阅读习惯，需要在自己的 Obsidian 设置下查看结果。

## 检查方法与边界

在本仓库或已安装的 Skill 目录中运行；把示例文件路径替换为自己的文件。使用本机有效的 Python 命令：通常 Mac 为 `python3`，Windows 为 `python` 或 `py`。

```sh
python scripts/format_obsidian_markdown.py --check "path/to/note.md"
python scripts/format_obsidian_markdown.py --write "path/to/note.md"
python scripts/format_obsidian_markdown.py --check "path/to/note.md"
```

检查模式退出码：`0` 表示格式无需调整，`1` 表示需要调整，`2` 表示输入无效或不适合安全处理。必须先查看检查结果，再决定是否运行 `--write`。可用 `--diff` 查看变化。

只接受明确的 `.md` 文件路径，不会递归整理整个笔记库。本地链接缺失会给出警告；`[[Wiki 链接]]` 的解析依赖 Obsidian 设置，不在检查范围内。格式检查不验证正文或科学内容。

运行已有测试：

```sh
python -m unittest discover -s tests -v
```

## 资源

- [格式整理脚本](scripts/format_obsidian_markdown.py)
- [现有测试](tests/test_format_obsidian_markdown.py)

## 更新

请 Agent 对比已安装版本与本仓库的改动，再更新需要的文件；保留本地定制。维护者在本仓库修改源文件，安装目录只是使用副本。安装或更新后记录使用的提交版本，并做一次小任务验证。

当前发布检查覆盖 Skill 结构、资源链接和本机 Python 脚本行为；没有把这些检查等同于所有模型和所有操作系统上的完整任务验收。
