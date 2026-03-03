import pathlib
import tempfile
import unittest

from pyontrust_gnuradio.runner import RunSpec, build_command


class TestRunnerBuildCommand(unittest.TestCase):
    def test_py_flowgraph(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "fg.py"
            p.write_text("print('hi')\n", encoding="utf-8")
            spec = RunSpec(mode="python", python_exe="python", conda_env="", flowgraph_path=str(p))
            cmd, gen = build_command(spec)
            self.assertIn(str(p), cmd)
            self.assertIsNone(gen)


if __name__ == "__main__":
    unittest.main()
