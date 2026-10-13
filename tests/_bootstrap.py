import datetime as real_datetime
import importlib.util
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CONTRACT_PATH = os.path.join(ROOT, "contracts", "citecheck.py")

if HERE not in sys.path:
    sys.path.insert(0, HERE)

import genlayer_stub  # noqa: E402

sys.modules["genlayer"] = genlayer_stub


class Clock:
    t = 1_700_000_000


class _FakeDatetime:
    @staticmethod
    def now(tz=None):
        return real_datetime.datetime.fromtimestamp(Clock.t)


_fake_datetime_module = types.SimpleNamespace(datetime=_FakeDatetime)


def load_contract():
    spec = importlib.util.spec_from_file_location("citecheck_under_test", CONTRACT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.datetime = _fake_datetime_module
    return module
