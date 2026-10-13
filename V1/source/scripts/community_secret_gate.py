"""Scan the exact proposed Git tree without printing secret values.

Run after git add, before commit. Does not scan/rewrite historical commits.
"""
from pathlib import Path
import json
import os
import re
import subprocess
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def main():
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=ROOT)
    names = [p for p in git('ls-files', '-z').decode().split('\0') if p]
    environment = {**dotenv_values(ROOT / '.env'), **dotenv_values(ROOT / 'frontend/.env.local'), **os.environ}
    values = {k:v for k,v in environment.items() if re.search('KEY|TOKEN|PASSWORD|SECRET',k,re.I)
              and isinstance(v,str) and len(v)>=8}
    patterns = {
        'github_token': r'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})',
        'private_key': r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
        'provider_key': r'\bsk-[A-Za-z0-9_-]{28,}',
        'aws_access_key': r'\bAKIA[A-Z0-9]{16}\b',
        'credential_url': r'\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?):\/\/[^\s:/]+:([^\s@]+)@',
    }
    findings, reviewed = [], []
    for name in names:
        path = Path(name)
        if (path.name.startswith('.env') and path.name != '.env.example') or any(
            part in {'.runtime','__pycache__','node_modules','.next','logs','outputs'} for part in path.parts
        ) or path.suffix in {'.pyc','.tsbuildinfo','.pem','.key'} or path.name.startswith('conversation-'):
            findings.append({'path':name,'rule':'forbidden_release_file'})
        data = git('show', ':'+name)
        for key,value in values.items():
            if value.encode() in data:
                findings.append({'path':name,'rule':'configured_secret:'+key})
        if b'\0' in data:
            continue
        for number,line in enumerate(data.decode('utf-8',errors='replace').splitlines(),1):
            for rule,pattern in patterns.items():
                match = re.search(pattern,line)
                if not match:
                    continue
                # Narrow reviewed exception: template comment with literal password placeholder.
                if name == '.env.example' and rule == 'credential_url' and line.lstrip().startswith('#') and match.group(1) == 'password':
                    reviewed.append({'path':name,'line':number,'rule':'commented_placeholder'})
                else:
                    findings.append({'path':name,'line':number,'rule':rule})
    report = {'status':'FAIL' if findings else 'PASS','scanned_index_files':len(names),
              'findings':findings,'reviewed_placeholders':reviewed}
    output = ROOT / '.runtime/release/community/secret-gate.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
    return bool(findings)


if __name__ == '__main__':
    raise SystemExit(main())
