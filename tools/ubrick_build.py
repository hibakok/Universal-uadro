# @uadro
# @file    tools/ubrick_build.py
# @layer   T0
# @branch  t0.ubrick.build
# @desc    Сборка программы uBrick: пролог, производные слова словаря,
# @desc    определения и данные исходника в текст uAsm и образ UVM
# @desc    (SPEC/L3-UBRICK.txt, раздел 7).

"""Сборка программы uBrick (ветвь t0.ubrick.build).

Вход — записи ветви t0.ubrick.parse (parse_ubrk): имена, литералы
и связывание конструкций уже проверены, слово main гарантировано
разбором; компиляция тел — кирпичи ветви t0.ubrick.compile, словарь —
ветви t0.ubrick.dict (CHARTER.txt, п. 2: кирпич не дублирует работу
соседа).

Текст uAsm печатается в четыре части (SPEC, раздел 7): пролог
(CALL main, HALT 0); производные слова словаря — метка, тело, RET
(тела — кортежи слов uBrick: превращение в элементы — здесь,
компиляция — те же кирпичи); определения исходника в порядке
появления — метка слова, тело, RET, var и text — PUSH d_имя, RET;
секция данных — d_имя: DW 0 (var) или DZ "литерал" (text). Счётчик
служебных меток _L<n> один на программу: производные слова берут
номера первыми, определения исходника продолжают нумерацию. Образ
собирает ассемблер uAsm (ветвь t0.uasm.assemble); его ошибки
(недостижимые для записей из разбора) build_ubrk пропускает наружу.
"""

from tools.uasm_assemble import assemble
from tools.uasm_lex import parse_number
from tools.ubrick_compile import compile_body, new_counter
from tools.ubrick_dict import (
    derived_body,
    derived_names,
    find_word,
    is_construct,
)

LITERALS = {0: "\\0", 9: "\\t", 10: "\\n", 13: "\\r",
            34: '\\"', 92: "\\\\"}  # escape-байты (SPEC/L2-UASM.txt, разд. 4)


# @method prologue() -> tuple
# @in    нет
# @out   lines: tuple — строки пролога ("CALL main", "HALT 0")
# @does  Часть 1 текста (SPEC, разделы 2 и 7): вход в программу —
# @does  CALL main; возврат из main попадает на HALT 0.
def prologue():
    return ("CALL main", "HALT 0")


# @method token_element(token) -> tuple
# @in    token: str — слово тела производного слова словаря
# @out   element: tuple — ("construct", слово) | ("word", слово) |
# @out   ("lit", значение)
# @does  Превращает слово тела производного слова в элемент тела:
# @does  конструкция — construct, слово словаря — word, прочее —
# @does  численный литерал форм uAsm; согласованность тел гарантирует
# @does  ветвь t0.ubrick.dict (проверено её тестами).
# @depends is_construct, find_word, parse_number
def token_element(token):
    if is_construct(token):
        return ("construct", token)
    if find_word(token) is not None:
        return ("word", token)
    return ("lit", parse_number(token))


# @method derived_elements(body) -> tuple
# @in    body: tuple — кортеж слов uBrick: тело производного слова
# @out   elements: tuple — элементы тела для compile_body
# @does  Превращает тело производного слова словаря в элементы тела
# @does  (SPEC, раздел 4.2): по одному элементу на слово (token_element).
# @depends token_element
def derived_elements(body):
    return tuple(token_element(token) for token in body)


# @method word_lines(name, elements, counter) -> tuple
# @in    name: str — имя слова (метка)
# @in    elements: tuple — элементы тела (ветвь t0.ubrick.parse)
# @in    counter: dict — счётчик меток; метод двигает его
# @out   lines: tuple — метка, строки тела, RET
# @does  Печатает определение слова (SPEC, раздел 7): метка «имя:»,
# @does  тело — компилятором t0.ubrick.compile, завершение — RET.
# @depends compile_body
def word_lines(name, elements, counter):
    return (name + ":",) + compile_body(elements, counter) + ("RET",)


# @method ref_lines(name) -> tuple
# @in    name: str — имя var или text
# @out   lines: tuple — метка, PUSH d_имя, RET
# @does  Печатает слово-адрес данных (SPEC, разделы 6-7): обращение
# @does  к var/text кладёт адрес своей ячейки — PUSH d_имя.
def ref_lines(name):
    return (name + ":", "PUSH d_" + name, "RET")


# @method quote_literal(data) -> str
# @in    data: bytes — байты записи text: валидный UTF-8 (произведён
# @in    кирпичем take_string ветви t0.ubrick.parse)
# @out   literal: str — строковый литерал uAsm "..."
# @does  Записывает байты строковым литералом uAsm (SPEC/L2-UASM.txt,
# @does  раздел 4): байты 0, 9, 10, 13, кавычка и обратный слеш —
# @does  escape \\0 \\t \\n \\r \" \\, прочие символы UTF-8 — как есть;
# @does  parse_string разбирает литерал в те же байты.
def quote_literal(data):
    out = []
    for ch in data.decode("utf-8"):
        out.append(LITERALS.get(ord(ch), ch))
    return '"' + "".join(out) + '"'


# @method data_lines(record) -> tuple
# @in    record: tuple — запись разбора: ("var", имя), ("text", имя,
# @in    байты) либо ("word", ...) — слова данных не дают
# @out   lines: tuple — строки секции данных записи либо ()
# @does  Печатает данные записи (SPEC, разделы 6-7): var — метка d_имя
# @does  и DW 0 (ячейка 8 байтов), text — метка d_имя и DZ "литерал"
# @does  (байты UTF-8 литерала плюс нуль-байт).
# @depends quote_literal
def data_lines(record):
    if record[0] == "var":
        return ("d_" + record[1] + ":", "DW 0")
    if record[0] == "text":
        return ("d_" + record[1] + ":", "DZ " + quote_literal(record[2]))
    return ()


# @method definition_lines(record, counter) -> tuple
# @in    record: tuple — запись разбора: word, var либо text
# @in    counter: dict — счётчик меток; метод двигает его
# @out   lines: tuple — строки части определений записи либо ()
# @does  Печатает определение записи (SPEC, раздел 7): слово — метка,
# @does  тело, RET (word_lines); var и text — слово-адрес (ref_lines).
# @depends word_lines, ref_lines
def definition_lines(record, counter):
    if record[0] == "word":
        return word_lines(record[1], record[2], counter)
    if record[0] in ("var", "text"):
        return ref_lines(record[1])
    return ()


# @method derived_part(counter) -> tuple
# @in    counter: dict — счётчик меток; метод двигает его
# @out   lines: tuple — строки всех производных слов словаря
# @does  Часть 2 текста (SPEC, разделы 4.2 и 7): производные слова
# @does  в порядке derived_names — каждое меткой, телом и RET;
# @does  включаются всегда, исключение неиспользованных — оптимизация
# @does  будущих версий.
# @depends derived_names, derived_body, derived_elements, word_lines
def derived_part(counter):
    lines = []
    for name in derived_names():
        elements = derived_elements(derived_body(name))
        lines.extend(word_lines(name, elements, counter))
    return tuple(lines)


# @method definitions_part(records, counter) -> tuple
# @in    records: tuple — записи разбора в порядке исходника
# @in    counter: dict — счётчик меток; метод двигает его
# @out   lines: tuple — строки всех определений исходника
# @does  Часть 3 текста (SPEC, раздел 7): определения в порядке
# @does  появления — definition_lines на каждую запись.
# @depends definition_lines
def definitions_part(records, counter):
    lines = []
    for record in records:
        lines.extend(definition_lines(record, counter))
    return tuple(lines)


# @method data_part(records) -> tuple
# @in    records: tuple — записи разбора в порядке исходника
# @out   lines: tuple — строки секции данных
# @does  Часть 4 текста (SPEC, раздел 7): данные var и text в порядке
# @does  появления — data_lines на каждую запись (слова данных не дают).
# @depends data_lines
def data_part(records):
    lines = []
    for record in records:
        lines.extend(data_lines(record))
    return tuple(lines)


# @method build_text(records) -> str
# @in    records: tuple — записи разбора parse_ubrk (слово main
# @in    гарантировано разбором)
# @out   text: str — текст uAsm программы
# @does  Собирает текст uAsm (SPEC, раздел 7) из четырёх частей:
# @does  пролог, производные слова, определения исходника, секция
# @does  данных; счётчик _L<n> один на всю программу — производные
# @does  слова берут номера первыми, определения продолжают.
# @depends new_counter, prologue, derived_part, definitions_part, data_part
def build_text(records):
    counter = new_counter()
    parts = (prologue() + derived_part(counter)
             + definitions_part(records, counter) + data_part(records))
    return "\n".join(parts)


# @method build_ubrk(records) -> tuple
# @in    records: tuple — записи разбора parse_ubrk
# @out   pair: tuple — (образ, None) либо (None, текст ошибки
# @out   «uAsm: строка N: ...»)
# @does  Собирает образ UVM: текст build_text — ассемблером uAsm
# @does  (ветвь t0.uasm.assemble); записи разбора ошибок сборки не
# @does  дают (имена коллизий не имеют), ошибка пропускается наружу —
# @does  например, «неизвестное имя main» для записей без main.
# @depends build_text, assemble
def build_ubrk(records):
    return assemble(build_text(records))
