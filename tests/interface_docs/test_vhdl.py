from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INTERFACE_DOCS_DIR = REPO_ROOT / "interface_docs"
if str(INTERFACE_DOCS_DIR) not in sys.path:
    sys.path.insert(0, str(INTERFACE_DOCS_DIR))


from generators.gen_vhdl import gen_vhdl_arch, gen_vhdl_package  # noqa: E402


def test_gen_vhdl_package_renders_addresses_and_bits(tmp_path: Path) -> None:
    source = tmp_path / "demo.yaml"
    source.write_text(
        """
types:
  RegisterTable:
    format: struct
    fields:
      status:
        format: bitfield
        fields:
          ACTIVE:
            size: 1
          ERROR:
            size: 1
      control:
        format: uint
        size: 32
        fpga:
          flags: [write]
""".strip(),
        encoding="utf-8",
    )
    rendered = gen_vhdl_package(
        {
            "source": "demo.yaml",
            "output": "demo_pkg.vhd",
            "target": "RegisterTable",
            "template_params": {"project": "Demo", "library": "demo", "package": "demo_regs"},
        },
        tmp_path,
    )
    assert "package demo_regs_pkg is" in rendered
    assert "constant C_TADDR_status" in rendered
    assert "subtype BITS_status is natural range 1 downto 0;" in rendered
    assert "subtype BITS_ACTIVE is natural range 0 downto 0;" in rendered


def test_gen_vhdl_arch_renders_entity_and_process(tmp_path: Path) -> None:
    source = tmp_path / "demo.yaml"
    source.write_text(
        """
types:
  RegisterTable:
    format: struct
    fields:
      status:
        format: uint
        size: 16
        fpga:
          flags: [read]
      control:
        format: uint
        size: 16
        fpga:
          flags: [write]
""".strip(),
        encoding="utf-8",
    )
    rendered = gen_vhdl_arch(
        {
            "source": "demo.yaml",
            "output": "demo_arch.vhd",
            "target": "RegisterTable",
            "template_params": {"library": "demo", "package": "demo_regs", "entity": "demo_entity"},
        },
        tmp_path,
    )
    assert "entity demo_entity is" in rendered
    assert "status : in std_logic_vector(BITS_status);" in rendered
    assert "control : out std_logic_vector(BITS_control)" in rendered
    assert "regTable_prs_rs : process(clk) is" in rendered
    assert "when C_TADDR_status =>" in rendered