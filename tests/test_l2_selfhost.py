# @uadro
# @file    tests/test_l2_selfhost.py
# @layer   T0
# @branch  l2.selfhost
# @desc    Связка l2.selfhost — закрытие Этапа 4 (SPEC/L4-SELFHOST.txt,
# @desc    разделы 7-8): раунд-трип «текст -> образ (собственный
# @desc    ассемблер) -> исполнение (собственный эмулятор) -> текст
# @desc    (собственный дизассемблер) -> образ» сходится без
# @desc    Python-инструментов — программы этапов 1-2 и образ с хвостом
# @desc    данных; паритет с эталоном на каждом шаге; TestProcess —
# @desc    сквозная цепь настоящими процессами печатает «Hi».

"""Связка собственных инструментов — ветвь l2.selfhost (SPEC/
L4-SELFHOST.txt, разделы 7 и 8; закрытие Этапа 4).

Три собственных инструмента Этапа 4 — ассемблер (src/l2/assemble.ubrk),
эмулятор (src/l1/emu.ubrk) и дизассемблер (src/l2/disasm.ubrk) —
собираются командой compile (ubrick_cli, бустрап-компилятор uBrick)
и прогоняются кирпичом run_with_io на UVM (Python-эталон UVM —
тест-харнесс, SPEC, раздел 8). Раунд-трип: текст -> образ (собственный
ассемблер) -> исполнение (собственный эмулятор) -> текст (собственный
дизассемблер) -> образ — сходится: второй образ равен первому байт
в байт. На каждом шаге — паритет с эталоном (сборка и печать —
t0.uasm.*, исполнение — ref_state из tests/test_l1_emu_jump.py).

Набор: программы этапов 1-2 (hello — «Hi», arith — [20] на DS,
nested_calls — «!» и [111, 222]) и образ с хвостом данных (неизвестный
опкод 0x51 и 16 байтов данных: печать DB-директивами собирается
обратно, исполнение — ловушка 6, данные, а не баг).

TestProcess — сквозная цепь настоящими процессами: ubrick_cli
собирает три инструмента, uvm_cli гонит их по цепи с входными
файлами — stdout «Hi», образы сходятся, коды процессов 0.
"""

import os
import subprocess
import sys
import tempfile
import unittest

from tests import test_l1_emu_jump as ej
from tests import uvm_testkit as tk
from tools import ubrick_cli
from tools.uasm_assemble import assemble
from tools.uasm_disasm import disasm as ref_disasm

ASM = "asm"   # собственный ассемблер — src/l2/assemble.ubrk
EMU = "emu"   # собственный эмулятор — src/l1/emu.ubrk
DIS = "dis"   # собственный дизассемблер — src/l2/disasm.ubrk
TOOL_SOURCES = {
    ASM: os.path.join("src", "l2", "assemble.ubrk"),
    EMU: os.path.join("src", "l1", "emu.ubrk"),
    DIS: os.path.join("src", "l2", "disasm.ubrk"),
}

# Известный эффект программ этапов 1-2 на машине гостя (SPEC,
# L4-SELFHOST.txt, раздел 6): имя, байты вывода, снимок DS.
EFFECTS = [
    ("hello.uasm", b"Hi", []),
    ("arith.uasm", b"", [20]),
    ("nested_calls.uasm", b"!", [111, 222]),
]

# Образ с хвостом данных: неизвестный опкод 0x51 и 16 байтов —
# дизассемблер печатает DB-директивами (2 строки по 8 и неполная),
# ассемблер собирает их обратно; исполнение — ловушка 6.
DATA_TAIL = b"\x51" + bytes(range(0x11, 0x21))

_IMAGE_CACHE = {}   # kind -> образ инструмента (сборка один раз)


# @method repo_root() -> str
# @in    нет
# @out   root: str — корень репозитория (каталог над tests)
# @does  Даёт корень репозитория для путей src/ и tools/ — кирпич
# @does  tool_source, src_text и TestProcess.
def repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# @method tool_source(kind) -> str
# @in    kind: str — имя инструмента: ASM, EMU либо DIS
# @out   path: str — путь к исходнику .ubrk инструмента
# @does  Даёт путь исходника собственного инструмента от корня
# @does  репозитория (TOOL_SOURCES); кирпич tool_image и TestProcess.
def tool_source(kind):
    return os.path.join(repo_root(), TOOL_SOURCES[kind])


# @method tool_image(kind) -> bytes
# @in    kind: str — имя инструмента: ASM, EMU либо DIS
# @out   image: bytes — образ инструмента, собранный командой compile
# @does  Собирает исходник инструмента настоящей командой ubrick_cli
# @does  (режим compile) один раз за прогон файла и кеширует
# @does  (_IMAGE_CACHE) — кирпич вызывается на каждом шаге цепи;
# @does  ошибка сборки — ошибка теста (образы инструментов уже
# @does  закрыты золотыми наборами своих ветвей).
# @depends ubrick_cli.main
# @uses   _IMAGE_CACHE — кеш образов инструментов
def tool_image(kind):
    if kind not in _IMAGE_CACHE:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, kind + ".uvm")
            code = ubrick_cli.main(["compile", tool_source(kind), path])
            assert code == 0, (kind, "ошибка сборки инструмента")
            with open(path, "rb") as handle:
                _IMAGE_CACHE[kind] = handle.read()
    return _IMAGE_CACHE[kind]


# @method run_tool(kind, feed) -> tuple
# @in    kind: str — имя инструмента: ASM, EMU либо DIS
# @in    feed: bytes — байты stdin инструмента (текст uAsm, образ)
# @out   pair: tuple — (код завершения, байты stdout) инструмента
# @does  Прогон собственного инструмента на UVM без процесса
# @does  (run_with_io — подменённые stdin/stdout); кирпич всех шагов
# @does  цепи без процесса.
# @depends tool_image, tk.run_with_io
def run_tool(kind, feed):
    return tk.run_with_io(tool_image(kind), feed)


# @method run_guest(image) -> tuple
# @in    image: bytes — образ гостя (stdin собственного эмулятора)
# @out   triple: tuple — (код гостя, байты вывода, машина узла)
# @does  Исполнение образа собственным эмулятором с сохранением
# @does  машины узла (run_saved): снимки DS/RS гостя читаются
# @does  по раскладке раздела 5Б (ej.ds_of, ej.rs_of); кирпич шага
# @does  «исполнение» цепи.
# @depends tool_image, tk.run_saved
def run_guest(image):
    return tk.run_saved(tool_image(EMU), image)


# @method src_text(name) -> str
# @in    name: str — имя исходника в src/, например "hello.uasm"
# @out   text: str — текст исходника в кодировке UTF-8
# @does  Читает исходник программы этапа 1-2 целиком; кирпич
# @does  TestRoundTrip.
def src_text(name):
    path = os.path.join(repo_root(), "src", name)
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


# @method want_image(text) -> bytes
# @in    text: str — текст uAsm
# @out   image: bytes — образ эталонной сборки
# @does  Паритет шага «сборка» (SPEC, раздел 2): эталон assemble —
# @does  источник истины поведения; ошибка сборки — ошибка теста.
# @depends assemble
def want_image(text):
    image, error = assemble(text)
    assert error is None, error
    return image


# @method want_text(image) -> bytes
# @in    image: bytes — образ UVM
# @out   text: bytes — текст эталонного дизассемблера в UTF-8
# @does  Паритет шага «печать» (SPEC, раздел 2): эталон disasm —
# @does  источник истины поведения.
# @depends ref_disasm
def want_text(image):
    return ref_disasm(image).encode("utf-8")


# @method sys_python() -> str
# @in    нет
# @out   python: str — интерпретатор для запуска инструментов процессом
# @does  Даёт исполняемый файл Python, запустивший тесты.
# @uses   sys.executable — интерпретатор текущего процесса
def sys_python():
    return sys.executable


# @method tools_path(name) -> str
# @in    name: str — имя сценария в каталоге tools
# @out   path: str — путь к инструменту репозитория
# @does  Строит путь к сценарию инструментов для запуска процессом.
# @depends repo_root
def tools_path(name):
    return os.path.join(repo_root(), "tools", name)


class TestRoundTrip(unittest.TestCase):
    """Раунд-трип цепи без процесса (SPEC, разделы 7-8)."""

    # @method test_stage12_chain() -> None
    # @in    нет
    # @out   нет
    # @does  Раунд-трип на программах этапов 1-2 (SPEC, раздел 8):
    # @does  собственный ассемблер собирает текст (образ равен
    # @does  эталону), собственный эмулятор исполняет образ (код 0,
    # @does  известные байты вывода и снимки DS/RS — паритет
    # @does  с эталоном ref_state), собственный дизассемблер печатает
    # @does  образ (текст равен эталону), собственный ассемблер
    # @does  собирает текст обратно — второй образ равен первому
    # @does  байт в байт: раунд-трип сходится без Python-инструментов.
    # @depends run_tool, run_guest, src_text, want_image, want_text,
    # @depends ej.ds_of, ej.rs_of, ej.ref_state, EFFECTS
    def test_stage12_chain(self):
        for name, want_out, want_ds in EFFECTS:
            with self.subTest(program=name):
                text = src_text(name).encode("utf-8")
                code, img1 = run_tool(ASM, text)
                self.assertEqual(code, 0)
                self.assertEqual(img1, want_image(src_text(name)))
                code, out, machine = run_guest(img1)
                self.assertEqual((code, out), (0, want_out))
                self.assertEqual(ej.ds_of(machine), want_ds)
                self.assertEqual(ej.rs_of(machine), [])
                self.assertEqual(ej.ref_state(img1), (0, want_ds, []))
                code, text2 = run_tool(DIS, img1)
                self.assertEqual(code, 0)
                self.assertEqual(text2, want_text(img1))
                code, img2 = run_tool(ASM, text2)
                self.assertEqual(code, 0)
                self.assertEqual(img2, img1)

    # @method test_data_tail_chain() -> None
    # @in    нет
    # @out   нет
    # @does  Раунд-трип с хвостом данных (SPEC, раздел 8): образ
    # @does  из неизвестного опкода и 16 байтов данных — собственный
    # @does  дизассемблер печатает его DB-директивами (текст равен
    # @does  эталону), собственный
    # @does  ассемблер собирает директивы обратно в исходный образ,
    # @does  собственный эмулятор исполняет образ — ловушка 6
    # @does  (данные, а не баг), паритет кода с эталоном ref_state.
    # @depends run_tool, run_guest, want_text, ej.ref_state, DATA_TAIL
    def test_data_tail_chain(self):
        code, text = run_tool(DIS, DATA_TAIL)
        self.assertEqual(code, 0)
        self.assertEqual(text, want_text(DATA_TAIL))
        code, img2 = run_tool(ASM, text)
        self.assertEqual(code, 0)
        self.assertEqual(img2, DATA_TAIL)
        code, out = run_tool(EMU, DATA_TAIL)
        self.assertEqual((code, out), (6, b""))
        self.assertEqual(ej.ref_state(DATA_TAIL), (6, [], []))


class TestProcess(unittest.TestCase):
    """Сквозная цепь настоящими процессами (SPEC, разделы 7-8)."""

    # @method test_process_chain() -> None
    # @in    нет
    # @out   нет
    # @does  Полная цепь контракта настоящими процессами: ubrick_cli
    # @does  compile собирает три собственных инструмента, uvm_cli
    # @does  исполняет их с входными файлами — собственный ассемблер
    # @does  собирает src/hello.uasm (stdout равен эталонному образу),
    # @does  собственный эмулятор исполняет собранный образ и печатает
    # @does  «Hi», собственный дизассемблер печатает образ (stdout
    # @does  равен эталонному тексту), собственный ассемблер собирает
    # @does  текст обратно — образ сходится байт в байт; коды всех
    # @does  процессов 0.
    # @depends tool_source, src_text, want_image, want_text, sys_python,
    # @depends tools_path, run_step, ASM, EMU, DIS
    # @uses   subprocess — запуск инструментов настоящими процессами
    def test_process_chain(self):
        hello = src_text("hello.uasm")
        with tempfile.TemporaryDirectory() as tmp:
            paths = {kind: os.path.join(tmp, kind + ".uvm")
                     for kind in (ASM, EMU, DIS)}
            for kind, path in paths.items():
                compile_code = subprocess.call(
                    [sys_python(), tools_path("ubrick_cli.py"), "compile",
                     tool_source(kind), path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.assertEqual(compile_code, 0)
            img1 = self.run_step(paths[ASM], hello.encode("utf-8"), tmp,
                                 "hello.uasm")
            self.assertEqual(img1, want_image(hello))
            out = self.run_step(paths[EMU], img1, tmp, "text1.uvm")
            self.assertEqual(out, b"Hi")
            text2 = self.run_step(paths[DIS], img1, tmp, "text1.uvm")
            self.assertEqual(text2, want_text(img1))
            img2 = self.run_step(paths[ASM], text2, tmp, "text2.uasm")
            self.assertEqual(img2, img1)

    # @method run_step(tool, feed, tmp, src_name) -> bytes
    # @in    tool: str — путь к образу инструмента (uvm_cli)
    # @in    feed: bytes — байты входного файла инструмента
    # @in    tmp: str — каталог входного файла
    # @in    src_name: str — имя входного файла в tmp
    # @out   out: bytes — байты stdout процесса
    # @does  Один шаг цепи настоящим процессом: пишет feed во входной
    # @does  файл tmp/src_name, запускает uvm_cli с образом инструмента
    # @does  и входным файлом, проверяет код процесса 0 и возвращает
    # @does  stdout — результат шага цепи (test_process_chain).
    # @depends sys_python, tools_path
    # @uses   subprocess — запуск uvm_cli настоящим процессом
    def run_step(self, tool, feed, tmp, src_name):
        src = os.path.join(tmp, src_name)
        with open(src, "wb") as handle:
            handle.write(feed)
        with open(src, "rb") as source:
            step = subprocess.run(
                [sys_python(), tools_path("uvm_cli.py"), tool],
                stdin=source, capture_output=True, timeout=60)
        self.assertEqual(step.returncode, 0, step.stderr)
        return step.stdout


if __name__ == "__main__":
    unittest.main()
