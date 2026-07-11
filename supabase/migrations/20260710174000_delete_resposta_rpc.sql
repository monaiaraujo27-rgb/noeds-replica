-- ============================================================
-- RPC para a EQUIPE excluir um formulário do Banco de clientes.
-- Token-gated (mesmo token da leitura). Anon não tem DELETE policy;
-- este SECURITY DEFINER faz a exclusão de forma controlada.
-- ============================================================

drop function if exists public.delete_resposta(text, text);
create or replace function public.delete_resposta(rid text, token text)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if token <> 'dossie_4df5b2433df2f1cffee71b22' then
    raise exception 'unauthorized';
  end if;
  delete from public.dossie_respostas where id = rid;
end;
$$;

revoke all on function public.delete_resposta(text, text) from public;
grant execute on function public.delete_resposta(text, text) to anon;
