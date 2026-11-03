# @uadro
# @file    tools/check_limits.py
# @layer   T0
# @branch  t0.infra.registry
# @desc    Проверка лимита строк: каждый файл репозитория не длиннее 500 строк.

"""Проверка размера файлов репозитория.

Запуск: python tools/check_limits.py
Код завершения: 0 — все файлы в лимите; 1 — есть нарушения.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LIMIT = 500
SKIP_DIRS = {".git", "__pycache__"}


# @method iter_repo_files(root) -> iterator
# @in    root: Path — корень репозитория
# @out   files: итератор Path — файлы без пропускаемых каталогов
# @does  Обходит дерево репозитория, исключая .git и __pycache__.
def iter_repo_files(root):
    for path in root.rglob("*"):
        if path.is_file() and not (SKIP_DIRS & set(path.parts)):
            yield path


# @method count_lines(path) -> int
# @in    path: Path — путь к файлу
# @out   n: int — число строк (0 при ошибке чтения)
# @does  Считает строки текстового файла в кодировке UTF-8.
def count_lines(path):
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return 0


# @method main() -> int
# @in    нет
# @out   code: int — 0 если нарушений нет, иначе 1
# @does  Печатает файлы сверх лимита и возвращает код завершения.
def main():
    violations = []
    checked = 0
    for path in iter_repo_files(ROOT):
        n = count_lines(path)
        checked += 1
        if n > LIMIT:
            violations.append((path.relative_to(ROOT).as_posix(), n))
    for rel, n in sorted(violations):
        print(f"ЛИМИТ: {rel} — {n} строк (максимум {LIMIT})")
    if violations:
        return 1
    print(f"OK: {checked} файлов, все не длиннее {LIMIT} строк")
    return 0


if __name__ == "__main__":
    sys.exit(main())
