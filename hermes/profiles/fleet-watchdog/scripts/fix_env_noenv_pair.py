import re, os

src = open('~/.hermes/profiles/hyakka-crawl/.env').read()
m = re.search(r'^OPENROUTER_API_KEY=(.+)$', src, re.M)
if not m:
    raise SystemExit('OPENROUTER_API_KEY not found in hyakka-crawl/.env (source of truth)')
key_line = m.group(0)

for p in ['shinshi-chat-ops', 'suji-anatomy']:
    path = '~/.hermes/profiles/%s/.env' % p
    try:
        txt = open(path).read()
    except FileNotFoundError:
        txt = ''
    if re.search(r'^OPENROUTER_API_KEY=..*$', txt, re.M):
        print(p, 'ALREADY_HAS (skip)')
        continue
    if txt.strip():
        newtxt = txt.rstrip('\n') + '\n' + key_line + '\n'
    else:
        newtxt = key_line + '\n'
    open(path, 'w').write(newtxt)
    print(p, 'CREATED_OR_APPENDED')