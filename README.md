# MongoDB database template

Template de banco MongoDB versionado por comandos JSON.

## Uso

```bash
cp .env.example .env
pip install -r requirements.txt
python scripts/apply_mongo.py
```

Os scripts ficam em `mongo/` e a ordem fica em `config.yaml`. Cada execução registra uma versão com commit e comentário. Os modos são `always`, `on_change`, `once` e `never`.

No GitHub Actions, configure `MONGODB_HOST`, `MONGODB_PORT`, `MONGODB_DB`, `MONGODB_USER`, `MONGODB_PASSWORD` e `MONGODB_AUTH_DB` como secrets. O deploy roda somente em push para `main`.
