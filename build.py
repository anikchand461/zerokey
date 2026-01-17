# build.py
import os
import shutil
import subprocess
import sys

def build_for_platform():
    system = sys.platform
    if system == "win32":
        name = "zerokey.exe"
        opts = ["--onefile", "--windowed"]  # --windowed hides console on Windows (optional)
    elif system == "darwin":
        name = "zerokey-macos"
        opts = ["--onefile"]
    else:  # linux
        name = "zerokey-linux"
        opts = ["--onefile"]

    print(f"Building for {system} → {name}")
    cmd = [
        "pyinstaller",
        "--name", name,
        "--clean",
        "--noconfirm",
        *opts,
        "cli.py"
    ]
    subprocess.run(cmd, check=True)

    # Move binary to dist/
    src = os.path.join("dist", name)
    dst = os.path.join("bin", name)
    os.makedirs("bin", exist_ok=True)
    shutil.move(src, dst)
    print(f"✅ Binary saved to: bin/{name}")

if __name__ == "__main__":
    build_for_platform()
