#!/usr/bin/env python3
"""Audit tracked/unignored files without displaying credential values."""
import argparse,json,os,re,subprocess,tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
THIRD_PARTY=('vendor/','src/MicroPython/ulab/upstream/','src/MicroPython/JPEGDEC/')
PRIVATE_ROOTS=('local-backup/','host-tools/','SD contents/','.build/','simulator/sdcard/','simulator/sdcard.flash/',
               'releases/','sd-card/',
               'builds/MicroPython/apps/','builds/MicroPython/desktop/','sd-card/picoware/apps/','updates/','Tetris Sound/')
TOKENS=re.compile(rb'(?<![A-Za-z0-9])(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|sk-(?:proj-)?[A-Za-z0-9_-]{30,}|AKIA[A-Z0-9]{16}|xox[baprs]-[A-Za-z0-9-]{25,})')
PEM=re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----')
ASSIGNMENT=re.compile(rb'''(?i)["']?(?:wifi_password|api_key|access_token|auth_token|server_password)["']?\s*[:=]\s*["']([^"'\r\n]+)["']''')
TEST_VALUES={b'initial-pass',b'test-only',b'test-key',b'other-test-key'}
TEST_FILES={'simulator/test_preferences.py','simulator/test_trimmed_firmware.py'}
PUBLIC_TEMPLATES={'sd-card/README.md','.env.example'}
PUBLIC_KEYS=('vendor/micropython/lib/mbedtls/tests/','vendor/micropython/lib/pico-sdk/tools/example_keys/')

def git(*args,root=ROOT):
 return subprocess.run(['git','-C',str(root),*args],capture_output=True,check=True).stdout

def candidates(root):
 # An ephemeral Git index applies exactly the project's ignore rules before init.
 # Existing repositories also include already-tracked ignored paths.
 initialized=(root/'.git').exists()
 if initialized:return git('ls-files','--cached','--others','--exclude-standard','-z',root=root).split(b'\0'),True
 with tempfile.TemporaryDirectory(prefix='gungos-public-index-') as d:
  subprocess.run(['git','init','--bare','--quiet',d],check=True)
  return git('--git-dir='+d,'--work-tree='+str(root),'ls-files','--cached','--others','--exclude-standard','-z',root=root).split(b'\0'),False

def audit(root=ROOT):
 names,initialized=candidates(root);names=sorted({os.fsdecode(n) for n in names if n})
 issues=[];fixtures=set();bytes_total=0
 for name in names:
  p=root/name;third_party=name.startswith(THIRD_PARTY)
  if p.is_symlink():issues.append({'file':name,'reason':'symlink: review source portability'});continue
  if not p.is_file():issues.append({'file':name,'reason':'tracked file is missing'});continue
  size=p.stat().st_size;bytes_total+=size
  if size>50*1024*1024:issues.append({'file':name,'reason':'file exceeds project 50 MiB review limit'})
  if ((name.startswith(PRIVATE_ROOTS) or name=='.env' or name.startswith('.env.')) and name not in PUBLIC_TEMPLATES) or p.name=='.DS_Store' or name in ('SHA256SUMS.txt','screenshot.bmp','screenshot.png'):
   issues.append({'file':name,'reason':'private/generated file is a Git candidate'})
  if not third_party and p.suffix.lower() in ('.wav','.zip','.mpy','.uf2','.elf','.map'):
   issues.append({'file':name,'reason':'generated binary or audio must be reviewed as a separate release'})
  data=p.read_bytes()
  if b'\0' in data[:8192]:continue
  for kind,pattern in (('service token',TOKENS),('private key',PEM),('literal credential',ASSIGNMENT)):
   for match in pattern.finditer(data):
    line=data.count(b'\n',0,match.start())+1
    if kind=='private key' and (name.startswith(PUBLIC_KEYS) or name=='vendor/micropython/lib/mbedtls/library/pk_internal.h'):
     fixtures.add(name);continue
    if kind=='literal credential':
     value=match.group(1)
     if name in TEST_FILES and value in TEST_VALUES:fixtures.add(name);continue
     if name.startswith('vendor/micropython/examples/esp32_wifi_csi/') and value==b'your-password':fixtures.add(name);continue
     if third_party and re.fullmatch(rb'\$[A-Z][A-Z_0-9]*',value):fixtures.add(name);continue
    issues.append({'file':name,'line':line,'reason':kind+' pattern; value redacted'})
 # Deployment template is checked structurally, including SSID and nested keys.
 template=root/'sd-card/picoware/settings/picoware.json'
 if template.is_file() and 'sd-card/picoware/settings/picoware.json' in names:
  settings=json.loads(template.read_text())
  for key,value in settings.items():
   if (key=='wifi_ssid' or any(word in key.lower() for word in ('password','api_key','token','secret'))) and value:
    issues.append({'file':str(template.relative_to(root)),'reason':'nonempty deployment credential field: '+key})
 for required in ('LICENSE','CREDITS.md','THIRD_PARTY_NOTICES.md','vendor/revisions.json','vendor/micropython/LICENSE','src/MicroPython/ulab/upstream/LICENSE'):
  if required not in names:issues.append({'file':required,'reason':'required source/license provenance missing from Git candidates'})
 return {'status':'passed' if not issues else 'failed','git_initialized':initialized,'history_audited':False,
         'candidate_files':len(names),'candidate_bytes':bytes_total,'known_public_test_fixtures':sorted(fixtures),'issues':issues,
         'scope':'Git tracked/unignored files; common credential signatures, media/generated exclusions, deployment defaults, source notices and file-size limits. Not a complete legal or secret-detection guarantee.'}

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--root',type=Path,default=ROOT)
 parser.add_argument('--json',action='store_true')
 args=parser.parse_args();report=audit(args.root.resolve())
 if args.json:print(json.dumps(report,indent=2))
 else:
  print(report['status'].upper()+': '+str(report['candidate_files'])+' Git candidate files; '+str(round(report['candidate_bytes']/1024**2,1))+' MiB')
  for issue in report['issues']:print(issue['file']+(':'+str(issue['line']) if 'line' in issue else '')+': '+issue['reason'])
  print('Known upstream/synthetic fixtures reviewed:',len(report['known_public_test_fixtures']))
  print('Git history not audited.' if report['git_initialized'] else 'No Git repository/history exists yet.')
 raise SystemExit(0 if report['status']=='passed' else 1)

if __name__=='__main__':main()
