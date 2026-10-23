"""Build the account plugin from the versioned shared skill source."""
from pathlib import Path
import argparse
import json
import re
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parent.parent
inventory = json.loads((root/'_sources/shared-skills-manifest.json').read_text(encoding='utf-8'))
entries = []
skill_names = []
for folder in inventory['plugin_skills'] + ['_jutsu']:
    for file in sorted((root/folder).rglob('*')):
        if file.is_file():
            if file.is_symlink():
                raise ValueError(f'Symlink in package: {file}')
            if file.name == 'SKILL.md':
                skill_names.append(re.search(r'^name:\s*[\"\']?([^\r\n\"\']+)', file.read_text(encoding='utf-8'), re.M).group(1))
            entries.append((file, 'skills/' + file.relative_to(root).as_posix()))
if len(skill_names) != len(set(skill_names)):
    raise ValueError('Duplicate skill names')
args.output.parent.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(args.output, 'w', zipfile.ZIP_DEFLATED) as archive:
    archive.writestr('.claude-plugin/plugin.json', json.dumps(inventory['plugin'], ensure_ascii=False, indent=2))
    for file, name in entries:
        archive.write(file, name)
print(f'Built {args.output}: {len(inventory["plugin_skills"])} primary skills, 17 internal modules; existing account skills are not duplicated.')
