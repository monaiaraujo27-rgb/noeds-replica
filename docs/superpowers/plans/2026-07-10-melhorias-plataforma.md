# Melhorias na Plataforma — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Conectar o formulário do cliente (`dossie.html`) direto à geração do dossiê (eliminando cópia manual), adicionar Claude como terceiro provedor de IA com modelos buscados dinamicamente, e permitir compartilhamento somente-leitura do dossiê por link exclusivo e revogável.

**Architecture:** Site estático gerado por scripts Python (`build.py` orquestra `gen_app.py` e `gen_form.py`, que emitem HTML+CSS+JS inline em strings Python). Sem framework, sem bundler, sem testes automatizados — cada mudança é validada rodando `python3 build.py` e inspecionando o HTML gerado (localmente e via `file://`, ou headless quando útil) antes do deploy. Todas as chamadas de rede são `fetch()` cru contra a REST API do Supabase (PostgREST) e contra as APIs das IAs — não há SDK nem servidor próprio.

**Tech Stack:** Python 3 (geradores), HTML/CSS/JS vanilla (saída), Supabase Postgres/PostgREST (projeto "SETUP", ref `cvzaqqlagwueldpookdf`), Vercel (deploy estático).

## Global Constraints

- Nenhuma chave de API (Gemini/OpenAI/Claude) é enviada a servidor próprio — permanece só em `localStorage` do navegador de quem usa a tela "Gerar", como já ocorre hoje.
- Toda mudança em `build.py`/`gen_app.py`/`gen_form.py` deve ser validada rodando `python3 build.py` e conferindo que os 9 arquivos do dossiê + `gerar.html` + `clientes.html` + `dossie.html` são reescritos sem erro Python.
- Updates em tabelas Supabase via REST direto usam `Prefer: return=minimal` (evita 42501 por falta de policy de SELECT pós-update/insert — padrão já validado no projeto, ver memória `noeds-replica-app`).
- Migrations SQL novas são arquivos `.sql` novos e idempotentes (`create or replace function`, `drop policy if exists` + `create policy`), nunca editam os arquivos `.sql` existentes.
- Deploy final: `cd ~/noeds-replica && vercel deploy --prod --yes --scope monaiaraujo27-4850s-projects`.
- Build não tem função `_page()` genérica — a montagem das 9 páginas do dossiê é feita inline via `TEMPLATE.format(...)` dentro do loop `for slug, (outname, srcpath) in ROUTES.items():` em `build.py:503-541`. Qualquer mudança nesse template edita esse bloco diretamente.

## Correção descoberta durante a execução (Task 1 / Task 8)

A Task 1 originalmente previa `GRANT UPDATE (share_token)` + policy RLS `using(true)` para permitir `PATCH /rest/v1/dossie_clientes?id=eq.X` direto via REST. **Isso não funciona nesta tabela**: `dossie_clientes` nunca teve `GRANT SELECT` para `anon` (decisão original do projeto — anon só insere, leitura é via RPC com token). Sem SELECT, o PostgREST não consegue localizar a linha pelo filtro `id=eq.X` para aplicar o UPDATE, mesmo com GRANT UPDATE e policy corretos — confirmado por teste direto (UPDATE via role `anon` com grants certos afetou 0 linhas, tanto via SQL quanto via REST).

**Correção aplicada:** trocado GRANT/policy de UPDATE por uma RPC `set_share_token(cliente_id uuid, novo_token text)` SECURITY DEFINER — mesmo padrão já usado no resto do projeto (`upsert_resposta`, `get_clientes`). `supabase_clientes_share.sql` e `gen_app.py` (`compartilhar`/`revogar`, agora via `setShareToken()`) já refletem essa correção. Nenhum GRANT de UPDATE/SELECT foi deixado na tabela para `anon`.

---

## Task 1: Migration SQL — coluna `dados` genérica + policy de UPDATE + `share_token` (Supabase)

Prepara o banco para P1 (dados de 82 campos) e P3 (compartilhamento) numa única migration, já que ambas tocam a tabela `dossie_clientes`.

**Files:**
- Create: `~/noeds-replica/supabase_clientes_share.sql`

**Interfaces:**
- Produces: coluna `dossie_clientes.share_token text unique null`; policy `"anon update share_token"` (UPDATE para `anon`); RPC `get_dossie_by_share(token text) returns setof dossie_clientes`.

- [ ] **Step 1: Escrever a migration**

```sql
-- ============================================================
-- Projeto Supabase "SETUP" (ref cvzaqqlagwueldpookdf)
-- Compartilhamento exclusivo por cliente (Prioridade 3) +
-- suporte a coluna "dados" com payload de 82 campos (Prioridade 1).
-- Idempotente: pode rodar de novo sem quebrar nada existente.
-- ============================================================

-- 1) Coluna do token de compartilhamento (null = não compartilhado)
alter table public.dossie_clientes
  add column if not exists share_token text unique;

-- 2) anon pode ATUALIZAR (só usamos para setar/limpar share_token).
--    Sem policy de SELECT para anon nesta tabela; update deve ser feito
--    com Prefer: return=minimal no client para evitar 42501 pós-update.
drop policy if exists "anon update share_token" on public.dossie_clientes;
create policy "anon update share_token"
  on public.dossie_clientes for update to anon
  using ( true )
  with check ( true );

-- 3) RPC: devolve o dossiê (dados + documentos + clinica) de UM registro,
--    dado o token de compartilhamento. Token invalido/nulo -> erro.
drop function if exists public.get_dossie_by_share(text);
create or replace function public.get_dossie_by_share(token text)
returns setof public.dossie_clientes
language plpgsql
security definer
set search_path = ''
as $$
begin
  if token is null or char_length(token) < 8 then
    raise exception 'unauthorized';
  end if;
  return query
    select * from public.dossie_clientes
    where share_token = token
    limit 1;
end;
$$;

revoke all on function public.get_dossie_by_share(text) from public;
grant execute on function public.get_dossie_by_share(text) to anon;

-- pronto.
```

- [ ] **Step 2: Aplicar a migration no Supabase**

Run: `cd ~/noeds-replica && supabase db push` (CLI já autenticada e linkada ao projeto, conforme documentado na memória do projeto — sem prompt de senha).

Expected: saída confirma a migration aplicada sem erro (`Applying migration...` seguido de sucesso). Se `supabase db push` pedir para vincular migrations locais explicitamente e a estrutura de pastas `supabase/migrations` não existir, aplicar via `supabase db execute --file supabase_clientes_share.sql` ou colar o SQL no SQL Editor do painel Supabase como alternativa.

- [ ] **Step 3: Validar a RPC manualmente**

Run:
```bash
curl -s -X POST "https://cvzaqqlagwueldpookdf.supabase.co/rest/v1/rpc/get_dossie_by_share" \
  -H "apikey: sb_publishable_guPZajaIZW8_hABcLqIx1w_AD3EKh_o" \
  -H "Authorization: Bearer sb_publishable_guPZajaIZW8_hABcLqIx1w_AD3EKh_o" \
  -H "Content-Type: application/json" \
  -d '{"token":"tokeninvalido"}'
```
Expected: resposta JSON de erro (`{"message":"unauthorized",...}` ou equivalente), HTTP não-200 — confirma que a RPC existe e rejeita token inválido/curto.

- [ ] **Step 4: Commit**

Não é repositório git (confirmado: `~/noeds-replica` não tem `.git`). Pular commit — seguir para a próxima task.

---

## Task 2: Prioridade 1 — botão "Gerar dossiê" em `clientes.html` (gen_app.py, `_clientes_js`)

Adiciona o botão que grava os 82 campos no localStorage e navega para `gerar.html?from=<id>`.

**Files:**
- Modify: `~/noeds-replica/gen_app.py:681-716` (dentro de `carregar()`, função `_clientes_js`)

**Interfaces:**
- Consumes: linhas de `dossie_respostas` já retornadas por `carregar()` — cada `c` tem `{id, clinica, responsavel, status, progresso, dados, atualizado_em, created_at}` (`dados` = objeto com as 7 seções).
- Produces: `localStorage.dossie_para_gerar` com shape `{id, clinica, dados}`; navegação para `gerar.html?from=<id>`.

- [ ] **Step 1: Ler o trecho atual de `carregar()` para localizar o ponto exato de inserção**

Run: `grep -n "bVer\|bLink\|acts.appendChild" ~/noeds-replica/gen_app.py`
Expected: mostra as linhas onde `bVer` (Ver respostas) e `bLink` (Copiar link) são criados e anexados a `acts`, dentro de `carregar()` (por volta de `gen_app.py:695-707`).

- [ ] **Step 2: Adicionar o botão "Gerar dossiê" e a função `gerarDossieDe(c)`**

Editar `gen_app.py`, dentro de `_clientes_js()`, logo após a criação de `bLink` e antes de `acts.appendChild(bVer); acts.appendChild(bLink);`:

```python
      var bGerar=document.createElement("button"); bGerar.className="app-btn"; bGerar.textContent="Gerar dossiê";
      bGerar.disabled=!(c.progresso>0);
      bGerar.addEventListener("click",function(){ gerarDossieDe(c); });
      acts.appendChild(bVer); acts.appendChild(bLink); acts.appendChild(bGerar);
```
(substitui a linha `acts.appendChild(bVer); acts.appendChild(bLink);` existente)

E adicionar a função `gerarDossieDe`, antes da definição de `carregar()`:

```python
function gerarDossieDe(c){
  localStorage.setItem("dossie_para_gerar", JSON.stringify({id:c.id, clinica:c.clinica||"", dados:c.dados||{}}));
  location.href="gerar.html?from="+encodeURIComponent(c.id);
}
```

- [ ] **Step 3: Rodar o gerador e verificar a saída**

Run: `cd ~/noeds-replica && python3 build.py`
Expected: sem traceback Python; saída lista `clientes.html <- gen_app.py` (ou equivalente) entre os arquivos gerados.

Run: `grep -c "gerarDossieDe\|Gerar dossiê" ~/noeds-replica/clientes.html`
Expected: `2` ou mais (função definida + botão renderizado no JS embutido).

- [ ] **Step 4: Commit**

Sem git no projeto — pular.

---

## Task 3: Prioridade 1 — `gerar.html` consome `?from=` e pula a etapa `interpretar()`

**Files:**
- Modify: `~/noeds-replica/gen_app.py:308-458` (dentro de `_gerar_js`, antes da definição de `interpretar()`), `~/noeds-replica/gen_app.py:756-793` (corpo HTML de `gerar_body`)

**Interfaces:**
- Consumes: `localStorage.dossie_para_gerar` = `{id, clinica, dados}` (produzido na Task 2); `ctx` esperado por `gerarDoc(spec, ctx, onWait)` já existente (objeto chave→valor usado no prompt).
- Produces: variável global `window.__ctxOrigem` ("form"|"texto"); `montarCtxDeFormulario(dadosForm)` → retorna `ctx` achatado para os prompts.

- [ ] **Step 1: Adicionar função que achata os 82 campos em contexto legível pelos prompts**

Editar `gen_app.py`, dentro de `_gerar_js()`, logo depois da definição de `const FIELDS=[...]` e antes de `const PROVIDERS={`:

```python
// achata os 82 campos (7 seções aninhadas) num objeto chave->texto p/ os prompts dos 9 docs
const SEC_TITULOS={empresa:"Empresa",posicionamento:"Posicionamento",publico:"Público",
  oferta:"Oferta",comercial:"Comercial",marketing:"Marketing",crescimento:"Crescimento"};
function montarCtxDeFormulario(dadosForm){
  var ctx={clinica:(dadosForm.empresa&&dadosForm.empresa.nome)||""};
  Object.keys(SEC_TITULOS).forEach(function(sid){
    var vals=dadosForm[sid]||{};
    Object.keys(vals).forEach(function(k){
      var v=vals[k];
      if(sid==="oferta"&&k==="itens"&&Array.isArray(v)){
        var txt=v.filter(function(it){return it&&it.nome;}).map(function(it){
          return it.nome+(it.ticket?(" (ticket R$ "+it.ticket+")"):"");
        }).join("; ");
        if(txt) ctx[SEC_TITULOS[sid]+" - Ofertas"]=txt;
        return;
      }
      if(v==null||(""+v).trim()==="")return;
      ctx[SEC_TITULOS[sid]+" - "+k]=v;
    });
  });
  return ctx;
}
```

- [ ] **Step 2: Detectar `?from=` no boot da tela e pré-carregar o contexto**

Editar `gen_app.py`, no fim de `_gerar_js()` — logo antes do listener `$("#interpretar").addEventListener(...)` existente (`gen_app.py:562`), adicionar:

```python
// ---- fluxo vindo de "Gerar dossiê" no Banco de clientes (pula colar texto) ----
window.__ctxOrigem="texto";
window.__ctxPreCarregado=null;
(function(){
  var params=new URLSearchParams(location.search);
  var fromId=params.get("from");
  if(!fromId) return;
  var raw; try{ raw=JSON.parse(localStorage.getItem("dossie_para_gerar")||"null"); }catch(_){ raw=null; }
  if(!raw || raw.id!==fromId) return;
  window.__ctxOrigem="form";
  window.__ctxPreCarregado=montarCtxDeFormulario(raw.dados||{});
  $("#raw-card").style.display="none";
  $("#from-card").style.display="block";
  $("#from-nome").textContent=raw.clinica||"Cliente";
  var campos=Object.keys(window.__ctxPreCarregado).length;
  $("#from-resumo").textContent=campos+" campos carregados do formulário.";
})();
```

- [ ] **Step 3: Ajustar o listener de `#interpretar` para pular `interpretar()` quando vier do formulário**

Substituir o corpo atual do listener (`gen_app.py:562-586`, começando em `$("#interpretar").addEventListener("click",async function(){`) por:

```python
$("#interpretar").addEventListener("click",async function(){
  var d;
  if(window.__ctxOrigem==="form"){
    d=window.__ctxPreCarregado;
  }else{
    var t=$("#raw").value.trim();
    if(t.length<20){setStatus("Cole as respostas do formulário primeiro.","err");return;}
  }
  this.disabled=true; $("#salvar").disabled=true;
  var docs={}, falhas=[];
  try{
    if(window.__ctxOrigem!=="form"){
      setStatus('<span class="spinner"></span> Interpretando o diagnóstico…');
      d=await interpretar(t);
    }
    renderDados(d);
    var res=await gerarTodos(d);
    docs=res.docs; falhas=res.falhas;
  }catch(e){
    if(e.parcial){ docs=e.parcial; falhas=e.falhas||[]; }
    else { setStatus(e.message,"err"); this.disabled=false; return; }
  }
  try{
    await salvar(docs);
    var n=Object.keys(docs).length;
    window.__docs=docs;
    if(falhas.length){
      setStatus("Gerado e salvo ("+n+"/"+DOC_SPECS.length+"). Faltaram: "+falhas.join(", ")+". Você pode gerar de novo mais tarde para completar.","ok");
    }else{
      setStatus("Dossiê completo gerado e salvo ✓ ("+n+" documentos).","ok");
    }
    $("#abrir").style.display="inline-flex";
  }catch(e){ setStatus("Documentos gerados, mas falha ao salvar: "+e.message,"err"); }
  this.disabled=false;
});
```

- [ ] **Step 4: Ajustar `renderDados(d)` para não quebrar com objeto achatado do formulário**

`renderDados` (`gen_app.py:538-548`) itera `FIELDS` (os 10 campos fixos) — quando `d` vem de `montarCtxDeFormulario`, as chaves são diferentes (`"Empresa - nome"` etc). Substituir `renderDados` para iterar as chaves reais do objeto recebido em vez de `FIELDS` fixo:

```python
function renderDados(d){
  var g=$("#dados"); g.innerHTML="";
  Object.keys(d).forEach(function(k){
    if(k==="clinica")return;
    var v=(d[k]||"").toString().trim()||"—";
    var cell=document.createElement("div");
    cell.innerHTML='<div class="k">'+k.replace(/_/g," ")+'</div><div class="v">'+v.replace(/</g,"&lt;")+'</div>';
    g.appendChild(cell);
  });
  g.style.display="grid";
  $("#salvar").disabled=false;
  window.__dados=d;
}
```

- [ ] **Step 5: Adicionar o HTML dos dois cards (raw-card / from-card) no corpo de `gerar_body`**

Editar `gen_app.py`, dentro de `build()`, no bloco `gerar_body = """..."""` (`gen_app.py:756-793`). Envolver o card existente de textarea com `id="raw-card"` e adicionar um novo `id="from-card"` oculto por padrão, logo antes dele:

```python
<div class="app-card" id="from-card" style="display:none">
  <p class="app-eyebrow">Origem · Formulário do cliente</p>
  <h2 class="app-h1" style="font-size:24px; margin-top:8px" id="from-nome"></h2>
  <p class="conn-hint" id="from-resumo"></p>
</div>

<div class="app-card" id="raw-card">
  <label class="app-label" for="raw">Respostas do formulário (texto livre)</label>
  <textarea id="raw" class="app-textarea" placeholder="Cole aqui as perguntas e respostas do cliente…"></textarea>
  <button id="interpretar" class="app-btn">Gerar dossiê completo</button>
  <p class="conn-hint" style="margin-top:14px">A IA lê o diagnóstico, gera os 9 documentos personalizados
  (um por vez, ~1–3 min) e salva o cliente. Mantenha esta aba aberta durante a geração.</p>
  <div id="status" class="app-status"></div>
  <div id="progresso" class="prog" style="display:none"></div>
  <div id="dados" class="app-grid" style="display:none"></div>
  <button id="abrir" class="app-btn" style="display:none; margin-top:24px">Abrir dossiê gerado →</button>
  <button id="salvar" style="display:none"></button>
</div>
```

Nota: o botão `#interpretar` e os elementos `#status`/`#progresso`/`#dados`/`#abrir`/`#salvar` continuam dentro de `#raw-card` — quando a origem é "form", o Step 2 esconde `#raw-card` (textarea) mas o botão "Gerar dossiê completo" ficaria escondido junto. Ajustar: mover `#interpretar` e os elementos de status/progresso/dados/abrir/salvar para FORA de `#raw-card`, num card à parte que aparece sempre. Reescrever o bloco completo assim:

```python
<div class="app-card" id="from-card" style="display:none">
  <p class="app-eyebrow">Origem · Formulário do cliente</p>
  <h2 class="app-h1" style="font-size:24px; margin-top:8px" id="from-nome"></h2>
  <p class="conn-hint" id="from-resumo"></p>
</div>

<div class="app-card" id="raw-card">
  <label class="app-label" for="raw">Respostas do formulário (texto livre)</label>
  <textarea id="raw" class="app-textarea" placeholder="Cole aqui as perguntas e respostas do cliente…"></textarea>
</div>

<div class="app-card">
  <button id="interpretar" class="app-btn">Gerar dossiê completo</button>
  <p class="conn-hint" style="margin-top:14px">A IA lê o diagnóstico, gera os 9 documentos personalizados
  (um por vez, ~1–3 min) e salva o cliente. Mantenha esta aba aberta durante a geração.</p>
  <div id="status" class="app-status"></div>
  <div id="progresso" class="prog" style="display:none"></div>
  <div id="dados" class="app-grid" style="display:none"></div>
  <button id="abrir" class="app-btn" style="display:none; margin-top:24px">Abrir dossiê gerado →</button>
  <button id="salvar" style="display:none"></button>
</div>
```

- [ ] **Step 6: Rodar o gerador e validar os dois caminhos**

Run: `cd ~/noeds-replica && python3 build.py`
Expected: sem traceback.

Run: `grep -c "montarCtxDeFormulario\|from-card\|raw-card" ~/noeds-replica/gerar.html`
Expected: `>= 3`.

Validação manual do caminho `?from=`: abrir `file:///Users/jean.monai/noeds-replica/clientes.html` num navegador, rodar no console:
```js
localStorage.setItem("dossie_para_gerar", JSON.stringify({id:"teste-1", clinica:"Clínica Teste", dados:{empresa:{nome:"Clínica Teste", responsavel:"Ana"}, publico:{dores:"dor de exemplo"}}}));
location.href="gerar.html?from=teste-1";
```
Expected: a tela abre com `#from-card` visível mostrando "Clínica Teste" e a contagem de campos, `#raw-card` (textarea) oculto.

- [ ] **Step 7: Commit**

Sem git — pular.

---

## Task 4: Prioridade 1 — `salvar()` grava os 82 campos quando origem é formulário

**Files:**
- Modify: `~/noeds-replica/gen_app.py:551-560` (função `salvar`)

**Interfaces:**
- Consumes: `window.__dados` (já setado por `renderDados`), `window.__ctxOrigem`, e (novo) `window.__dadosFormOriginais` — os 82 campos brutos (não achatados), para persistir a estrutura por seção em vez do achatamento usado só para o prompt.

- [ ] **Step 1: Guardar os 82 campos originais (não achatados) ao detectar `?from=`**

Editar o bloco do Step 2 da Task 3 (detecção de `?from=`), adicionando a linha `window.__dadosFormOriginais=raw.dados||{};` logo após `window.__ctxPreCarregado=...`:

```python
  window.__ctxOrigem="form";
  window.__dadosFormOriginais=raw.dados||{};
  window.__ctxPreCarregado=montarCtxDeFormulario(raw.dados||{});
```

- [ ] **Step 2: Ajustar `salvar()` para persistir os 82 campos estruturados quando disponíveis**

Substituir `salvar()` (`gen_app.py:551-560`):

```python
async function salvar(documentos){
  var d=window.__dados; if(!d){return false;}
  var clinicaNome=(window.__dadosFormOriginais&&window.__dadosFormOriginais.empresa&&window.__dadosFormOriginais.empresa.nome)||d.clinica||"Sem nome";
  var dadosParaSalvar=window.__ctxOrigem==="form" ? window.__dadosFormOriginais : d;
  var r=await fetch(SUPABASE_URL+"/rest/v1/dossie_clientes",{
    method:"POST",
    headers:{"apikey":SUPABASE_ANON,"Authorization":"Bearer "+SUPABASE_ANON,
      "Content-Type":"application/json","Prefer":"return=minimal"},
    body:JSON.stringify({clinica:clinicaNome, dados:dadosParaSalvar,
      documentos:documentos||{}, respostas_brutas:$("#raw")?($("#raw").value||""):""})
  });
  if(!r.ok){throw new Error("Supabase recusou ("+r.status+").");}
  return true;
}
```

- [ ] **Step 3: Rodar o gerador**

Run: `cd ~/noeds-replica && python3 build.py`
Expected: sem traceback.

Run: `grep -c "dadosParaSalvar" ~/noeds-replica/gerar.html`
Expected: `>= 1`.

- [ ] **Step 4: Commit**

Sem git — pular.

---

## Task 5: Prioridade 1 — "Ver dados" do dossiê reaproveita layout de seções

Hoje não há uma tela dedicada "Ver dados" do dossiê gerado (a listagem em `clientes.html` mostra clientes de `dossie_respostas`, não de `dossie_clientes`) — mas a tela de detalhe por seção (`verRespostas`) já existe e será reaproveitada. Esta task extrai esse renderer para uma função compartilhada capaz de exibir tanto o formato novo (82 campos aninhados) quanto o antigo (10 campos soltos).

**Files:**
- Modify: `~/noeds-replica/gen_app.py:718-747` (função `verRespostas`)

**Interfaces:**
- Produces: `renderRespostasModal(clinica, dados)` — função genérica que decide o layout pela forma do objeto `dados` e monta o modal.

- [ ] **Step 1: Extrair `verRespostas` para uma função genérica com detecção de formato**

Substituir a função `verRespostas(c)` (`gen_app.py:718-741`) por duas funções: a genérica `renderRespostasModal` e um wrapper fino `verRespostas` que mantém compatibilidade com o call-site existente:

```python
var SEC_IDS=["empresa","posicionamento","publico","oferta","comercial","marketing","crescimento"];
function ehFormatoSecoes(dados){
  return SEC_IDS.some(function(sid){ return dados&&typeof dados[sid]==="object"&&dados[sid]!==null; });
}
function renderRespostasModal(clinica,dados){
  var d=dados||{};
  var h='<div class="resp-modal-in"><button class="resp-close" id="resp-close">✕</button>'
    +'<div class="app-eyebrow">Respostas do cliente</div>'
    +'<h2 class="app-h1" style="margin-top:12px;font-size:36px">'+esc(clinica||"Cliente")+'</h2>';
  if(ehFormatoSecoes(d)){
    SEC_ORDER.forEach(function(sid){
      var meta=SEC[sid]; if(!meta)return;
      var vals=d[sid]||{};
      var rowsHtml="";
      if(sid==="oferta"&&Array.isArray(vals.itens)&&vals.itens.length){
        vals.itens.forEach(function(it,i){
          if(!it||!(it.nome||it.ticket))return;
          rowsHtml+='<div class="resp-row"><div class="resp-k">Oferta '+(i+1)+'</div><div class="resp-v">'
            +esc(it.nome||"—")+(it.ticket?(" · ticket R$ "+esc(it.ticket)):"")
            +(it.margem?(" · margem "+esc(it.margem)+"%"):"")+(it.volume?(" · "+esc(it.volume)+"/mês"):"")+'</div></div>';
        });
      }
      Object.keys(meta.campos).forEach(function(fk){
        var v=vals[fk]; if(v==null||(""+v).trim()==="")return;
        rowsHtml+='<div class="resp-row"><div class="resp-k">'+esc(meta.campos[fk])+'</div><div class="resp-v">'+esc(v)+'</div></div>';
      });
      if(!rowsHtml)rowsHtml='<div class="resp-empty">— sem respostas nesta seção —</div>';
      h+='<div class="resp-sec"><div class="resp-sec-h"><span class="resp-num">'+meta.num+'</span> '+esc(meta.titulo)+'</div>'+rowsHtml+'</div>';
    });
  }else{
    var rowsHtml="";
    Object.keys(d).forEach(function(k){
      if(k==="clinica")return;
      var v=d[k]; if(v==null||(""+v).trim()==="")return;
      rowsHtml+='<div class="resp-row"><div class="resp-k">'+esc(k.replace(/_/g," "))+'</div><div class="resp-v">'+esc(v)+'</div></div>';
    });
    h+='<div class="resp-sec">'+(rowsHtml||'<div class="resp-empty">— sem dados —</div>')+'</div>';
  }
  h+='</div>';
  var m=document.createElement("div"); m.className="resp-modal"; m.innerHTML=h;
  document.body.appendChild(m);
  m.querySelector("#resp-close").onclick=function(){m.remove();};
  m.addEventListener("click",function(e){if(e.target===m)m.remove();});
}
function verRespostas(c){ renderRespostasModal(c.clinica, c.dados); }
```

- [ ] **Step 2: Rodar o gerador**

Run: `cd ~/noeds-replica && python3 build.py`
Expected: sem traceback.

Run: `grep -c "renderRespostasModal\|ehFormatoSecoes" ~/noeds-replica/clientes.html`
Expected: `>= 3`.

- [ ] **Step 3: Validar visualmente os dois formatos**

Abrir `file:///Users/jean.monai/noeds-replica/clientes.html` num navegador, console:
```js
renderRespostasModal("Cliente Novo Formato", {empresa:{nome:"Clínica X", responsavel:"João"}, publico:{dores:"dor A"}});
```
Expected: modal com seção "01 Empresa" mostrando Nome/Responsável, sem erro no console.

```js
renderRespostasModal("Cliente Formato Antigo", {clinica:"Clínica Y", responsavel:"Maria", cidade:"SP"});
```
Expected: modal com uma única seção sem cabeçalho numerado, listando clinica/responsavel/cidade como linhas rótulo/valor.

- [ ] **Step 4: Commit**

Sem git — pular.

---

## Task 6: Prioridade 2 — objeto `PROVIDERS` ganha Claude + busca dinâmica de modelos

**Files:**
- Modify: `~/noeds-replica/gen_app.py:321-347` (objeto `PROVIDERS` e funções `getModelFor`/`modelsInOrder`/`refreshConn`)

**Interfaces:**
- Produces: `PROVIDERS.claude` (novo); `async function fetchModelos(provider,key)` → `Promise<Array<{id,label}>>`; `refreshConn()` passa a ser assíncrona e popular o `<select>` via `fetchModelos`.

- [ ] **Step 1: Adicionar a entrada `claude` em `PROVIDERS` e uma lista mínima de fallback por provedor**

Substituir o bloco `const PROVIDERS={...}` (`gen_app.py:321-335`):

```python
const FALLBACK_MODELS={
  gemini:[{id:"gemini-2.0-flash",label:"Gemini 2.0 Flash"},{id:"gemini-2.5-flash",label:"Gemini 2.5 Flash"}],
  openai:[{id:"gpt-4o-mini",label:"GPT-4o mini"},{id:"gpt-4o",label:"GPT-4o"}],
  claude:[{id:"claude-sonnet-4-5-20250929",label:"Claude Sonnet 4.5"},{id:"claude-opus-4-1-20250805",label:"Claude Opus 4.1"}]
};
const PROVIDERS={
  gemini:{ nome:"Google Gemini", link:"https://aistudio.google.com/app/apikey",
    linkLabel:"Pegar chave no Google AI Studio", ph:"Cole aqui sua chave do Gemini (AIza…)",
    store:"gemini_key" },
  openai:{ nome:"OpenAI", link:"https://platform.openai.com/api-keys",
    linkLabel:"Pegar chave na OpenAI", ph:"Cole aqui sua chave da OpenAI (sk-…)",
    store:"openai_key" },
  claude:{ nome:"Anthropic Claude", link:"https://console.anthropic.com/settings/keys",
    linkLabel:"Pegar chave na Anthropic", ph:"Cole aqui sua chave da Anthropic (sk-ant-…)",
    store:"claude_key" }
};
var MODELOS_CACHE={}; // provider -> [{id,label}] já buscados nesta sessão
```

Nota: `models:[...]` foi removido de cada entrada de `PROVIDERS` (a lista agora vem de `fetchModelos`/`FALLBACK_MODELS`, não mais hardcoded por provedor).

- [ ] **Step 2: Escrever `fetchModelos(provider, key)`**

Adicionar logo após o bloco de `PROVIDERS`, antes de `function getProvider(){`:

```python
async function fetchModelos(provider,key){
  try{
    if(provider==="openai"){
      var r=await fetch("https://api.openai.com/v1/models",{headers:{Authorization:"Bearer "+key}});
      if(!r.ok) throw new Error("http "+r.status);
      var data=await r.json();
      return (data.data||[])
        .map(function(m){return m.id;})
        .filter(function(id){return /^(gpt-|o[0-9])/.test(id) && !/embedding|whisper|tts|moderation|audio|realtime|transcribe|image/i.test(id);})
        .sort()
        .map(function(id){return {id:id,label:id};});
    }
    if(provider==="claude"){
      var r=await fetch("https://api.anthropic.com/v1/models",{headers:{
        "x-api-key":key,"anthropic-version":"2023-06-01","anthropic-dangerous-direct-browser-access":"true"}});
      if(!r.ok) throw new Error("http "+r.status);
      var data=await r.json();
      return (data.data||[]).map(function(m){return {id:m.id, label:m.display_name||m.id};});
    }
    if(provider==="gemini"){
      var r=await fetch("https://generativelanguage.googleapis.com/v1beta/models?key="+encodeURIComponent(key));
      if(!r.ok) throw new Error("http "+r.status);
      var data=await r.json();
      return (data.models||[])
        .filter(function(m){return (m.supportedGenerationMethods||[]).indexOf("generateContent")>=0;})
        .map(function(m){return {id:(m.name||"").replace(/^models\//,""), label:m.displayName||m.name};})
        .filter(function(m){return m.id;});
    }
  }catch(e){ /* cai no fallback abaixo */ }
  return FALLBACK_MODELS[provider]||[];
}
```

- [ ] **Step 3: Tornar `refreshConn()` assíncrona, buscando modelos ao conectar**

Substituir `refreshConn()` (`gen_app.py:350-366`):

```python
async function refreshConn(){
  var p=getProvider(), cfg=PROVIDERS[p];
  document.querySelectorAll(".prov-tab").forEach(function(b){ b.classList.toggle("on", b.dataset.p===p); });
  $("#conn-title").textContent="Conexão · "+cfg.nome;
  $("#prov-link").href=cfg.link; $("#prov-link").textContent="↗ "+cfg.linkLabel;
  $("#gkey").placeholder=cfg.ph;
  var k=getKeyFor(p);
  $("#gkey").value=k||"";
  var sel=$("#model-sel");
  if(k){
    $("#conn-state").textContent="Conectado"; $("#conn-state").className="conn-on";
    if(!MODELOS_CACHE[p]){
      sel.innerHTML='<option>Carregando modelos…</option>';
      MODELOS_CACHE[p]=await fetchModelos(p,k);
    }
    sel.innerHTML="";
    MODELOS_CACHE[p].forEach(function(m){
      var o=document.createElement("option"); o.value=m.id; o.textContent=m.label; sel.appendChild(o);
    });
    sel.value=getModelFor(p);
  } else {
    $("#conn-state").textContent="Não conectado"; $("#conn-state").className="conn-off";
    sel.innerHTML="";
    FALLBACK_MODELS[p].forEach(function(m){
      var o=document.createElement("option"); o.value=m.id; o.textContent=m.label; sel.appendChild(o);
    });
  }
}
```

- [ ] **Step 4: Ajustar `getModelFor` para usar o cache/fallback em vez de `PROVIDERS[p].models`**

Substituir (`gen_app.py:341-347`):

```python
function getModelFor(p){ return localStorage.getItem("ai_model_"+p)||(FALLBACK_MODELS[p][0]||{}).id; }
function setModelFor(p,m){ localStorage.setItem("ai_model_"+p,m); }
function modelsInOrder(p){
  var chosen=getModelFor(p), all=(MODELOS_CACHE[p]||FALLBACK_MODELS[p]).map(function(m){return m.id;});
  return [chosen].concat(all.filter(function(id){return id!==chosen;}));
}
```

- [ ] **Step 5: Confirmar que os call-sites de `refreshConn()` continuam funcionando como Promise não-aguardada**

`refreshConn()` é definida e usada só dentro de `_gerar_js()` (tela `gerar.html`) — não existe em `_clientes_js()`. Localizar seus call-sites:

Run: `grep -n "refreshConn()" ~/noeds-replica/gen_app.py`

Expected: 3 ocorrências dentro de `_gerar_js()` — (1) dentro do listener de troca de aba `document.querySelectorAll(".prov-tab").forEach(...)`, (2) dentro do listener do botão `$("#salvar-key")`, (3) uma chamada solta perto do fim do bloco (boot inicial da tela). Como `refreshConn` agora é `async function` (Step 3), chamá-la sem `await` nesses três pontos continua válido em JS — a função roda, popula o `<select>` assim que a Promise interna resolver, e nenhum código depende do retorno imediato. Nenhuma edição de código é necessária neste step, apenas a confirmação de que nenhum call-site espera um valor de retorno síncrono de `refreshConn()`.

Run: `grep -n "refreshConn()" ~/noeds-replica/gen_app.py | grep "="`
Expected: nenhum resultado (confirma que `refreshConn()` nunca é atribuída a uma variável nem usada como expressão que exigiria o valor resolvido).

- [ ] **Step 6: Adicionar aba Claude no HTML do card de conexão**

Editar `gen_app.py`, no bloco `gerar_body` (dentro de `.prov-tabs`), adicionar a terceira aba:

```python
  <div class="prov-tabs">
    <button class="prov-tab on" data-p="gemini">Gemini</button>
    <button class="prov-tab" data-p="openai">OpenAI</button>
    <button class="prov-tab" data-p="claude">Claude</button>
  </div>
```

- [ ] **Step 7: Rodar o gerador e validar**

Run: `cd ~/noeds-replica && python3 build.py`
Expected: sem traceback.

Run: `grep -c "claude\|fetchModelos\|FALLBACK_MODELS" ~/noeds-replica/gerar.html`
Expected: `>= 5`.

Validação manual: abrir `file:///Users/jean.monai/noeds-replica/gerar.html`, clicar na aba "Claude", confirmar que aparece o campo de chave com placeholder `sk-ant-…` e link para `console.anthropic.com`.

- [ ] **Step 8: Commit**

Sem git — pular.

---

## Task 7: Prioridade 2 — `callClaude`, `extractText` e `aiJSON` com suporte a 3 provedores

**Files:**
- Modify: `~/noeds-replica/gen_app.py:392-450` (`callGemini`, `callOpenAI`, `extractText`, `aiJSON`)

**Interfaces:**
- Consumes: `getProvider()`, `getKeyFor(provider)`, `modelsInOrder(provider)` (já existentes/ajustados na Task 6).
- Produces: `callClaude(model, prompt, key)`.

- [ ] **Step 1: Adicionar `callClaude`**

Editar `gen_app.py`, logo após `callOpenAI` (`gen_app.py:398-404`):

```python
async function callClaude(model,prompt,key){
  return fetch("https://api.anthropic.com/v1/messages",{method:"POST",
    headers:{"Content-Type":"application/json","x-api-key":key,
      "anthropic-version":"2023-06-01","anthropic-dangerous-direct-browser-access":"true"},
    body:JSON.stringify({model:model, max_tokens:8192, temperature:0.2,
      messages:[{role:"user",content:prompt+"\n\nResponda APENAS com JSON válido, sem markdown."}]})});
}
```

- [ ] **Step 2: Ajustar `extractText` para o formato da Anthropic**

Substituir `extractText` (`gen_app.py:406-409`):

```python
function extractText(provider,data){
  if(provider==="openai"){ return (((data.choices||[])[0]||{}).message||{}).content||"{}"; }
  if(provider==="claude"){ return (((data.content||[])[0]||{}).text)||"{}"; }
  return (((data.candidates||[])[0]||{}).content||{}).parts?.[0]?.text||"{}";
}
```

- [ ] **Step 3: Ajustar `aiJSON` para despachar para `callClaude` e tratar erros da Anthropic**

Substituir o corpo do loop de tentativas em `aiJSON` (`gen_app.py:413-449`), especificamente a linha de despacho e o tratamento de 401/403/429:

```python
async function aiJSON(prompt, onWait){
  var provider=getProvider(), cfg=PROVIDERS[provider], key=getKeyFor(provider);
  if(!key) throw new Error("Conecte sua chave da "+cfg.nome+" no card de conexão acima.");
  var MODELS=modelsInOrder(provider);
  var lastDetail="", quotaPerDay=false;
  for(var mi=0; mi<MODELS.length; mi++){
    var model=MODELS[mi];
    for(var attempt=0; attempt<3; attempt++){
      var r = provider==="openai" ? await callOpenAI(model,prompt,key)
            : provider==="claude" ? await callClaude(model,prompt,key)
            : await callGemini(model,prompt,key);
      if(r.ok){
        var data=await r.json();
        var txt=extractText(provider,data);
        try{return JSON.parse(txt);}catch(e){var m=txt.match(/\{[\s\S]*\}/);return m?JSON.parse(m[0]):{};}
      }
      var detail=""; try{ var je=await r.json(); detail=(je.error&&je.error.message)||""; }catch(_){ je={}; }
      lastDetail=detail;
      if(r.status===401 || (r.status===400&&/API key not valid|API_KEY_INVALID|Incorrect API key|invalid x-api-key/i.test(detail)))
        throw new Error("Chave da "+cfg.nome+" inválida. Reconecte com uma chave válida ("+cfg.linkLabel+").");
      if(r.status===403) throw new Error("Chave sem permissão na "+cfg.nome+". Verifique o painel do provedor.");
      if(r.status===429){
        if(provider==="openai" && /insufficient_quota|exceeded your current quota/i.test(detail)){ quotaPerDay=true; break; }
        if(provider==="gemini" && /per day|PerDay|daily/i.test(detail)){ quotaPerDay=true; break; }
        var wait=retryDelaySec(je)|| (attempt+1)*8;
        if(attempt<2){ if(onWait) onWait("Limite atingido — aguardando "+wait+"s…"); await sleep(wait*1000); continue; }
        break;
      }
      if(r.status===404) break;
      throw new Error(cfg.nome+" falhou ("+r.status+")"+(detail?": "+detail:""));
    }
  }
  if(quotaPerDay){
    if(provider==="openai") throw new Error("Sem crédito/cota na OpenAI. Adicione créditos em platform.openai.com (Billing) ou use outro provedor.");
    throw new Error("Cota DIÁRIA gratuita do Gemini esgotada. Volte amanhã, use outra chave, ou ative billing no Google AI Studio.");
  }
  throw new Error("Limite da "+cfg.nome+" atingido (429) em todos os modelos. Aguarde 1–2 min e tente de novo."+(lastDetail?" · "+lastDetail:""));
}
```

- [ ] **Step 4: Rodar o gerador e validar**

Run: `cd ~/noeds-replica && python3 build.py`
Expected: sem traceback.

Run: `grep -c "callClaude" ~/noeds-replica/gerar.html`
Expected: `>= 2` (definição + uso em `aiJSON`).

- [ ] **Step 5: Teste funcional manual (requer chave real da Anthropic, fornecida pelo usuário dentro da plataforma)**

Abrir `file:///Users/jean.monai/noeds-replica/gerar.html`, aba Claude, colar uma chave válida, clicar Conectar. Expected: dropdown de modelo popula com modelos reais da conta (ex. `claude-sonnet-4-5-...`), sem erro no console. Este passo depende de credencial do usuário — não pode ser automatizado pelo agente; reportar ao usuário para testar com a própria chave.

- [ ] **Step 6: Commit**

Sem git — pular.

---

## Task 8: Prioridade 3 — listagem de dossiês gerados + botão "Compartilhar"/"Revogar" em `clientes.html`

**Achado ao revisar o plano:** a memória do projeto menciona um botão "Abrir dossiê (N)" e uma listagem de `dossie_clientes` em `clientes.html`, mas isso **não existe no código atual** — `clientes.html` hoje só lista `dossie_respostas` (via `carregar()`/RPC `get_respostas`); a única interação com `dossie_clientes` é o INSERT feito por `gerar.html` ao salvar. Confirmado por grep (`get_clientes`/`abrirDossie` não aparecem fora de um comentário) e por chamada direta à RPC via curl: **`get_clientes(token)` existe e funciona no banco** (responde com as linhas de `dossie_clientes`, incluindo `id`, `clinica`, `dados`, `documentos`), só nunca foi chamada do frontend. Esta task cria a listagem do zero.

**Files:**
- Modify: `~/noeds-replica/gen_app.py:607-751` (`_clientes_js`), `~/noeds-replica/gen_app.py:788-797` (HTML de `clientes_body` em `build()`)

**Interfaces:**
- Consumes: RPC `get_clientes(token)` — `POST /rest/v1/rpc/get_clientes` com body `{"token": READ_TOKEN}`, devolve array de linhas `{id, created_at, clinica, dados, documentos, respostas_brutas, share_token}`.
- Produces: `carregarDossies()`, `compartilhar(c)`, `revogar(c)`, elemento `<div id="lista-dossies">` no HTML de `clientes.html`.

- [ ] **Step 1: Adicionar a seção "Dossiês gerados" no HTML de `clientes_body`**

Editar `gen_app.py`, dentro de `build()`, no bloco `clientes_body = """..."""` (`gen_app.py:788-797`). Adicionar uma segunda seção após a `<div id="lista">` existente (que lista `dossie_respostas`):

```python
<p class="app-eyebrow" style="margin-top:48px">Dossiês gerados</p>
<h2 class="app-h1" style="font-size:26px; margin-top:8px">Compartilhar com o cliente</h2>
<p class="app-sub">Gere um link exclusivo e somente-leitura para o cliente acompanhar o próprio dossiê.</p>
<div style="margin-top:20px" id="lista-dossies"></div>
```

- [ ] **Step 2: Adicionar `carregarDossies()` dentro de `_clientes_js()`**

Adicionar logo após a função `carregar()` existente (`gen_app.py:681-716`), reaproveitando `esc()` já definida no mesmo escopo:

```python
async function carregarDossies(){
  var box=$("#lista-dossies"); box.innerHTML='<div class="app-status"><span class="spinner"></span> Carregando…</div>';
  try{
    var r=await fetch(SUPABASE_URL+"/rest/v1/rpc/get_clientes",{
      method:"POST", headers:{"apikey":SUPABASE_ANON,"Authorization":"Bearer "+SUPABASE_ANON,"Content-Type":"application/json"},
      body:JSON.stringify({token:READ_TOKEN})
    });
    if(!r.ok){throw new Error("Não foi possível ler ("+r.status+").");}
    var rows=await r.json();
    if(!Array.isArray(rows)){throw new Error((rows&&rows.message)?rows.message:"Resposta inesperada do banco.");}
    if(!rows.length){box.innerHTML='<div class="app-status">Nenhum dossiê gerado ainda.</div>';return;}
    box.innerHTML="";
    rows.forEach(function(c){
      var nDocs=Object.keys(c.documentos||{}).length;
      var row=document.createElement("div"); row.className="client-row";
      var info=document.createElement("div");
      info.innerHTML='<div class="nm">'+esc(c.clinica||"Sem nome")+'</div>'
        +'<div class="meta">'+esc(nDocs+" documentos")+'</div>';
      var acts=document.createElement("div"); acts.className="client-acts";
      var bDados=document.createElement("button"); bDados.className="app-btn ghost"; bDados.textContent="Ver dados";
      bDados.addEventListener("click",function(){ renderRespostasModal(c.clinica, c.dados); });
      var bShare=document.createElement("button"); bShare.className="app-btn ghost";
      bShare.textContent=c.share_token?"Gerenciar link":"Compartilhar";
      bShare.addEventListener("click",function(){ compartilhar(c, bShare); });
      acts.appendChild(bDados); acts.appendChild(bShare);
      row.appendChild(info); row.appendChild(acts);
      box.appendChild(row);
    });
  }catch(e){box.innerHTML='<div class="app-status err">'+e.message+'</div>';}
}
carregarDossies();
```

- [ ] **Step 3: Adicionar `compartilhar(c, btn)` e `revogar(c, btn)` dentro de `_clientes_js()`**

Adicionar logo após a definição de `renderRespostasModal`/`verRespostas` (Task 5):

```python
async function compartilhar(c, btn){
  if(c.share_token){
    var link=location.origin+location.pathname.replace(/[^/]*$/,"")+"index.html?share="+c.share_token;
    var acao=confirm("Link já ativo:\n"+link+"\n\nOK = copiar de novo · Cancelar = revogar acesso");
    if(acao){ try{await navigator.clipboard.writeText(link);}catch(e){} alert("Copiado."); }
    else { await revogar(c, btn); }
    return;
  }
  var token=(crypto.randomUUID?crypto.randomUUID():(Date.now().toString(36)+Math.random().toString(36).slice(2)))
    .replace(/-/g,"");
  var r=await fetch(SUPABASE_URL+"/rest/v1/dossie_clientes?id=eq."+encodeURIComponent(c.id),{
    method:"PATCH",
    headers:{apikey:SUPABASE_ANON,Authorization:"Bearer "+SUPABASE_ANON,
      "Content-Type":"application/json","Prefer":"return=minimal"},
    body:JSON.stringify({share_token:token})});
  if(!r.ok){ alert("Falha ao gerar link ("+r.status+")."); return; }
  c.share_token=token;
  if(btn) btn.textContent="Gerenciar link";
  var link=location.origin+location.pathname.replace(/[^/]*$/,"")+"index.html?share="+token;
  try{await navigator.clipboard.writeText(link);}catch(e){}
  alert("Link exclusivo do cliente:\n"+link+"\n\n(Copiado para a área de transferência.)");
}
async function revogar(c, btn){
  var r=await fetch(SUPABASE_URL+"/rest/v1/dossie_clientes?id=eq."+encodeURIComponent(c.id),{
    method:"PATCH",
    headers:{apikey:SUPABASE_ANON,Authorization:"Bearer "+SUPABASE_ANON,
      "Content-Type":"application/json","Prefer":"return=minimal"},
    body:JSON.stringify({share_token:null})});
  if(!r.ok){ alert("Falha ao revogar ("+r.status+")."); return; }
  c.share_token=null;
  if(btn) btn.textContent="Compartilhar";
  alert("Acesso revogado.");
}
```

Nota: `compartilhar`/`revogar` devem ser definidas ANTES de `carregarDossies()` no arquivo (JS hoisting de `function` declarada normalmente resolve isso, mas como são `async function` no mesmo padrão das demais, manter a ordem de definição não é estritamente necessária — hoisting cobre ambos os casos aqui).

- [ ] **Step 4: Rodar o gerador e validar**

Run: `cd ~/noeds-replica && python3 build.py`
Expected: sem traceback.

Run: `grep -c "compartilhar\|share_token" ~/noeds-replica/clientes.html`
Expected: `>= 3`.

- [ ] **Step 5: Teste funcional manual end-to-end**

Requer um registro real em `dossie_clientes` (gerado nas tasks anteriores ou já existente). Abrir `clientes.html` publicado (após deploy da Task 10) ou local, clicar "Compartilhar" numa linha com dossiê, confirmar que o link é copiado e que rodar de novo mostra "Gerenciar link" com opção de revogar. Confirmar via:
```bash
curl -s "https://cvzaqqlagwueldpookdf.supabase.co/rest/v1/dossie_clientes?select=id,share_token&share_token=not.is.null" \
  -H "apikey: sb_publishable_guPZajaIZW8_hABcLqIx1w_AD3EKh_o"
```
Expected: linha vazia `[]` se `dossie_clientes` não tem SELECT liberado para anon (esperado pelo padrão RLS do projeto) — nesse caso a confirmação é só visual/pela RPC `get_dossie_by_share` (Task 1, Step 3, repetido agora com um token real).

- [ ] **Step 6: Commit**

Sem git — pular.

---

## Task 9: Prioridade 3 — `index.html` (e demais páginas do dossiê) consomem `?share=<token>`

**Files:**
- Modify: `~/noeds-replica/build.py:294-299` (início de `RENDER_JS`), `~/noeds-replica/build.py:248-273` (`sidebar_html`), `~/noeds-replica/build.py:525-541` (loop de geração das 9 páginas)

**Interfaces:**
- Consumes: RPC `get_dossie_by_share(token)` (Task 1).
- Produces: `RENDER_JS` passa a resolver `dados`/`docs` também via `?share=`, não só via `localStorage.dossie_atual`; sidebar oculta quando em modo compartilhado.

- [ ] **Step 1: Tornar o início de `RENDER_JS` assíncrono e capaz de buscar via `?share=`**

Substituir as linhas iniciais de `RENDER_JS` (`build.py:294-303`, do `(function(){` até a definição de `esc`):

```python
RENDER_JS = r"""
<script>
(async function(){
  var SHARE_SUPABASE_URL="https://cvzaqqlagwueldpookdf.supabase.co";
  var SHARE_SUPABASE_ANON="sb_publishable_guPZajaIZW8_hABcLqIx1w_AD3EKh_o";
  var shareToken=new URLSearchParams(location.search).get("share");
  var raw=null, shareErro=false;
  if(shareToken){
    try{
      var r=await fetch(SHARE_SUPABASE_URL+"/rest/v1/rpc/get_dossie_by_share",{method:"POST",
        headers:{apikey:SHARE_SUPABASE_ANON,Authorization:"Bearer "+SHARE_SUPABASE_ANON,"Content-Type":"application/json"},
        body:JSON.stringify({token:shareToken})});
      var rows=r.ok?await r.json():[];
      if(Array.isArray(rows)&&rows.length){ raw={dados:rows[0].dados||{}, documentos:rows[0].documentos||{}}; }
      else { shareErro=true; }
    }catch(_){ shareErro=true; }
  } else {
    try{ raw=JSON.parse(localStorage.getItem("dossie_atual")||"null"); }catch(_){ raw=null; }
  }
  if(shareErro){
    document.body.innerHTML='<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;font-family:sans-serif;text-align:center;padding:24px"><div><p style="font-size:20px">Link inválido ou expirado.</p><p style="color:#888;margin-top:8px">Peça um novo link à equipe responsável.</p></div></div>';
    return;
  }
  if(shareToken){ document.body.classList.add("dossie-share-mode"); }
  if(!raw) return;
  var dados=raw.dados||{}, docs=raw.documentos||{};

  // slug da página atual pelo arquivo
  var file=(location.pathname.split("/").pop()||"index.html").replace(/\.html$/,"")||"index";
  function esc(s){return (s==null?"":(""+s)).replace(/[&<>]/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;"}[c];});}
```

Nota: `dossie-share-mode` na classe do `<body>` é usado no Step 2 para ocultar a sidebar via CSS (mais simples e robusto que remover o DOM da sidebar, já que a sidebar já foi injetada antes do `RENDER_JS` rodar — ver ordem no `TEMPLATE`, Task global constraints).

- [ ] **Step 2: Ocultar a sidebar via CSS quando em modo compartilhado**

Editar `build.py`, dentro da constante `SIDEBAR_CSS` (buscar sua definição antes do `TEMPLATE`). Adicionar ao final do bloco CSS existente (via concatenação, sem apagar nada):

Run: `grep -n "^SIDEBAR_CSS" ~/noeds-replica/build.py`

Adicionar logo após o fechamento da string `SIDEBAR_CSS = """..."""` encontrada:

```python
SIDEBAR_CSS += """
body.dossie-share-mode #ng-toggle, body.dossie-share-mode #ng-side, body.dossie-share-mode #ng-overlay { display:none !important; }
"""
```

- [ ] **Step 3: Propagar `?share=<token>` nos links de navegação da sidebar (client-side)**

Editar `build.py`, dentro de `SIDEBAR_JS` (`build.py:275-286`), adicionar ao IIFE existente, antes do fechamento `})();`:

```python
SIDEBAR_JS = r"""
<script>
(function(){
  var t=document.getElementById('ng-toggle'), o=document.getElementById('ng-overlay');
  function close(){document.body.classList.remove('ng-open');}
  function toggle(){document.body.classList.toggle('ng-open');}
  if(t)t.addEventListener('click',toggle);
  if(o)o.addEventListener('click',close);
  document.addEventListener('keydown',function(e){if(e.key==='Escape')close();});
  var shareToken=new URLSearchParams(location.search).get("share");
  if(shareToken){
    document.querySelectorAll('#ng-side a.ng-item').forEach(function(a){
      if(a.getAttribute('href')) a.setAttribute('href', a.getAttribute('href')+"?share="+encodeURIComponent(shareToken));
    });
  }
})();
</script>
"""
```

- [ ] **Step 4: Desabilitar o botão "Sair do dossiê" em modo compartilhado**

Editar `build.py`, no fim de `RENDER_JS` (banner "DOSSIÊ · Cliente", identificado no levantamento como `build.py:491-501`). Ajustar para esconder o botão de sair quando `shareToken` está presente:

```python
  // banner discreto indicando dossiê do cliente
  var b=document.createElement("div");
  b.style.cssText="position:fixed;bottom:0;left:0;right:0;z-index:50;background:var(--surface,#111);border-top:1px solid var(--border,#262626);padding:8px 16px 8px 72px;font-size:11px;letter-spacing:.1em;color:var(--muted-foreground,#aaa);display:flex;gap:14px;align-items:center;justify-content:space-between";
  b.innerHTML='<span>DOSSIÊ · '+esc(dados.clinica||"Cliente")+'</span>';
  if(!shareToken){
    var x=document.createElement("button"); x.textContent="Sair do dossiê";
    x.style.cssText="background:none;border:1px solid var(--border,#333);color:inherit;padding:5px 12px;cursor:pointer;font-size:10px;letter-spacing:.2em;text-transform:uppercase";
    x.onclick=function(){ localStorage.removeItem("dossie_atual"); location.reload(); };
    b.appendChild(x);
  }
  document.body.appendChild(b);
})();
</script>
"""
```

- [ ] **Step 5: Rodar o gerador e validar as 9 páginas**

Run: `cd ~/noeds-replica && python3 build.py`
Expected: sem traceback; todas as 9 rotas (`index.html`, `diagnostico.html`, `swot.html`, `bcg.html`, `persona.html`, `marketing.html`, `conteudo.html`, `playbook.html`, `certificado.html`) reescritas.

Run: `grep -c "get_dossie_by_share\|dossie-share-mode" ~/noeds-replica/index.html`
Expected: `>= 2`.

Run: `grep -c "get_dossie_by_share\|dossie-share-mode" ~/noeds-replica/swot.html`
Expected: `>= 2` (confirma que o `RENDER_JS` novo foi propagado para as outras páginas, não só `index.html`).

- [ ] **Step 6: Teste funcional manual com token real**

Usando um token gerado na Task 8 (Step 5), abrir localmente:
```
file:///Users/jean.monai/noeds-replica/index.html?share=<token-real>
```
Expected: a capa do dossiê carrega com os dados do cliente, sidebar (☰) não aparece, banner inferior mostra "DOSSIÊ · <clínica>" sem botão "Sair do dossiê".

Testar token inválido:
```
file:///Users/jean.monai/noeds-replica/index.html?share=tokeninvalido
```
Expected: tela de "Link inválido ou expirado.", sem sidebar, sem crash no console.

- [ ] **Step 7: Commit**

Sem git — pular.

---

## Task 10: Build final + deploy em produção

**Files:** nenhum (task de verificação e deploy).

- [ ] **Step 1: Rodar o build completo do zero**

Run: `cd ~/noeds-replica && python3 build.py`
Expected: todas as saídas listadas sem traceback — 9 páginas do dossiê, `gerar.html`, `clientes.html`, `dossie.html`.

- [ ] **Step 2: Checagem sintática rápida de todos os HTML gerados**

Run: `for f in ~/noeds-replica/*.html; do node -e "require('fs').readFileSync('$f','utf8')" >/dev/null || echo "FALHA: $f"; done`
Expected: nenhuma linha "FALHA" impressa (checagem mínima de que os arquivos existem e são legíveis; não é um validador HTML completo, mas pega erros grosseiros de geração).

- [ ] **Step 3: Confirmar que nenhuma chave nova ficou hardcoded incorretamente**

Run: `grep -n "sk-ant-\|sk-proj-\|AIzaSy" ~/noeds-replica/*.html ~/noeds-replica/*.py`
Expected: nenhum resultado (nenhuma chave de API real commitada nos geradores nem no HTML — só placeholders e a chave publishable do Supabase, que é pública por design).

- [ ] **Step 4: Deploy em produção no Vercel**

Confirmar com o usuário antes de rodar (ação visível publicamente / afeta ambiente compartilhado).

Run: `cd ~/noeds-replica && vercel deploy --prod --yes --scope monaiaraujo27-4850s-projects`
Expected: saída termina com a URL de produção `https://noeds-replica.vercel.app` (ou alias equivalente) e status de deploy bem-sucedido.

- [ ] **Step 5: Smoke test em produção**

Run: `curl -s -o /dev/null -w "%{http_code}\n" https://noeds-replica.vercel.app/clientes.html`
Expected: `200`.

Run: `curl -s -o /dev/null -w "%{http_code}\n" https://noeds-replica.vercel.app/gerar.html`
Expected: `200`.

Run: `curl -s https://noeds-replica.vercel.app/gerar.html | grep -c "claude\|fetchModelos"`
Expected: `>= 1` (confirma que o deploy publicado já reflete a Prioridade 2).

- [ ] **Step 6: Commit**

Sem git — pular.
