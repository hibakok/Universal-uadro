# @uadro
# @file    tests/test_registry_scan_render.py
# @layer   T0
# @branch  t0.infra.registry
# @desc    Тесты генератора реестра: рендер простым текстом, сверка
# @desc    и очистка на диске (разбор и план — tests/test_registry_scan.py).

"""Тесты рендера и диска реестра (tools/registry_scan.py).

Перенос по словам, склейка полей, рендер карточек и индекса, скан
реального репозитория (включая исходники .uasm/.ubrk, Этап 4), запись
и сверка реестра на диске. Разбор аннотаций и план —
tests/test_registry_scan.py.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import tempfile
import unittest
from pathlib import Path

from tools import registry_scan as rs


# @method sample_entry() -> dict
# @in    нет
# @out   entry: dict — элемент реестра: шапка и две карточки
# @does  Даёт детерминированный элемент для тестов рендера без
# @does  обращения к диску.
# @depends rs.parse_file_header, rs.parse_method_cards
def sample_entry():
    lines = [
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
        "# @method two() -> int",
        "# @does  Возвращает 2.",
    ]
    return {
        "path": rs.ROOT / "tools" / "sample.py",
        "header": rs.parse_file_header(lines),
        "cards": rs.parse_method_cards(lines),
    }


# @method empty_entry(name) -> dict
# @in    name: str — имя файла без каталога
# @out   entry: dict — элемент без ветви и без методов
# @does  Даёт минимальный элемент для тестов рендера без методов.
def empty_entry(name):
    return {
        "path": rs.ROOT / "tools" / name,
        "header": {"file": "", "layer": "T0", "branch": "", "desc": []},
        "cards": [],
    }


class TestWrapWords(unittest.TestCase):
    """Перенос текста по словам."""

    # @method test_short_text_stays_single_line() -> None
    # @in    нет
    # @out   нет
    # @does  Текст короче ширины не переносится.
    def test_short_text_stays_single_line(self):
        self.assertEqual(rs.wrap_words("короткий текст", 40), ["короткий текст"])

    # @method test_words_wrap_at_width() -> None
    # @in    нет
    # @out   нет
    # @does  Слова переносятся так, что строки не шире границы.
    def test_words_wrap_at_width(self):
        self.assertEqual(rs.wrap_words("ааа ббб ввв", 7), ["ааа ббб", "ввв"])
        self.assertEqual(rs.wrap_words("ааа ббб ввв", 11), ["ааа ббб ввв"])

    # @method test_long_word_owns_line() -> None
    # @in    нет
    # @out   нет
    # @does  Слово длиннее ширины занимает строку целиком.
    def test_long_word_owns_line(self):
        self.assertEqual(
            rs.wrap_words("а длинноещёдлиннее б", 5),
            ["а", "длинноещёдлиннее", "б"],
        )

    # @method test_empty_text_gives_no_lines() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой текст даёт пустой список строк.
    def test_empty_text_gives_no_lines(self):
        self.assertEqual(rs.wrap_words("", 40), [])


class TestMergeItems(unittest.TestCase):
    """Склейка значений полей карточки."""

    # @method test_does_joins_into_one_text() -> None
    # @in    нет
    # @out   нет
    # @does  Продолжения @does склеиваются через пробел.
    def test_does_joins_into_one_text(self):
        merged = rs.merge_items("does", ["Первая часть", "вторая часть."])
        self.assertEqual(merged, ["Первая часть вторая часть."])

    # @method test_lists_join_with_comma() -> None
    # @in    нет
    # @out   нет
    # @does  Списки @uses и @depends склеиваются через запятую.
    def test_lists_join_with_comma(self):
        self.assertEqual(rs.merge_items("depends", ["a", "b"]), ["a, b"])
        self.assertEqual(rs.merge_items("uses", ["x"]), ["x"])

    # @method test_in_stays_separate() -> None
    # @in    нет
    # @out   нет
    # @does  Строки @in и @out остаются отдельными.
    def test_in_stays_separate(self):
        self.assertEqual(
            rs.merge_items("in", ["a: int", "b: int"]), ["a: int", "b: int"]
        )

    # @method test_empty_items_give_empty_list() -> None
    # @in    нет
    # @out   нет
    # @does  Отсутствующее поле даёт пустой список абзацев.
    def test_empty_items_give_empty_list(self):
        self.assertEqual(rs.merge_items("does", []), [])


class TestRenderField(unittest.TestCase):
    """Рендер полей карточки."""

    # @method test_label_and_continuation_align() -> None
    # @in    нет
    # @out   нет
    # @does  Значение начинается после метки; продолжения выровнены
    # @does  под началом значения и не содержат метки.
    def test_label_and_continuation_align(self):
        lines = rs.render_field("функция", ["слово " * 30])
        self.assertTrue(lines[0].startswith("  функция:"))
        pad = " " * (len("  ") + rs.LABEL_WIDTH)
        for line in lines[1:]:
            self.assertTrue(line.startswith(pad))

    # @method test_separate_items_give_separate_paragraphs() -> None
    # @in    нет
    # @out   нет
    # @does  Каждый абзац значения начинается с метки поля.
    def test_separate_items_give_separate_paragraphs(self):
        lines = rs.render_field("вход", ["a: int — первое", "b: int — второе"])
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("  вход:"))
        self.assertTrue(lines[1].startswith("  вход:"))


class TestRender(unittest.TestCase):
    """Рендер файлов реестра."""

    # @method test_card_file_contains_cards() -> None
    # @in    нет
    # @out   нет
    # @does  Файл карточек содержит шапку с путём исходника и карточки.
    def test_card_file_contains_cards(self):
        plan = rs.plan_registry([sample_entry()])
        text = rs.render_card_file(plan[0])
        self.assertIn("КАРТОЧКИ ФАЙЛА tools/sample.py", text)
        self.assertIn("Ветвь: t0.sample.demo", text)
        self.assertIn("МЕТОД one(a) -> int", text)
        self.assertIn("a: int — число", text)

    # @method test_card_file_without_methods_note() -> None
    # @in    нет
    # @out   нет
    # @does  Файл без методов получает пометку «Методов нет».
    def test_card_file_without_methods_note(self):
        plan = rs.plan_registry([empty_entry("empty.py")])
        text = rs.render_card_file(plan[0])
        self.assertIn("Методов нет.", text)

    # @method test_index_lists_branch_and_cards() -> None
    # @in    нет
    # @out   нет
    # @does  Индекс перечисляет ветвь, путь карточек и итог.
    def test_index_lists_branch_and_cards(self):
        plan = rs.plan_registry([sample_entry()])
        text = rs.render_index(plan)
        self.assertIn("ВЕТВЬ t0.sample.demo [слой T0] — методов: 2", text)
        self.assertIn("registry/t0.sample.demo/sample.txt", text)
        self.assertIn("ВСЕГО МЕТОДОВ: 2", text)

    # @method test_render_all_names() -> None
    # @in    нет
    # @out   нет
    # @does  Реестр состоит из индекса и карточек по исходным файлам.
    def test_render_all_names(self):
        files = rs.render_all([sample_entry()])
        self.assertEqual(
            set(files), {"METHODS.txt", "t0.sample.demo/sample.txt"}
        )


class TestRepositoryScan(unittest.TestCase):
    """Интеграция: сканирование реального репозитория."""

    # @method test_scan_finds_card_files() -> None
    # @in    нет
    # @out   нет
    # @does  Сканер даёт карточки по файлам в каталогах ветвей.
    def test_scan_finds_card_files(self):
        files = rs.scan_repository()
        self.assertIn("METHODS.txt", files)
        self.assertIn("t0.infra.registry/registry_scan.txt", files)
        self.assertIn("t0.uvm.core/uvm_core.txt", files)

    # @method test_scan_finds_own_language_sources() -> None
    # @in    нет
    # @out   нет
    # @does  Интеграционные исходники .uasm/.ubrk с «; @»-шапками
    # @does  входят в реестр своих ветвей (Этап 4).
    def test_scan_finds_own_language_sources(self):
        files = rs.scan_repository()
        self.assertIn("t0.uasm.integration/hello.txt", files)
        self.assertIn("t0.uasm.integration/nested_calls.txt", files)
        self.assertIn("t0.ubrick.integration/hello.txt", files)
        self.assertIn("t0.ubrick.integration/nested_calls.txt", files)

    # @method test_all_cards_in_branch_dirs() -> None
    # @in    нет
    # @out   нет
    # @does  Кроме индекса все файлы реестра лежат в подкаталогах ветвей.
    def test_all_cards_in_branch_dirs(self):
        files = rs.scan_repository()
        nested = [name for name in files if name != rs.INDEX_NAME]
        self.assertTrue(nested)
        for name in nested:
            self.assertIn("/", name)

    # @method test_card_file_mentions_source() -> None
    # @in    нет
    # @out   нет
    # @does  Карточки генератора упоминают его исходный файл.
    def test_card_file_mentions_source(self):
        files = rs.scan_repository()
        text = files["t0.infra.registry/registry_scan.txt"]
        self.assertIn("tools/registry_scan.py", text)


class TestDisk(unittest.TestCase):
    """Сверка и запись реестра на диске (во временном каталоге)."""

    # @method test_write_check_and_cleanup() -> None
    # @in    нет
    # @out   нет
    # @does  Запись создаёт подкаталоги ветвей, удаляет лишние файлы и
    # @does  пустые каталоги; после записи сверка чиста.
    def test_write_check_and_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_dir = rs.REGISTRY_DIR
            rs.REGISTRY_DIR = Path(tmp)
            try:
                stale = Path(tmp) / "t0.old.txt"
                stale.write_text("старая раскладка", encoding="utf-8")
                empty_branch = Path(tmp) / "t0.old"
                empty_branch.mkdir()
                files = {"t0.demo/demo.txt": "карточки"}
                problems = rs.check_registry(files)
                self.assertIn("лишний файл: registry/t0.old.txt", problems)
                rs.write_registry(files)
                self.assertTrue((Path(tmp) / "t0.demo" / "demo.txt").exists())
                self.assertFalse(stale.exists())
                self.assertFalse(empty_branch.exists())
                self.assertEqual(rs.check_registry(files), [])
            finally:
                rs.REGISTRY_DIR = old_dir


if __name__ == "__main__":
    unittest.main()
