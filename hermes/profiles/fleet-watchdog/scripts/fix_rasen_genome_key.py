"""Create rasen-genome/.env with OPENROUTER_API_KEY copied from hyakka-crawl (source of truth)."""
import os

SRC = os.path.expanduser('~/.hermes/profiles/hyakka-crawl/.env')
TGT = os.path.expanduser('~/.hermes/profiles/rasen-genome/.env')


def get_key(path):
    try:
        with open(path) as f:
            for line in f:
                if line.startswith('OPENROUTER_API_KEY=') and len(line.strip()) > len('OPENROUTER_API_KEY='):
                    return line.strip()
    except OSError:
        return None
    return None


key_line = get_key(SRC)
assert key_line, f'source key missing in {SRC}'

tdir = os.path.dirname(TGT)
os.makedirs(tdir, exist_ok=True)
if os.path.exists(TGT):
    # append only if key absent
    with open(TGT) as f:
        existing = f.read()
    if 'OPENROUTER_API_KEY=' in existing:
        print('already has key, no change:', TGT)
    else:
        with open(TGT, 'a') as f:
            f.write('\n' + key_line + '\n')
        print('appended key to existing:', TGT)
else:
    with open(TGT, 'w') as f:
        f.write(key_line + '\n')
    print('created with key:', TGT)

# verify
with open(TGT) as f:
    ok = any(l.startswith('OPENROUTER_API_KEY=') and len(l.strip()) > len('OPENROUTER_API_KEY=') for l in f)
print('verify has non-empty OPENROUTER_API_KEY:', ok)