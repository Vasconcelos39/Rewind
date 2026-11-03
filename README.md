# Rewind

PWA self-hosted para um grupo de amigos tirar **uma selfie por dia** até uma data-meta
(um casamento, uma viagem) e gerar um timelapse no final.

- **Backend:** Python + FastAPI + SQLite (SQL puro, migrações em `backend/app/migrations`)
- **Front:** React + Vite + `vite-plugin-pwa`
- **Deploy:** imagem Docker ARM64 no Orange Pi, atrás do Nginx Proxy Manager (fase 6)

## Estado

| Fase | O quê | Status |
|---|---|---|
| 1 | Esqueleto, banco, login, admin por CLI | pronta |
| 2 | Viagens, convites, amizades | — |
| 3 | Câmera com overlay, upload, criptografia em repouso, fotos extras | — |
| 4 | Telas: streak, status do dia, amigos, galeria | — |
| 5 | Timelapse com ffmpeg + fila | — |
| 6 | Backup, deploy, HTTPS | — |
| 7 | Notificações push | depois |

## Rodando no PC (desenvolvimento)

Requisitos: Python 3.13 e Node 20+.

```bash
# Backend
cd backend
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # Linux/Mac: .venv/bin/python
.venv/Scripts/python -m pytest

# Primeiro admin (pede a senha duas vezes)
REWIND_DATA_DIR=./data .venv/Scripts/python -m app.cli create-admin --username seu_nome

# API em http://127.0.0.1:8000
REWIND_DATA_DIR=./data REWIND_COOKIE_SECURE=false .venv/Scripts/python -m uvicorn app.main:create_app --factory --port 8000
```

```bash
# Front (outro terminal): http://localhost:5173, repassa /api para a porta 8000
cd frontend
npm install
npm run dev
```

Para testar como em produção, rode `npm run build`: o FastAPI passa a servir o
`frontend/dist` sozinho, sem o Vite.

## Segurança (até aqui)

- Senhas com **argon2id**; o banco guarda só o hash.
- Sessão por cookie `httpOnly` + `Secure` + `SameSite=Lax`. O banco guarda só o
  sha256 do token, então uma cópia do banco não abre a conta de ninguém.
- Login limitado a 20 tentativas por IP e 5 erros por usuário a cada 15 minutos.
  Usuário inexistente e senha errada dão a mesma resposta, no mesmo tempo.
- POST/PUT/DELETE vindos de outro site são recusados (checagem do `Origin`).
- Não existe cadastro aberto: o primeiro admin nasce pela linha de comando.
