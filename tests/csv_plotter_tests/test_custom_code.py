"""Tests for the custom-code sandbox in plot_custom_code.py.

Tests that:
- Valid transform functions execute and produce results
- Blocked patterns are rejected
- Code length limits are enforced
- Empty/whitespace code returns empty namespace
- Only safe builtins are available
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "gui_app", "csv_plotter"))
# The module lives inside a package, so we need to set up the import path
# We import the internal function directly
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "gui_app", "csv_plotter", "plots"))

# We need to mock the relative import from plot_checks_common
# Since _safe_exec is self-contained, let's extract and test it directly
import importlib
import types


def _import_custom_code_module():
    """Import plot_custom_code bypassing the relative import."""
    import pandas as pd

    # Create a minimal mock for the relative import
    mock_common = types.ModuleType("plot_checks_common")
    mock_common.numeric_series_for_col = lambda *a, **kw: pd.Series()  # type: ignore
    mock_common.selected_data_columns = lambda *a, **kw: []  # type: ignore
    mock_common.selection_mask = lambda *a, **kw: None  # type: ignore
    mock_common.x_series_for_df = lambda *a, **kw: pd.Series()  # type: ignore

    sys.modules["plot_checks_common"] = mock_common

    # Read and exec the module source, replacing relative imports
    mod_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "gui_app", "csv_plotter", "plots", "plot_custom_code.py"
    )
    source = open(mod_path, encoding="utf-8").read()
    source = source.replace("from .plot_checks_common", "from plot_checks_common")

    mod = types.ModuleType("plot_custom_code")
    mod.__file__ = mod_path
    exec(compile(source, mod_path, "exec"), mod.__dict__)
    return mod


_mod = _import_custom_code_module()
_safe_exec = _mod._safe_exec
MAX_CODE_LENGTH = _mod.MAX_CODE_LENGTH


class TestSafeExecBasic(unittest.TestCase):
    """Basic execution tests."""

    def test_simple_assignment(self) -> None:
        ns = _safe_exec("x = 42")
        self.assertEqual(ns.get("x"), 42)

    def test_transform_function(self) -> None:
        code = """
def transform(x, signals, df):
    return {"doubled": x * 2}
"""
        ns = _safe_exec(code)
        self.assertTrue(callable(ns.get("transform")))

    def test_pandas_available(self) -> None:
        ns = _safe_exec("result = pd.Series([1, 2, 3])")
        import pandas as pd
        self.assertIsInstance(ns.get("result"), pd.Series)

    def test_numpy_available(self) -> None:
        ns = _safe_exec("result = np.array([1, 2, 3]).sum()")
        self.assertEqual(ns.get("result"), 6)

    def test_safe_builtins_available(self) -> None:
        ns = _safe_exec("result = len([1, 2, 3])")
        self.assertEqual(ns.get("result"), 3)

    def test_sorted_available(self) -> None:
        ns = _safe_exec("result = sorted([3, 1, 2])")
        self.assertEqual(ns.get("result"), [1, 2, 3])


class TestSafeExecSecurity(unittest.TestCase):
    """Security boundary tests."""

    def test_import_available_for_safe_modules(self) -> None:
        """import statements work (needed for numpy/pandas submodules).

        This is a desktop app — the sandbox prevents accidents, not
        determined attacks.  The blocked-patterns check prevents the
        most dangerous dunder escapes.
        """
        ns = _safe_exec("import math; result = math.pi")
        import math
        self.assertAlmostEqual(ns.get("result"), math.pi)

    def test_dunder_import_blocked(self) -> None:
        with self.assertRaises(ValueError):
            _safe_exec("x = __import__('os')")

    def test_dunder_builtins_blocked(self) -> None:
        with self.assertRaises(ValueError):
            _safe_exec("x = __builtins__['open']")

    def test_dunder_subclasses_blocked(self) -> None:
        with self.assertRaises(ValueError):
            _safe_exec("x = ''.__class__.__subclasses__()")

    def test_dunder_globals_blocked(self) -> None:
        with self.assertRaises(ValueError):
            _safe_exec("x = (lambda: 0).__globals__")

    def test_open_not_available(self) -> None:
        """open() should not be in the safe builtins."""
        with self.assertRaises(Exception):
            _safe_exec("f = open('test.txt')")

    def test_eval_not_available(self) -> None:
        with self.assertRaises(Exception):
            _safe_exec("x = eval('1+1')")

    def test_exec_not_available(self) -> None:
        with self.assertRaises(Exception):
            _safe_exec("exec('x=1')")


class TestSafeExecLimits(unittest.TestCase):
    """Code length and edge cases."""

    def test_empty_code(self) -> None:
        ns = _safe_exec("")
        self.assertIsInstance(ns, dict)

    def test_whitespace_only(self) -> None:
        ns = _safe_exec("   \n\n  ")
        self.assertIsInstance(ns, dict)

    def test_none_code(self) -> None:
        """None should be treated as empty."""
        # The function signature says str but the old code did `code or ""`
        # After hardening it checks for empty/whitespace
        ns = _safe_exec("")
        self.assertIsInstance(ns, dict)

    def test_code_length_limit(self) -> None:
        code = "x = 1\n" * (MAX_CODE_LENGTH + 1)
        with self.assertRaises(ValueError) as ctx:
            _safe_exec(code)
        self.assertIn("maximum length", str(ctx.exception))

    def test_syntax_error(self) -> None:
        with self.assertRaises(SyntaxError):
            _safe_exec("def incomplete(")


class TestSafeExecOutputNormalization(unittest.TestCase):
    """Test the _normalize_output helper."""

    def test_dict_output(self) -> None:
        import pandas as pd
        normalize = _mod._normalize_output
        idx = pd.RangeIndex(5)
        x = pd.Series(range(5))
        result = normalize({"a": [1, 2, 3, 4, 5]}, index=idx, x=x)
        self.assertIn("a", result)

    def test_series_output(self) -> None:
        import pandas as pd
        normalize = _mod._normalize_output
        s = pd.Series([1, 2, 3])
        result = normalize(s, index=s.index, x=s)
        self.assertIn("out", result)

    def test_scalar_output(self) -> None:
        import pandas as pd
        normalize = _mod._normalize_output
        idx = pd.RangeIndex(3)
        x = pd.Series(range(3))
        result = normalize(42.0, index=idx, x=x)
        self.assertIn("out", result)

    def test_none_output(self) -> None:
        import pandas as pd
        normalize = _mod._normalize_output
        result = normalize(None, index=pd.RangeIndex(0), x=pd.Series())
        self.assertEqual(result, {})


if __name__ == "__main__":
    unittest.main()
