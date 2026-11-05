# @uadro
# @file    tools/ubrick_parse.py
# @layer   T0
# @branch  t0.ubrick.parse
# @desc    Разбор исходника uBrick в записи: определения слов «: ... ;»,
# @desc    var, text, слова и литералы тел (SPEC/L3-UBRICK.txt v0.2,
# @desc    разделы 3 и 8); ошибки «uBrick: строка N: текст».

"""Разбор исходника uBrick v0.1 (ветвь t0.ubrick.parse).

Разбор потоковый (SPEC, раздел 3): тело определения живёт на нескольких
строках, перенос строки — разделитель слов; имя определения — первое
слово после «:», даже на следующей строке.

Виды записей (первый элемент — вид):
- ("word", имя, тело)   — определение слова; тело — кортеж элементов
- ("var", имя)          — переменная
- ("text", имя, байты)  — строка данных: байты UTF-8 без завершающего 0

Элементы тела: ("word", слово) — примитив, псевдоним, производное или
пользовательское слово (включая var/text); ("lit", значение) — численный
литерал диапазона -2^63..2^64-1; ("construct", слово) — конструкции
IF/ELSE/THEN/BEGIN/UNTIL/AGAIN.

Правила «;» (v0.2, раздел 3 SPEC): «;» вне литералов в кавычках
обрезает строку; строка, начинающаяся с него, — комментарий; обрезавший
строку «;» внутри определения закрывает тело, вне определения после
непустого начала — ошибка «точка с запятой вне определения».

Порядок ошибок (v0.2, раздел 8 SPEC): синтаксические и структурные
ошибки прекращают разбор первой по ходу текста; «неизвестное слово»
и «слово main обязательно» назначаются по безошибочному исходнику
в порядке следования. Исключения не используются: разбор возвращает
пару (записи, None) либо (None, сообщение об ошибке).
"""

from tools.uasm_lex import STR_ESCAPES, in_literal_range, parse_number
from tools.uasm_line import find_outside_quotes, split_first, split_words
from tools.ubrick_dict import (
    derived_names,
    find_word,
    is_construct,
    primitive_instr,
    word_names,
)

SPACES = " \t"                        # разделители слов (SPEC, раздел 3)
LOWER = "abcdefghijklmnopqrstuvwxyz"  # первый символ имени
NAME_REST = LOWER + "0123456789"      # прочие символы имени
RESERVED = ("var", "text")            # ключевые слова операторов (v0.2)
DERIVED_SET = frozenset(derived_names())


# @method split_lines(text) -> list
# @in    text: str — исходный текст uBrick
# @out   lines: list — строки без концевых байтов CR
# @does  Делит текст по LF, снимает концевые CR (CRLF как LF);
# @does  повторяет кирпич split_lines ветви t0.uasm.assemble.
def split_lines(text):
    return [line.rstrip("\r") for line in text.split("\n")]


# @method wrap_error(line_no, text) -> str
# @in    line_no: int — номер строки, начиная с 1
# @in    text: str — текст ошибки без префикса
# @out   msg: str — сообщение «uBrick: строка N: текст»
# @does  Приписывает ошибке номер строки (SPEC, раздел 8).
def wrap_error(line_no, text):
    return "uBrick: строка " + str(line_no) + ": " + text


# @method is_word_name(text) -> bool
# @in    text: str — слово без пробелов
# @out   flag: bool — True для имени [a-z][a-z0-9]*
# @does  Распознаёт имя (SPEC, раздел 3): строчная латиница, затем
# @does  латиница или цифры; регистр значим, дефисы запрещены.
def is_word_name(text):
    if not text or text[0] not in LOWER:
        return False
    return all(ch in NAME_REST for ch in text[1:])


# @method take_string(text) -> tuple
# @in    text: str — текст, возможно начинающийся строковым литералом
# @out   pair: tuple — (байты UTF-8, остаток без краевых пробелов) либо
# @out   None: нет кавычки в начале, незакрытая кавычка, дурной escape
# @does  Разбирает один строковый литерал "..." в начале текста (формы
# @does  SPEC/L2-UASM.txt, раздел 4; escape \\n \\r \\t \\\\ \\" \\0);
# @does  семантика повторяет кирпич parse_string ветви t0.uasm.lex.
def take_string(text):
    if not text.startswith('"'):
        return None
    out = bytearray()
    i = 1
    while i < len(text):
        ch = text[i]
        if ch == '"':
            return bytes(out), text[i + 1:].strip(SPACES)
        if ch == "\\":
            if i + 1 >= len(text) or text[i + 1] not in STR_ESCAPES:
                return None
            out.append(STR_ESCAPES[text[i + 1]])
            i += 2
        else:
            out += ch.encode("utf-8")
            i += 1
    return None


# @method new_state() -> dict
# @in    нет
# @out   state: dict — records (записи), error (текст или None),
# @out   word (открытое определение), refs (пары слово/строка),
# @out   defined (все имена), words (имена через «:»)
# @does  Создаёт начальное состояние разбора.
def new_state():
    return {"records": [], "error": None, "word": None,
            "refs": [], "defined": set(), "words": set()}


# @method fail(state, line_no, text) -> None
# @in    state: dict — состояние разбора; метод пишет state["error"]
# @in    line_no: int — номер строки
# @in    text: str — текст ошибки без префикса
# @out   нет
# @does  Запоминает первую ошибку с номером строки; повторные вызовы
# @does  сообщение не меняют (SPEC, раздел 8).
# @depends wrap_error
def fail(state, line_no, text):
    if state["error"] is None:
        state["error"] = wrap_error(line_no, text)


# @method open_word(state) -> None
# @in    state: dict — состояние разбора; метод пишет state["word"]
# @out   нет
# @does  Открывает определение после «:»: имя ещё не прочитано,
# @does  тело и стек конструкций пусты.
def open_word(state):
    state["word"] = {"name": None, "body": [], "stack": []}


# @method name_taken(name) -> bool
# @in    name: str — проверяемое имя
# @out   flag: bool — True, если имя занято
# @does  Занятость имени (v0.2, раздел 8 SPEC): примитив, псевдоним,
# @does  конструкция или ключевое слово var/text.
# @depends primitive_instr, is_construct
def name_taken(name):
    return (primitive_instr(name) is not None or is_construct(name)
            or name in RESERVED)


# @method check_name(state, line_no, name) -> bool
# @in    state: dict — состояние разбора
# @in    line_no: int — номер строки имени
# @in    name: str — проверяемое имя
# @out   flag: bool — True, если имя корректно и свободно (и уже
# @out   занесено в state["defined"])
# @does  Проверяет новое имя в порядке раздела 8 SPEC: «имя занято X»,
# @does  «плохое имя X», «повторное определение слова X» (производная
# @does  словаря, слово, var, text, main).
# @depends name_taken, is_word_name, fail
def check_name(state, line_no, name):
    if name_taken(name):
        fail(state, line_no, "имя занято " + name)
        return False
    if not is_word_name(name):
        fail(state, line_no, "плохое имя " + name)
        return False
    if name in DERIVED_SET or name in state["defined"]:
        fail(state, line_no, "повторное определение слова " + name)
        return False
    state["defined"].add(name)
    return True


# @method set_word_name(state, line_no, name) -> None
# @in    state: dict — состояние разбора с открытым определением
# @in    line_no: int — номер строки слова-имени
# @in    name: str — имя-кандидат (следующее слово после «:»)
# @out   нет; при ошибке state["error"] занят, иначе имя присвоено
# @does  Назначает имя открытому определению; кандидат проверяется
# @does  правилами имён, поэтому «: ;» даёт «плохое имя ;».
# @depends check_name
def set_word_name(state, line_no, name):
    if check_name(state, line_no, name):
        state["word"]["name"] = name
        state["words"].add(name)


# @method close_word(state, line_no) -> None
# @in    state: dict — состояние разбора с открытым определением
# @in    line_no: int — номер строки закрывающего «;»
# @out   нет; при незакрытых конструкциях или без имени — ошибка,
# @out   иначе слово добавлено в записи
# @does  Закрывает определение по «;» (SPEC, разделы 3 и 5): стек
# @does  конструкций пуст, иначе «незакрытый IF»/«незакрытый BEGIN»
# @does  по первой открытой (v0.2); без имени — «плохое имя ;»; тело
# @does  становится записью ("word", имя, тело).
# @depends fail
def close_word(state, line_no):
    word = state["word"]
    if word["stack"]:
        fail(state, line_no, "незакрытый " + word["stack"][0][0])
        return
    if word["name"] is None:
        fail(state, line_no, "плохое имя ;")
        return
    state["records"].append(("word", word["name"], tuple(word["body"])))
    state["word"] = None


# @method construct_step(state, line_no, token) -> None
# @in    state: dict — состояние разбора с открытым определением
# @in    line_no: int — номер строки конструкции
# @in    token: str — IF, ELSE, THEN, BEGIN, UNTIL или AGAIN
# @out   нет; ошибка — в state["error"], элемент тела добавлен
# @out   при успехе
# @does  Шаг конструкции (SPEC, раздел 5): IF и BEGIN кладутся в стек
# @does  вложенности, ELSE помечает открытый IF, THEN/UNTIL/AGAIN
# @does  снимают верхнюю; нарушения — «THEN без IF», «ELSE без IF»,
# @does  «ELSE после ELSE», «UNTIL без BEGIN», «AGAIN без BEGIN».
# @depends fail
def construct_step(state, line_no, token):
    word = state["word"]
    stack = word["stack"]
    if token == "IF":
        stack.append(["IF", line_no, False])
    elif token == "BEGIN":
        stack.append(["BEGIN", line_no])
    elif token == "ELSE":
        if not stack or stack[-1][0] != "IF":
            fail(state, line_no, "ELSE без IF")
            return
        if stack[-1][2]:
            fail(state, line_no, "ELSE после ELSE")
            return
        stack[-1][2] = True
    elif token == "THEN":
        if not stack or stack[-1][0] != "IF":
            fail(state, line_no, "THEN без IF")
            return
        stack.pop()
    else:
        if not stack or stack[-1][0] != "BEGIN":
            fail(state, line_no, token + " без BEGIN")
            return
        stack.pop()
    word["body"].append(("construct", token))


# @method body_literal(state, line_no, token) -> None
# @in    state: dict — состояние разбора с открытым определением
# @in    line_no: int — номер строки литерала
# @in    token: str — слово, не имя и не слово словаря
# @out   нет; при успехе элемент ("lit", значение) добавлен в тело
# @does  Численный литерал тела (SPEC, раздел 3): формы и диапазон
# @does  SPEC/L2-UASM.txt, раздел 4; нераспознанное слово — «плохой
# @does  литерал X», выход за -2^63..2^64-1 — «литерал вне диапазона».
# @depends parse_number, in_literal_range, fail
def body_literal(state, line_no, token):
    value = parse_number(token)
    if value is None:
        fail(state, line_no, "плохой литерал " + token)
        return
    if not in_literal_range(value):
        fail(state, line_no, "литерал вне диапазона")
        return
    state["word"]["body"].append(("lit", value))


# @method body_token(state, line_no, token) -> None
# @in    state: dict — состояние разбора с открытым определением
# @in    line_no: int — номер строки слова
# @in    token: str — слово тела
# @out   нет; ошибка или элемент тела — по виду слова
# @does  Обрабатывает слово тела (SPEC, разделы 3-5): «:», var и text
# @does  внутри тела — ошибки; конструкция — construct_step; слово
# @does  словаря — элемент ("word", слово); строчное имя — ссылка
# @does  (проверяется в конце разбора); прочее — численный литерал.
# @depends construct_step, find_word, is_construct, is_word_name, body_literal, fail
def body_token(state, line_no, token):
    if token == ":":
        fail(state, line_no, "двоеточие внутри определения")
        return
    if token in RESERVED:
        fail(state, line_no, token + " внутри определения")
        return
    if is_construct(token):
        construct_step(state, line_no, token)
        return
    if find_word(token) is not None:
        state["word"]["body"].append(("word", token))
        return
    if is_word_name(token):
        state["refs"].append((token, line_no))
        state["word"]["body"].append(("word", token))
        return
    body_literal(state, line_no, token)


# @method body_line(state, tokens, line_no) -> None
# @in    state: dict — состояние разбора
# @in    tokens: list — слова строки (без «;»-хвоста)
# @in    line_no: int — номер строки
# @out   нет
# @does  Слова строки открытого определения: первое слово после «:» —
# @does  имя, прочие — слова тела; первая ошибка прекращает строку.
# @depends set_word_name, body_token
def body_line(state, tokens, line_no):
    for token in tokens:
        if state["error"] is not None:
            return
        if state["word"]["name"] is None:
            set_word_name(state, line_no, token)
        else:
            body_token(state, line_no, token)


# @method semicolon_tail(state, line_no) -> None
# @in    state: dict — состояние разбора
# @in    line_no: int — номер строки «;»
# @out   нет
# @does  Обрезавший строку «;» (v0.2, раздел 3 SPEC): внутри определения
# @does  закрывает тело (остаток строки уже отброшен), вне — ошибка
# @does  «точка с запятой вне определения».
# @depends close_word, fail
def semicolon_tail(state, line_no):
    if state["word"] is None:
        fail(state, line_no, "точка с запятой вне определения")
    else:
        close_word(state, line_no)


# @method var_line(state, tokens, line_no) -> None
# @in    state: dict — состояние разбора
# @in    tokens: list — слова строки после var (без «;»-хвоста)
# @in    line_no: int — номер строки
# @out   нет
# @does  Оператор var (SPEC, разделы 3 и 6): имя по правилам раздела 3
# @does  и ровно одно слово после var — иначе «var без имени» или
# @does  «лишние слова после var»; успех — запись ("var", имя).
# @depends check_name, fail
def var_line(state, tokens, line_no):
    if not tokens:
        fail(state, line_no, "var без имени")
        return
    if not check_name(state, line_no, tokens[0]):
        return
    if len(tokens) > 1:
        fail(state, line_no, "лишние слова после var")
        return
    state["records"].append(("var", tokens[0]))


# @method text_line(state, rest, line_no) -> None
# @in    state: dict — состояние разбора
# @in    rest: str — остаток строки после слова text (без «;»-хвоста)
# @in    line_no: int — номер строки
# @out   нет
# @does  Оператор text (SPEC, разделы 3 и 6): имя, затем ровно один
# @does  строковый литерал — иначе «text без имени», «плохой строковый
# @does  литерал» или «лишние слова после text»; успех — запись
# @does  ("text", имя, байты UTF-8 литерала).
# @depends split_first, check_name, take_string, fail
def text_line(state, rest, line_no):
    if not rest.strip(SPACES):
        fail(state, line_no, "text без имени")
        return
    name, rest = split_first(rest)
    if not check_name(state, line_no, name):
        return
    taken = take_string(rest)
    if taken is None:
        fail(state, line_no, "плохой строковый литерал")
        return
    if taken[1]:
        fail(state, line_no, "лишние слова после text")
        return
    state["records"].append(("text", name, taken[0]))


# @method top_line(state, head, tokens, line_no) -> None
# @in    state: dict — состояние разбора вне определения
# @in    head: str — часть строки до «;» вне кавычек
# @in    tokens: list — слова head
# @in    line_no: int — номер строки
# @out   нет
# @does  Оператор верхнего уровня (SPEC, раздел 3): «:» открывает
# @does  определение (имя и тело читают и следующие строки), var и
# @does  text — однострочные; конструкция вне определения — своя
# @does  ошибка, прочее слово — «слово вне определения X».
# @depends open_word, body_line, var_line, split_first, text_line, is_construct, fail
def top_line(state, head, tokens, line_no):
    first = tokens[0]
    if first == ":":
        open_word(state)
        body_line(state, tokens[1:], line_no)
    elif first == "var":
        var_line(state, tokens[1:], line_no)
    elif first == "text":
        rest = split_first(head.strip(SPACES))[1]
        text_line(state, rest, line_no)
    elif is_construct(first):
        fail(state, line_no, "конструкция вне определения")
    else:
        fail(state, line_no, "слово вне определения " + first)


# @method process_line(state, raw, line_no) -> None
# @in    state: dict — состояние разбора
# @in    raw: str — исходная строка текста
# @in    line_no: int — номер строки
# @out   нет
# @does  Обрабатывает строку (v0.2, раздел 3 SPEC): «;» вне кавычек
# @does  обрезает строку (строка с «;» в начале — комментарий),
# @does  оставшиеся слова уходят верхнему уровню или открытому
# @does  определению; обрезавший «;» — semicolon_tail.
# @depends find_outside_quotes, split_words, top_line, body_line, semicolon_tail
def process_line(state, raw, line_no):
    cut = find_outside_quotes(raw, ";")
    tail = cut >= 0
    head = raw if cut < 0 else raw[:cut]
    tokens = split_words(head)
    if tail and not head.strip(SPACES):
        return
    if not tokens and not tail:
        return
    if state["word"] is None:
        top_line(state, head, tokens, line_no)
    else:
        body_line(state, tokens, line_no)
    if tail and state["error"] is None:
        semicolon_tail(state, line_no)


# @method check_refs(state) -> None
# @in    state: dict — состояние разбора без ошибок
# @out   нет; первая неизвестная ссылка — ошибка в state["error"]
# @does  Проверяет слова-ссылки тел по окончании текста (v0.2, раздел 8
# @does  SPEC): ссылки вперёд разрешены, поэтому «неизвестное слово X»
# @does  назначается только в конце — первым в порядке следования.
# @depends word_names, fail
def check_refs(state):
    known = set(word_names()) | state["defined"]
    for token, line_no in state["refs"]:
        if token not in known:
            fail(state, line_no, "неизвестное слово " + token)
            return


# @method finish(state, last_line) -> None
# @in    state: dict — состояние разбора после всех строк
# @in    last_line: int — номер последней строки (пустой текст — 1)
# @out   нет; ошибки конца текста — в state["error"]
# @does  Завершает разбор (v0.2, раздел 8 SPEC): незакрытое определение
# @does  — «незакрытое определение X» («без имени», если имя не
# @does  прочитано); затем check_refs; отсутствие слова main — «слово
# @does  main обязательно» с номером последней строки (var/text его
# @does  не заменяют).
# @depends check_refs, fail
def finish(state, last_line):
    word = state["word"]
    if word is not None:
        if word["name"] is None:
            fail(state, last_line, "незакрытое определение без имени")
        else:
            fail(state, last_line, "незакрытое определение " + word["name"])
        return
    check_refs(state)
    if state["error"] is None and "main" not in state["words"]:
        fail(state, last_line, "слово main обязательно")


# @method parse_ubrk(text) -> tuple
# @in    text: str — исходный текст uBrick (UTF-8)
# @out   pair: tuple — (записи, None) либо (None, «uBrick: строка N:
# @out   текст»); записи — кортежи ("word", имя, тело), ("var", имя),
# @out   ("text", имя, байты) в порядке исходника
# @does  Разбирает исходник в записи по разделам 3 и 8 SPEC/L3-UBRICK
# @does  (v0.2): потоковая обработка строк (process_line), затем
# @does  контрольные проверки конца текста (finish); первая ошибка
# @does  прекращает разбор.
# @depends new_state, split_lines, process_line, finish
def parse_ubrk(text):
    state = new_state()
    lines = split_lines(text)
    for line_no, raw in enumerate(lines, 1):
        if state["error"] is not None:
            break
        process_line(state, raw, line_no)
    if state["error"] is None:
        finish(state, len(lines))
    if state["error"] is not None:
        return None, state["error"]
    return state["records"], None
