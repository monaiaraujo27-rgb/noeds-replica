-- remove linhas de teste de QA da tabela dossie_respostas
delete from public.dossie_respostas
where id like 'dossie-test%' or id like 'dossie-rpc%' or id = 'dossie-qatest-browser1';
