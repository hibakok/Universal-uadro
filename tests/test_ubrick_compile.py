# @uadro
# @file    tests/test_ubrick_compile.py
# @layer   T0
# @branch  t0.ubrick.compile
# @desc    Тесты компиляции тел uBrick: кирпичи меток, слов и литералов;
# @desc    каждая конструкция, вложенность, полные тела и общий счётчик
# @desc    (SPEC/L3-UBRICK.txt, разделы 2, 5 и 7).

"""Тесты ветви t0.ubrick.compile (tools/ubrick_compile.py).

Тела берутся разбором t0.ubrick.parse (parse_ubrk) — это
документированный производитель элементов; точные случаи задаются
напрямую кортежами элементов. Ожидания — точные строки uAsm.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tools.ubrick_compile import (
    compile_body,
    lit_line,
    new_counter,
    next_label,
    word_line,
)
from tools.ubrick_parse import parse_ubrk


# @method word_body(records, name) -> tuple
# @in    records: list — записи разбора parse_ubrk
# @in    name: str — имя слова
# @out   body: tuple — элементы тела слова либо None, если слова нет
# @does  Достаёт тело определения по имени из записей разбора.
def word_body(records, name):
    for record in records:
        if record[0] == "word" and record[1] == name:
            return record[2]
    return None


class TestLabels(unittest.TestCase):
    """Счётчик служебных меток _L<n> (SPEC, раздел 7)."""

    # @method test_first_label() -> None
    # @in    нет
    # @out   нет
    # @does  Счётчик создаётся нулём; первый номер — 1 (_L1).
    def test_first_label(self):
        counter = new_counter()
        self.assertEqual(counter, {"n": 0})
        self.assertEqual(next_label(counter), "_L1")

    # @method test_monotonic() -> None
    # @in    нет
    # @out   нет
    # @does  Номера растут монотонно: _L1, _L2, _L3.
    def test_monotonic(self):
        counter = new_counter()
        self.assertEqual([next_label(counter) for _ in range(3)],
                         ["_L1", "_L2", "_L3"])
        self.assertEqual(counter, {"n": 3})

    # @method test_independent_counters() -> None
    # @in    нет
    # @out   нет
    # @does  Счётчики программ независимы: каждый начинает с _L1.
    def test_independent_counters(self):
        first = new_counter()
        second = new_counter()
        next_label(first)
        next_label(first)
        self.assertEqual(next_label(second), "_L1")


class TestWordLines(unittest.TestCase):
    """Компиляция слов тела (SPEC, раздел 2): инструкция или CALL."""

    # @method test_primitive() -> None
    # @in    нет
    # @out   нет
    # @does  Примитив врезается одной инструкцией без imm.
    def test_primitive(self):
        self.assertEqual(word_line("ADD"), "ADD")
        self.assertEqual(word_line("LOAD8"), "LOAD8")
        self.assertEqual(word_line("GEU"), "GEU")

    # @method test_alias() -> None
    # @in    нет
    # @out   нет
    # @does  Псевдоним — одна инструкция с фиксированным imm; EXIT
    # @does  компилируется в RET.
    def test_alias(self):
        self.assertEqual(word_line("EMIT"), "SYS 1")
        self.assertEqual(word_line("KEY"), "SYS 0")
        self.assertEqual(word_line("BYE"), "HALT 0")
        self.assertEqual(word_line("EXIT"), "RET")

    # @method test_derived_is_call() -> None
    # @in    нет
    # @out   нет
    # @does  Производное слово — подпрограмма: обращение — CALL метки.
    def test_derived_is_call(self):
        self.assertEqual(word_line("not"), "CALL not")
        self.assertEqual(word_line("lts"), "CALL lts")
        self.assertEqual(word_line("prints"), "CALL prints")

    # @method test_user_word_is_call() -> None
    # @in    нет
    # @out   нет
    # @does  Слово пользователя (включая var/text) — подпрограмма:
    # @does  обращение — CALL метки.
    def test_user_word_is_call(self):
        self.assertEqual(word_line("main"), "CALL main")
        self.assertEqual(word_line("x"), "CALL x")
        self.assertEqual(word_line("msg"), "CALL msg")


class TestLitLines(unittest.TestCase):
    """Компиляция литералов (SPEC, разделы 2-3): PUSH imm."""

    # @method test_zero_and_positive() -> None
    # @in    нет
    # @out   нет
    # @does  Ноль и положительные — без изменений; верхняя граница
    # @does  диапазона 2^64-1 остаётся собой.
    def test_zero_and_positive(self):
        self.assertEqual(lit_line(0), "PUSH 0")
        self.assertEqual(lit_line(42), "PUSH 42")
        self.assertEqual(lit_line(2 ** 64 - 1), "PUSH 18446744073709551615")

    # @method test_negative_wraps() -> None
    # @in    нет
    # @out   нет
    # @does  Отрицательные оборачиваются по модулю 2^64: -1, -123
    # @does  и нижняя граница -2^63.
    def test_negative_wraps(self):
        self.assertEqual(lit_line(-1), "PUSH 18446744073709551615")
        self.assertEqual(lit_line(-123), "PUSH 18446744073709551493")
        self.assertEqual(lit_line(-2 ** 63), "PUSH 9223372036854775808")


class TestConstructs(unittest.TestCase):
    """Компиляция конструкций (SPEC, раздел 5): переходы и метки _L<n>."""

    # @method test_if_then() -> None
    # @in    нет
    # @out   нет
    # @does  IF — JZ вперёд на свежую метку, THEN ставит её тут.
    def test_if_then(self):
        records, error = parse_ubrk(": main IF DROP THEN ;")
        self.assertIsNone(error)
        self.assertEqual(compile_body(word_body(records, "main"),
                                      new_counter()),
                         ("JZ _L1", "DROP", "_L1:"))

    # @method test_if_else_then() -> None
    # @in    нет
    # @out   нет
    # @does  ELSE — JMP вперёд на свежую метку и метка IF тут; THEN
    # @does  ставит метку ELSE.
    def test_if_else_then(self):
        records, error = parse_ubrk(": main IF 1 ELSE 2 THEN ;")
        self.assertIsNone(error)
        self.assertEqual(compile_body(word_body(records, "main"),
                                      new_counter()),
                         ("JZ _L1", "PUSH 1", "JMP _L2", "_L1:",
                          "PUSH 2", "_L2:"))

    # @method test_begin_until() -> None
    # @in    нет
    # @out   нет
    # @does  BEGIN — метка тут; UNTIL — JZ назад на метку BEGIN;
    # @does  псевдоним KEY врезается инструкцией SYS 0.
    def test_begin_until(self):
        records, error = parse_ubrk(": main BEGIN KEY UNTIL ;")
        self.assertIsNone(error)
        self.assertEqual(compile_body(word_body(records, "main"),
                                      new_counter()),
                         ("_L1:", "SYS 0", "JZ _L1"))

    # @method test_begin_again() -> None
    # @in    нет
    # @out   нет
    # @does  AGAIN — JMP назад на метку BEGIN; тело из псевдонима,
    # @does  литерала и примитива врезается построчно.
    def test_begin_again(self):
        records, error = parse_ubrk(": main BEGIN EMIT 1 ADD AGAIN ;")
        self.assertIsNone(error)
        self.assertEqual(compile_body(word_body(records, "main"),
                                      new_counter()),
                         ("_L1:", "SYS 1", "PUSH 1", "ADD", "JMP _L1"))

    # @method test_nested_if_else() -> None
    # @in    нет
    # @out   нет
    # @does  IF в IF с ELSE: номера меток растут по порядку появления,
    # @does  THEN связывается с ближайшей незакрытой конструкцией.
    def test_nested_if_else(self):
        records, error = parse_ubrk(
            ": main IF 1 ELSE IF 2 ELSE 3 THEN THEN ;")
        self.assertIsNone(error)
        self.assertEqual(compile_body(word_body(records, "main"),
                                      new_counter()),
                         ("JZ _L1", "PUSH 1", "JMP _L2", "_L1:",
                          "JZ _L3", "PUSH 2", "JMP _L4", "_L3:",
                          "PUSH 3", "_L4:", "_L2:"))

    # @method test_begin_with_if_else() -> None
    # @in    нет
    # @out   нет
    # @does  IF/ELSE внутри BEGIN: EXIT — RET, UNTIL замыкает на метку
    # @does  BEGIN, номера не пересекаются.
    def test_begin_with_if_else(self):
        records, error = parse_ubrk(
            ": main BEGIN DUP IF DROP ELSE EXIT THEN UNTIL ;")
        self.assertIsNone(error)
        self.assertEqual(compile_body(word_body(records, "main"),
                                      new_counter()),
                         ("_L1:", "DUP", "JZ _L2", "DROP", "JMP _L3",
                          "_L2:", "RET", "_L3:", "JZ _L1"))


class TestBodies(unittest.TestCase):
    """Полные тела: все виды элементов и счётчик программы."""

    # @method test_full_body() -> None
    # @in    нет
    # @out   нет
    # @does  Тело со всеми видами элементов: ссылки var/text и
    # @does  производных — CALL, отрицательный литерал — PUSH
    # @does  с оборачиванием, EXIT — RET, BYE — HALT 0.
    def test_full_body(self):
        records, error = parse_ubrk(
            "var x\n"
            'text msg "Hi"\n'
            ": main msg prints -1 0 lts IF EXIT THEN BYE ;\n")
        self.assertIsNone(error)
        self.assertEqual(compile_body(word_body(records, "main"),
                                      new_counter()),
                         ("CALL msg", "CALL prints",
                          "PUSH 18446744073709551615", "PUSH 0",
                          "CALL lts", "JZ _L1", "RET", "_L1:",
                          "HALT 0"))

    # @method test_empty_body() -> None
    # @in    нет
    # @out   нет
    # @does  Пустое тело («: имя ;») компилируется в пустой кортеж.
    def test_empty_body(self):
        records, error = parse_ubrk(": main ;")
        self.assertIsNone(error)
        self.assertEqual(word_body(records, "main"), ())
        self.assertEqual(compile_body((), new_counter()), ())

    # @method test_counter_shared_across_bodies() -> None
    # @in    нет
    # @out   нет
    # @does  Счётчик один на программу: второе тело продолжает
    # @does  нумерацию первого (_L2 после _L1).
    def test_counter_shared_across_bodies(self):
        records, error = parse_ubrk(
            ": main IF NOP THEN ;\n"
            ": loop BEGIN AGAIN ;\n")
        self.assertIsNone(error)
        counter = new_counter()
        self.assertEqual(compile_body(word_body(records, "main"), counter),
                         ("JZ _L1", "NOP", "_L1:"))
        self.assertEqual(compile_body(word_body(records, "loop"), counter),
                         ("_L2:", "JMP _L2"))
        self.assertEqual(counter, {"n": 2})

    # @method test_direct_elements() -> None
    # @in    нет
    # @out   нет
    # @does  Контракт ветви — кортежи элементов: тело, заданное напрямую
    # @does  (без разбора), компилируется теми же кирпичами.
    def test_direct_elements(self):
        elements = (("construct", "IF"), ("word", "DROP"),
                    ("construct", "THEN"))
        self.assertEqual(compile_body(elements, new_counter()),
                         ("JZ _L1", "DROP", "_L1:"))


if __name__ == "__main__":
    unittest.main()
