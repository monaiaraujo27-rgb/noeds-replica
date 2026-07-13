-- ============================================================
-- Acesso restrito de equipe (papel "vendedor"): só vê/copia clientes,
-- sem criar, excluir, gerenciar link de compartilhamento, ou acessar
-- a tela "Gerar" (chaves de IA). "admin" continua com acesso total.
--
-- get_clientes_auth/get_respostas_auth ficam abertos pra qualquer papel
-- (vendedor precisa ver a lista pra copiar link). upsert_resposta (criar
-- cliente) já é usado pelo formulário público via anon — não dá pra travar
-- por papel ali; a restrição de "vendedor não cria" é só de UI (o botão
-- "+ Novo cliente" fica escondido), decisão consciente: não é superfície
-- de ataque nova, é a mesma permissão que o anon público já tem hoje.
-- ============================================================

create or replace function public.get_meu_papel_auth()
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  p text;
begin
  select papel into p from public.team_members where id = auth.uid();
  if p is null then
    raise exception 'unauthorized';
  end if;
  return p;
end;
$$;
revoke all on function public.get_meu_papel_auth() from public;
grant execute on function public.get_meu_papel_auth() to authenticated;

-- exclusão de resposta de formulário: só admin.
create or replace function public.delete_resposta_auth(rid text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from public.team_members where id = auth.uid() and papel = 'admin') then
    raise exception 'unauthorized';
  end if;
  delete from public.dossie_respostas where id = rid;
end;
$$;
revoke all on function public.delete_resposta_auth(text) from public;
grant execute on function public.delete_resposta_auth(text) to authenticated;

-- gerenciar (criar/revogar) link de compartilhamento do dossiê: só admin.
create or replace function public.set_share_token_auth(cliente_id uuid, novo_token text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from public.team_members where id = auth.uid() and papel = 'admin') then
    raise exception 'unauthorized';
  end if;
  update public.dossie_clientes
  set share_token = novo_token
  where id = cliente_id;
end;
$$;
revoke all on function public.set_share_token_auth(uuid, text) from public;
grant execute on function public.set_share_token_auth(uuid, text) to authenticated;

-- pronto.
