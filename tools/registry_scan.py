# @uadro
# @file    tools/registry_scan.py
# @layer   T0
# @branch  t0.infra.registry
# @desc    Сканер реестра методов: чтение исходников, план (ветви и имена
# @desc    карточек), запись и сверка registry/ на диске; рендер текстов —
# @desc    tools/registry_render.py. Режим --check сверяет реестр
# @desc    без записи.

"""Сканер реестра методов репозитория (ветвь t0.infra.registry).

Сканируются исходники Python (*.py, аннотации "# @...") и исходники
собственных языков (*.uasm, *.ubrk — аннотации "; @...", Этап 4,
SPEC/L4-SELFHOST.txt, раздел 3). План назначает каждому исходнику ветвь,
имя файла карточек и относительный путь; рендер файлов реестра —
tools/registry_render.py (индекс registry/METHODS.txt, индексы ветвей
registry/<ветвь>/INDEX.txt, карточки registry/<ветвь>/<файл>.txt).

Реестр — простой текст UTF-8 без разметки Markdown (.md запрещены).
Запуск:
    python tools/registry_scan.py           — записать файлы реестра
    python tools/registry_scan.py --check   — сверка без записи (для CI)
"""

import os
import sys
from pathlib import Path

# Запуск сценарием (python tools/registry_scan.py) требует корня
# репозитория в sys.path для пакета tools; при запуске модулем (-m)
# он уже есть.
if not __package__:
    sys.path.insert(
        0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import registry_render as render
from tools.registry_render import BRANCH_INDEX_NAME

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIRS = ("tools", "src", "tests")
SOURCE_EXTS = ("*.py", "*.uasm", "*.ubrk")
REGISTRY_DIR = ROOT / "registry"
NO_BRANCH = "no-branch"
CARD_SUFFIX = ".txt"

FILE_KEYS = ("file", "layer", "branch")


# @method _strip_tag(line) -> tuple
# @in    line: str — строка исходного файла
# @out   pair: tuple — (ключ, значение) для строки "# @ключ значение"
# @out   (Python) или "; @ключ значение" (uAsm/uBrick, Этап 4),
# @out   иначе (None, "")
# @does  Распознаёт строки-аннотации обоих видов: после маркера
# @does  комментария (# или ;) идёт пробел и "@ключ значение"
# @does  (SPEC/L4-SELFHOST.txt, раздел 3).
def _strip_tag(line):
    s = line.strip()
    if not (s.startswith("# @") or s.startswith("; @")):
        return None, ""
    body = s[2:].strip()
    key, _, value = body.partition(" ")
    return key.lstrip("@"), value.strip()


# @method parse_file_header(lines) -> dict
# @in    lines: list[str] — строки файла
# @out   header: dict — поля file, layer, branch, desc (список строк)
# @does  Читает шапку файла: непрерывный блок "# @..." в начале файла.
def parse_file_header(lines):
    header = {"file": "", "layer": "", "branch": "", "desc": []}
    for line in lines:
        key, value = _strip_tag(line)
        if key is None:
            break
        if key == "desc":
            header["desc"].append(value)
        elif key in FILE_KEYS:
            header[key] = value
    return header


# @method parse_method_cards(lines) -> list
# @in    lines: list[str] — строки файла
# @out   cards: list[dict] — карточки с полями name, in, out, does, uses, depends
# @does  Собирает карточки: строка "@method" открывает карточку, последующие
# @does  строки "@in/@out/@does/@uses/@depends" наполняют её, любая другая
# @does  строка закрывает.
def parse_method_cards(lines):
    cards = []
    current = None

    def close():
        nonlocal current
        if current is not None:
            cards.append(current)
            current = None

    for line in lines:
        key, value = _strip_tag(line)
        if key == "method":
            close()
            current = {
                "name": value,
                "in": [],
                "out": [],
                "does": [],
                "uses": [],
                "depends": [],
            }
        elif current is not None and key in render.CARD_KEYS:
            current[key].append(value)
        else:
            close()
    close()
    return cards


# @method collect_sources() -> list
# @in    нет
# @out   paths: list[Path] — отсортированные исходники расширений
# @out   SOURCE_EXTS (*.py, *.uasm, *.ubrk) из каталогов исходников
# @does  Обходит существующие каталоги SOURCE_DIRS и собирает файлы
# @does  расширений SOURCE_EXTS: Python-инструменты и исходники
# @does  собственных языков (SPEC/L4-SELFHOST.txt, раздел 3).
def collect_sources():
    paths = []
    for name in SOURCE_DIRS:
        base = ROOT / name
        if base.is_dir():
            for pattern in SOURCE_EXTS:
                paths.extend(sorted(base.rglob(pattern)))
    return paths


# @method read_entries() -> list
# @in    нет
# @out   entries: list[dict] — элементы: path, header, cards
# @does  Читает все исходники и разбирает шапки и карточки.
# @depends collect_sources, parse_file_header, parse_method_cards
def read_entries():
    entries = []
    for path in collect_sources():
        lines = path.read_text(encoding="utf-8").splitlines()
        entries.append({
            "path": path,
            "header": parse_file_header(lines),
            "cards": parse_method_cards(lines),
        })
    return entries


# @method branch_of(entry) -> str
# @in    entry: dict — элемент реестра (path, header, cards)
# @out   branch: str — имя ветви или no-branch, если в шапке нет ветви
# @does  Достаёт имя ветви из шапки файла.
def branch_of(entry):
    return entry["header"]["branch"] or NO_BRANCH


# @method rel_path(entry) -> str
# @in    entry: dict — элемент реестра (path, header, cards)
# @out   rel: str — путь файла относительно корня репозитория
# @does  Преобразует путь в POSIX-вид для плана реестра.
def rel_path(entry):
    return entry["path"].relative_to(ROOT).as_posix()


# @method card_name_for(entry, used) -> str
# @in    entry: dict — элемент реестра (path, header, cards)
# @in    used: set[str] — уже занятые имена карточек этой ветви
# @out   name: str — имя файла карточек, уникальное внутри ветви
# @does  Строит имя карточек из имени исходника; при совпадении имён
# @does  внутри ветви добавляет числовой суффикс. Имена сравниваются
# @does  без учёта регистра (файловые системы узла могут не различать
# @does  регистр); имя индекса ветви (INDEX.txt) занято и карточкам
# @does  не выдаётся.
def card_name_for(entry, used):
    stem = entry["path"].stem
    name = stem + CARD_SUFFIX
    taken = {u.lower() for u in used}
    n = 2
    while name.lower() in taken:
        name = f"{stem}_{n}{CARD_SUFFIX}"
        n += 1
    used.add(name)
    return name


# @method plan_registry(entries) -> list
# @in    entries: list[dict] — элементы реестра
# @out   plan: list[dict] — элементы: branch, entry, card (имя файла
# @out   карточек), rel (путь исходника)
# @does  Назначает каждому исходнику его ветвь, имя файла карточек
# @does  и относительный путь; имя индекса ветви резервируется
# @does  в каждой ветви (BRANCH_INDEX_NAME).
# @depends branch_of, rel_path, card_name_for
def plan_registry(entries):
    plan = []
    used_by_branch = {}
    for entry in entries:
        branch = branch_of(entry)
        used = used_by_branch.setdefault(branch, {BRANCH_INDEX_NAME})
        plan.append({"branch": branch, "entry": entry, "rel": rel_path(entry),
                     "card": card_name_for(entry, used)})
    return plan


# @method scan_repository() -> dict
# @in    нет
# @out   files: dict — имя файла -> текст реестра для текущих исходников
# @does  Обходит исходники, строит план и рендерит все файлы реестра.
# @depends read_entries, plan_registry, render.render_all
def scan_repository():
    return render.render_all(plan_registry(read_entries()))


# @method check_registry(files) -> list
# @in    files: dict — имя файла -> ожидаемый текст
# @out   problems: list[str] — расхождения (пустой список = реестр актуален)
# @does  Сверяет ожидаемый реестр с файлами на диске, включая любые
# @does  лишние файлы во всех подкаталогах registry/.
def check_registry(files):
    problems = []
    for name in sorted(files):
        path = REGISTRY_DIR / name
        actual = path.read_text(encoding="utf-8") if path.exists() else None
        if actual != files[name]:
            problems.append(f"не актуален: registry/{name}")
    for path in sorted(REGISTRY_DIR.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(REGISTRY_DIR).as_posix()
        if rel not in files:
            problems.append(f"лишний файл: registry/{rel}")
    return problems


# @method remove_extra_files(files) -> None
# @in    files: dict — имя файла -> текст; набор файлов, который должен существовать
# @out   нет
# @does  Удаляет в registry/ файлы вне ожидаемого набора и опустевшие
# @does  подкаталоги ветвей.
def remove_extra_files(files):
    for path in sorted(REGISTRY_DIR.rglob("*")):
        if path.is_file():
            rel = path.relative_to(REGISTRY_DIR).as_posix()
            if rel not in files:
                path.unlink()
    dirs = [p for p in REGISTRY_DIR.rglob("*") if p.is_dir()]
    for path in sorted(dirs, key=lambda p: len(p.parts), reverse=True):
        if not any(path.iterdir()):
            path.rmdir()


# @method write_registry(files) -> None
# @in    files: dict — имя файла -> текст
# @out   нет; файлы registry/ перезаписываются, лишние удаляются
# @does  Записывает реестр на диск, создавая подкаталоги ветвей.
# @depends remove_extra_files
def write_registry(files):
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        path = REGISTRY_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    remove_extra_files(files)


# @method main(argv) -> int
# @in    argv: list[str] — аргументы командной строки
# @out   code: int — 0 — успех; 1 — реестр устарел (только для --check)
# @does  Без --check записывает реестр; с --check сверяет без записи.
# @depends scan_repository, check_registry, write_registry
def main(argv):
    files = scan_repository()
    if "--check" in argv:
        problems = check_registry(files)
        for line in problems:
            print(line)
        if problems:
            print("УСТАРЕЛ: перегенерируйте: python tools/registry_scan.py")
            return 1
        print("OK: реестр методов актуален")
        return 0
    write_registry(files)
    print(f"Записано файлов реестра: {len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
