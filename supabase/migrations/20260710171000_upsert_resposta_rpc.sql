-- ============================================================
-- Fix: anon não tem SELECT policy, então PATCH ?id=eq.X não acha a linha
-- (retorna 204 sem alterar nada). Rota o autosave por um RPC SECURITY DEFINER.
-- ============================================================

drop function if exists public.upsert_resposta(text, text, text, text, int, jsonb);
create or replace function public.upsert_resposta(
  rid text,
  p_clinica text,
  p_responsavel text,
  p_status text,
  p_progresso int,
  p_dados jsonb
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if char_length(coalesce(rid,'')) < 5 then
    raise exception 'invalid id';
  end if;
  insert into public.dossie_respostas (id, clinica, responsavel, status, progresso, dados, atualizado_em)
    values (rid, coalesce(p_clinica,''), coalesce(p_responsavel,''),
            coalesce(p_status,'nao-iniciado'), coalesce(p_progresso,0),
            coalesce(p_dados,'{}'::jsonb), now())
  on conflict (id) do update set
    clinica       = excluded.clinica,
    responsavel   = excluded.responsavel,
    status        = excluded.status,
    progresso     = excluded.progresso,
    dados         = excluded.dados,
    atualizado_em = now();
end;
$$;

revoke all on function public.upsert_resposta(text, text, text, text, int, jsonb) from public;
grant execute on function public.upsert_resposta(text, text, text, text, int, jsonb) to anon;
