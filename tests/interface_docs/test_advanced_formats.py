from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INTERFACE_DOCS_DIR = REPO_ROOT / "interface_docs"
if str(INTERFACE_DOCS_DIR) not in sys.path:
    sys.path.insert(0, str(INTERFACE_DOCS_DIR))


from generators.gen_advanced import (  # noqa: E402
    gen_c_od,
    gen_c_pdo_macro,
    gen_c_types,
    gen_py_alias,
    gen_xml_canether,
    gen_xml_od,
    gen_xml_to_yaml,
)


def test_gen_xml_canether_renders_canopen_xml() -> None:
    data = {
        "interface": {
            "canopen": {
                "object dictionary": {
                    "status": {
                        "temperature": {
                            "mlx": 0x310001,
                            "flags": ["read"],
                            "type": {"format": "uint", "size": 16},
                        }
                    }
                }
            }
        }
    }
    xml = gen_xml_canether(data, {}, "DemoBoard")
    assert '<ObjectDictionary type="DEMOBOARD" >' in xml
    assert '<group name="STATUS">' in xml
    assert 'name="TEMPERATURE"' in xml
    assert 'type="uint16"' in xml


def test_gen_c_types_renders_struct_and_enum(tmp_path: Path) -> None:
    source = tmp_path / "types.yaml"
    source.write_text(
        """
types:
  DemoEnum:
    format: enum
    size: 8
    values:
      IDLE: 0x0
      RUN: 0x1
  DemoStruct:
    format: struct
    codegen:
      c:
        naming: snake_case
    fields:
      currentValue:
        format: uint
        size: 16
""".strip(),
        encoding="utf-8",
    )
    rendered = gen_c_types({"source": "types.yaml", "output": "generated/demo_types.h"}, tmp_path)
    assert "typedef enum DemoEnum" in rendered
    assert "typedef struct demo_struct_tst" in rendered
    assert "uint16_t current_value;" in rendered


def test_gen_c_od_renders_mlx_macros(tmp_path: Path) -> None:
    source = tmp_path / "demo.yaml"
    source.write_text(
        """
interface:
  canopen:
    object dictionary:
      status:
        value_a:
          mlx: 0x310001
          flags: [read]
          type:
            format: uint
            size: 16
""".strip(),
        encoding="utf-8",
    )
    rendered = gen_c_od({"source": "demo.yaml", "output": "generated/demo_od.h"}, tmp_path)
    assert "#define STATUS_VALUE_A_MLX 0x310001" in rendered
    assert "#define STATUS_MLX(STRUCT)" in rendered
    assert "MLX_DEF_MACRO(STRUCT.value_a_u16, STATUS_VALUE_A_MLX, SDO_READ, SDO_NOWRITE)" in rendered


def test_gen_xml_od_renders_flat_xml_od(tmp_path: Path) -> None:
    source = tmp_path / "demo.yaml"
    source.write_text(
        """
interface:
  canopen:
    object dictionary:
      status:
        value_a:
          mlx: 0x310001
          flags: [read, write]
          type:
            format: uint
            size: 16
""".strip(),
        encoding="utf-8",
    )
    rendered = gen_xml_od({"source": "demo.yaml", "output": "generated/demo.xml", "template_params": {"od_name": "Demo"}}, tmp_path)
    assert '<ObjectDictionary type="Demo" >' in rendered
    assert 'name="VALUE_A" mlx="0x310001" type="uint16" RW="RW"' in rendered


def test_gen_py_alias_uses_template_params_od_name(tmp_path: Path) -> None:
    source = tmp_path / "demo.yaml"
    source.write_text(
        """
interface:
  title: Demo
  transport: canopen
  canopen:
    object dictionary:
      status:
        value_a:
          mlx: 0x310001
          flags: [read]
          type:
            format: uint
            size: 16
""".strip(),
        encoding="utf-8",
    )
    rendered = gen_py_alias({"source": "demo.yaml", "output": "generated/demo.py", "template_params": {"od_name": "AliasBoard"}}, tmp_path)
    assert "class AliasBoardOD:" in rendered


def test_gen_xml_to_yaml_converts_object_dictionary(tmp_path: Path) -> None:
    source = tmp_path / "demo.xml"
    source.write_text(
        """
<?xml version='1.0'?>
<ObjectDictionary type="Demo">
  <group name="STATUS">
    <ODE name="VALUE_A" mlx="0x310001" type="uint16" RW="RW"/>
  </group>
</ObjectDictionary>
""".strip(),
        encoding="utf-8",
    )
    rendered = gen_xml_to_yaml({"source": "demo.xml", "output": "generated/demo.yaml", "title": "Demo Interface"}, tmp_path)
    assert "title: Demo Interface" in rendered
    assert "transport: canopen" in rendered
    assert "value_a:" in rendered


def test_gen_c_pdo_macro_renders_defaults(tmp_path: Path) -> None:
    dep = tmp_path / "types.yaml"
    dep.write_text(
        """
types:
  DemoType:
    format: uint
    size: 16
""".strip(),
        encoding="utf-8",
    )
    source = tmp_path / "demo.yaml"
    source.write_text(
        """
interface:
  canopen:
    object dictionary:
      status:
        value_a:
          mlx: 0x310001
          type: EXT__DemoType
          flags: [read]
pdo:
  demo:
    1_tx:
      data:
        - status:value_a
""".strip(),
        encoding="utf-8",
    )
    rendered = gen_c_pdo_macro(
        {
            "source": "demo.yaml",
            "output": "generated/demo_pdo.h",
            "dependencies": ["types.yaml"],
        },
        tmp_path,
    )
    assert "#define DEMO_1_TX" in rendered
    assert "/* status:value_a mlx=0x310001 size=16 */" in rendered
    assert "#define DEMO_TX_PDO_DEFAULTS" in rendered