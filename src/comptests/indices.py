import hashlib
import os
from functools import lru_cache
from typing import Any, Callable

__all__ = [
    "accept",
    "accept_test_string",
    "accept_tst_on_this_worker",
    "get_test_index",
]

ENV_COMPTESTS_HASH = "Z_COMPTESTS_HASH"


@lru_cache(None)
def get_prefix() -> bytes:
    if ENV_COMPTESTS_HASH in os.environ:
        return os.environ[ENV_COMPTESTS_HASH].encode()
    else:
        return b""


def int_from_string(s: str) -> int:
    m = hashlib.md5()
    m.update(s.encode())
    d = m.digest()
    b = d[-4:]
    return int.from_bytes(b, "big")


@lru_cache(None)
def get_test_index() -> tuple[int, int]:
    """Returns i,n: machine index and mcdp_comp_tests"""
    n = int(os.environ.get("CIRCLE_NODE_TOTAL", 1))
    i = int(os.environ.get("CIRCLE_NODE_INDEX", 0))
    # logger.info(worker=i, total=n)
    return i, n


def accept(f: Callable[..., Any], worker_i: int, worker_n: int) -> bool:
    return accept_test_string(f.__name__, worker_i, worker_n)


def accept_test_string(s: str, worker_i: int, worker_n: int) -> bool:
    x = int_from_string(s)

    return x % worker_n == worker_i


def accept_tst_on_this_worker(s: str) -> bool:
    """Use this from outside."""
    worker_i, worker_n = get_test_index()
    return accept_test_string(s, worker_i, worker_n)
