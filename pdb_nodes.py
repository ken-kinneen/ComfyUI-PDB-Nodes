# PDB → Image (PyMOL, CLI, RGB only, baked background)

import os, tempfile, subprocess, shlex, shutil
import numpy as np
import torch
from PIL import Image

NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}

def _as_bool(v):
    return str(v).strip().lower() in ("1", "true", "yes", "y", "on")

class PDBToImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "pdb_path": ("STRING", {
                    "multiline": False,
                    "placeholder": "/Volumes/ComfySSD/ComfyUI/PDB/1crn.pdb"
                }),
                "pymol_bin": ("STRING", {
                    "default": "",
                    "multiline": False,
                    "placeholder": "/Users/you/miniforge3/envs/pymol/bin/pymol"
                }),

                "width":  ("INT",   {"default": 1024, "min": 256,  "max": 4096, "step": 64}),
                "height": ("INT",   {"default": 1024, "min": 256,  "max": 4096, "step": 64}),

                "render_mode": (["cartoon", "surface", "sticks", "ball_and_stick"], {"default": "cartoon"}),
                "cartoon_style": (["oval", "loop", "putty"], {"default": "oval"}),

                "color_mode": (["chain", "element", "single", "custom"], {"default": "chain"}),
                "single_color": ("STRING", {"default": "deepsalmon"}),
                "custom_per_chain": ("STRING", {
                    "default": "A:cyan,B:green,C:yellow",
                    "placeholder": "A:cyan,B:green …"
                }),

               
                "background": (["white", "black", "custom"], {"default": "white"}),
                "bg_custom":  ("STRING", {"default": "white"}),

                "ambient_occlusion": ("BOOLEAN", {"default": True}),
                "depth_cue":         ("BOOLEAN", {"default": True}),

                "ambient":      ("FLOAT", {"default": 0.6, "min": 0.0, "max": 1.0,  "step": 0.05}),
                "spec_count":   ("INT",   {"default": 4,   "min": 0,   "max": 8,    "step": 1}),
                "spec_reflect": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0,  "step": 0.1}),
                "shininess":    ("INT",   {"default": 60,  "min": 0,   "max": 128,  "step": 2}),
                "light_count":  ("INT",   {"default": 6,   "min": 1,   "max": 8,    "step": 1}),
                "fog_amount":   ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0,  "step": 0.05}),

                "camera":     (["auto_orient", "front", "side", "top", "iso", "custom"], {"default": "iso"}),
                "rotate_x":   ("FLOAT", {"default": 45.0, "min": -180.0, "max": 180.0, "step": 1.0}),
                "rotate_y":   ("FLOAT", {"default": 30.0, "min": -180.0, "max": 180.0, "step": 1.0}),
                "zoom_factor":("FLOAT", {"default": 1.50, "min": 0.5, "max": 3.0, "step": 0.05}),
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
        raise RuntimeError("PyMOL CLI not found. Provide full path in 'pymol_bin', or export PYMOL_BIN, or ensure 'pymol' on PATH.")

    def _color_cmds(self, color_mode, single_color, custom_per_chain):
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
        cmds = []
        items = [x.strip() for x in custom_per_chain.split(",") if ":" in x]
        for it in items:
            ch, col = it.split(":", 1)
            cmds.append(f"color {col.strip()}, chain {ch.strip()}")
        return "\n".join(cmds)

    def _camera(self, camera, rx, ry, zoom_factor):
        lines = ["orient prot"]
        if camera == "side":
            lines.append("turn y, 90")
        elif camera == "top":
            lines.append("turn x, -90")
        elif camera == "iso":
            lines += ["turn x, 45", "turn y, 30"]
        elif camera == "custom":
            lines += [f"turn x, {rx}", f"turn y, {ry}"]
        lines.append(f"zoom visible, {zoom_factor}")
        return "\n".join(lines)

    def render(self,
               pdb_path, pymol_bin,
               width, height,
               render_mode, cartoon_style,
               color_mode, single_color, custom_per_chain,
               background, bg_custom,
               ambient_occlusion, depth_cue,
               ambient, spec_count, spec_reflect, shininess, light_count, fog_amount,
               camera, rotate_x, rotate_y, zoom_factor):

        pdb_path = os.path.abspath(os.path.expanduser(os.path.expandvars(str(pdb_path)))).strip()
        if not os.path.isfile(pdb_path):
            raise FileNotFoundError(f"PDB not found: {pdb_path}")

        pymol_exec = self._find_pymol(pymol_bin)
        out_png = tempfile.mktemp(suffix=".png")

        # force a real plate color
        if background == "custom":
            bg = (bg_custom or "white")
        else:
            bg = background  # white or black

        # show mode
        if render_mode == "cartoon":
            show_cmd = (
                "show cartoon, prot\n"
                f"cartoon {cartoon_style}, prot\n"
                "set cartoon_fancy_helices, 1\n"
                "set cartoon_highlight_color, grey90"
            )
        elif render_mode == "surface":
            show_cmd = "show surface, prot\nset surface_quality, 1"
        elif render_mode == "sticks":
            show_cmd = "show sticks, prot\nset stick_radius, 0.25"
        else:
            show_cmd = (
                "show spheres, prot\n"
                "show sticks, prot\n"
                "set sphere_scale, 0.17\n"
                "set stick_radius, 0.22"
            )

        color_cmds = self._color_cmds(color_mode, single_color, custom_per_chain)
        cam = self._camera(camera, rotate_x, rotate_y, zoom_factor)

        ao = 1 if _as_bool(ambient_occlusion) else 0
        dc = 1 if _as_bool(depth_cue) else 0

        
        script = f"""
reinitialize
load {shlex.quote(pdb_path)}, prot
hide everything, all
{show_cmd}
{color_cmds}
bg_color {bg}
set opaque_background, 1
set ray_opaque_background, 1
set ambient, {float(ambient)}
set spec_count, {int(spec_count)}
set spec_reflect, {float(spec_reflect)}
set shininess, {int(shininess)}
set light_count, {int(light_count)}
set ambient_occlusion_mode, {ao}
set depth_cue, {dc}
set fog, {float(fog_amount)}
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
        
        folder_path = os.path.abspath(os.path.expanduser(os.path.expandvars(str(folder_path)))).strip()
        
        if not os.path.isdir(folder_path):
            raise FileNotFoundError(f"Folder not found: {folder_path}")
        
        # Build glob pattern
        if not extension.startswith("*"):
            extension = "*" + extension
        pattern = os.path.join(folder_path, extension)
        
        # Get all matching files
        files = glob.glob(pattern)
        
        if not files:
            raise FileNotFoundError(f"No files matching '{extension}' found in {folder_path}")
        
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
