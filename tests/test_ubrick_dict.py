# @uadro
# @file    tests/test_ubrick_dict.py
# @layer   T0
# @branch  t0.ubrick.dict
# @desc    Тесты словаря uBrick v0.4: примитивы, псевдонимы, производные
# @desc    слова, конструкции, поиск по имени и списки слов
# @desc    (SPEC/L3-UBRICK.txt, разделы 4-5).

"""Тесты ветви t0.ubrick.dict (tools/ubrick_dict.py).

Золотые списки повторяют SPEC/L3-UBRICK.txt (разделы 4-5): любое
расхождение словаря со спецификацией ловится здесь. Примитивы
сверяются и с таблицей опкодов UVM (ветвь t0.uvm.table): мнемоника
существует и не имеет поля imm64.

Тела производных слов — пока чистые данные без исполнителя, поэтому
проверяются структурно (SPEC, раздел 4.2: «тесты проверяют поведение,
а не байты тел» — поведение появится с ветвями t0.ubrick.compile
и t0.ubrick.build): каждое слово тела — примитив, псевдоним,
производная, конструкция или числовой литерал диапазона uAsm (ветвь
t0.uasm.lex); тела lts и prints зафиксированы SPEC дословно.

Запуск из корня репозитория:
    python -m unittest discover -s tests -t . -v
"""

import unittest

from tools import uasm_lex
from tools import uvm_table
from tools.ubrick_dict import (
    CONSTRUCTS,
    alias_names,
    derived_body,
    derived_names,
    find_word,
    is_construct,
    primitive_instr,
    primitive_names,
    word_names,
)

GOLDEN_PRIMITIVES = (
    "NOP", "DROP", "DUP", "SWAP", "OVER", "ROT",
    "LOAD8", "LOAD64", "STORE8", "STORE64",
    "ADD", "SUB", "MUL", "UDIV", "UMOD", "NEG",
    "SHL", "SHR", "SAR", "AND", "OR", "XOR", "INV",
    "EQ", "NEQ", "LTU", "GTU", "LEU", "GEU",
)

GOLDEN_ALIASES = (
    ("EMIT", "SYS 1"),
    ("KEY", "SYS 0"),
    ("EXIT", "RET"),
    ("BYE", "HALT 0"),
    ("QUIT", "HALT 16"),
)

GOLDEN_DERIVED = (
    "not", "inc", "dec", "lts", "les", "gts", "ges", "abs",
    "min", "max", "load16", "load32", "store16", "store32",
    "sext8", "sext16", "sext32", "space", "cr", "prints",
)

GOLDEN_CONSTRUCTS = ("IF", "ELSE", "THEN", "BEGIN", "UNTIL", "AGAIN")

BIAS = "0x8000000000000000"


# @method is_known_token(token) -> bool
# @in    token: str — слово из тела производного слова
# @out   flag: bool — True, если слово известно словарю или это литерал
# @does  Проверяет согласованность тела со словарём: каждое слово —
# @does  примитив, псевдоним, производная, конструкция либо числовой
# @does  литерал диапазона uAsm.
# @depends find_word, is_construct, uasm_lex.parse_number, uasm_lex.in_literal_range
def is_known_token(token):
    if find_word(token) is not None or is_construct(token):
        return True
    value = uasm_lex.parse_number(token)
    return value is not None and uasm_lex.in_literal_range(value)


class TestPrimitives(unittest.TestCase):
    """Группа «примитивы» (SPEC, раздел 4.1: 29 мнемоник)."""

    # @method test_count_is_29() -> None
    # @in    нет
    # @out   нет
    # @does  Примитивов ровно 29, как в таблице раздела 4.1 SPEC.
    def test_count_is_29(self):
        self.assertEqual(len(primitive_names()), 29)

    # @method test_names_match_spec() -> None
    # @in    нет
    # @out   нет
    # @does  Набор имён примитивов совпадает с золотым списком SPEC
    # @does  (порядок записей не контракт — сравнение как множеств).
    def test_names_match_spec(self):
        self.assertEqual(sorted(primitive_names()),
                         sorted(GOLDEN_PRIMITIVES))

    # @method test_each_is_uvm_mnemonic_without_imm() -> None
    # @in    нет
    # @out   нет
    # @does  Каждый примитив — существующая мнемоника UVM без поля
    # @does  imm64 (SPEC/L0-UVM.txt, раздел 5; сверка с t0.uvm.table).
    def test_each_is_uvm_mnemonic_without_imm(self):
        for name in primitive_names():
            entry = uvm_table.entry_by_mnemonic(name)
            self.assertIsNotNone(entry, name)
            self.assertFalse(entry[3], name)

    # @method test_instr_equals_name() -> None
    # @in    нет
    # @out   нет
    # @does  Примитив компилируется в одноимённую инструкцию uAsm.
    def test_instr_equals_name(self):
        for name in primitive_names():
            self.assertEqual(primitive_instr(name), name, name)

    # @method test_control_opcodes_are_not_words() -> None
    # @in    нет
    # @out   нет
    # @does  PUSH, PICK и опкоды управления (JMP JZ JNZ CALL RET HALT
    # @does  SYS) словами uBrick не являются (SPEC, раздел 4.1).
    def test_control_opcodes_are_not_words(self):
        for name in ("PUSH", "PICK", "JMP", "JZ", "JNZ",
                     "CALL", "RET", "HALT", "SYS"):
            self.assertIsNone(primitive_instr(name), name)

    # @method test_unknown_and_lowercase_are_none() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестное имя, пустая строка и строчное «add» дают None:
    # @does  регистр значим (SPEC, раздел 3).
    def test_unknown_and_lowercase_are_none(self):
        self.assertIsNone(primitive_instr("foo"))
        self.assertIsNone(primitive_instr("add"))
        self.assertIsNone(primitive_instr(""))


class TestAliases(unittest.TestCase):
    """Группа «псевдонимы» (SPEC, раздел 4.1: 5 имён)."""

    # @method test_count_is_5() -> None
    # @in    нет
    # @out   нет
    # @does  Псевдонимов ровно 5: EMIT, KEY, EXIT, BYE, QUIT.
    def test_count_is_5(self):
        self.assertEqual(len(alias_names()), 5)
        self.assertEqual(sorted(alias_names()),
                         sorted(rec[0] for rec in GOLDEN_ALIASES))

    # @method test_mapping_matches_spec() -> None
    # @in    нет
    # @out   нет
    # @does  Каждый псевдоним даёт свою инструкцию с фиксированным
    # @does  imm точно по таблице раздела 4.1 SPEC.
    def test_mapping_matches_spec(self):
        for name, instr in GOLDEN_ALIASES:
            self.assertEqual(primitive_instr(name), instr, name)

    # @method test_each_mnemonic_is_uvm_opcode() -> None
    # @in    нет
    # @out   нет
    # @does  Мнемоника инструкции каждого псевдонима существует
    # @does  в таблице опкодов UVM (t0.uvm.table).
    def test_each_mnemonic_is_uvm_opcode(self):
        for _, instr in GOLDEN_ALIASES:
            mnemonic = instr.split()[0]
            self.assertIsNotNone(
                uvm_table.entry_by_mnemonic(mnemonic), mnemonic)

    # @method test_lowercase_is_none() -> None
    # @in    нет
    # @out   нет
    # @does  Сточные «emit», «bye», «quit» — не псевдонимы: регистр
    # @does  значим.
    def test_lowercase_is_none(self):
        self.assertIsNone(primitive_instr("emit"))
        self.assertIsNone(primitive_instr("bye"))
        self.assertIsNone(primitive_instr("quit"))


class TestDerived(unittest.TestCase):
    """Группа «производные слова» (SPEC, раздел 4.2: 20 слов)."""

    # @method test_count_is_20() -> None
    # @in    нет
    # @out   нет
    # @does  Производных ровно 20.
    def test_count_is_20(self):
        self.assertEqual(len(derived_names()), 20)

    # @method test_names_in_spec_order() -> None
    # @in    нет
    # @out   нет
    # @does  Имена производных идут в порядке таблицы раздела 4.2
    # @does  SPEC: от not до prints.
    def test_names_in_spec_order(self):
        self.assertEqual(derived_names(), GOLDEN_DERIVED)

    # @method test_bodies_are_word_tuples() -> None
    # @in    нет
    # @out   нет
    # @does  Тело каждого производного слова — непустой кортеж
    # @does  непустых строк без пробелов внутри слов.
    def test_bodies_are_word_tuples(self):
        for name in derived_names():
            body = derived_body(name)
            self.assertTrue(body, name)
            for token in body:
                self.assertIsInstance(token, str, name)
                self.assertTrue(token, name)
                self.assertNotEqual(token.strip(), "", name)
                self.assertEqual(token, token.strip(), name)

    # @method test_every_token_is_known() -> None
    # @in    нет
    # @out   нет
    # @does  Каждое слово каждого тела — примитив, псевдоним,
    # @does  производная, конструкция или литерал uAsm диапазона
    # @does  (словарь внутренне согласован).
    def test_every_token_is_known(self):
        for name in derived_names():
            for token in derived_body(name):
                self.assertTrue(is_known_token(token),
                                name + ": " + token)

    # @method test_lts_body_matches_spec() -> None
    # @in    нет
    # @out   нет
    # @does  Тело lts дословно по SPEC (раздел 4.2): биас 2^63
    # @does  обоим операндам, затем LTU.
    def test_lts_body_matches_spec(self):
        self.assertEqual(derived_body("lts"),
                         (BIAS, "XOR", "SWAP",
                          BIAS, "XOR", "SWAP", "LTU"))

    # @method test_sign_comparisons_share_bias_pattern() -> None
    # @in    нет
    # @out   нет
    # @does  lts/les/gts/ges — одна схема с биасом 2^63 и разным
    # @does  беззнаковым сравнением (SPEC, раздел 4.2).
    def test_sign_comparisons_share_bias_pattern(self):
        cases = (("lts", "LTU"), ("les", "LEU"),
                 ("gts", "GTU"), ("ges", "GEU"))
        for name, op in cases:
            self.assertEqual(derived_body(name),
                             (BIAS, "XOR", "SWAP",
                              BIAS, "XOR", "SWAP", op), name)

    # @method test_simple_bodies() -> None
    # @in    нет
    # @out   нет
    # @does  Короткие тела точно по семантике раздела 4.2 SPEC:
    # @does  not, inc, dec, знак-расширения, space, cr.
    def test_simple_bodies(self):
        cases = (
            ("not", ("0", "EQ")),
            ("inc", ("1", "ADD")),
            ("dec", ("1", "SUB")),
            ("sext8", ("56", "SHL", "56", "SAR")),
            ("sext16", ("48", "SHL", "48", "SAR")),
            ("sext32", ("32", "SHL", "32", "SAR")),
            ("space", ("32", "EMIT")),
            ("cr", ("10", "EMIT")),
        )
        for name, body in cases:
            self.assertEqual(derived_body(name), body, name)

    # @method test_prints_body_matches_spec() -> None
    # @in    нет
    # @out   нет
    # @does  Тело prints дословно из примера раздела 5 SPEC: цикл
    # @does  BEGIN..AGAIN с проверкой байта 0 и выходом EXIT.
    def test_prints_body_matches_spec(self):
        self.assertEqual(
            derived_body("prints"),
            ("BEGIN", "DUP", "LOAD8", "DUP", "0", "EQ",
             "IF", "DROP", "DROP", "EXIT", "THEN",
             "EMIT", "1", "ADD", "AGAIN"))

    # @method test_derived_words_compose() -> None
    # @in    нет
    # @out   нет
    # @does  Производные собираются из производных (SPEC, раздел 4.2):
    # @does  load32 из load16, store32 из store16, min из gts,
    # @does  max из lts, prints из EMIT и EXIT.
    def test_derived_words_compose(self):
        cases = (
            ("load32", "load16"),
            ("store32", "store16"),
            ("min", "gts"),
            ("max", "lts"),
            ("prints", "EMIT"),
            ("prints", "EXIT"),
        )
        for name, part in cases:
            self.assertIn(part, derived_body(name), name)

    # @method test_memory_bodies_use_load8_store8() -> None
    # @in    нет
    # @out   нет
    # @does  Узкие обращения к памяти собраны из LOAD8/STORE64-этажа
    # @does  UVM: load16 и store16 содержат LOAD8/STORE8, load32
    # @does  и store32 — только производные и литералы сдвигов.
    def test_memory_bodies_use_load8_store8(self):
        self.assertIn("LOAD8", derived_body("load16"))
        self.assertIn("STORE8", derived_body("store16"))
        self.assertNotIn("LOAD64", derived_body("load16"))
        self.assertNotIn("STORE64", derived_body("store16"))


class TestFind(unittest.TestCase):
    """Поиск слова по имени (SPEC, разделы 4.1-4.2)."""

    # @method test_find_primitive() -> None
    # @in    нет
    # @out   нет
    # @does  Примитив находится с видом "prim" и своей инструкцией.
    def test_find_primitive(self):
        self.assertEqual(find_word("NOP"), ("prim", "NOP"))
        self.assertEqual(find_word("ADD"), ("prim", "ADD"))

    # @method test_find_alias() -> None
    # @in    нет
    # @out   нет
    # @does  Псевдоним находится с видом "alias" и инструкцией
    # @does  с фиксированным imm.
    def test_find_alias(self):
        self.assertEqual(find_word("EMIT"), ("alias", "SYS 1"))
        self.assertEqual(find_word("BYE"), ("alias", "HALT 0"))
        self.assertEqual(find_word("QUIT"), ("alias", "HALT 16"))

    # @method test_find_derived() -> None
    # @in    нет
    # @out   нет
    # @does  Производное слово находится с видом "derived" и телом.
    def test_find_derived(self):
        self.assertEqual(find_word("not"), ("derived", ("0", "EQ")))

    # @method test_find_unknown() -> None
    # @in    нет
    # @out   нет
    # @does  Неизвестное имя, строчная мнемоника, пустая строка
    # @does  и конструкция дают None: конструкции — не слова словаря.
    def test_find_unknown(self):
        self.assertIsNone(find_word("foo"))
        self.assertIsNone(find_word("add"))
        self.assertIsNone(find_word(""))
        self.assertIsNone(find_word("IF"))

    # @method test_primitive_instr_covers_aliases() -> None
    # @in    нет
    # @out   нет
    # @does  Один кирпич primitive_instr закрывает и примитивы,
    # @does  и псевдонимы (SPEC, раздел 4.1, «включая псевдонимы»).
    def test_primitive_instr_covers_aliases(self):
        self.assertEqual(primitive_instr("EXIT"), "RET")
        self.assertEqual(primitive_instr("KEY"), "SYS 0")


class TestLists(unittest.TestCase):
    """Списки слов словаря (SPEC, разделы 4.1-4.2)."""

    # @method test_word_names_count_and_unique() -> None
    # @in    нет
    # @out   нет
    # @does  Всего 54 слова (29 + 5 + 20), без повторов.
    def test_word_names_count_and_unique(self):
        names = word_names()
        self.assertEqual(len(names), 54)
        self.assertEqual(len(set(names)), 54)

    # @method test_word_names_order() -> None
    # @in    нет
    # @out   нет
    # @does  Порядок списка: примитивы, затем псевдонимы, затем
    # @does  производные; состав совпадает с золотыми списками SPEC.
    def test_word_names_order(self):
        golden = (tuple(GOLDEN_PRIMITIVES)
                  + tuple(rec[0] for rec in GOLDEN_ALIASES)
                  + tuple(GOLDEN_DERIVED))
        self.assertEqual(word_names(), golden)

    # @method test_group_lists_are_stable() -> None
    # @in    нет
    # @out   нет
    # @does  Списки групп не меняются между вызовами и не пересекаются.
    def test_group_lists_are_stable(self):
        self.assertEqual(primitive_names(), primitive_names())
        self.assertEqual(alias_names(), alias_names())
        self.assertEqual(derived_names(), derived_names())
        groups = primitive_names(), alias_names(), derived_names()
        self.assertFalse(set(groups[0]) & set(groups[1]))
        self.assertFalse(set(groups[0]) & set(groups[2]))
        self.assertFalse(set(groups[1]) & set(groups[2]))


class TestConstructs(unittest.TestCase):
    """Управляющие конструкции (SPEC, раздел 5: 6 имён)."""

    # @method test_constructs_match_spec() -> None
    # @in    нет
    # @out   нет
    # @does  Конструкции ровно шесть и точно по разделу 5 SPEC.
    def test_constructs_match_spec(self):
        self.assertEqual(tuple(CONSTRUCTS), GOLDEN_CONSTRUCTS)

    # @method test_is_construct() -> None
    # @in    нет
    # @out   нет
    # @does  Каждая конструкция распознаётся; строчная «if» — нет
    # @does  (регистр значим).
    def test_is_construct(self):
        for name in GOLDEN_CONSTRUCTS:
            self.assertTrue(is_construct(name), name)
        self.assertFalse(is_construct("if"))
        self.assertFalse(is_construct("begin"))

    # @method test_words_are_not_constructs() -> None
    # @in    нет
    # @out   нет
    # @does  Примитив, псевдоним и производная — не конструкции;
    # @does  пустая строка и None — тоже.
    def test_words_are_not_constructs(self):
        self.assertFalse(is_construct("NOP"))
        self.assertFalse(is_construct("EMIT"))
        self.assertFalse(is_construct("not"))
        self.assertFalse(is_construct(""))
        self.assertFalse(is_construct("main"))


if __name__ == "__main__":
    unittest.main()
