-- ============================================================
-- Achado CRÍTICO da auditoria pós-Fase 0 (2026-07-11): set_share_token(cliente_id, novo_token)
-- não validava NENHUMA autorização — qualquer requisição anônima (com a
-- publishable key, que já é pública) podia chamar esse RPC para QUALQUER
-- cliente_id (UUID) e sobrescrever/revogar o share_token daquele cliente,
-- sequestrando ou derrubando o link de compartilhamento de qualquer cliente.
-- Confirmado via teste real (HTTP 204 sem token) e revertido sem dano.
--
-- Esta função também não existia em nenhuma migration rastreável — só no
-- SQL solto supabase_clientes_share.sql na raiz do projeto (aplicado
-- manualmente ao banco fora de qualquer histórico). Esta migration recria
-- a função (idempotente) já corrigida, trazendo-a para o histórico real.
--
-- Correção: exigir o mesmo READ_TOKEN da equipe (mesmo padrão de
-- get_clientes/get_respostas/delete_resposta) — só quem opera o painel
-- pode gerar/revogar um link de compartilhamento.
-- ============================================================

drop function if exists public.set_share_token(uuid, text);
create or replace function public.set_share_token(cliente_id uuid, novo_token text, token text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if token <> 'dossie_c70b8dae24408ffc7b3c8bb946f81396' then
    raise exception 'unauthorized';
  end if;
  update public.dossie_clientes
  set share_token = novo_token
  where id = cliente_id;
end;
$$;

revoke all on function public.set_share_token(uuid, text, text) from public;
grant execute on function public.set_share_token(uuid, text, text) to anon;

-- get_dossie_by_share continua sem token de equipe (é o RPC que o CLIENTE
-- final usa para ver o dossiê, intencionalmente público dado o token — só
-- exige o token aleatório de posse, já validado por char_length >= 8).

-- pronto.
