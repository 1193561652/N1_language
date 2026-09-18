from __future__ import annotations

import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIBRARY = ROOT / "library2"
OUTPUT = ROOT / "output"
TOOLS = ROOT / "tools"
REPORT = OUTPUT / "library2_aistudio" / "library2文件重命名记录.md"

TEXT_SUFFIXES = {
    ".md",
    ".txt",
    ".json",
    ".jsonl",
    ".py",
    ".ps1",
}


def normalize_filename(name: str) -> str:
    return name.replace(" ", "_").replace("【", "").replace("】", "")


def collect_file_renames() -> list[tuple[Path, Path]]:
    renames: list[tuple[Path, Path]] = []
    for path in sorted(LIBRARY.rglob("*")):
        if not path.is_file():
            continue
        new_name = normalize_filename(path.name)
        if new_name != path.name:
            renames.append((path, path.with_name(new_name)))
    return renames


def check_collisions(renames: list[tuple[Path, Path]]) -> None:
    target_counts: dict[str, list[Path]] = {}
    for src, dst in renames:
        key = str(dst).lower()
        target_counts.setdefault(key, []).append(src)

    collisions = {key: srcs for key, srcs in target_counts.items() if len(srcs) > 1}
    existing_conflicts = [
        (src, dst) for src, dst in renames if dst.exists() and dst.resolve() != src.resolve()
    ]

    if collisions or existing_conflicts:
        lines = ["重命名存在冲突，已停止："]
        for key, srcs in collisions.items():
            lines.append(f"- 目标重复：{key}")
            for src in srcs:
                lines.append(f"  - {src}")
        for src, dst in existing_conflicts:
            lines.append(f"- 目标已存在：{src} -> {dst}")
        raise SystemExit("\n".join(lines))


def make_replacements(renames: list[tuple[Path, Path]]) -> list[tuple[str, str]]:
    replacements: list[tuple[str, str]] = []
    for src, dst in renames:
        src_abs = str(src)
        dst_abs = str(dst)
        src_rel = str(src.relative_to(ROOT))
        dst_rel = str(dst.relative_to(ROOT))

        variants = {
            (src_abs, dst_abs),
            (src_abs.replace("\\", "/"), dst_abs.replace("\\", "/")),
            (src_rel, dst_rel),
            (src_rel.replace("\\", "/"), dst_rel.replace("\\", "/")),
            (src.name, dst.name),
        }
        replacements.extend(sorted(variants, key=lambda item: len(item[0]), reverse=True))

    replacements.sort(key=lambda item: len(item[0]), reverse=True)
    return replacements


def update_text_records(replacements: list[tuple[str, str]]) -> list[Path]:
    roots = [OUTPUT, TOOLS]
    changed: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            new_text = text
            for old, new in replacements:
                new_text = new_text.replace(old, new)
            if new_text != text:
                path.write_text(new_text, encoding="utf-8")
                changed.append(path)
    return changed


def write_report(renames: list[tuple[Path, Path]], changed_records: list[Path]) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# library2文件重命名记录",
        "",
        "规则：文件名中的空格替换为 `_`；删除 `【` 和 `】`；括号内序号或文字保留。",
        "",
        "## 重命名文件",
        "",
        "| 原文件 | 新文件 |",
        "|---|---|",
    ]
    for src, dst in renames:
        lines.append(f"| `{src}` | `{dst}` |")

    lines.extend(["", "## 已同步更新的本地记录/脚本", ""])
    if changed_records:
        for path in changed_records:
            lines.append(f"- `{path}`")
    else:
        lines.append("- 无")

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if not LIBRARY.exists():
        raise SystemExit(f"找不到目录：{LIBRARY}")

    renames = collect_file_renames()
    check_collisions(renames)
    replacements = make_replacements(renames)

    for src, dst in renames:
        os.replace(src, dst)

    changed_records = update_text_records(replacements)
    write_report(renames, changed_records)

    print(f"renamed files: {len(renames)}")
    print(f"updated text records: {len(changed_records)}")
    print(f"report: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

