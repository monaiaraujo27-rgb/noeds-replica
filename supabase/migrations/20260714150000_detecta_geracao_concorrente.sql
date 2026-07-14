-- ============================================================
-- Achado BAIXO/MÉDIO da varredura de segurança (2026-07-14): duas abas
-- gerando o dossiê do MESMO cliente ao mesmo tempo (cliente_origem_id
-- igual) resultavam em "last write wins" silencioso — a segunda geração a
-- salvar sobrescrevia dados/documentos da primeira sem avisar nenhuma das
-- duas abas. Não corrompe dado (dossie_geracoes preserva o histórico de
-- ambas via criar_geracao_auth), mas quem salvou primeiro podia achar que
-- sua versão era a vigente quando na verdade já tinha sido substituída.
--
-- Correção: salvar_dossie_auth agora recebe p_versao_esperada (o
-- created_at da linha que a aba tinha em mãos quando começou a gerar, ou
-- null se é a primeira geração desse cliente). Se a linha já existir com
-- um created_at DIFERENTE do esperado, quer dizer que outra geração já
-- rodou depois que esta aba carregou o cliente — a função recusa o
-- upsert e devolve 'concurrent_generation' em vez de sobrescrever calado.
-- O client decide então se quer forçar a sobrescrita (recarregando o mais
-- recente e confirmando) ou descartar a própria geração.
-- ============================================================

create or replace function public.salvar_dossie_auth(
  p_clinica text,
  p_dados jsonb,
  p_documentos jsonb,
  p_respostas_brutas text,
  p_cliente_origem_id text,
  p_versao_esperada timestamptz default null
)
returns public.dossie_clientes
language plpgsql
security definer
set search_path = ''
as $$
declare
  v public.dossie_clientes;
  atual public.dossie_clientes;
begin
  if not exists (select 1 from public.team_members where id = auth.uid()) then
    raise exception 'unauthorized';
  end if;

  if p_cliente_origem_id is not null then
    select * into atual from public.dossie_clientes where cliente_origem_id = p_cliente_origem_id;

    if atual.id is not null and atual.created_at is distinct from p_versao_esperada then
      raise exception 'concurrent_generation' using errcode = 'P0002';
    end if;

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

revoke all on function public.salvar_dossie_auth(text, jsonb, jsonb, text, text, timestamptz) from public;
grant execute on function public.salvar_dossie_auth(text, jsonb, jsonb, text, text, timestamptz) to authenticated;

-- assinatura antiga (sem p_versao_esperada) sai de circulação — o client
-- passa a sempre enviar o parâmetro novo (null na primeira geração).
drop function if exists public.salvar_dossie_auth(text, jsonb, jsonb, text, text);

-- pronto.
