# @uadro
# @file    tests/test_registry_scan.py
# @layer   T0
# @branch  t0.infra.registry
# @desc    Тесты генератора реестра: разбор аннотаций, группировка, рендер.

"""Тесты ветви t0.infra.registry (tools/registry_scan.py).

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

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


class TestGrouping(unittest.TestCase):
    """Группировка файлов по ветвям."""

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
        entry = {"path": rs.ROOT / "x.py", "header": {"branch": ""}, "cards": []}
        self.assertEqual(rs.branch_of(entry), rs.NO_BRANCH)

    # @method test_group_by_branch_two_groups() -> None
    # @in    нет
    # @out   нет
    # @does  Файлы разных ветвей образуют разные группы.
    def test_group_by_branch_two_groups(self):
        other = {
            "path": rs.ROOT / "tools" / "other.py",
            "header": {"branch": "t0.other", "layer": "T0", "desc": []},
            "cards": [],
        }
        groups = rs.group_by_branch([sample_entry(), other])
        self.assertEqual(set(groups), {"t0.sample.demo", "t0.other"})


class TestRender(unittest.TestCase):
    """Рендер файлов реестра."""

    # @method test_branch_file_contains_cards() -> None
    # @in    нет
    # @out   нет
    # @does  Файл ветви содержит раздел файла и карточки методов.
    def test_branch_file_contains_cards(self):
        text = rs.render_branch_file("t0.sample.demo", [sample_entry()])
        self.assertIn("## tools/sample.py", text)
        self.assertIn("### one(a) -> int", text)
        self.assertIn("**вход:** a: int — число", text)

    # @method test_index_lists_branch() -> None
    # @in    нет
    # @out   нет
    # @does  Индекс перечисляет ветвь с числом методов и итог.
    def test_index_lists_branch(self):
        groups = rs.group_by_branch([sample_entry()])
        text = rs.render_index(groups)
        self.assertIn("## [T0] t0.sample.demo — методов: 2", text)
        self.assertIn("**Всего методов: 2**", text)

    # @method test_render_all_names() -> None
    # @in    нет
    # @out   нет
    # @does  Реестр состоит из индекса и по одному файлу на ветвь.
    def test_render_all_names(self):
        files = rs.render_all([sample_entry()])
        self.assertEqual(set(files), {"METHODS.md", "t0.sample.demo.md"})


class TestRepositoryScan(unittest.TestCase):
    """Интеграция: сканирование реального репозитория."""

    # @method test_scan_finds_infra_branch() -> None
    # @in    нет
    # @out   нет
    # @does  Сканер находит ветвь t0.infra.registry в реальном репозитории.
    def test_scan_finds_infra_branch(self):
        files = rs.scan_repository()
        self.assertIn("METHODS.md", files)
        self.assertIn("t0.infra.registry.md", files)

    # @method test_infra_cards_mention_tools() -> None
    # @in    нет
    # @out   нет
    # @does  Карточки ветви инфраструктуры упоминают её инструменты.
    def test_infra_cards_mention_tools(self):
        files = rs.scan_repository()
        self.assertIn("tools/registry_scan.py", files["t0.infra.registry.md"])


if __name__ == "__main__":
    unittest.main()
