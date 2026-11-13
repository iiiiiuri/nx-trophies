import unittest

from _path import ensure_path

ensure_path()

from sa_core.expr import MISSING, Context, ExprError, eval_condition, eval_value, split_path  # noqa: E402

DOC = {
    "sections": {
        "base": {"data": {"flags": 0b1011, "items": [5, 0, 7], "ok": True}},
    }
}
ALIASES = {"base": "sections.base.data"}


def ctx() -> Context:
    return Context(DOC, ALIASES)


class SplitPathTest(unittest.TestCase):
    def test_keys_and_indices(self):
        self.assertEqual(split_path("a.b[2].c[0x10]"), ["a", "b", 2, "c", 16])

    def test_rejects_garbage(self):
        for bad in ("", "a..b", "a[x]", "a[1"):
            with self.subTest(bad=bad), self.assertRaises(ExprError):
                split_path(bad)


class ValueTest(unittest.TestCase):
    def test_alias_and_index(self):
        self.assertEqual(eval_value("base.items[2]", ctx()), 7)

    def test_length(self):
        self.assertEqual(eval_value("base.items.length", ctx()), 3)

    def test_bool_becomes_int(self):
        self.assertEqual(eval_value("base.ok", ctx()), 1)

    def test_missing_is_tracked(self):
        c = ctx()
        self.assertIs(eval_value("base.nope", c), MISSING)
        self.assertIs(eval_value("base.items[9]", c), MISSING)
        self.assertEqual(c.missing_paths, {"base.nope", "base.items[9]"})

    def test_popcount_sum_div(self):
        self.assertEqual(eval_value({"popcount": {"value": "base.flags", "mask": "0x3"}}, ctx()), 2)
        self.assertEqual(eval_value({"sum": ["base.items[0]", "base.items[2]", 1]}, ctx()), 13)
        self.assertEqual(eval_value({"div": ["base.items[2]", 2]}, ctx()), 3)
        self.assertIs(eval_value({"div": ["base.items[2]", 0]}, ctx()), MISSING)

    def test_sum_range_bounds(self):
        self.assertEqual(eval_value({"sum_range": {"path": "base.items", "from": 0, "to": 2}}, ctx()), 12)
        self.assertIs(eval_value({"sum_range": {"path": "base.items", "from": 0, "to": 3}}, ctx()), MISSING)

    def test_unknown_operator(self):
        with self.assertRaises(ExprError):
            eval_value({"exec": "rm -rf"}, ctx())


class ConditionTest(unittest.TestCase):
    def test_bit_operators(self):
        self.assertTrue(eval_condition({"value": "base.flags", "op": "has_all", "rhs": "0b1010"}, ctx()))
        self.assertFalse(eval_condition({"value": "base.flags", "op": "has_all", "rhs": "0x4"}, ctx()))
        self.assertTrue(eval_condition({"value": "base.flags", "op": "has_any", "rhs": "0x6"}, ctx()))

    def test_groups(self):
        yes = {"value": "base.items[0]", "op": "==", "rhs": 5}
        no = {"value": "base.items[1]", "op": ">", "rhs": 0}
        self.assertTrue(eval_condition({"any": [no, yes]}, ctx()))
        self.assertFalse(eval_condition({"all": [no, yes]}, ctx()))
        self.assertTrue(eval_condition({"not": no}, ctx()))

    def test_missing_value_is_false_even_with_not_equal(self):
        self.assertFalse(eval_condition({"value": "base.ghost", "op": "!=", "rhs": 0}, ctx()))


if __name__ == "__main__":
    unittest.main()
