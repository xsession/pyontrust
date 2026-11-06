class MockDwf:
    """
    Mock class for DWF (Digital Waveform) driver.
    This class simulates the behavior of a DWF driver for testing purposes.
    """

    def __init__(self):
        self.is_open = False
        self.device_handle = None

    def open(self):
        """Simulate opening the DWF device."""
        self.is_open = True
        self.device_handle = "mock_device_handle"

    def close(self):
        """Simulate closing the DWF device."""
        self.is_open = False
        self.device_handle = None

    def is_opened(self):
        """Check if the DWF device is opened."""
        return self.is_open
    
    
if __name__ == "__main__":
    # Example usage
    mock_dwf = MockDwf()
    mock_dwf.open()
    print("Device opened:", mock_dwf.is_opened())
    mock_dwf.close()
    print("Device opened after close:", mock_dwf.is_opened())