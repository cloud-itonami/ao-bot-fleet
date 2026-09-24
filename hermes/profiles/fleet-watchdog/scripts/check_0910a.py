import sys, os, json, glob
sys.path.insert(0, '~/.hermes/scripts')
import fleet_cron_watchdog as w

def key_of(p):
    env = os.path.join(p, '.env')
    k = None
    if os.path.exists(env):
        for line in open(env):
            if line.startswith('OPENROUTER_API_KEY='):
                v = line.strip().split('=',1)[1]
                if len(v) > 5:
                    k = v
    return k

default_env = '~/.hermes/.env'
dk = key_of('~/.hermes')
print('default .env exists', os.path.exists(default_env), 'key', dk is not None)
missing = []
for _name, home in w.profile_homes():
    p = str(home)
    if key_of(p) is None and dk is None:
        missing.append(p)
print('PROVIDER-MISSING-KEY(after fallback):', len(missing), missing[:10])

homes = {}
for f in glob.glob(os.path.expanduser('~/.hermes/cron/jobs.json')) + glob.glob(os.path.expanduser('~/.hermes/profiles/*/cron/jobs.json')):
    try:
        data = json.load(open(f))
    except Exception as e:
        print('ERR', f, e); continue
    for j in data.get('jobs', []):
        le = (j.get('last_error') or '')
        if 'drift' in le.lower():
            prof = f.split('/profiles/')[1].split('/cron')[0] if '/profiles/' in f else 'default'
            homes[j['id']] = (prof, j.get('name'), j.get('provider'), j.get('model'))
print('drift_skip jobs:', len(homes))
unpinned = {i:v for i,v in homes.items() if not v[2] or not v[3]}
print('UNPINNED:', len(unpinned))
for i,v in sorted(homes.items()):
    print(' ', i, v)
