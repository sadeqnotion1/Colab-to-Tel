# Correct content for: colab_leecher/utility/transfer_state.py

class Transfer:
    """Holds state related to file transfer progress and results."""
    down_bytes: int = 0
    up_bytes: int = 0
    total_down_size: int = 0
    sent_file = [] 
    sent_file_names = [] 
    successful_downloads = []

    def reset(self):
        """Resets the state for a new task."""
        self.down_bytes = 0
        self.up_bytes = 0
        self.total_down_size = 0
        self.sent_file = []
        self.sent_file_names = []
        self.successful_downloads = []
