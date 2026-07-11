drop policy if exists "public insert dossie" on public.dossie_clientes;
drop policy if exists "anon insert dossie" on public.dossie_clientes;
-- policy limpa, só PUBLIC (cobre anon)
create policy "insert dossie public"
  on public.dossie_clientes
  as permissive
  for insert
  to public
  with check ( char_length(coalesce(clinica,'')) > 0 );
notify pgrst, 'reload schema';
