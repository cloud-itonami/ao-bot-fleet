import sys
from pathlib import Path

sys.path.insert(0, '~/.hermes/scripts')
import fleet_cron_watchdog as w

probs = []
for name, home in w.profile_homes():
    probs += w.check_provider_key(name, home)

print(f'provider-missing-key: {len(probs)}')
for p in probs:
    print('  -', p)