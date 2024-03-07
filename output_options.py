import enum


class OutputOptions(enum.IntEnum):
    Telegraph = 1
    PDF = 2

    def __and__(self, other):
        return self.value & other

    def __xor__(self, other):
        return self.value ^ other

    def __or__(self, other):
        return self.value | other
