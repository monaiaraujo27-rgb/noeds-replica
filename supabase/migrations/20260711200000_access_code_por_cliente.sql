-- ============================================================
-- Level 4.8: código de acesso único por cliente, em vez do código fixo
-- global "MKT@2026" usado por todos os formulários. O código de acesso
-- de um cliente não deve abrir o formulário de outro.
--
-- Coluna nova em dossie_respostas: access_code (gerado ao criar "Novo
-- cliente", formato curto tipo 6 caracteres alfanuméricos). Validação via
-- RPC (não expor a lista de códigos válidos, não comparar client-side).
-- ============================================================

alter table public.dossie_respostas add column if not exists access_code text;

-- RPC: valida o código digitado contra o registro (por id), sem expor
-- o código real em caso de erro nem listar códigos de outros clientes.
create or replace function public.check_access_code(rid text, code text)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  ok boolean;
begin
  select (access_code is not null and access_code = code) into ok
  from public.dossie_respostas where id = rid;
  return coalesce(ok, false);
end;
$$;
revoke all on function public.check_access_code(text, text) from public;
grant execute on function public.check_access_code(text, text) to anon;

-- pronto.
