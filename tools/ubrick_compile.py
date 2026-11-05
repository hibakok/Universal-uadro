# @uadro
# @file    tools/ubrick_compile.py
# @layer   T0
# @branch  t0.ubrick.compile
# @desc    Компиляция тела определения uBrick в строки uAsm: слова —
# @desc    инструкции и CALL, литералы — PUSH imm, конструкции —
# @desc    переходы со служебными метками _L<n> (SPEC/L3-UBRICK.txt,
# @desc    разделы 2, 5 и 7).

"""Компиляция тел определений uBrick (ветвь t0.ubrick.compile).

Вход — элементы тела ("word"/"lit"/"construct") из записей ветви
t0.ubrick.parse: разбор уже проверил имена, литералы и связывание
конструкций, поэтому компиляция не повторяет проверок (CHARTER.txt,
п. 2: кирпич не дублирует работу соседа).

Выход — строки uAsm (SPEC/L2-UASM.txt, разделы 2-3): одна строка на
элемент тела. Служебные метки конструкций — _L<n>: счётчик один на
программу и растёт монотонно (SPEC/L3-UBRICK.txt, раздел 7), первый
номер — 1; имена слов не содержат заглавных и подчёркиваний, поэтому
коллизий со служебными метками нет. Метку слова, завершающий RET
и сборку программы из частей добавит ветвь t0.ubrick.build (раздел
10 SPEC); тела производных слов хранятся в словаре кортежами слов
uBrick — их превращение в элементы тоже войдёт в build.
"""

from tools.ubrick_dict import primitive_instr

MOD = 1 << 64  # модуль оборачивания литералов (SPEC, разделы 2-3)


# @method new_counter() -> dict
# @in    нет
# @out   counter: dict — {"n": 0}: номер последней выданной метки
# @does  Создаёт счётчик служебных меток _L<n> (SPEC, раздел 7):
# @does  один счётчик на программу, общий для всех её тел.
def new_counter():
    return {"n": 0}


# @method next_label(counter) -> str
# @in    counter: dict — счётчик меток; метод увеличивает n
# @out   label: str — имя очередной метки «_L<n>», первый — _L1
# @does  Выдаёт метку и подвигает счётчик: номера растут монотонно.
def next_label(counter):
    counter["n"] += 1
    return "_L" + str(counter["n"])


# @method lit_line(value) -> str
# @in    value: int — литерал тела, диапазон -2^63..2^64-1 (проверен
# @in    разбором, SPEC/L3-UBRICK.txt, раздел 3)
# @out   line: str — строка uAsm «PUSH imm»
# @does  Компилирует численный литерал (SPEC, разделы 2-3): PUSH imm;
# @does  отрицательные оборачиваются по модулю 2^64.
def lit_line(value):
    return "PUSH " + str(value % MOD)


# @method word_line(token) -> str
# @in    token: str — слово тела: примитив, псевдоним, производное
# @in    или слово пользователя (включая var/text)
# @out   line: str — строка uAsm
# @does  Компилирует слово тела (SPEC, раздел 2): примитив и псевдоним
# @does  врезаются одной инструкцией (EXIT — RET), производное слово
# @does  и слово пользователя — подпрограммы: обращение — CALL их
# @does  метки.
# @depends primitive_instr
def word_line(token):
    instr = primitive_instr(token)
    if instr is not None:
        return instr
    return "CALL " + token


# @method construct_line(lines, stack, counter, token) -> None
# @in    lines: list — накопленные строки тела; метод дописывает в конец
# @in    stack: list — стек меток открытых конструкций (связывание уже
# @in    проверено разбором, SPEC, раздел 5)
# @in    counter: dict — счётчик меток; метод двигает его
# @in    token: str — IF, ELSE, THEN, BEGIN, UNTIL или AGAIN
# @out   нет
# @does  Компилирует конструкцию (SPEC, разделы 5 и 7): IF — JZ вперёд,
# @does  ELSE — JMP вперёд и метка IF тут, THEN — метка тут (от IF или
# @does  от ELSE), BEGIN — метка тут, UNTIL — JZ назад, AGAIN — JMP
# @does  назад; служебные метки _L<n> выдаёт next_label.
# @depends next_label
def construct_line(lines, stack, counter, token):
    if token == "IF":
        label = next_label(counter)
        lines.append("JZ " + label)
        stack.append(label)
    elif token == "ELSE":
        here = stack.pop()
        after = next_label(counter)
        lines.append("JMP " + after)
        lines.append(here + ":")
        stack.append(after)
    elif token == "THEN":
        lines.append(stack.pop() + ":")
    elif token == "BEGIN":
        label = next_label(counter)
        lines.append(label + ":")
        stack.append(label)
    elif token == "UNTIL":
        lines.append("JZ " + stack.pop())
    else:
        lines.append("JMP " + stack.pop())


# @method compile_body(elements, counter) -> tuple
# @in    elements: tuple — тело определения: элементы ("word", имя),
# @in    ("lit", значение), ("construct", слово) из ветви t0.ubrick.parse
# @in    counter: dict — счётчик меток; метод двигает его
# @out   lines: tuple — строки uAsm тела; без метки слова и без RET
# @does  Компилирует тело определения (SPEC, разделы 2 и 5): порядок
# @does  элементов сохраняется; слова — word_line, литералы — lit_line,
# @does  конструкции — construct_line со своим стеком меток; к концу
# @does  тела стек пуст (связывание проверено разбором).
# @depends word_line, lit_line, construct_line
def compile_body(elements, counter):
    lines = []
    stack = []
    for element in elements:
        kind = element[0]
        if kind == "word":
            lines.append(word_line(element[1]))
        elif kind == "lit":
            lines.append(lit_line(element[1]))
        else:
            construct_line(lines, stack, counter, element[1])
    return tuple(lines)
