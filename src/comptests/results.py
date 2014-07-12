
from contracts import contract

__all__ = [
    'Skipped',
    'PartiallySkipped',
]

class Skipped():
    """ 
        Can be returned by tests to mean that the test
        was skipped for some reason.
    """
    @contract(reason='str')
    def __init__(self, reason):
        self.reason = reason
        
    def get_reason(self):
        return self.reason
        
class PartiallySkipped():
    """
        Can be returned to mean that some parts of the test
        were skipped.
    """
    @contract(skipped='seq(str)')
    def __init__(self, skipped):
        self.skipped = set(skipped)
        
    def get_skipped_parts(self):
        return self.skipped