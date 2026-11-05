# @uadro
# @file    tests/test_uasm_cli.py
# @layer   T0
# @branch  t0.uasm.cli
# @desc    Тесты командных режимов uAsm: разбор аргументов, чтение
# @desc    исходников и запись результата, режимы asm и dis, ошибки
# @desc    с кодом 2 и сообщением в stderr, раунд-трип asm -> dis -> asm
# @desc    через CLI и сквозной запуск настоящим процессом
# @desc    (SPEC/L2-UASM.txt, раздел 9).

"""Тесты ветви t0.uasm.cli (tools/uasm_cli.py).

Кирпичи parse_args/parse_asm_args/parse_dis_args, read_text/read_image,
write_bytes/write_text проверяются напрямую; режимы — через cli.main
с временными файлами (source_file — исходник .uasm, file_bytes/
file_text — чтение результата); вывод dis в stdout проверяется подменой
потока; сквозной тест TestProcess гоняет настоящий процесс Python
и проверяет код выхода и stdout. Раунд-трип asm -> dis -> asm через CLI
собирает критерий готовности Этапа 2 (SPEC, раздел 8).

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

from tools import uasm_cli as cli
from tools.uvm_table import entry_by_mnemonic


# @method repo_root() -> str
# @in    нет
# @out   root: str — корень репозитория (каталог над tests)
# @does  Даёт корень репозитория для запуска tools/uasm_cli.py настоящим
# @does  процессом в тестах TestProcess.
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# @method op(mnemonic) -> bytes
# @in    mnemonic: str — мнемоника опкода UVM
# @out   data: bytes — один байт опкода
# @does  Байт опкода по мнемонике — для золотых байтов тестов.
# @depends entry_by_mnemonic
def op(mnemonic):
    return bytes([entry_by_mnemonic(mnemonic)[0]])


# @method word(value) -> bytes
# @in    value: int — значение слова
# @out   data: bytes — восемь байтов little-endian
# @does  Поле imm64 в золотых байтах тестов.
def word(value):
    return (value % (1 << 64)).to_bytes(8, "little")


# @method source_file(text) -> contextmanager
# @in    text: str — исходный текст uAsm
# @out   cm: contextmanager — выдаёт путь к временному файлу .uasm
# @does  Записывает текст во временный файл; путь действует внутри with,
# @does  файл и каталог удаляются на выходе; соседние файлы результатов
# @does  кладутся в тот же каталог через os.path.dirname.
# @uses  tempfile — временный каталог теста
@contextlib.contextmanager
def source_file(text):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prog.uasm")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)
        yield path


# @method file_bytes(path) -> bytes
# @in    path: str — путь к файлу результата
# @out   data: bytes — содержимое файла целиком
# @does  Читает файл байтами — для проверки образов, записанных CLI.
def file_bytes(path):
    with open(path, "rb") as handle:
        return handle.read()


# @method file_text(path) -> str
# @in    path: str — путь к файлу результата
# @out   text: str — содержимое файла в кодировке UTF-8
# @does  Читает файл текстом — для проверки текстов, записанных CLI.
def file_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


# @method near(path, name) -> str
# @in    path: str — путь к временному исходнику из source_file
# @in    name: str — имя файла результата
# @out   target: str — путь к соседнему файлу в том же каталоге
# @does  Строит путь результата рядом с исходником: файлы режима живут
# @does  в одном временном каталоге source_file.
def near(path, name):
    return os.path.join(os.path.dirname(path), name)


class TestParseArgs(unittest.TestCase):
    """Разбор аргументов режимов asm и dis (SPEC, раздел 9)."""

    # @method test_no_args_is_none() -> None
    # @in    нет
    # @out   нет
    # @does  Пустые аргументы — None: режим обязателен.
    def test_no_args_is_none(self):
        self.assertIsNone(cli.parse_args([]))

    # @method test_unknown_mode_is_none() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестный режим — None.
    def test_unknown_mode_is_none(self):
        self.assertIsNone(cli.parse_args(["run", "a.uasm", "b.uvm"]))

    # @method test_asm_two_paths() -> None
    # @in    нет
    # @out   нет
    # @does  Режим asm с двумя путями разбирается в тройку.
    def test_asm_two_paths(self):
        parsed = cli.parse_args(["asm", "s.uasm", "o.uvm"])
        self.assertEqual(parsed, ("asm", "s.uasm", "o.uvm"))

    # @method test_asm_wrong_count_is_none() -> None
    # @in    нет
    # @out   нет
    # @does  Ноль, один и три пути после asm — None.
    def test_asm_wrong_count_is_none(self):
        for argv in (["asm"], ["asm", "s"], ["asm", "s", "o", "x"]):
            self.assertIsNone(cli.parse_args(argv), str(argv))

    # @method test_dis_paths_with_and_without_text() -> None
    # @in    нет
    # @out   нет
    # @does  Режим dis: один путь — текст None (stdout), два пути —
    # @does  путь текста.
    def test_dis_paths_with_and_without_text(self):
        self.assertEqual(cli.parse_args(["dis", "b.uvm"]),
                         ("dis", "b.uvm", None))
        self.assertEqual(cli.parse_args(["dis", "b.uvm", "t.uasm"]),
                         ("dis", "b.uvm", "t.uasm"))

    # @method test_dis_wrong_count_is_none() -> None
    # @in    нет
    # @out   нет
    # @does  Ноль и три пути после dis — None.
    def test_dis_wrong_count_is_none(self):
        for argv in (["dis"], ["dis", "a", "b", "c"]):
            self.assertIsNone(cli.parse_args(argv), str(argv))


class TestFileBricks(unittest.TestCase):
    """Кирпичи чтения и записи файлов CLI."""

    # @method test_read_text_returns_file_content() -> None
    # @in    нет
    # @out   нет
    # @does  Исходник читается целиком в UTF-8.
    def test_read_text_returns_file_content(self):
        with source_file("PUSH 1\nHALT 0") as path:
            self.assertEqual(cli.read_text(path), "PUSH 1\nHALT 0")

    # @method test_read_text_failures_are_none() -> None
    # @in    нет
    # @out   нет
    # @does  Отсутствие файла, каталог и плохая кодировка UTF-8 — None.
    def test_read_text_failures_are_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.uasm")
            with open(bad, "wb") as handle:
                handle.write(b"\xff\xfe\x00")
            self.assertIsNone(cli.read_text(bad))
        self.assertIsNone(cli.read_text("нет-такого.uasm"))
        self.assertIsNone(cli.read_text(tempfile.gettempdir()))

    # @method test_read_image_returns_bytes() -> None
    # @in    нет
    # @out   нет
    # @does  Образ читается байт в байт.
    def test_read_image_returns_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "b.uvm")
            with open(path, "wb") as handle:
                handle.write(b"\x01\x02\x03")
            self.assertEqual(cli.read_image(path), b"\x01\x02\x03")

    # @method test_read_image_failures_are_none() -> None
    # @in    нет
    # @out   нет
    # @does  Отсутствие файла и каталог — None.
    def test_read_image_failures_are_none(self):
        self.assertIsNone(cli.read_image("нет-такого.uvm"))
        self.assertIsNone(cli.read_image(tempfile.gettempdir()))

    # @method test_write_bytes_ok_returns_none() -> None
    # @in    нет
    # @out   нет
    # @does  Запись байтов проходит, ошибка — None, файл совпадает.
    def test_write_bytes_ok_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.uvm")
            self.assertIsNone(cli.write_bytes(path, b"\x01\x02"))
            self.assertEqual(file_bytes(path), b"\x01\x02")

    # @method test_write_bytes_failure_returns_error() -> None
    # @in    нет
    # @out   нет
    # @does  Каталог вместо файла и путь в несуществующем каталоге —
    # @does  текст ошибки.
    def test_write_bytes_failure_returns_error(self):
        error = cli.write_bytes(tempfile.gettempdir(), b"\x01")
        self.assertIn("не пишется файл образа", error)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "нет", "out.uvm")
            self.assertIn("не пишется файл образа",
                          cli.write_bytes(path, b"\x01"))

    # @method test_write_text_ok_returns_none() -> None
    # @in    нет
    # @out   нет
    # @does  Запись текста проходит, ошибка — None, файл совпадает.
    def test_write_text_ok_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.uasm")
            self.assertIsNone(cli.write_text(path, "NOP\n"))
            self.assertEqual(file_text(path), "NOP\n")

    # @method test_write_text_failure_returns_error() -> None
    # @in    нет
    # @out   нет
    # @does  Каталог вместо файла — текст ошибки.
    def test_write_text_failure_returns_error(self):
        error = cli.write_text(tempfile.gettempdir(), "NOP\n")
        self.assertIn("не пишется файл текста", error)


class TestMainAsm(unittest.TestCase):
    """Режим asm: сборка исходника в файл образа."""

    # @method test_asm_writes_image() -> None
    # @in    нет
    # @out   нет
    # @does  Вывод символа на uAsm: код 0 и золотые байты образа.
    def test_asm_writes_image(self):
        with source_file("PUSH 65\nSYS 1\nHALT 0") as path:
            image = near(path, "out.uvm")
            self.assertEqual(cli.main(["asm", path, image]), 0)
            self.assertEqual(file_bytes(image),
                             op("PUSH") + word(65) + op("SYS") + word(1)
                             + op("HALT") + word(0))

    # @method test_asm_assemble_error() -> None
    # @in    нет
    # @out   нет
    # @does  Ошибка сборки печатается в stderr с номером строки, код 2,
    # @does  файл образа не создаётся.
    def test_asm_assemble_error(self):
        err = io.StringIO()
        with source_file("FOO\n") as path:
            image = near(path, "out.uvm")
            with contextlib.redirect_stderr(err):
                self.assertEqual(cli.main(["asm", path, image]),
                                 cli.USAGE_CODE)
            self.assertFalse(os.path.exists(image))
        self.assertIn("uAsm: строка 1: неизвестная мнемоника FOO",
                      err.getvalue())

    # @method test_asm_missing_source() -> None
    # @in    нет
    # @out   нет
    # @does  Нечитаемый исходник: код 2 и сообщение в stderr.
    def test_asm_missing_source(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(cli.main(["asm", "нет-такого.uasm", "o.uvm"]),
                             cli.USAGE_CODE)
        self.assertIn("не читается исходник", err.getvalue())

    # @method test_asm_unwritable_image() -> None
    # @in    нет
    # @out   нет
    # @does  Незаписываемый образ: код 2 и сообщение в stderr.
    def test_asm_unwritable_image(self):
        err = io.StringIO()
        with source_file("NOP") as path:
            image = near(path, os.path.join("нет", "out.uvm"))
            with contextlib.redirect_stderr(err):
                self.assertEqual(cli.main(["asm", path, image]),
                                 cli.USAGE_CODE)
        self.assertIn("не пишется файл образа", err.getvalue())


class TestMainDis(unittest.TestCase):
    """Режим dis: дизассемблирование образа в файл или stdout."""

    # @method test_dis_prints_stdout() -> None
    # @in    нет
    # @out   нет
    # @does  Без пути текста дизассемблирование печатается в stdout:
    # @does  HALT 0 — строка «HALT 0» с переводом.
    def test_dis_prints_stdout(self):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "halt.uvm")
            with open(path, "wb") as handle:
                handle.write(op("HALT") + word(0))
            with contextlib.redirect_stdout(out):
                self.assertEqual(cli.main(["dis", path]), 0)
        self.assertEqual(out.getvalue(), "HALT 0\n")

    # @method test_dis_writes_file() -> None
    # @in    нет
    # @out   нет
    # @does  С путём текста дизассемблирование пишется в файл: хвост
    # @does  данных — директивы DB.
    def test_dis_writes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            image = os.path.join(tmp, "tail.uvm")
            text = os.path.join(tmp, "tail.uasm")
            with open(image, "wb") as handle:
                handle.write(op("HALT") + word(0) + b"\x01\x02")
            self.assertEqual(cli.main(["dis", image, text]), 0)
            self.assertEqual(file_text(text), "HALT 0\nDB 1 2\n")

    # @method test_dis_missing_image() -> None
    # @in    нет
    # @out   нет
    # @does  Нечитаемый образ: код 2 и сообщение в stderr.
    def test_dis_missing_image(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(cli.main(["dis", "нет-такого.uvm"]),
                             cli.USAGE_CODE)
        self.assertIn("не читается образ", err.getvalue())

    # @method test_dis_unwritable_text() -> None
    # @in    нет
    # @out   нет
    # @does  Незаписываемый текст: код 2 и сообщение в stderr.
    def test_dis_unwritable_text(self):
        err = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            image = os.path.join(tmp, "halt.uvm")
            with open(image, "wb") as handle:
                handle.write(op("HALT") + word(0))
            text = os.path.join(tmp, "нет", "out.uasm")
            with contextlib.redirect_stderr(err):
                self.assertEqual(cli.main(["dis", image, text]),
                                 cli.USAGE_CODE)
        self.assertIn("не пишется файл текста", err.getvalue())


class TestCliRoundTrip(unittest.TestCase):
    """Раунд-трип через CLI: asm -> dis -> asm (SPEC, раздел 8)."""

    # @method test_cli_roundtrip() -> None
    # @in    нет
    # @out   нет
    # @does  Собранный образ дизассемблируется в текст и собирается
    # @does  обратно в те же байты: инструкции и хвост данных DB.
    def test_cli_roundtrip(self):
        with source_file("PUSH 10\nHALT 0\nDB 1 2 3") as path:
            image = near(path, "round.uvm")
            text = near(path, "round.uasm")
            again = near(path, "round2.uvm")
            self.assertEqual(cli.main(["asm", path, image]), 0)
            self.assertEqual(cli.main(["dis", image, text]), 0)
            self.assertEqual(file_text(text), "PUSH 10\nHALT 0\nDB 1 2 3\n")
            self.assertEqual(cli.main(["asm", text, again]), 0)
            self.assertEqual(file_bytes(again), file_bytes(image))

    # @method test_cli_empty_source() -> None
    # @in    нет
    # @out   нет
    # @does  Пустой исходник: пустой образ, пустой текст и снова пустой
    # @does  образ — без ошибок.
    def test_cli_empty_source(self):
        with source_file("") as path:
            image = near(path, "empty.uvm")
            text = near(path, "empty.uasm")
            again = near(path, "empty2.uvm")
            self.assertEqual(cli.main(["asm", path, image]), 0)
            self.assertEqual(file_bytes(image), b"")
            self.assertEqual(cli.main(["dis", image, text]), 0)
            self.assertEqual(file_text(text), "")
            self.assertEqual(cli.main(["asm", text, again]), 0)
            self.assertEqual(file_bytes(again), b"")


class TestProcess(unittest.TestCase):
    """Сквозной запуск настоящим процессом: коды до ОС."""

    # @method test_process_asm_dis() -> None
    # @in    нет
    # @out   нет
    # @does  python tools/uasm_cli.py asm ... затем dis: оба процесса
    # @does  завершаются кодом 0, stdout dis — текст с хвостом DB.
    def test_process_asm_dis(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "p.uasm")
            img = os.path.join(tmp, "p.uvm")
            with open(src, "w", encoding="utf-8") as handle:
                handle.write("PUSH 10\nHALT 0\nDB 1 2 3")
            run = [sys.executable, os.path.join("tools", "uasm_cli.py")]
            asm = subprocess.run(run + ["asm", src, img],
                                 capture_output=True, cwd=repo_root(),
                                 timeout=60)
            dis = subprocess.run(run + ["dis", img],
                                 capture_output=True, cwd=repo_root(),
                                 timeout=60)
        self.assertEqual(asm.returncode, 0)
        self.assertEqual(dis.returncode, 0)
        self.assertEqual(dis.stdout, b"PUSH 10\nHALT 0\nDB 1 2 3\n")

    # @method test_process_error_code() -> None
    # @in    нет
    # @out   нет
    # @does  Нечитаемый исходник: процесс завершается кодом 2, ошибка —
    # @does  в stderr.
    def test_process_error_code(self):
        run = [sys.executable, os.path.join("tools", "uasm_cli.py")]
        proc = subprocess.run(run + ["asm", "нет-такого.uasm", "x.uvm"],
                               capture_output=True, cwd=repo_root(),
                               timeout=60)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("не читается исходник",
                      proc.stderr.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
