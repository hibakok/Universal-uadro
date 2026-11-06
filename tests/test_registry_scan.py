# @uadro
# @file    tests/test_registry_scan.py
# @layer   T0
# @branch  t0.infra.registry
# @desc    Тесты генератора реестра: разбор аннотаций «# @» и «; @»,
# @desc    план карточек по исходным файлам и страховка целостности
# @desc    источников — карточка без @does и файл без концевого
# @desc    перевода строки (признаки оборванного при переносе файла)
# @desc    падают в main до генерации реестра (рендер и диск —
# @desc    tests/test_registry_scan_render.py).

"""Тесты разбора и плана реестра (tools/registry_scan.py).

Аннотации «# @...» — Python-исходники, «; @...» — исходники
собственных языков .uasm/.ubrk (Этап 4, SPEC/L4-SELFHOST.txt).
Страховка целостности (card_gaps, unfinished_sources, source_problems):
оборванный при переносе файл ловится до генерации реестра — карточка
без @does и отсутствие перевода строки в конце. Рендер и работа
с диском — tests/test_registry_scan_render.py.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import os
import tempfile
import unittest

from tools import registry_scan as rs


# @method sample_lines() -> list
# @in    нет
# @out   lines: list[str] — образец исходника: шапка и две карточки
# @does  Даёт детерминированный образец для тестов разбора.
def sample_lines():
    return [
        "# @uadro",
        "# @file    tools/sample.py",
        "# @layer   T0",
        "# @branch  t0.sample.demo",
        "# @desc    Образец для тестов.",
        "",
        "# @method one(a) -> int",
        "# @in    a: int — число",
        "# @out   b: int — удвоенное число",
        "# @does  Удваивает число.",
        "def one(a):",
        "    return a * 2",
        "",
        "# @method two() -> int",
        "# @does  Возвращает 2.",
        "def two():",
        "    return 2",
    ]


# @method sample_entry() -> dict
# @in    нет
# @out   entry: dict — элемент реестра, собранный из образца
# @does  Собирает элемент реестра без обращения к диску.
# @depends sample_lines, rs.parse_file_header, rs.parse_method_cards
def sample_entry():
    lines = sample_lines()
    return {
        "path": rs.ROOT / "tools" / "sample.py",
        "header": rs.parse_file_header(lines),
        "cards": rs.parse_method_cards(lines),
    }


# @method empty_entry(name) -> dict
# @in    name: str — имя файла без каталога
# @out   entry: dict — элемент без ветви и без методов
# @does  Даёт минимальный элемент для тестов группировки и имён.
def empty_entry(name):
    return {
        "path": rs.ROOT / "tools" / name,
        "header": {"file": "", "layer": "T0", "branch": "", "desc": []},
        "cards": [],
    }


class TestStripTag(unittest.TestCase):
    """Разбор строк-аннотаций."""

    # @method test_recognizes_tag_line() -> None
    # @in    нет
    # @out   нет
    # @does  Строка "# @ключ значение" даёт пару (ключ, значение).
    def test_recognizes_tag_line(self):
        self.assertEqual(
            rs._strip_tag("# @method f(x) -> int"), ("method", "f(x) -> int")
        )
        self.assertEqual(rs._strip_tag("# @file    a.py"), ("file", "a.py"))

    # @method test_plain_line_gives_none() -> None
    # @in    нет
    # @out   нет
    # @does  Обычная строка кода не является аннотацией.
    def test_plain_line_gives_none(self):
        self.assertEqual(rs._strip_tag("def f():"), (None, ""))
        self.assertEqual(rs._strip_tag("    return 2"), (None, ""))

    # @method test_recognizes_semicolon_tag_line() -> None
    # @in    нет
    # @out   нет
    # @does  Строка "; @ключ значение" (uAsm/uBrick, Этап 4) даёт пару
    # @does  (ключ, значение) — как и "# @...".
    def test_recognizes_semicolon_tag_line(self):
        self.assertEqual(
            rs._strip_tag("; @method main ( -- )"), ("method", "main ( -- )")
        )
        self.assertEqual(
            rs._strip_tag("; @branch  l2.uasm.disasm"),
            ("branch", "l2.uasm.disasm"),
        )
        self.assertEqual(rs._strip_tag("; @uadro"), ("uadro", ""))

    # @method test_plain_semicolon_comment_gives_none() -> None
    # @in    нет
    # @out   нет
    # @does  Комментарий с ";" без " @" — не аннотация: после маркера
    # @does  обязателен пробел и ключ с "@".
    def test_plain_semicolon_comment_gives_none(self):
        self.assertEqual(rs._strip_tag("; обычный комментарий"), (None, ""))
        self.assertEqual(rs._strip_tag(";@нетпробела"), (None, ""))
        self.assertEqual(rs._strip_tag(";"), (None, ""))


class TestSemicolonSources(unittest.TestCase):
    """Аннотации исходников собственных языков (uAsm/uBrick)."""

    # @method test_header_and_cards_from_semicolon_lines() -> None
    # @in    нет
    # @out   нет
    # @does  Шапка и карточки исходника .ubrk разбираются из строк
    # @does  "; @..." теми же кирпичами, что и для .py.
    def test_header_and_cards_from_semicolon_lines(self):
        lines = [
            "; @uadro",
            "; @file    src/l2/disasm.ubrk",
            "; @layer   L2",
            "; @branch  l2.uasm.disasm",
            "; @desc    Дизассемблер uAsm на uBrick.",
            "",
            "; @method main ( -- )",
            "; @does  Читает образ из stdin, печатает текст в stdout.",
            ": main",
            "0 BYE ;",
        ]
        header = rs.parse_file_header(lines)
        cards = rs.parse_method_cards(lines)
        self.assertEqual(header["file"], "src/l2/disasm.ubrk")
        self.assertEqual(header["layer"], "L2")
        self.assertEqual(header["branch"], "l2.uasm.disasm")
        self.assertEqual(header["desc"], ["Дизассемблер uAsm на uBrick."])
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["name"], "main ( -- )")
        self.assertEqual(
            cards[0]["does"],
            ["Читает образ из stdin, печатает текст в stdout."],
        )

    # @method test_collect_sources_includes_own_languages() -> None
    # @in    нет
    # @out   нет
    # @does  Сканер собирает не только .py: интеграционные исходники
    # @does  src/*.uasm и src/*.ubrk входят в набор исходников.
    def test_collect_sources_includes_own_languages(self):
        paths = rs.collect_sources()
        names = [p.name for p in paths]
        self.assertIn("hello.uasm", names)
        self.assertIn("nested_calls.ubrk", names)
        for path in paths:
            self.assertIn(path.suffix, (".py", ".uasm", ".ubrk"))


class TestParseHeader(unittest.TestCase):
    """Разбор шапки файла."""

    # @method test_header_fields() -> None
    # @in    нет
    # @out   нет
    # @does  Шапка образца разбирается в поля file, layer, branch, desc.
    def test_header_fields(self):
        header = rs.parse_file_header(sample_lines())
        self.assertEqual(header["file"], "tools/sample.py")
        self.assertEqual(header["layer"], "T0")
        self.assertEqual(header["branch"], "t0.sample.demo")
        self.assertEqual(header["desc"], ["Образец для тестов."])

    # @method test_header_stops_after_block() -> None
    # @in    нет
    # @out   нет
    # @does  Шапка обрывается на первой строке вне блока "# @...".
    def test_header_stops_after_block(self):
        header = rs.parse_file_header(["# @layer T0", "", "# @branch x.y"])
        self.assertEqual(header["layer"], "T0")
        self.assertEqual(header["branch"], "")


class TestParseCards(unittest.TestCase):
    """Разбор карточек методов."""

    # @method test_two_cards_found() -> None
    # @in    нет
    # @out   нет
    # @does  Из образца собираются две карточки с верными именами.
    def test_two_cards_found(self):
        cards = rs.parse_method_cards(sample_lines())
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]["name"], "one(a) -> int")
        self.assertEqual(cards[1]["name"], "two() -> int")

    # @method test_card_fields() -> None
    # @in    нет
    # @out   нет
    # @does  Поля вход/выход/функция попадают в карточку первого метода.
    def test_card_fields(self):
        cards = rs.parse_method_cards(sample_lines())
        self.assertEqual(cards[0]["in"], ["a: int — число"])
        self.assertEqual(cards[0]["out"], ["b: int — удвоенное число"])
        self.assertEqual(cards[0]["does"], ["Удваивает число."])
        self.assertEqual(cards[1]["in"], [])

    # @method test_lone_tags_ignored() -> None
    # @in    нет
    # @out   нет
    # @does  Аннотации без открывающей "@method" не создают карточек.
    def test_lone_tags_ignored(self):
        cards = rs.parse_method_cards(["# @in потерян", "# @does потерян"])
        self.assertEqual(cards, [])


# @method card_entry(name, lines) -> dict
# @in    name: str — имя файла без каталога
# @in    lines: list[str] — строки исходника
# @out   entry: dict — элемент реестра с разобранными карточками
# @does  Собирает элемент из строк без обращения к диску; кирпич тестов
# @does  целостности источников (card_gaps).
# @depends rs.parse_method_cards
def card_entry(name, lines):
    return {
        "path": rs.ROOT / "tools" / name,
        "header": {"file": "", "layer": "T0", "branch": "", "desc": []},
        "cards": rs.parse_method_cards(lines),
    }


# @method entry_from_file(path) -> dict
# @in    path: str — путь к существующему файлу
# @out   entry: dict — элемент реестра с карточками из этого файла
# @does  Читает файл и разбирает карточки без обращения к collect_sources;
# @does  кирпич тестов целостности источников (card_gaps,
# @does  unfinished_sources, source_problems).
# @depends rs.parse_method_cards
def entry_from_file(path):
    with open(path, "r", encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    return {
        "path": type(rs.ROOT)(path),
        "header": {"file": "", "layer": "T0", "branch": "", "desc": []},
        "cards": rs.parse_method_cards(lines),
    }


class TestSourceIntegrity(unittest.TestCase):
    """Страховка целостности: оборванные файлы видны до генерации."""

    # @method test_full_card_passes() -> None
    # @in    нет
    # @out   нет
    # @does  Карточка с полем @does — не дыра: образец с двумя полными
    # @does  карточками проходит страховку молча.
    # @depends card_entry, rs.card_gaps, sample_lines
    def test_full_card_passes(self):
        self.assertEqual(rs.card_gaps([card_entry("ok.py", sample_lines())]),
                         [])

    # @method test_card_without_does_reported() -> None
    # @in    нет
    # @out   нет
    # @does  Карточка без @does — признак оборванного файла: сообщение
    # @does  называет исходник и имя метода; полная карточка в том же
    # @does  файле не мешает (обрыв ловится точечно).
    # @depends card_entry, rs.card_gaps
    def test_card_without_does_reported(self):
        lines = [
            "# @method whole(a) -> int",
            "# @does  Целая карточка.",
            "def whole(a):",
            "    return a",
            "# @method cut(b) -> int",
            "# @in    b: int — число",
        ]
        problems = rs.card_gaps([card_entry("cut.py", lines)])
        self.assertEqual(len(problems), 1)
        self.assertIn("cut.py", problems[0])
        self.assertIn("cut(b) -> int", problems[0])

    # @method test_semicolon_card_without_does_reported() -> None
    # @in    нет
    # @out   нет
    # @does  Страховка видит и исходники собственных языков: карточка
    # @does  «; @method» без «; @does» (uAsm/uBrick) — дыра.
    # @depends card_entry, rs.card_gaps
    def test_semicolon_card_without_does_reported(self):
        lines = ["; @method main ( -- )", "; @does  Целая.", "; @method cut"]
        problems = rs.card_gaps([card_entry("cut.ubrk", lines)])
        self.assertEqual(problems, ["карточка без @does: tools/cut.ubrk — "
                                    "cut"])

    # @method test_source_problems_joins_guards() -> None
    # @in    нет
    # @out   нет
    # @does  Кирпич main собирает обе страховки: один оборванный файл
    # @does  без @does и без концевого перевода строки даёт два разных
    # @does  сообщения.
    # @depends entry_from_file, rs.source_problems
    # @uses   tempfile — временный файл вне репозитория
    def test_source_problems_joins_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            cut = os.path.join(tmp, "cut.py")
            with open(cut, "w", encoding="utf-8") as handle:
                handle.write("# @method cut\n# @in    x: int")
            problems = rs.source_problems([entry_from_file(cut)])
        self.assertEqual(len(problems), 2)
        self.assertTrue(problems[0].startswith("карточка без @does:"))
        self.assertTrue(problems[1].startswith("нет перевода строки"))

    # @method test_unfinished_file_reported() -> None
    # @in    нет
    # @out   нет
    # @does  Файл без перевода строки в конце — обрыв последней строки:
    # @does  сообщение называет путь; завершённый и пустой файлы
    # @does  проходят молча.
    # @depends entry_from_file, rs.unfinished_sources
    # @uses   tempfile — временные файлы вне репозитория
    def test_unfinished_file_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            cut = os.path.join(tmp, "cut.py")
            whole = os.path.join(tmp, "whole.py")
            empty = os.path.join(tmp, "empty.py")
            with open(cut, "w", encoding="utf-8") as handle:
                handle.write("# обрыв на середине строки")
            with open(whole, "w", encoding="utf-8") as handle:
                handle.write("# завершён\n")
            with open(empty, "w", encoding="utf-8") as handle:
                handle.write("")
            entries = [entry_from_file(p) for p in (cut, whole, empty)]
            problems = rs.unfinished_sources(entries)
        self.assertEqual(len(problems), 1)
        self.assertIn("cut.py", problems[0])
        self.assertIn("нет перевода строки", problems[0])


class TestPlan(unittest.TestCase):
    """План реестра: ветви и имена файлов карточек."""

    # @method test_branch_of_entry() -> None
    # @in    нет
    # @out   нет
    # @does  Имя ветви берётся из шапки элемента.
    def test_branch_of_entry(self):
        self.assertEqual(rs.branch_of(sample_entry()), "t0.sample.demo")

    # @method test_branch_of_empty_header() -> None
    # @in    нет
    # @out   нет
    # @does  Без ветви в шапке элемент попадает в группу no-branch.
    def test_branch_of_empty_header(self):
        self.assertEqual(rs.branch_of(empty_entry("x.py")), rs.NO_BRANCH)

    # @method test_card_name_from_stem() -> None
    # @in    нет
    # @out   нет
    # @does  Имя файла карточек строится из имени исходника с .txt.
    def test_card_name_from_stem(self):
        self.assertEqual(rs.card_name_for(sample_entry(), set()), "sample.txt")

    # @method test_card_name_collision_gets_suffix() -> None
    # @in    нет
    # @out   нет
    # @does  Совпадающие имена внутри ветви получают числовой суффикс.
    def test_card_name_collision_gets_suffix(self):
        used = set()
        first = rs.card_name_for(sample_entry(), used)
        second = rs.card_name_for(empty_entry("sample.py"), used)
        self.assertEqual(first, "sample.txt")
        self.assertEqual(second, "sample_2.txt")

    # @method test_card_name_reserves_branch_index() -> None
    # @in    нет
    # @out   нет
    # @does  Имя индекса ветви INDEX.txt занято (registry_render.
    # @does  BRANCH_INDEX_NAME): исходник index.py получает суффикс.
    # @depends rs.card_name_for
    def test_card_name_reserves_branch_index(self):
        used = {"INDEX.txt"}
        self.assertEqual(rs.card_name_for(empty_entry("index.py"), used),
                         "index_2.txt")

    # @method test_plan_registry_maps_branch_and_card() -> None
    # @in    нет
    # @out   нет
    # @does  План назначает исходнику его ветвь, имя файла карточек
    # @does  и относительный путь (rel) для рендера.
    # @depends rs.plan_registry
    def test_plan_registry_maps_branch_and_card(self):
        plan = rs.plan_registry([sample_entry()])
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["branch"], "t0.sample.demo")
        self.assertEqual(plan[0]["card"], "sample.txt")
        self.assertEqual(plan[0]["rel"], "tools/sample.py")


if __name__ == "__main__":
    unittest.main()
