import re, os

src = open('~/.hermes/profiles/hyakka-crawl/.env').read()
m = re.search(r'^OPENROUTER_API_KEY=(.+)$', src, re.M)
if not m:
    raise SystemExit('OPENROUTER_API_KEY not found in hyakka-crawl/.env (source of truth)')
key_line = m.group(0)

p = 'kbb-migrator'
path = '~/.hermes/profiles/%s/.env' % p
try:
    txt = open(path).read()
except FileNotFoundError:
    txt = ''
if re.search(r'^OPENROUTER_API_KEY=..*$', txt, re.M):
    print(p, 'ALREADY_HAS (skip)')
elif txt.strip():
    open(path, 'w').write(txt.rstrip('\n') + '\n' + key_line + '\n')
    print(p, 'APPENDED')
else:
    open(path, 'w').write(key_line + '\n')
    print(p, 'CREATED')