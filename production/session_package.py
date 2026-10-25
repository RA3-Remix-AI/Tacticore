"""Resolve only the package explicitly identified by the authoritative session."""
import hashlib,re
from pathlib import Path

def verify_session_package(session):
 if session.get('mod_big'):
  package=Path(session['mod_big'])
  if not package.is_absolute():raise RuntimeError('Session mod_big must be absolute')
  package=package.resolve()
 else:
  config=session.get('mod_config')
  if not config:
   matches=re.findall(r'(?i)(?:^|\s)-modConfig\s+(?:"([^"]+)"|(\S+))',session.get('arguments',''))
   if len(matches)!=1:raise RuntimeError('Require explicit mod_big or one modConfig')
   config=next(x for x in matches[0] if x)
  config=Path(config)
  if not config.is_absolute():raise RuntimeError('Session mod_config must be absolute')
  config=config.resolve();entries=[]
  for line in config.read_text(encoding='utf-8-sig').splitlines():
   line=line.strip()
   if re.match(r'(?i)^add-big(?:\s|$)',line):
    match=re.fullmatch(r'(?i)add-big\s+(?:"([^"\r\n]+)"|([^\s]+))\s*',line)
    if not match:raise RuntimeError('Unsupported add-big syntax')
    entries.append(next(x for x in match.groups() if x is not None))
  if len(entries)!=1:raise RuntimeError('Require exactly one add-big package')
  relative=Path(entries[0]);package=(config.parent/relative).resolve()
  if relative.is_absolute() or package.parent!=config.parent or relative.name!=entries[0] or package.suffix.lower()!='.big':raise RuntimeError('Derived package must be adjacent to skudef')
 if hashlib.sha256(package.read_bytes()).hexdigest()!=session.get('mod_sha256'):raise RuntimeError('Mod changed from recorded session')
 return package
