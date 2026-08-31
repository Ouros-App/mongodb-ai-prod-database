import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.apply_mongo import apply_scripts, load_config, validate_unique_indexes


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

    def test_unique_indexes_reject_duplicate_existing_keys(self):
        class Collection:
            def aggregate(self, _pipeline):
                return iter([{"count": 2}])

        class Database:
            def __getitem__(self, _name):
                return Collection()

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "mongo"
            scripts.mkdir()
            (scripts / "indexes.json").write_text(
                '[{"createIndexes":"users","indexes":[{"key":{"user_id":1},"name":"user_id_1","unique":true}]}]',
                encoding="utf-8",
            )
            cfg = {"database": {"scripts_path": "mongo", "execution_order": ["indexes.json"]}}

            with self.assertRaisesRegex(ValueError, "Dados duplicados impedem"):
                validate_unique_indexes(root, cfg, Database())

    def test_unique_indexes_skip_disabled_scripts(self):
        class Database:
            def __getitem__(self, _name):
                raise AssertionError("scripts disabled should not be inspected")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "mongo"
            scripts.mkdir()
            (scripts / "indexes.json").write_text(
                '[{"createIndexes":"users","indexes":[{"key":{"user_id":1},"name":"user_id_1","unique":true}]}]',
                encoding="utf-8",
            )
            cfg = {"database": {"scripts_path": "mongo", "execution_order": [
                {"file": "indexes.json", "mode": "never"}
            ]}}

            validate_unique_indexes(root, cfg, Database())


if __name__ == "__main__":
    unittest.main()
