# @uadro
# @file    tests/test_ubrick_source.py
# @layer   T0
# @branch  t0.ubrick.source
# @desc    Тесты загрузчика исходников uBrick: оператор use
# @desc    (SPEC/L3-UBRICK.txt, v0.3) — склейка файлов, сквозная
# @desc    нумерация строк, каталоги включений, состояние определения,
# @desc    ошибки загрузчика, сборка и запуск многофайловой программы.

"""Тесты ветви t0.ubrick.source (tools/ubrick_source.py).

Кирпич resolve_uses проверяется на временных файлах: текст без
use-строк возвращается неизменным; строки use заменяются строками
включённого файла; нумерация строк объединённого текста сквозная —
ошибки загрузчика и разбора дают одни и те же номера; каталог
включённого файла — база его собственных use-путей; комментарии,
литералы в кавычках и однострочные определения не сбивают состояние
определения; ошибки — «use без имени файла», «лишние слова после
use», «use внутри определения», «не читается use-файл X»,
«циклический use X».

Многофайловая программа собирается командой compile (cli.main): образ
равен однофайлочному эквиваленту байт в байт и исполняется кирпичом
run_with_io; TestProcess гоняет настоящие процессы: compile, затем
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

from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools.ubrick_build import build_ubrk
from tools.ubrick_parse import parse_ubrk
from tools.ubrick_source import resolve_uses

HELLO_WORD = ": hi\n  72 EMIT 105 EMIT ;\n"   # слово печатает «Hi»
HELLO_MAIN = "use part.ubrk\n: main hi ;\n"   # main.ubrk: слово из part


# @method repo_root() -> str
# @in    нет
# @out   root: str — корень репозитория (каталог над tests)
# @does  Даёт корень репозитория для запуска инструментов настоящим
# @does  процессом в TestProcess.
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# @method source_tree(files) -> contextmanager
# @in    files: dict — имя файла (с подкаталогами) -> текст
# @out   cm: contextmanager — выдаёт путь к каталогу с файлами
# @does  Записывает набор файлов .ubrk во временный каталог; каталог
# @does  удаляется на выходе; кирпич всех тестов ветви.
# @uses  tempfile — временный каталог теста
@contextlib.contextmanager
def source_tree(files):
    with tempfile.TemporaryDirectory() as tmp:
        for name, text in files.items():
            path = os.path.join(tmp, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(text)
        yield tmp


# @method main_of(tmp) -> str
# @in    tmp: str — каталог с исходниками
# @out   path: str — путь к главному файлу main.ubrk
# @does  Даёт путь главного исходника дерева теста.
def main_of(tmp):
    return os.path.join(tmp, "main.ubrk")


# @method resolve(tmp, text) -> tuple
# @in    tmp: str — каталог с исходниками (база use-путей)
# @in    text: str — текст главного исходника
# @out   pair: tuple — результат resolve_uses для main.ubrk
# @does  Вызывает загрузчик с главным файлом в каталоге дерева.
# @depends resolve_uses, main_of
def resolve(tmp, text):
    return resolve_uses(main_of(tmp), text)


class TestSplice(unittest.TestCase):
    """Склейка: use заменяет строку, остальной текст не меняется."""

    # @method test_text_without_use_unchanged() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Тексты без use-строк возвращаются неизменными (round-trip
    # @does  точен), с пустым текстом включительно.
    # @depends resolve
    def test_text_without_use_unchanged(self):
        with source_tree({}) as tmp:
            for text in ("", ": main ;\n", ": main\n  DUP ;\nvar x\ntext s \"a\"\n"):
                self.assertEqual(resolve(tmp, text), (text, None))

    # @method test_crlf_normalized() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Концевые CR строк снимаются (как split_lines разбора):
    # @does  строки те же, переводы — только LF.
    # @depends resolve
    def test_crlf_normalized(self):
        with source_tree({}) as tmp:
            spliced, error = resolve(tmp, ": main ;\r\nDUP\r\n")
            self.assertEqual((spliced, error), (": main ;\nDUP\n", None))

    # @method test_use_splices_lines() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Строки включённого файла встают на место строки use;
    # @does  строки до и после остаются на своих местах; концевой
    # @does  перевод файла — конец последней строки, не пустая строка.
    # @depends source_tree, resolve
    def test_use_splices_lines(self):
        files = {"part.ubrk": ": hi\n  72 EMIT ;\n", "main.ubrk": HELLO_MAIN}
        with source_tree(files) as tmp:
            text = "; до\nuse part.ubrk\n; после\n"
            expect = "; до\n: hi\n  72 EMIT ;\n; после\n"
            self.assertEqual(resolve(tmp, text), (expect, None))

    # @method test_file_edge_lines() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Краевые файлы: пустой файл — ноль строк (строки use
    # @does  схлопываются), файл без концевого перевода — свои строки
    # @does  без добавления пустой.
    # @depends source_tree, resolve
    def test_file_edge_lines(self):
        files = {"empty.ubrk": "", "one.ubrk": ": hi ;",
                 "main.ubrk": HELLO_MAIN}
        with source_tree(files) as tmp:
            self.assertEqual(resolve(tmp, "; a\nuse empty.ubrk\n; b\n"),
                             ("; a\n; b\n", None))
            self.assertEqual(resolve(tmp, "use one.ubrk\n: main hi ;\n"),
                             (": hi ;\n: main hi ;\n", None))

    # @method test_use_trailing_comment_dropped() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Хвост-комментарий строки use отбрасывается вместе
    # @does  со строкой: два слова — use и имя файла.
    # @depends source_tree, resolve
    def test_use_trailing_comment_dropped(self):
        files = {"part.ubrk": ": hi ;\n", "main.ubrk": HELLO_MAIN}
        with source_tree(files) as tmp:
            text = "use part.ubrk ; хвост\n"
            self.assertEqual(resolve(tmp, text), (": hi ;\n", None))

    # @method test_comment_use_ignored() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Строка-комментарий «; use ...» — не директива: файл
    # @does  не читается, строка остаётся в тексте.
    # @depends resolve
    def test_comment_use_ignored(self):
        with source_tree({}) as tmp:
            text = "; use nope.ubrk\n: main ;\n"
            self.assertEqual(resolve(tmp, text), (text, None))

    # @method test_nested_directories() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Включённый файл ищется в подкаталоге; его собственный
    # @does  use-путь — относительно его каталога, не главного.
    # @depends source_tree, resolve
    def test_nested_directories(self):
        files = {
            "main.ubrk": "use sub/part.ubrk\n: main go ;\n",
            "sub/part.ubrk": "use deep.ubrk\n: go 65 EMIT ;\n",
            "sub/deep.ubrk": ": extra NOP ;\n",
        }
        with source_tree(files) as tmp:
            text = files["main.ubrk"]
            expect = ": extra NOP ;\n: go 65 EMIT ;\n: main go ;\n"
            self.assertEqual(resolve(tmp, text), (expect, None))

    # @method test_double_include_splices_twice() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Повторное включение вставляет определения повторно —
    # @does  повторные определения слов становятся ошибкой разбора
    # @does  на строке второго включения (v0.3, раздел 3 SPEC).
    # @depends source_tree, resolve, parse_ubrk
    def test_double_include_splices_twice(self):
        part = ": hi 65 EMIT ;\n"
        files = {"part.ubrk": part, "main.ubrk": HELLO_MAIN}
        with source_tree(files) as tmp:
            spliced, error = resolve(tmp, "use part.ubrk\nuse part.ubrk\n"
                                          ": main hi ;\n")
            self.assertEqual((spliced, error), (part + part + ": main hi ;\n",
                                                None))
            records, parse_error = parse_ubrk(spliced)
            self.assertIsNone(records)
            self.assertEqual(parse_error,
                             "uBrick: строка 2: повторное определение слова hi")


class TestNumbers(unittest.TestCase):
    """Сквозная нумерация: ошибки загрузчика и разбора — одни номера."""

    # @method test_loader_error_line_number() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Ошибка загрузчика получает сквозной номер строки use:
    # @does  строка 2 после комментария.
    # @depends resolve
    def test_loader_error_line_number(self):
        with source_tree({}) as tmp:
            _, error = resolve(tmp, "; комментарий\nuse nope.ubrk\n")
            self.assertEqual(error,
                             "uBrick: строка 2: не читается use-файл nope.ubrk")

    # @method test_parse_error_line_number() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Ошибка разбора внутри включённого файла — номер строки
    # @does  объединённого текста: часть встаёт на место use.
    # @depends source_tree, resolve, parse_ubrk
    def test_parse_error_line_number(self):
        files = {"part.ubrk": ": helper\n  nosuch ;\n",
                 "main.ubrk": HELLO_MAIN}
        with source_tree(files) as tmp:
            spliced, error = resolve(tmp, "; c\nuse part.ubrk\n"
                                          ": main helper ;\n")
            self.assertEqual((spliced is not None, error), (True, None))
            records, parse_error = parse_ubrk(spliced)
            self.assertIsNone(records)
            self.assertEqual(parse_error,
                             "uBrick: строка 3: неизвестное слово nosuch")


class TestState(unittest.TestCase):
    """Состояние определения: где use допустен, где нет."""

    # @method test_use_inside_definition() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Строка use внутри тела «:» — ошибка загрузчика
    # @does  «use внутри определения».
    # @depends resolve
    def test_use_inside_definition(self):
        files = {"part.ubrk": ": hi ;\n", "main.ubrk": HELLO_MAIN}
        with source_tree(files) as tmp:
            _, error = resolve(tmp, ": foo\nuse part.ubrk\n;\n: main ;\n")
            self.assertEqual(error,
                             "uBrick: строка 2: use внутри определения")

    # @method test_comment_line_keeps_definition_open() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Строка-комментарий внутри тела определение не закрывает
    # @does  (правило «;» v0.2): use за ней — всё ещё внутри.
    # @depends resolve
    def test_comment_line_keeps_definition_open(self):
        files = {"part.ubrk": ": hi ;\n", "main.ubrk": HELLO_MAIN}
        with source_tree(files) as tmp:
            text = ": foo\n; комментарий\nuse part.ubrk\nDUP ;\n: main ;\n"
            _, error = resolve(tmp, text)
            self.assertEqual(error,
                             "uBrick: строка 3: use внутри определения")

    # @method test_one_line_definition_closed() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Однострочное определение «: ... ;» закрывается той же
    # @does  строкой: use после него — верхний уровень, включение
    # @does  проходит, разбор объединённого текста успешен.
    # @depends source_tree, resolve, parse_ubrk
    def test_one_line_definition_closed(self):
        files = {"part.ubrk": ": hi ;\n", "main.ubrk": HELLO_MAIN}
        with source_tree(files) as tmp:
            text = ": foo DUP ;\nuse part.ubrk\n: main hi ;\n"
            spliced, error = resolve(tmp, text)
            self.assertEqual(error, None)
            records, parse_error = parse_ubrk(spliced)
            self.assertIsNone(parse_error)
            self.assertEqual(records[0], ("word", "foo", (("word", "DUP"),)))

    # @method test_text_literal_does_not_break_state() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  «;» и «:» внутри литерала в кавычках не считаются: text
    # @does  со строкой-ловушкой не открывает определение и не режет
    # @does  строку, use за ним — верхний уровень.
    # @depends source_tree, resolve, parse_ubrk
    def test_text_literal_does_not_break_state(self):
        files = {"part.ubrk": ": hi ;\n", "main.ubrk": HELLO_MAIN}
        with source_tree(files) as tmp:
            text = 'text s "a ; b : c"\nuse part.ubrk\n: main hi ;\n'
            spliced, error = resolve(tmp, text)
            self.assertEqual(error, None)
            records, parse_error = parse_ubrk(spliced)
            self.assertIsNone(parse_error)
            self.assertIn(("text", "s", b"a ; b : c"), records)


class TestErrors(unittest.TestCase):
    """Ошибки загрузчика: тексты и номера строк (SPEC, раздел 8)."""

    # @method test_use_without_name() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Строка «use» без имени файла — «use без имени файла».
    # @depends resolve
    def test_use_without_name(self):
        with source_tree({}) as tmp:
            _, error = resolve(tmp, "use\n")
            self.assertEqual(error, "uBrick: строка 1: use без имени файла")

    # @method test_use_extra_words() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Три слова в строке use — «лишние слова после use».
    # @depends resolve
    def test_use_extra_words(self):
        with source_tree({}) as tmp:
            _, error = resolve(tmp, "use a.ubrk b\n")
            self.assertEqual(error, "uBrick: строка 1: лишние слова после use")

    # @method test_missing_file() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Нечитаемый включаемый файл — «не читается use-файл X».
    # @depends resolve
    def test_missing_file(self):
        with source_tree({}) as tmp:
            _, error = resolve(tmp, "use nope.ubrk\n")
            self.assertEqual(error,
                             "uBrick: строка 1: не читается use-файл nope.ubrk")

    # @method test_self_cycle() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Файл, включающий себя, — «циклический use X».
    # @depends source_tree, resolve
    def test_self_cycle(self):
        files = {"loop.ubrk": "use loop.ubrk\n", "main.ubrk": HELLO_MAIN}
        with source_tree(files) as tmp:
            _, error = resolve_uses(os.path.join(tmp, "loop.ubrk"),
                                    files["loop.ubrk"])
            self.assertEqual(error, "uBrick: строка 1: циклический use loop.ubrk")

    # @method test_pair_cycle() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Пара файлов, включающих друг друга, — цикл на обратном
    # @does  включении, номер строки — сквозной.
    # @depends source_tree, resolve
    def test_pair_cycle(self):
        files = {"a.ubrk": ": main ;\nuse b.ubrk\n",
                 "b.ubrk": "use a.ubrk\n", "main.ubrk": HELLO_MAIN}
        with source_tree(files) as tmp:
            _, error = resolve_uses(os.path.join(tmp, "a.ubrk"),
                                    files["a.ubrk"])
            self.assertEqual(error, "uBrick: строка 2: циклический use a.ubrk")


class TestCompile(unittest.TestCase):
    """Многофайловая программа собирается командой compile."""

    # @method test_multifile_image_and_run() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  compile собирает main.ubrk с use-включением: образ равен
    # @does  однофайлочному эквиваленту байт в байт, исполнение на UVM
    # @does  печатает «Hi», код 0.
    # @depends source_tree, ubrick_cli.main, build_ubrk, parse_ubrk, tk.run_with_io
    # @uses   sys.stderr — перехват сообщений cli
    def test_multifile_image_and_run(self):
        files = {"part.ubrk": HELLO_WORD, "main.ubrk": HELLO_MAIN}
        single = HELLO_WORD + ": main hi ;\n"
        expect_image, _ = build_ubrk(parse_ubrk(single)[0])
        with source_tree(files) as tmp, \
                tempfile.TemporaryDirectory() as out:
            image = os.path.join(out, "hello.uvm")
            with contextlib.redirect_stderr(io.StringIO()):
                code = ubrick_cli.main(["compile", main_of(tmp), image])
            self.assertEqual(code, 0)
            with open(image, "rb") as handle:
                built = handle.read()
            self.assertEqual(built, expect_image)
            self.assertEqual(tk.run_with_io(built, b""), (0, b"Hi"))

    # @method test_cli_use_error() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Ошибка загрузчика в режиме compile: код 2 и строка
    # @does  «uBrick: строка N: ...» в stderr.
    # @depends source_tree, ubrick_cli.main
    # @uses   sys.stderr — перехват сообщений cli
    def test_cli_use_error(self):
        files = {"main.ubrk": "use nope.ubrk\n: main ;\n"}
        with source_tree(files) as tmp, \
                tempfile.TemporaryDirectory() as out:
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                code = ubrick_cli.main(["compile", main_of(tmp),
                                        os.path.join(out, "x.uvm")])
            self.assertEqual(code, 2)
            self.assertEqual(stderr.getvalue().strip(),
                             "uBrick: строка 1: не читается use-файл nope.ubrk")


class TestProcess(unittest.TestCase):
    """Сквозной прогон настоящим процессом: compile, затем uvm_cli."""

    # @method test_process_multifile() -> None
    # @in    нет
    # @out   нет (утверждение теста)
    # @does  Настоящие процессы: ubrick_cli compile многофайловой
    # @does  программы, затем uvm_cli — вывод «Hi», коды процессов 0.
    # @depends source_tree, repo_root
    # @uses   subprocess — запуск инструментов настоящими процессами
    def test_process_multifile(self):
        files = {"part.ubrk": HELLO_WORD, "main.ubrk": HELLO_MAIN}
        with source_tree(files) as tmp, \
                tempfile.TemporaryDirectory() as out:
            image = os.path.join(out, "hello.uvm")
            compile_code = subprocess.call(
                [sys.executable, os.path.join(repo_root(), "tools",
                                              "ubrick_cli.py"),
                 "compile", main_of(tmp), image],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.assertEqual(compile_code, 0)
            run = subprocess.run(
                [sys.executable, os.path.join(repo_root(), "tools",
                                              "uvm_cli.py"), image],
                stdin=subprocess.DEVNULL, capture_output=True)
            self.assertEqual(run.returncode, 0)
            self.assertEqual(run.stdout, b"Hi")


if __name__ == "__main__":
    unittest.main()
