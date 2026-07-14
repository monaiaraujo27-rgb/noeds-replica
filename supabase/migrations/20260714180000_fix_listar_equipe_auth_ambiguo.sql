-- ============================================================
-- Corrige bug real confirmado em produção: listar_equipe_auth() falhava
-- com "column reference id is ambiguous" (42702). Causa: a cláusula
-- "returns table (id uuid, ...)" declara "id" como nome de coluna de
-- retorno da própria função — dentro do corpo, isso colide com
-- team_members.id no "where id = auth.uid()" (o Postgres não sabe se "id"
-- é a coluna de saída ou a da tabela). Corrigido qualificando com o alias
-- da tabela (tm.id) na checagem de autorização também, não só no select.
-- ============================================================

create or replace function public.listar_equipe_auth()
returns table (id uuid, nome text, papel text, created_at timestamptz)
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not exists (select 1 from public.team_members tm where tm.id = auth.uid() and tm.papel = 'admin') then
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
