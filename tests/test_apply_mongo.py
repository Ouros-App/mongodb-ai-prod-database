import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.apply_mongo import apply_scripts, load_config


class ApplyMongoTest(unittest.TestCase):
    def test_load_config_expands_environment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "config.yaml").write_text("database:\n  host: ${MONGODB_HOST}\n", encoding="utf-8")
            with patch.dict(os.environ, {"MONGODB_HOST": "mongo.example.test"}):
                self.assertEqual(load_config(root)["database"]["host"], "mongo.example.test")

    def test_non_transactional_script_resumes_after_failure(self):
        class Control:
            def __init__(self):
                self.document = None

            def create_index(self, *_args, **_kwargs):
                return None

            def find_one(self, _query):
                return dict(self.document) if self.document else None

            def update_one(self, query, update, **_kwargs):
                self.document = {**(self.document or {}), **query, **update["$set"]}

        class Database:
            def __init__(self):
                self.control = Control()
                self.executed = []
                self.fail = True

            def __getitem__(self, _name):
                return self.control

            def command(self, command):
                self.executed.append(command["step"])
                if command["step"] == 2 and self.fail:
                    self.fail = False
                    raise RuntimeError("failed")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "mongo"
            scripts.mkdir()
            (scripts / "steps.json").write_text('[{"step": 1}, {"step": 2}]', encoding="utf-8")
            cfg = {"database": {"scripts_path": "mongo", "execution_order": [
                {"file": "steps.json", "mode": "once", "transactional": False, "idempotent": True}
            ]}}
            db = Database()
            with self.assertRaises(RuntimeError):
                apply_scripts(root, cfg, db, "commit")
            apply_scripts(root, cfg, db, "commit")
            self.assertEqual(db.executed, [1, 2, 2])


if __name__ == "__main__":
    unittest.main()
