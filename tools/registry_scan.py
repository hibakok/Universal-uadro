# @uadro
# @file    tools/registry_scan.py
# @layer   T0
# @branch  t0.infra.registry
# @desc    Генератор реестра методов: собирает карточки @method из исходников
# @desc    и пишет registry/METHODS.md. Режим --check только сверяет реестр.

"""Реестр методов репозитория.

Запуск:
    python tools/registry_scan.py           — записать registry/METHODS.md
    python tools/registry_scan.py --check   — сверка без записи (для CI)
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE_DIRS = ("tools", "src", "tests")
OUT_PATH = ROOT / "registry" / "METHODS.md"

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


# @method render_registry(entries) -> str
# @in    entries: list[dict] — элементы: path, header, cards
# @out   text: str — полный текст registry/METHODS.md
# @does  Формирует markdown: раздел на файл, внутри — карточки методов.
def render_registry(entries):
    lines = [
        "# Реестр методов",
        "",
        "Файл генерируется автоматически инструментом `tools/registry_scan.py`.",
        "Вручную не редактировать: карточки методов живут в исходниках (`@method`).",
        "",
    ]
    total = 0
    order = sorted(
        entries,
        key=lambda e: (e["header"]["layer"], e["path"].as_posix()),
    )
    for entry in order:
        header = entry["header"]
        rel = entry["path"].relative_to(ROOT).as_posix()
        lines.append(f"## [{header['layer']}] {rel} — ветвь `{header['branch']}`")
        lines.append("")
        if header["desc"]:
            lines.append(" ".join(header["desc"]))
            lines.append("")
        cards = entry["cards"]
        total += len(cards)
        if not cards:
            lines.append("_Методов нет._")
            lines.append("")
            continue
        for card in cards:
            lines.append(f"### {card['name']}")
            lines.append("")
            for key in CARD_KEYS:
                for item in card[key]:
                    lines.append(f"- **{CARD_TITLES[key]}:** {item}")
            lines.append("")
    lines.append(f"**Всего методов: {total}**")
    lines.append("")
    return "\n".join(lines)


# @method scan_repository() -> str
# @in    нет
# @out   text: str — текст реестра для текущего состояния исходников
# @does  Обходит исходники, парсит шапки и карточки, рендерит реестр.
def scan_repository():
    entries = []
    for path in collect_sources():
        lines = path.read_text(encoding="utf-8").splitlines()
        entries.append({
            "path": path,
            "header": parse_file_header(lines),
            "cards": parse_method_cards(lines),
        })
    return render_registry(entries)


# @method main(argv) -> int
# @in    argv: list[str] — аргументы командной строки
# @out   code: int — 0 — успех; 1 — реестр устарел (только для --check)
# @does  Без --check записывает реестр; с --check сверяет без записи.
def main(argv):
    text = scan_repository()
    if "--check" in argv:
        current = OUT_PATH.read_text(encoding="utf-8") if OUT_PATH.exists() else ""
        if current == text:
            print("OK: реестр методов актуален")
            return 0
        print("УСТАРЕЛ: registry/METHODS.md не совпадает с исходниками")
        print("Перегенерируйте: python tools/registry_scan.py")
        return 1
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(text, encoding="utf-8")
    print(f"Записан {OUT_PATH.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
