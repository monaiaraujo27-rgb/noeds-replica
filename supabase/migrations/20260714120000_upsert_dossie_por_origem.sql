-- ============================================================
-- Bug em produção: gerar o dossiê do mesmo cliente mais de uma vez (comum
-- ao ajustar algo e clicar "Gerar dossiê completo" de novo) criava uma
-- NOVA linha em dossie_clientes a cada "Salvar e finalizar", em vez de
-- atualizar a existente — salvar() em gen_app.py sempre fazia POST/INSERT
-- puro. Resultado: cliente duplicado em "Dossiês gerados", cada linha com
-- seu próprio share_token e seu próprio resultado de IA (não-determinístico
-- entre gerações), dando a impressão de "dados de outro cliente" quando na
-- verdade eram duas versões da mesma geração. Confirmado em produção via
-- inspeção direta (Chrome DevTools): duas linhas "Monnyer slusars", mesmo
-- respostas_brutas, criadas 7 min uma da outra, dados.especialidade e
-- dados.principal_dor com textos diferentes entre si.
--
-- Correção: quando a geração parte de um cliente já cadastrado (fluxo
-- "Gerar dossiê" no Banco de clientes → gerar.html?from=<id>), rastrear
-- esse id de origem (dossie_respostas.id) em dossie_clientes e fazer
-- upsert por ele, preservando o share_token já emitido (não invalidar um
-- link que já possa ter sido enviado ao cliente). Geração "avulsa" (texto
-- colado direto, sem cliente de origem) continua criando linha nova — não
-- há identidade de cliente confiável para dedupe automático nesse caso.
-- ============================================================

alter table public.dossie_clientes
  add column if not exists cliente_origem_id text references public.dossie_respostas(id) on delete set null;

-- unicidade parcial: só bloqueia duplicata quando a origem é rastreada.
-- linhas antigas/avulsas com cliente_origem_id null não são afetadas.
create unique index if not exists dossie_clientes_origem_unica
  on public.dossie_clientes (cliente_origem_id)
  where cliente_origem_id is not null;

create or replace function public.salvar_dossie_auth(
  p_clinica text,
  p_dados jsonb,
  p_documentos jsonb,
  p_respostas_brutas text,
  p_cliente_origem_id text
)
returns public.dossie_clientes
language plpgsql
security definer
set search_path = ''
as $$
declare
  v public.dossie_clientes;
begin
  if not exists (select 1 from public.team_members where id = auth.uid()) then
    raise exception 'unauthorized';
  end if;

  if p_cliente_origem_id is not null then
    insert into public.dossie_clientes (clinica, dados, documentos, respostas_brutas, cliente_origem_id)
    values (p_clinica, p_dados, p_documentos, p_respostas_brutas, p_cliente_origem_id)
    on conflict (cliente_origem_id) where cliente_origem_id is not null
    do update set
      clinica = excluded.clinica,
      dados = excluded.dados,
      documentos = excluded.documentos,
      respostas_brutas = excluded.respostas_brutas,
      created_at = now()
      -- share_token NÃO é sobrescrito: preserva link já emitido/enviado ao cliente.
    returning * into v;
  else
    insert into public.dossie_clientes (clinica, dados, documentos, respostas_brutas)
    values (p_clinica, p_dados, p_documentos, p_respostas_brutas)
    returning * into v;
  end if;

  return v;
end;
$$;

revoke all on function public.salvar_dossie_auth(text, jsonb, jsonb, text, text) from public;
grant execute on function public.salvar_dossie_auth(text, jsonb, jsonb, text, text) to authenticated;

-- pronto.
