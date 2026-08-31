# mongodb-prod-database

<!-- REPO-METADATA:START -->
<div align="center">

[![Repo Size](https://img.shields.io/github/repo-size/Ouros-App/mongodb-prod-database?style=flat-square&label=REPO%20SIZE)](https://github.com/Ouros-App/mongodb-prod-database)
[![Languages](https://img.shields.io/github/languages/count/Ouros-App/mongodb-prod-database?style=flat-square&label=LANGUAGES)](https://github.com/Ouros-App/mongodb-prod-database/languages)
[![Forks](https://img.shields.io/github/forks/Ouros-App/mongodb-prod-database?style=flat-square&label=FORKS)](https://github.com/Ouros-App/mongodb-prod-database/network/members)
[![Issues](https://img.shields.io/github/issues/Ouros-App/mongodb-prod-database?style=flat-square&label=ISSUES)](https://github.com/Ouros-App/mongodb-prod-database/issues)
[![Pull Requests](https://img.shields.io/github/issues-pr/Ouros-App/mongodb-prod-database?style=flat-square&label=PULL%20REQUESTS)](https://github.com/Ouros-App/mongodb-prod-database/pulls)

</div>
<!-- REPO-METADATA:END -->

Template para versionamento e aplicação de comandos JSON em MongoDB no repositório destinado ao ambiente de produção.

## Status e escopo

O repositório contém um executor Python, configuração de conexão, controle de versões e o script JSON `mongo/colecoes.json`, que mantém a estrutura usada pelo AI server.

A aplicação automática está definida em `.github/workflows/apply-mongo-on-main.yml` e é disparada por push em `main`.

## Componentes

- `scripts/apply_mongo.py`: lê a configuração, conecta ao MongoDB, executa os comandos JSON e registra o estado de cada script.
- `config.yaml`: define a URI, TLS, caminho dos scripts, coleção de versões e ordem de execução.
- `mongo/colecoes.json`: cria os índices de `user_memories`, `thread_owners`, `checkpoints` e `checkpoint_writes`.
- `tests/test_apply_mongo.py`: testa a expansão de variáveis e a retomada de script não transacional após falha.
- `.env.example`: exemplo das variáveis de conexão.

O executor usa a coleção `controle_scripts_mongo` para acompanhar checksums e progresso, `controle_contadores` para incrementar a versão e `controle_versoes` para registrar o commit e o comentário da execução.

## Pré-requisitos

- Python 3.12, usado pelos workflows.
- Uma instância MongoDB acessível pela URI configurada. O executor seleciona explicitamente o banco `mongodb-ai-prod`.
- Certificado CA quando a conexão TLS exigir um arquivo configurado em `MONGODB_TLS_CA_FILE`.

As dependências Python estão fixadas em `requirements.txt`:

- `pymongo==4.10.1`
- `PyYAML==6.0.2`
- `python-dotenv==1.0.1`

## Instalação e configuração

Na raiz do repositório:

```bash
cp .env.example .env
python -m pip install -r requirements.txt
```

Configure no arquivo `.env`:

- `MONGODB_URI`
- `MONGODB_TLS`
- `MONGODB_TLS_CA_FILE`

A configuração expande essas variáveis em `config.yaml`. Para adicionar comandos, edite um arquivo JSON em `mongo/` e registre-o em `database.execution_order`. Os modos aceitos são `always`, `on_change`, `once` e `never`.

Cada entrada é transacional por padrão. Uma entrada não transacional precisa declarar `idempotent: true`.

## Execução

```bash
python scripts/apply_mongo.py
```

O executor lê cada entrada na ordem configurada e chama o comando MongoDB correspondente. Em entradas transacionais, os comandos e o registro de controle são executados em uma transação. Entradas não transacionais registram o próximo comando para permitir retomada após uma falha.

No GitHub Actions, o workflow de aplicação usa os secrets `MONGODB_URI` e `MONGODB_TLS_CA_FILE`, força `MONGODB_TLS=true` e executa o mesmo script após instalar as dependências. As alterações de estrutura devem ser feitas neste repositório, não no código do AI server.

## Testes e qualidade

Execute as mesmas verificações principais do CI com:

```bash
python -m py_compile scripts/apply_mongo.py
python -m unittest discover -s tests -v
```

O workflow `.github/workflows/ci-cd.yml` também valida a existência de `config.yaml`, do executor e de pelo menos um arquivo JSON em `mongo/`.

## Estrutura do projeto

```text
.
├── .env.example
├── config.yaml
├── requirements.txt
├── mongo/
│   └── colecoes.json
├── scripts/
│   └── apply_mongo.py
└── tests/
    └── test_apply_mongo.py
```

## Contribuição

Ao adicionar ou alterar comandos, mantenha a ordem em `config.yaml`, declare corretamente o modo de execução e respeite a exigência de idempotência para scripts não transacionais. Execute as verificações locais antes de enviar a alteração.

## Licença

Este projeto está sob a licença MIT. Consulte o arquivo [LICENSE](LICENSE).


## Principais contribuidores

<!-- CONTRIBUTORS:START -->
- [@Nicolas25vlad](https://github.com/Nicolas25vlad) — 4 contribuições
<!-- CONTRIBUTORS:END -->

> Atualizado automaticamente semanalmente pelo workflow de metadados do README.
