# -*- coding: utf-8 -*-
from typing import Sequence, Set

__all__ = [
    'Skipped',
    'PartiallySkipped',
]


class Skipped(object):
    """
        Can be returned by mcdp_lang_tests to mean that the test
        was skipped for some reason.
    """
    reason: str

    def __init__(self, reason: str):
        self.reason = reason

    def get_reason(self):
        return self.reason


class PartiallySkipped(object):
    """
        Can be returned to mean that some parts of the test
        were skipped.
    """

    skipped: Set[str]

    def __init__(self, skipped: Sequence[str]):
        self.skipped = set(skipped)

    def get_skipped_parts(self):
        return self.skipped
