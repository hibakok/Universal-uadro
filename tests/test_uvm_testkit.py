# @uadro
# @file    tests/test_uvm_testkit.py
# @layer   T0
# @branch  t0.infra.tests
# @desc    Тесты кирпичей тест-набора: run_with_io — прогон образа
# @desc    без процесса (эхо-фильтр до конца ввода, коды завершения,
# @desc    частичный вывод до ловушки, восстановление потоков) и проброс
# @desc    результата patched_stdin.

"""Тесты кирпичей тест-набора (ветвь t0.infra.tests).

run_with_io — основа золотых тестов собственных инструментов Этапа 4
(SPEC/L4-SELFHOST.txt, разделы 4 и 6): прогон образа без процесса
с подменёнными stdin/stdout. Эхо-фильтр повторяет потоковую модель
инструментов этапа: читать байт (SYS 0) до конца ввода и выводить
каждый прочитанный байт (SYS 1). Программы собираются кирпичами
image_of и imm64; адреса подсчитаны по формату инструкций
(SPEC/L0-UVM.txt, раздел 4): байт опкода, при наличии поля imm64 —
ещё восемь байтов.
"""

import sys
import unittest

from tests import uvm_testkit as tk
from tools import uvm_core as uc


# Эхо-фильтр «ввод -> вывод» до конца ввода: цикл читает байт (SYS 0),
# на признаке конца ввода завершается (HALT 0), иначе выводит байт
# (SYS 1) и повторяет. Адреса: loop = 0, emit = 39.
ECHO_FILTER = [
    0x50, tk.imm64(0),              # 0:  loop: SYS 0 ( -- c )
    0x03,                           # 9:        DUP    ( -- c c )
    0x01, tk.imm64(uc.WORD_MASK),   # 10:       PUSH eof ( -- c c eof )
    0x30,                           # 19:       EQ     ( -- c ф )
    0x41, tk.imm64(39),             # 20:       JZ emit ( -- c )
    0x02,                           # 29:       DROP   ( -- )
    0x45, tk.imm64(0),              # 30:       HALT 0
    0x50, tk.imm64(1),              # 39: emit: SYS 1 ( c -- )
    0x40, tk.imm64(0),              # 48:       JMP loop
]


class TestRunWithIo(unittest.TestCase):
    """Кирпич run_with_io: прогон образа с подменёнными потоками."""

    # @method test_echo_filter_copies_feed() -> None
    # @in    нет
    # @out   нет
    # @does  Эхо-фильтр копирует ввод в вывод байт в байт и завершается
    # @does  кодом 0 на признаке конца ввода.
    def test_echo_filter_copies_feed(self):
        code, out = tk.run_with_io(tk.image_of(ECHO_FILTER), b"Hi")
        self.assertEqual(code, 0)
        self.assertEqual(out, b"Hi")

    # @method test_echo_filter_empty_feed() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой ввод: первое же чтение даёт признак конца ввода,
    # @does  вывод пуст, код 0.
    def test_echo_filter_empty_feed(self):
        code, out = tk.run_with_io(tk.image_of(ECHO_FILTER), b"")
        self.assertEqual(code, 0)
        self.assertEqual(out, b"")

    # @method test_halt_code_passes_through() -> None
    # @in    нет
    # @out   нет
    # @does  Код остановки HALT проходит наружу: HALT 16 — код 16
    # @does  (контракт ошибок входа инструментов Этапа 4, раздел 4).
    def test_halt_code_passes_through(self):
        image = tk.image_of([0x45, tk.imm64(16)])
        self.assertEqual(tk.run_with_io(image), (16, b""))

    # @method test_trap_keeps_partial_output() -> None
    # @in    нет
    # @out   нет
    # @does  Ловушка 6 (неизвестный опкод) становится кодом завершения;
    # @does  байты, выведенные до ловушки, сохраняются в выходе.
    def test_trap_keeps_partial_output(self):
        image = tk.image_of([
            0x01, tk.imm64(65),   # PUSH 65
            0x50, tk.imm64(1),    # SYS 1: вывод "A"
            0xFF,                 # неизвестный опкод: ловушка 6
        ])
        self.assertEqual(tk.run_with_io(image), (6, b"A"))

    # @method test_streams_restored() -> None
    # @in    нет
    # @out   нет
    # @does  После прогона stdin и stdout хоста восстановлены: подмена
    # @does  действует только внутри run_with_io.
    def test_streams_restored(self):
        before = (sys.stdin, sys.stdout)
        tk.run_with_io(tk.image_of([0x45, tk.imm64(0)]))
        self.assertEqual((sys.stdin, sys.stdout), before)


class TestPatchedStdin(unittest.TestCase):
    """Кирпич patched_stdin: проброс результата и восстановление."""

    # @method test_returns_action_result() -> None
    # @in    нет
    # @out   нет
    # @does  patched_stdin возвращает значение, возвращённое действием.
    def test_returns_action_result(self):
        src = tk.FakeStream()
        self.assertEqual(tk.patched_stdin(src, lambda: 42), 42)

    # @method test_stdin_restored_after_error() -> None
    # @in    нет
    # @out   нет
    # @does  Действие, поднявшее исключение, не ломает восстановление
    # @does  stdin; исключение пробрасывается наружу.
    def test_stdin_restored_after_error(self):
        saved = sys.stdin
        src = tk.FakeStream()

        def boom():
            raise RuntimeError("сбой действия")

        with self.assertRaises(RuntimeError):
            tk.patched_stdin(src, boom)
        self.assertIs(sys.stdin, saved)


if __name__ == "__main__":
    unittest.main()
