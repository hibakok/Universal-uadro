# @uadro
# @file    tools/ubrick_source.py
# @layer   T0
# @branch  t0.ubrick.source
# @desc    Загрузчик исходников uBrick: оператор use — многофайловые
# @desc    исходники склеиваются в один текст со сквозной нумерацией
# @desc    строк (SPEC/L3-UBRICK.txt, v0.3, раздел 3); ошибки загрузчика
# @desc    предшествуют ошибкам разбора.

"""Загрузчик исходников uBrick (ветвь t0.ubrick.source).

Оператор «use ИМЯ-ФАЙЛА» (v0.3) — однострочное включение исходника
вне определения: строки включённого файла встают на место строки use,
нумерация строк объединённого текста сквозная — номера строк ошибок
разбора и загрузчика относятся к одному тексту. Каталог включённого
файла — база его собственных use-путей; цикл включений и нечитаемый
файл — ошибки загрузчика («uBrick: строка N: текст», SPEC, раздел 8).

Загрузчик не разбирает программу: он лишь узнаёт use-строки (первое
слово строки — use, вне определения) и следит, открыто ли определение
(«:» первым словом открывает, «;» вне кавычек с непустой головой
закрывает) — теми же кирпичами, что и разбор (find_outside_quotes,
split_words). Ошибки содержимого — дело разбора (t0.ubrick.parse).

Кирпичи: read_file_text, new_loader, loader_fail, use_target,
opens_definition, closes_definition, use_path, in_cycle, file_lines,
source_line, include_file, resolve_uses.
"""

import os

from tools.uasm_line import find_outside_quotes, split_words
from tools.ubrick_parse import split_lines, wrap_error

USE_KEYWORD = "use"   # ключевое слово включения (SPEC, раздел 3, v0.3)
DEF_OPEN = ":"        # слово, открывающее определение (SPEC, раздел 3)


# @method read_file_text(path) -> str
# @in    path: str — путь к файлу исходника
# @out   text: str — текст файла UTF-8 либо None при ошибке чтения
# @does  Читает файл целиком; отсутствие файла, каталог и плохая
# @does  кодировка дают None (сообщение печатает вызывающий).
def read_file_text(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError):
        return None


# @method new_loader() -> dict
# @in    нет
# @out   state: dict — lines (строки объединённого текста), stack
# @out   (пути открытых включений), in_def (определение открыто),
# @out   error (текст ошибки или None)
# @does  Создаёт начальное состояние загрузчика.
def new_loader():
    return {"lines": [], "stack": [], "in_def": False, "error": None}


# @method loader_fail(loader, line_no, text) -> None
# @in    loader: dict — состояние загрузчика; метод пишет error
# @in    line_no: int — сквозной номер строки use
# @in    text: str — текст ошибки без префикса
# @out   нет
# @does  Запоминает первую ошибку с номером строки (как fail разбора);
# @does  повторные вызовы сообщение не меняют (SPEC, раздел 8).
# @depends wrap_error
def loader_fail(loader, line_no, text):
    if loader["error"] is None:
        loader["error"] = wrap_error(line_no, text)


# @method use_target(tokens) -> tuple
# @in    tokens: list — слова строки use (первое — само use)
# @out   pair: tuple — (имя файла, None) либо (None, текст ошибки):
# @out   «use без имени файла», «лишние слова после use»
# @does  Даёт имя файла строки use (SPEC, раздел 3, v0.3): ровно два
# @does  слова — use и имя; пробелы в имени невозможны (слова).
def use_target(tokens):
    if len(tokens) < 2:
        return None, "use без имени файла"
    if len(tokens) > 2:
        return None, "лишние слова после use"
    return tokens[1], None


# @method opens_definition(tokens, in_def) -> bool
# @in    tokens: list — слова строки до «;»-хвоста
# @in    in_def: bool — определение открыто
# @out   flag: bool — True, если строка открывает определение
# @does  Определение открывает «:» первым словом строки верхнего
# @does  уровня (как top_line разбора); «:» внутри тела — ошибка
# @does  разбора, состояние загрузчика не меняет.
def opens_definition(tokens, in_def):
    return not in_def and bool(tokens) and tokens[0] == DEF_OPEN


# @method closes_definition(tokens, tail, in_def) -> bool
# @in    tokens: list — слова строки до «;»-хвоста
# @in    tail: bool — строка обрезана «;» вне кавычек
# @in    in_def: bool — определение открыто
# @out   flag: bool — True, если строка закрывает определение
# @does  Определение закрывает обрезавший строку «;» с непустой
# @does  головой (как process_line разбора: строка-комментарий
# @does  определение не закрывает); вне определения такой «;» —
# @does  ошибка разбора, состояние не меняется.
def closes_definition(tokens, tail, in_def):
    return in_def and tail and bool(tokens)


# @method use_path(base_dir, name) -> str
# @in    base_dir: str — каталог включающего файла
# @in    name: str — имя файла из строки use
# @out   path: str — путь к включаемому файлу
# @does  Строит путь use-файла относительно каталога включающего
# @does  файла (SPEC, раздел 3, v0.3).
def use_path(base_dir, name):
    return os.path.join(base_dir, name)


# @method in_cycle(loader, path) -> bool
# @in    loader: dict — состояние загрузчика
# @in    path: str — абсолютный путь включаемого файла
# @out   flag: bool — True, если файл уже в стеке включений
# @does  Признаёт циклическое включение (SPEC, раздел 8, v0.3): файл
# @does  из стека включает себя транзитивно.
def in_cycle(loader, path):
    return path in loader["stack"]


# @method source_line(loader, base_dir, raw) -> None
# @in    loader: dict — состояние загрузчика
# @in    base_dir: str — каталог файла, которому принадлежит строка
# @in    raw: str — исходная строка текста
# @out   нет; строка добавляется к объединённому тексту, use-строка
# @out   заменяется строками включённого файла; ошибка — error
# @does  Обрабатывает одну строку исходника (SPEC, раздел 3, v0.3):
# @does  «;» вне кавычек делит строку на голову и хвост, слова —
# @does  split_words; строка use вне определения — включение файла
# @does  include_file либо ошибка use_target; строка use внутри
# @does  определения — «use внутри определения»; прочие строки идут
# @does  в объединённый текст, состояние определения ведут
# @does  opens_definition и closes_definition.
# @depends find_outside_quotes, split_words, use_target, include_file,
# @depends opens_definition, closes_definition, loader_fail
def source_line(loader, base_dir, raw):
    if loader["error"] is not None:
        return
    line_no = len(loader["lines"]) + 1
    cut = find_outside_quotes(raw, ";")
    tail = cut >= 0
    head = raw if cut < 0 else raw[:cut]
    tokens = split_words(head)
    if tokens and tokens[0] == USE_KEYWORD:
        if loader["in_def"]:
            loader_fail(loader, line_no, "use внутри определения")
            return
        name, error = use_target(tokens)
        if error is not None:
            loader_fail(loader, line_no, error)
            return
        include_file(loader, base_dir, name, line_no)
        return
    loader["lines"].append(raw)
    if opens_definition(tokens, loader["in_def"]):
        loader["in_def"] = True
    if closes_definition(tokens, tail, loader["in_def"]):
        loader["in_def"] = False


# @method file_lines(text) -> list
# @in    text: str — текст включаемого файла
# @out   lines: list — строки файла без артефакта концевого перевода
# @does  Делит текст файла на строки (split_lines): концевой перевод
# @does  строки файла — конец последней строки, не пустая строка
# @does  после неё; пустой файл — ноль строк.
# @depends split_lines
def file_lines(text):
    if not text:
        return []
    lines = split_lines(text)
    if text.endswith("\n"):
        return lines[:-1]
    return lines


# @method include_file(loader, base_dir, name, line_no) -> None
# @in    loader: dict — состояние загрузчика
# @in    base_dir: str — каталог включающего файла
# @in    name: str — имя файла из строки use
# @in    line_no: int — сквозной номер строки use
# @out   нет; строки включённого файла встают на место строки use;
# @out   ошибка — error
# @does  Включает файл (SPEC, раздел 3, v0.3): путь — use_path; цикл —
# @does  «циклический use X»; нечитаемый файл — «не читается use-файл
# @does  X»; строки файла (file_lines) обрабатывает source_line
# @does  с базой — каталогом включённого файла (его use-пути
# @does  относительны ему).
# @depends use_path, in_cycle, read_file_text, file_lines, source_line,
# @depends loader_fail
def include_file(loader, base_dir, name, line_no):
    path = use_path(base_dir, name)
    absolute = os.path.abspath(path)
    if in_cycle(loader, absolute):
        loader_fail(loader, line_no, "циклический use " + name)
        return
    text = read_file_text(path)
    if text is None:
        loader_fail(loader, line_no, "не читается use-файл " + name)
        return
    loader["stack"].append(absolute)
    for raw in file_lines(text):
        if loader["error"] is not None:
            break
        source_line(loader, os.path.dirname(absolute) or ".", raw)
    loader["stack"].pop()


# @method resolve_uses(base_path, text) -> tuple
# @in    base_path: str — путь главного исходника (каталог — база его
# @in    use-путей)
# @in    text: str — текст главного исходника
# @out   pair: tuple — (объединённый текст, None) либо (None, «uBrick:
# @out   строка N: текст»)
# @does  Склеивает многофайловый исходник (SPEC, раздел 3, v0.3):
# @does  строки use заменяются строками включённых файлов, нумерация
# @does  строк объединённого текста сквозная; текст без use-строк
# @does  возвращается неизменным (round-trip split_lines точен,
# @does  концевые CR строк снимаются как в разборе). Главный файл
# @does  кладётся в стек включений: возврат к нему — цикл.
# @depends new_loader, split_lines, source_line
def resolve_uses(base_path, text):
    loader = new_loader()
    loader["stack"].append(os.path.abspath(base_path))
    base_dir = os.path.dirname(os.path.abspath(base_path)) or "."
    for raw in split_lines(text):
        if loader["error"] is not None:
            break
        source_line(loader, base_dir, raw)
    if loader["error"] is not None:
        return None, loader["error"]
    return "\n".join(loader["lines"]), None
