#!/usr/bin/env python3
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import ConfigurationError

ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def load_config(root: Path) -> dict:
    raw = yaml.safe_load((root / "config.yaml").read_text(encoding="utf-8"))

    def expand(value):
        if isinstance(value, str):
            return ENV_RE.sub(lambda match: os.environ[match.group(1)], value)
        if isinstance(value, list):
            return [expand(item) for item in value]
        if isinstance(value, dict):
            return {key: expand(item) for key, item in value.items()}
        return value

    return expand(raw)


def script_entries(root: Path, cfg: dict) -> list[tuple[Path, str, bool, bool]]:
    directory = root / cfg["database"]["scripts_path"]
    entries, seen = [], set()
    for item in cfg["database"]["execution_order"]:
        name, mode = (item, "on_change") if isinstance(item, str) else (item.get("file"), item.get("mode", "on_change"))
        transactional = item.get("transactional", True) if isinstance(item, dict) else True
        idempotent = item.get("idempotent", False) if isinstance(item, dict) else False
        path = Path(name) if isinstance(name, str) else None
        identity = path.as_posix() if path else ""
        if not path or path.is_absolute() or ".." in path.parts or path.suffix != ".json" or identity in seen or mode not in {"always", "on_change", "once", "never"}:
            raise ValueError("Cada script exige arquivo JSON relativo e modo valido.")
        target = directory / path
        if not target.is_file():
            raise FileNotFoundError(f"Script MongoDB nao encontrado: {target}")
        seen.add(identity)
        if not transactional and not idempotent:
            raise ValueError("Scripts nao transacionais devem declarar idempotent: true.")
        entries.append((target, mode, transactional, idempotent))
    return entries


def git_value(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def apply_scripts(root: Path, cfg: dict, db, commit_id: str) -> None:
    control = db["controle_scripts_mongo"]
    control.create_index("arquivo", unique=True)
    base = root / cfg["database"]["scripts_path"]
    for path, mode, transactional, _ in script_entries(root, cfg):
        identity = path.relative_to(base).as_posix()
        content = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(content.encode()).hexdigest()
        previous = control.find_one({"arquivo": identity})
        completed = previous and previous.get("status", "completed") == "completed"
        if mode == "never" or (mode == "once" and completed) or (mode == "on_change" and completed and previous["checksum"] == checksum):
            print(f"[SKIP] {identity}: {mode}")
            continue
        commands = json.loads(content)
        commands = commands if isinstance(commands, list) else [commands]
        if transactional:
            with db.client.start_session() as session, session.start_transaction():
                for command in commands:
                    db.command(command, session=session)
                control.update_one(
                    {"arquivo": identity},
                    {"$set": {"checksum": checksum, "commit_id": commit_id, "status": "completed", "next_command": len(commands)}},
                    upsert=True,
                    session=session,
                )
        else:
            start = previous.get("next_command", 0) if previous and previous.get("checksum") == checksum and not completed else 0
            control.update_one(
                {"arquivo": identity},
                {"$set": {"checksum": checksum, "commit_id": commit_id, "status": "running", "next_command": start}},
                upsert=True,
            )
            for index, command in enumerate(commands[start:], start=start):
                db.command(command)
                control.update_one({"arquivo": identity}, {"$set": {"next_command": index + 1}})
            control.update_one({"arquivo": identity}, {"$set": {"status": "completed"}})
        print(f"[RUN] {identity}: {mode}")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    load_dotenv(root / ".env")
    cfg = load_config(root)
    db_cfg = cfg["database"]
    tls = str(db_cfg["tls"]).lower() in {"1", "true", "yes"}
    tls_options = {"tls": tls}
    if db_cfg.get("tls_ca_file"):
        tls_options["tlsCAFile"] = db_cfg["tls_ca_file"]
    client = MongoClient(db_cfg["connection_url"], **tls_options)
    try:
        db = client[db_cfg["name"]] if db_cfg.get("name") else client.get_default_database()
    except ConfigurationError as exc:
        raise ValueError("A URI MongoDB deve informar o banco no caminho da URL.") from exc
    commit_id = os.getenv("GITHUB_SHA") or git_value(root, "rev-parse", "HEAD")
    commit_message = os.getenv("GITHUB_COMMIT_MESSAGE") or git_value(root, "log", "-1", "--pretty=%B")
    if commit_id == "unknown":
        raise RuntimeError("Nao foi possivel identificar o commit atual.")
    apply_scripts(root, cfg, db, commit_id)
    version = db["controle_contadores"].find_one_and_update({"_id": "versao"}, {"$inc": {"value": 1}}, upsert=True, return_document=ReturnDocument.AFTER)["value"]
    db[db_cfg["version_collection"]].insert_one({"versao": version, "commit_id": commit_id, "comentario_commit": commit_message})
    client.close()


if __name__ == "__main__":
    main()
