# ComfyUI-PDB-Nodes

Custom ComfyUI nodes for visualizing PDB (Protein Data Bank) protein structure files using PyMOL.

## Nodes

### PDBToImage
Renders a PDB file to an image using PyMOL CLI.

**Features:**
- Multiple render modes: cartoon, surface, sticks, ball_and_stick
- Color modes: chain, element, single color, custom per-chain
- Camera presets: auto, front, side, top, iso, custom rotation
- Lighting controls: ambient occlusion, depth cue, fog
- Background options: white, black, custom

### FolderToPDBQueue
Scans a folder for PDB files and provides them as a queue for batch processing.

**Outputs:**
- `current_pdb_path`: Path to the current PDB file
- `file_list`: Newline-separated list of all PDB files
- `total_count`: Total number of PDB files found

### FileListIndex
Selects a file from a newline-separated file list by index.

**Outputs:**
- `file_path`: Selected file path
- `total_count`: Total files in list

## Requirements

- Python 3.9+
- PyMOL (automatically installed via pip)

## Installation

1. Clone this repo into your ComfyUI `custom_nodes` folder:
   ```bash
   cd ComfyUI/custom_nodes
   git clone https://github.com/ken-kinneen/ComfyUI-PDB-Nodes.git
   ```

2. Install requirements (includes PyMOL):
   ```bash
   cd ComfyUI-PDB-Nodes
   pip install -r requirements.txt
   ```

3. Restart ComfyUI

## Usage

PyMOL is automatically found if installed via pip. You can also set the `PYMOL_BIN` environment variable or specify the path directly in the node.
