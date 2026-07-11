# Melhorias na plataforma — Design

Data: 2026-07-10

## Contexto

O app (`~/noeds-replica`, deploy https://noeds-replica.vercel.app) tem hoje três peças que já existem mas estão desconectadas:

- **`dossie.html`** (gerado por `gen_form.py`): formulário público do cliente, 7 seções / ~82 campos, autosave no Supabase (`dossie_respostas`, projeto SETUP `cvzaqqlagwueldpookdf`).
- **`gerar.html`** (gerado por `gen_app.py`): tela onde a equipe cola texto livre com as respostas do cliente → IA (Gemini/OpenAI) extrai 10 campos (`DOSSIE_FIELDS`) → IA gera os 9 documentos do dossiê (`DOC_SPECS`) → salva em `dossie_clientes`.
- **`clientes.html`**: lista clientes de `dossie_respostas` (via RPC `get_respostas`) e de `dossie_clientes` (via RPC `get_clientes`), com "Ver respostas" e "Abrir dossiê".

O problema: entre o formulário (`dossie_respostas`) e a geração (`gerar.html`) não há ponte automática — a equipe precisa copiar e colar manualmente o conteúdo das respostas em texto livre.

Este spec cobre três melhorias, em ordem de prioridade.

## Prioridade 1 — Integração automática das respostas do diagnóstico

**Objetivo:** eliminar a cópia manual entre o formulário do cliente e a geração do dossiê.

**Mudanças:**

1. **`clientes.html`** — na listagem de `dossie_respostas`, cada linha com `progresso > 0` ganha um botão **"Gerar dossiê"** ao lado de "Ver respostas" e "Copiar link". Ao clicar:
   - Grava os 82 campos (objeto `dados` da linha) em `localStorage.dossie_para_gerar` junto com `{id, clinica}`.
   - Navega para `gerar.html?from=<id>`.

2. **`gerar.html`** — detecta `?from=` na URL:
   - Se presente: lê `localStorage.dossie_para_gerar`, **pula a etapa `interpretar()`** (hoje usa IA para extrair 10 campos de um texto livre — desnecessária pois os 82 campos já chegam estruturados) e monta o contexto (`ctx`) direto a partir deles para `gerarDoc()`/`gerarTodos()`.
   - Mostra um resumo/preview dos dados carregados (nome da clínica, seções) antes de disparar a geração.
   - Se ausente (acesso direto à tela, como hoje): mantém o textarea de colar texto livre + `interpretar()` como fallback manual (ex.: respostas recebidas por WhatsApp/e-mail fora do formulário).

3. **Contrato dos 9 documentos (`gerarDoc`)** — o prompt de cada documento passa a receber os 82 campos organizados por seção (em vez dos 10 campos resumidos) como contexto da empresa. `DOSSIE_FIELDS`/`interpretar()` continuam existindo só para o caminho de fallback (texto livre).

4. **Persistência (`salvar()` em `dossie_clientes`)** — a coluna `dados` passa a guardar os 82 campos estruturados quando a origem é o formulário (em vez dos 10 campos). Quando a origem é o fallback de texto livre, continua guardando os 10 campos extraídos (compatibilidade com dossiês antigos/gerados sem formulário).

5. **Tela "Ver dados" do dossiê** (dentro de "Abrir dossiê" / listagem de `dossie_clientes`) — passa a reaproveitar o mesmo layout de `verRespostas()` (seções 01–07, rótulo/valor) já usado em "Ver respostas" do Banco de clientes, em vez do grid chave/valor achatado atual. Um helper de render compartilhado entre as duas telas evita duplicar o HTML das seções.
   - **Critério de detecção do formato:** como a mesma coluna `dados` agora pode conter tanto o formato novo (82 campos em 7 seções aninhadas) quanto o formato antigo (10 campos `DOSSIE_FIELDS`, chaves soltas), o render decide pela forma do objeto — se `dados` contém alguma das chaves de seção conhecidas (`empresa`, `posicionamento`, `publico`, `oferta`, `comercial`, `marketing`, `crescimento`) como objeto aninhado, usa o layout por seções; caso contrário, usa o grid achatado antigo.

**Fora de escopo:** dossiês antigos já salvos em `dossie_clientes` com o formato de 10 campos continuam sendo exibidos no formato antigo (sem migração retroativa).

## Prioridade 2 — Escolha do modelo de IA (Gemini, OpenAI, Claude)

**Objetivo:** deixar os três provedores (Gemini, OpenAI, Claude) disponíveis lado a lado, com a última escolha do usuário lembrada.

**Mudanças em `gen_app.py` (`_gerar_js`, objeto `PROVIDERS`):**

1. Nova entrada `claude` em `PROVIDERS`, mesmo padrão dos existentes: nome, link para obter chave (console.anthropic.com), placeholder, `store: "claude_key"`.
2. Nova aba **Claude** no card de conexão (`.prov-tabs`), ao lado de Gemini e OpenAI — três abas.
3. **Lista de modelos buscada dinamicamente da API**, para os três provedores, no momento em que a chave é conectada (não mais lista fixa no código):
   - OpenAI: `GET https://api.openai.com/v1/models` (Authorization: Bearer).
   - Anthropic: `GET https://api.anthropic.com/v1/models` (header `x-api-key`, `anthropic-version`, `anthropic-dangerous-direct-browser-access: true`).
   - Gemini: `GET https://generativelanguage.googleapis.com/v1beta/models?key=...`.
   - Resultado popula o `<select id="model-sel">`. Filtrar por modelos de geração de texto/chat (excluir embeddings, TTS, moderação, whisper etc. quando o endpoint não distinguir por si só, usar heurística de nome).
   - Se a listagem falhar (rede, chave sem permissão para `/models`), cair para uma lista mínima hardcoded por provedor como fallback silencioso, para não travar o fluxo.
4. **`callClaude(model, prompt, key)`** — nova função, chama `api.anthropic.com/v1/messages` com o header de bypass CORS, `max_tokens` adequado, `messages: [{role:"user", content: prompt}]`.
5. **`extractText(provider, data)`** — novo branch para Anthropic: `data.content[0].text`.
6. **`aiJSON()`** — passa a despachar para `callGemini`/`callOpenAI`/`callClaude` conforme o provedor selecionado, mantendo a mesma lógica de fallback de modelo + retry em 429 + mensagens de erro por status (401/403/429) adaptadas ao formato de erro da Anthropic.
7. `localStorage`: `ai_provider` (gemini|openai|claude) e `ai_model_<provider>` continuam guardando a última escolha, agora com uma terceira chave possível.

**Fora de escopo:** proxy serverless para a chave da Anthropic (decidido manter client-side, mesmo padrão do Gemini/OpenAI — o usuário vai colar as próprias chaves dentro da plataforma).

## Prioridade 3 — Compartilhamento exclusivo por cliente

**Objetivo:** gerar um link somente-leitura por cliente, que mostra apenas o dossiê daquele cliente, sem acesso à sidebar administrativa (Gerar, Banco de clientes, outras páginas).

**Banco de dados (`dossie_clientes`):**

1. Nova coluna `share_token text unique null`.
2. Nova RPC `get_dossie_by_share(token text)` (SECURITY DEFINER, `search_path=''`): valida o token contra `share_token`, devolve `dados` + `documentos` + `clinica` daquele único registro. Token inválido/nulo → erro. `revoke all` + `grant execute to anon`.
3. Nova policy de UPDATE para `anon` em `dossie_clientes` (hoje a tabela só tem policy de INSERT) restrita à coluna `share_token`, para o botão "Compartilhar"/"Revogar" funcionar. Update feito com `Prefer: return=minimal` (mesmo padrão já validado no projeto, evita 42501 por falta de policy de SELECT pós-update).

**`clientes.html`:**

4. Botão **"Compartilhar"** em cada linha de `dossie_clientes` (ao lado de "Ver dossiê"):
   - Sem token ainda: gera token aleatório longo (`crypto.randomUUID()`), faz `PATCH` na linha (`share_token`), copia `https://noeds-replica.vercel.app/index.html?share=<token>` para a área de transferência, mostra confirmação.
   - Já com token: mostra o link atual + botão **"Revogar"** (`PATCH share_token = null`), que invalida o link imediatamente.

**`index.html` (capa do dossiê) e demais páginas do dossiê:**

5. Detecção de `?share=<token>` na URL, antes de checar `localStorage.dossie_atual`:
   - Busca via `get_dossie_by_share(token)`.
   - Sucesso: injeta `dados`/`documentos` no `RENDER_JS` existente (mesmo mecanismo usado hoje para `dossie_atual`), **oculta a sidebar global** (sem itens de Gerar/Banco de clientes/outras ferramentas), e propaga `?share=<token>` em todos os links de navegação entre as 9 páginas do dossiê (para o token seguir disponível página a página, já que não há login).
   - Falha (token inválido/revogado): mostra mensagem de "link inválido ou expirado".
6. Sem upload de arquivos, sem edição — somente leitura nesta primeira versão.

**Fora de escopo:** permissões granulares por link (leitura vs. edição), múltiplos links por cliente, expiração automática por tempo — só revogação manual on/off.

## Notas de implementação transversais

- Todas as chamadas de rede novas (listagem de modelos, RPC de share) seguem o padrão já validado no projeto: `Prefer: return=minimal` em updates para evitar 42501 de RLS pós-insert/update sem SELECT liberado.
- Nenhuma chave de API (OpenAI/Claude/Gemini) é enviada ao Supabase ou a qualquer servidor próprio — permanecem só no `localStorage` do navegador de quem está usando o "Gerar", como já ocorre hoje.
- Build continua via `python3 build.py` (que chama `gen_app.py`, `gen_form.py`) e deploy via `vercel deploy --prod --yes --scope monaiaraujo27-4850s-projects`.
