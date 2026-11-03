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
| 2 | Viagens, convites, amizades | pronta |
| 3 | Câmera com overlay, upload, criptografia em repouso, fotos extras | pronta |
| 4 | Telas: streak, status do dia, amigos, cutucadas, galeria | pronta |
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

# Chave de criptografia das fotos (uma vez só; GUARDE UMA CÓPIA fora do PC/servidor)
.venv/Scripts/python -m app.cli generate-key      # cria backend/rewind.key (ignorado pelo git)

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
- Não existe cadastro aberto: o primeiro admin nasce pela linha de comando; o resto
  entra por convite (link de uso único, 7 dias).

### Fotos

- Toda foto passa pela rota `/api/photos/{id}`, que confere quem está pedindo. A pasta
  das fotos nunca é servida direto.
  - Selfie: você vê a sua e a de quem está numa viagem com você, só nos dias do
    período da viagem. Amigo fora da viagem vê só se você já tirou a foto.
  - Foto extra: só os membros da viagem onde ela foi publicada.
- O servidor recodifica toda imagem: confere que é imagem de verdade (JPEG/PNG/WebP),
  apaga o EXIF (GPS, celular...), limita a 1600 px e a 10 MB.
- Os nomes dos arquivos são aleatórios e não dizem de quem é nem de quando.

### Criptografia em repouso (AES-256-GCM)

Cada foto é gravada criptografada, com um nonce aleatório. O nome do arquivo entra
como dado autenticado, então trocar arquivos de lugar faz a leitura falhar.

- **Protege:** quem levar o HDD, uma cópia dele ou o backup vê só lixo.
- **Não protege:** quem invadir o servidor enquanto ele está ligado. O app precisa da
  chave pra mostrar as fotos, então quem controla o servidor controla a chave.
- **A chave fica fora da pasta de dados e fora do git.** Perder a chave = perder todas
  as fotos. Guarde uma cópia num lugar seguro (gerenciador de senhas, pendrive guardado).

### Espelhamento da câmera

A prévia aparece espelhada, como um espelho, porque é assim que a gente se arruma. A
foto **salva** não é espelhada: é a imagem real da câmera, como os outros te veem. Ela
sai igual todos os dias, e o timelapse não "pula" de lado. A foto de ontem, que aparece
por cima pra alinhar o rosto, também é espelhada só na tela, pra bater com a prévia.
