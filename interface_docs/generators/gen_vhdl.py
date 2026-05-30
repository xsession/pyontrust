"""Simplified VHDL package and architecture generators."""

from __future__ import annotations

import copy
import math
from pathlib import Path

from . import load_yaml


REFERENCE_PREFIX = "EXT__"


def gen_vhdl_package(target: dict, base_dir: Path) -> str:
    regs, params, file_name, addr_width = _prepare_vhdl_context(target, base_dir)
    package_name = params.get("package") or f"{params.get('library', 'work')}_top"
    lines = [
        "--------------------------------------------------------------------------------",
        "--",
        f"--  [Project]        : {params.get('project', '')}",
        f"--  [Library]        : {params.get('library', '')}",
        f"--  [Filename]       : {file_name}",
        "--",
        "--------------------------------------------------------------------------------",
        "",
        "library ieee;",
        "  use ieee.std_logic_1164.all;",
        "  use ieee.numeric_std.all;",
        "",
        f"package {package_name}_pkg is",
        f"  constant C_REGS_TADDR_WIDTH : integer := {addr_width};",
        "  constant C_REGS_TDATA_WIDTH : integer := 32;",
        "",
        "  type taddrArray_type is array (natural range <>) of std_logic_vector(C_REGS_TADDR_WIDTH - 1 downto 0);",
        "",
    ]

    for reg in regs:
        if reg["size"] <= 32:
            lines.append(
                f"  constant C_TADDR_{reg['name']} : std_logic_vector(C_REGS_TADDR_WIDTH - 1 downto 0) := std_logic_vector(to_unsigned({reg['bit_offset'] // 32}, C_REGS_TADDR_WIDTH));"
            )
        elif reg["size"] > 32:
            slots = math.ceil(reg["size"] / 32)
            assignments = ", ".join(
                f"std_logic_vector(to_unsigned({reg['bit_offset'] // 32 + index}, C_REGS_TADDR_WIDTH))"
                for index in range(slots)
            )
            lines.append(
                f"  constant C_TADDR_{reg['name']} : taddrArray_type(0 to {slots - 1}) := ({assignments});"
            )
    lines.append("")

    for reg in regs:
        fmt = reg["format"]
        if fmt == "bitfield":
            lines.append(f"  subtype BITS_{reg['name']} is natural range {reg['size'] - 1} downto 0;")
            for field in reg.get("fields", []):
                lines.append(
                    f"  subtype BITS_{field['name']} is natural range {field['bit_offset'] + field['size'] - 1} downto {field['bit_offset']};"
                )
        elif fmt in {"uint", "int", "enum"}:
            lines.append(f"  subtype BITS_{reg['name']} is natural range {reg['size'] - 1} downto 0;")
        elif fmt == "array":
            lines.append(
                f"  type {reg['name']}_type is array(0 to {reg['length'] - 1}) of std_logic_vector({reg['bit_width'] - 1} downto 0);"
            )
    lines.append("")

    for reg in regs:
        if reg["format"] == "enum":
            enum_values = ", ".join(reg["values"])
            lines.append(f"  type {reg['name']}_type is ({enum_values});")
    lines.append("")
    lines.append(f"end {package_name}_pkg;")
    return "\n".join(lines) + "\n"


def gen_vhdl_arch(target: dict, base_dir: Path) -> str:
    regs, params, _, addr_width = _prepare_vhdl_context(target, base_dir)
    package_name = params.get("package") or f"{params.get('library', 'work')}_top"
    entity_name = params.get("entity") or f"reg_table_{params.get('library', 'work')}"
    lines = [
        "--------------------------------------------------------------------------------",
        "-- Register table implementation",
        "--------------------------------------------------------------------------------",
        "library ieee;",
        "  use ieee.std_logic_1164.all;",
        "  use ieee.numeric_std.all;",
        f"library {params.get('library', 'work')};",
        f"  use {params.get('library', 'work')}.{package_name}_pkg.all;",
        "",
        f"entity {entity_name} is",
        "  port(",
        "    rst             : in  std_logic;",
        "    clk             : in  std_logic;",
        "    regTableWrNotRd : in  std_logic;",
        f"    regTableAddress : in  std_logic_vector({addr_width}-1 downto 0);",
        "    regTableWrData  : in  std_logic_vector(C_REGS_TDATA_WIDTH-1 downto 0);",
        "    regTableRdData  : out std_logic_vector(C_REGS_TDATA_WIDTH-1 downto 0);",
    ]

    port_lines: list[str] = []
    for reg in regs:
        direction = "out" if "write" in reg["fpga_flags"] else "in"
        if reg["format"] == "array":
            port_lines.append(f"    {reg['name']} : {direction} {reg['name']}_type;")
        else:
            port_lines.append(f"    {reg['name']} : {direction} std_logic_vector(BITS_{reg['name']});")
    if port_lines:
        port_lines[-1] = port_lines[-1].rstrip(";")
        lines.extend(port_lines)
    lines.extend(["  );", f"end entity {entity_name};", "", f"architecture txt of {entity_name} is", "  type registerTable_type is array(0 to 2**C_REGS_TADDR_WIDTH-1) of std_logic_vector(C_REGS_TDATA_WIDTH-1 downto 0);", "  signal registerTable : registerTable_type;", "begin", "", "  regTable_prs_rs : process(clk) is", "  begin", "    if rising_edge(clk) then", "      if rst = '1' then", "        regTableRdData <= (others => '0');", "      else", "        if regTableWrNotRd = '1' then", "          registerTable(to_integer(unsigned(regTableAddress))) <= regTableWrData;", "        else", "          case regTableAddress is"])

    for reg in regs:
        if "write" in reg["fpga_flags"]:
            continue
        if reg["size"] > 32:
            continue
        lines.append(f"            when C_TADDR_{reg['name']} =>")
        lines.append("              regTableRdData <= (others => '0');")
        lines.append(f"              regTableRdData(BITS_{reg['name']}) <= {reg['name']};")
    lines.extend(["            when others => regTableRdData <= registerTable(to_integer(unsigned(regTableAddress)));", "          end case;", "        end if;", "      end if;", "    end if;", "  end process;", "", "end architecture txt;"])
    return "\n".join(lines) + "\n"


def _prepare_vhdl_context(target: dict, base_dir: Path):
    source_data = load_yaml(base_dir / target["source"])
    types = copy.deepcopy(source_data.get("types", {}))
    for dep in target.get("dependencies", []):
        types.update(copy.deepcopy(load_yaml(base_dir / dep).get("types", {})))
    target_name = target["target"]
    target_type = copy.deepcopy(types[target_name])
    if target_type.get("format") != "struct":
        raise ValueError(f"VHDL target {target_name} must be a struct")

    regs = []
    bit_offset = 0
    for reg_name, reg_value in target_type.get("fields", {}).items():
        reg = _resolve_vhdl_type(reg_value, types)
        reg_size = _vhdl_size(reg)
        reg["name"] = reg_name
        reg["bit_offset"] = bit_offset
        reg["size"] = reg_size
        reg["fpga_flags"] = reg.get("fpga", {}).get("flags", [])
        if reg.get("format") == "bitfield":
            current_offset = 0
            reg["fields"] = [
                {
                    "name": field_name,
                    "size": field_data["size"],
                    "bit_offset": current_offset + (current_offset := current_offset) - current_offset,
                }
                for field_name, field_data in reg.get("fields", {}).items()
            ]
            field_offset = 0
            for field in reg["fields"]:
                field["bit_offset"] = field_offset
                field_offset += field["size"]
        if reg.get("format") == "enum":
            reg["values"] = list(reg.get("values", {}).keys())
        regs.append(reg)
        bit_offset += reg_size

    addr_width = max(1, math.ceil(math.log2(max(1, math.ceil(bit_offset / 32)))))
    return regs, target.get("template_params", {}), Path(target["output"]).name, addr_width


def _resolve_vhdl_type(type_ref: str | dict, types: dict) -> dict:
    if isinstance(type_ref, str) and type_ref.startswith(REFERENCE_PREFIX):
        return copy.deepcopy(types[type_ref[len(REFERENCE_PREFIX):]])
    if isinstance(type_ref, dict):
        return copy.deepcopy(type_ref)
    raise ValueError(f"Unsupported VHDL type reference: {type_ref}")


def _vhdl_size(type_data: dict) -> int:
    size = type_data.get("size")
    if isinstance(size, int):
        return size
    if type_data.get("format") == "array":
        return int(type_data["bit_width"]) * int(type_data["length"])
    if type_data.get("format") == "bitfield":
        return sum(int(field["size"]) for field in type_data.get("fields", {}).values())
    raise ValueError(f"Cannot derive VHDL size for {type_data}")