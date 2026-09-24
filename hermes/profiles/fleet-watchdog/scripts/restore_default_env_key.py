import re

src = open('~/.hermes/profiles/hyakka-crawl/.env').read()
m = re.search(r'^OPENROUTER_API_KEY=(.+)$', src, re.M)
if not m:
    raise SystemExit('OPENROUTER_API_KEY not found in hyakka-crawl/.env (source of truth)')
key_line = m.group(0)

# restore the default home .env (watchdog's provider-key fallback source)
DEFAULT_ENV = '~/.hermes/.env'
try:
    dtxt = open(DEFAULT_ENV).read()
except FileNotFoundError:
    dtxt = ''
if re.search(r'^OPENROUTER_API_KEY=..*$', dtxt, re.M):
    print('default .env ALREADY_HAS (skip)')
else:
    body = dtxt.rstrip('\n') + ('\n' if dtxt.strip() else '') if dtxt.strip() else ''
    newtxt = (body + '\n' if body else '') + key_line + '\n'
    open(DEFAULT_ENV, 'w').write(newtxt)
    print('default .env RESTORED_OR_CREATED with OPENROUTER_API_KEY')