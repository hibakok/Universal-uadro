# @uadro
# @file    tools/uvm_core.py
# @layer   T0
# @branch  t0.uvm.core
# @desc    Ядро UVM: состояние машины, ловушки, ОЗУ и стеки DS/RS (SPEC/L0-UVM.md, Этап 1).

"""Ядро виртуальной машины UVM v0.1 (ветвь t0.uvm.core).

Здесь живут только кирпичи состояния по SPEC/L0-UVM.md: слова, ловушки,
ОЗУ, стеки DS/RS и загрузка образа. Исполнение инструкций — следующие
ветви Этапа 1: t0.uvm.ops, t0.uvm.table, t0.uvm.decode, t0.uvm.exec,
t0.uvm.run, t0.uvm.cli.
"""

RAM_SIZE_DEFAULT = 1048576  # 1 МиБ ОЗУ (SPEC, раздел 1)
DS_SIZE_DEFAULT = 1024      # слов в стеке данных
RS_SIZE_DEFAULT = 256       # слов в стеке возвратов
WORD_BITS = 64
WORD_MASK = (1 << WORD_BITS) - 1
BYTE_MASK = 0xFF

TRAP_DIV0 = 1        # деление на ноль
TRAP_DS_EMPTY = 2    # опустошение стека данных
TRAP_DS_FULL = 3     # переполнение стека данных
TRAP_RS_EMPTY = 4    # опустошение стека возвратов
TRAP_RS_FULL = 5     # переполнение стека возвратов
TRAP_BAD_OPCODE = 6  # неизвестный опкод
TRAP_OOB = 7         # обращение вне ОЗУ
TRAP_BAD_SYS = 8     # неизвестный номер SYS


# @method to_word(x) -> int
# @in    x: int — целое, возможно вне диапазона 64-битных слов
# @out   w: int — значение по модулю 2^64
# @does  Оборачивает целое в 64-битное слово: переполнения оборачиваются
# @does  (SPEC, раздел 1).
def to_word(x):
    return x & WORD_MASK


# @method to_byte(x) -> int
# @in    x: int — целое, возможно вне 0..255
# @out   b: int — младший байт 0..255
# @does  Оставляет младшие 8 бит значения.
def to_byte(x):
    return x & BYTE_MASK


# @method UvmTrap(code)
# @in    code: int — код завершения-ловушки 1..8 (SPEC, раздел 3)
# @out   exception — ловушка с полем code
# @does  Ловушка немедленно завершает исполнение с указанным кодом;
# @does  поднимается как исключение, ловит его цикл t0.uvm.run.
class UvmTrap(Exception):
    """Ловушка UVM: поле code — код завершения (SPEC, раздел 3)."""

    def __init__(self, code):
        super().__init__(f"ловушка {code}")
        self.code = code


# @method trap(code) -> None
# @in    code: int — код ловушки
# @out   нет — всегда поднимает UvmTrap
# @does  Поднимает ловушку с кодом; исполнение немедленно завершается.
# @depends UvmTrap
def trap(code):
    raise UvmTrap(code)


# @method Machine(ram_size, ds_size, rs_size)
# @in    ram_size: int — размер ОЗУ в байтах (по умолчанию 1 МиБ)
# @in    ds_size: int — ёмкость стека данных в словах (по умолчанию 1024)
# @in    rs_size: int — ёмкость стека возвратов в словах (по умолчанию 256)
# @out   m: Machine — состояние UVM
# @does  Свежее состояние: ОЗУ из нулей, PC = 0, стеки DS и RS пусты
# @does  (SPEC, разделы 1-2).
class Machine:
    """Состояние UVM: ОЗУ, PC, стеки DS и RS с их ёмкостями.

    ОЗУ — байтовый массив; стеки — отдельные списки слов, не отображённые
    в ОЗУ (SPEC, раздел 1). Ёмкости хранятся в ds_size и rs_size.
    """

    def __init__(self, ram_size=RAM_SIZE_DEFAULT, ds_size=DS_SIZE_DEFAULT,
                 rs_size=RS_SIZE_DEFAULT):
        self.ram = bytearray(ram_size)
        self.pc = 0
        self.ds = []
        self.ds_size = ds_size
        self.rs = []
        self.rs_size = rs_size


# @method in_ram(m, addr) -> bool
# @in    m: Machine — состояние машины
# @in    addr: int — адрес байта
# @out   ok: bool — True, если адрес внутри ОЗУ
# @does  Проверяет принадлежность адреса ОЗУ: 0 <= addr < размер ОЗУ.
def in_ram(m, addr):
    return 0 <= addr < len(m.ram)


# @method load_byte(m, addr) -> int
# @in    m: Machine — состояние машины
# @in    addr: int — адрес байта
# @out   b: int — байт 0..255
# @does  Читает байт ОЗУ; адрес вне ОЗУ — ловушка 7.
# @depends in_ram, trap
def load_byte(m, addr):
    if not in_ram(m, addr):
        trap(TRAP_OOB)
    return m.ram[addr]


# @method store_byte(m, addr, val) -> None
# @in    m: Machine — состояние машины
# @in    addr: int — адрес байта
# @in    val: int — значение; записывается его младший байт
# @out   нет
# @does  Пишет младший байт val в ОЗУ; адрес вне ОЗУ — ловушка 7.
# @depends in_ram, trap, to_byte
def store_byte(m, addr, val):
    if not in_ram(m, addr):
        trap(TRAP_OOB)
    m.ram[addr] = to_byte(val)


# @method load_word(m, addr) -> int
# @in    m: Machine — состояние машины
# @in    addr: int — адрес младшего байта слова
# @out   w: int — 64-битное слово
# @does  Собирает слово из 8 байтов ОЗУ в порядке little-endian, без
# @does  требования выравнивания (SPEC, раздел 1).
# @depends load_byte
def load_word(m, addr):
    w = 0
    for i in range(8):
        w |= load_byte(m, addr + i) << (8 * i)
    return w


# @method store_word(m, addr, val) -> None
# @in    m: Machine — состояние машины
# @in    addr: int — адрес младшего байта слова
# @in    val: int — слово; биты старше 64 игнорируются
# @out   нет
# @does  Раскладывает слово в 8 байтов ОЗУ в порядке little-endian,
# @does  без требования выравнивания.
# @depends store_byte
def store_word(m, addr, val):
    for i in range(8):
        store_byte(m, addr + i, (val >> (8 * i)) & BYTE_MASK)


# @method load_image(m, image) -> None
# @in    m: Machine — состояние машины
# @in    image: bytes — образ программы
# @out   нет
# @does  Копирует образ в ОЗУ с адреса 0 и сбрасывает состояние запуска:
# @does  PC = 0, DS и RS пусты (SPEC, раздел 2); образ больше ОЗУ —
# @does  ловушка 7.
# @depends trap
def load_image(m, image):
    if len(image) > len(m.ram):
        trap(TRAP_OOB)
    m.ram[0:len(image)] = image
    m.pc = 0
    m.ds.clear()
    m.rs.clear()


# @method ds_push(m, w) -> None
# @in    m: Machine — состояние машины
# @in    w: int — слово; оборачивается по модулю 2^64
# @out   нет
# @does  Кладёт слово на стек данных; переполнение ёмкости — ловушка 3.
# @depends to_word, trap
def ds_push(m, w):
    if len(m.ds) >= m.ds_size:
        trap(TRAP_DS_FULL)
    m.ds.append(to_word(w))


# @method ds_pop(m) -> int
# @in    m: Machine — состояние машины
# @out   w: int — снятое слово
# @does  Снимает вершину стека данных; пустой стек — ловушка 2.
# @depends trap
def ds_pop(m):
    if not m.ds:
        trap(TRAP_DS_EMPTY)
    return m.ds.pop()


# @method ds_pick(m, depth) -> int
# @in    m: Machine — состояние машины
# @in    depth: int — глубина элемента (0 — вершина)
# @out   w: int — копия элемента, стек не меняется
# @does  Копия элемента глубины depth; глубина вне стека — ловушка 2.
# @does  Кирпич инструкции PICK: depth 0 = DUP, depth 1 = OVER.
# @depends trap
def ds_pick(m, depth):
    if depth < 0 or depth >= len(m.ds):
        trap(TRAP_DS_EMPTY)
    return m.ds[-1 - depth]


# @method rs_push(m, w) -> None
# @in    m: Machine — состояние машины
# @in    w: int — слово; оборачивается по модулю 2^64
# @out   нет
# @does  Кладёт слово на стек возвратов; переполнение ёмкости — ловушка 5.
# @depends to_word, trap
def rs_push(m, w):
    if len(m.rs) >= m.rs_size:
        trap(TRAP_RS_FULL)
    m.rs.append(to_word(w))


# @method rs_pop(m) -> int
# @in    m: Machine — состояние машины
# @out   w: int — снятое слово
# @does  Снимает вершину стека возвратов; пустой стек — ловушка 4.
# @depends trap
def rs_pop(m):
    if not m.rs:
        trap(TRAP_RS_EMPTY)
    return m.rs.pop()
