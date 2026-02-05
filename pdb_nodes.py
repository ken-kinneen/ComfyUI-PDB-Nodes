# PDB → Image (PyMOL, CLI, RGB only, baked background)

import os
import tempfile
import subprocess
import shlex
import shutil
import numpy as np
import torch
from PIL import Image

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}


def _as_bool(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")


# Quality presets: balance between speed and visual quality
# Each preset defines: antialias, ray_shadows, surface_quality, ray_trace_mode
QUALITY_PRESETS = {
    "draft": {
        "antialias": 0,
        "ray_shadows": False,
        "surface_quality": 0,
        "ray_trace_mode": 0,
        "ambient_occlusion": False,
        "light_count": 2,
    },
    "standard": {
        "antialias": 1,
        "ray_shadows": True,
        "surface_quality": 1,
        "ray_trace_mode": 0,
        "ambient_occlusion": True,
        "light_count": 4,
    },
    "high": {
        "antialias": 2,
        "ray_shadows": True,
        "surface_quality": 2,
        "ray_trace_mode": 0,
        "ambient_occlusion": True,
        "light_count": 6,
    },
    "publication": {
        "antialias": 4,
        "ray_shadows": True,
        "surface_quality": 3,
        "ray_trace_mode": 0,
        "ambient_occlusion": True,
        "light_count": 8,
    },
    "publication_outlined": {
        "antialias": 4,
        "ray_shadows": True,
        "surface_quality": 3,
        "ray_trace_mode": 1,  # Outlined style
        "ambient_occlusion": True,
        "light_count": 8,
    },
    "custom": None,  # Use manual settings
}


class PDBToImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                # === CORE INPUTS ===
                "pdb_path": ("STRING", {
                    "multiline": False,
                    "placeholder": "/path/to/protein.pdb or RCSB URL"
                }),

                # === QUALITY PRESET ===
                # Presets control: antialias, shadows, surface_quality, ray_trace_mode, AO, lights
                # Use "custom" to override with optional advanced parameters below
                "quality_preset": (["standard", "draft", "high", "publication", "publication_outlined", "custom"], {
                    "default": "standard"
                }),

                # === OUTPUT SIZE ===
                "width":  ("INT",   {"default": 1024, "min": 256,  "max": 4096, "step": 64}),
                "height": ("INT",   {"default": 1024, "min": 256,  "max": 4096, "step": 64}),

                # === VISUALIZATION ===
                "render_mode": (["cartoon", "surface", "sticks", "ball_and_stick", "ribbon", "lines", "spheres", "mesh", "dots"], {"default": "cartoon"}),
                "color_mode": (["chain", "element", "single", "custom", "spectrum", "secondary_structure", "b_factor", "hydrophobicity"], {"default": "chain"}),
                "background": (["white", "black", "custom"], {"default": "white"}),

                # === CAMERA ===
                "camera": (["auto_orient", "front", "back", "side", "top", "bottom", "iso", "custom"], {"default": "iso"}),
            },
            "optional": {
                # === PYMOL PATH (usually auto-detected) ===
                "pymol_bin": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "Auto-detected (or /path/to/pymol)"
                }),

                # === SELECTION FILTER (limit what's rendered) ===
                "selection": ("STRING", {
                    "default": "all",
                    "placeholder": "all, chain A, resi 1-100, etc."
                }),

                # === VISUALIZATION OPTIONS ===
                "cartoon_style": (["oval", "loop", "putty", "rect", "tube", "arrow", "dumbbell"], {"default": "oval"}),
                "cartoon_fancy_helices": ("BOOLEAN", {"default": True}),
                "cartoon_fancy_sheets": ("BOOLEAN", {"default": True}),
                "cartoon_flat_sheets": ("BOOLEAN", {"default": False}),
                "cartoon_smooth_loops": ("INT", {"default": 5, "min": 0, "max": 20, "step": 1}),
                "cartoon_tube_radius": ("FLOAT", {"default": 0.5, "min": 0.1, "max": 2.0, "step": 0.1}),
                "cartoon_helix_radius": ("FLOAT", {"default": 2.25, "min": 0.5, "max": 5.0, "step": 0.25}),
                "cartoon_loop_radius": ("FLOAT", {"default": 0.3, "min": 0.1, "max": 1.0, "step": 0.1}),

                # === STICK/SPHERE SETTINGS ===
                "stick_radius": ("FLOAT", {"default": 0.25, "min": 0.05, "max": 1.0, "step": 0.05}),
                "stick_ball": ("BOOLEAN", {"default": False}),
                "sphere_scale": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 3.0, "step": 0.1}),
                "sphere_mode": (["default", "simple", "shader", "fast"], {"default": "default"}),

                # === LINE/MESH/DOT SETTINGS ===
                "line_width": ("FLOAT", {"default": 1.5, "min": 0.5, "max": 10.0, "step": 0.5}),
                "mesh_width": ("FLOAT", {"default": 0.5, "min": 0.1, "max": 2.0, "step": 0.1}),
                "dot_density": ("INT", {"default": 3, "min": 1, "max": 5, "step": 1}),

                # === RIBBON SETTINGS ===
                "ribbon_width": ("FLOAT", {"default": 3.0, "min": 0.5, "max": 10.0, "step": 0.5}),
                "ribbon_smooth": ("INT", {"default": 0, "min": 0, "max": 10, "step": 1}),

                # === COLOR OPTIONS ===
                "single_color": ("STRING", {"default": "deepsalmon"}),
                "custom_per_chain": ("STRING", {
                    "default": "A:cyan,B:green,C:yellow",
                    "placeholder": "A:cyan,B:green,C:yellow"
                }),
                "spectrum_palette": (["rainbow", "blue_white_red", "green_white_magenta", "cyan_white_yellow", "blue_green", "yellow_cyan_white"], {"default": "rainbow"}),

                # === BACKGROUND ===
                "bg_custom": ("STRING", {"default": "white"}),

                # === TRANSPARENCY ===
                "transparency": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "cartoon_transparency": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "surface_transparency": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "stick_transparency": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),
                "sphere_transparency": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.05}),

                # === CAMERA OPTIONS ===
                "rotate_x":   ("FLOAT", {"default": 45.0, "min": -180.0, "max": 180.0, "step": 1.0}),
                "rotate_y":   ("FLOAT", {"default": 30.0, "min": -180.0, "max": 180.0, "step": 1.0}),
                "rotate_z":   ("FLOAT", {"default": 0.0, "min": -180.0, "max": 180.0, "step": 1.0}),
                "zoom_factor": ("FLOAT", {"default": 1.50, "min": 0.5, "max": 5.0, "step": 0.05}),

                # === ADVANCED: RAY TRACING (only used when quality_preset="custom") ===
                "antialias": (["0 (none)", "1 (adaptive)", "2 (2x oversample)", "3 (3x oversample)", "4 (4x oversample)"], {
                    "default": "1 (adaptive)"
                }),
                "ray_shadows": ("BOOLEAN", {"default": True}),
                "ray_trace_mode": (["normal", "outlined", "bw_outlined", "quantized"], {
                    "default": "normal"
                }),
                "ray_trace_gain": ("FLOAT", {"default": 0.12, "min": 0.0, "max": 1.0, "step": 0.02}),
                "ray_trace_color": ("STRING", {"default": "black"}),
                "surface_quality": ("INT", {"default": 1, "min": 0, "max": 4, "step": 1}),

                # === ADVANCED: LIGHTING (only used when quality_preset="custom") ===
                "ambient_occlusion": ("BOOLEAN", {"default": True}),
                "ambient_occlusion_scale": ("FLOAT", {"default": 25.0, "min": 1.0, "max": 100.0, "step": 1.0}),
                "depth_cue":         ("BOOLEAN", {"default": True}),
                "ambient":      ("FLOAT", {"default": 0.6, "min": 0.0, "max": 1.0,  "step": 0.05}),
                "direct":       ("FLOAT", {"default": 0.45, "min": 0.0, "max": 1.0, "step": 0.05}),
                "reflect":      ("FLOAT", {"default": 0.45, "min": 0.0, "max": 1.0, "step": 0.05}),
                "spec_count":   ("INT",   {"default": 4,   "min": 0,   "max": 8,    "step": 1}),
                "spec_reflect": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0,  "step": 0.1}),
                "spec_direct":  ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0,  "step": 0.05}),
                "shininess":    ("INT",   {"default": 60,  "min": 0,   "max": 128,  "step": 2}),
                "light_count":  ("INT",   {"default": 6,   "min": 1,   "max": 10,   "step": 1}),
                "two_sided_lighting": ("BOOLEAN", {"default": True}),
                "fog_amount":   ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0,  "step": 0.05}),

                # === LABELS (optional text on structure) ===
                "show_labels": ("BOOLEAN", {"default": False}),
                "label_selection": ("STRING", {"default": "name CA", "placeholder": "name CA, resi 1+10+20"}),
                "label_content": (["resn", "resi", "name", "chain", "b", "custom"], {"default": "resi"}),
                "label_size": ("FLOAT", {"default": 20.0, "min": 5.0, "max": 100.0, "step": 5.0}),
                "label_color": ("STRING", {"default": "black"}),

                # === OUTLINE (for outlined modes) ===
                "outline_width": ("FLOAT", {"default": 1.0, "min": 0.1, "max": 5.0, "step": 0.1}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image_rgb",)
    FUNCTION = "render"
    CATEGORY = "Biostructure"

    def _find_pymol(self, pymol_bin):
        cands = []
        if pymol_bin and pymol_bin.strip():
            cands.append(pymol_bin.strip())
        envb = os.environ.get("PYMOL_BIN", "").strip()
        if envb:
            cands.append(envb)
        auto = shutil.which("pymol")
        if auto:
            cands.append(auto)
        for p in cands:
            if os.path.isfile(p) and os.access(p, os.X_OK):
                return p
        raise RuntimeError(
            "PyMOL CLI not found. Provide full path in 'pymol_bin', or export PYMOL_BIN, or ensure 'pymol' on PATH.")

    def _color_cmds(self, color_mode, single_color, custom_per_chain, spectrum_palette="rainbow"):
        if color_mode == "chain":
            return "util.cbc()"
        if color_mode == "element":
            # explicit per-element colors (robust without util.cbag)
            return (
                "color gray70, prot\n"
                "color slate,  elem C & prot\n"
                "color blue,   elem N & prot\n"
                "color red,    elem O & prot\n"
                "color yellow, elem S & prot\n"
                "color orange, elem P & prot\n"
                "color white,  elem H & prot\n"
            )
        if color_mode == "single":
            return f"color {single_color}, prot"
        if color_mode == "spectrum":
            # Coloring by residue number with selected palette
            return f"spectrum count, {spectrum_palette}, prot"
        if color_mode == "secondary_structure":
            # Color by secondary structure
            return (
                "color red, ss h & prot\n"      # helices = red
                "color yellow, ss s & prot\n"   # sheets = yellow
                "color green, ss l+ & prot"     # loops = green
            )
        if color_mode == "b_factor":
            # Color by B-factor (temperature factor / flexibility)
            return f"spectrum b, {spectrum_palette}, prot"
        if color_mode == "hydrophobicity":
            # Color by hydrophobicity
            return "util.color_by_hydropathy(prot)"
        # custom per-chain
        cmds = []
        items = [x.strip() for x in custom_per_chain.split(",") if ":" in x]
        for it in items:
            ch, col = it.split(":", 1)
            cmds.append(f"color {col.strip()}, chain {ch.strip()}")
        return "\n".join(cmds)

    def _camera(self, camera, rx, ry, rz, zoom_factor):
        lines = ["orient prot"]
        if camera == "side":
            lines.append("turn y, 90")
        elif camera == "top":
            lines.append("turn x, -90")
        elif camera == "bottom":
            lines.append("turn x, 90")
        elif camera == "back":
            lines.append("turn y, 180")
        elif camera == "iso":
            lines += ["turn x, 45", "turn y, 30"]
        elif camera == "custom":
            lines += [f"turn x, {rx}", f"turn y, {ry}", f"turn z, {rz}"]
        lines.append(f"zoom visible, {zoom_factor}")
        return "\n".join(lines)

    def render(self,
               pdb_path,
               quality_preset,
               width, height,
               render_mode, color_mode, background, camera,
               # Optional parameters with defaults
               pymol_bin="",
               selection="all",
               # Cartoon settings
               cartoon_style="oval",
               cartoon_fancy_helices=True,
               cartoon_fancy_sheets=True,
               cartoon_flat_sheets=False,
               cartoon_smooth_loops=5,
               cartoon_tube_radius=0.5,
               cartoon_helix_radius=2.25,
               cartoon_loop_radius=0.3,
               # Stick/sphere settings
               stick_radius=0.25,
               stick_ball=False,
               sphere_scale=1.0,
               sphere_mode="default",
               # Line/mesh/dot settings
               line_width=1.5,
               mesh_width=0.5,
               dot_density=3,
               # Ribbon settings
               ribbon_width=3.0,
               ribbon_smooth=0,
               # Color options
               single_color="deepsalmon",
               custom_per_chain="A:cyan,B:green,C:yellow",
               spectrum_palette="rainbow",
               # Background
               bg_custom="white",
               # Transparency
               transparency=0.0,
               cartoon_transparency=0.0,
               surface_transparency=0.0,
               stick_transparency=0.0,
               sphere_transparency=0.0,
               # Camera
               rotate_x=45.0, rotate_y=30.0, rotate_z=0.0, zoom_factor=1.5,
               # Advanced ray tracing (only used when quality_preset="custom")
               antialias="1 (adaptive)",
               ray_shadows=True,
               ray_trace_mode="normal",
               ray_trace_gain=0.12,
               ray_trace_color="black",
               surface_quality=1,
               # Advanced lighting (only used when quality_preset="custom")
               ambient_occlusion=True,
               ambient_occlusion_scale=25.0,
               depth_cue=True,
               ambient=0.6, direct=0.45, reflect=0.45,
               spec_count=4, spec_reflect=1.0, spec_direct=0.0, shininess=60,
               light_count=6, two_sided_lighting=True, fog_amount=0.5,
               # Labels
               show_labels=False,
               label_selection="name CA",
               label_content="resi",
               label_size=20.0,
               label_color="black",
               # Outline
               outline_width=1.0):

        # Handle various input formats for PDB path:
        # 1. base64file://<filename>/<base64content> - from web UI file upload
        # 2. https://... or http://... - URL to download (e.g., RCSB PDB)
        # 3. Local file path
        pdb_path = str(pdb_path).strip()

        if pdb_path.startswith("base64file://"):
            import base64
            # Parse the base64file format
            parts = pdb_path[len("base64file://"):].split("/", 1)
            if len(parts) == 2:
                filename, b64_content = parts
                # Decode and save to temp file
                pdb_content = base64.b64decode(b64_content).decode("utf-8")
                temp_pdb = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".pdb", delete=False)
                temp_pdb.write(pdb_content)
                temp_pdb.close()
                pdb_path = temp_pdb.name
                print(
                    f"[PDBToImage] Decoded base64 PDB file: {filename} -> {pdb_path}")
            else:
                raise ValueError("Invalid base64file format for pdb_path")

        elif pdb_path.startswith("http://") or pdb_path.startswith("https://"):
            import urllib.request
            import urllib.error
            # Download PDB from URL (e.g., RCSB PDB)
            print(f"[PDBToImage] Downloading PDB from URL: {pdb_path}")
            try:
                # Extract filename from URL or use default
                url_filename = pdb_path.split("/")[-1] or "downloaded.pdb"
                if not url_filename.endswith((".pdb", ".cif", ".mmcif", ".ent")):
                    url_filename += ".pdb"

                # Download to temp file
                req = urllib.request.Request(
                    pdb_path, headers={"User-Agent": "ComfyUI-PDB-Nodes/1.0"})
                with urllib.request.urlopen(req, timeout=30) as response:
                    pdb_content = response.read().decode("utf-8")

                temp_pdb = tempfile.NamedTemporaryFile(
                    mode="w", suffix=".pdb", delete=False)
                temp_pdb.write(pdb_content)
                temp_pdb.close()
                pdb_path = temp_pdb.name
                print(
                    f"[PDBToImage] Downloaded PDB to: {pdb_path} ({len(pdb_content)} bytes)")
            except urllib.error.URLError as e:
                raise RuntimeError(
                    f"Failed to download PDB from URL: {pdb_path}. Error: {e}")
            except Exception as e:
                raise RuntimeError(
                    f"Failed to download PDB from URL: {pdb_path}. Error: {e}")

        else:
            pdb_path = os.path.abspath(
                os.path.expanduser(os.path.expandvars(pdb_path)))

        if not os.path.isfile(pdb_path):
            raise FileNotFoundError(f"PDB not found: {pdb_path}")

        pymol_exec = self._find_pymol(pymol_bin)
        out_png = tempfile.mktemp(suffix=".png")

        # === Apply quality preset if not "custom" ===
        preset = QUALITY_PRESETS.get(quality_preset)
        if preset:
            # Override with preset values
            antialias_val = preset["antialias"]
            ray_shadows_val = preset["ray_shadows"]
            surface_quality_val = preset["surface_quality"]
            ray_trace_mode_val = preset["ray_trace_mode"]
            ao_val = 1 if preset["ambient_occlusion"] else 0
            light_count_val = preset["light_count"]
        else:
            # Use manual/custom settings
            # Parse antialias from string like "1 (adaptive)"
            antialias_val = int(antialias.split()[0]) if isinstance(antialias, str) else int(antialias)
            ray_shadows_val = _as_bool(ray_shadows)
            surface_quality_val = int(surface_quality)
            # Parse ray_trace_mode
            ray_trace_mode_map = {"normal": 0, "outlined": 1, "bw_outlined": 2, "quantized": 3}
            ray_trace_mode_val = ray_trace_mode_map.get(ray_trace_mode, 0)
            ao_val = 1 if _as_bool(ambient_occlusion) else 0
            light_count_val = int(light_count)

        # force a real plate color
        if background == "custom":
            bg = (bg_custom or "white")
        else:
            bg = background  # white or black

        # Determine selection target (defaults to "prot" for all)
        sel = selection.strip() if selection and selection.strip() != "all" else "prot"
        sel_cmd = f"select sel, {selection}\n" if selection and selection.strip() != "all" else ""

        # Cartoon settings string
        fancy_helices = 1 if _as_bool(cartoon_fancy_helices) else 0
        fancy_sheets = 1 if _as_bool(cartoon_fancy_sheets) else 0
        flat_sheets = 1 if _as_bool(cartoon_flat_sheets) else 0

        # Sphere mode mapping
        sphere_mode_map = {"default": 0, "simple": 1, "shader": 2, "fast": 9}
        sphere_mode_val = sphere_mode_map.get(sphere_mode, 0)

        # show mode - expanded with new render modes and full settings
        if render_mode == "cartoon":
            show_cmd = (
                f"show cartoon, prot\n"
                f"cartoon {cartoon_style}, prot\n"
                f"set cartoon_fancy_helices, {fancy_helices}\n"
                f"set cartoon_fancy_sheets, {fancy_sheets}\n"
                f"set cartoon_flat_sheets, {flat_sheets}\n"
                f"set cartoon_smooth_loops, {int(cartoon_smooth_loops)}\n"
                f"set cartoon_tube_radius, {float(cartoon_tube_radius)}\n"
                f"set cartoon_helix_radius, {float(cartoon_helix_radius)}\n"
                f"set cartoon_loop_radius, {float(cartoon_loop_radius)}\n"
                f"set cartoon_highlight_color, grey90\n"
                f"set cartoon_transparency, {float(cartoon_transparency)}"
            )
        elif render_mode == "surface":
            show_cmd = (
                f"show surface, prot\n"
                f"set surface_quality, {surface_quality_val}\n"
                f"set surface_transparency, {float(surface_transparency)}"
            )
        elif render_mode == "sticks":
            stick_ball_val = 1 if _as_bool(stick_ball) else 0
            show_cmd = (
                f"show sticks, prot\n"
                f"set stick_radius, {float(stick_radius)}\n"
                f"set stick_ball, {stick_ball_val}\n"
                f"set stick_transparency, {float(stick_transparency)}"
            )
        elif render_mode == "ball_and_stick":
            show_cmd = (
                f"show spheres, prot\n"
                f"show sticks, prot\n"
                f"set sphere_scale, 0.25\n"
                f"set stick_radius, {float(stick_radius)}\n"
                f"set sphere_transparency, {float(sphere_transparency)}\n"
                f"set stick_transparency, {float(stick_transparency)}"
            )
        elif render_mode == "ribbon":
            show_cmd = (
                f"show ribbon, prot\n"
                f"set ribbon_width, {float(ribbon_width)}\n"
                f"set ribbon_smooth, {int(ribbon_smooth)}"
            )
        elif render_mode == "lines":
            show_cmd = (
                f"show lines, prot\n"
                f"set line_width, {float(line_width)}"
            )
        elif render_mode == "spheres":
            show_cmd = (
                f"show spheres, prot\n"
                f"set sphere_scale, {float(sphere_scale)}\n"
                f"set sphere_mode, {sphere_mode_val}\n"
                f"set sphere_transparency, {float(sphere_transparency)}"
            )
        elif render_mode == "mesh":
            show_cmd = (
                f"show mesh, prot\n"
                f"set mesh_width, {float(mesh_width)}\n"
                f"set surface_quality, {surface_quality_val}"
            )
        elif render_mode == "dots":
            show_cmd = (
                f"show dots, prot\n"
                f"set dot_density, {int(dot_density)}"
            )
        else:
            show_cmd = "show cartoon, prot"

        color_cmds = self._color_cmds(
            color_mode, single_color, custom_per_chain, spectrum_palette)
        cam = self._camera(camera, rotate_x, rotate_y, rotate_z, zoom_factor)

        dc = 1 if _as_bool(depth_cue) else 0
        two_sided = 1 if _as_bool(two_sided_lighting) else 0
        transparency_val = float(transparency) if not preset else 0.0

        # Label commands (optional)
        label_cmds = ""
        if _as_bool(show_labels):
            label_expr = {
                "resn": "resn",
                "resi": "resi", 
                "name": "name",
                "chain": "chain",
                "b": "b",
                "custom": '"%s-%s" % (resn, resi)'
            }.get(label_content, "resi")
            label_cmds = f"""
# Labels
set label_size, {float(label_size)}
set label_color, {label_color}
label {label_selection}, {label_expr}
"""

        # Outline width for traced modes
        outline_cmds = ""
        if ray_trace_mode_val in [1, 2, 3]:  # outlined modes
            outline_cmds = f"""
set ray_trace_gain, {float(ray_trace_gain)}
set ray_trace_color, {ray_trace_color}
"""

        script = f"""
reinitialize
load {shlex.quote(pdb_path)}, prot
{sel_cmd}
hide everything, all
{show_cmd}
{color_cmds}
bg_color {bg}
set opaque_background, 1
set ray_opaque_background, 1

# Quality / Ray Tracing
set antialias, {antialias_val}
set ray_shadow, {1 if ray_shadows_val else 0}
set ray_trace_mode, {ray_trace_mode_val}
{outline_cmds}

# Global Transparency
set transparency, {transparency_val}

# Lighting
set ambient, {float(ambient)}
set direct, {float(direct)}
set reflect, {float(reflect)}
set spec_count, {int(spec_count)}
set spec_reflect, {float(spec_reflect)}
set spec_direct, {float(spec_direct)}
set shininess, {int(shininess)}
set light_count, {light_count_val}
set two_sided_lighting, {two_sided}
set ambient_occlusion_mode, {ao_val}
set ambient_occlusion_scale, {float(ambient_occlusion_scale)}
set depth_cue, {dc}
set fog, {float(fog_amount)}
{label_cmds}
{cam}
png {shlex.quote(out_png)}, width={int(width)}, height={int(height)}, ray=1
quit
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".pml", delete=False) as f:
            f.write(script)
            pml_path = f.name

        try:
            subprocess.run([pymol_exec, "-cq", pml_path],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                "PyMOL CLI failed.\n"
                f"Command: {pymol_exec} -cq {pml_path}\n"
                f"STDOUT:\n{e.stdout}\n\nSTDERR:\n{e.stderr}\n"
            )

        if not os.path.exists(out_png):
            raise RuntimeError("PyMOL did not produce an image (png missing).")

        img = Image.open(out_png).convert("RGB")  # ALWAYS RGB, baked bg
        arr = (np.array(img).astype("float32") / 255.0)[None, ...]  # [1,H,W,3]
        ten = torch.from_numpy(arr)
        return (ten,)


class FolderToPDBQueue:
    """
    Scans a folder for PDB files and provides them as a queue for batch processing.
    Outputs the current PDB path and a list of all PDB files found.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "folder_path": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "/path/to/pdb/folder"
                }),
                "extension": ("STRING", {
                    "default": "*.pdb",
                    "multiline": False,
                }),
                "sort_by": (["name", "date_modified", "date_created", "size"], {"default": "name"}),
                "order": (["ascending", "descending"], {"default": "ascending"}),
            },
            "optional": {
                "index": ("INT", {"default": 0, "min": 0, "max": 10000, "step": 1}),
            }
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("current_pdb_path", "file_list", "total_count")
    FUNCTION = "scan_folder"
    CATEGORY = "Biostructure"

    def scan_folder(self, folder_path, extension="*.pdb", sort_by="name", order="ascending", index=0):
        import glob

        folder_path = os.path.abspath(os.path.expanduser(
            os.path.expandvars(str(folder_path)))).strip()

        if not os.path.isdir(folder_path):
            raise FileNotFoundError(f"Folder not found: {folder_path}")

        # Build glob pattern
        if not extension.startswith("*"):
            extension = "*" + extension
        pattern = os.path.join(folder_path, extension)

        # Get all matching files
        files = glob.glob(pattern)

        if not files:
            raise FileNotFoundError(
                f"No files matching '{extension}' found in {folder_path}")

        # Sort files
        if sort_by == "name":
            files.sort(key=lambda x: os.path.basename(x).lower())
        elif sort_by == "date_modified":
            files.sort(key=lambda x: os.path.getmtime(x))
        elif sort_by == "date_created":
            files.sort(key=lambda x: os.path.getctime(x))
        elif sort_by == "size":
            files.sort(key=lambda x: os.path.getsize(x))

        if order == "descending":
            files.reverse()

        # Get current file by index
        total_count = len(files)
        safe_index = index % total_count if total_count > 0 else 0
        current_file = files[safe_index]

        # Create newline-separated file list
        file_list = "\n".join(files)

        return (current_file, file_list, total_count)


class FileListIndex:
    """
    Selects a file from a newline-separated file list by index.
    Useful for iterating through files in a batch workflow.
    """
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "file_list": ("STRING", {
                    "multiline": True,
                    "forceInput": True,
                }),
                "index": ("INT", {"default": 0, "min": 0, "max": 10000, "step": 1}),
            }
        }

    RETURN_TYPES = ("STRING", "INT")
    RETURN_NAMES = ("file_path", "total_count")
    FUNCTION = "get_file"
    CATEGORY = "Biostructure"

    def get_file(self, file_list, index=0):
        # Split the file list by newlines
        files = [f.strip() for f in file_list.strip().split("\n") if f.strip()]

        if not files:
            raise ValueError("File list is empty")

        total_count = len(files)
        safe_index = index % total_count if total_count > 0 else 0
        selected_file = files[safe_index]

        return (selected_file, total_count)


NODE_CLASS_MAPPINGS["PDBToImage"] = PDBToImage
NODE_CLASS_MAPPINGS["FolderToPDBQueue"] = FolderToPDBQueue
NODE_CLASS_MAPPINGS["FileListIndex"] = FileListIndex

NODE_DISPLAY_NAME_MAPPINGS["PDBToImage"] = "PDB → Image (PyMOL, CLI, RGB plate)"
NODE_DISPLAY_NAME_MAPPINGS["FolderToPDBQueue"] = "Folder to PDB Queue"
NODE_DISPLAY_NAME_MAPPINGS["FileListIndex"] = "File List Index"
