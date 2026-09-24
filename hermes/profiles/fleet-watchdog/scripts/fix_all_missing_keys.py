"""Copy OPENROUTER_API_KEY from hyakka-crawl (source of truth) into profiles missing it."""
import glob
import os
import shutil

HOME = os.path.expanduser('~/.hermes/profiles')
SRC = os.path.join(HOME, 'hyakka-crawl', '.env')


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

for d in sorted(glob.glob(os.path.join(HOME, '*/'))):
    env = os.path.join(d, '.env')
    if get_key(env):
        continue
    if os.path.exists(env):
        with open(env, 'a') as f:
            f.write('\n' + key_line + '\n')
    else:
        os.makedirs(d, exist_ok=True)
        with open(env, 'w') as f:
            f.write(key_line + '\n')
    print('fixed:', d)
