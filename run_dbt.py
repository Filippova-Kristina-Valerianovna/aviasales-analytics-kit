import os
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values


def main():
    root = Path(__file__).resolve().parent
    env_file = root / ".env"

    if not env_file.is_file():
        sys.exit("Missing .env file in project root.")

    settings = dotenv_values(env_file)
    required = [
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_USER",
        "POSTGRES_DB",
        "POSTGRES_PASSWORD",
    ]

    missing = [key for key in required if not settings.get(key)]
    if missing:
        sys.exit("Missing .env settings: " + ", ".join(missing))

    if len(sys.argv) < 2:
        sys.exit("Usage: dbt_local.bat <dbt command> [options]")

    env = os.environ.copy()
    env.update({
        key: settings[key]
        for key in required
        if key != "POSTGRES_PASSWORD"
    })
    env["DBT_ENV_SECRET_POSTGRES_PASSWORD"] = settings["POSTGRES_PASSWORD"]

    dbt_executable = Path(sys.executable).parent / "Scripts" / "dbt.exe"
    if not dbt_executable.is_file():
        sys.exit("dbt.exe not found in the current Python environment.")

    command = [
        str(dbt_executable),
        *sys.argv[1:],
        "--project-dir",
        str(root / "dbt_project"),
        "--profiles-dir",
        str(Path.home() / ".dbt"),
    ]

    result = subprocess.run(command, cwd=root, env=env)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())