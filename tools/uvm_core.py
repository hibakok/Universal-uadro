# @uadro
# @file    tools/uvm_core.py
# @layer   T0
# @branch  t0.uvm.core
# @desc    Ядро UVM: состояние машины, ловушки, ОЗУ, стеки DS/RS, счётчик
# @desc    шагов CYC и поле шины устройств (SPEC/L0-UVM.txt, раздел 1;
# @desc    CYC и шина — черновик v0.3, Этап 5).

"""Ядро виртуальной машины UVM (ветвь t0.uvm.core).

Здесь живут только кирпичи состояния по SPEC/L0-UVM.txt: слова, ловушки,
ОЗУ, стеки DS/RS, счётчик шагов CYC, поле шины устройств и загрузка
образа. Исполнение инструкций — следующие ветви: t0.uvm.ops,
t0.uvm.table, t0.uvm.decode, t0.uvm.exec, t0.uvm.run, t0.uvm.cli;
механика шины — ветвь t0.uvm.bus (tools/uvm_bus.py).
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
TRAP_BAD_PORT = 9    # отказ устройства: без шины, порт не привязан
                     # или операция запрещена (v0.3, SPEC, 6А.1)


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


# @method to_signed(w) -> int
# @in    w: int — 64-битное слово без знака (возможно, вне диапазона)
# @out   s: int — то же значение как знаковое -2^63..2^63-1
# @does  Читает слово в дополнительном коде до двух; кирпич инструкции
# @does  SAR и будущих знаковых операций слоя uBrick.
def to_signed(w):
    w &= WORD_MASK
    if w >= (1 << (WORD_BITS - 1)):
        return w - (1 << WORD_BITS)
    return w


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


# @method UvmHalt(code)
# @in    code: int — код завершения 0..255 (imm инструкции HALT по
# @in    модулю 256)
# @out   exception — нормальная остановка с полем code
# @does  Нормальное завершение по HALT imm (SPEC, раздел 5): в отличие
# @does  от ловушек UvmTrap ошибкой не является; поднимается обработчиком
# @does  HALT ветви t0.uvm.ops, ловит цикл ветви t0.uvm.run.
class UvmHalt(Exception):
    """Нормальная остановка UVM; поле code — код завершения 0..255."""

    def __init__(self, code):
        super().__init__(f"остановка {code}")
        self.code = code


# @method Machine(ram_size, ds_size, rs_size)
# @in    ram_size: int — размер ОЗУ в байтах (по умолчанию 1 МиБ)
# @in    ds_size: int — ёмкость стека данных в словах (по умолчанию 1024)
# @in    rs_size: int — ёмкость стека возвратов в словах (по умолчанию 256)
# @out   m: Machine — состояние UVM
# @does  Свежее состояние: ОЗУ из нулей, PC = 0, CYC = 0, стеки DS и RS
# @does  пусты, шина не привязана (SPEC, разделы 1-2; CYC и шина —
# @does  v0.3: bus = None, пока раннер не привязал устройства).
class Machine:
    """Состояние UVM: ОЗУ, PC, CYC, стеки DS и RS, шина устройств.

    ОЗУ — байтовый массив; стеки — отдельные списки слов, не отображённые
    в ОЗУ (SPEC, раздел 1). Ёмкости хранятся в ds_size и rs_size.
    CYC — счётчик шагов, слово по модулю 2^64 (v0.3). Шина bus — таблица
    «порт -> устройство» (None до привязки раннером); её механика —
    ветвь t0.uvm.bus, ядро только хранит поле.
    """

    def __init__(self, ram_size=RAM_SIZE_DEFAULT, ds_size=DS_SIZE_DEFAULT,
                 rs_size=RS_SIZE_DEFAULT):
        self.ram = bytearray(ram_size)
        self.pc = 0
        self.cyc = 0
        self.ds = []
        self.ds_size = ds_size
        self.rs = []
        self.rs_size = rs_size
        self.bus = None


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
# @does  Читает байт ОЗУ; адрес вне ОЗУ — ловушка 7. Горячий кирпич
# @does  интерпретатора: проверка границы встроена в тело (раньше —
# @does  вызов in_ram); поведение то же, вызовов меньше.
# @depends trap
def load_byte(m, addr):
    if not 0 <= addr < len(m.ram):
        trap(TRAP_OOB)
    return m.ram[addr]


# @method store_byte(m, addr, val) -> None
# @in    m: Machine — состояние машины
# @in    addr: int — адрес байта
# @in    val: int — значение; записывается его младший байт
# @out   нет
# @does  Пишет младший байт val в ОЗУ; адрес вне ОЗУ — ловушка 7.
# @does  Горячий кирпич интерпретатора: проверка границы встроена
# @does  в тело (раньше — вызов in_ram); поведение то же.
# @depends trap
def store_byte(m, addr, val):
    if not 0 <= addr < len(m.ram):
        trap(TRAP_OOB)
    m.ram[addr] = val & BYTE_MASK


# @method load_word(m, addr) -> int
# @in    m: Machine — состояние машины
# @in    addr: int — адрес младшего байта слова
# @out   w: int — 64-битное слово
# @does  Собирает слово из 8 байтов ОЗУ в порядке little-endian, без
# @does  требования выравнивания (SPEC, раздел 1). Быстрый путь — срез
# @does  восьми байтов одной проверкой границы; слово на границе ОЗУ
# @does  идёт побайтово через load_byte — ловушка 7 на первом байте
# @does  вне ОЗУ, как раньше.
# @depends load_byte
def load_word(m, addr):
    ram = m.ram
    if 0 <= addr and addr + 8 <= len(ram):
        return int.from_bytes(ram[addr:addr + 8], "little")
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
# @does  без требования выравнивания. Быстрый путь — срез восемь
# @does  байтов одной проверкой границы; слово на границе ОЗУ идёт
# @does  побайтово через store_byte — ловушка 7 на первом байте
# @does  вне ОЗУ, как раньше.
# @depends store_byte
def store_word(m, addr, val):
    ram = m.ram
    if 0 <= addr and addr + 8 <= len(ram):
        ram[addr:addr + 8] = (val & WORD_MASK).to_bytes(8, "little")
        return
    for i in range(8):
        store_byte(m, addr + i, (val >> (8 * i)) & BYTE_MASK)


# @method load_image(m, image) -> None
# @in    m: Machine — состояние машины
# @in    image: bytes — образ программы
# @out   нет
# @does  Копирует образ в ОЗУ с адреса 0 и сбрасывает состояние запуска:
# @does  PC = 0, CYC = 0, DS и RS пусты (SPEC, раздел 2); образ больше
# @does  ОЗУ — ловушка 7. Шина не трогается: привязка устройств —
# @does  дело раннера, а не загрузки (v0.3, раздел 2, п. 3).
# @depends trap
def load_image(m, image):
    if len(image) > len(m.ram):
        trap(TRAP_OOB)
    m.ram[0:len(image)] = image
    m.pc = 0
    m.cyc = 0
    m.ds.clear()
    m.rs.clear()


# @method ds_push(m, w) -> None
# @in    m: Machine — состояние машины
# @in    w: int — слово; оборачивается по модулю 2^64
# @out   нет
# @does  Кладёт слово на стек данных; переполнение ёмкости — ловушка 3.
# @does  Горячий кирпич интерпретатора: маска слова встроена в тело
# @does  (раньше — вызов to_word); поведение то же.
# @depends trap
def ds_push(m, w):
    if len(m.ds) >= m.ds_size:
        trap(TRAP_DS_FULL)
    m.ds.append(w & WORD_MASK)


# @method ds_pop(m) -> int
# @in    m: Machine — состояние машины
# @out   w: int — снятое слово
# @does  Снимает вершину стека данных; пустой стек — ловушка 2.
# @depends trap
def ds_pop(m):
    if not m.ds:
        trap(TRAP_DS_EMPTY)
    return m.ds.pop()


# @method ds_pop2(m) -> tuple
# @in    m: Machine — состояние машины
# @out   pair: tuple — (a, b): a — глубже, b — вершина
# @does  Снимает два верхних слова стека данных: a — первый операнд
# @does  бинарной операции, b — второй; меньше двух слов — ловушка 2.
# @does  Кирпич бинарных инструкций (STORE8/STORE64, арифметика,
# @does  сравнения).
# @depends ds_pop
def ds_pop2(m):
    b = ds_pop(m)
    a = ds_pop(m)
    return a, b


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
# @does  Горячий кирпич интерпретатора: маска слова встроена в тело
# @does  (раньше — вызов to_word); поведение то же.
# @depends trap
def rs_push(m, w):
    if len(m.rs) >= m.rs_size:
        trap(TRAP_RS_FULL)
    m.rs.append(w & WORD_MASK)


# @method rs_pop(m) -> int
# @in    m: Machine — состояние машины
# @out   w: int — снятое слово
# @does  Снимает вершину стека возвратов; пустой стек — ловушка 4.
# @depends trap
def rs_pop(m):
    if not m.rs:
        trap(TRAP_RS_EMPTY)
    return m.rs.pop()
