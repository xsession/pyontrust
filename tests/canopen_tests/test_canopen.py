"""Tests for pyontrust.analysis.canopen — NMT/SDO codec, EDS round-trip, simulated node."""
from __future__ import annotations

import pytest

from pyontrust.analysis.canopen import (
    SimulatedCanopenNode, decode_emcy,
    nmt_frame, parse_eds, parse_sdo_response, sdo_download_request,
    sdo_upload_request, write_eds,
)

SAMPLE_EDS = """\
[FileInfo]
FileName=test.eds
FileRevision=1
FileType=1
FileDescription=sample device

[CANopenDevice]
ProducerName=Acme
ProducerNumber=0x00000099
ProductNumber=0x00000077
RevisionNumber=0x00020000
BaudRate_500=1

[0x1000]
ParameterName=Device type
ObjectType=0x0007
AccessType=ro

[0x1008]
SubNumber=4
ParameterName=Identity object
ObjectType=0x0030
AccessType=ro

[0x1008.00]
ParameterName=Producer specific ID
ObjectType=0x0007
PdoConsumer=1

[0x1008.01]
ParameterName=Product number
ObjectType=0x0007

[0x2000]
SubNumber=1
ParameterName=Motor speed setpoint
ObjectType=0x0006
AccessType=rw
PdoProducer=1

[0x2000.00]
ParameterName=Speed [rpm]
ObjectType=0x0006
"""


class TestNmt:
    def test_frame(self):
        arb, data = nmt_frame(5, 0x01)
        assert arb == 0x000
        assert data == bytes([0x01, 0x05])

    def test_invalid_node(self):
        with pytest.raises(ValueError):
            nmt_frame(0, 0x01)
        with pytest.raises(ValueError):
            nmt_frame(128, 0x01)

    def test_unknown_command_rejected(self):
        with pytest.raises(ValueError):
            nmt_frame(1, 0x99)


class TestSdoCodec:
    def test_upload_request_bytes(self):
        # CiA 301 / CANopenNode CO_SDOclient.c: expedited upload request = 0xC0
        arb, data = sdo_upload_request(3, 0x2000, 0)
        assert arb == 0x600 + 3
        assert data == bytes([0xC0, 0x00, 0x20, 0x00])

    def test_download_request_bytes(self):
        # byte0 = 0x20|0x02(expedited)|0x01(size-ind)|((4-nbytes)<<2)
        arb, data = sdo_download_request(1, 0x2000, 0, 1500)
        assert arb == 0x601
        assert data[0] == 0x2B                      # 2-byte value: (4-2)<<2
        assert data[1:4] == bytes([0x00, 0x20, 0x00])
        assert int.from_bytes(data[4:8], "little") == 1500

    def test_download_request_1byte(self):
        arb, data = sdo_download_request(1, 0x2000, 0, 7)
        assert data[0] == 0x2F                      # (4-1)<<2
        assert int.from_bytes(data[4:8], "little") == 7

    def test_parse_expedited_4byte(self):
        # CANopenNode server: byte0 = 0x43 | ((4-count)<<2) -> 0x43 for 4 bytes
        data = bytes([0x43, 0x00, 0x20, 0x00]) + (1500).to_bytes(4, "little")
        out = parse_sdo_response(data)
        assert out["ok"] is True
        assert out["value"] == 1500

    def test_parse_expedited_2byte(self):
        data = bytes([0x4B, 0x00, 0x20, 0x01]) + (42).to_bytes(2, "little")
        out = parse_sdo_response(data)
        assert out["ok"] is True and out["value"] == 42

    def test_parse_download_ack(self):
        data = bytes([0x60, 0x00, 0x20, 0x00])
        out = parse_sdo_response(data)
        assert out["ok"] is True and out.get("ack") is True

    def test_parse_abort(self):
        data = bytes([0x80, 0x00, 0x20, 0x00]) + (0x0609_0011).to_bytes(4, "little")
        out = parse_sdo_response(data)
        assert out["ok"] is False
        assert out["error_code"] == 0x0609_0011


class TestEmcy:
    def test_decode(self):
        # EEC 0x4200 + error register bit 4 (SDO protocol timeout)
        data = (0x4200).to_bytes(2, "little") + bytes([0x10])
        out = decode_emcy(data)
        assert out["eec"] == 0x4200
        assert "Device profile" in out["description"]
        assert "SDO protocol timeout" in out["flags"]


class TestEds:
    def test_parse_sample(self):
        doc = parse_eds(SAMPLE_EDS)
        assert doc.device_info.get("producername") == "Acme"
        e1000 = doc.entry(0x1000, -1)  # bare section -> parent row (subindex -1)
        assert e1000 is not None and e1000.name == "Device type"
        assert e1000.access == "ro"
        subs_1008 = [e for e in doc.entries if e.index == 0x1008]
        assert len(subs_1008) == 3  # parent row + .00 + .01
        spd = doc.entry(0x2000, -1)
        assert spd.pdo_producer is True

    def test_roundtrip(self):
        doc = parse_eds(SAMPLE_EDS)
        text = write_eds(doc)
        doc2 = parse_eds(text)
        keys1 = {(e.index, e.subindex) for e in doc.entries}
        keys2 = {(e.index, e.subindex) for e in doc2.entries}
        assert keys1 == keys2
        assert doc2.entry(0x2000, -1).name == "Motor speed setpoint"
        assert doc2.device_info.get("producername") == "Acme"

    def test_bare_hex_sections(self):
        # CANopenNode-style EDS: unprefixed numbers are HEX (CiA 306), not decimal
        text = """[FileInfo]
FileName=m.eds

[1000]
SubNumber=2
ParameterName=Device type
ObjectType=0x0007
AccessType=ro

[1000.01]
ParameterName=Vendor ID
Value=4

[6040]
SubNumber=1
ParameterName=CISDS Controlword
ObjectType=0x0020
AccessType=rw

[6040.01]
ParameterName=Target Velocity
"""
        doc = parse_eds(text)
        assert doc.entry(0x1000, -1) is not None          # [1000] == 0x1000, not decimal 1000
        assert doc.entry(0x1000, 1).name == "Vendor ID"   # subindex parsed too
        e = doc.entry(0x6040, 1)
        assert e is not None
        assert e.access == "rw"


class TestSimulatedNode:
    def test_nmt_state_machine(self):
        node = SimulatedCanopenNode(node_id=1)
        assert node.state == "Pre-Operational"
        node.handle_nmt(0x02)
        assert node.state == "Operational"
        assert node.heartbeat_byte() == 5  # 0x05 = Operational heartbeat byte
        node.handle_nmt(0x03)
        assert node.state == "Stopped"
        node.handle_nmt(0x81)  # reset communication -> defaults + pre-op
        assert node.state == "Pre-Operational"

    def test_sdo_read_write(self):
        node = SimulatedCanopenNode()
        ok, val = node.sdo_read(0x2000, 0)
        assert ok and val == 1500
        assert node.sdo_write(0x2000, 0, 3000) is True
        ok, val = node.sdo_read(0x2000, 0)
        assert ok and val == 3000

    def test_sdo_readonly_rejected(self):
        node = SimulatedCanopenNode()
        assert node.sdo_write(0x1000, 0, 1) is False

    def test_sdo_unknown_object(self):
        node = SimulatedCanopenNode()
        ok, code = node.sdo_read(0xFFFF, 0)
        assert ok is False and code == 0x0609_0011
