# @uadro
# @file    tools/registry_scan.py
# @layer   T0
# @branch  t0.infra.registry
# @desc    Генератор реестра методов: индекс registry/METHODS.txt и карточки
# @desc    по исходным файлам registry/<ветвь>/<файл>.txt. Режим --check
# @desc    сверяет реестр без записи.

"""Реестр методов репозитория: индекс + карточки по исходным файлам.

Карточки одного исходного файла живут в registry/<ветвь>/<файл>.txt:
файл карточек не растёт вместе с ветвью и не упирается в лимит строк.
Реестр — простой текст UTF-8 без разметки Markdown (.md запрещены).

Сканируются исходники Python (*.py, аннотации "# @...") и исходники
собственных языков (*.uasm, *.ubrk — аннотации "; @...", Этап 4,
SPEC/L4-SELFHOST.txt, раздел 3).

Запуск:
    python tools/registry_scan.py           — записать файлы реестра
    python tools/registry_scan.py --check   — сверка без записи (для CI)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIRS = ("tools", "src", "tests")
SOURCE_EXTS = ("*.py", "*.uasm", "*.ubrk")
REGISTRY_DIR = ROOT / "registry"
INDEX_NAME = "METHODS.txt"
NO_BRANCH = "no-branch"
CARD_SUFFIX = ".txt"
LINE_WIDTH = 72

FILE_KEYS = ("file", "layer", "branch")
CARD_KEYS = ("in", "out", "does", "uses", "depends")
CARD_TITLES = {
    "in": "вход",
    "out": "выход",
    "does": "функция",
    "uses": "использует",
    "depends": "зависимости",
}
LABEL_WIDTH = max(len(t) for t in CARD_TITLES.values()) + 2


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
        elif current is not None and key in CARD_KEYS:
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
    name = stem + CARD_SUFFIX
    n = 2
    while name in used:
        name = f"{stem}_{n}{CARD_SUFFIX}"
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


# @method wrap_words(text, width) -> list
# @in    text: str — текст без переводов строк
# @in    width: int — максимальная ширина строки
# @out   lines: list[str] — строки не шире width
# @does  Переносит текст по словам; слово длиннее width занимает строку
# @does  целиком; пустой текст даёт пустой список.
def wrap_words(text, width):
    lines = []
    line = ""
    for word in text.split():
        if not line:
            line = word
        elif len(line) + 1 + len(word) <= width:
            line = line + " " + word
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


# @method merge_items(key, items) -> list
# @in    key: str — ключ поля (in, out, does, uses, depends)
# @in    items: list[str] — значения поля, как в исходнике
# @out   merged: list[str] — абзацы поля после склейки
# @does  Склеивает продолжения: @does — в один текст через пробел;
# @does  @uses и @depends — в один список через запятую; @in и @out
# @does  остаются отдельными строками.
def merge_items(key, items):
    if key == "does":
        return [" ".join(items)] if items else []
    if key in ("uses", "depends"):
        return [", ".join(items)] if items else []
    return list(items)


# @method render_field(title, items, indent) -> list
# @in    title: str — название поля («вход», «функция», ...)
# @in    items: list[str] — абзацы значения поля
# @in    indent: str — отступ поля (по умолчанию два пробела)
# @out   lines: list[str] — строки поля с переносами по словам
# @does  Рендерит поле карточки: первая строка «<indent>метка: текст»,
# @does  продолжения выровнены под началом текста.
# @depends wrap_words
def render_field(title, items, indent="  "):
    lines = []
    label = indent + (title + ":").ljust(LABEL_WIDTH)
    for item in items:
        body = wrap_words(item, LINE_WIDTH - len(label))
        if not body:
            lines.append(label.rstrip())
            continue
        lines.append(label + body[0])
        for part in body[1:]:
            lines.append(" " * len(label) + part)
    return lines


# @method render_card(card) -> list
# @in    card: dict — карточка метода (name, in, out, does, uses, depends)
# @out   lines: list[str] — строки одной карточки в простом тексте
# @does  Рендерит карточку: заголовок «МЕТОД ...» и поля с отступом.
# @depends merge_items, render_field
def render_card(card):
    lines = ["МЕТОД " + card["name"]]
    for key in CARD_KEYS:
        lines.extend(render_field(CARD_TITLES[key], merge_items(key, card[key])))
    lines.append("")
    return lines


# @method render_cards(entry) -> list
# @in    entry: dict — элемент реестра (path, header, cards)
# @out   lines: list[str] — карточки методов файла
# @does  Рендерит карточки методов; файл без методов даёт пометку.
# @depends render_card
def render_cards(entry):
    if not entry["cards"]:
        return ["Методов нет.", ""]
    lines = []
    for card in entry["cards"]:
        lines.extend(render_card(card))
    return lines


# @method render_card_file(item) -> str
# @in    item: dict — элемент плана реестра (branch, entry, card)
# @out   text: str — текст файла registry/<ветвь>/<файл>.txt
# @does  Собирает карточки одного исходного файла: шапка с ветвью, слоем
# @does  и описанием, затем карточки методов.
# @depends rel_path, render_cards, wrap_words
def render_card_file(item):
    entry = item["entry"]
    layer = entry["header"]["layer"] or "?"
    lines = [
        "КАРТОЧКИ ФАЙЛА " + rel_path(entry),
        "",
        "Ветвь: " + item["branch"],
        "Слой: " + layer,
        "Методов: " + str(len(entry["cards"])),
        "Генерируется tools/registry_scan.py; вручную не редактировать.",
    ]
    desc = " ".join(entry["header"]["desc"])
    if desc:
        label = "Описание: "
        body = wrap_words(desc, LINE_WIDTH - len(label))
        lines.append(label + body[0])
        for part in body[1:]:
            lines.append(" " * len(label) + part)
    lines.append("")
    lines.extend(render_cards(entry))
    return "\n".join(lines)


# @method render_index(plan) -> str
# @in    plan: list[dict] — план реестра: branch, entry, card на исходник
# @out   text: str — текст индекса registry/METHODS.txt
# @does  Формирует компактный индекс: ветви, их файлы с путями карточек
# @does  и числом методов, плюс итог по репозиторию.
# @depends group_plan_by_branch, sort_plan_branches, rel_path, wrap_words
def render_index(plan):
    groups = group_plan_by_branch(plan)
    lines = [
        "РЕЕСТР МЕТОДОВ — ИНДЕКС",
        "",
        "Индекс генерируется tools/registry_scan.py; вручную не редактировать.",
        "Карточки методов исходного файла — registry/<ветвь>/<файл>.txt.",
        "",
    ]
    total = 0
    for branch in sort_plan_branches(groups):
        items = groups[branch]
        layer = items[0]["entry"]["header"]["layer"] or "?"
        methods = sum(len(i["entry"]["cards"]) for i in items)
        total += methods
        lines.append("ВЕТВЬ " + branch + " [слой " + layer
                     + "] — методов: " + str(methods))
        lines.append("")
        for item in items:
            entry = item["entry"]
            lines.append("- " + rel_path(entry) + " — методов: "
                         + str(len(entry["cards"])))
            lines.append("  карточки: registry/" + branch + "/" + item["card"])
            desc = " ".join(entry["header"]["desc"]) or "без описания"
            label = "  описание: "
            body = wrap_words(desc, LINE_WIDTH - len(label))
            lines.append(label + body[0])
            for part in body[1:]:
                lines.append(" " * len(label) + part)
        lines.append("")
    lines.append("ВСЕГО МЕТОДОВ: " + str(total))
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
