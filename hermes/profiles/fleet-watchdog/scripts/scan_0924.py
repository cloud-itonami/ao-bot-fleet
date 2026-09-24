import sys, io, contextlib
sys.path.insert(0, '~/.hermes/scripts')
import fleet_cron_watchdog as w
print('default .env exists:', __import__('os').path.exists('~/.hermes/.env'))
print('default .env key:', 'OPENROUTER_API_KEY' in open('~/.hermes/.env').read() if __import__('os').path.exists('~/.hermes/.env') else False)
missing = []
for name, home in w.profile_homes():
    res = w.check_provider_key(name, home)
    if res:
        missing.append((name, res))
print('PROVIDER-MISSING-KEY count:', len(missing))
for m in missing:
    print(m)
