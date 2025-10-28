# Rocks Monitoramento Backend

Backend FastAPI responsável por autenticar usuários internos, cadastrar máquinas monitoradas, armazenar configurações e receber métricas enviadas pelo agente desktop **rocks-monitoramento-desktop**. A API também fornece endpoints para consulta das métricas pelo frontend e documentação automática (OpenAPI/Swagger).

## Tecnologias

- [FastAPI](https://fastapi.tiangolo.com/) + Uvicorn
- SQLAlchemy (modo assíncrono) utilizando SQLite local
- Autenticação JWT (`python-jose` + `passlib[bcrypt]`)
- Testes assíncronos com `pytest` + `httpx`
- Log centralizado com `loguru`

## Estrutura do Projeto

```
app/
├── api/routes.py        # Rotas principais (auth, máquinas, métricas)
├── core/config.py       # Configurações via variáveis de ambiente
├── database.py          # Conexão com banco assíncrono
├── dependencies.py      # Dependências reutilizáveis (auth, sessão)
├── main.py              # Criação da aplicação FastAPI
├── models.py            # Modelos SQLAlchemy
├── schemas.py           # Schemas Pydantic para validação/respostas
└── security.py          # Funções de hash e geração de tokens
```

## Configuração de Ambiente

1. **Configuração automática (recomendada em Codespaces)** – execute o script:

   ```bash
   ./scripts/setup_codespace.sh
   ```

   Ele cria/atualiza o ambiente virtual, instala as dependências e gera um `.env` com valores de desenvolvimento.

2. **Configuração manual** – copie o arquivo `.env.example` para `.env` e ajuste conforme necessário. Em seguida, instale as dependências:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Banco de dados** – o projeto utiliza SQLite (arquivo `app.db`) por padrão e cria as tabelas automaticamente no primeiro start.
   Se desejar usar outro banco futuramente, ajuste a variável `DATABASE_URL` e configure suas migrações Alembic.

## Execução Local

```bash
uvicorn app.main:app --reload
```

- Documentação interativa: `http://localhost:8000/docs`
- Health check: `GET /api/health`

## Fluxo de Autenticação

1. **Registro interno** – `POST /api/register` recebe `email`, `password` e `full_name`.
2. **Login desktop** – `POST /api/login`

   ```json
   {
     "email": "ops@example.com",
     "password": "s3cret",
     "mac_address": "AA:BB:CC:DD:EE:FF",
     "username": "Desktop-01",
     "c": "windows-pc"
   }
   ```

   Resposta `200 OK`:

   ```json
   {
     "token": "<jwt>",
     "type": "pc"
   }
   ```

   Utilize o token no header `Authorization: Bearer <jwt>` para chamadas subsequentes.

## Endpoints Principais

| Método | Rota                        | Descrição                                                                 |
|--------|-----------------------------|---------------------------------------------------------------------------|
| POST   | `/api/register`             | Cria usuário interno.                                                     |
| POST   | `/api/login`                | Autentica usuário + máquina e retorna JWT.                                |
| POST   | `/api/update_confg_maquina` | Atualiza configuração da máquina (payload em PT/maiúsculas).              |
| GET    | `/api/machine/{mac}`        | Recupera configuração atual da máquina autenticada.                       |
| PUT    | `/api/maquina/status`       | Recebe métricas periódicas do agente desktop.                             |
| GET    | `/api/metrics/{mac}`        | Lista métricas armazenadas (filtros `start`, `end`, `limit`).             |
| GET    | `/api/metrics/{mac}/aggregate` | Estatísticas de métricas (média, mínimo, máximo por chave).            |
| GET    | `/api/machines`             | Lista máquinas vinculadas ao usuário autenticado.                         |
| POST   | `/api/machines`             | Registra/atualiza máquina manualmente.                                    |

### Exemplo de atualização de configuração

```json
{
  "data": {
    "Nome": "Desktop Principal",
    "MAC": "AA:BB:CC:DD:EE:FF",
    "type": "pc",
    "Notificar": true,
    "Frequency": 30,
    "iniciarSO": true,
    "status": {
      "CPU": true,
      "RAM": true,
      "DISCO": true
    }
  }
}
```

### Exemplo de envio de métricas

```json
{
  "data": {
    "timestamp": "2024-05-20T10:33:00Z",
    "machine_info": {
      "mac": "AA:BB:CC:DD:EE:FF",
      "hostname": "Desktop-01"
    },
    "cpu": 52.3,
    "memory": 61.4,
    "disk": {
      "usage": 73.9
    }
  }
}
```

## Rate Limiting e Logs

- Todas as requisições (exceto documentação) passam por um rate limiting simples em memória configurado por `RATE_LIMIT_REQUESTS` e `RATE_LIMIT_WINDOW_SECONDS`.
- Logs de auditoria utilizam Loguru com mensagens para autenticação, configuração e armazenamento de métricas.

## Testes

```bash
pytest
```

Os testes automatizados validam o fluxo completo de autenticação ➜ atualização de configuração ➜ envio de métricas ➜ consulta e agregação.

## Docker (opcional)

O arquivo `docker-compose.yml` sobe apenas o serviço FastAPI utilizando o SQLite local (o arquivo `app.db` é persistido em um
volume nomeado). Nenhum serviço externo de banco é necessário.

```bash
docker compose up --build
```

A aplicação ficará disponível em `http://localhost:8000`.

## Variáveis de Ambiente

| Variável                    | Descrição                                        | Default                          |
|-----------------------------|--------------------------------------------------|----------------------------------|
| `DATABASE_URL`              | URL do banco (ex: `sqlite+aiosqlite:///./app.db`) | SQLite local (`app.db`)          |
| `JWT_SECRET_KEY`            | Chave secreta para assinar tokens                | `change_me`                      |
| `JWT_ALGORITHM`             | Algoritmo JWT                                    | `HS256`                          |
| `JWT_EXPIRATION_MINUTES`    | Expiração do token em minutos                    | `1440` (24h)                     |
| `RATE_LIMIT_REQUESTS`       | Nº máximo de requisições no intervalo            | `120`                            |
| `RATE_LIMIT_WINDOW_SECONDS` | Janela em segundos para o rate limiting          | `60`                             |
| `CORS_ALLOW_ORIGINS`        | Origens liberadas (lista JSON)                   | `[*]`                            |
| `INITIAL_ADMIN_EMAIL`       | Cria usuário admin automático (opcional)         | —                                |
| `INITIAL_ADMIN_PASSWORD`    | Senha do admin inicial                           | —                                |

## Collection / OpenAPI

Ao rodar o servidor, a especificação OpenAPI em `http://localhost:8000/openapi.json` pode ser importada em Postman/Insomnia.

## Monitoramento e Health Check

- `GET /api/health`: verifica disponibilidade da API.
- Header `X-Process-Time`: tempo de processamento da requisição (segundos).

## Licença

Projeto distribuído sob MIT License.
