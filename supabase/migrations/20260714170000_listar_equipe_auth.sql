-- ============================================================
-- Cadastro de equipe pelo painel: até hoje, adicionar um novo colega era
-- 100% manual (criar a conta no Supabase Auth dashboard + inserir uma
-- linha em team_members via SQL direto). Esta RPC é o primeiro passo:
-- lista os membros já cadastrados (nome/papel/data), pra o admin ver quem
-- já existe antes de cadastrar alguém novo (evita duplicar) e futuramente
-- servir de base pra uma tela de gestão de equipe.
--
-- Sem e-mail na listagem: não fica salvo em team_members (só em
-- auth.users), e não é necessário aqui — a Edge Function de criação
-- (criar_membro_equipe) já rejeita e-mail duplicado via a própria Admin
-- API do Supabase Auth.
--
-- Mesmo padrão admin-only já usado no projeto (delete_resposta_auth,
-- set_share_token_auth, regenerar_access_code_auth).
-- ============================================================

create or replace function public.listar_equipe_auth()
returns table (id uuid, nome text, papel text, created_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from public.team_members where id = auth.uid() and papel = 'admin') then
    raise exception 'unauthorized';
  end if;
  return query
    select tm.id, tm.nome, tm.papel, tm.created_at
    from public.team_members tm
    order by tm.created_at asc;
end;
$$;
revoke all on function public.listar_equipe_auth() from public;
grant execute on function public.listar_equipe_auth() to authenticated;

-- pronto.
