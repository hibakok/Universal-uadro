# @uadro
# @file    tools/registry_render.py
# @layer   T0
# @branch  t0.infra.registry
# @desc    Рендер реестра методов простым текстом: компактный индекс
# @desc    registry/METHODS.txt, индексы ветвей registry/<ветвь>/INDEX.txt
# @desc    и карточки по исходным файлам (сканирование, план и запись —
# @desc    tools/registry_scan.py).

"""Рендер файлов реестра методов (ветвь t0.infra.registry).

Файлы реестра — простой текст UTF-8 без разметки Markdown (.md запрещены):

- registry/METHODS.txt — компактный индекс верхнего уровня: ветви
  с числом файлов и методов и путём индекса ветви; не растёт с числом
  файлов репозитория (лимит строк CHARTER.txt, п. 3);
- registry/<ветвь>/INDEX.txt — индекс ветви: исходники, пути карточек
  и описания из шапок; растёт только с числом файлов ветви;
- registry/<ветвь>/<файл>.txt — карточки методов одного исходного
  файла (вход / выход / функция / зависимости).

Рендер чистый: получает план реестра (tools/registry_scan.py,
plan_registry) и ничего не читает с диска. Запуск генерации:
    python tools/registry_scan.py
"""

LINE_WIDTH = 72
INDEX_NAME = "METHODS.txt"
BRANCH_INDEX_NAME = "INDEX.txt"

CARD_KEYS = ("in", "out", "does", "uses", "depends")
CARD_TITLES = {
    "in": "вход",
    "out": "выход",
    "does": "функция",
    "uses": "использует",
    "depends": "зависимости",
}
LABEL_WIDTH = max(len(t) for t in CARD_TITLES.values()) + 2


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
# @in    item: dict — элемент плана реестра (branch, entry, card, rel)
# @out   text: str — текст файла registry/<ветвь>/<файл>.txt
# @does  Собирает карточки одного исходного файла: шапка с ветвью, слоем
# @does  и описанием, затем карточки методов.
# @depends render_cards, wrap_words
def render_card_file(item):
    entry = item["entry"]
    layer = entry["header"]["layer"] or "?"
    lines = [
        "КАРТОЧКИ ФАЙЛА " + item["rel"],
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
# @does  Даёт стабильный порядок ветвей в индексах реестра.
def sort_plan_branches(groups):
    def layer_of(branch):
        return groups[branch][0]["entry"]["header"]["layer"]

    return sorted(groups, key=lambda b: (layer_of(b), b))


# @method render_branch_index(branch, items) -> str
# @in    branch: str — имя ветви
# @in    items: list[dict] — элементы плана ветви (branch, entry, card, rel)
# @out   text: str — текст индекса ветви registry/<ветвь>/INDEX.txt
# @does  Перечисляет исходники ветви: путь, число методов, путь карточек
# @does  и описание из шапки файла; растёт только с числом файлов ветви,
# @does  поэтому индекс верхнего уровня не перечисляет файлы (лимит
# @does  строк CHARTER.txt, п. 3).
# @depends wrap_words
def render_branch_index(branch, items):
    layer = items[0]["entry"]["header"]["layer"] or "?"
    lines = [
        "ИНДЕКС ВЕТВИ " + branch + " [слой " + layer + "]",
        "",
        "Индекс генерируется tools/registry_scan.py; вручную не редактировать.",
        "Карточки методов исходного файла — registry/" + branch + "/<файл>.txt.",
        "",
    ]
    for item in items:
        entry = item["entry"]
        lines.append("- " + item["rel"] + " — методов: "
                     + str(len(entry["cards"])))
        lines.append("  карточки: registry/" + branch + "/" + item["card"])
        desc = " ".join(entry["header"]["desc"]) or "без описания"
        label = "  описание: "
        body = wrap_words(desc, LINE_WIDTH - len(label))
        lines.append(label + body[0])
        for part in body[1:]:
            lines.append(" " * len(label) + part)
    lines.append("")
    return "\n".join(lines)


# @method render_index(groups) -> str
# @in    groups: dict — ветвь -> элементы плана (group_plan_by_branch)
# @out   text: str — текст индекса registry/METHODS.txt
# @does  Формирует компактный индекс верхнего уровня: ветви с числом
# @does  файлов и методов и путём индекса ветви; файлы и описания
# @does  перечисляет индекс ветви, поэтому индекс не растёт с числом
# @does  файлов репозитория (лимит строк CHARTER.txt, п. 3).
# @depends sort_plan_branches
def render_index(groups):
    lines = [
        "РЕЕСТР МЕТОДОВ — ИНДЕКС",
        "",
        "Индекс генерируется tools/registry_scan.py; вручную не редактировать.",
        "Файлы и описания ветви — registry/<ветвь>/" + BRANCH_INDEX_NAME
        + ", карточки",
        "методов исходного файла — registry/<ветвь>/<файл>.txt.",
        "",
    ]
    total = 0
    for branch in sort_plan_branches(groups):
        items = groups[branch]
        methods = sum(len(i["entry"]["cards"]) for i in items)
        total += methods
        lines.append("ВЕТВЬ " + branch + " [слой "
                     + (items[0]["entry"]["header"]["layer"] or "?")
                     + "] — файлов: " + str(len(items))
                     + ", методов: " + str(methods))
        lines.append("  индекс: registry/" + branch + "/" + BRANCH_INDEX_NAME)
        lines.append("")
    lines.append("ВСЕГО ВЕТВЕЙ: " + str(len(groups)))
    lines.append("ВСЕГО МЕТОДОВ: " + str(total))
    lines.append("")
    return "\n".join(lines)


# @method render_all(plan) -> dict
# @in    plan: list[dict] — план реестра: branch, entry, card, rel
# @out   files: dict — имя файла -> текст: индекс, индексы ветвей
# @out   и карточки по исходным файлам
# @does  Рендерит весь реестр целиком по плану.
# @depends group_plan_by_branch, sort_plan_branches, render_index,
# @depends render_branch_index, render_card_file
def render_all(plan):
    groups = group_plan_by_branch(plan)
    files = {INDEX_NAME: render_index(groups)}
    for branch in sort_plan_branches(groups):
        files[f"{branch}/{BRANCH_INDEX_NAME}"] = render_branch_index(
            branch, groups[branch])
    for item in plan:
        files[f"{item['branch']}/{item['card']}"] = render_card_file(item)
    return files
