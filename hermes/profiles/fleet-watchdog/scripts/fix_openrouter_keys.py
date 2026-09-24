import re

src = open('~/.hermes/profiles/hyakka-crawl/.env').read()
m = re.search(r'^OPENROUTER_API_KEY=(.+)$', src, re.M)
key_line = m.group(0)

profiles = ['adsk', 'adska', 'animeka', 'babiniku-support', 'dougaka', 'gameka',
            'gftd-support', 'isekai-support', 'kotoba-cloud-support',
            'kotoba-lang-support', 'mangaka']

for p in profiles:
    path = '~/.hermes/profiles/%s/.env' % p
    txt = open(path).read()
    if re.search(r'^OPENROUTER_API_KEY=..*$', txt, re.M):
        print(p, 'ALREADY_HAS (skip)')
        continue
    if txt.strip():
        newtxt = txt.rstrip('\n') + '\n' + key_line + '\n'
    else:
        newtxt = key_line + '\n'
    open(path, 'w').write(newtxt)
    print(p, 'APPENDED')
