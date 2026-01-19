import sys
import pathlib
pyontrust_path = pathlib.Path(__file__).parent.parent.parent /"pyontrust_packages"
sys.path.append(str(pyontrust_path))

from drivers.ad3.mock_dwf import MockDwf
import unittest
from ctypes import byref, c_double, c_int, c_char_p

class MockDwf_test(unittest.TestCase):
    def __init__(self, methodName = "runTest"):
        super().__init__(methodName) 
           
    
    def setUp(self):
        # Reset the mock_dwf state before each test
        # mock_dwf.reset()
        self.mock_dwf = MockDwf()
        pass

    def tearDown(self):
        # Clean up after each test
        # mock_dwf.reset()
        pass

    def test_true(self):
        print("True")
        self.assertTrue(True)
        
    def test_mock_dwf_initialization(self):
        pass
        # self.assertFalse(self.mock_dwf.open())

    # def test_open_device():
    #     hdwf = [0]
    #     assert mock_dwf.FDwfDeviceOpen(0, hdwf)
    #     assert hdwf[0] != mock_dwf.hdwfNone

    # def test_acquire_data():
    #     hdwf = [0]
    #     mock_dwf.FDwfDeviceOpen(0, hdwf)
    #     mock_dwf.FDwfAnalogInConfigure(hdwf[0], 1, 1)

    #     status = [0]
    #     mock_dwf.FDwfAnalogInStatus(hdwf[0], 1, status)
    #     assert status[0] == mock_dwf.DwfStateDone

    #     data = [0.0] * 10
    #     mock_dwf.FDwfAnalogInStatusData(hdwf[0], 0, data, len(data))
    #     assert all(-5.0 <= v <= 5.0 for v in data)
    # def test_close_device():
    #     hdwf = [0]
    #     mock_dwf.FDwfDeviceOpen(0, hdwf)
    #     assert mock_dwf.FDwfDeviceClose(hdwf[0]) == 1
    #     assert hdwf[0] == mock_dwf.hdwfNone
    
if __name__ == "__main__":    
    unittest.main()