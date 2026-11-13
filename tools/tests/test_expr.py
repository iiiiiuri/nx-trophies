import unittest

from _path import ensure_path

ensure_path()

from sa_core.expr import MISSING, Context, ExprError, collect_references, eval_condition, eval_value  # noqa: E402

VALUES = {"flags": 0b1011, "a": 5, "b": 0, "c": 7, "ok": True, "text": "x"}


def ctx(counters=None) -> Context:
    return Context(VALUES, counters or {})


class ValueTest(unittest.TestCase):
    def test_variable_lookup(self):
        self.assertEqual(eval_value("c", ctx()), 7)
        self.assertEqual(eval_value({"var": "a"}, ctx()), 5)

    def test_bool_becomes_int_and_non_numbers_are_missing(self):
        self.assertEqual(eval_value("ok", ctx()), 1)
        self.assertIs(eval_value("text", ctx()), MISSING)
        self.assertIs(eval_value("ghost", ctx()), MISSING)

    def test_operators(self):
        self.assertEqual(eval_value({"popcount": {"value": "flags", "mask": "0x3"}}, ctx()), 2)
        self.assertEqual(eval_value({"sum": ["a", "c", 1]}, ctx()), 13)
        self.assertEqual(eval_value({"div": ["c", 2]}, ctx()), 3)
        self.assertIs(eval_value({"div": ["c", 0]}, ctx()), MISSING)
        self.assertEqual(eval_value({"count": "star"}, ctx({"star": 4})), 4)
        self.assertEqual(eval_value({"count": "never"}, ctx()), 0)
        self.assertEqual(eval_value({"truth": {"value": "a", "op": "==", "rhs": 5}}, ctx()), 1)

    def test_unknown_operator(self):
        with self.assertRaises(ExprError):
            eval_value({"exec": "rm -rf"}, ctx())


class ConditionTest(unittest.TestCase):
    def test_bit_operators(self):
        self.assertTrue(eval_condition({"value": "flags", "op": "has_all", "rhs": "0b1010"}, ctx()))
        self.assertFalse(eval_condition({"value": "flags", "op": "has_all", "rhs": "0x4"}, ctx()))
        self.assertTrue(eval_condition({"value": "flags", "op": "has_any", "rhs": "0x6"}, ctx()))

    def test_groups_and_exists(self):
        yes = {"value": "a", "op": "==", "rhs": 5}
        no = {"value": "b", "op": ">", "rhs": 0}
        self.assertTrue(eval_condition({"any": [no, yes]}, ctx()))
        self.assertFalse(eval_condition({"all": [no, yes]}, ctx()))
        self.assertTrue(eval_condition({"not": no}, ctx()))
        self.assertTrue(eval_condition({"exists": "a"}, ctx()))
        self.assertFalse(eval_condition({"exists": "ghost"}, ctx()))

    def test_missing_value_is_false_even_with_not_equal(self):
        self.assertFalse(eval_condition({"value": "ghost", "op": "!=", "rhs": 0}, ctx()))

    def test_collect_references(self):
        refs = collect_references({"all": [
            {"value": {"count": "star"}, "op": ">=", "rhs": 1},
            {"value": {"popcount": {"value": "flags"}}, "op": ">", "rhs": "c"},
            {"exists": "ptr"},
        ]})
        self.assertEqual(refs.events, {"star"})
        self.assertEqual(refs.variables, {"flags", "ptr"})


if __name__ == "__main__":
    unittest.main()
