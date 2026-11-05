# @uadro
# @file    tests/test_ubrick_parse_errors.py
# @layer   T0
# @branch  t0.ubrick.parse
# @desc    Тесты текстов ошибок разбора uBrick с номерами строк: имена,
# @desc    литералы, var/text, правила «;», конструкции, контекст,
# @desc    конец текста и порядок ошибок (SPEC/L3-UBRICK.txt v0.2,
# @desc    раздел 8).

"""Тесты ошибок ветви t0.ubrick.parse (tools/ubrick_parse.py).

Каждый текст ошибок раздела 8 SPEC v0.2 покрыт, включая новую
«незакрытое определение X». Порядок ошибок (v0.2): структурные —
по ходу разбора первыми; «неизвестное слово» и «слово main
обязательно» — по безошибочному исходнику, в порядке следования.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tools.ubrick_parse import parse_ubrk


# @method parse_error(source) -> str
# @in    source: str — текст uBrick
# @out   msg: str — сообщение ошибки разбора
# @does  Разбирает текст, который обязан содержать ошибку, и возвращает
# @does  её сообщение.
# @depends parse_ubrk
def parse_error(source):
    records, error = parse_ubrk(source)
    assert records is None
    return error


class TestNameErrors(unittest.TestCase):
    """Ошибки имён (SPEC, раздел 8): занято, плохое, повторное."""

    # @method test_name_taken() -> None
    # @in    нет
    # @out   нет
    # @does  Примитив, псевдоним, конструкция и ключевые слова var/text
    # @does  заняты — в том числе как имена var и text (v0.2).
    def test_name_taken(self):
        self.assertEqual(parse_error(": NOP 1 ;"),
                         "uBrick: строка 1: имя занято NOP")
        self.assertEqual(parse_error(": IF 1 ;"),
                         "uBrick: строка 1: имя занято IF")
        self.assertEqual(parse_error(": EMIT 1 ;"),
                         "uBrick: строка 1: имя занято EMIT")
        self.assertEqual(parse_error(": var 1 ;"),
                         "uBrick: строка 1: имя занято var")
        self.assertEqual(parse_error(": text 1 ;"),
                         "uBrick: строка 1: имя занято text")
        self.assertEqual(parse_error("var IF"),
                         "uBrick: строка 1: имя занято IF")
        self.assertEqual(parse_error('text NOP "a"'),
                         "uBrick: строка 1: имя занято NOP")

    # @method test_bad_name() -> None
    # @in    нет
    # @out   нет
    # @does  Правило имён [a-z][a-z0-9]*: заглавная, цифра в начале,
    # @does  дефис, подчёркивание и «;» как имя-кандидат — плохие имена.
    def test_bad_name(self):
        for name in ("Foo", "1bad", "_x", "bad-name", "a_b"):
            self.assertEqual(parse_error(": " + name + " ;"),
                             "uBrick: строка 1: плохое имя " + name)
        self.assertEqual(parse_error(": ;"),
                         "uBrick: строка 1: плохое имя ;")
        self.assertEqual(parse_error("var 1x"),
                         "uBrick: строка 1: плохое имя 1x")
        self.assertEqual(parse_error('text Foo "a"'),
                         "uBrick: строка 1: плохое имя Foo")

    # @method test_duplicate_definition() -> None
    # @in    нет
    # @out   нет
    # @does  Повторное определение: производная словаря, слово, main,
    # @does  var, text — общий пул имён (SPEC, раздел 8).
    def test_duplicate_definition(self):
        self.assertEqual(parse_error(": not 1 ;"),
                         "uBrick: строка 1: повторное определение слова not")
        self.assertEqual(parse_error(": main 1 ;\n: main 2 ;"),
                         "uBrick: строка 2: повторное определение слова main")
        self.assertEqual(parse_error("var x\nvar x"),
                         "uBrick: строка 2: повторное определение слова x")
        self.assertEqual(parse_error(": x 1 ;\nvar x"),
                         "uBrick: строка 2: повторное определение слова x")
        self.assertEqual(parse_error('text m "a"\nvar m'),
                         "uBrick: строка 2: повторное определение слова m")

    # @method test_line_numbers_count_comments() -> None
    # @in    нет
    # @out   нет
    # @does  Номер строки — позиция в исходном тексте: пустые строки
    # @does  и комментарии считаются.
    def test_line_numbers_count_comments(self):
        self.assertEqual(parse_error("\n; комментарий\n: Foo ;"),
                         "uBrick: строка 3: плохое имя Foo")


class TestLiteralErrors(unittest.TestCase):
    """Ошибки литералов тел (SPEC, разделы 3 и 8)."""

    # @method test_bad_literal() -> None
    # @in    нет
    # @out   нет
    # @does  Нераспознанное слово-не-имя — плохой литерал: обрыв 0x,
    # @does  строковый литерал в теле, мусор.
    def test_bad_literal(self):
        self.assertEqual(parse_error(": main 12x ;"),
                         "uBrick: строка 1: плохой литерал 12x")
        self.assertEqual(parse_error(": main 0x ;"),
                         "uBrick: строка 1: плохой литерал 0x")
        self.assertEqual(parse_error(': main "s" ;'),
                         'uBrick: строка 1: плохой литерал "s"')

    # @method test_out_of_range() -> None
    # @in    нет
    # @out   нет
    # @does  Границы -2^63 .. 2^64-1: выход за верхнюю и нижнюю.
    def test_out_of_range(self):
        self.assertEqual(parse_error(": main 18446744073709551616 ;"),
                         "uBrick: строка 1: литерал вне диапазона")
        self.assertEqual(parse_error(": main -9223372036854775809 ;"),
                         "uBrick: строка 1: литерал вне диапазона")


class TestVarTextErrors(unittest.TestCase):
    """Ошибки операторов var и text (SPEC, разделы 3, 6 и 8)."""

    # @method test_var_errors() -> None
    # @in    нет
    # @out   нет
    # @does  «var без имени» и «лишние слова после var».
    def test_var_errors(self):
        self.assertEqual(parse_error("var"),
                         "uBrick: строка 1: var без имени")
        self.assertEqual(parse_error("var x y"),
                         "uBrick: строка 1: лишние слова после var")
        self.assertEqual(parse_error("var x y z"),
                         "uBrick: строка 1: лишние слова после var")

    # @method test_text_errors() -> None
    # @in    нет
    # @out   нет
    # @does  «text без имени», «плохой строковый литерал» (нет, мусор,
    # @does  обрыв, дурной escape) и «лишние слова после text».
    def test_text_errors(self):
        self.assertEqual(parse_error("text"),
                         "uBrick: строка 1: text без имени")
        self.assertEqual(parse_error("text m"),
                         "uBrick: строка 1: плохой строковый литерал")
        self.assertEqual(parse_error("text m abc"),
                         "uBrick: строка 1: плохой строковый литерал")
        self.assertEqual(parse_error('text m "abc'),
                         "uBrick: строка 1: плохой строковый литерал")
        self.assertEqual(parse_error('text m "a\\q"'),
                         "uBrick: строка 1: плохой строковый литерал")
        self.assertEqual(parse_error('text m "a" b'),
                         "uBrick: строка 1: лишние слова после text")
        self.assertEqual(parse_error('text m "a" "b"'),
                         "uBrick: строка 1: лишние слова после text")


class TestSemicolon(unittest.TestCase):
    """Правила «;» (v0.2, раздел 3 SPEC): комментарий и ошибка."""

    # @method test_semicolon_outside_definition() -> None
    # @in    нет
    # @out   нет
    # @does  «;» в середине строки вне определения — ошибка; вне
    # @does  определения комментарий пишется только с начала строки.
    def test_semicolon_outside_definition(self):
        self.assertEqual(parse_error("var x ; примечание"),
                         "uBrick: строка 1: точка с запятой вне определения")
        self.assertEqual(parse_error('text m "a" ; примечание'),
                         "uBrick: строка 1: точка с запятой вне определения")
        self.assertEqual(parse_error(": main 1 ;\nvar y ; c"),
                         "uBrick: строка 2: точка с запятой вне определения")

    # @method test_comment_lines_always_ok() -> None
    # @in    нет
    # @out   нет
    # @does  Строка, начинающаяся с «;», — комментарий в любом
    # @does  контексте: не ошибка и не закрывающее слово.
    def test_comment_lines_always_ok(self):
        records, error = parse_ubrk("; только комментарий\n: main BYE ;")
        self.assertIsNone(error)
        self.assertEqual(records,
                         [("word", "main", (("word", "BYE"),))])


class TestConstructErrors(unittest.TestCase):
    """Ошибки связывания конструкций (SPEC, разделы 5 и 8)."""

    # @method test_unclosed_at_semicolon() -> None
    # @in    нет
    # @out   нет
    # @does  Незакрытые IF и BEGIN к моменту «;»; при нескольких
    # @does  сообщается первая открытая конструкция (v0.2).
    def test_unclosed_at_semicolon(self):
        self.assertEqual(parse_error(": main IF ;"),
                         "uBrick: строка 1: незакрытый IF")
        self.assertEqual(parse_error(": main BEGIN ;"),
                         "uBrick: строка 1: незакрытый BEGIN")
        self.assertEqual(parse_error(": main IF BEGIN ;"),
                         "uBrick: строка 1: незакрытый IF")
        self.assertEqual(parse_error(": main BEGIN IF ;"),
                         "uBrick: строка 1: незакрытый BEGIN")

    # @method test_bad_pairs() -> None
    # @in    нет
    # @out   нет
    # @does  THEN/ELSE без IF, ELSE после ELSE, UNTIL/AGAIN без
    # @does  BEGIN, THEN над BEGIN, UNTIL над IF.
    def test_bad_pairs(self):
        cases = (
            (": main THEN ;", "THEN без IF"),
            (": main ELSE ;", "ELSE без IF"),
            (": main IF ELSE ELSE ;", "ELSE после ELSE"),
            (": main UNTIL ;", "UNTIL без BEGIN"),
            (": main AGAIN ;", "AGAIN без BEGIN"),
            (": main BEGIN THEN ;", "THEN без IF"),
            (": main IF UNTIL ;", "UNTIL без BEGIN"),
        )
        for source, text in cases:
            self.assertEqual(parse_error(source),
                             "uBrick: строка 1: " + text, source)

    # @method test_construct_outside_definition() -> None
    # @in    нет
    # @out   нет
    # @does  Конструкция вне тела «:» — своя ошибка, не «слово вне
    # @does  определения».
    def test_construct_outside_definition(self):
        for name in ("IF", "ELSE", "THEN", "BEGIN", "UNTIL", "AGAIN"):
            self.assertEqual(parse_error(name),
                             "uBrick: строка 1: конструкция вне определения",
                             name)


class TestContextErrors(unittest.TestCase):
    """Ошибки места слов (SPEC, раздел 8): внутри и вне определения."""

    # @method test_keywords_inside_definition() -> None
    # @in    нет
    # @out   нет
    # @does  «:», var и text внутри тела — ошибки своего текста.
    def test_keywords_inside_definition(self):
        self.assertEqual(parse_error(": main : ;"),
                         "uBrick: строка 1: двоеточие внутри определения")
        self.assertEqual(parse_error(": main var ;"),
                         "uBrick: строка 1: var внутри определения")
        self.assertEqual(parse_error(": main text ;"),
                         "uBrick: строка 1: text внутри определения")

    # @method test_word_outside_definition() -> None
    # @in    нет
    # @out   нет
    # @does  Верхний уровень допускает только «:», var и text: прочее
    # @does  слово — ошибка с самим словом.
    def test_word_outside_definition(self):
        self.assertEqual(parse_error("foo"),
                         "uBrick: строка 1: слово вне определения foo")
        self.assertEqual(parse_error("123"),
                         "uBrick: строка 1: слово вне определения 123")
        self.assertEqual(parse_error("NOP"),
                         "uBrick: строка 1: слово вне определения NOP")
        self.assertEqual(parse_error(": main 1 ;\nfoo"),
                         "uBrick: строка 2: слово вне определения foo")


class TestFinalErrors(unittest.TestCase):
    """Ошибки конца текста (SPEC, раздел 8, v0.2)."""

    # @method test_unclosed_definition() -> None
    # @in    нет
    # @out   нет
    # @does  Конец текста при открытом «:»: с именем и без имени;
    # @does  строка-комментарий не закрывает определение.
    def test_unclosed_definition(self):
        self.assertEqual(parse_error(": main 1"),
                         "uBrick: строка 1: незакрытое определение main")
        self.assertEqual(parse_error(":"),
                         "uBrick: строка 1: незакрытое определение без имени")
        self.assertEqual(parse_error(": main 1\n; хвост"),
                         "uBrick: строка 2: незакрытое определение main")

    # @method test_unknown_word() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестное слово назначается после разбора, строкой
    # @does  своего вхождения, первым в порядке следования.
    def test_unknown_word(self):
        self.assertEqual(parse_error(": main zzz ;"),
                         "uBrick: строка 1: неизвестное слово zzz")
        self.assertEqual(parse_error(": a b ; : main c ;"),
                         "uBrick: строка 1: неизвестное слово b")
        self.assertEqual(parse_error(": main zzz aaa ;"),
                         "uBrick: строка 1: неизвестное слово zzz")
        self.assertEqual(parse_error(": main 1 ;\n: x yy ;"),
                         "uBrick: строка 2: неизвестное слово yy")

    # @method test_main_required() -> None
    # @in    нет
    # @out   нет
    # @does  Слово main обязательно и одно: var main его не заменяет;
    # @does  пустой текст — строка 1, обычный — последняя строка.
    def test_main_required(self):
        self.assertEqual(parse_error("var x"),
                         "uBrick: строка 1: слово main обязательно")
        self.assertEqual(parse_error(""),
                         "uBrick: строка 1: слово main обязательно")
        self.assertEqual(parse_error("; только комментарий"),
                         "uBrick: строка 1: слово main обязательно")
        self.assertEqual(parse_error("var main"),
                         "uBrick: строка 1: слово main обязательно")
        self.assertEqual(parse_error(": x 1 ;\nvar y"),
                         "uBrick: строка 2: слово main обязательно")


class TestErrorOrder(unittest.TestCase):
    """Порядок ошибок (v0.2, раздел 8 SPEC)."""

    # @method test_first_structural_wins() -> None
    # @in    нет
    # @out   нет
    # @does  Первая структурная ошибка прекращает разбор: сообщается
    # @does  строка 1, а не строка 2.
    def test_first_structural_wins(self):
        self.assertEqual(parse_error(": Foo ;\n: 1bad ;"),
                         "uBrick: строка 1: плохое имя Foo")

    # @method test_structural_beats_deferred() -> None
    # @in    нет
    # @out   нет
    # @does  Структурная ошибка позже строки с неизвестным словом всё
    # @does  равно сообщается первой: проверка ссылок — в конце.
    def test_structural_beats_deferred(self):
        self.assertEqual(parse_error(": main zzz ;\n: b 12x ;"),
                         "uBrick: строка 2: плохой литерал 12x")

    # @method test_unknown_beats_main() -> None
    # @in    нет
    # @out   нет
    # @does  Среди проверок конца текста сначала идёт «неизвестное
    # @does  слово», затем «слово main обязательно».
    def test_unknown_beats_main(self):
        self.assertEqual(parse_error(": main zzz ;"),
                         "uBrick: строка 1: неизвестное слово zzz")
        self.assertEqual(parse_error(": x yy ;"),
                         "uBrick: строка 1: неизвестное слово yy")


if __name__ == "__main__":
    unittest.main()
