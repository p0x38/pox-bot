class InteractionStatistics:
    def __init__(self):
        self.total: int = 0
        self.success: int = 0

    @property
    def failed(self) -> int:
        return self.total - self.success

    def count(self, failed: bool = False):
        self.total += 1

        if not failed:
            self.success += 1
