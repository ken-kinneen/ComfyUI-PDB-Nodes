# ComfyUI-PDB-Nodes

Custom ComfyUI nodes for visualizing PDB (Protein Data Bank) protein structure files using PyMOL.

## Nodes

### PDBToImage

Renders a PDB file to an image using PyMOL CLI with professional-quality ray tracing.

## Core Inputs (Required)

| Parameter | Options | Description |
|-----------|---------|-------------|
| `pdb_path` | String | Path, URL, or base64 PDB data |
| `quality_preset` | draft, standard, high, publication, publication_outlined, custom | Controls rendering quality |
| `width` / `height` | 256-4096 | Output image dimensions |
| `render_mode` | cartoon, surface, sticks, ball_and_stick, ribbon, lines, spheres, mesh, dots | Visualization style |
| `color_mode` | chain, element, single, custom, spectrum, secondary_structure, b_factor, hydrophobicity | Coloring scheme |
| `background` | white, black, custom | Background color |
| `camera` | auto_orient, front, back, side, top, bottom, iso, custom | Camera angle |

## Quality Presets

Presets automatically configure ray tracing, shadows, antialiasing, and lighting:

| Preset | Speed | Quality | Best For |
|--------|-------|---------|----------|
| `draft` | ~2s | Preview | Quick iteration, testing layouts |
| `standard` | ~5s | Good | General use, web display |
| `high` | ~15s | High | Presentations, detailed views |
| `publication` | ~30s+ | Maximum | Papers, posters, print |
| `publication_outlined` | ~30s+ | Maximum | Publication with edge outlines |
| `custom` | Varies | Manual | Full control (uses advanced options) |

## Optional Inputs (Full Customization)

### Selection Filter
| Parameter | Default | Description |
|-----------|---------|-------------|
| `selection` | "all" | PyMOL selection (e.g., "chain A", "resi 1-100") |

### Cartoon Settings
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `cartoon_style` | oval | oval, loop, putty, rect, tube, arrow, dumbbell | Cartoon tube style |
| `cartoon_fancy_helices` | true | bool | Fancy helix rendering |
| `cartoon_fancy_sheets` | true | bool | Fancy sheet rendering |
| `cartoon_flat_sheets` | false | bool | Flat vs curved sheets |
| `cartoon_smooth_loops` | 5 | 0-20 | Loop smoothing level |
| `cartoon_tube_radius` | 0.5 | 0.1-2.0 | Tube radius |
| `cartoon_helix_radius` | 2.25 | 0.5-5.0 | Helix radius |
| `cartoon_loop_radius` | 0.3 | 0.1-1.0 | Loop radius |

### Stick/Sphere Settings
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `stick_radius` | 0.25 | 0.05-1.0 | Stick thickness |
| `stick_ball` | false | bool | Show balls at atoms |
| `sphere_scale` | 1.0 | 0.1-3.0 | Sphere size multiplier |
| `sphere_mode` | default | default, simple, shader, fast | Sphere rendering mode |

### Line/Mesh/Dot Settings
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `line_width` | 1.5 | 0.5-10.0 | Line thickness |
| `mesh_width` | 0.5 | 0.1-2.0 | Mesh line width |
| `dot_density` | 3 | 1-5 | Dot density level |

### Ribbon Settings
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `ribbon_width` | 3.0 | 0.5-10.0 | Ribbon width |
| `ribbon_smooth` | 0 | 0-10 | Ribbon smoothing |

### Color Options
| Parameter | Default | Description |
|-----------|---------|-------------|
| `single_color` | deepsalmon | PyMOL color name |
| `custom_per_chain` | A:cyan,B:green,C:yellow | Per-chain colors |
| `spectrum_palette` | rainbow | rainbow, blue_white_red, green_white_magenta, cyan_white_yellow, blue_green, yellow_cyan_white |

### Transparency (per representation)
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `transparency` | 0.0 | 0-1 | Global transparency |
| `cartoon_transparency` | 0.0 | 0-1 | Cartoon transparency |
| `surface_transparency` | 0.0 | 0-1 | Surface transparency |
| `stick_transparency` | 0.0 | 0-1 | Stick transparency |
| `sphere_transparency` | 0.0 | 0-1 | Sphere transparency |

### Camera Options
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `rotate_x` | 45.0 | -180 to 180 | X rotation (custom camera) |
| `rotate_y` | 30.0 | -180 to 180 | Y rotation (custom camera) |
| `rotate_z` | 0.0 | -180 to 180 | Z rotation (custom camera) |
| `zoom_factor` | 1.5 | 0.5-5.0 | Zoom level |

### Ray Tracing (quality_preset="custom")
| Parameter | Default | Options/Range | Description |
|-----------|---------|---------------|-------------|
| `antialias` | 1 (adaptive) | 0-4 | Antialiasing level |
| `ray_shadows` | true | bool | Enable shadows |
| `ray_trace_mode` | normal | normal, outlined, bw_outlined, quantized | Rendering style |
| `ray_trace_gain` | 0.12 | 0-1 | Outline strength |
| `ray_trace_color` | black | color | Outline color |
| `surface_quality` | 1 | 0-4 | Surface mesh quality |

### Lighting (quality_preset="custom")
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `ambient` | 0.6 | 0-1 | Ambient light |
| `direct` | 0.45 | 0-1 | Direct light from camera |
| `reflect` | 0.45 | 0-1 | Reflectivity |
| `spec_count` | 4 | 0-8 | Specular count |
| `spec_reflect` | 1.0 | 0-2 | Specular reflection |
| `spec_direct` | 0.0 | 0-1 | Specular from camera |
| `shininess` | 60 | 0-128 | Surface shininess |
| `light_count` | 6 | 1-10 | Number of lights |
| `two_sided_lighting` | true | bool | Light both faces |
| `ambient_occlusion` | true | bool | Enable AO |
| `ambient_occlusion_scale` | 25.0 | 1-100 | AO intensity |
| `depth_cue` | true | bool | Enable depth cue |
| `fog_amount` | 0.5 | 0-1 | Fog density |

### Labels
| Parameter | Default | Description |
|-----------|---------|-------------|
| `show_labels` | false | Enable atom/residue labels |
| `label_selection` | "name CA" | Which atoms to label |
| `label_content` | resi | resn, resi, name, chain, b, custom |
| `label_size` | 20.0 | Label font size |
| `label_color` | black | Label color |

### Outline (for outlined modes)
| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `outline_width` | 1.0 | 0.1-5.0 | Outline thickness |

## Color Modes Explained

| Mode | Description |
|------|-------------|
| `chain` | Different color per chain (A, B, C...) |
| `element` | CPK coloring (C=gray, N=blue, O=red, S=yellow) |
| `single` | One color for entire structure |
| `custom` | Specify per-chain (e.g., "A:cyan,B:green") |
| `spectrum` | Gradient by residue number |
| `secondary_structure` | Helix=red, Sheet=yellow, Loop=green |
| `b_factor` | Gradient by temperature factor (flexibility) |
| `hydrophobicity` | Color by amino acid hydrophobicity |

## Other Nodes

### FolderToPDBQueue
Scans a folder for PDB files for batch processing.

### FileListIndex
Selects a file from a list by index.

## Requirements

- Python 3.9+
- PyMOL (automatically installed via pip)

## Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/your-repo/ComfyUI-PDB-Nodes.git
cd ComfyUI-PDB-Nodes
pip install -r requirements.txt
```

## Input Formats

The `pdb_path` input accepts:

1. **Local file path**: `/path/to/protein.pdb`
2. **URL**: `https://files.rcsb.org/download/1CRN.pdb` (auto-downloaded)
3. **Base64**: `base64file://filename.pdb/<base64content>` (from web UI uploads)

## Examples

**Quick Preview:**
- `quality_preset` = `draft`
- `width/height` = 512

**Publication Quality:**
- `quality_preset` = `publication`
- `width/height` = 2048+
- `render_mode` = `cartoon` or `surface`

**Custom Styling:**
- `quality_preset` = `custom`
- Adjust all ray tracing, lighting, and visualization parameters
