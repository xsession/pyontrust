#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""FloEFD-style CFD feature modules — Geometry, Meshing, Heat Transfer,
Parametric Study, and Post Processing.

These mirror the FloEFD training agenda (L1–L9) and provide in-memory
state plus JSON-serialisable dictionaries for the REST API.
"""

from __future__ import annotations

import logging
import math
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
#  Enumerations
# ═══════════════════════════════════════════════════════════════════════════

class AnalysisType(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class HeatTransferMode(str, Enum):
    CONDUCTION = "conduction"
    CONVECTION = "convection"
    RADIATION = "radiation"


class FluidType(str, Enum):
    LAMINAR = "laminar"
    TURBULENT = "turbulent"
    LAMINAR_AND_TURBULENT = "laminar_and_turbulent"


class MeshRefinementType(str, Enum):
    GLOBAL = "global"
    LOCAL = "local"
    SOLUTION_ADAPTIVE = "solution_adaptive"


class CellType(str, Enum):
    FLUID = "fluid"
    SOLID = "solid"
    PARTIAL = "partial"


class GoalType(str, Enum):
    GLOBAL = "global"
    SURFACE = "surface"
    VOLUME = "volume"
    POINT = "point"
    EQUATION = "equation"


class WallThermalCondition(str, Enum):
    ADIABATIC = "adiabatic"
    HEAT_FLUX = "heat_flux"
    HEAT_TRANSFER_COEFF = "heat_transfer_coeff"
    TEMPERATURE = "temperature"


class RadiationModel(str, Enum):
    NONE = "none"
    DISCRETE_ORDINATE = "discrete_ordinate"
    SURFACE_TO_SURFACE = "surface_to_surface"
    MONTE_CARLO = "monte_carlo"


class ConvergenceStatus(str, Enum):
    NOT_STARTED = "not_started"
    CONVERGING = "converging"
    CONVERGED = "converged"
    DIVERGING = "diverging"


# ═══════════════════════════════════════════════════════════════════════════
#  Data Classes
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class HeatTransferConfig:
    """L1 slide: Three modes of heat transfer."""
    conduction_enabled: bool = True
    convection_enabled: bool = True
    radiation_enabled: bool = False
    radiation_model: str = RadiationModel.NONE.value
    # Conduction: Q = kA(ΔT/Δx)
    default_solid_conductivity: float = 200.0  # W/m·K (Aluminum)
    # Convection: Q = hAΔT
    default_htc: float = 10.0  # W/m²·K
    # Radiation: Q = εσA(T_hot⁴ - T_cold⁴)
    default_emissivity: float = 0.9
    stefan_boltzmann: float = 5.67e-8  # W/m²·K⁴
    # L3 Analysis Type — physical features
    heat_conduction_in_solids: bool = True
    heat_conduction_solids_only: bool = False   # True = Heat Transfer Only (no flow)
    radiation_environment: bool = False
    radiation_solar: bool = False
    radiation_absorption: bool = False
    radiation_spectrum: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AnalysisConfig:
    """L3: Full analysis configuration — wizard settings + physics."""
    # Analysis type
    analysis_type: str = "internal"    # internal, external
    # Consider closed cavities
    exclude_cavities: bool = True      # Exclude cavities without flow conditions
    exclude_internal_space: bool = False  # External only: exclude internal space
    reference_axis: str = "X"          # X, Y, Z — default face reference for BCs
    # Physical features
    time_dependent: bool = False       # Transient analysis
    gravity_enabled: bool = False      # Natural convection
    gravity_x: float = 0.0
    gravity_y: float = -9.81
    gravity_z: float = 0.0
    rotation_enabled: bool = False     # Axisymmetric / rotating region
    rotation_rpm: float = 0.0
    rotation_axis: str = "Y"
    # Unit system
    unit_system: str = "SI (m-kg-s)"   # SI, CGS, FPS, IPS, NMM, USA
    temperature_unit: str = "K"         # K, C, F, R, Ra
    # Default fluid
    fluid_type: str = "laminar_and_turbulent"  # laminar, turbulent, laminar_and_turbulent
    selected_fluids: list = field(default_factory=lambda: ["air"])
    fluid_categories: list = field(default_factory=lambda: [
        "Gases", "Liquids", "Non-Newtonian Liquids",
        "Compressible Liquids", "Real Gases", "Steam", "Combustible Mixtures"
    ])
    flow_options_cavitation: bool = False
    flow_options_humidity: bool = False
    # Default solid
    selected_solids: list = field(default_factory=lambda: ["aluminum"])
    solid_categories: list = field(default_factory=lambda: [
        "Alloys", "Building Materials", "Ceramics", "Glasses and Minerals",
        "IC Packages", "Laminates", "Metals", "Non-Isotropic",
        "Polymers", "Semiconductors", "User Defined"
    ])
    # Wall conditions (defaults)
    wall_thermal_condition: str = "adiabatic"  # adiabatic, htc, heat_gen_rate, surface_heat_gen, temperature
    wall_radiative_surface: str = "blackbody"
    wall_outer_radiative: str = "blackbody"
    wall_roughness: float = 0.0      # micrometers (Rz)
    # Initial conditions
    ic_pressure: float = 101325.0     # Pa
    ic_temperature: float = 293.2     # K
    ic_velocity_x: float = 0.0
    ic_velocity_y: float = 0.0
    ic_velocity_z: float = 0.0
    ic_turbulence_intensity: float = 0.01
    ic_turbulence_length: float = 0.001
    ic_solid_temperature: float = 293.2
    ic_definition: str = "user_defined"  # user_defined, transferred
    # Results and Geometry Resolution
    result_resolution_level: int = 3   # 1-8 slider
    manual_gap_size: bool = False
    min_gap_size: float = 0.0
    manual_wall_thickness: bool = False
    min_wall_thickness: float = 0.0
    narrow_channel_refinement: bool = False
    optimize_thin_walls: bool = True
    # Project info
    project_name: str = "Project"
    project_comments: str = ""
    configuration_name: str = "Default"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GeometryPart:
    """L2: Geometry Preparation — a single geometry part."""
    id: str = ""
    name: str = ""
    file_path: str = ""
    file_type: str = ""  # stl, step, iges, obj, parasolid, sat
    file_origin: str = "neutral"  # native, neutral
    cad_source: str = ""  # solidworks, creo, catia_v5, nx, other
    num_faces: int = 0
    num_vertices: int = 0
    bounding_box: dict = field(default_factory=lambda: {
        "min": [0, 0, 0], "max": [0, 0, 0]
    })
    is_fluid_region: bool = False
    is_solid_region: bool = False
    is_surface_body: bool = False  # True = surface import (needs knit/thicken)
    suppress: bool = False       # Removes from CFD but keeps in CAD
    disabled: bool = False       # Visible in CAD but invisible to CFD
    replaced: bool = False       # Complex → simplified replacement
    replacement_note: str = ""   # e.g. "Porous media" or "Simple box"
    transparency: float = 1.0
    color: str = "#89b4fa"
    # Diagnostics
    faulty_faces: list = field(default_factory=list)    # [{"id":..., "type":"gap"|"faulty", "healed":bool}]
    gaps: list = field(default_factory=list)             # [{"id":..., "faces": [...], "healed":bool}]
    has_errors: bool = False
    is_watertight: bool = True
    diagnostics_run: bool = False
    # Lids
    lids: list = field(default_factory=list)  # [{"id":..., "name":..., "opening_type":"inlet"|"outlet"}]
    # Tags for workflow
    tags: list = field(default_factory=list)   # e.g. ["fastener","cosmetic","insignificant"]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GeometryCheckResult:
    """Result from a geometry check / import diagnostics run."""
    part_id: str = ""
    part_name: str = ""
    is_solid: bool = True
    is_watertight: bool = True
    faulty_face_count: int = 0
    gap_count: int = 0
    invalid_contact_count: int = 0
    fluid_region_detected: bool = False
    needs_lids: bool = False
    errors: list = field(default_factory=list)       # ["Face <4> has gap", ...]
    warnings: list = field(default_factory=list)      # ["Point contact at ...", ...]
    recommendations: list = field(default_factory=list)  # ["Create lid on opening 1", ...]
    healed_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ComputationalDomain:
    """L3: Analysis Setup — computational domain definition."""
    x_min: float = -0.5
    x_max: float = 0.5
    y_min: float = -0.5
    y_max: float = 0.5
    z_min: float = -0.5
    z_max: float = 0.5
    symmetry_x: bool = False
    symmetry_y: bool = False
    symmetry_z: bool = False

    @property
    def volume(self) -> float:
        return (self.x_max - self.x_min) * (self.y_max - self.y_min) * (self.z_max - self.z_min)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["volume"] = self.volume
        return d


@dataclass
class BoundaryConditionFloEFD:
    """L4: Boundary condition (FloEFD-style)."""
    id: str = ""
    name: str = ""
    bc_type: str = "wall"  # wall, inlet, outlet, opening, symmetry, periodic
    faces: list = field(default_factory=list)
    # Velocity inlet
    velocity: list = field(default_factory=lambda: [0, 0, 0])
    mass_flow_rate: float = 0.0
    volume_flow_rate: float = 0.0
    # Pressure
    pressure: float = 101325.0
    # Temperature
    temperature: float = 293.15
    # Wall
    wall_thermal: str = WallThermalCondition.ADIABATIC.value
    wall_heat_flux: float = 0.0
    wall_htc: float = 10.0
    wall_temperature: float = 293.15
    wall_roughness: float = 0.0
    # Radiation
    emissivity: float = 0.9
    # Flow Opening sub-type
    flow_opening_type: str = "inlet_mass_flow"  # inlet_mass_flow, inlet_volume_flow, inlet_velocity, outlet_mass_flow, outlet_volume_flow, outlet_velocity
    # Pressure Opening sub-type
    pressure_type: str = "environment"  # environment, static, total
    # Wall sub-type
    wall_type: str = "real"  # real, ideal, outer
    # Wall motion
    wall_motion_enabled: bool = False
    wall_linear_velocity: float = 0.0
    wall_angular_velocity: float = 0.0
    wall_motion_axis: str = "X"
    # Turbulence
    boundary_layer: str = "turbulent"  # turbulent, laminar
    fully_developed_flow: bool = False
    # Options
    create_associated_goals: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════
#  L4a: Feature dataclasses (Standard FloEFD Features)
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ComponentControl:
    """L4a: Component Control — enable/disable CAD components for CFD."""
    id: str = ""
    name: str = ""
    enabled: bool = True
    # Disabled parts can still be used for Volume Heat Sources, Porous Media,
    # Rotating Regions, Local Initial Mesh, Volume/Surface Goals
    use_for_heat_source: bool = False
    use_for_porous_media: bool = False
    use_for_rotating_region: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FluidSubdomain:
    """L4a: Fluid Subdomain — different fluid in a closed cavity."""
    id: str = ""
    name: str = ""
    selection: str = ""  # face/body selection
    coordinate_system: str = "Global"
    reference_axis: str = "X"
    # Fluids
    fluid_type: str = "Gases / Real Gases / Steam"
    fluids: list = field(default_factory=list)  # e.g. ["Propane"]
    # Flow parameters
    velocity: list = field(default_factory=lambda: [0, 0, 0])
    # Thermodynamic parameters
    thermo_pair: str = "P-T"  # P-T, P-p, T-p
    pressure: float = 101325.0
    temperature: float = 293.15
    # Turbulence
    turbulence_intensity: float = 0.01
    turbulence_length: float = 0.001

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RotatingRegion:
    """L4a: Rotating Region — for fans, pumps, impellers."""
    id: str = ""
    name: str = ""
    selection: str = ""
    # Must be axisymmetric
    rotation_type: str = "centrifugal"  # centrifugal, axial
    angular_velocity_rpm: float = 0.0
    translation_velocity: float = 0.0
    rotation_axis: str = "X"  # X, Y, Z
    # Stator/Rotor walls
    stator_faces: list = field(default_factory=list)
    rotor_faces: list = field(default_factory=list)
    # Component will be disabled in Component Control
    disabled_in_cc: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SolidMaterial:
    """L4a: Solid Material — applied to parts/bodies."""
    id: str = ""
    name: str = "Aluminum"
    # Properties (temperature-dependent)
    density: float = 2688.9  # kg/m³
    specific_heat: float = 900.0  # J/(kg·K)
    conductivity_type: str = "isotropic"  # isotropic, unidirectional, axisymmetric, orthotropic
    thermal_conductivity: float = 237.0  # W/(m·K)
    electrical_conductivity: str = "conductor"  # conductor, insulator
    resistivity: float = 2.65e-8  # Ohm·m
    melting_temperature: float = 933.4  # K
    # For orthotropic: coord system needed
    coordinate_system: str = "Global"
    # Assigned bodies
    assigned_bodies: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FanFeature:
    """L4a: Fan — Axial, Radial, or Fan Curve."""
    id: str = ""
    name: str = "New Fan"
    fan_type: str = "axial"  # axial, radial, fan_curve
    selection: str = ""
    # Fan curve
    reference_density: float = 1.2  # kg/m³
    flow_rate_type: str = "mass_flow_rate"  # mass_flow_rate, volume_flow_rate
    curve_data: list = field(default_factory=list)  # [{flow_rate, pressure_diff}]
    # Rotor
    rotor_speed: float = 0.0  # rad/s
    outer_diameter: float = 0.0  # m
    hub_diameter: float = 0.0  # m
    rotation_direction: str = "clockwise"
    # Transient toggle
    toggle_mode: str = "always_on"  # always_on, goal_dependent
    toggle_goal: str = ""
    toggle_condition: str = "on_above"  # on_above, off_above, on_below, off_below
    control_value: float = 0.0
    dead_band: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HeatSourceFeature:
    """L4a: Heat Source — Volume or Surface source."""
    id: str = ""
    name: str = ""
    source_type: str = "volume"  # volume, surface
    selection: str = ""
    # Parameters
    parameter_type: str = "heat_generation_rate"  # heat_generation_rate, volumetric_heat_gen, fixed_temperature
    heat_generation_rate: float = 0.0  # W
    volumetric_heat_gen: float = 0.0  # W/m³
    fixed_temperature: float = 293.15  # K (volume only)
    # Multiple bodies: power divided by number of bodies (not volume)
    # Transient toggle
    toggle_mode: str = "always_on"
    toggle_goal: str = ""
    toggle_condition: str = "on_above"
    control_value: float = 0.0
    dead_band: float = 1.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RadiativeSurface:
    """L4a: Radiative Surface — wall or wall-to-ambient radiation."""
    id: str = ""
    name: str = ""
    selection: str = ""
    surface_type: str = "wall"  # wall (within model), wall_to_ambient
    # Emissivity (temperature-dependent in full version)
    emissivity: float = 0.9
    # Specularity coefficient — fraction of specularly reflected radiation
    specularity: float = 0.0
    # Solar absorptance
    solar_absorptance: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RadiationSource:
    """L4a: Radiation Source — radiation through openings."""
    id: str = ""
    name: str = ""
    selection: str = ""
    radiation_type: str = "diffusive"  # diffusive, solar
    # Diffusive: blackbody (emissivity=1) at Power/Intensity/Temperature
    parameter_type: str = "power"  # power, intensity, temperature
    power: float = 0.0  # W
    intensity: float = 0.0  # W/m²
    temperature: float = 5778.0  # K (sun surface)
    # Solar: directional radiation
    direction: list = field(default_factory=lambda: [0, -1, 0])  # X, Y, Z

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ContactResistance:
    """L4a: Contact Resistance — thermal resistance at solid/solid or solid/fluid boundaries."""
    id: str = ""
    name: str = ""
    selection: str = ""
    resistance_type: str = "resistance"  # resistance, material_thickness
    # Rc = dc / λc (thickness / conductivity)
    thermal_resistance: float = 0.0  # m²·K/W
    contact_thickness: float = 0.0  # m
    contact_conductivity: float = 0.0  # W/(m·K)
    contact_material: str = ""
    apply_solid_solid_only: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ThermoelectricCooler:
    """L4a: TEC — Peltier effect device."""
    id: str = ""
    name: str = ""
    selection: str = ""
    hot_side_face: str = ""
    cold_side_face: str = ""
    # Peltier parameters
    max_pumped_heat: float = 0.0  # W — Qmax at imax, zero ΔT
    max_temperature_drop: float = 0.0  # K — ΔTmax
    max_current: float = 0.0  # A — imax
    max_voltage: float = 0.0  # V — Vmax at imax
    # Operating point
    operating_current: float = 0.0  # A

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HeatSinkSimulation:
    """L4a: Heat Sink Simulation — compact model."""
    id: str = ""
    name: str = ""
    selection: str = ""
    # Fan + heatsink from Engineering Database
    fan_db_name: str = ""
    heatsink_db_name: str = ""
    heat_generation_rate: float = 0.0  # W
    inlet_surface: str = ""
    outlet_surfaces: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PorousMedia:
    """L4a: Porous Media — replace complex geometry with effective pressure drop."""
    id: str = ""
    name: str = ""
    selection: str = ""
    # Applied to disabled body
    porosity: float = 0.5  # volume fraction of interconnected pores
    permeability_type: str = "isotropic"  # isotropic, unidirectional, axisymmetric, orthotropic
    # Resistance k = -grad(P) / (ρV)
    resistance: float = 0.0  # 1/m
    # Direction (for non-isotropic)
    direction_axis: str = "X"
    coordinate_system: str = "Global"
    # Thermal properties
    initial_temperature: float = 293.15
    apply_source_to: str = "porous_matrix_only"  # porous_matrix_only, porous_matrix_and_fluid

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PerforatedPlate:
    """L4a: Perforated Plate — thin plate with multiple holes."""
    id: str = ""
    name: str = ""
    selection: str = ""
    # Free area ratio
    free_area_ratio: float = 0.4  # 0-1
    hole_shape: str = "round"  # round, rectangular, polygon
    hole_diameter: float = 0.005  # m (for round)
    hole_width: float = 0.005  # m (for rectangular)
    hole_height: float = 0.005  # m (for rectangular)
    plate_thickness: float = 0.001  # m
    # Pressure drop coefficient auto-calculated
    # Can be added to Environment Pressure BC or Fan BC

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ThermalJoint:
    """L4a: Thermal Joint — heat transfer between disjoint parts."""
    id: str = ""
    name: str = ""
    face_a: str = ""
    face_b: str = ""
    joint_type: str = "htc"  # htc, thermal_resistance
    heat_transfer_coefficient: float = 0.0  # W/(m²·K)
    thermal_resistance: float = 0.0  # m²·K/W
    # Faces become thermally insulated from surrounding medium

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InitialConditionLocal:
    """L4a: Initial Condition — local override per face/body."""
    id: str = ""
    name: str = ""
    selection: str = ""
    coordinate_system: str = "Global"
    reference_axis: str = "X"
    disable_solid_components: bool = False
    # Flow parameters
    velocity: list = field(default_factory=lambda: [0, 0, 0])
    # Thermodynamic
    thermo_pair: str = "P-T"
    pressure: float = 101325.0
    temperature: float = 283.15  # 10 °C

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EngineeringDatabase:
    """L4a: Engineering Database — categories of pre-defined and user-defined features."""
    categories: list = field(default_factory=lambda: [
        "Cities", "Contact Electrical Resistances", "Contact Thermal Resistances",
        "Custom - Visualization Parameters", "Fans", "Heat Sinks", "LEDs",
        "Materials", "Perforated Plates", "Porous Media", "Printed Circuit Boards",
        "Radiation Spectra", "Radiative Surfaces", "Thermoelectric Coolers",
        "Tracers", "Two-Resistor Components", "Units",
    ])
    material_subcategories: list = field(default_factory=lambda: [
        "Combustible Mixtures", "Compressible Liquids", "Gases", "Liquids",
        "Non-Newtonian Liquids", "Real Gases", "Solids", "Steam",
    ])
    solid_subcategories: list = field(default_factory=lambda: [
        "Pre-Defined", "User Defined",
    ])
    # Database is in XML format, can be on a central server
    database_path: str = ""
    user_database_path: str = ""
    external_database_dir: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LocalMeshRegion:
    """L5: Local Initial Mesh region."""
    id: str = ""
    name: str = ""
    target_type: str = "surface"  # surface, edge, vertex, cad_body
    target_name: str = ""
    body_shape: str = "cuboid"  # cuboid, cylinder, sphere
    equidistant_refinement_enabled: bool = False
    equidistant_level: int = 2  # 0-9
    cell_size_x: float = 0.0
    cell_size_y: float = 0.0
    cell_size_z: float = 0.0
    enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MeshStudyEntry:
    """L5: Mesh sensitivity study data point."""
    mesh_count: int = 0
    dp_value: float = 0.0
    percent_delta: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MeshSettings:
    """L5: Meshing — FloEFD-style mesh configuration.

    Comprehensive coverage of all Lecture 5 (Meshing) slides:
      1. Base Mesh Settings (Global Mesh Settings dialog)
      2. Basic Mesh (Manual mode)
      3. Control Planes
      4. Solid/Fluid Interface (Advanced Refinement)
      5. Refining Cells
      6. Narrow Channels
      7. Close Thin Slots
      8. Display Refinement Level
      9. Solution Adaptive Meshing
     10. Local Initial Mesh
     11. Mesh Study / Sensitivity
     12. Statistics & Solver Progress
    """

    # ── 1. Base Mesh Settings (Global Mesh Settings dialog) ──────────────
    mesh_type: str = "automatic"  # "automatic" or "manual"
    initial_mesh_level: int = 3  # 1-8 slider
    cell_size: float = 0.0  # auto-computed from geometry bounding box
    advanced_channel_refinement: bool = False
    show_basic_mesh: bool = False

    # ── 2. Basic Mesh (Manual mode, N cells in each axis) ────────────────
    nx: int = 10  # cells in X
    ny: int = 10  # cells in Y
    nz: int = 10  # cells in Z
    keep_aspect_ratio: bool = True
    show_mesh: bool = False

    # ── 3. Control Planes ────────────────────────────────────────────────
    # Each entry: {axis: "X"/"Y"/"Z", min: float, max: float,
    #              type: "ratio"/"size"/"number", number: int,
    #              size: float, ratio: float}
    control_planes: list = field(default_factory=list)

    # ── 4. Solid/Fluid Interface — Advanced Refinement ───────────────────
    small_solid_feature_level: int = 2  # 0-9, "most critical slider"
    curvature_refinement_level: int = 1  # 0-9
    curvature_critical_angle: float = 0.318  # rad (~18.2°)
    tolerance_refinement_level: int = 0  # 0-9
    tolerance_value: float = 0.002325  # m

    # ── 5. Refining Cells ────────────────────────────────────────────────
    fluid_cells_refinement: int = 0  # 0-9 slider
    solid_cells_refinement: int = 0  # 0-9 slider
    partial_cells_refinement: int = 1  # 0-9 slider

    # ── 6. Narrow Channels ───────────────────────────────────────────────
    narrow_channels_enabled: bool = True
    narrow_channels_num_cells: int = 5
    narrow_channels_refinement_level: int = 2  # 0-9 slider
    narrow_channels_min_tolerance: float = 0.0  # m, 0 = auto
    narrow_channels_max_tolerance: float = 0.0  # m, 0 = auto

    # ── 7. Close Thin Slots ──────────────────────────────────────────────
    close_thin_slots_enabled: bool = False
    close_thin_slots_tolerance: float = 0.0  # m

    # ── 8. Display Refinement Level ──────────────────────────────────────
    display_refinement_enabled: bool = False
    display_refinement_level: int = 0  # 0-9 slider
    display_use_all_components: bool = True
    display_selected_components: list = field(default_factory=list)

    # ── 9. Solution Adaptive Meshing ─────────────────────────────────────
    solution_adaptive_enabled: bool = False
    adaptive_refinement_level: int = 4
    adaptive_max_cells: int = 2_000_000
    adaptive_strategy: str = "periodic"  # "periodic", "tabular", "manual"
    adaptive_relaxation_interval: float = 0.2
    adaptive_start: float = 2.0  # in travels
    adaptive_period: float = 1.0  # in travels

    # ── 10. Local Initial Mesh (list of LocalMeshRegion) ─────────────────
    local_meshes: list = field(default_factory=list)

    # ── 11. Mesh Study / Sensitivity (list of MeshStudyEntry) ────────────
    mesh_study_entries: list = field(default_factory=list)

    # ── 12. Statistics & Solver Progress ─────────────────────────────────
    total_cells: int = 0
    fluid_cells: int = 0
    solid_cells: int = 0
    partial_cells: int = 0
    iterations: int = 0
    travels: float = 0.0
    iterations_per_travel: int = 0
    cpu_time: float = 0.0  # seconds
    calculation_time_left: float = 0.0  # seconds

    # Legacy convenience aliases
    min_gap_size: float = 0.001  # m (used in analysis-setup round-trip)
    min_wall_thickness: float = 0.001  # m
    result_resolution_level: int = 3  # 1-8
    optimize_thin_walls: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Goal:
    """L4b: FloEFD Goals — convergence & monitoring targets.

    Types:  Global (GG), Point (PG), Surface (SG), Volume (VG), Equation (EG).
    Each goal tracks a physical parameter with Min/Av/Max/Bulk-Av criteria
    and can be flagged for convergence or monitoring.
    """
    id: str = ""
    name: str = ""
    goal_type: str = GoalType.SURFACE.value  # global, surface, volume, point, equation
    parameter: str = "temperature"
    # ── Selection context ─────────────────────────────────────────────
    component: str = ""             # face / body / point name
    faces: list = field(default_factory=list)          # face ids for surface goals
    bodies: list = field(default_factory=list)          # body ids for volume goals
    # ── Point goal coordinates ────────────────────────────────────────
    point_x: float = 0.0
    point_y: float = 0.0
    point_z: float = 0.0
    point_method: str = "coordinates"  # coordinates, pick_from_screen, reference
    # ── Criteria columns (checkboxes in FloEFD UI) ────────────────────
    use_min: bool = False
    use_av: bool = False
    use_max: bool = False
    use_bulk_av: bool = False
    use_for_convergence: bool = True
    # ── Name template ─────────────────────────────────────────────────
    name_template: str = "SG <Parameter> <Number>"
    # ── Convergence / finish settings ─────────────────────────────────
    convergence_mode: str = "auto"    # auto, manual
    tolerance_value: float = 0.0      # manual tolerance (0 = auto)
    delta_criteria: float = 0.01      # convergence delta
    target_value: float = 0.0
    # ── Equation goal expression ──────────────────────────────────────
    expression: str = ""              # e.g. "{SG Pressure 1} - {SG Pressure 2}"
    dimensionality: str = "No units"  # No units, Pa, K, m/s, W, ...
    equation_parameters: list = field(default_factory=list)  # input parameter refs
    # ── Surface goal filters ──────────────────────────────────────────
    filter_out_of_domain: bool = False
    filter_outer_faces: bool = False
    filter_fluid_contacting: bool = False
    keep_outer_and_fluid: bool = False
    # ── Associated goals (auto-created from features) ─────────────────
    is_associated: bool = False       # true if auto-generated from BC / heat source
    source_feature_type: str = ""     # "boundary_condition", "volume_source", etc.
    source_feature_id: str = ""
    # ── Live tracking ─────────────────────────────────────────────────
    current_value: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    averaged_value: float = 0.0
    bulk_averaged_value: float = 0.0
    is_converged: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


# ── L4b: Finish Conditions ────────────────────────────────────────────

@dataclass
class FinishConditions:
    """Calculation Control Options → Finish tab (L4b slide)."""
    min_refinement_number: int = 0
    min_refinement_enabled: bool = True
    max_iterations: int = 100
    max_iterations_enabled: bool = False
    max_calculation_time: float = 36000.0   # seconds
    max_calculation_time_enabled: bool = False
    max_travels: int = 4
    max_travels_mode: str = "auto"          # auto, manual
    max_travels_enabled: bool = True
    goals_convergence_enabled: bool = True
    analysis_interval: float = 0.5          # travels
    analysis_interval_mode: str = "auto"    # auto, manual
    # Per-goal criteria overrides
    goal_criteria: list = field(default_factory=list)  # [{goal_id, enabled, mode, value}]

    def to_dict(self) -> dict:
        return asdict(self)


# ── L4b: Associated Goals Configuration ──────────────────────────────

@dataclass
class AssociatedGoalsConfig:
    """FloEFD Options → Automatic Goals tree (L4b slide)."""
    create_associated_goals: bool = False
    # Boundary Condition goals
    bc_inlet_mass_flow: bool = True
    bc_inlet_volume_flow: bool = True
    bc_inlet_velocity: bool = True
    bc_inlet_mach_number: bool = True
    bc_outlet_mass_flow: bool = True
    bc_outlet_volume_flow: bool = True
    bc_outlet_velocity: bool = True
    bc_outlet_mach_number: bool = True
    bc_static_pressure: bool = True
    bc_environment_pressure: bool = True
    bc_real_wall: bool = True
    bc_outer_wall: bool = True
    bc_ideal_wall: bool = True
    # Surface Source goals
    ss_heat_transfer_rate: bool = True
    ss_heat_generation_rate: bool = True
    ss_surface_heat_generation_rate: bool = True
    # Volume Source goals
    vs_volumetric_heat_generation_rate: bool = True
    vs_temperature: bool = True
    vs_heat_generation_rate: bool = True
    # Radiative Surface goals
    rs_wall: bool = True
    rs_symmetry: bool = True
    rs_wall_to_ambient: bool = True
    rs_non_radiating_wall: bool = True
    # Fan goals
    fan_external_inlet: bool = True
    fan_external_outlet: bool = True
    fan_internal: bool = True
    # Other
    other_two_resistor: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunConfig:
    """L6: Run dialog configuration."""
    mesh_enabled: bool = True
    solve_enabled: bool = True
    new_calculation: bool = True          # True=new, False=continue
    take_previous_results: bool = False
    run_at: str = "this_computer"         # this_computer, network
    close_cad: bool = False
    cpu_count: int = 4
    load_results: bool = True
    batch_results: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PreviewPlot:
    """L6: Preview plot settings — view results during solving."""
    id: str = ""
    name: str = "Preview 1"
    # Definition tab
    plane_name: str = "Right Plane"       # Right Plane, Front Plane, Top Plane, custom
    plane_offset: float = 0.005
    min_max_mode: str = "auto"            # auto, manual
    mode: str = "contours"                # contours, isolines, velocity_vectors
    # Settings tab
    parameter: str = "Velocity"
    settings_min: float = 0.0
    settings_max: float = 100.0
    max_velocity: float = 100.0
    vector_spacing: float = 0.5           # 0=min, 1=max
    # Image Attributes tab
    image_size: str = "640x480"           # 400x300, 640x480, 800x600, 1000x1000, 2000x2000, user_defined
    x_size: int = 640
    y_size: int = 480
    flip_horizontal: bool = False
    flip_vertical: bool = False
    rotate_90: bool = False
    # Options tab
    auto_update: bool = True
    auto_caption: bool = True
    auto_save: bool = False
    show_box: bool = True
    display_mesh: bool = False
    interpolate_results: bool = True
    caption: str = ""
    auto_name_prefix: str = ""
    auto_save_step: int = 1               # iterations
    # Region tab
    region_x_min: float = -0.001
    region_x_max: float = 0.616
    region_y_min: float = -0.415
    region_y_max: float = 0.415
    region_z_min: float = -0.415
    region_z_max: float = 0.415
    enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class GoalPlotConfig:
    """L6: Goal Plot settings — monitor goal convergence during solving."""
    id: str = ""
    name: str = "Goal plot 1"
    selected_goals: list = field(default_factory=list)  # list of goal ids
    # Options
    x_axis_units: str = "iterations"      # iterations, physical_time
    scale_mode: str = "absolute"          # absolute, normalised
    display_value: str = "current"        # current, minimum, maximum, average
    logarithmic_scale: bool = False
    show_titles: bool = True
    show_analysis_interval: bool = False
    show_convergence_history: bool = False
    # Numerical settings
    manual_min_enabled: bool = False
    manual_min: float = 0.0
    manual_max_enabled: bool = False
    manual_max: float = 100.0
    plot_length: float = 0.5              # min..max slider
    length_scale: float = 1.51356

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SolverLogEntry:
    """L6: Solver log entry."""
    event: str = ""
    iteration: int = 0
    time: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SolverConfig:
    """L6: Solving configuration (FloEFD-style)."""
    max_iterations: int = 200
    auto_convergence: bool = True
    convergence_criterion: float = 1e-4
    finish_conditions: str = "goals"      # goals, iterations, both
    # Navier-Stokes solver settings
    turbulence_model: str = "k-epsilon"   # k-epsilon, k-omega, laminar
    wall_function: str = "modified"       # standard, modified (FloEFD-unique)
    # Relaxation
    velocity_relaxation: float = 0.7
    pressure_relaxation: float = 0.3
    temperature_relaxation: float = 0.8
    # Status
    current_iteration: int = 0
    convergence_status: str = ConvergenceStatus.NOT_STARTED.value
    residuals: dict = field(default_factory=dict)
    # Run config
    run_config: RunConfig = field(default_factory=RunConfig)
    # Preview plots
    preview_plots: list = field(default_factory=list)
    # Goal plots
    goal_plots: list = field(default_factory=list)
    # Solver log
    solver_log: list = field(default_factory=list)
    # Solver info window fields
    status_text: str = "Not started"
    fluid_cells_info: int = 0
    partial_cells_info: int = 0
    last_iteration_finished: str = ""
    cpu_time_per_iteration: str = ""
    travels: float = 0.0
    iterations_per_travel: int = 0
    cpu_time: str = ""
    calculation_time_left: str = ""
    # Warnings
    warnings: list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class PostProcessingCutPlot:
    """L7: Post Processing — cut plot definition (enhanced)."""
    id: str = ""
    name: str = ""
    parameter: str = "temperature"  # temperature, pressure, velocity, density, mach, total_pressure, etc.
    plane: str = "XY"  # XY, XZ, YZ, custom
    offset: float = 0.0
    # Display modes
    show_contours: bool = True
    show_isolines: bool = False
    show_vectors: bool = False
    show_streamlines: bool = False
    show_mesh: bool = False
    # Contour settings
    min_value: float = 0.0
    max_value: float = 100.0
    num_levels: int = 20
    color_map: str = "rainbow"  # rainbow, thermal, blue-red, grayscale, diverging
    use_cad_geometry: bool = True
    # Isoline settings
    isoline_count: int = 10
    isoline_color: str = "#000000"
    isoline_width: float = 1.0
    # Vector settings
    vector_spacing: float = 5.0
    vector_size: float = 1.0
    vector_color_by_parameter: bool = True
    # Streamline settings
    streamline_density: int = 20
    streamline_thickness: float = 1.0
    # Advanced display
    display_3d_profile: bool = False
    profile_direction: str = "normal"  # normal, X, Y, Z
    profile_offset: float = 0.0
    display_boundary_layer: bool = False
    display_outlines: bool = True
    interpolate: bool = True
    dynamic_drag: bool = False
    transparency: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SurfacePlot:
    """L7: Post Processing — surface plot (enhanced)."""
    id: str = ""
    name: str = ""
    parameter: str = "temperature"
    surface_name: str = ""
    # Display modes
    show_contours: bool = True
    show_isolines: bool = False
    show_vectors: bool = False
    show_streamlines: bool = False
    show_mesh: bool = False
    # Contour settings
    min_value: float = 0.0
    max_value: float = 100.0
    num_levels: int = 20
    color_map: str = "rainbow"
    use_cad_geometry: bool = True
    # Isoline settings
    isoline_count: int = 10
    isoline_color: str = "#000000"
    # Vector settings
    vector_spacing: float = 5.0
    vector_size: float = 1.0
    # Offset/Tip
    offset: float = 0.0
    offset_tip: bool = False
    transparency: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Isosurface:
    """L7: Post Processing — isosurface."""
    id: str = ""
    name: str = ""
    parameter: str = "temperature"
    # Up to 3 iso-values
    value1: float = 0.0
    value1_enabled: bool = True
    value2: float = 0.0
    value2_enabled: bool = False
    value3: float = 0.0
    value3_enabled: bool = False
    # Appearance
    color_map: str = "rainbow"
    min_value: float = 0.0
    max_value: float = 100.0
    show_mesh: bool = False
    transparency: float = 0.0
    use_cad_geometry: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FlowTrajectory:
    """L7: Post Processing — flow trajectory / particle trace."""
    id: str = ""
    name: str = ""
    parameter: str = "velocity"  # color-by parameter
    # Starting points
    start_mode: str = "surface"  # surface, pick_point, coordinates
    start_surface: str = ""
    start_x: float = 0.0
    start_y: float = 0.0
    start_z: float = 0.0
    # Trajectory settings
    number: int = 20
    in_plane: bool = False
    constraints: str = "both"  # ahead, behind, both
    max_length: float = 1000.0
    time_limit: float = 100.0
    # Appearance
    appearance: str = "lines"  # pipes, lines, lines_arrows, bands, spheres, arrows, arrows_flat
    thickness: float = 1.0
    color_map: str = "rainbow"
    min_value: float = 0.0
    max_value: float = 100.0
    use_cad_geometry: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParticleStudy:
    """L7: Post Processing — particle study visualization."""
    id: str = ""
    name: str = ""
    visualize: str = "erosion"  # erosion, accretion, absorption
    statistical_study: bool = False
    # Display
    parameter: str = "velocity"
    appearance: str = "spheres"  # spheres, lines, points
    color_map: str = "rainbow"
    min_value: float = 0.0
    max_value: float = 100.0
    show_mesh: bool = False
    # Wizard state
    wizard_step: int = 1  # 1=type, 2=settings, 3=display

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PointParameter:
    """L7: Post Processing — point parameter extraction."""
    id: str = ""
    name: str = ""
    selection_mode: str = "coordinates"  # reference, pattern, pick, coordinates
    # Points
    points: list = field(default_factory=list)  # [{x,y,z,label}]
    # Parameters to extract
    parameters: list = field(default_factory=lambda: ["temperature", "pressure", "velocity"])
    coordinate_system: str = "global"  # global, local
    export_to_excel: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SurfaceParameter:
    """L7: Post Processing — surface parameter extraction."""
    id: str = ""
    name: str = ""
    surfaces: list = field(default_factory=list)  # surface names
    # Parameters to extract
    parameters: list = field(default_factory=lambda: ["temperature", "heat_flux", "htc"])
    # HTC determination
    htc_determination: str = "default"  # default, manual_ref_temp
    htc_reference_temp: float = 293.15
    export_to_excel: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class VolumeParameter:
    """L7: Post Processing — volume parameter extraction."""
    id: str = ""
    name: str = ""
    volumes: list = field(default_factory=list)  # component/volume names
    # Parameters to extract
    parameters: list = field(default_factory=lambda: ["temperature", "pressure", "velocity"])
    export_to_excel: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PPXYPlot:
    """L7: Post Processing — XY plot from sketch or probe line."""
    id: str = ""
    name: str = ""
    sketch: str = ""  # sketch or line selection
    # Abscissa (X-axis)
    abscissa: str = "length"  # length, model_x, model_y, model_z, sketch_x, sketch_y, sketch_z
    # Parameters (Y-axis)
    parameters: list = field(default_factory=lambda: ["temperature"])
    resolution: int = 100
    coordinate_system: str = "global"
    export_to_excel: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PPGoalPlot:
    """L7: Post Processing — goal plot (post-processing version)."""
    id: str = ""
    name: str = ""
    goals: list = field(default_factory=list)  # goal names/ids to plot
    # Abscissa
    abscissa: str = "iterations"  # iterations, physical_time, cpu_time, travels
    group_by_parameter: bool = False
    template: str = "default"  # default, custom
    export_to_excel: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PPReport:
    """L7: Post Processing — report generation."""
    id: str = ""
    name: str = "Report 1"
    template: str = "default"  # default, custom
    format: str = "html"  # html, word, pdf
    # Documents tab
    include_model_info: bool = True
    include_mesh_info: bool = True
    include_solver_info: bool = True
    include_goals: bool = True
    include_boundary_conditions: bool = True
    # Pictures & Charts tab
    include_cut_plots: bool = True
    include_surface_plots: bool = True
    include_xy_plots: bool = True
    include_goal_plots: bool = True
    include_convergence: bool = True
    chart_resolution: str = "medium"  # low, medium, high
    # IDs tab
    include_geometry_ids: bool = True
    include_material_ids: bool = True
    include_bc_ids: bool = True
    include_goal_ids: bool = True
    generated: bool = False
    generated_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class PPAnimation:
    """L7: Post Processing — animation settings."""
    id: str = ""
    name: str = ""
    # Video settings
    video_resolution: str = "800x600"  # 640x480, 800x600, 1024x768, 1280x720, 1920x1080
    frame_rate: int = 30
    duration_sec: float = 10.0
    output_format: str = "avi"  # avi, gif, mp4
    # Timeline
    start_iteration: int = 1
    end_iteration: int = 100
    step: int = 1
    # Parts to animate
    animate_cut_plots: bool = True
    animate_surface_plots: bool = False
    animate_isosurfaces: bool = False
    animate_trajectories: bool = False
    # Camera
    rotate_camera: bool = False
    rotation_axis: str = "Y"  # X, Y, Z
    rotation_angle: float = 360.0
    # Wizard state
    wizard_step: int = 1  # 1=options, 2=parts, 3=export

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResultsSummary:
    """L7: Post Processing — results summary / overview."""
    # Model info
    project_name: str = ""
    configuration: str = "Default"
    analysis_type: str = "Internal"
    # Mesh info
    total_cells: int = 0
    fluid_cells: int = 0
    solid_cells: int = 0
    partial_cells: int = 0
    # Domain
    domain_x_min: float = 0.0
    domain_x_max: float = 0.0
    domain_y_min: float = 0.0
    domain_y_max: float = 0.0
    domain_z_min: float = 0.0
    domain_z_max: float = 0.0
    # Physics flags
    heat_conduction_in_solids: bool = True
    radiation: bool = False
    gravity: bool = False
    time_dependent: bool = False
    # Solution info
    total_iterations: int = 0
    solution_time_sec: float = 0.0
    cpu_time_sec: float = 0.0
    # Warnings
    warnings: list = field(default_factory=list)
    # Status
    solver_status: str = ""  # converged, diverged, etc.

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class InputVariable:
    """L8: Parametric Study — one input variable to vary."""
    id: str = ""
    name: str = ""
    source: str = "simulation"  # simulation, dimension, design_table
    # Source details
    category: str = ""  # general_settings, mesh_settings, boundary_conditions, extrusion, assembly_mate, pattern
    bc_name: str = ""  # BC name if source=boundary_conditions
    property_name: str = ""  # e.g. mass_flow_rate, temperature, pressure
    current_value: float = 0.0
    unit: str = ""
    # Variation type
    variation_type: str = "discrete_values"  # discrete_values, range_with_number, range_with_step, step_around
    # Discrete Values
    discrete_values: list = field(default_factory=list)  # [val1, val2, ...]
    # Range with Number
    range_min: float = 0.0
    range_max: float = 100.0
    range_number: int = 5
    # Range with Step
    step_min: float = 0.0
    step_max: float = 100.0
    step_size: float = 10.0
    # Step Around
    step_around_center: float = 50.0
    step_around_n_minus: int = 2
    step_around_n_plus: int = 2
    step_around_size: float = 10.0

    def get_values(self) -> list:
        """Generate the list of values based on variation type."""
        if self.variation_type == "discrete_values":
            return self.discrete_values if self.discrete_values else [self.current_value]
        elif self.variation_type == "range_with_number":
            n = max(self.range_number, 1)
            if n == 1:
                return [self.range_min]
            step = (self.range_max - self.range_min) / (n - 1)
            return [round(self.range_min + i * step, 6) for i in range(n)]
        elif self.variation_type == "range_with_step":
            if self.step_size <= 0:
                return [self.step_min]
            vals = []
            v = self.step_min
            while v <= self.step_max + 1e-9:
                vals.append(round(v, 6))
                v += self.step_size
            return vals
        elif self.variation_type == "step_around":
            vals = []
            for i in range(-self.step_around_n_minus, self.step_around_n_plus + 1):
                vals.append(round(self.step_around_center + i * self.step_around_size, 6))
            return vals
        return [self.current_value]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["computed_values"] = self.get_values()
        return d


@dataclass
class OutputVariable:
    """L8: Parametric Study — output variable (goal to track)."""
    id: str = ""
    name: str = ""  # goal name
    goal_id: str = ""
    # Goal Optimization only
    use_for_optimization: bool = False
    target_value: float = 0.0
    target_unit: str = ""
    tolerance: float = 0.0
    # Initial values (optimization hints)
    at_variable_minimum: bool = False
    at_var_min_value: float = 0.0
    at_variable_maximum: bool = False
    at_var_max_value: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DesignPoint:
    """L8: Parametric Study — one design point (scenario row)."""
    id: str = ""
    name: str = "Design Point 1"
    # Input values: {input_var_id: value}
    input_values: dict = field(default_factory=dict)
    # Output results: {output_var_name: value}
    output_results: dict = field(default_factory=dict)
    # Execution
    status: str = "not_calculated"  # not_calculated, running, finished, failed
    run_at: str = "auto"  # auto, this_computer, network
    number_of_cores: str = "use_all"  # use_all, 1, 2, 4, 8
    close_monitor: bool = True
    create_and_save_project: bool = True
    # Results
    mesh_cells: int = 0
    solve_time_sec: float = 0.0
    iterations: int = 0
    # Optimization
    target_value: float = 0.0
    discrepancy: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParametricVariant:
    """L8: Parametric Study — one design variant (legacy compat)."""
    id: str = ""
    name: str = ""
    description: str = ""
    parameters: dict = field(default_factory=dict)  # param_name -> value
    status: str = "pending"  # pending, running, converged, failed
    # Results
    goals_results: dict = field(default_factory=dict)  # goal_name -> value
    mesh_cells: int = 0
    solve_time_sec: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ParametricStudy:
    """L8: Parametric Study — full study (What If or Goal Optimization)."""
    id: str = ""
    name: str = ""
    study_type: str = "what_if"  # what_if, goal_optimization
    # Input Variables
    input_variables: list = field(default_factory=list)  # [InputVariable]
    # Output Variables (goals)
    output_variables: list = field(default_factory=list)  # [OutputVariable]
    # Design Points / Scenario Table
    design_points: list = field(default_factory=list)  # [DesignPoint]
    # Legacy variants (backward compat)
    variants: list = field(default_factory=list)
    base_variant_id: str = ""
    parameters: list = field(default_factory=list)  # [{name, min, max, steps}]
    auto_mesh: bool = True
    # Execution settings
    run_on_network: bool = False
    excel_output: bool = False
    save_format: str = "fwps"  # fwps file
    # Compare results
    compare_active_scene: bool = True
    compare_surface_params: bool = True
    compare_goal_plots: bool = True

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "study_type": self.study_type,
            "input_variables": [v.to_dict() if hasattr(v, 'to_dict') else v for v in self.input_variables],
            "output_variables": [v.to_dict() if hasattr(v, 'to_dict') else v for v in self.output_variables],
            "design_points": [d.to_dict() if hasattr(d, 'to_dict') else d for d in self.design_points],
            "variants": [v.to_dict() if hasattr(v, 'to_dict') else v for v in self.variants],
            "base_variant_id": self.base_variant_id,
            "parameters": self.parameters,
            "auto_mesh": self.auto_mesh,
            "run_on_network": self.run_on_network,
            "excel_output": self.excel_output,
            "save_format": self.save_format,
            "compare_active_scene": self.compare_active_scene,
            "compare_surface_params": self.compare_surface_params,
            "compare_goal_plots": self.compare_goal_plots,
        }


@dataclass
class CompareDefinition:
    """L8: Compare Results — definition of what to compare."""
    id: str = ""
    name: str = "Compare 1"
    # Data to compare
    compare_active_scene: bool = True
    compare_surface_parameters: list = field(default_factory=list)  # surface param names
    compare_goal_plots: list = field(default_factory=list)  # goal names
    # Projects to compare
    project_configs: list = field(default_factory=list)  # [{name, variant_id, selected}]
    # Display
    side_by_side: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════
#  FloEFD Project State (in-memory)
# ═══════════════════════════════════════════════════════════════════════════

class FloEFDProject:
    """Aggregates all FloEFD-style data for one project session."""

    def __init__(self):
        self.id = uuid.uuid4().hex[:12]
        # L2: Geometry
        self.geometry_parts: list[GeometryPart] = []
        # L3: Analysis Setup (full config)
        self.analysis_config = AnalysisConfig()
        self.analysis_type = AnalysisType.INTERNAL.value
        self.heat_transfer = HeatTransferConfig()
        self.computational_domain = ComputationalDomain()
        # L4: Features / Boundary Conditions
        self.boundary_conditions: list[BoundaryConditionFloEFD] = []
        # L4a: Standard FloEFD Features
        self.component_controls: list[ComponentControl] = []
        self.fluid_subdomains: list[FluidSubdomain] = []
        self.rotating_regions: list[RotatingRegion] = []
        self.solid_materials: list[SolidMaterial] = []
        self.fan_features: list[FanFeature] = []
        self.heat_source_features: list[HeatSourceFeature] = []
        self.radiative_surfaces: list[RadiativeSurface] = []
        self.radiation_sources: list[RadiationSource] = []
        self.contact_resistances: list[ContactResistance] = []
        self.thermoelectric_coolers: list[ThermoelectricCooler] = []
        self.heatsink_simulations: list[HeatSinkSimulation] = []
        self.porous_media: list[PorousMedia] = []
        self.perforated_plates: list[PerforatedPlate] = []
        self.thermal_joints: list[ThermalJoint] = []
        self.initial_conditions_local: list[InitialConditionLocal] = []
        self.engineering_database = EngineeringDatabase()
        # L5: Meshing
        self.mesh_settings = MeshSettings()
        # L6: Goals & Solver
        self.goals: list[Goal] = []
        self.finish_conditions = FinishConditions()
        self.associated_goals_config = AssociatedGoalsConfig()
        self.solver_config = SolverConfig()
        # L7: Post Processing
        self.cut_plots: list[PostProcessingCutPlot] = []
        self.surface_plots: list[SurfacePlot] = []
        self.isosurfaces: list[Isosurface] = []
        self.flow_trajectories: list[FlowTrajectory] = []
        self.particle_studies: list[ParticleStudy] = []
        self.point_parameters: list[PointParameter] = []
        self.surface_parameters: list[SurfaceParameter] = []
        self.volume_parameters: list[VolumeParameter] = []
        self.xy_plots: list[PPXYPlot] = []
        self.pp_goal_plots: list[PPGoalPlot] = []
        self.pp_reports: list[PPReport] = []
        self.pp_animations: list[PPAnimation] = []
        self.results_summary = ResultsSummary()
        # L8: Parametric Study
        self.parametric_studies: list[ParametricStudy] = []
        self.compare_definitions: list[CompareDefinition] = []
        # Iteration history for convergence chart
        self.iteration_history: list[dict] = []  # [{iter, goals: {name: val}, residuals: {name: val}}]

    def summary(self) -> dict:
        return {
            "id": self.id,
            "analysis_type": self.analysis_type,
            "geometry_count": len(self.geometry_parts),
            "bc_count": len(self.boundary_conditions),
            "goal_count": len(self.goals),
            "mesh_cells": self.mesh_settings.total_cells,
            "solver_status": self.solver_config.convergence_status,
            "current_iteration": self.solver_config.current_iteration,
        }

    # ── Geometry ──────────────────────────────────────────────────────

    def add_geometry(self, name: str, file_path: str = "", file_type: str = "") -> GeometryPart:
        part = GeometryPart(
            id=uuid.uuid4().hex[:8],
            name=name,
            file_path=file_path,
            file_type=file_type,
        )
        # Auto-detect origin from file type
        native_types = {"sldprt", "sldasm", "prt", "asm", "catpart", "catproduct"}
        neutral_types = {"step", "stp", "sat", "igs", "iges", "x_t", "x_b", "parasolid", "stl"}
        ft_lower = file_type.lower()
        if ft_lower in native_types:
            part.file_origin = "native"
        elif ft_lower in neutral_types:
            part.file_origin = "neutral"
        self.geometry_parts.append(part)
        return part

    def remove_geometry(self, part_id: str) -> bool:
        before = len(self.geometry_parts)
        self.geometry_parts = [g for g in self.geometry_parts if g.id != part_id]
        return len(self.geometry_parts) < before

    def update_geometry(self, part_id: str, updates: dict) -> Optional[GeometryPart]:
        for part in self.geometry_parts:
            if part.id == part_id:
                for k, v in updates.items():
                    if hasattr(part, k):
                        setattr(part, k, v)
                return part
        return None

    def suppress_geometry(self, part_id: str, suppress: bool = True) -> Optional[GeometryPart]:
        """Suppress: removes from CFD analysis but does not delete from model."""
        for part in self.geometry_parts:
            if part.id == part_id:
                part.suppress = suppress
                return part
        return None

    def disable_geometry(self, part_id: str, disabled: bool = True) -> Optional[GeometryPart]:
        """Disable: visible in CAD but not to CFD solver."""
        for part in self.geometry_parts:
            if part.id == part_id:
                part.disabled = disabled
                return part
        return None

    def replace_geometry(self, part_id: str, replacement_note: str = "") -> Optional[GeometryPart]:
        """Replace: mark as simplified replacement (porous media, simple box, etc.)."""
        for part in self.geometry_parts:
            if part.id == part_id:
                part.replaced = True
                part.replacement_note = replacement_note
                return part
        return None

    def run_import_diagnostics(self, part_id: str) -> Optional[GeometryCheckResult]:
        """Run import diagnostics on a geometry part (mock).
        Simulates faulty faces, gaps, and recommendations from the slides."""
        import random
        part = None
        for p in self.geometry_parts:
            if p.id == part_id:
                part = p
                break
        if not part:
            return None

        result = GeometryCheckResult(part_id=part.id, part_name=part.name)

        # Neutral files more likely to have errors
        error_probability = 0.7 if part.file_origin == "neutral" else 0.2

        if random.random() < error_probability:
            n_faulty = random.randint(2, 32)
            n_gaps = random.randint(1, 16)
            faulty = [{"id": f"face_{i}", "type": "faulty", "healed": False}
                      for i in range(1, n_faulty + 1)]
            gaps = [{"id": f"gap_{i}", "faces": [f"Face<{random.randint(1,200)}>",
                    f"Face<{random.randint(1,200)}>"], "healed": False}
                    for i in range(1, n_gaps + 1)]
            part.faulty_faces = faulty
            part.gaps = gaps
            part.has_errors = True
            part.is_watertight = False
            result.is_watertight = False
            result.faulty_face_count = n_faulty
            result.gap_count = n_gaps
            result.errors = [f"Faulty face: Face<{i}>" for i in range(1, min(n_faulty + 1, 8))]
            result.errors += [f"Gap between faces: Gap<{i}>" for i in range(1, min(n_gaps + 1, 5))]
        else:
            part.has_errors = False
            part.is_watertight = True
            result.is_watertight = True

        # Check if surface body (imported solid came through as surface)
        if part.file_origin == "neutral" and random.random() < 0.3:
            part.is_surface_body = True
            result.is_solid = False
            result.errors.append("Imported as surface body — needs knit/thicken to solid")
            result.recommendations.append("Use Knit or Thicken to form a solid body")
        else:
            result.is_solid = True

        # Invalid contacts
        n_contacts = random.randint(0, 3)
        if n_contacts > 0:
            result.invalid_contact_count = n_contacts
            result.warnings += [
                f"Invalid contact: {random.choice(['Tangency', 'Line contact', 'Point contact'])} "
                f"between Part {random.randint(1, 5)} and Part {random.randint(6, 10)}"
                for _ in range(n_contacts)
            ]
            result.recommendations.append("Ensure surface contact between mating parts")

        # Fluid region detection (for internal analysis)
        if self.analysis_type == "internal":
            if part.is_watertight and not part.is_surface_body:
                result.fluid_region_detected = True
            else:
                result.fluid_region_detected = False
                result.needs_lids = True
                result.recommendations.append("Create lids on flow openings for internal analysis")
                result.recommendations.append("Check geometry is fully sealed")

        # Recommendations based on part tags
        for tag in part.tags:
            if tag in ("fastener", "bolt", "nut", "washer"):
                result.recommendations.append(f"Consider disabling '{part.name}' — fastener irrelevant to CFD")
            elif tag in ("fillet", "chamfer", "thread"):
                result.recommendations.append(f"Consider suppressing '{tag}' feature — negligible CFD impact")

        part.diagnostics_run = True
        return result

    def heal_geometry(self, part_id: str) -> dict:
        """Attempt to heal all faulty faces and gaps (mock)."""
        import random
        part = None
        for p in self.geometry_parts:
            if p.id == part_id:
                part = p
                break
        if not part:
            return {"success": False, "error": "Part not found"}

        healed_faces = 0
        remaining_faces = 0
        for f in part.faulty_faces:
            if random.random() < 0.85:  # 85% heal success rate
                f["healed"] = True
                healed_faces += 1
            else:
                remaining_faces += 1

        healed_gaps = 0
        remaining_gaps = 0
        for g in part.gaps:
            if random.random() < 0.80:
                g["healed"] = True
                healed_gaps += 1
            else:
                remaining_gaps += 1

        if remaining_faces == 0 and remaining_gaps == 0:
            part.has_errors = False
            part.is_watertight = True

        return {
            "success": True,
            "healed_faces": healed_faces,
            "remaining_faces": remaining_faces,
            "healed_gaps": healed_gaps,
            "remaining_gaps": remaining_gaps,
            "is_watertight": part.is_watertight,
        }

    def add_lid(self, part_id: str, name: str = "Lid",
                opening_type: str = "inlet") -> Optional[dict]:
        """Create a lid on an opening (for internal analysis)."""
        for part in self.geometry_parts:
            if part.id == part_id:
                lid = {
                    "id": uuid.uuid4().hex[:8],
                    "name": name,
                    "opening_type": opening_type,
                }
                part.lids.append(lid)
                return lid
        return None

    def remove_lid(self, part_id: str, lid_id: str) -> bool:
        for part in self.geometry_parts:
            if part.id == part_id:
                before = len(part.lids)
                part.lids = [l for l in part.lids if l.get("id") != lid_id]
                return len(part.lids) < before
        return False

    def check_all_geometry(self) -> dict:
        """Run a full geometry check across all parts — summary flowchart from slides."""
        results = []
        total_errors = 0
        total_warnings = 0
        all_watertight = True
        fluid_detected = False

        for part in self.geometry_parts:
            if part.suppress or part.disabled:
                continue
            r = self.run_import_diagnostics(part.id)
            if r:
                results.append(r.to_dict())
                total_errors += len(r.errors)
                total_warnings += len(r.warnings)
                if not r.is_watertight:
                    all_watertight = False
                if r.fluid_region_detected:
                    fluid_detected = True

        return {
            "parts_checked": len(results),
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "all_watertight": all_watertight,
            "fluid_region_detected": fluid_detected,
            "results": results,
            "ready_for_analysis": all_watertight and (fluid_detected or self.analysis_type == "external"),
        }

    # ── Boundary Conditions ───────────────────────────────────────────

    def add_bc(self, name: str, bc_type: str = "wall") -> BoundaryConditionFloEFD:
        bc = BoundaryConditionFloEFD(
            id=uuid.uuid4().hex[:8],
            name=name,
            bc_type=bc_type,
        )
        self.boundary_conditions.append(bc)
        return bc

    def update_bc(self, bc_id: str, updates: dict) -> Optional[BoundaryConditionFloEFD]:
        for bc in self.boundary_conditions:
            if bc.id == bc_id:
                for k, v in updates.items():
                    if hasattr(bc, k):
                        setattr(bc, k, v)
                return bc
        return None

    def remove_bc(self, bc_id: str) -> bool:
        before = len(self.boundary_conditions)
        self.boundary_conditions = [b for b in self.boundary_conditions if b.id != bc_id]
        return len(self.boundary_conditions) < before

    # ── L4a: Generic Feature CRUD ─────────────────────────────────────

    def _add_feature(self, collection_name: str, cls, body: dict):
        """Generic add: create an instance of cls, set fields from body, append to collection."""
        obj = cls(id=uuid.uuid4().hex[:8])
        for k, v in body.items():
            if hasattr(obj, k) and k != "id":
                setattr(obj, k, v)
        getattr(self, collection_name).append(obj)
        return obj

    def _update_feature(self, collection_name: str, fid: str, body: dict):
        for obj in getattr(self, collection_name):
            if obj.id == fid:
                for k, v in body.items():
                    if hasattr(obj, k) and k != "id":
                        setattr(obj, k, v)
                return obj
        return None

    def _remove_feature(self, collection_name: str, fid: str) -> bool:
        col = getattr(self, collection_name)
        before = len(col)
        setattr(self, collection_name, [o for o in col if o.id != fid])
        return len(getattr(self, collection_name)) < before

    # ── Goals ─────────────────────────────────────────────────────────

    def add_goal(self, name: str, goal_type: str = "surface",
                 parameter: str = "temperature") -> Goal:
        goal = Goal(
            id=uuid.uuid4().hex[:8],
            name=name,
            goal_type=goal_type,
            parameter=parameter,
        )
        self.goals.append(goal)
        return goal

    def remove_goal(self, goal_id: str) -> bool:
        before = len(self.goals)
        self.goals = [g for g in self.goals if g.id != goal_id]
        return len(self.goals) < before

    # ── Cut Plots ─────────────────────────────────────────────────────

    def add_cut_plot(self, name: str, parameter: str = "temperature",
                     plane: str = "XY") -> PostProcessingCutPlot:
        plot = PostProcessingCutPlot(
            id=uuid.uuid4().hex[:8],
            name=name,
            parameter=parameter,
            plane=plane,
        )
        self.cut_plots.append(plot)
        return plot

    # ── Surface Plots ─────────────────────────────────────────────────

    def add_surface_plot(self, name: str, parameter: str = "temperature",
                         surface_name: str = "") -> SurfacePlot:
        plot = SurfacePlot(
            id=uuid.uuid4().hex[:8],
            name=name,
            parameter=parameter,
            surface_name=surface_name,
        )
        self.surface_plots.append(plot)
        return plot

    # ── L7: Generic post-processing CRUD helpers ──────────────────────

    def _pp_add(self, collection_name: str, cls, body: dict):
        """Generic add for any L7 post-processing item."""
        obj = cls(id=uuid.uuid4().hex[:8])
        for k, v in body.items():
            if hasattr(obj, k) and k != "id":
                setattr(obj, k, v)
        getattr(self, collection_name).append(obj)
        return obj

    def _pp_update(self, collection_name: str, item_id: str, body: dict):
        for obj in getattr(self, collection_name):
            if obj.id == item_id:
                for k, v in body.items():
                    if hasattr(obj, k) and k != "id":
                        setattr(obj, k, v)
                return obj
        return None

    def _pp_remove(self, collection_name: str, item_id: str) -> bool:
        col = getattr(self, collection_name)
        before = len(col)
        setattr(self, collection_name, [o for o in col if o.id != item_id])
        return len(getattr(self, collection_name)) < before

    def build_results_summary(self) -> ResultsSummary:
        """Populate results summary from current project state."""
        rs = self.results_summary
        rs.analysis_type = self.analysis_type
        rs.total_cells = self.mesh_settings.total_cells
        rs.fluid_cells = self.mesh_settings.fluid_cells
        rs.solid_cells = self.mesh_settings.solid_cells
        rs.partial_cells = self.mesh_settings.partial_cells
        rs.domain_x_min = self.computational_domain.x_min
        rs.domain_x_max = self.computational_domain.x_max
        rs.domain_y_min = self.computational_domain.y_min
        rs.domain_y_max = self.computational_domain.y_max
        rs.domain_z_min = self.computational_domain.z_min
        rs.domain_z_max = self.computational_domain.z_max
        rs.heat_conduction_in_solids = self.heat_transfer.heat_conduction_in_solids
        rs.radiation = self.heat_transfer.radiation_enabled
        rs.gravity = self.analysis_config.gravity_enabled
        rs.time_dependent = self.analysis_config.time_dependent
        rs.total_iterations = self.solver_config.current_iteration
        rs.solver_status = self.solver_config.convergence_status
        return rs

    # ── Parametric Study ──────────────────────────────────────────────

    def create_parametric_study(self, name: str, study_type: str = "what_if") -> ParametricStudy:
        study = ParametricStudy(
            id=uuid.uuid4().hex[:8],
            name=name,
            study_type=study_type,
        )
        self.parametric_studies.append(study)
        return study

    def _find_study(self, study_id: str):
        for s in self.parametric_studies:
            if s.id == study_id:
                return s
        return None

    def add_input_variable(self, study_id: str, body: dict) -> Optional[InputVariable]:
        study = self._find_study(study_id)
        if not study:
            return None
        iv = InputVariable(id=uuid.uuid4().hex[:8])
        for k, v in body.items():
            if hasattr(iv, k) and k != "id":
                setattr(iv, k, v)
        study.input_variables.append(iv)
        return iv

    def remove_input_variable(self, study_id: str, var_id: str) -> bool:
        study = self._find_study(study_id)
        if not study:
            return False
        before = len(study.input_variables)
        study.input_variables = [v for v in study.input_variables if v.id != var_id]
        return len(study.input_variables) < before

    def add_output_variable(self, study_id: str, body: dict) -> Optional[OutputVariable]:
        study = self._find_study(study_id)
        if not study:
            return None
        ov = OutputVariable(id=uuid.uuid4().hex[:8])
        for k, v in body.items():
            if hasattr(ov, k) and k != "id":
                setattr(ov, k, v)
        study.output_variables.append(ov)
        return ov

    def remove_output_variable(self, study_id: str, var_id: str) -> bool:
        study = self._find_study(study_id)
        if not study:
            return False
        before = len(study.output_variables)
        study.output_variables = [v for v in study.output_variables if v.id != var_id]
        return len(study.output_variables) < before

    def generate_design_points(self, study_id: str) -> list:
        """Generate design points from input variable variations (cartesian product)."""
        import itertools
        study = self._find_study(study_id)
        if not study or not study.input_variables:
            return []
        # Clear existing
        study.design_points = []
        # Build value lists per input variable
        var_values = []
        var_ids = []
        for iv in study.input_variables:
            vals = iv.get_values() if hasattr(iv, 'get_values') else [iv.current_value]
            var_values.append(vals)
            var_ids.append(iv.id)
        # Cartesian product
        for idx, combo in enumerate(itertools.product(*var_values)):
            dp = DesignPoint(
                id=uuid.uuid4().hex[:8],
                name=f"Design Point {idx + 1}",
                input_values={var_ids[i]: combo[i] for i in range(len(var_ids))},
            )
            study.design_points.append(dp)
        return study.design_points

    def run_design_point(self, study_id: str, dp_id: str) -> Optional[DesignPoint]:
        """Simulate running one design point."""
        study = self._find_study(study_id)
        if not study:
            return None
        for dp in study.design_points:
            if dp.id == dp_id:
                dp.status = "running"
                self.reset_solver()
                for _ in range(30):
                    self.simulate_iteration()
                dp.status = "finished"
                dp.mesh_cells = self.mesh_settings.total_cells
                dp.iterations = self.solver_config.current_iteration
                # Collect goal results
                for g in self.goals:
                    dp.output_results[g.name] = round(g.current_value, 4)
                return dp
        return None

    def run_all_design_points(self, study_id: str) -> Optional[ParametricStudy]:
        """Run all design points in a study."""
        study = self._find_study(study_id)
        if not study:
            return None
        for dp in study.design_points:
            self.run_design_point(study_id, dp.id)
        return study

    def add_variant(self, study_id: str, name: str,
                    parameters: dict) -> Optional[ParametricVariant]:
        for study in self.parametric_studies:
            if study.id == study_id:
                variant = ParametricVariant(
                    id=uuid.uuid4().hex[:8],
                    name=name,
                    parameters=parameters,
                )
                study.variants.append(variant)
                return variant
        return None

    def clone_variant(self, study_id: str, variant_id: str,
                      new_name: str) -> Optional[ParametricVariant]:
        """FloEFD 'Cloning' feature — copy a variant's settings."""
        for study in self.parametric_studies:
            if study.id == study_id:
                for v in study.variants:
                    if (hasattr(v, 'id') and v.id == variant_id) or \
                       (isinstance(v, dict) and v.get('id') == variant_id):
                        src = v if isinstance(v, dict) else v.to_dict()
                        new_variant = ParametricVariant(
                            id=uuid.uuid4().hex[:8],
                            name=new_name,
                            parameters=dict(src.get("parameters", {})),
                        )
                        study.variants.append(new_variant)
                        return new_variant
        return None

    # ── Compare ───────────────────────────────────────────────────────

    def create_compare(self, name: str = "Compare 1") -> CompareDefinition:
        cd = CompareDefinition(id=uuid.uuid4().hex[:8], name=name)
        self.compare_definitions.append(cd)
        return cd

    # ── Simulate mesh generation (mock) ───────────────────────────────

    def generate_mesh(self) -> dict:
        """Simulate FloEFD mesh generation based on settings."""
        ms = self.mesh_settings
        base = 10 ** ms.initial_mesh_level
        fluid = int(base * 0.65)
        solid = int(base * 0.20)
        partial = int(base * 0.15)
        total = fluid + solid + partial

        ms.total_cells = total
        ms.fluid_cells = fluid
        ms.solid_cells = solid
        ms.partial_cells = partial

        return {
            "total_cells": total,
            "fluid_cells": fluid,
            "solid_cells": solid,
            "partial_cells": partial,
            "mesh_level": ms.initial_mesh_level,
        }

    # ── Simulate solver run (mock) ────────────────────────────────────

    def simulate_iteration(self) -> dict:
        """Simulate one solver iteration — returns residuals and goal values."""
        sc = self.solver_config
        sc.current_iteration += 1
        it = sc.current_iteration

        # Mock residual decay
        factor = math.exp(-0.03 * it)
        residuals = {
            "Ux": 0.5 * factor + 1e-6,
            "Uy": 0.4 * factor + 1e-6,
            "Uz": 0.3 * factor + 1e-6,
            "p": 0.6 * factor + 1e-6,
            "k": 0.2 * factor + 1e-6,
            "epsilon": 0.25 * factor + 1e-6,
        }
        if self.heat_transfer.conduction_enabled or self.heat_transfer.convection_enabled:
            residuals["T"] = 0.35 * factor + 1e-6

        sc.residuals = residuals

        # Mock goal values
        goal_values = {}
        for g in self.goals:
            noise = math.sin(it * 0.1) * 0.5 * factor
            if g.parameter == "temperature":
                g.current_value = 350.0 + noise
            elif g.parameter == "pressure":
                g.current_value = 101325 + 50 * noise
            elif g.parameter == "velocity":
                g.current_value = 5.0 + noise
            elif g.parameter == "heat_flux":
                g.current_value = 1000 + 100 * noise
            else:
                g.current_value = 1.0 + noise

            g.min_value = min(g.min_value, g.current_value) if it > 1 else g.current_value
            g.max_value = max(g.max_value, g.current_value) if it > 1 else g.current_value
            g.averaged_value = (g.averaged_value * (it - 1) + g.current_value) / it

            # Check convergence
            delta = abs(g.max_value - g.min_value)
            if it > 20:
                g.is_converged = delta < g.delta_criteria * abs(g.averaged_value + 1e-10)

            goal_values[g.name] = g.current_value

        # Check overall convergence
        all_converged = all(r < sc.convergence_criterion for r in residuals.values())
        goals_converged = all(g.is_converged for g in self.goals) if self.goals else False

        if sc.finish_conditions == "goals":
            done = goals_converged and it > 10
        elif sc.finish_conditions == "iterations":
            done = it >= sc.max_iterations
        else:
            done = (all_converged or goals_converged) and it > 10

        if done:
            sc.convergence_status = ConvergenceStatus.CONVERGED.value
        elif any(r > 1e6 for r in residuals.values()):
            sc.convergence_status = ConvergenceStatus.DIVERGING.value
        else:
            sc.convergence_status = ConvergenceStatus.CONVERGING.value

        entry = {
            "iteration": it,
            "residuals": dict(residuals),
            "goals": goal_values,
        }
        self.iteration_history.append(entry)

        return entry

    def reset_solver(self):
        """Reset solver state for a fresh run."""
        self.solver_config.current_iteration = 0
        self.solver_config.convergence_status = ConvergenceStatus.NOT_STARTED.value
        self.solver_config.residuals = {}
        self.iteration_history = []
        for g in self.goals:
            g.current_value = 0
            g.min_value = 0
            g.max_value = 0
            g.averaged_value = 0
            g.is_converged = False


# ═══════════════════════════════════════════════════════════════════════════
#  Module-level singleton
# ═══════════════════════════════════════════════════════════════════════════

floefd_project = FloEFDProject()
