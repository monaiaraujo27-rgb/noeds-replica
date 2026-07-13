-- ============================================================
-- Excluir dossiê gerado (dossie_clientes). Hoje só dava pra excluir o
-- FORMULÁRIO (dossie_respostas, via delete_resposta_auth) — depois de gerar
-- o dossiê, o cliente ficava preso pra sempre em "Banco de clientes" >
-- "Dossiês gerados", sem nenhuma forma de remover pelo painel.
--
-- Mesmo padrão dos outros RPCs admin-only (delete_resposta_auth,
-- set_share_token_auth): security definer, só papel='admin'. dossie_geracoes
-- (histórico de versões) tem "on delete cascade" pra cliente_id — apagar o
-- cliente já limpa o histórico junto, sem precisar de lógica extra aqui.
-- ============================================================

create or replace function public.delete_cliente_auth(cid uuid)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from public.team_members where id = auth.uid() and papel = 'admin') then
    raise exception 'unauthorized';
  end if;
  delete from public.dossie_clientes where id = cid;
end;
$$;
revoke all on function public.delete_cliente_auth(uuid) from public;
grant execute on function public.delete_cliente_auth(uuid) to authenticated;

-- pronto.
