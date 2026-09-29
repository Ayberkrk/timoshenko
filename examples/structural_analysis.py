"""Static, P-delta, modal and stability analysis of a planar cantilever."""

import timoshenko as tm

material = tm.FrameMaterial(
    youngs_modulus_pa=200e9,
    shear_modulus_pa=200e9 / (2 * (1 + 0.3)),
    poisson_ratio=0.3,
)
shape = tm.rectangle_section(width_m=0.10, height_m=0.20)
section = tm.FrameSection(
    area_m2=shape.area_m2,
    second_moment_local_z_m4=shape.second_moment_z_m4,
    section_modulus_at_positive_local_y_m3=shape.section_modulus_z_m3,
    section_modulus_at_negative_local_y_m3=shape.section_modulus_z_m3,
)
model = tm.StructuralModel(
    nodes=(tm.FrameNode(0.0, 0.0), tm.FrameNode(4.0, 0.0)),
    members=(tm.FrameMember(0, 1, material, section, mass_per_length_kg_m=25.0),),
    restraints=((True, True, True), (False, False, False)),
    nodal_loads=((0.0, 0.0, 0.0), (-40_000.0, -2_000.0, 0.0)),
)

static = tm.analyze_linear_static(model)
second_order = tm.analyze_p_delta(model)
modes = tm.analyze_modes(model, mode_count=2)
buckling = tm.analyze_linear_buckling(model, mode_count=1)

print("Tip displacement, first order (m):", static.displacements[1][:2])
print("Tip displacement, P-delta (m):", second_order.displacements[1][:2])
print("End normal stresses (Pa):", static.member_end_normal_stresses_pa[0])
print("First natural frequency (Hz):", modes.frequencies_hz[0])
print("X effective modal mass ratio:", modes.effective_modal_mass_ratios_x[0])
print("First linear buckling load factor:", buckling.critical_load_factors[0])
