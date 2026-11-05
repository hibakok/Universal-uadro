# @uadro
# @file    tests/test_ubrick_build.py
# @layer   T0
# @branch  t0.ubrick.build
# @desc    Тесты сборки программы uBrick: кирпичи пролога, слов и данных,
# @desc    части текста uAsm, порядок частей и счётчик меток программы,
# @desc    поведение эталонных программ на UVM (SPEC/L3-UBRICK.txt,
# @desc    раздел 7).

"""Тесты ветви t0.ubrick.build (tools/ubrick_build.py).

Кирпичи и части текста проверяются точно; полная сборка — текстом
(порядок четырёх частей, счётчик _L<n> один на программу) и
поведением: эталонные программы собираются build_ubrk и исполняются
run_image (ветвь t0.uvm.run) — это первое исполнение производных
слов словаря на UVM.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import contextlib
import unittest

from tests import uvm_testkit as tk
from tools import uvm_run as rn
from tools.ubrick_build import (
    build_text,
    build_ubrk,
    data_lines,
    data_part,
    definition_lines,
    definitions_part,
    derived_elements,
    derived_part,
    prologue,
    quote_literal,
    ref_lines,
    token_element,
    word_lines,
)
from tools.ubrick_compile import new_counter
from tools.ubrick_dict import derived_body, derived_names
from tools.ubrick_parse import parse_ubrk
from tools.uasm_lex import parse_string


# @method records_of(source) -> tuple
# @in    source: str — исходный текст uBrick
# @out   records: tuple — записи разбора; ошибка разбора — ошибка теста
# @does  Разбирает исходник parse_ubrk: сборка получает только
# @does  безошибочные записи (контракт ветви t0.ubrick.parse).
# @depends parse_ubrk
def records_of(source):
    records, error = parse_ubrk(source)
    assert error is None, error
    return records


# @method built_image(source) -> bytes
# @in    source: str — исходный текст uBrick
# @out   image: bytes — образ, собранный build_ubrk; ошибка сборки —
# @out   ошибка теста
# @does  Собирает образ эталонной программы: записи разбора — build_ubrk.
# @depends records_of, build_ubrk
def built_image(source):
    image, error = build_ubrk(records_of(source))
    assert error is None, error
    return image


# @method run_of(source) -> tuple
# @in    source: str — исходный текст uBrick
# @out   triple: tuple — (машина, код завершения, байты stdout)
# @does  Собирает и исполняет эталонную программу: вывод идёт в заглушку
# @does  stdout (FakeStream тест-набора), машина и код — run_image.
# @depends built_image, rn.run_image, tk.FakeStream
# @uses   sys.stdout — стандартный вывод хоста (подмена на время запуска)
def run_of(source):
    out = tk.FakeStream()
    with contextlib.redirect_stdout(out):
        m, code = rn.run_image(built_image(source))
    return m, code, out.buffer.getvalue()


class TestQuoteLiteral(unittest.TestCase):
    """Строковый литерал данных (SPEC/L2-UASM.txt, раздел 4)."""

    # @method test_plain() -> None
    # @in    нет
    # @out   нет
    # @does  Пустые и простые байты — литерал без escape.
    def test_plain(self):
        self.assertEqual(quote_literal(b""), '""')
        self.assertEqual(quote_literal(b"Hi"), '"Hi"')

    # @method test_escapes() -> None
    # @in    нет
    # @out   нет
    # @does  Байты 0, 9, 10 и 13 — escape \\0 \\t \\n \\r.
    def test_escapes(self):
        self.assertEqual(quote_literal(b"a\nb\tc\rd\0e"),
                         '"a\\nb\\tc\\rd\\0e"')

    # @method test_quote_and_backslash() -> None
    # @in    нет
    # @out   нет
    # @does  Кавычка и обратный слеш экранируются, литерал не рвётся.
    def test_quote_and_backslash(self):
        self.assertEqual(quote_literal(b'x"y\\z'), '"x\\"y\\\\z"')

    # @method test_utf8() -> None
    # @in    нет
    # @out   нет
    # @does  Многобайтные символы UTF-8 остаются собой.
    def test_utf8(self):
        data = "привет".encode("utf-8")
        self.assertEqual(quote_literal(data), '"привет"')

    # @method test_roundtrip() -> None
    # @in    нет
    # @out   нет
    # @does  parse_string(quote_literal(данные)) == данные: escape,
    # @does  кавычка, слеш, UTF-8 и непечатные однобайтовые символы.
    def test_roundtrip(self):
        cases = (b"", b"Hi", b"a\nb\tc\rd\0e", b'x"y\\z',
                 "привет".encode("utf-8"), bytes(range(32, 127)),
                 bytes((1, 11, 12, 14, 127)))
        for data in cases:
            self.assertEqual(parse_string(quote_literal(data)), data)


class TestBricks(unittest.TestCase):
    """Кирпичи пролога, слов, ссылок и данных (SPEC, разделы 6-7)."""

    # @method test_prologue() -> None
    # @in    нет
    # @out   нет
    # @does  Пролог — CALL main и HALT 0.
    def test_prologue(self):
        self.assertEqual(prologue(), ("CALL main", "HALT 0"))

    # @method test_token_element() -> None
    # @in    нет
    # @out   нет
    # @does  Конструкция — construct, слово словаря — word, число — lit.
    def test_token_element(self):
        self.assertEqual(token_element("IF"), ("construct", "IF"))
        self.assertEqual(token_element("ADD"), ("word", "ADD"))
        self.assertEqual(token_element("gts"), ("word", "gts"))
        self.assertEqual(token_element("0x10"), ("lit", 16))
        self.assertEqual(token_element("0x8000000000000000"),
                         ("lit", 1 << 63))

    # @method test_derived_elements() -> None
    # @in    нет
    # @out   нет
    # @does  Тела производных слов — в элементы: литерал, примитив,
    # @does  вызов производного и конструкции.
    def test_derived_elements(self):
        self.assertEqual(derived_elements(derived_body("inc")),
                         (("lit", 1), ("word", "ADD")))
        self.assertEqual(derived_elements(derived_body("min")),
                         (("word", "OVER"), ("word", "OVER"),
                          ("word", "gts"), ("construct", "IF"),
                          ("word", "SWAP"), ("word", "DROP"),
                          ("construct", "ELSE"), ("word", "DROP"),
                          ("construct", "THEN")))

    # @method test_word_lines() -> None
    # @in    нет
    # @out   нет
    # @does  Определение слова: метка, тело (PUSH и врезанный EMIT), RET.
    def test_word_lines(self):
        elements = (("lit", 1), ("word", "EMIT"))
        self.assertEqual(word_lines("main", elements, new_counter()),
                         ("main:", "PUSH 1", "SYS 1", "RET"))

    # @method test_ref_lines() -> None
    # @in    нет
    # @out   нет
    # @does  Слово var/text: метка, PUSH d_имя, RET.
    def test_ref_lines(self):
        self.assertEqual(ref_lines("x"), ("x:", "PUSH d_x", "RET"))

    # @method test_data_lines() -> None
    # @in    нет
    # @out   нет
    # @does  var — d_имя и DW 0; text — d_имя и DZ "литерал"; слово
    # @does  данных не даёт.
    def test_data_lines(self):
        self.assertEqual(data_lines(("var", "x")), ("d_x:", "DW 0"))
        self.assertEqual(data_lines(("text", "msg", b"Hi")),
                         ("d_msg:", 'DZ "Hi"'))
        self.assertEqual(data_lines(("word", "main", ())), ())


class TestDerivedPart(unittest.TestCase):
    """Часть 2: производные слова словаря (SPEC, разделы 4.2 и 7)."""

    # @method test_order_and_ret() -> None
    # @in    нет
    # @out   нет
    # @does  Метки слов идут в порядке derived_names, каждое слово
    # @does  завершается RET.
    def test_order_and_ret(self):
        lines = derived_part(new_counter())
        names = list(derived_names())
        self.assertEqual(lines[0], "not:")
        self.assertEqual(lines[-1], "RET")
        spots = [lines.index(name + ":") for name in names]
        self.assertEqual(spots, sorted(spots))
        for i, name in enumerate(names):
            after = spots[i + 1] if i + 1 < len(names) else len(lines)
            self.assertEqual(lines[after - 1], "RET", name)

    # @method test_not_body() -> None
    # @in    нет
    # @out   нет
    # @does  Тело not дословно из SPEC: PUSH 0, EQ.
    def test_not_body(self):
        lines = derived_part(new_counter())
        start = lines.index("not:")
        end = lines.index("inc:")
        self.assertEqual(lines[start:end], ("not:", "PUSH 0", "EQ", "RET"))

    # @method test_construct_labels() -> None
    # @in    нет
    # @out   нет
    # @does  Конструкции производных слов берут метки первыми: min —
    # @does  _L1 и _L2, max — _L3 и _L4, prints — _L5 и _L6; счётчик
    # @does  остановился на 6.
    def test_construct_labels(self):
        counter = new_counter()
        lines = derived_part(counter)
        self.assertIn("JZ _L1", lines)
        self.assertIn("JMP _L2", lines)
        self.assertIn("_L5:", lines)
        self.assertIn("JZ _L6", lines)
        self.assertIn("JMP _L5", lines)
        self.assertEqual(counter, {"n": 6})

    # @method test_prints_body() -> None
    # @in    нет
    # @out   нет
    # @does  Тело prints из примера SPEC (раздел 5): BEGIN, чтение
    # @does  байта, IF-выход по нулю, EMIT и AGAIN назад.
    def test_prints_body(self):
        lines = derived_part(new_counter())
        start = lines.index("prints:")
        self.assertEqual(lines[start:],
                         ("prints:", "_L5:", "DUP", "LOAD8", "DUP",
                          "PUSH 0", "EQ", "JZ _L6", "DROP", "DROP",
                          "RET", "_L6:", "SYS 1", "PUSH 1", "ADD",
                          "JMP _L5", "RET"))


class TestDefinitionsPart(unittest.TestCase):
    """Часть 3: определения исходника в порядке появления (SPEC, разд. 7)."""

    # @method test_order_and_kinds() -> None
    # @in    нет
    # @out   нет
    # @does  Слово, var и text печатаются в порядке записей: метка,
    # @does  тело, RET; var и text — PUSH d_имя, RET.
    def test_order_and_kinds(self):
        records = (("word", "main", (("lit", 1), ("word", "EMIT"))),
                   ("var", "x"),
                   ("text", "msg", b"Hi"))
        self.assertEqual(
            definitions_part(records, new_counter()),
            ("main:", "PUSH 1", "SYS 1", "RET",
             "x:", "PUSH d_x", "RET",
             "msg:", "PUSH d_msg", "RET"))

    # @method test_counter_continues() -> None
    # @in    нет
    # @out   нет
    # @does  Счётчик общий для определений: второй IF получает _L2
    # @does  после _L1 первого.
    def test_counter_continues(self):
        records = (("word", "first",
                    (("construct", "IF"), ("word", "NOP"),
                     ("construct", "THEN"))),
                   ("word", "second",
                    (("construct", "IF"), ("word", "NOP"),
                     ("construct", "THEN"))))
        self.assertEqual(
            definitions_part(records, new_counter()),
            ("first:", "JZ _L1", "NOP", "_L1:", "RET",
             "second:", "JZ _L2", "NOP", "_L2:", "RET"))


class TestDataPart(unittest.TestCase):
    """Часть 4: секция данных в порядке появления (SPEC, раздел 7)."""

    # @method test_order_and_kinds() -> None
    # @in    нет
    # @out   нет
    # @does  Данные в порядке записей: var — DW 0, text — DZ "литерал";
    # @does  слова данных не дают.
    def test_order_and_kinds(self):
        records = (("var", "x"), ("word", "main", ()),
                   ("text", "msg", b"Hi"))
        self.assertEqual(data_part(records),
                         ("d_x:", "DW 0", "d_msg:", 'DZ "Hi"'))


class TestBuildText(unittest.TestCase):
    """Полный текст: порядок частей и счётчик программы (SPEC, раздел 7)."""

    # @method test_composition() -> None
    # @in    нет
    # @out   нет
    # @does  Текст — сцепление четырёх частей с одним счётчиком:
    # @does  производные слова первыми, определения продолжают.
    def test_composition(self):
        source = 'text msg "Hi"\nvar x\n: main msg prints x LOAD64 ;'
        records = records_of(source)
        counter = new_counter()
        expected = "\n".join(
            prologue() + derived_part(counter)
            + definitions_part(records, counter) + data_part(records))
        self.assertEqual(build_text(records), expected)

    # @method test_starts_with_prologue() -> None
    # @in    нет
    # @out   нет
    # @does  Текст начинается с пролога: CALL main, HALT 0.
    def test_starts_with_prologue(self):
        text = build_text(records_of(": main 0 DROP ;"))
        self.assertTrue(text.startswith("CALL main\nHALT 0\n"))

    # @method test_definitions_after_derived() -> None
    # @in    нет
    # @out   нет
    # @does  Определения исходника идут после производных слов словаря.
    def test_definitions_after_derived(self):
        text = build_text(records_of(": main prints ;"))
        self.assertLess(text.index("prints:"), text.index("main:"))

    # @method test_data_at_end() -> None
    # @in    нет
    # @out   нет
    # @does  Секция данных замыкает текст: слово-адрес, затем d_имя.
    def test_data_at_end(self):
        text = build_text(records_of(": main x LOAD64 DROP ;\nvar x"))
        self.assertTrue(text.endswith("x:\nPUSH d_x\nRET\nd_x:\nDW 0"))

    # @method test_user_labels_continue() -> None
    # @in    нет
    # @out   нет
    # @does  Определения исходника продолжают нумерацию меток: IF
    # @does  слова main — _L7 после шести меток производных слов.
    def test_user_labels_continue(self):
        text = build_text(records_of(": main IF NOP THEN ;"))
        self.assertIn("JZ _L7", text)
        self.assertIn("_L7:", text)
        self.assertNotIn("_L8", text)


class TestBuildUbrk(unittest.TestCase):
    """Образ и поведение эталонных программ на UVM (SPEC, разделы 2-7)."""

    # @method test_hello() -> None
    # @in    нет
    # @out   нет
    # @does  hello: text + prints печатают "Hi", код 0, стек пуст —
    # @does  первое исполнение производного слова prints.
    def test_hello(self):
        m, code, out = run_of('text msg "Hi"\n: main msg prints ;')
        self.assertEqual(code, 0)
        self.assertEqual(out, b"Hi")
        self.assertEqual(tk.stack_of(m), [])

    # @method test_arith() -> None
    # @in    нет
    # @out   нет
    # @does  Арифметика: (2+3)*4 = 20 остаётся на стеке, вывода нет.
    def test_arith(self):
        m, code, out = run_of(": main 2 3 ADD 4 MUL ;")
        self.assertEqual(code, 0)
        self.assertEqual(out, b"")
        self.assertEqual(tk.stack_of(m), [20])

    # @method test_var() -> None
    # @in    нет
    # @out   нет
    # @does  var: 5 x STORE64 и x LOAD64 читают ячейку DW 0 секции
    # @does  данных — на стеке 5.
    def test_var(self):
        m, code, out = run_of("var x\n: main 5 x STORE64 x LOAD64 ;")
        self.assertEqual(code, 0)
        self.assertEqual(tk.stack_of(m), [5])

    # @method test_nested_calls() -> None
    # @in    нет
    # @out   нет
    # @does  Вложенные вызовы: sub из main, стек [111, 222], стек
    # @does  возвратов пуст.
    def test_nested_calls(self):
        m, code, out = run_of(": sub 111 ;\n: main sub 222 ;")
        self.assertEqual(code, 0)
        self.assertEqual(tk.stack_of(m), [111, 222])
        self.assertEqual(m.rs, [])

    # @method test_begin_until() -> None
    # @in    нет
    # @out   нет
    # @does  BEGIN/UNTIL: цикл печатает "ABC" и оставляет стек пустым.
    def test_begin_until(self):
        m, code, out = run_of(
            ": main 65 BEGIN DUP EMIT 1 ADD DUP 68 EQ UNTIL DROP ;")
        self.assertEqual(code, 0)
        self.assertEqual(out, b"ABC")
        self.assertEqual(tk.stack_of(m), [])

    # @method test_quit() -> None
    # @in    нет
    # @out   нет
    # @does  Псевдоним QUIT (HALT 16): программа завершается кодом 16 —
    # @does  ошибка входа инструмента (SPEC/L3-UBRICK.txt, раздел 4.1,
    # @does  v0.4); вывод пуст, стек пуст.
    def test_quit(self):
        m, code, out = run_of(": main QUIT ;")
        self.assertEqual(code, 16)
        self.assertEqual(out, b"")
        self.assertEqual(tk.stack_of(m), [])


    # @method test_derived_words() -> None
    # @in    нет
    # @out   нет
    # @does  Производные слова: abs(-5) = 5, min(-3, 7) = -3,
    # @does  max(-3, 7) = 7 — знаковая семантика тел словаря.
    def test_derived_words(self):
        m, code, out = run_of(": main -5 abs -3 7 min -3 7 max ;")
        self.assertEqual(code, 0)
        self.assertEqual(tk.stack_of(m), [5, (1 << 64) - 3, 7])

    # @method test_lts() -> None
    # @in    нет
    # @out   нет
    # @does  Знаковое сравнение биасом: -5 < 3 — истина (1).
    def test_lts(self):
        m, code, out = run_of(": main -5 3 lts ;")
        self.assertEqual(code, 0)
        self.assertEqual(tk.stack_of(m), [1])

    # @method test_sext8() -> None
    # @in    нет
    # @out   нет
    # @does  Знак-расширение байта: sext8(255) = -1 (2^64-1 словом).
    def test_sext8(self):
        m, code, out = run_of(": main 255 sext8 ;")
        self.assertEqual(code, 0)
        self.assertEqual(tk.stack_of(m), [(1 << 64) - 1])

    # @method test_no_main_error() -> None
    # @in    нет
    # @out   нет
    # @does  Записи без main (минуя разбор): пролог ссылается на метку
    # @does  main — ошибка ассемблера проходит наружу с номером
    # @does  строки пролога.
    def test_no_main_error(self):
        image, error = build_ubrk((("word", "foo", ()),))
        self.assertIsNone(image)
        self.assertEqual(error, "uAsm: строка 1: неизвестное имя main")


if __name__ == "__main__":
    unittest.main()
