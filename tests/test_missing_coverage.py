import coverup
from coverup import CodeSegment
from pathlib import Path
import pytest


class mockfs:
    """Mocks the built-in open() function"""

    def __init__(self, files: dict):
        self.files = files

    def __enter__(self):
        import unittest.mock as mock

        def _open(filename, mode="r"):
            if filename not in self.files: raise FileNotFoundError(filename)
            return mock.mock_open(read_data=self.files[filename]).return_value

        self.mock = mock.patch('builtins.open', new=_open)
        self.mock.__enter__()
        return self

    def __exit__(self, *args):
        self.mock.__exit__(*args)


somecode_py = (Path("tests") / "somecode.py").read_text()
somecode_json = """
{
    "files": {
        "tests/somecode.py": {
            "executed_lines": [
                3, 4, 6, 9, 20, 21, 25, 27, 29, 38, 39, 40
            ],
            "missing_lines": [
                7, 10, 12, 13, 15, 16, 18, 23, 32, 34, 36
            ],
            "executed_branches": [
                [38, 39]
            ],
            "missing_branches": [
                [12, 13], [12, 15], [38, 0]
            ]
        }
    }
}
"""


def test_basic():
    with mockfs({"tests/somecode.py": somecode_py,
                 "tests/somecode.json": somecode_json}):
        segs = coverup.get_missing_coverage('tests/somecode.json', line_limit=2)

        assert all([Path(seg.filename).name == 'somecode.py' for seg in segs])
        seg_names = [seg.name for seg in segs]
        assert ['__init__', 'foo', 'bar', 'globalDef2'] == seg_names

        bar = segs[seg_names.index('bar')]
        assert bar.begin == 20 # decorator line
        assert '@staticmethod' in bar.get_excerpt(), "Decorator missing"

        for seg in segs:
            for l in seg.missing_lines:
                assert seg.begin <= l <= seg.end

def test_coarse():
    with mockfs({"tests/somecode.py": somecode_py,
                 "tests/somecode.json": somecode_json}):
        segs = coverup.get_missing_coverage('tests/somecode.json', line_limit=100)

        assert all([Path(seg.filename).name == 'somecode.py' for seg in segs])
        seg_names = [seg.name for seg in segs]
        assert ['SomeCode', 'globalDef2'] == seg_names

        assert segs[seg_names.index('SomeCode')].begin == 3 # entire class?
        assert segs[seg_names.index('SomeCode')].end == 24  # entire class?

        for seg in segs:
            for l in seg.missing_lines:
                assert seg.begin <= l <= seg.end


def test_no_branch_coverage():
    somecode_json_no_branch = """
{
    "files": {
        "tests/somecode.py": {
            "executed_lines": [
                3, 4, 6, 9, 20, 21, 25, 27, 29, 38, 39, 40
            ],
            "missing_lines": [
                7, 10, 12, 13, 15, 16, 18, 23, 32, 34, 36
            ]
        }
    }
}
"""
    with mockfs({"tests/somecode.py": somecode_py,
                 "tests/somecode.json": somecode_json_no_branch}):
        segs = coverup.get_missing_coverage('tests/somecode.json', line_limit=2)

        assert all([Path(seg.filename).name == 'somecode.py' for seg in segs])
        assert ['__init__', 'foo', 'bar', 'globalDef2'] == [seg.name for seg in segs]


def test_all_missing():
    somecode_json = """
{
    "files": {
        "tests/somecode.py": {
            "executed_lines": [
            ],
            "missing_lines": [
                3, 4, 6, 9, 20, 21, 25, 27, 29, 38, 39, 40,
                7, 10, 12, 13, 15, 16, 18, 23, 32, 34, 36
            ]
        }
    }
}
"""

    with mockfs({"tests/somecode.py": somecode_py,
                 "tests/somecode.json": somecode_json}):
        segs = coverup.get_missing_coverage('tests/somecode.json', line_limit=3)

#        print("\n".join(str(s) for s in segs))

        assert all([Path(seg.filename).name == 'somecode.py' for seg in segs])
        assert ['SomeCode', '__init__', 'foo', 'bar', 'globalDef', 'globalDef2'] == [seg.name for seg in segs]

        for i in range(1, len(segs)):
            assert segs[i-1].end <= segs[i].begin     # no overlaps

        # FIXME global statements missing... how to best capture them?


def test_class_excludes_decorator_of_function_if_at_limit():
    code_py = """
class Foo:
    x = 0

    @staticmethod
    def foo():
        pass
""".lstrip()

    code_json = """
{
    "files": {
        "code.py": {
            "executed_lines": [
            ],
            "missing_lines": [
                1, 2, 4, 5, 6
            ]
        }
    }
}
"""
    with mockfs({"code.py": code_py, "code.json": code_json}):
        segs = coverup.get_missing_coverage('code.json', line_limit=4)

        print("\n".join(str(s) for s in segs))

        assert ['Foo', 'foo'] == [seg.name for seg in segs]
        assert segs[0].begin == 1
        assert segs[0].end <= 4 # shouldn't include "@staticmethod"
        assert segs[0].missing_lines == {1,2}


def test_class_statements_after_methods():
    code_py = """
class Foo:
    @staticmethod
    def foo():
        pass

    x = 0
    y = 1

    def bar():
        pass
""".lstrip()

    code_json = """
{
    "files": {
        "code.py": {
            "executed_lines": [
            ],
            "missing_lines": [
                1, 2, 3, 4, 6, 7, 9, 10
            ]
        }
    }
}
"""
    with mockfs({"code.py": code_py, "code.json": code_json}):
        segs = coverup.get_missing_coverage('code.json', line_limit=4)

        print("\n".join(str(s) for s in segs))

        for seg in segs:
            for l in seg.missing_lines:
                assert seg.begin <= l <= seg.end