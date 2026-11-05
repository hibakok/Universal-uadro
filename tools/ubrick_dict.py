# @uadro
# @file    tools/ubrick_dict.py
# @layer   T0
# @branch  t0.ubrick.dict
# @desc    Словарь uBrick v0.1: примитивы и псевдонимы (имя -> одна
# @desc    инструкция uAsm), производные слова с телами словами uBrick
# @desc    и управляющие конструкции (SPEC/L3-UBRICK.txt, разделы 4-5).

"""Словарь uBrick v0.1 (ветвь t0.ubrick.dict).

Чистые данные и функции поиска над ними. Примитив и псевдоним дают
одну инструкцию uAsm: примитив — мнемонику без imm, псевдоним —
мнемонику с фиксированным imm (SPEC, раздел 4.1). Производное слово —
кортеж слов uBrick: примитивы, литералы, конструкции, другие
производные слова (SPEC, раздел 4.2); исполнять тела будут ветви
t0.ubrick.compile и t0.ubrick.build (раздел 10 SPEC).

Имена примитивов и псевдонимов — заглавные мнемоники, производных —
строчные: пользовательские имена тоже строчные (раздел 3 SPEC),
коллизий со словарём нет. Регистр значим: «add» и «ADD» — разные
слова. Конструкции раздела 5 — не слова словаря: их распознаёт
отдельный кирпич is_construct.
"""

# Формат записи примитива и псевдонима: (имя, инструкция uAsm).
# Инструкция — готовый текст без меток: мнемоника [фиксированный imm].
PRIMITIVES = (
    ("NOP", "NOP"),
    ("DROP", "DROP"),
    ("DUP", "DUP"),
    ("SWAP", "SWAP"),
    ("OVER", "OVER"),
    ("ROT", "ROT"),
    ("LOAD8", "LOAD8"),
    ("LOAD64", "LOAD64"),
    ("STORE8", "STORE8"),
    ("STORE64", "STORE64"),
    ("ADD", "ADD"),
    ("SUB", "SUB"),
    ("MUL", "MUL"),
    ("UDIV", "UDIV"),
    ("UMOD", "UMOD"),
    ("NEG", "NEG"),
    ("SHL", "SHL"),
    ("SHR", "SHR"),
    ("SAR", "SAR"),
    ("AND", "AND"),
    ("OR", "OR"),
    ("XOR", "XOR"),
    ("INV", "INV"),
    ("EQ", "EQ"),
    ("NEQ", "NEQ"),
    ("LTU", "LTU"),
    ("GTU", "GTU"),
    ("LEU", "LEU"),
    ("GEU", "GEU"),
)

# Псевдонимы: одна инструкция с фиксированным imm (SPEC, раздел 4.1).
ALIASES = (
    ("EMIT", "SYS 1"),    # ( c -- ) вывести байт c в stdout
    ("KEY", "SYS 0"),     # ( -- c ) прочитать байт stdin; EOF -> 2^64-1
    ("EXIT", "RET"),      # ( -- ) выход из слова (возврат)
    ("BYE", "HALT 0"),    # ( -- ) завершить программу, код 0
)

# Формат записи производного слова: (имя, тело). Тело — кортеж слов
# uBrick; комментарий над записью — эффект на стек DS (SPEC, раздел
# 4.2). Порядок записей — порядок таблицы раздела 4.2 SPEC.
DERIVED = (
    # not: ( ф -- ф' ) логическое отрицание: 0 -> 1, не 0 -> 0.
    ("not", ("0", "EQ")),
    # inc: ( a -- a+1 ) увеличение на 1 по модулю 2^64.
    ("inc", ("1", "ADD")),
    # dec: ( a -- a-1 ) уменьшение на 1 по модулю 2^64.
    ("dec", ("1", "SUB")),
    # lts: ( a b -- ф ) знаковое a < b, биас 2^63 (SPEC, раздел 4.2).
    ("lts", ("0x8000000000000000", "XOR", "SWAP",
             "0x8000000000000000", "XOR", "SWAP", "LTU")),
    # les: ( a b -- ф ) знаковое a <= b.
    ("les", ("0x8000000000000000", "XOR", "SWAP",
             "0x8000000000000000", "XOR", "SWAP", "LEU")),
    # gts: ( a b -- ф ) знаковое a > b.
    ("gts", ("0x8000000000000000", "XOR", "SWAP",
             "0x8000000000000000", "XOR", "SWAP", "GTU")),
    # ges: ( a b -- ф ) знаковое a >= b.
    ("ges", ("0x8000000000000000", "XOR", "SWAP",
             "0x8000000000000000", "XOR", "SWAP", "GEU")),
    # abs: ( a -- |a| ) модуль знакового числа: маска из знакового
    # бита, (a XOR маска) - маска.
    ("abs", ("DUP", "63", "SHR", "NEG", "SWAP", "OVER",
             "XOR", "SWAP", "SUB")),
    # min: ( a b -- m ) меньшее из двух (знаковое).
    ("min", ("OVER", "OVER", "gts", "IF",
             "SWAP", "DROP", "ELSE", "DROP", "THEN")),
    # max: ( a b -- m ) большее из двух (знаковое).
    ("max", ("OVER", "OVER", "lts", "IF",
             "SWAP", "DROP", "ELSE", "DROP", "THEN")),
    # load16: ( addr -- w ) беззнаковое чтение 16 бит (LE): два LOAD8.
    ("load16", ("DUP", "LOAD8", "SWAP", "1", "ADD",
                "LOAD8", "8", "SHL", "ADD")),
    # load32: ( addr -- w ) беззнаковое чтение 32 бита (LE): два
    # load16.
    ("load32", ("DUP", "load16", "SWAP", "2", "ADD",
                "load16", "16", "SHL", "ADD")),
    # store16: ( val addr -- ) запись младших 16 бит (LE): два STORE8.
    ("store16", ("OVER", "OVER", "STORE8", "SWAP", "8", "SHR",
                 "SWAP", "1", "ADD", "STORE8")),
    # store32: ( val addr -- ) запись младших 32 бит (LE): два
    # store16.
    ("store32", ("OVER", "OVER", "store16", "SWAP", "16", "SHR",
                 "SWAP", "2", "ADD", "store16")),
    # sext8: ( u -- s ) знак-расширение байта (по биту 7).
    ("sext8", ("56", "SHL", "56", "SAR")),
    # sext16: ( u -- s ) знак-расширение 16 бит (по биту 15).
    ("sext16", ("48", "SHL", "48", "SAR")),
    # sext32: ( u -- s ) знак-расширение 32 бит (по биту 31).
    ("sext32", ("32", "SHL", "32", "SAR")),
    # space: ( -- ) вывести пробел (байт 32).
    ("space", ("32", "EMIT")),
    # cr: ( -- ) вывести перевод строки (байт 10).
    ("cr", ("10", "EMIT")),
    # prints: ( addr -- ) печатать байты с addr до байта 0
    # (SPEC, раздел 5, пример).
    ("prints", ("BEGIN", "DUP", "LOAD8", "DUP", "0", "EQ",
                "IF", "DROP", "DROP", "EXIT", "THEN",
                "EMIT", "1", "ADD", "AGAIN")),
)

# Управляющие конструкции (SPEC, раздел 5): не слова словаря.
CONSTRUCTS = (
    "IF",
    "ELSE",
    "THEN",
    "BEGIN",
    "UNTIL",
    "AGAIN",
)

BY_PRIM = {rec[0]: rec[1] for rec in PRIMITIVES}
BY_ALIAS = {rec[0]: rec[1] for rec in ALIASES}
BY_DERIVED = {rec[0]: rec[1] for rec in DERIVED}


# @method primitive_instr(name) -> str
# @in    name: str — имя слова (регистр значим)
# @out   instr: str — текст инструкции uAsm или None, если имени нет
# @does  Даёт одну инструкцию uAsm для примитива или псевдонима
# @does  (SPEC, раздел 4.1, «включая псевдонимы»); слово управления
# @does  (PUSH, JMP, ...) и строчные имена дают None.
def primitive_instr(name):
    instr = BY_PRIM.get(name)
    if instr is None:
        instr = BY_ALIAS.get(name)
    return instr


# @method derived_body(name) -> tuple
# @in    name: str — имя производного слова (регистр значим)
# @out   body: tuple — кортеж слов uBrick либо None, если имени нет
# @does  Даёт тело производного слова словами uBrick (SPEC, раздел
# @does  4.2) для компиляции ветвью t0.ubrick.compile.
def derived_body(name):
    return BY_DERIVED.get(name)


# @method find_word(name) -> tuple
# @in    name: str — имя слова (регистр значим)
# @out   entry: tuple — ("prim", instr) | ("alias", instr) |
# @out   ("derived", body) либо None, если имени нет в словаре
# @does  Единый поиск слова словаря с точным видом; конструкции —
# @does  не слова (см. is_construct).
# @depends primitive_instr, derived_body
def find_word(name):
    instr = primitive_instr(name)
    if instr is not None:
        kind = "alias" if name in BY_ALIAS else "prim"
        return (kind, instr)
    body = derived_body(name)
    if body is not None:
        return ("derived", body)
    return None


# @method primitive_names() -> tuple
# @in    нет
# @out   names: tuple — имена 29 примитивов-мнемоник
# @does  Список слов группы «примитивы» (SPEC, раздел 4.1).
def primitive_names():
    return tuple(rec[0] for rec in PRIMITIVES)


# @method alias_names() -> tuple
# @in    нет
# @out   names: tuple — имена 4 псевдонимов
# @does  Список слов группы «псевдонимы» (SPEC, раздел 4.1).
def alias_names():
    return tuple(rec[0] for rec in ALIASES)


# @method derived_names() -> tuple
# @in    нет
# @out   names: tuple — имена 20 производных слов в порядке SPEC
# @does  Список слов группы «производные» (SPEC, раздел 4.2); порядок
# @does  задаёт порядок генерации тел ветвью t0.ubrick.build.
def derived_names():
    return tuple(rec[0] for rec in DERIVED)


# @method word_names() -> tuple
# @in    нет
# @out   names: tuple — все 53 имени словаря: примитивы, затем
# @out   псевдонимы, затем производные
# @does  Полный список слов словаря uBrick v0.1.
# @depends primitive_names, alias_names, derived_names
def word_names():
    return primitive_names() + alias_names() + derived_names()


# @method is_construct(name) -> bool
# @in    name: str — имя слова (регистр значим)
# @out   flag: bool — True, если имя — конструкция раздела 5 SPEC
# @does  Распознаёт управляющие конструкции IF/ELSE/THEN/BEGIN/
# @does  UNTIL/AGAIN; примитивы и производные дают False.
def is_construct(name):
    return name in CONSTRUCTS
