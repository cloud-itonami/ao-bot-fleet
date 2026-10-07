import shutil, os
src = "~/.hermes/profiles/hyakka-crawl/.env"
dst_dir = "~/.hermes/profiles/minidrama"
dst = os.path.join(dst_dir, ".env")
if not os.path.exists(dst):
    os.makedirs(dst_dir, exist_ok=True)
    with open(src) as f:
        for line in f:
            if line.startswith("OPENROUTER_API_KEY=") and len(line.split("=",1)[1].strip()) > 5:
                with open(dst, "w") as g:
                    g.write(line)
                print("CREATED", dst)
                break
else:
    print("EXISTS", dst)
