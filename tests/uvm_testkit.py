# @uadro
# @file    tests/uvm_testkit.py
# @layer   T0
# @branch  t0.infra.tests
# @desc    Общий тест-набор UVM: компактные машины, снимки стека, сборка
# @desc    образов программ (в машину и байтами в файл), чтение кодов
# @desc    ловушек и остановки, заглушки потоков хоста, прогон образов
# @desc    через cli, прогон без процесса с подменёнными stdin/stdout
# @desc    (run_with_io) и прогон с сохранением машины (run_saved) — для
# @desc    тестов ветвей t0.uvm.* и собственных инструментов Этапа 4
# @desc    (SPEC/L4-SELFHOST.txt).

"""Тест-набор UVM (ветвь t0.infra.tests).

Переиспользуется всеми тестами ветвей t0.uvm.*: компактные машины
для проверок границ, чтение кодов ловушек и остановки HALT, сборка
образов (load_prog — сразу в машину, image_of/image_file — байтами,
в том числе в файл для ветви t0.uvm.cli), заглушки stdin/stdout
с полем buffer — как у реальных потоков Python, run_via_cli —
полный прогон образа через командный запуск, run_with_io — прогон
без процесса с подменёнными stdin/stdout для собственных инструментов
Этапа 4 (SPEC/L4-SELFHOST.txt, раздел 6) и run_saved — тот же прогон
с сохранением машины узла для чтения снимков по раскладке инструмента
(SPEC/L4-SELFHOST.txt, раздел 5Б — эмулятор l1.uvm.*).
"""

import contextlib
import io
import os
import sys
import tempfile

from tools import uvm_cli
from tools import uvm_core as uc
from tools import uvm_run


# @method small(ram_size, ds_size, rs_size) -> Machine
# @in    ram_size: int — размер ОЗУ в байтах (по умолчанию 64)
# @in    ds_size: int — ёмкость стека данных в словах (по умолчанию 8)
# @in    rs_size: int — ёмкость стека возвратов в словах (по умолчанию 4)
# @out   m: Machine — машина с малым ОЗУ и малыми стеками
# @does  Компактная машина для быстрых тестов границ и переполнений;
# @does  размеры переопределяются точечно.
# @depends uc.Machine
def small(ram_size=64, ds_size=8, rs_size=4):
    return uc.Machine(ram_size=ram_size, ds_size=ds_size, rs_size=rs_size)


# @method stack_of(m) -> list
# @in    m: Machine — состояние машины
# @out   items: list — снимок стека данных (нижний элемент первым)
# @does  Копия содержимого DS для сравнения в тестах.
def stack_of(m):
    return list(m.ds)


# @method trap_code(action) -> int
# @in    action: callable — действие, обязанное поднять ловушку
# @out   code: int — код поднятой ловушки
# @does  Исполняет действие и возвращает код ловушки; без ловушки —
# @does  ошибка теста.
# @depends uc.UvmTrap
def trap_code(action):
    try:
        action()
    except uc.UvmTrap as exc:
        return exc.code
    raise AssertionError("ловушка не поднята")


# @method halt_code(action) -> int
# @in    action: callable — действие, обязанное поднять UvmHalt
# @out   code: int — код нормальной остановки
# @does  Исполняет действие и возвращает код остановки HALT; без
# @does  остановки — ошибка теста.
# @depends uc.UvmHalt
def halt_code(action):
    try:
        action()
    except uc.UvmHalt as exc:
        return exc.code
    raise AssertionError("остановка не поднята")


# @method imm64(v) -> bytes
# @in    v: int — слово (оборачивается по модулю 2^64)
# @out   raw: bytes — 8 байтов little-endian
# @does  Кодирует поле imm64 инструкции (SPEC, раздел 4); кирпич сборки
# @does  тестовых образов для ветвей t0.uvm.*.
# @depends uc.to_word
def imm64(v):
    return uc.to_word(v).to_bytes(8, "little")


# @method image_of(parts) -> bytes
# @in    parts: list — элементы образа: int 0..255 (байт) или bytes
# @out   image: bytes — образ программы
# @does  Собирает элементы в один образ байтов; кирпич тестов ветвей
# @does  t0.uvm.cli и t0.uvm.integration (запись образа в файл).
def image_of(parts):
    image = bytearray()
    for part in parts:
        if isinstance(part, int):
            image.append(part & 0xFF)
        else:
            image.extend(part)
    return bytes(image)


# @method image_file(image) -> contextmanager
# @in    image: bytes — образ программы
# @out   cm: contextmanager — выдаёт путь к временному файлу с образом
# @does  Записывает образ во временный файл; путь действует внутри
# @does  with, файл и каталог удаляются на выходе; кирпич тестов
# @does  ветвей t0.uvm.cli и t0.uvm.integration.
# @uses  tempfile — временный каталог теста
@contextlib.contextmanager
def image_file(image):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "prog.uvm")
        with open(path, "wb") as handle:
            handle.write(image)
        yield path


# @method load_prog(m, parts) -> None
# @in    m: Machine — состояние машины
# @in    parts: list — элементы образа: int 0..255 (байт) или bytes
# @out   нет
# @does  Собирает элементы в образ (image_of), загружает его с адреса 0
# @does  и сбрасывает состояние запуска: PC = 0, стеки пусты; кирпич
# @does  тестов ветвей t0.uvm.decode/exec/run.
# @depends uc.load_image, image_of
def load_prog(m, parts):
    uc.load_image(m, image_of(parts))


# @method FakeStream(data)
# @in    data: bytes — начальные байты (для заглушки ввода)
# @out   fake: FakeStream — поток с полем buffer
# @does  Заглушка stdin/stdout: обработчики SYS читают и пишут через
# @does  поле buffer, как у реальных потоков Python; для stdout —
# @does  с contextlib.redirect_stdout, для stdin — с patched_stdin.
class FakeStream:
    """Заглушка стандартного потока: buffer — BytesIO."""

    def __init__(self, data=b""):
        self.buffer = io.BytesIO(data)


# @method patched_stdin(stream, action) -> result
# @in    stream: FakeStream — заглушка стандартного ввода
# @in    action: callable — проверяемое действие
# @out   result — значение, возвращённое action (проброс наружу)
# @does  Подменяет sys.stdin на время действия, гарантированно
# @does  восстанавливает после (в contextlib нет redirect_stdin)
# @does  и возвращает результат действия; кирпич run_with_io.
# @uses  sys.stdin — стандартный ввод хоста (подмена на время действия)
def patched_stdin(stream, action):
    saved = sys.stdin
    sys.stdin = stream
    try:
        return action()
    finally:
        sys.stdin = saved


# @method run_via_cli(image, args) -> tuple
# @in    image: bytes — образ программы
# @in    args: list — дополнительные аргументы после пути (по умолчанию
# @in    пусто)
# @out   code: int — код завершения cli.main
# @out   out: bytes — байты, выведенные программой в stdout
# @does  Полный прогон образа через командный запуск: временный файл
# @does  (image_file), cli.main с подменённым stdout (FakeStream);
# @does  кирпич тестов ветвей t0.uvm.cli и t0.uvm.integration.
# @depends image_file, FakeStream, uvm_cli.main
# @uses  sys.stdout — стандартный вывод хоста (подмена на время прогона)
def run_via_cli(image, args=()):
    out = FakeStream()
    with image_file(image) as path:
        with contextlib.redirect_stdout(out):
            code = uvm_cli.main([path] + list(args))
    return code, out.buffer.getvalue()


# @method run_with_io(image, feed) -> tuple
# @in    image: bytes — образ программы
# @in    feed: bytes — байты стандартного ввода (по умолчанию пусто)
# @out   code: int — код завершения: imm HALT или код ловушки
# @out   out: bytes — байты, выведенные программой в stdout
# @does  Прогон образа без процесса: SYS 0 читает feed, SYS 1 пишет
# @does  в выходной буфер (run_image под подменёнными stdin/stdout);
# @does  кирпич золотых тестов собственных инструментов Этапа 4
# @does  (SPEC/L4-SELFHOST.txt, раздел 6).
# @depends FakeStream, patched_stdin, uvm_run.run_image
# @uses   sys.stdin, sys.stdout — потоки хоста (подмена на время прогона)
def run_with_io(image, feed=b""):
    src = FakeStream(feed)
    out = FakeStream()
    with contextlib.redirect_stdout(out):
        _, code = patched_stdin(src,
                                lambda: uvm_run.run_image(image))
    return code, out.buffer.getvalue()


# @method run_saved(image, feed) -> tuple
# @in    image: bytes — образ программы (инструмента)
# @in    feed: bytes — байты стандартного ввода (по умолчанию пусто)
# @out   code: int — код завершения: imm HALT или код ловушки
# @out   out: bytes — байты, выведенные программой в stdout
# @out   m: Machine — остановленная машина узла (ОЗУ, PC, стеки):
# @out   снимки читаются после прогона по раскладке инструмента
# @does  Прогон образа без процесса с сохранением машины (SPEC/
# @does  L4-SELFHOST.txt, раздел 5Б, подшаг 1): как run_with_io, но
# @does  машина не отбрасывается — эмулятор l1.uvm.* хранит состояние
# @does  гостя в фиксированных адресах своей ОЗУ, тесты читают их из
# @does  снимка; машина узла — по умолчанию 1 МиБ (инструменту нужно
# @does  не менее 0x90A80).
# @depends FakeStream, patched_stdin, uvm_run.run_image
# @uses   sys.stdin, sys.stdout — потоки хоста (подмена на время прогона)
def run_saved(image, feed=b""):
    src = FakeStream(feed)
    out = FakeStream()
    with contextlib.redirect_stdout(out):
        m, code = patched_stdin(src,
                                lambda: uvm_run.run_image(image))
    return code, out.buffer.getvalue(), m
