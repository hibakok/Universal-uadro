# @uadro
# @file    tools/registry_scan.py
# @layer   T0
# @branch  t0.infra.registry
# @desc    Генератор реестра методов: индекс registry/METHODS.md и карточки
# @desc    по исходным файлам registry/<ветвь>/<файл>.md. Режим --check
# @desc    сверяет реестр без записи.

"""Реестр методов репозитория: индекс + карточки по исходным файлам.

Карточки одного исходного файла живут в registry/<ветвь>/<файл>.md:
файл карточек не растёт вместе с ветвью и не упирается в лимит строк.

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


# @method rel_path(entry) -> str
# @in    entry: dict — элемент реестра (path, header, cards)
# @out   rel: str — путь файла относительно корня репозитория
# @does  Преобразует путь в POSIX-вид для реестра.
def rel_path(entry):
    return entry["path"].relative_to(ROOT).as_posix()


# @method card_name_for(entry, used) -> str
# @in    entry: dict — элемент реестра (path, header, cards)
# @in    used: set[str] — уже занятые имена карточек этой ветви
# @out   name: str — имя файла карточек, уникальное внутри ветви
# @does  Строит имя карточек из имени исходника; при совпадении имён
# @does  внутри ветви добавляет числовой суффикс.
def card_name_for(entry, used):
    stem = entry["path"].stem
    name = stem + ".md"
    n = 2
    while name in used:
        name = f"{stem}_{n}.md"
        n += 1
    used.add(name)
    return name


# @method plan_registry(entries) -> list
# @in    entries: list[dict] — элементы реестра
# @out   plan: list[dict] — элементы: branch, entry, card (имя файла карточек)
# @does  Назначает каждому исходнику его ветвь и имя файла карточек.
# @depends branch_of, card_name_for
def plan_registry(entries):
    plan = []
    used_by_branch = {}
    for entry in entries:
        branch = branch_of(entry)
        used = used_by_branch.setdefault(branch, set())
        plan.append({"branch": branch, "entry": entry,
                     "card": card_name_for(entry, used)})
    return plan


# @method group_plan_by_branch(plan) -> dict
# @in    plan: list[dict] — план реестра
# @out   groups: dict — ветвь -> элементы плана в порядке обхода
# @does  Группирует элементы плана по ветвям.
def group_plan_by_branch(plan):
    groups = {}
    for item in plan:
        groups.setdefault(item["branch"], []).append(item)
    return groups


# @method sort_plan_branches(groups) -> list
# @in    groups: dict — ветвь -> элементы плана
# @out   names: list[str] — имена ветвей в стабильном порядке (слой, имя)
# @does  Даёт стабильный порядок ветвей в индексе реестра.
def sort_plan_branches(groups):
    def layer_of(branch):
        return groups[branch][0]["entry"]["header"]["layer"]

    return sorted(groups, key=lambda b: (layer_of(b), b))


# @method render_cards(entry) -> list
# @in    entry: dict — элемент реестра (path, header, cards)
# @out   lines: list[str] — markdown-строки: карточки методов файла
# @does  Рендерит карточки методов; файл без методов даёт пометку.
def render_cards(entry):
    if not entry["cards"]:
        return ["_Методов нет._", ""]
    lines = []
    for card in entry["cards"]:
        lines.append(f"### {card['name']}")
        lines.append("")
        for key in CARD_KEYS:
            for item in card[key]:
                lines.append(f"- **{CARD_TITLES[key]}:** {item}")
        lines.append("")
    return lines


# @method render_card_file(item) -> str
# @in    item: dict — элемент плана реестра (branch, entry, card)
# @out   text: str — текст файла registry/<ветвь>/<файл>.md
# @does  Собирает карточки одного исходного файла: шапка с ветвью, слоем
# @does  и описанием, затем карточки методов.
# @depends rel_path, render_cards
def render_card_file(item):
    entry = item["entry"]
    layer = entry["header"]["layer"] or "?"
    lines = [
        f"# Карточки файла {rel_path(entry)}",
        "",
        f"Ветвь {item['branch']}, слой {layer}, методов:"
        f" {len(entry['cards'])}. Генерируется `tools/registry_scan.py`;"
        " вручную не редактировать.",
        "",
    ]
    if entry["header"]["desc"]:
        lines.append("_" + " ".join(entry["header"]["desc"]) + "_")
        lines.append("")
    lines.extend(render_cards(entry))
    return "\n".join(lines)


# @method render_index(plan) -> str
# @in    plan: list[dict] — план реестра: branch, entry, card на исходник
# @out   text: str — текст индекса registry/METHODS.md
# @does  Формирует компактный индекс: ветви, их файлы со ссылками на карточки
# @does  и числом методов, плюс итог по репозиторию.
# @depends group_plan_by_branch, sort_plan_branches, rel_path
def render_index(plan):
    groups = group_plan_by_branch(plan)
    lines = [
        "# Реестр методов — индекс",
        "",
        "Индекс генерируется `tools/registry_scan.py`; вручную не редактировать.",
        "Карточки методов исходного файла — в `registry/<ветвь>/<файл>.md`.",
        "",
    ]
    total = 0
    for branch in sort_plan_branches(groups):
        items = groups[branch]
        layer = items[0]["entry"]["header"]["layer"] or "?"
        methods = sum(len(i["entry"]["cards"]) for i in items)
        total += methods
        lines.append(f"## [{layer}] {branch} — методов: {methods}")
        lines.append("")
        for item in items:
            entry = item["entry"]
            desc = " ".join(entry["header"]["desc"]) or "_без описания_"
            link = f"[{rel_path(entry)}]({branch}/{item['card']})"
            lines.append(f"- {link} — {desc} — методов: {len(entry['cards'])}")
        lines.append("")
    lines.append(f"**Всего методов: {total}**")
    lines.append("")
    return "\n".join(lines)


# @method render_all(entries) -> dict
# @in    entries: list[dict] — элементы реестра
# @out   files: dict — имя файла -> текст (индекс + карточки по файлам)
# @does  Рендерит весь реестр целиком.
# @depends plan_registry, render_index, render_card_file
def render_all(entries):
    plan = plan_registry(entries)
    files = {INDEX_NAME: render_index(plan)}
    for item in plan:
        files[f"{item['branch']}/{item['card']}"] = render_card_file(item)
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
# @does  Сверяет ожидаемый реестр с файлами на диске, включая лишние файлы
# @does  во всех подкаталогах registry/.
def check_registry(files):
    problems = []
    for name in sorted(files):
        path = REGISTRY_DIR / name
        actual = path.read_text(encoding="utf-8") if path.exists() else None
        if actual != files[name]:
            problems.append(f"не актуален: registry/{name}")
    for path in sorted(REGISTRY_DIR.rglob("*.md")):
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
