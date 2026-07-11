-- garante INSERT para anon E authenticated (publishable key pode mapear p/ qualquer um)
drop policy if exists "anon insert dossie" on public.dossie_clientes;
create policy "public insert dossie"
  on public.dossie_clientes for insert to anon, authenticated, public
  with check ( char_length(coalesce(clinica,'')) > 0 );
