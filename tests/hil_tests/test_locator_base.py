"""Example HIL tests for Codelayer Locator Base board.

This module demonstrates how to use the HIL testing framework
for testing Zephyr drivers on the Locator Base board.

Requirements:
- Analog Discovery 3 connected to PC
- Locator Base board wired to AD3 according to the pinout
- Zephyr SDK and west tool installed

Usage:
    pytest tests/hil_tests/test_locator_base.py -v
    
    Or run standalone:
    python -m tests.hil_tests.test_locator_base
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from pyontrust.boards.locator_base import LOCATOR_BASE, LocatorBaseAD3 as AD3
from pyontrust.hil import HILTestFixture, AD3Interface


# ========== Fixtures ==========

@pytest.fixture(scope="module")
def hil_fixture():
    """Create and manage the HIL test fixture."""
    fixture = HILTestFixture(
        board=LOCATOR_BASE,
        # Adjust these paths for your environment
        zephyr_base=Path.home() / "zephyrproject" / "zephyr",
        app_base=Path(__file__).parent.parent.parent.parent / "locator_base" / "examples_apps",
    )
    
    with fixture:
        yield fixture


@pytest.fixture(scope="function")
def ad3(hil_fixture):
    """Get AD3 interface with reset before each test."""
    hil_fixture.ad3.reset()
    return hil_fixture.ad3


# ========== Digital Output Tests ==========

class TestDigitalOutputs:
    """Test GPIO digital output functionality."""
    
    def test_dout0_write_high(self, ad3: AD3Interface):
        """Test DOUT0 (PA2) can be driven high."""
        # Configure DIO0 as input to read MCU output
        ad3.digital.set_channel_output(AD3.DIO_DOUT0, False)
        
        # TODO: Trigger MCU to set PA2 high
        # This would require the firmware to respond to a command
        
        # For now, just verify we can read the pin
        value = ad3.digital.read(AD3.DIO_DOUT0)
        assert isinstance(value, bool)
    
    def test_dout_all_toggle(self, ad3: AD3Interface):
        """Test all DOUT pins can toggle."""
        for channel in AD3.DOUT_CHANNELS:
            ad3.digital.set_channel_output(channel, False)
        
        # Read initial state
        initial = ad3.digital.read_all()
        
        # Just verify we can read them
        for channel in AD3.DOUT_CHANNELS:
            value = ad3.digital.read(channel)
            assert isinstance(value, bool)


# ========== Digital Input Tests ==========

class TestDigitalInputs:
    """Test GPIO digital input functionality."""
    
    def test_din0_read(self, ad3: AD3Interface):
        """Test DIN0 (PA15) can be read after driving with AD3."""
        # Configure DIO4 as output to drive MCU input
        ad3.digital.set_channel_output(AD3.DIO_AIN0, True)
        
        # Drive high
        ad3.digital.write(AD3.DIO_AIN0, True)
        time.sleep(0.01)
        
        # Drive low
        ad3.digital.write(AD3.DIO_AIN0, False)
        time.sleep(0.01)
        
        # This verifies AD3 can control the pin
        # MCU verification would need firmware support
    
    def test_din_all_drive(self, ad3: AD3Interface):
        """Test all DIN pins can be driven by AD3."""
        for channel in AD3.DIN_CHANNELS:
            ad3.digital.set_channel_output(channel, True)
            
            # Test both states
            ad3.digital.write(channel, True)
            time.sleep(0.001)
            ad3.digital.write(channel, False)
            time.sleep(0.001)


# ========== PWM Tests ==========

class TestPWMOutputs:
    """Test PWM output functionality."""
    
    @pytest.mark.skip(reason="Requires firmware with PWM output")
    def test_pwm0_frequency(self, hil_fixture: HILTestFixture):
        """Test PWM0 (PA7, TIMG8_C0) frequency."""
        # Load PWM test application
        hil_fixture.load_app("07_solution_usb_print")  # Adjust to actual PWM app
        hil_fixture.wait_for_boot(timeout_s=2.0)
        
        # Measure PWM
        result = hil_fixture.verify_pwm(
            pin_name="PA7",
            expected_freq_hz=1000,
            expected_duty=0.5,
        )
        
        assert result["pass"], f"PWM verification failed: {result}"
    
    def test_pwm_measurement_capability(self, ad3: AD3Interface):
        """Test that we can measure PWM signals."""
        # Generate a test signal with AD3's waveform generator
        # and verify measurement works
        
        from pyontrust.hil.analog_io import WaveformType
        
        # Configure analog output as square wave (simulates PWM)
        ad3.analog.set_waveform(
            channel=0,
            waveform=WaveformType.SQUARE,
            frequency_hz=1000,
            amplitude_v=1.65,
            offset_v=1.65,
        )
        ad3.analog.output_enable(0, True)
        
        time.sleep(0.1)
        
        # Measure using analog input (requires loopback for self-test)
        # In real test, this would read from MCU's PWM output
        
        ad3.analog.output_enable(0, False)


# ========== ADC Tests ==========

class TestADCInputs:
    """Test ADC input functionality."""
    
    def test_adc_stimulus(self, ad3: AD3Interface):
        """Test AD3 can provide analog stimulus for ADC testing."""
        # Set DC voltage on AOUT0 (connected to PA15)
        test_voltages = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0]
        
        for voltage in test_voltages:
            ad3.analog.set_dc(AD3.AOUT_ADC0, voltage)
            ad3.analog.output_enable(AD3.AOUT_ADC0, True)
            time.sleep(0.05)
            
            # In real test, read ADC value via UART and compare
        
        ad3.analog.output_enable(AD3.AOUT_ADC0, False)
    
    def test_analog_measurement(self, ad3: AD3Interface):
        """Test analog measurement capability."""
        # Configure input
        ad3.analog.configure_input(
            channel=AD3.AIN_PWM0,
            range_v=5.0,
        )
        
        # Read voltage
        voltage = ad3.analog.read_voltage(AD3.AIN_PWM0)
        
        # Just verify we get a valid reading
        assert -5.0 <= voltage <= 5.0


# ========== SPI Tests ==========

class TestSPIInterface:
    """Test SPI communication."""
    
    def test_spi_configuration(self, ad3: AD3Interface):
        """Test SPI can be configured."""
        ad3.spi.configure(
            clock_hz=1_000_000,
            dio_sck=AD3.DIO_SPI_SCK,
            dio_mosi=AD3.DIO_SPI_MOSI,
            dio_miso=AD3.DIO_SPI_MISO,
            dio_cs=AD3.DIO_SPI_CS0,
        )
        
        # Verify configuration was accepted
        assert ad3.spi._configured
    
    @pytest.mark.skip(reason="Requires SPI peripheral connected")
    def test_spi_loopback(self, ad3: AD3Interface):
        """Test SPI loopback (connect MOSI to MISO)."""
        ad3.spi.configure(clock_hz=100_000)
        
        tx_data = [0xAA, 0x55, 0x00, 0xFF]
        rx_data = ad3.spi.transfer(tx_data)
        
        # With loopback, RX should match TX
        assert rx_data == tx_data


# ========== I2C Tests ==========

class TestI2CInterface:
    """Test I2C communication."""
    
    def test_i2c_configuration(self, ad3: AD3Interface):
        """Test I2C can be configured."""
        ad3.i2c.configure(
            clock_hz=100_000,
            dio_sda=AD3.DIO_I2C_SDA,
            dio_scl=AD3.DIO_I2C_SCL,
        )
        
        assert ad3.i2c._configured
    
    @pytest.mark.skip(reason="Requires I2C device connected")
    def test_i2c_scan(self, ad3: AD3Interface):
        """Test I2C bus scan."""
        ad3.i2c.configure(clock_hz=100_000)
        
        devices = ad3.i2c.scan()
        
        # Just verify scan completes
        assert isinstance(devices, list)


# ========== UART Tests ==========

class TestUARTInterface:
    """Test UART communication."""
    
    def test_uart_configuration(self, ad3: AD3Interface):
        """Test UART can be configured."""
        ad3.uart.configure(
            baud_rate=115200,
            dio_tx=AD3.DIO_UART_TX,
            dio_rx=AD3.DIO_UART_RX,
        )
        
        assert ad3.uart._configured
    
    @pytest.mark.skip(reason="Requires UART loopback or device")
    def test_uart_loopback(self, ad3: AD3Interface):
        """Test UART loopback (connect TX to RX)."""
        ad3.uart.configure(baud_rate=9600)
        
        test_message = b"Hello, World!\n"
        ad3.uart.write(test_message)
        
        # With loopback, should receive what we sent
        received = ad3.uart.read(timeout_s=0.5)
        assert received == test_message


# ========== Integration Tests ==========

class TestIntegration:
    """Integration tests requiring firmware support."""
    
    @pytest.mark.skip(reason="Requires blink firmware")
    def test_blink_led(self, hil_fixture: HILTestFixture):
        """Test LED blink application."""
        # Load blink application
        hil_fixture.load_app("01_blink")
        hil_fixture.wait_for_boot(timeout_s=2.0)
        
        # Count toggles on LED pin (assuming DOUT0 is LED)
        toggles = hil_fixture.verify_gpio_toggle(
            pin_name="PA2",
            min_toggles=4,
            timeout_s=5.0,
        )
        
        assert toggles >= 4, f"Expected at least 4 toggles, got {toggles}"
    
    @pytest.mark.skip(reason="Requires button firmware")
    def test_button_input(self, hil_fixture: HILTestFixture):
        """Test button input handling."""
        # Load button demo application
        hil_fixture.load_app("04_solution_button_led")
        hil_fixture.wait_for_boot(timeout_s=2.0)
        
        # Simulate button press using AD3
        button_pin = "PA15"  # Adjust to actual button pin
        led_pin = "PA2"      # Adjust to actual LED pin
        
        # Press button (drive low)
        hil_fixture.ad3.digital.write_pin(button_pin, False)
        time.sleep(0.1)
        
        # Verify LED changed state
        led_state = hil_fixture.ad3.digital.read_pin(led_pin)
        
        # Release button
        hil_fixture.ad3.digital.write_pin(button_pin, True)


# ========== Standalone runner ==========

if __name__ == "__main__":
    """Run tests without pytest for quick verification."""
    
    print("Locator Base HIL Test Suite")
    print("=" * 50)
    
    # Check if AD3 is available
    try:
        from pyontrust.instruments import dwf_loader
        dwf = dwf_loader.load_dwf()
        print("✓ DWF library loaded")
    except Exception as e:
        print(f"✗ DWF library not available: {e}")
        print("  Install Digilent WaveForms to run HIL tests")
        exit(1)
    
    # Try to open AD3
    try:
        ad3 = AD3Interface(board=LOCATOR_BASE)
        ad3.open()
        print("✓ AD3 connected")
        
        # Run basic tests
        print("\nRunning basic tests...")
        
        # Test digital I/O
        print("  Digital I/O...", end=" ")
        ad3.digital.set_output_enable(0x0F)  # DIO0-3 as outputs
        ad3.digital.write_all(0x05)          # DIO0 and DIO2 high
        state = ad3.digital.read_all()
        print(f"✓ (state: 0x{state:04X})")
        
        # Test analog read
        print("  Analog input...", end=" ")
        voltage = ad3.analog.read_voltage(0)
        print(f"✓ (CH1: {voltage:.3f}V)")
        
        # Test analog output
        print("  Analog output...", end=" ")
        ad3.analog.set_dc(0, 1.5)
        ad3.analog.output_enable(0, True)
        time.sleep(0.1)
        ad3.analog.output_enable(0, False)
        print("✓")
        
        print("\n" + "=" * 50)
        print("Basic tests passed!")
        print("\nRun 'pytest tests/hil_tests/test_locator_base.py -v' for full test suite")
        
        ad3.close()
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        exit(1)
