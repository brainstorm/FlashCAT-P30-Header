#!/usr/bin/env python3
"""Write flashcat_p30.kicad_pro: design rules + net classes.

Rules target a standard 4-layer prototype process (JLCPCB/PCBWay class):
  min track/space 0.127 mm (5 mil), via 0.3/0.5 mm, PTH >= 0.3 mm.
The socket contacts sit on a 1.0 mm grid with 0.6 mm pads, leaving a
0.4 mm gap: exactly one 0.127 mm track with 0.1365 mm clearance each side.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "flashcat_p30.kicad_pro")


def netclass(name, track, clearance, via_d=0.5, via_drill=0.3, prio=0):
    return {
        "bus_width": 12, "clearance": clearance, "diff_pair_gap": 0.25, "diff_pair_via_gap": 0.25,
        "diff_pair_width": 0.2, "line_style": 0, "microvia_diameter": 0.3, "microvia_drill": 0.1,
        "name": name, "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": prio,
        "schematic_color": "rgba(0, 0, 0, 0.000)", "track_width": track,
        "via_diameter": via_d, "via_drill": via_drill, "wire_width": 6,
    }


pro = {
    "board": {
        "3dviewports": [],
        "design_settings": {
            "defaults": {
                "board_outline_line_width": 0.1, "copper_line_width": 0.2, "copper_text_size_h": 1.5,
                "copper_text_size_v": 1.5, "copper_text_thickness": 0.3, "other_line_width": 0.1,
                "silk_line_width": 0.12, "silk_text_size_h": 1.0, "silk_text_size_v": 1.0,
                "silk_text_thickness": 0.15,
                "pads": {"drill": 0.8, "height": 1.35, "width": 1.35},
                "zones": {"min_clearance": 0.2},
            },
            "diff_pair_dimensions": [],
            "drc_exclusions": [],
            "meta": {"version": 2},
            "rule_severities": {
                "lib_footprint_issues": "ignore",
                "lib_footprint_mismatch": "ignore",
                "silk_overlap": "warning",
                "silk_over_copper": "warning",
                "text_height": "warning",
                "text_thickness": "warning",
            },
            "rules": {
                "allow_blind_buried_vias": False, "allow_microvias": False, "max_error": 0.005,
                "min_clearance": 0.127, "min_connection": 0.127, "min_copper_edge_clearance": 0.3,
                "min_groove_width": 0.0, "min_hole_clearance": 0.2, "min_hole_to_hole": 0.25,
                "min_microvia_diameter": 0.2, "min_microvia_drill": 0.1, "min_resolved_spokes": 1,
                "min_silk_clearance": 0.0, "min_text_height": 0.8, "min_text_thickness": 0.12,
                "min_through_hole_diameter": 0.3, "min_track_width": 0.127,
                "min_via_annular_width": 0.1, "min_via_diameter": 0.5,
                "solder_mask_to_copper_clearance": 0.0, "use_height_for_length_calcs": True,
            },
            "teardrop_options": [{"td_onpthpad": True, "td_onroundshapesonly": False,
                                  "td_onsmdpad": True, "td_ontrackend": False, "td_onvia": True}],
            "teardrop_parameters": [],
            "track_widths": [0.0, 0.127, 0.2, 0.3, 0.5],
            "tuning_pattern_settings": {},
            "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.5, "drill": 0.3},
                               {"diameter": 0.6, "drill": 0.3}],
            "zones_allow_external_fillets": False,
        },
        "ipc2581": {"dist": "", "distpn": "", "internal_id": "", "mfg": "", "mpn": ""},
        "layer_pairs": [],
        "layer_presets": [],
        "viewports": [],
    },
    "boards": [],
    "cvpcb": {"equivalence_files": []},
    "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
    "meta": {"filename": "flashcat_p30.kicad_pro", "version": 3},
    "net_settings": {
        "classes": [
            netclass("Default", 0.127, 0.127, prio=2147483647),
            netclass("Power", 0.2, 0.127, prio=0),
        ],
        "meta": {"version": 4},
        "net_colors": None,
        "netclass_assignments": None,
        "netclass_patterns": [
            {"netclass": "Power", "pattern": "GND"},
            {"netclass": "Power", "pattern": "+1V8"},
        ],
    },
    "pcbnew": {"last_paths": {}, "page_layout_descr_file": ""},
    "schematic": {
        "annotate_start_num": 0,
        "drawing": {"default_line_thickness": 6.0, "default_text_size": 50.0,
                    "field_names": [{"name": "MPN", "url": False, "visible": False},
                                    {"name": "Manufacturer", "url": False, "visible": False}],
                    "intersheets_ref_own_page": False, "intersheets_ref_prefix": "",
                    "intersheets_ref_short": False, "intersheets_ref_show": False,
                    "intersheets_ref_suffix": "", "junction_size_choice": 3, "label_size_ratio": 0.375,
                    "pin_symbol_size": 25.0, "text_offset_ratio": 0.15},
        "legacy_lib_dir": "",
        "legacy_lib_list": [],
        "meta": {"version": 1},
        "page_layout_descr_file": "",
        "plot_directory": "",
        "subpart_first_id": 65,
        "subpart_id_separator": 0,
    },
    "sheets": [["e682b334-2aff-5068-a0db-59f15f6c8397", "Root"]],
    "text_variables": {},
}

if __name__ == "__main__":
    with open(OUT, "w") as f:
        json.dump(pro, f, indent=2)
    print("wrote", os.path.normpath(OUT))
