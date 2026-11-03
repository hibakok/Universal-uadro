# @uadro
# @file    tools/registry_scan.py
# @layer   T0
# @branch  t0.infra.registry
# @desc    Генератор реестра методов: индекс registry/METHODS.md и карточки
# @desc    ветвей registry/<ветвь>.md. Режим --check сверяет реестр без записи.

"""Реестр методов репозитория: индекс + карточки по ветвям.

Запуск:
    python tools/registry_scan.py           — записать файлы реестра
    python tools/registry_scan.py --check   — сверка без записи (для CI)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIRS = ("tools", "src", "tests")
REGISTRY_DIR = ROOT / "registry"
INDEX_NAME = "METHODS.md"
NO_BRANCH = "no-branch"

FILE_KEYS = ("file", "layer", "branch")
CARD_KEYS = ("in", "out", "does", "uses", "depends")
CARD_TITLES = {
    "in": "вход",
    "out": "выход",
    "does": "функция",
    "uses": "использует",
    "depends": "зависимости",
}


# @method _strip_tag(line) -> tuple
# @in    line: str — строка исходного файла
# @out   pair: tuple — (ключ, значение) для строки "# @ключ значение", иначе (None, "")
# @does  Распознаёт строки-аннотации "# @ключ значение".
def _strip_tag(line):
    s = line.strip()
    if not s.startswith("# @"):
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
        elif current is not None and key in CARD_KEYS:
            current[key].append(value)
        else:
            close()
    close()
    return cards


# @method collect_sources() -> list
# @in    нет
# @out   paths: list[Path] — отсортированные *.py из каталогов исходников
# @does  Обходит существующие каталоги SOURCE_DIRS и собирает .py-файлы.
def collect_sources():
    paths = []
    for name in SOURCE_DIRS:
        base = ROOT / name
        if base.is_dir():
            paths.extend(sorted(base.rglob("*.py")))
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


# @method group_by_branch(entries) -> dict
# @in    entries: list[dict] — элементы реестра
# @out   groups: dict — ветвь -> список элементов в порядке обхода
# @does  Группирует файлы по ветвям.
# @depends branch_of
def group_by_branch(entries):
    groups = {}
    for entry in entries:
        groups.setdefault(branch_of(entry), []).append(entry)
    return groups


# @method sort_branches(groups) -> list
# @in    groups: dict — ветвь -> список элементов
# @out   names: list[str] — имена ветвей в стабильном порядке (слой, имя)
# @does  Даёт стабильный порядок ветвей в реестре.
def sort_branches(groups):
    return sorted(groups, key=lambda b: (groups[b][0]["header"]["layer"], b))


# @method rel_path(entry) -> str
# @in    entry: dict — элемент реестра (path, header, cards)
# @out   rel: str — путь файла относительно корня репозитория
# @does  Преобразует путь в POSIX-вид для реестра.
def rel_path(entry):
    return entry["path"].relative_to(ROOT).as_posix()


# @method render_cards(entry) -> list
# @in    entry: dict — элемент реестра (path, header, cards)
# @out   lines: list[str] — markdown-строки: раздел файла с карточками методов
# @does  Рендерит заголовок файла и карточки его методов.
def render_cards(entry):
    lines = [f"## {rel_path(entry)}", ""]
    if entry["header"]["desc"]:
        lines.append("_" + " ".join(entry["header"]["desc"]) + "_")
        lines.append("")
    if not entry["cards"]:
        lines.append("_Методов нет._")
        lines.append("")
    for card in entry["cards"]:
        lines.append(f"### {card['name']}")
        lines.append("")
        for key in CARD_KEYS:
            for item in card[key]:
                lines.append(f"- **{CARD_TITLES[key]}:** {item}")
        lines.append("")
    return lines


# @method branch_file_name(branch) -> str
# @in    branch: str — имя ветви
# @out   name: str — имя файла карточек ветви
# @does  Преобразует имя ветви в имя файла реестра (ветвь.md).
def branch_file_name(branch):
    return branch + ".md"


# @method render_branch_file(branch, entries) -> str
# @in    branch: str — имя ветви
# @in    entries: list[dict] — файлы ветви
# @out   text: str — текст файла registry/<ветвь>.md
# @does  Собирает карточки всех файлов ветви в один файл реестра.
# @depends render_cards
def render_branch_file(branch, entries):
    layer = entries[0]["header"]["layer"] or "?"
    total = sum(len(entry["cards"]) for entry in entries)
    lines = [
        f"# Карточки ветви {branch}",
        "",
        f"Слой {layer}, методов: {total}. Генерируется"
        " `tools/registry_scan.py`; вручную не редактировать.",
        "",
    ]
    for entry in entries:
        lines.extend(render_cards(entry))
    return "\n".join(lines)


# @method render_index(groups) -> str
# @in    groups: dict — ветвь -> список элементов
# @out   text: str — текст индекса registry/METHODS.md
# @does  Формирует компактный индекс: ветви, их файлы, число методов.
# @depends sort_branches, rel_path, branch_file_name
def render_index(groups):
    lines = [
        "# Реестр методов — индекс",
        "",
        "Индекс генерируется `tools/registry_scan.py`; вручную не редактировать.",
        "Карточки методов ветви — в `registry/<ветвь>.md`.",
        "",
    ]
    total = 0
    for branch in sort_branches(groups):
        entries = groups[branch]
        layer = entries[0]["header"]["layer"] or "?"
        methods = sum(len(entry["cards"]) for entry in entries)
        total += methods
        lines.append(f"## [{layer}] {branch} — методов: {methods}")
        lines.append("")
        for entry in entries:
            desc = " ".join(entry["header"]["desc"]) or "_без описания_"
            lines.append(f"- {rel_path(entry)} — {desc}")
        lines.append(f"- карточки: `registry/{branch_file_name(branch)}`")
        lines.append("")
    lines.append(f"**Всего методов: {total}**")
    lines.append("")
    return "\n".join(lines)


# @method render_all(entries) -> dict
# @in    entries: list[dict] — элементы реестра
# @out   files: dict — имя файла -> текст (индекс + карточки ветвей)
# @does  Рендерит весь реестр целиком.
# @depends group_by_branch, render_index, render_branch_file, branch_file_name
def render_all(entries):
    groups = group_by_branch(entries)
    files = {INDEX_NAME: render_index(groups)}
    for branch, group in groups.items():
        files[branch_file_name(branch)] = render_branch_file(branch, group)
    return files


# @method scan_repository() -> dict
# @in    нет
# @out   files: dict — имя файла -> текст реестра для текущих исходников
# @does  Обходит исходники и рендерит все файлы реестра.
# @depends read_entries, render_all
def scan_repository():
    return render_all(read_entries())


# @method check_registry(files) -> list
# @in    files: dict — имя файла -> ожидаемый текст
# @out   problems: list[str] — расхождения (пустой список = реестр актуален)
# @does  Сверяет ожидаемый реестр с файлами на диске, включая лишние файлы.
def check_registry(files):
    problems = []
    for name in sorted(files):
        path = REGISTRY_DIR / name
        actual = path.read_text(encoding="utf-8") if path.exists() else None
        if actual != files[name]:
            problems.append(f"не актуален: registry/{name}")
    for path in sorted(REGISTRY_DIR.glob("*.md")):
        if path.name not in files:
            problems.append(f"лишний файл: registry/{path.name}")
    return problems


# @method write_registry(files) -> None
# @in    files: dict — имя файла -> текст
# @out   нет; файлы registry/ перезаписываются, лишние удаляются
# @does  Записывает реестр на диск.
def write_registry(files):
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in files.items():
        (REGISTRY_DIR / name).write_text(text, encoding="utf-8")
    for path in REGISTRY_DIR.glob("*.md"):
        if path.name not in files:
            path.unlink()


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
