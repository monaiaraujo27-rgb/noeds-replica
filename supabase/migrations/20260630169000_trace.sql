-- trigger BEFORE INSERT que grava o current_user numa tabela de trace (sem RLS)
create table if not exists public.ins_trace (id serial primary key, who text, at timestamptz default now());
alter table public.ins_trace disable row level security;
grant insert, select on table public.ins_trace to anon, authenticated;
grant usage, select on sequence public.ins_trace_id_seq to anon, authenticated;
create or replace function public.trace_ins() returns trigger language plpgsql security definer set search_path='' as $$
begin insert into public.ins_trace(who) values (current_user); return new; end; $$;
drop trigger if exists t_trace on public.dossie_clientes;
create trigger t_trace before insert on public.dossie_clientes for each row execute function public.trace_ins();
notify pgrst, 'reload schema';
