"""Signal a requested batch stop at a safe processing boundary."""


class BatchStopped(Exception):
    pass
