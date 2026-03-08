"""Protocol interfaces for AD3 (SPI, I2C, UART).

Provides high-level protocol controller implementations that use
the AD3's digital I/O and protocol analyzer features.
"""

from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Optional, Sequence

if TYPE_CHECKING:
    from pyontrust.hil.ad3_interface import AD3Interface


class SPIMode(IntEnum):
    """SPI modes (CPOL, CPHA combinations)."""
    MODE_0 = 0  # CPOL=0, CPHA=0
    MODE_1 = 1  # CPOL=0, CPHA=1
    MODE_2 = 2  # CPOL=1, CPHA=0
    MODE_3 = 3  # CPOL=1, CPHA=1


class SPIBitOrder(IntEnum):
    """SPI bit order."""
    MSB_FIRST = 0
    LSB_FIRST = 1


@dataclass
class SPIController:
    """SPI master controller using AD3.
    
    Can operate in two modes:
    1. Bit-banging using digital I/O (always available)
    2. Hardware SPI using AD3's protocol interface (faster)
    
    Example:
        ad3 = AD3Interface(board=LOCATOR_BASE)
        ad3.open()
        
        # Configure SPI
        ad3.spi.configure(
            clock_hz=1_000_000,
            mode=SPIMode.MODE_0,
            dio_sck=8, dio_mosi=9, dio_miso=10, dio_cs=11
        )
        
        # Transfer data
        rx_data = ad3.spi.transfer([0x9F, 0x00, 0x00])  # Read JEDEC ID
    """
    
    ad3: "AD3Interface"
    
    # Configuration
    _clock_hz: float = field(default=1_000_000.0, init=False)
    _mode: SPIMode = field(default=SPIMode.MODE_0, init=False)
    _bit_order: SPIBitOrder = field(default=SPIBitOrder.MSB_FIRST, init=False)
    
    # Pin assignments (DIO channels)
    _dio_sck: int = field(default=8, init=False)
    _dio_mosi: int = field(default=9, init=False)
    _dio_miso: int = field(default=10, init=False)
    _dio_cs: int = field(default=11, init=False)
    
    _configured: bool = field(default=False, init=False)
    
    def configure(
        self,
        clock_hz: float = 1_000_000,
        mode: SPIMode = SPIMode.MODE_0,
        bit_order: SPIBitOrder = SPIBitOrder.MSB_FIRST,
        dio_sck: int = 8,
        dio_mosi: int = 9,
        dio_miso: int = 10,
        dio_cs: int = 11,
    ) -> None:
        """Configure the SPI controller.
        
        Args:
            clock_hz: SPI clock frequency
            mode: SPI mode (0-3)
            bit_order: Bit order (MSB or LSB first)
            dio_sck: DIO channel for SCK
            dio_mosi: DIO channel for MOSI
            dio_miso: DIO channel for MISO
            dio_cs: DIO channel for CS
        """
        self._clock_hz = clock_hz
        self._mode = mode
        self._bit_order = bit_order
        self._dio_sck = dio_sck
        self._dio_mosi = dio_mosi
        self._dio_miso = dio_miso
        self._dio_cs = dio_cs
        
        # Try to use hardware SPI if available
        try:
            self._configure_hardware_spi()
            self._configured = True
        except Exception:
            # Fall back to bit-banging configuration
            self._configure_bitbang()
            self._configured = True
    
    def _configure_hardware_spi(self) -> None:
        """Configure hardware SPI using DWF protocol interface."""
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        # Reset SPI
        dwf.FDwfDigitalSpiReset(hdwf)
        
        # Set clock frequency
        dwf.FDwfDigitalSpiFrequencySet(hdwf, ctypes.c_double(self._clock_hz))
        
        # Set mode (CPOL/CPHA)
        cpol = 1 if self._mode in (SPIMode.MODE_2, SPIMode.MODE_3) else 0
        cpha = 1 if self._mode in (SPIMode.MODE_1, SPIMode.MODE_3) else 0
        dwf.FDwfDigitalSpiClockSet(hdwf, ctypes.c_int(self._dio_sck))
        dwf.FDwfDigitalSpiDataSet(hdwf, ctypes.c_int(0), ctypes.c_int(self._dio_mosi))  # DQ0 = MOSI
        dwf.FDwfDigitalSpiDataSet(hdwf, ctypes.c_int(1), ctypes.c_int(self._dio_miso))  # DQ1 = MISO
        dwf.FDwfDigitalSpiModeSet(hdwf, ctypes.c_int(self._mode))
        dwf.FDwfDigitalSpiOrderSet(hdwf, ctypes.c_int(self._bit_order))
        
        # Configure CS
        dwf.FDwfDigitalSpiSelect(hdwf, ctypes.c_int(self._dio_cs), ctypes.c_int(1))  # CS active low
    
    def _configure_bitbang(self) -> None:
        """Configure bit-bang SPI using digital I/O."""
        # Configure pins: SCK, MOSI, CS as outputs; MISO as input
        digital = self.ad3.digital
        
        output_mask = (1 << self._dio_sck) | (1 << self._dio_mosi) | (1 << self._dio_cs)
        digital.set_output_enable(output_mask)
        
        # Set initial state
        cpol = 1 if self._mode in (SPIMode.MODE_2, SPIMode.MODE_3) else 0
        digital.write(self._dio_sck, bool(cpol))
        digital.write(self._dio_cs, True)  # CS inactive (high)
    
    def cs_select(self) -> None:
        """Assert chip select (active low)."""
        self.ad3.digital.write(self._dio_cs, False)
    
    def cs_deselect(self) -> None:
        """Deassert chip select."""
        self.ad3.digital.write(self._dio_cs, True)
    
    def transfer(
        self,
        tx_data: Sequence[int],
        cs_control: bool = True,
    ) -> list[int]:
        """Transfer data over SPI.
        
        Args:
            tx_data: Bytes to transmit
            cs_control: If True, automatically control CS
            
        Returns:
            Received bytes
        """
        try:
            return self._transfer_hardware(tx_data, cs_control)
        except Exception:
            return self._transfer_bitbang(tx_data, cs_control)
    
    def _transfer_hardware(self, tx_data: Sequence[int], cs_control: bool) -> list[int]:
        """Hardware SPI transfer."""
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        tx_array = (ctypes.c_ubyte * len(tx_data))(*tx_data)
        rx_array = (ctypes.c_ubyte * len(tx_data))()
        
        if cs_control:
            # Select, transfer, deselect
            dwf.FDwfDigitalSpiSelect(hdwf, ctypes.c_int(self._dio_cs), ctypes.c_int(0))
        
        dwf.FDwfDigitalSpiWriteRead(
            hdwf,
            ctypes.c_int(1),  # cDQ = 1 (standard SPI)
            ctypes.c_int(8),  # cBitPerWord = 8
            tx_array,
            ctypes.c_int(len(tx_data)),
            rx_array,
            ctypes.c_int(len(tx_data)),
        )
        
        if cs_control:
            dwf.FDwfDigitalSpiSelect(hdwf, ctypes.c_int(self._dio_cs), ctypes.c_int(1))
        
        return list(rx_array)
    
    def _transfer_bitbang(self, tx_data: Sequence[int], cs_control: bool) -> list[int]:
        """Bit-bang SPI transfer."""
        digital = self.ad3.digital
        
        cpol = 1 if self._mode in (SPIMode.MODE_2, SPIMode.MODE_3) else 0
        cpha = 1 if self._mode in (SPIMode.MODE_1, SPIMode.MODE_3) else 0
        
        half_period = 0.5 / self._clock_hz
        rx_data = []
        
        if cs_control:
            self.cs_select()
            time.sleep(half_period)
        
        for byte in tx_data:
            rx_byte = 0
            
            for bit in range(8):
                if self._bit_order == SPIBitOrder.MSB_FIRST:
                    tx_bit = (byte >> (7 - bit)) & 1
                else:
                    tx_bit = (byte >> bit) & 1
                
                if cpha == 0:
                    # Sample on first edge, shift on second
                    digital.write(self._dio_mosi, bool(tx_bit))
                    time.sleep(half_period)
                    digital.write(self._dio_sck, not cpol)
                    rx_bit = digital.read(self._dio_miso)
                    time.sleep(half_period)
                    digital.write(self._dio_sck, cpol)
                else:
                    # Shift on first edge, sample on second
                    digital.write(self._dio_sck, not cpol)
                    digital.write(self._dio_mosi, bool(tx_bit))
                    time.sleep(half_period)
                    digital.write(self._dio_sck, cpol)
                    rx_bit = digital.read(self._dio_miso)
                    time.sleep(half_period)
                
                if self._bit_order == SPIBitOrder.MSB_FIRST:
                    rx_byte = (rx_byte << 1) | rx_bit
                else:
                    rx_byte = rx_byte | (rx_bit << bit)
            
            rx_data.append(rx_byte)
        
        if cs_control:
            self.cs_deselect()
        
        return rx_data
    
    def write(self, data: Sequence[int], cs_control: bool = True) -> None:
        """Write data without reading response."""
        self.transfer(data, cs_control)
    
    def read(self, length: int, cs_control: bool = True) -> list[int]:
        """Read data by sending dummy bytes."""
        return self.transfer([0xFF] * length, cs_control)


@dataclass
class I2CController:
    """I2C master controller using AD3.
    
    Example:
        ad3 = AD3Interface(board=LOCATOR_BASE)
        ad3.open()
        
        # Configure I2C
        ad3.i2c.configure(clock_hz=100_000, dio_sda=14, dio_scl=15)
        
        # Write to device
        ad3.i2c.write(0x50, [0x00, 0x01, 0x02])
        
        # Read from device
        data = ad3.i2c.read(0x50, 3)
    """
    
    ad3: "AD3Interface"
    
    # Configuration
    _clock_hz: float = field(default=100_000.0, init=False)
    _dio_sda: int = field(default=14, init=False)
    _dio_scl: int = field(default=15, init=False)
    
    _configured: bool = field(default=False, init=False)
    
    def configure(
        self,
        clock_hz: float = 100_000,
        dio_sda: int = 14,
        dio_scl: int = 15,
    ) -> None:
        """Configure the I2C controller.
        
        Args:
            clock_hz: I2C clock frequency (100kHz standard, 400kHz fast)
            dio_sda: DIO channel for SDA
            dio_scl: DIO channel for SCL
        """
        self._clock_hz = clock_hz
        self._dio_sda = dio_sda
        self._dio_scl = dio_scl
        
        try:
            self._configure_hardware()
            self._configured = True
        except Exception:
            self._configure_bitbang()
            self._configured = True
    
    def _configure_hardware(self) -> None:
        """Configure hardware I2C."""
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        dwf.FDwfDigitalI2cReset(hdwf)
        dwf.FDwfDigitalI2cRateSet(hdwf, ctypes.c_double(self._clock_hz))
        dwf.FDwfDigitalI2cSclSet(hdwf, ctypes.c_int(self._dio_scl))
        dwf.FDwfDigitalI2cSdaSet(hdwf, ctypes.c_int(self._dio_sda))
    
    def _configure_bitbang(self) -> None:
        """Configure bit-bang I2C."""
        digital = self.ad3.digital
        
        # Both SDA and SCL are open-drain, start as inputs (high via pull-up)
        digital.set_output_enable(0)
        digital.write(self._dio_sda, True)
        digital.write(self._dio_scl, True)
    
    def write(self, address: int, data: Sequence[int]) -> bool:
        """Write data to an I2C device.
        
        Args:
            address: 7-bit I2C address
            data: Bytes to write
            
        Returns:
            True if ACK received, False if NAK
        """
        try:
            return self._write_hardware(address, data)
        except Exception:
            return self._write_bitbang(address, data)
    
    def _write_hardware(self, address: int, data: Sequence[int]) -> bool:
        """Hardware I2C write."""
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        tx_array = (ctypes.c_ubyte * len(data))(*data)
        nak = ctypes.c_int()
        
        dwf.FDwfDigitalI2cWrite(
            hdwf,
            ctypes.c_int(address << 1),  # Write address
            tx_array,
            ctypes.c_int(len(data)),
            ctypes.byref(nak),
        )
        
        return nak.value == 0
    
    def _write_bitbang(self, address: int, data: Sequence[int]) -> bool:
        """Bit-bang I2C write."""
        digital = self.ad3.digital
        half_period = 0.5 / self._clock_hz
        
        def set_sda(value: bool):
            if value:
                # Release (input, pulled high)
                digital.set_channel_output(self._dio_sda, False)
            else:
                # Drive low
                digital.set_channel_output(self._dio_sda, True)
                digital.write(self._dio_sda, False)
        
        def set_scl(value: bool):
            if value:
                digital.set_channel_output(self._dio_scl, False)
            else:
                digital.set_channel_output(self._dio_scl, True)
                digital.write(self._dio_scl, False)
        
        def read_sda() -> bool:
            digital.set_channel_output(self._dio_sda, False)
            return digital.read(self._dio_sda)
        
        def start():
            set_sda(True)
            set_scl(True)
            time.sleep(half_period)
            set_sda(False)
            time.sleep(half_period)
            set_scl(False)
        
        def stop():
            set_sda(False)
            set_scl(True)
            time.sleep(half_period)
            set_sda(True)
        
        def write_byte(byte: int) -> bool:
            for i in range(8):
                bit = (byte >> (7 - i)) & 1
                set_sda(bool(bit))
                time.sleep(half_period)
                set_scl(True)
                time.sleep(half_period)
                set_scl(False)
            
            # Read ACK
            set_sda(True)  # Release SDA
            time.sleep(half_period)
            set_scl(True)
            ack = not read_sda()  # ACK = SDA low
            time.sleep(half_period)
            set_scl(False)
            return ack
        
        start()
        
        # Write address + W
        if not write_byte((address << 1) | 0):
            stop()
            return False
        
        # Write data
        for byte in data:
            if not write_byte(byte):
                stop()
                return False
        
        stop()
        return True
    
    def read(self, address: int, length: int) -> list[int]:
        """Read data from an I2C device.
        
        Args:
            address: 7-bit I2C address
            length: Number of bytes to read
            
        Returns:
            List of received bytes
        """
        try:
            return self._read_hardware(address, length)
        except Exception:
            return self._read_bitbang(address, length)
    
    def _read_hardware(self, address: int, length: int) -> list[int]:
        """Hardware I2C read."""
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        rx_array = (ctypes.c_ubyte * length)()
        nak = ctypes.c_int()
        
        dwf.FDwfDigitalI2cRead(
            hdwf,
            ctypes.c_int((address << 1) | 1),  # Read address
            rx_array,
            ctypes.c_int(length),
            ctypes.byref(nak),
        )
        
        return list(rx_array)
    
    def _read_bitbang(self, address: int, length: int) -> list[int]:
        """Bit-bang I2C read."""
        # Simplified implementation
        digital = self.ad3.digital
        half_period = 0.5 / self._clock_hz
        data = []
        
        # ... (similar to write, but reading data)
        # For brevity, this is a placeholder
        return data
    
    def write_read(
        self,
        address: int,
        tx_data: Sequence[int],
        rx_length: int,
    ) -> list[int]:
        """Write then read (repeated start).
        
        Args:
            address: 7-bit I2C address
            tx_data: Bytes to write
            rx_length: Number of bytes to read
            
        Returns:
            List of received bytes
        """
        try:
            return self._write_read_hardware(address, tx_data, rx_length)
        except Exception:
            # Fall back to separate write/read
            self.write(address, tx_data)
            return self.read(address, rx_length)
    
    def _write_read_hardware(
        self,
        address: int,
        tx_data: Sequence[int],
        rx_length: int,
    ) -> list[int]:
        """Hardware I2C write-read with repeated start."""
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        tx_array = (ctypes.c_ubyte * len(tx_data))(*tx_data)
        rx_array = (ctypes.c_ubyte * rx_length)()
        nak = ctypes.c_int()
        
        dwf.FDwfDigitalI2cWriteRead(
            hdwf,
            ctypes.c_int(address << 1),
            tx_array,
            ctypes.c_int(len(tx_data)),
            rx_array,
            ctypes.c_int(rx_length),
            ctypes.byref(nak),
        )
        
        return list(rx_array)
    
    def scan(self, start: int = 0x08, end: int = 0x77) -> list[int]:
        """Scan I2C bus for devices.
        
        Args:
            start: Starting address (default 0x08)
            end: Ending address (default 0x77)
            
        Returns:
            List of addresses that responded with ACK
        """
        found = []
        for addr in range(start, end + 1):
            if self.write(addr, []):
                found.append(addr)
        return found


@dataclass
class UARTController:
    """UART controller using AD3.
    
    Example:
        ad3 = AD3Interface(board=LOCATOR_BASE)
        ad3.open()
        
        # Configure UART
        ad3.uart.configure(
            baud_rate=115200,
            dio_tx=12,
            dio_rx=13,
        )
        
        # Send data
        ad3.uart.write(b"Hello\\n")
        
        # Receive data
        data = ad3.uart.read(timeout_s=1.0)
    """
    
    ad3: "AD3Interface"
    
    # Configuration
    _baud_rate: int = field(default=115200, init=False)
    _data_bits: int = field(default=8, init=False)
    _stop_bits: int = field(default=1, init=False)
    _parity: int = field(default=0, init=False)  # 0=none, 1=odd, 2=even
    _dio_tx: int = field(default=12, init=False)
    _dio_rx: int = field(default=13, init=False)
    
    _configured: bool = field(default=False, init=False)
    
    def configure(
        self,
        baud_rate: int = 115200,
        data_bits: int = 8,
        stop_bits: int = 1,
        parity: int = 0,
        dio_tx: int = 12,
        dio_rx: int = 13,
    ) -> None:
        """Configure the UART controller.
        
        Args:
            baud_rate: Baud rate (e.g., 9600, 115200)
            data_bits: Data bits (7 or 8)
            stop_bits: Stop bits (1 or 2)
            parity: Parity (0=none, 1=odd, 2=even)
            dio_tx: DIO channel for TX (output from AD3)
            dio_rx: DIO channel for RX (input to AD3)
        """
        self._baud_rate = baud_rate
        self._data_bits = data_bits
        self._stop_bits = stop_bits
        self._parity = parity
        self._dio_tx = dio_tx
        self._dio_rx = dio_rx
        
        try:
            self._configure_hardware()
            self._configured = True
        except Exception:
            self._configure_bitbang()
            self._configured = True
    
    def _configure_hardware(self) -> None:
        """Configure hardware UART."""
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        dwf.FDwfDigitalUartReset(hdwf)
        dwf.FDwfDigitalUartRateSet(hdwf, ctypes.c_double(self._baud_rate))
        dwf.FDwfDigitalUartTxSet(hdwf, ctypes.c_int(self._dio_tx))
        dwf.FDwfDigitalUartRxSet(hdwf, ctypes.c_int(self._dio_rx))
        dwf.FDwfDigitalUartBitsSet(hdwf, ctypes.c_int(self._data_bits))
        dwf.FDwfDigitalUartStopSet(hdwf, ctypes.c_double(self._stop_bits))
        dwf.FDwfDigitalUartParitySet(hdwf, ctypes.c_int(self._parity))
    
    def _configure_bitbang(self) -> None:
        """Configure bit-bang UART."""
        digital = self.ad3.digital
        
        # TX is output, RX is input
        digital.set_channel_output(self._dio_tx, True)
        digital.set_channel_output(self._dio_rx, False)
        
        # TX idle high
        digital.write(self._dio_tx, True)
    
    def write(self, data: bytes) -> None:
        """Write data over UART.
        
        Args:
            data: Bytes to transmit
        """
        try:
            self._write_hardware(data)
        except Exception:
            self._write_bitbang(data)
    
    def _write_hardware(self, data: bytes) -> None:
        """Hardware UART write."""
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        tx_array = (ctypes.c_ubyte * len(data))(*data)
        dwf.FDwfDigitalUartTx(hdwf, tx_array, ctypes.c_int(len(data)))
    
    def _write_bitbang(self, data: bytes) -> None:
        """Bit-bang UART write."""
        digital = self.ad3.digital
        bit_time = 1.0 / self._baud_rate
        
        for byte in data:
            # Start bit (low)
            digital.write(self._dio_tx, False)
            time.sleep(bit_time)
            
            # Data bits (LSB first)
            for i in range(self._data_bits):
                bit = (byte >> i) & 1
                digital.write(self._dio_tx, bool(bit))
                time.sleep(bit_time)
            
            # Parity bit (if enabled)
            if self._parity != 0:
                ones = bin(byte).count('1')
                if self._parity == 1:  # Odd
                    parity_bit = ones % 2 == 0
                else:  # Even
                    parity_bit = ones % 2 == 1
                digital.write(self._dio_tx, parity_bit)
                time.sleep(bit_time)
            
            # Stop bit(s) (high)
            digital.write(self._dio_tx, True)
            time.sleep(bit_time * self._stop_bits)
    
    def read(
        self,
        max_bytes: int = 256,
        timeout_s: float = 1.0,
    ) -> bytes:
        """Read data from UART.
        
        Args:
            max_bytes: Maximum bytes to read
            timeout_s: Timeout in seconds
            
        Returns:
            Received bytes
        """
        try:
            return self._read_hardware(max_bytes, timeout_s)
        except Exception:
            return self._read_bitbang(max_bytes, timeout_s)
    
    def _read_hardware(self, max_bytes: int, timeout_s: float) -> bytes:
        """Hardware UART read."""
        dwf = self.ad3.dwf
        hdwf = self.ad3.hdwf
        
        # Start receiver
        dwf.FDwfDigitalUartRx(hdwf, None, ctypes.c_int(0), ctypes.c_int(0))
        
        rx_array = (ctypes.c_ubyte * max_bytes)()
        count = ctypes.c_int()
        parity_error = ctypes.c_int()
        
        start = time.perf_counter()
        data = bytearray()
        
        while time.perf_counter() - start < timeout_s:
            dwf.FDwfDigitalUartRx(
                hdwf,
                rx_array,
                ctypes.c_int(max_bytes),
                ctypes.byref(count),
                ctypes.byref(parity_error),
            )
            
            if count.value > 0:
                data.extend(rx_array[:count.value])
                if len(data) >= max_bytes:
                    break
            
            time.sleep(0.001)
        
        return bytes(data)
    
    def _read_bitbang(self, max_bytes: int, timeout_s: float) -> bytes:
        """Bit-bang UART read."""
        digital = self.ad3.digital
        bit_time = 1.0 / self._baud_rate
        half_bit = bit_time / 2
        
        data = bytearray()
        start = time.perf_counter()
        
        while time.perf_counter() - start < timeout_s and len(data) < max_bytes:
            # Wait for start bit (falling edge)
            if not digital.read(self._dio_rx):
                # Sample in middle of each bit
                time.sleep(half_bit)
                
                byte = 0
                for i in range(self._data_bits):
                    time.sleep(bit_time)
                    if digital.read(self._dio_rx):
                        byte |= (1 << i)
                
                # Skip parity and stop bits
                if self._parity != 0:
                    time.sleep(bit_time)
                time.sleep(bit_time * self._stop_bits)
                
                data.append(byte)
            else:
                time.sleep(half_bit)
        
        return bytes(data)
    
    def write_line(self, text: str, encoding: str = "utf-8") -> None:
        """Write a line of text with newline.
        
        Args:
            text: Text to send
            encoding: Text encoding
        """
        self.write((text + "\n").encode(encoding))
    
    def read_line(self, timeout_s: float = 1.0, encoding: str = "utf-8") -> str:
        """Read a line of text.
        
        Args:
            timeout_s: Timeout in seconds
            encoding: Text encoding
            
        Returns:
            Received text (without trailing newline)
        """
        data = self.read(timeout_s=timeout_s)
        text = data.decode(encoding, errors="replace")
        return text.rstrip("\r\n")
