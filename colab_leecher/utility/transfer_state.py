# Correct content for: colab_leecher/utility/transfer_state.py

class SmartBytes(list):
    """
    A list subclass that behaves like a list for downloader operations 
    (supporting .append() and sum()) but also seamlessly behaves like 
    an integer for addition (+=, -=) and comparisons (== 0).
    """
    def __init__(self, value=None):
        if value is None:
            super().__init__()
        elif isinstance(value, (list, tuple, set)):
            super().__init__(value)
        elif isinstance(value, int):
            if value == 0:
                super().__init__()
            else:
                super().__init__([value])
        else:
            super().__init__([value])

    def __eq__(self, other):
        if isinstance(other, int):
            return sum(self) == other
        if isinstance(other, list):
            return list(self) == other
        return super().__eq__(other)

    def __iadd__(self, other):
        if isinstance(other, int):
            if not self:
                self.append(other)
            else:
                self[-1] += other
            return self
        elif isinstance(other, list):
            self.extend(other)
            return self
        return NotImplemented

    def __isub__(self, other):
        if isinstance(other, int):
            if not self:
                self.append(-other)
            else:
                self[-1] -= other
            return self
        elif isinstance(other, list):
            for val in other:
                if not self:
                    self.append(-val)
                else:
                    self[-1] -= val
            return self
        return NotImplemented

    def __add__(self, other):
        if isinstance(other, int):
            return sum(self) + other
        return super().__add__(other)

    def __radd__(self, other):
        if isinstance(other, int):
            return sum(self) + other
        return NotImplemented


class Transfer:
    """Holds state related to file transfer progress and results."""
    def __init__(self):
        self.reset()  # Force instance-level initialization

    def reset(self):
        """Resets the state for a new task."""
        self.down_bytes = SmartBytes(0)
        self.up_bytes = SmartBytes(0)
        self.total_down_size = 0
        self.sent_file = []
        self.sent_file_names = []
        self.successful_downloads = []


AWAITING_UPLOAD_DECISION = "AWAITING_UPLOAD_DECISION"

