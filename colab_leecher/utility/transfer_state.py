# Correct content for: colab_leecher/utility/transfer_state.py

class Transfer:
    """Holds state related to file transfer progress and results."""
    def __init__(self):
        self.reset()  # Force instance-level initialization

    def reset(self):
        """Resets the state for a new task."""
        self.down_bytes = 0
        self.up_bytes = 0
        self.total_down_size = 0
        self.sent_file = []
        self.sent_file_names = []
        self.successful_downloads = []
