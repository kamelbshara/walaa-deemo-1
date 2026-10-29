"""Publish only explicitly allowed assets, never classroom records or source."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
out=root/'public'
out.mkdir(exist_ok=True)
for name in ('index.html','app.js','style.css','dice-lab.html','lesson-plan.md'):
    shutil.copy2(root/name,out/name)
shutil.copytree(root/'vendor',out/'vendor',dirs_exist_ok=True)
