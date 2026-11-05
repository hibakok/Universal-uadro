# @uadro
# @file    tests/test_ubrick_cli.py
# @layer   T0
# @branch  t0.ubrick.cli
# @desc    Тесты командного режима uBrick: разбор аргументов с флагом
# @desc    --asm, чтение исходника и запись результата, режим compile,
# @desc    ошибки с кодом 2 и сообщением в stderr, сквозной запуск
# @desc    настоящим процессом (compile, затем uvm_cli)
# @desc    (SPEC/L3-UBRICK.txt, раздел 9).

"""Тесты ветви t0.ubrick.cli (tools/ubrick_cli.py).

Кирпичи parse_args/parse_compile_args, read_text, write_bytes/
write_text проверяются напрямую; режим compile — через cli.main
с временными файлами (source_file — исходник .ubrk, file_bytes/
file_text — чтение результата): образ и текст --asm сверяются
с золотыми значениями ветвей t0.ubrick.parse и t0.ubrick.build;
ошибка сборки проверяется заглушкой build_ubrk (записи разбора
ошибки сборки не дают — контракт t0.ubrick.build). TestProcess
гоняет настоящие процессы Python: compile, затем исполнение образа
uvm_cli (вывод «Hi», код 0).

Запуск из корня репозитория:
    python -m unittest discover -s tests -t .
"""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

from tools import ubrick_cli as cli
from tools.ubrick_build import build_text, build_ubrk
from tools.ubrick_parse import parse_ubrk

HELLO = ": main\n  72 EMIT\n  105 EMIT ;\n"    # вывод «Hi», код 0


# @method repo_root() -> str
# @in    нет
# @out   root: str — корень репозитория (каталог над tests)
# @does  Даёт корень репозитория для запуска tools/ubrick_cli.py настоящим
# @does  процессом в тестах TestProcess.
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# @method source_file(text) -> contextmanager
# @in    text: str — исходный текст uBrick
# @out   cm: contextmanager — выдаёт путь к временному файлу .ubrk
# @does  Записывает текст во временный файл; путь действует внутри with,
# @does  файл и каталог удаляются на выходе; соседние файлы результатов
# @does  кладутся в тот же каталог через os.path.dirname.
# @uses  tempfile — временный каталог теста
@contextlib.contextmanager
def source_file(text):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prog.ubrk")
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


# @method golden_pair(source) -> tuple
# @in    source: str — исходный текст uBrick
# @out   pair: tuple — (золотой образ, золотой текст uAsm); ошибка
# @out   разбора или сборки — ошибка теста
# @does  Собирает эталонные значения режима: образ build_ubrk и текст
# @does  build_text по записям parse_ubrk — кирпичи ветвей t0.ubrick.*
# @does  уже покрыты их тестами, CLI обязан совпасть с ними байт в байт.
# @depends parse_ubrk, build_ubrk, build_text
def golden_pair(source):
    records, error = parse_ubrk(source)
    assert error is None, error
    image, build_error = build_ubrk(records)
    assert build_error is None, build_error
    return image, build_text(records)


class TestParseArgs(unittest.TestCase):
    """Разбор аргументов режима compile (SPEC, раздел 9)."""

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
        self.assertIsNone(cli.parse_args(["run", "a.ubrk", "b.uvm"]))

    # @method test_compile_two_paths() -> None
    # @in    нет
    # @out   нет
    # @does  Режим compile с двумя путями разбирается в четвёрку без
    # @does  текста --asm.
    def test_compile_two_paths(self):
        parsed = cli.parse_args(["compile", "s.ubrk", "o.uvm"])
        self.assertEqual(parsed, ("compile", "s.ubrk", "o.uvm", None))

    # @method test_compile_with_asm_flag() -> None
    # @in    нет
    # @out   нет
    # @does  Флаг --asm с путём текста — четвёрка с путём текста.
    def test_compile_with_asm_flag(self):
        parsed = cli.parse_args(["compile", "s.ubrk", "o.uvm",
                                 "--asm", "t.uasm"])
        self.assertEqual(parsed, ("compile", "s.ubrk", "o.uvm", "t.uasm"))

    # @method test_compile_wrong_args_are_none() -> None
    # @in    нет
    # @out   нет
    # @does  Ноль и один путь, три пути, флаг без значения, чужой флаг,
    # @does  флаг на месте пути и лишний аргумент — None.
    def test_compile_wrong_args_are_none(self):
        for argv in (
            ["compile"],
            ["compile", "s"],
            ["compile", "s", "o", "x"],
            ["compile", "s", "o", "--asm"],
            ["compile", "s", "o", "--dump", "t"],
            ["compile", "--asm", "t", "s", "o"],
            ["compile", "s", "o", "--asm", "t", "x"],
        ):
            self.assertIsNone(cli.parse_args(argv), str(argv))


class TestFileBricks(unittest.TestCase):
    """Кирпичи чтения и записи файлов CLI."""

    # @method test_read_text_returns_file_content() -> None
    # @in    нет
    # @out   нет
    # @does  Исходник читается целиком в UTF-8.
    def test_read_text_returns_file_content(self):
        with source_file(HELLO) as path:
            self.assertEqual(cli.read_text(path), HELLO)

    # @method test_read_text_failures_are_none() -> None
    # @in    нет
    # @out   нет
    # @does  Отсутствие файла, каталог и плохая кодировка UTF-8 — None.
    def test_read_text_failures_are_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.ubrk")
            with open(bad, "wb") as handle:
                handle.write(b"\xff\xfe\x00")
            self.assertIsNone(cli.read_text(bad))
        self.assertIsNone(cli.read_text("нет-такого.ubrk"))
        self.assertIsNone(cli.read_text(tempfile.gettempdir()))

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


class TestMainCompile(unittest.TestCase):
    """Режим compile: сборка исходника в файл образа (SPEC, раздел 9)."""

    # @method test_compile_writes_image() -> None
    # @in    нет
    # @out   нет
    # @does  Вывод символа на uBrick: код 0 и золотой образ ветви
    # @does  t0.ubrick.build байт в байт.
    def test_compile_writes_image(self):
        golden, _ = golden_pair(HELLO)
        with source_file(HELLO) as path:
            image = near(path, "out.uvm")
            self.assertEqual(cli.main(["compile", path, image]), 0)
            self.assertEqual(file_bytes(image), golden)

    # @method test_compile_writes_asm_text() -> None
    # @in    нет
    # @out   нет
    # @does  С флагом --asm дополнительно записывается промежуточный
    # @does  текст uAsm — золотой текст ветви t0.ubrick.build.
    def test_compile_writes_asm_text(self):
        golden_image, golden_text = golden_pair(HELLO)
        with source_file(HELLO) as path:
            image = near(path, "out.uvm")
            text = near(path, "out.uasm")
            self.assertEqual(
                cli.main(["compile", path, image, "--asm", text]), 0)
            self.assertEqual(file_bytes(image), golden_image)
            self.assertEqual(file_text(text), golden_text)

    # @method test_compile_parse_error() -> None
    # @in    нет
    # @out   нет
    # @does  Ошибка разбора печатается в stderr с номером строки, код 2,
    # @does  файл образа не создаётся.
    def test_compile_parse_error(self):
        err = io.StringIO()
        with source_file("FOO\n") as path:
            image = near(path, "out.uvm")
            with contextlib.redirect_stderr(err):
                self.assertEqual(cli.main(["compile", path, image]),
                                 cli.USAGE_CODE)
            self.assertFalse(os.path.exists(image))
        self.assertIn("uBrick: строка 1: слово вне определения FOO",
                      err.getvalue())

    # @method test_compile_build_error() -> None
    # @in    нет
    # @out   нет
    # @does  Ошибка сборки (заглушка build_ubrk) печатается в stderr
    # @does  как есть, код 2, файл образа не создаётся.
    # @uses   cli.build_ubrk — подмена кирпича сборки на время теста
    def test_compile_build_error(self):
        err = io.StringIO()
        saved = cli.build_ubrk
        cli.build_ubrk = lambda records: (None, "uAsm: строка 1: тест")
        try:
            with source_file(": main ;\n") as path:
                image = near(path, "out.uvm")
                with contextlib.redirect_stderr(err):
                    self.assertEqual(cli.main(["compile", path, image]),
                                     cli.USAGE_CODE)
                self.assertFalse(os.path.exists(image))
        finally:
            cli.build_ubrk = saved
        self.assertIn("uAsm: строка 1: тест", err.getvalue())

    # @method test_compile_missing_source() -> None
    # @in    нет
    # @out   нет
    # @does  Нечитаемый исходник: код 2 и сообщение в stderr.
    def test_compile_missing_source(self):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            self.assertEqual(
                cli.main(["compile", "нет-такого.ubrk", "o.uvm"]),
                cli.USAGE_CODE)
        self.assertIn("не читается исходник", err.getvalue())

    # @method test_compile_unwritable_image() -> None
    # @in    нет
    # @out   нет
    # @does  Незаписываемый образ: код 2 и сообщение в stderr.
    def test_compile_unwritable_image(self):
        err = io.StringIO()
        with source_file(HELLO) as path:
            image = near(path, os.path.join("нет", "out.uvm"))
            with contextlib.redirect_stderr(err):
                self.assertEqual(cli.main(["compile", path, image]),
                                 cli.USAGE_CODE)
        self.assertIn("не пишется файл образа", err.getvalue())

    # @method test_compile_unwritable_asm() -> None
    # @in    нет
    # @out   нет
    # @does  Незаписываемый текст --asm: образ уже записан, код 2
    # @does  и сообщение в stderr.
    def test_compile_unwritable_asm(self):
        err = io.StringIO()
        with source_file(HELLO) as path:
            image = near(path, "out.uvm")
            text = near(path, os.path.join("нет", "out.uasm"))
            with contextlib.redirect_stderr(err):
                self.assertEqual(
                    cli.main(["compile", path, image, "--asm", text]),
                    cli.USAGE_CODE)
            self.assertTrue(os.path.exists(image))
        self.assertIn("не пишется файл текста", err.getvalue())


class TestProcess(unittest.TestCase):
    """Сквозной запуск настоящим процессом: коды до ОС."""

    # @method test_process_compile_and_run() -> None
    # @in    нет
    # @out   нет
    # @does  python tools/ubrick_cli.py compile, затем python
    # @does  tools/uvm_cli.py ОБРАЗ: оба процесса завершаются кодом 0,
    # @does  stdout исполнения — «Hi».
    def test_process_compile_and_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "hello.ubrk")
            img = os.path.join(tmp, "hello.uvm")
            with open(src, "w", encoding="utf-8") as handle:
                handle.write(HELLO)
            compile_run = [sys.executable,
                           os.path.join("tools", "ubrick_cli.py")]
            compiled = subprocess.run(compile_run + ["compile", src, img],
                                      capture_output=True, cwd=repo_root(),
                                      timeout=60)
            run = [sys.executable, os.path.join("tools", "uvm_cli.py")]
            executed = subprocess.run(run + [img],
                                      capture_output=True, cwd=repo_root(),
                                      timeout=60)
        self.assertEqual(compiled.returncode, 0)
        self.assertEqual(executed.returncode, 0)
        self.assertEqual(executed.stdout, b"Hi")

    # @method test_process_asm_flag() -> None
    # @in    нет
    # @out   нет
    # @does  Настоящий процесс с флагом --asm: код 0, файл текста
    # @does  содержит пролог CALL main и HALT 0.
    def test_process_asm_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "p.ubrk")
            img = os.path.join(tmp, "p.uvm")
            asm = os.path.join(tmp, "p.uasm")
            with open(src, "w", encoding="utf-8") as handle:
                handle.write(HELLO)
            run = [sys.executable, os.path.join("tools", "ubrick_cli.py")]
            proc = subprocess.run(
                run + ["compile", src, img, "--asm", asm],
                capture_output=True, cwd=repo_root(), timeout=60)
            text = file_text(asm)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("CALL main", text)
        self.assertIn("HALT 0", text)

    # @method test_process_error_code() -> None
    # @in    нет
    # @out   нет
    # @does  Нечитаемый исходник: процесс завершается кодом 2, ошибка —
    # @does  в stderr.
    def test_process_error_code(self):
        run = [sys.executable, os.path.join("tools", "ubrick_cli.py")]
        proc = subprocess.run(
            run + ["compile", "нет-такого.ubrk", "x.uvm"],
            capture_output=True, cwd=repo_root(), timeout=60)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("не читается исходник",
                      proc.stderr.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
