# @uadro
# @file    tests/test_uvm_cli.py
# @layer   T0
# @branch  t0.uvm.cli
# @desc    Тесты запуска образа из файла: разбор аргументов и размеров,
# @desc    чтение файла, коды HALT и ловушек в коде выхода, ошибки
# @desc    запуска, сквозной запуск настоящим процессом
# @desc    (SPEC/L0-UVM.txt, разделы 2-3).

"""Тесты ветви t0.uvm.cli (tools/uvm_cli.py).

Кирпичи parse_size/parse_args/read_image проверяются напрямую;
полный запуск — кирпичом run_via_cli тест-набора (временный файл,
cli.main, подменённый stdout); сквозной тест TestProcess гоняет
настоящий процесс Python и проверяет код выхода процесса. Запуск
из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

from tests import uvm_testkit as tk
from tools import uvm_cli as cli
from tools import uvm_core as uc


# @method repo_root() -> str
# @in    нет
# @out   root: str — корень репозитория (каталог над tests)
# @does  Даёт корень репозитория для запуска tools/uvm_cli.py настоящим
# @does  процессом в тестах TestProcess.
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestParseSize(unittest.TestCase):
    """Разбор чисел-размеров: только цифры 1..2^31-1."""

    # @method test_digits_ok() -> None
    # @in    нет
    # @out   нет
    # @does  Обычные цифры разбираются в число.
    def test_digits_ok(self):
        self.assertEqual(cli.parse_size("64"), 64)
        self.assertEqual(cli.parse_size("1048576"), 1048576)

    # @method test_bad_numbers_are_none() -> None
    # @in    нет
    # @out   нет
    # @does  Пустая строка, не-цифры, знак и ноль дают None.
    def test_bad_numbers_are_none(self):
        for bad in ("", "abc", "1k", "-5", "0", " 8"):
            self.assertIsNone(cli.parse_size(bad), bad)

    # @method test_over_limit_is_none() -> None
    # @in    нет
    # @out   нет
    # @does  Потолок MAX_SIZE принимается, выше потолка — None.
    def test_over_limit_is_none(self):
        self.assertEqual(cli.parse_size(str(cli.MAX_SIZE)), cli.MAX_SIZE)
        self.assertIsNone(cli.parse_size(str(cli.MAX_SIZE + 1)))


class TestParseArgs(unittest.TestCase):
    """Разбор аргументов командной строки."""

    # @method test_no_args_is_none() -> None
    # @in    нет
    # @out   нет
    # @does  Пустые аргументы — None: путь образа обязателен.
    def test_no_args_is_none(self):
        self.assertIsNone(cli.parse_args([]))

    # @method test_flag_instead_of_path_is_none() -> None
    # @in    нет
    # @out   нет
    # @does  Флаг на месте пути — None: путь не может начинаться с --.
    def test_flag_instead_of_path_is_none(self):
        self.assertIsNone(cli.parse_args(["--ram", "64"]))

    # @method test_path_only_gives_defaults() -> None
    # @in    нет
    # @out   нет
    # @does  Только путь: размеры по умолчанию из ядра t0.uvm.core.
    def test_path_only_gives_defaults(self):
        parsed = cli.parse_args(["prog.uvm"])
        self.assertEqual(parsed, ("prog.uvm", uc.RAM_SIZE_DEFAULT,
                                  uc.DS_SIZE_DEFAULT, uc.RS_SIZE_DEFAULT))

    # @method test_flags_set_sizes() -> None
    # @in    нет
    # @out   нет
    # @does  Флаги --ram/--ds/--rs задают размеры машины.
    def test_flags_set_sizes(self):
        parsed = cli.parse_args(["prog.uvm", "--ram", "64",
                                 "--ds", "4", "--rs", "2"])
        self.assertEqual(parsed, ("prog.uvm", 64, 4, 2))

    # @method test_duplicate_flag_last_wins() -> None
    # @in    нет
    # @out   нет
    # @does  Повторный флаг берёт последнее значение.
    def test_duplicate_flag_last_wins(self):
        parsed = cli.parse_args(["p", "--ram", "64", "--ram", "128"])
        self.assertEqual(parsed, ("p", 128, uc.DS_SIZE_DEFAULT,
                                  uc.RS_SIZE_DEFAULT))

    # @method test_bad_tail_is_none() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестный флаг, флаг без значения, плохое число и лишний
    # @does  позиционный аргумент — None.
    def test_bad_tail_is_none(self):
        for argv in (["p", "--cpu", "1"], ["p", "--ram"],
                     ["p", "--ram", "abc"], ["p", "--ram", "0"],
                     ["p", "x"]):
            self.assertIsNone(cli.parse_args(argv), str(argv))


class TestReadImage(unittest.TestCase):
    """Чтение файла образа."""

    # @method test_reads_bytes() -> None
    # @in    нет
    # @out   нет
    # @does  Файл образа читается целиком, байт в байт.
    def test_reads_bytes(self):
        image = bytes([0x45]) + tk.imm64(3)
        with tk.image_file(image) as path:
            self.assertEqual(cli.read_image(path), image)

    # @method test_missing_file_is_none() -> None
    # @in    нет
    # @out   нет
    # @does  Несуществующий файл — None, без исключения.
    def test_missing_file_is_none(self):
        self.assertIsNone(cli.read_image("нет-такого-файла.uvm"))

    # @method test_directory_is_none() -> None
    # @in    нет
    # @out   нет
    # @does  Каталог вместо файла — None (IsADirectoryError — это
    # @does  OSError).
    def test_directory_is_none(self):
        self.assertIsNone(cli.read_image(tempfile.gettempdir()))


class TestMain(unittest.TestCase):
    """Полный запуск main: коды UVM — в код выхода, вывод — в stdout."""

    # @method test_halt_code_becomes_exit_code() -> None
    # @in    нет
    # @out   нет
    # @does  HALT 7: main возвращает 7, ничего не выводя.
    def test_halt_code_becomes_exit_code(self):
        image = bytes([0x45]) + tk.imm64(7)
        code, out = tk.run_via_cli(image)
        self.assertEqual(code, 7)
        self.assertEqual(out, b"")

    # @method test_char_output_program() -> None
    # @in    нет
    # @out   нет
    # @does  PUSH 72, SYS 1, PUSH 105, SYS 1, HALT 0: код 0, в stdout —
    # @does  байты "Hi".
    def test_char_output_program(self):
        image = tk.image_of([0x01, tk.imm64(72), 0x50, tk.imm64(1),
                             0x01, tk.imm64(105), 0x50, tk.imm64(1),
                             0x45, tk.imm64(0)])
        code, out = tk.run_via_cli(image)
        self.assertEqual(code, 0)
        self.assertEqual(out, b"Hi")

    # @method test_bad_opcode_exit_code() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестный опкод 0x99: main возвращает код ловушки 6.
    def test_bad_opcode_exit_code(self):
        code, out = tk.run_via_cli(tk.image_of([0x99, 0x45,
                                                tk.imm64(0)]))
        self.assertEqual(code, uc.TRAP_BAD_OPCODE)

    # @method test_image_larger_than_ram_exit_code() -> None
    # @in    нет
    # @out   нет
    # @does  Образ в 9 байтов при --ram 8: ловушка 7 загрузки — main
    # @does  возвращает 7.
    def test_image_larger_than_ram_exit_code(self):
        image = bytes([0x45]) + tk.imm64(0)
        code, out = tk.run_via_cli(image, ["--ram", "8"])
        self.assertEqual(code, uc.TRAP_OOB)

    # @method test_ds_overflow_exit_code() -> None
    # @in    нет
    # @out   нет
    # @does  Три PUSH при --ds 2: ловушка 3 — флаг доходит до машины.
    def test_ds_overflow_exit_code(self):
        image = tk.image_of([0x01, tk.imm64(1), 0x01, tk.imm64(2),
                             0x01, tk.imm64(3), 0x45, tk.imm64(0)])
        code, out = tk.run_via_cli(image, ["--ds", "2"])
        self.assertEqual(code, uc.TRAP_DS_FULL)


class TestMainErrors(unittest.TestCase):
    """Ошибки запуска: код 2 и сообщение в stderr."""

    # @method test_no_args_prints_usage() -> None
    # @in    нет
    # @out   нет
    # @does  Без аргументов: код 2, в stderr — подсказка использования.
    def test_no_args_prints_usage(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(cli.main([]), cli.USAGE_CODE)
        self.assertIn("использование", err.getvalue())

    # @method test_bad_flag_prints_usage() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестный флаг: код 2 и подсказка в stderr.
    def test_bad_flag_prints_usage(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(cli.main(["p", "--cpu"]), cli.USAGE_CODE)
        self.assertIn("использование", err.getvalue())

    # @method test_missing_file_prints_error() -> None
    # @in    нет
    # @out   нет
    # @does  Нечитаемый файл: код 2, в stderr — сообщение об ошибке.
    def test_missing_file_prints_error(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(cli.main(["нет-такого.uvm"]), cli.USAGE_CODE)
        self.assertIn("не читается", err.getvalue())


class TestProcess(unittest.TestCase):
    """Сквозной запуск настоящим процессом: код выхода до ОС."""

    # @method test_process_runs_program() -> None
    # @in    нет
    # @out   нет
    # @does  python tools/uvm_cli.py ОБРАЗ: процесс выводит "K" и
    # @does  завершается кодом 0.
    def test_process_runs_program(self):
        image = tk.image_of([0x01, tk.imm64(75), 0x50, tk.imm64(1),
                             0x45, tk.imm64(0)])
        with tk.image_file(image) as path:
            proc = subprocess.run(
                [sys.executable, os.path.join("tools", "uvm_cli.py"),
                 path],
                capture_output=True, cwd=repo_root(), timeout=60)
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, b"K")

    # @method test_process_exit_code_nonzero() -> None
    # @in    нет
    # @out   нет
    # @does  HALT 7 в образе: процесс завершается кодом 7 — код UVM
    # @does  доходит до операционной системы.
    def test_process_exit_code_nonzero(self):
        image = bytes([0x45]) + tk.imm64(7)
        with tk.image_file(image) as path:
            proc = subprocess.run(
                [sys.executable, os.path.join("tools", "uvm_cli.py"),
                 path],
                capture_output=True, cwd=repo_root(), timeout=60)
        self.assertEqual(proc.returncode, 7)


if __name__ == "__main__":
    unittest.main()
