#!/usr/bin/env python3
"""Install a carrot-style compiled pkl as the active chestnut bundle pkl.

Moves the previously downloaded chunked pkl aside (backup) and writes the new
one under the exact file name the active bundle expects, so modeld_v2 keeps
using the same bundle metadata (is20hz, overrides, generation).
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, '/data/openpilot')

from openpilot.common.file_chunker import chunk_file, get_chunk_targets, get_manifest_path

MODELS = Path('/data/media/0/models')
SRC = MODELS / 'cinque_v2_carrot_style.pkl'
STEM = 'driving_cinque_terre_model_v2_september_08_2026_tinygrad.pkl'

assert SRC.is_file(), f'compiled pkl missing: {SRC}'

backup = MODELS / 'backup_orig_cinque_v2'
backup.mkdir(exist_ok=True)

moved = []
for f in sorted(MODELS.glob(STEM + '*')):
  dest = backup / f.name
  if dest.exists():
    dest.unlink()
  shutil.move(str(f), str(dest))
  moved.append(f.name)
print('backed up:', moved)

target = MODELS / STEM
if target.exists():
  target.unlink()
shutil.copyfile(SRC, target)

targets = get_chunk_targets(str(target), target.stat().st_size + 10 * 1024 * 1024)
chunk_file(str(target), targets)
manifest = get_manifest_path(str(target))
print('chunked into', len(targets) - 1, 'file(s)')
print('manifest:', manifest, 'exists:', Path(manifest).is_file())
print('installed ok')
