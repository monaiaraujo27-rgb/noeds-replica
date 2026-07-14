#!/usr/bin/env python3
"""
Gerador da réplica estática fiel de noeds-architect-suite.lovable.app
Estratégia: usa o HTML server-rendered REAL de cada rota (já baixado via curl),
remove apenas o badge da plataforma Lovable e os scripts de hidratação,
religa os links internos para arquivos .html locais e inlina o CSS real.
Nada de conteúdo é inventado — markup e texto vêm da fonte original.
"""
import re, os, html, pathlib

OUT = pathlib.Path(__file__).resolve().parent
# fontes versionadas em ./src (fallback p/ /tmp, que é volátil)
SRC = OUT / "src" if (OUT / "src" / "noeds.css").exists() else pathlib.Path("/tmp")
PAGES_SRC = SRC / "noeds_pages"
OUT.mkdir(exist_ok=True)

# slug -> arquivo de saída (índice é a home)
ROUTES = {
    "index": ("index.html", SRC / "noeds.html"),
    "diagnostico": ("diagnostico.html", PAGES_SRC / "diagnostico.html"),
    "swot": ("swot.html", PAGES_SRC / "swot.html"),
    "bcg": ("bcg.html", PAGES_SRC / "bcg.html"),
    "persona": ("persona.html", PAGES_SRC / "persona.html"),
    "marketing": ("marketing.html", PAGES_SRC / "marketing.html"),
    "conteudo": ("conteudo.html", PAGES_SRC / "conteudo.html"),
    "playbook": ("playbook.html", PAGES_SRC / "playbook.html"),
    "certificado": ("certificado.html", PAGES_SRC / "certificado.html"),
}

# mapa de href interno do original -> arquivo local
LINK_MAP = {
    "/": "index.html",
    "/diagnostico": "diagnostico.html",
    "/swot": "swot.html",
    "/bcg": "bcg.html",
    "/persona": "persona.html",
    "/marketing": "marketing.html",
    "/conteudo": "conteudo.html",
    "/playbook": "playbook.html",
    "/certificado": "certificado.html",
}

# ordem dos itens de navegação entre páginas (rótulo, arquivo)
NAV_PAGES = [
    ("Início", "index.html"),
    ("Diagnóstico", "diagnostico.html"),
    ("SWOT", "swot.html"),
    ("Matriz BCG", "bcg.html"),
    ("Persona", "persona.html"),
    ("Marketing", "marketing.html"),
    ("Conteúdo", "conteudo.html"),
    ("Playbook", "playbook.html"),
    ("Certificado", "certificado.html"),
]

# CSS real do site (baixado). Remove apenas as regras do badge da plataforma.
CSS = (SRC / "noeds.css").read_text(encoding="utf-8")
# tira o @font-face e as regras #lovable-badge* (pertencem à plataforma, não ao design)
CSS = re.sub(r"@font-face\s*\{[^}]*CameraPlainVariable[^}]*\}", "", CSS, flags=re.S)
CSS = re.sub(r"#lovable-badge[^{]*\{[^}]*\}", "", CSS)
CSS = re.sub(r"@media[^{]*\{\s*#lovable-badge[^@]*?\}\s*\}", "", CSS, flags=re.S)

# Tema claro do dossiê (camada aditiva, vem DEPOIS do CSS original na cascata —
# mesma especificidade de seletor, então a ordem decide). Padrão é claro
# (:root:not([data-theme="dark"])); [data-theme="dark"] restaura a paleta
# escura original do design (era o :root fixo antes do toggle existir). O
# atributo data-theme é setado no <html> por um script anti-FOUC (ver
# THEME_BOOT_JS) que roda antes de qualquer paint, lendo a preferência salva
# no localStorage de CADA navegador (não é sincronizado entre pessoas).
#
# PDF/impressão ficam sempre claros de propósito, independente do tema da
# tela — não remover esses dois blocos ao mexer no tema.
CSS += """
:root:not([data-theme="dark"]) {
  --background:#ffffff; --foreground:#1a1a1a; --surface:#f7f6f3; --surface-2:#efeee9;
  --border:#e2e0d9; --muted-foreground:#5c5b56; --faint:#8f8d85;
  --color-background:#ffffff; --color-foreground:#1a1a1a; --color-border:#e2e0d9;
}
/* body nunca tem o atributo data-theme (só o <html> tem, ver THEME_BOOT_JS)
   — "body:not([data-theme=dark])" seria sempre verdadeiro mesmo no escuro
   e brigaria com a regra escura abaixo. Usa "html:not(...) body" (ancestral)
   em vez de "body:not(...)" (o próprio elemento, que nunca tem o atributo). */
html:not([data-theme="dark"]), html:not([data-theme="dark"]) body { background:#ffffff !important; color:#1a1a1a !important; }
:root[data-theme="dark"] {
  --background:#000000; --foreground:#ffffff; --surface:#080808; --surface-2:#0e0e0e;
  --border:#151515; --muted-foreground:#a0a0a0; --faint:#707070;
  --color-background:#000000; --color-foreground:#ffffff; --color-border:#151515;
}
html[data-theme="dark"], html[data-theme="dark"] body { background:#000000 !important; color:#ffffff !important; }
/* PDF sempre claro (impressão/leitura formal), mesmo se a tela estiver no escuro. */
body.pdf-capturing #doc-print-area { background:#ffffff !important; color:#1a1a1a !important; }
/* o CSS original tem ::selection{color:#fff;background:#ffffff1f} (pensado pro
   tema escuro) — no claro isso é texto branco em fundo quase-branco, invisível
   ao selecionar. Redeclara os dois casos explicitamente. */
html:not([data-theme="dark"]) ::selection { color:#1a1a1a; background:#d8d4c4; }
html[data-theme="dark"] ::selection { color:#ffffff; background:#ffffff33; }
"""

# Fonts: o original carrega Cormorant Garamond + Inter via Google Fonts.
FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" '
    'href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600'
    '&family=Inter:wght@300;400;500;600&display=swap">'
)

def get_title(src_html):
    m = re.search(r"<title>(.*?)</title>", src_html, re.S)
    return html.unescape(m.group(1).strip()) if m else "Noeds · Consultoria Estratégica"

def get_body(src_html):
    m = re.search(r"<body[^>]*>(.*)</body>", src_html, re.S)
    body = m.group(1) if m else src_html
    # remover scripts de hidratação / TSR
    body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
    # remover o badge da plataforma Lovable (não faz parte do design do cliente)
    body = re.sub(r'<aside id="lovable-badge".*?</aside>', "", body, flags=re.S)
    # remover comentários de streaming RSC (<!--$--> etc.)
    body = re.sub(r"<!--/?\$[^>]*-->", "", body)
    body = re.sub(r"<!--\s*-->", "", body)
    return body

def relink(body):
    # converte href="/rota" -> href="rota.html"
    def repl(m):
        href = m.group(1)
        if href in LINK_MAP:
            return f'href="{LINK_MAP[href]}"'
        return m.group(0)
    return re.sub(r'href="(/[a-z]*)"', repl, body)

# ---------------------------------------------------------------------------
# MELHORIAS (camada aditiva — não altera o markup/design original)
#   1. Exportar PDF: botões "Baixar PDF"/"PDF" chamam window.print()
#   2. Navegação por capítulos: scroll suave + capítulo ativo (IntersectionObserver)
#   3. Gráficos: quadrante BCG + grade 2x2 SWOT (injetados via JS nas páginas certas)
# ---------------------------------------------------------------------------
PRINT_CSS = """
@media print {
  /* esconde navegação; expande o documento para a folha inteira */
  aside, .lg\\:ml-\\[300px\\] > div.sticky, [aria-label="Capítulos"] { display:none !important; }
  .lg\\:ml-\\[300px\\] { margin-left:0 !important; }
  html, body { background:#fff !important; color:#000 !important; }
  .bg-background, .bg-surface, .bg-surface-2 { background:#fff !important; }
  .text-foreground, h1, h2, h3, p, div, span, .serif { color:#000 !important; }
  .text-muted-foreground, .text-faint { color:#444 !important; }
  .border-border, .hairline, [class*="border"] { border-color:#ccc !important; background:#ccc !important; }
  .hairline { background:#ccc !important; }
  section, .doc-section { break-inside:avoid; page-break-inside:avoid; }
  a[href]::after { content:""; }
  @page { margin:18mm 16mm; }
}
/* destaque do capítulo ativo na navegação */
.noeds-chapter-active span:last-child { color:var(--foreground) !important; }
.noeds-chapter-active span:first-child { color:var(--muted-foreground) !important; }
html { scroll-behavior:smooth; }
/* gráficos injetados */
.noeds-chart { margin-top:2.5rem; }
.noeds-quad { display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--border);
  border:1px solid var(--border); aspect-ratio:1/1; max-width:560px; }
.noeds-quad > div { background:var(--surface); padding:1.25rem 1.5rem; display:flex; flex-direction:column; justify-content:space-between; }
.noeds-quad .q-tag { font-family:var(--font-sans); font-size:10px; letter-spacing:.28em; text-transform:uppercase; color:var(--faint); }
.noeds-quad .q-name { font-family:var(--font-serif); font-size:19px; margin-top:.4rem; line-height:1.2; }
.noeds-quad .q-meta { font-size:12px; color:var(--muted-foreground); margin-top:.75rem; font-weight:300; }
.noeds-axis { font-family:var(--font-sans); font-size:10px; letter-spacing:.2em; text-transform:uppercase; color:var(--faint); }
.noeds-swot { display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--border); border:1px solid var(--border); }
.noeds-swot > div { background:var(--surface); padding:1.5rem 1.75rem; }
.noeds-swot .s-tag { font-family:var(--font-sans); font-size:10px; letter-spacing:.28em; text-transform:uppercase; }
.noeds-swot .s-body { font-size:13px; color:var(--muted-foreground); margin-top:.6rem; font-weight:300; line-height:1.7; }
"""

ENHANCE_JS = r"""
<script src="/src/vendor/html2canvas-pro.min.js"></script>
<script src="/src/vendor/jspdf.umd.min.js"></script>
<script>
(function(){
  // 1. PDF: qualquer botão com texto "Baixar PDF"/"PDF" gera um PDF real
  // (captura o DOM renderizado, preservando 100% do design) em vez de só
  // abrir a caixa de impressão do navegador. html2canvas-pro (não a lib
  // html2canvas original) porque o site usa cores CSS modernas (oklch/
  // color-mix via Tailwind v4) que a html2canvas clássica não sabe parsear
  // — só o fork -pro suporta. jsPDF monta o PDF a partir do canvas
  // capturado, paginando em A4 se o conteúdo for mais alto que 1 página.
  // Se alguma lib não carregar, cai de volta pro window.print() antigo.
  document.querySelectorAll('button').forEach(function(b){
    var t=(b.textContent||'').trim();
    if(t==='Baixar PDF'||t==='PDF'){
      b.style.cursor='pointer'; b.removeAttribute('disabled');
      b.addEventListener('click',async function(){
        if(typeof html2canvas==='undefined' || typeof window.jspdf==='undefined'){ window.print(); return; }
        var alvo=document.getElementById('doc-print-area')
          || document.querySelector('main section[id]')?.closest('main')
          || document.querySelector('main') || document.body;
        var nomeArq=(document.title||'dossie').replace(/[^\w\- ]+/g,'').trim()+'.pdf';
        var textoOrig=b.textContent; b.textContent='Gerando PDF…'; b.disabled=true;
        try{
          var canvas=await html2canvas(alvo,{scale:2,useCORS:true,backgroundColor:'#ffffff'});
          var jsPDF=window.jspdf.jsPDF;
          var margemMm=14, larguraA4=210, alturaA4=297;
          var larguraUtil=larguraA4-margemMm*2;
          var alturaUtilPx=canvas.width/larguraUtil*(alturaA4-margemMm*2);
          var pdf=new jsPDF({unit:'mm',format:'a4',orientation:'portrait'});
          var yCanvas=0, primeira=true;
          while(yCanvas<canvas.height){
            var fatia=document.createElement('canvas');
            fatia.width=canvas.width;
            fatia.height=Math.min(alturaUtilPx, canvas.height-yCanvas);
            fatia.getContext('2d').drawImage(canvas,0,yCanvas,canvas.width,fatia.height,0,0,canvas.width,fatia.height);
            var imgData=fatia.toDataURL('image/jpeg',0.95);
            var alturaMm=fatia.height*larguraUtil/canvas.width;
            if(!primeira) pdf.addPage();
            pdf.addImage(imgData,'JPEG',margemMm,margemMm,larguraUtil,alturaMm);
            yCanvas+=fatia.height; primeira=false;
          }
          pdf.save(nomeArq);
        }catch(e){ console.error('Falha ao gerar PDF, usando impressão do navegador:',e); window.print(); }
        finally{ b.textContent=textoOrig; b.disabled=false; }
      });
    }
  });

  // 2. Navegação por capítulos: liga o N-ésimo botão da sidebar à N-ésima <section>
  var sections=[].slice.call(document.querySelectorAll('#doc-print-area section[id], main section[id], section[id]'));
  // botões de capítulo (sidebar desktop)
  var navBtns=[].slice.call(document.querySelectorAll('nav button.group'));
  if(sections.length && navBtns.length){
    var n=Math.min(sections.length,navBtns.length);
    for(var i=0;i<n;i++){(function(idx){
      navBtns[idx].style.cursor='pointer';
      navBtns[idx].addEventListener('click',function(){
        sections[idx].scrollIntoView({behavior:'smooth',block:'start'});
      });
    })(i);}
    // capítulo ativo conforme rola
    if('IntersectionObserver' in window){
      var io=new IntersectionObserver(function(entries){
        entries.forEach(function(e){
          if(e.isIntersecting){
            var idx=sections.indexOf(e.target);
            navBtns.forEach(function(b){b.classList.remove('noeds-chapter-active');});
            if(navBtns[idx]) navBtns[idx].classList.add('noeds-chapter-active');
          }
        });
      },{rootMargin:'-20% 0px -70% 0px'});
      sections.forEach(function(s){io.observe(s);});
    }
  }

  // 3a. Gráfico quadrante na Matriz BCG (injeta após a 1ª seção "Leitura do Portfólio")
  var bcg=document.querySelector('#portfolio');
  if(bcg && !document.querySelector('.noeds-quad')){
    var box=bcg.querySelector('div.mt-10, div[class*="mt-1"]')||bcg;
    var wrap=document.createElement('div'); wrap.className='noeds-chart';
    wrap.innerHTML=''
      +'<div class="noeds-axis" style="margin-bottom:.6rem">Crescimento de mercado ↑ · Participação →</div>'
      +'<div class="noeds-quad">'
      +'<div><div><div class="q-tag">Estrela</div><div class="q-name">Alta escala</div></div><div class="q-meta">Maior fatia do investimento · 60%</div></div>'
      +'<div><div><div class="q-tag">Interrogação</div><div class="q-name">Validar</div></div><div class="q-meta">Teste de oferta/canal · 15%</div></div>'
      +'<div><div><div class="q-tag">Vaca Leiteira</div><div class="q-name">Sustentação</div></div><div class="q-meta">Caixa e recorrência · 25%</div></div>'
      +'<div><div><div class="q-tag">Abacaxi</div><div class="q-name">Revisar</div></div><div class="q-meta">Baixo retorno · reduzir</div></div>'
      +'</div>';
    box.appendChild(wrap);
  }

  // 3b. Grade 2x2 visual no SWOT (injeta no fim da 1ª seção "Forças")
  var swotFirst=document.querySelector('#forcas');
  var isSwot=/An[aá]lise SWOT/.test((document.querySelector('h1')||{}).textContent||'');
  if(isSwot && swotFirst && !document.querySelector('.noeds-swot')){
    var grid=document.createElement('div'); grid.className='noeds-chart';
    grid.innerHTML='<div class="noeds-swot">'
      +'<div><div class="s-tag" style="color:#cfcfcf">Forças</div><div class="s-body">Internas · positivas — o que já funciona e diferencia.</div></div>'
      +'<div><div class="s-tag" style="color:#cfcfcf">Fraquezas</div><div class="s-body">Internas · negativas — o que trava o crescimento.</div></div>'
      +'<div><div class="s-tag" style="color:#cfcfcf">Oportunidades</div><div class="s-body">Externas · positivas — o que pode ser aproveitado.</div></div>'
      +'<div><div class="s-tag" style="color:#cfcfcf">Ameaças</div><div class="s-body">Externas · negativas — o que precisa ser observado.</div></div>'
      +'</div>';
    swotFirst.appendChild(grid);
  }
})();
</script>
"""

# script anti-FOUC (Flash Of Unstyled Content): roda ANTES de qualquer CSS
# ser parseado, lendo a preferência de tema salva no localStorage deste
# navegador e já setando o atributo no <html> — sem isso, a página sempre
# pisca no tema claro (padrão) antes de trocar pro escuro escolhido.
# Compartilhado entre o dossiê (build.py TEMPLATE) e o painel interno
# (gen_app.py _page()); NÃO usado no formulário público (fora de escopo).
THEME_BOOT_JS = """<script>(function(){try{
  if(localStorage.getItem('noeds_theme')==='dark') document.documentElement.setAttribute('data-theme','dark');
}catch(e){}})();</script>"""

# ---------------------------------------------------------------------------
# SIDEBAR GLOBAL (camada aditiva)
#   - oculta por padrão, abre no botão ☰ (hambúrguer, canto superior esquerdo)
#   - itens: Gerar · Banco de clientes · (linha) · 9 páginas do dossiê
#   - injetada logo após <body> em TODAS as páginas
# ---------------------------------------------------------------------------
SIDEBAR_CSS = """
/* ---- sidebar global (camada aditiva, não faz parte do design original) ---- */
#ng-toggle { position:fixed; top:18px; left:18px; z-index:60; width:42px; height:42px;
  display:flex; flex-direction:column; align-items:center; justify-content:center; gap:5px;
  background:var(--surface,#111); border:1px solid var(--border,#262626); cursor:pointer;
  transition:border-color .25s, background .25s; }
#ng-toggle:hover { border-color:var(--foreground,#fff); }
#ng-toggle span { display:block; width:18px; height:1px; background:var(--muted-foreground,#aaa); transition:.3s; }
body.ng-open #ng-toggle span:nth-child(1){ transform:translateY(6px) rotate(45deg); }
body.ng-open #ng-toggle span:nth-child(2){ opacity:0; }
body.ng-open #ng-toggle span:nth-child(3){ transform:translateY(-6px) rotate(-45deg); }
#ng-overlay { position:fixed; inset:0; z-index:55; background:rgba(0,0,0,.55);
  opacity:0; pointer-events:none; transition:opacity .3s; }
body.ng-open #ng-overlay { opacity:1; pointer-events:auto; }
#ng-side { position:fixed; top:0; left:0; bottom:0; z-index:58; width:300px; max-width:84vw;
  background:var(--surface,#0e0e0e); border-right:1px solid var(--border,#262626);
  transform:translateX(-104%); transition:transform .32s cubic-bezier(.4,0,.2,1);
  display:flex; flex-direction:column; padding:84px 0 28px; overflow-y:auto; }
body.ng-open #ng-side { transform:translateX(0); }
#ng-side .ng-brand { padding:0 28px 22px; }
#ng-side .ng-brand .e { font-family:var(--font-sans,sans-serif); font-size:10px; letter-spacing:.3em;
  text-transform:uppercase; color:var(--faint,#666); }
#ng-side .ng-brand .n { font-family:var(--font-serif,serif); font-size:22px; color:var(--foreground,#fff); margin-top:6px; }
#ng-side .ng-sep { height:1px; background:var(--border,#262626); margin:8px 28px; }
#ng-side .ng-label { padding:14px 28px 6px; font-size:9px; letter-spacing:.28em; text-transform:uppercase; color:var(--faint,#666); }
#ng-side a.ng-item { display:flex; align-items:center; gap:12px; padding:13px 28px;
  color:var(--muted-foreground,#aaa); text-decoration:none; font-size:14px; font-weight:300;
  border-left:2px solid transparent; transition:color .2s, background .2s, border-color .2s; }
#ng-side a.ng-item:hover { color:var(--foreground,#fff); background:var(--surface-2,#161616); }
#ng-side a.ng-item.ng-active { color:var(--foreground,#fff); border-left-color:var(--foreground,#fff); }
#ng-side a.ng-item .ic { width:16px; text-align:center; opacity:.7; }
#ng-side a.ng-item.ng-primary { font-size:15px; color:var(--foreground,#eee); }
@media print { #ng-toggle, #ng-overlay, #ng-side, #ng-theme-toggle { display:none !important; } }
"""
SIDEBAR_CSS += """
body.dossie-share-mode #ng-toggle, body.dossie-share-mode #ng-side, body.dossie-share-mode #ng-overlay { display:none !important; }
body.ng-share-view .ng-team-only { display:none !important; }
"""
# botão de tema: elemento PRÓPRIO, fora de #ng-side de propósito — a regra
# acima esconde a sidebar inteira no modo "?share=" (link do cliente final),
# mas o toggle precisa continuar visível ali (é o cenário mais provável de
# alguém sem contexto do painel querer trocar de tema).
#
# Posição: canto INFERIOR esquerdo, não superior — o topo já tem o
# hambúrguer (#ng-toggle, esquerda) e, no painel, até 5 botões de conta
# (.auth-logout: Sair/Trocar senha/Prompt/PMI/Cadastrar equipe,
# right:18px a 483px, condicionais por papel/admin) que já disputam espaço
# entre si em telas estreitas — testado e confirmado colidindo com o
# toggle quando ele também ficava no topo. O rodapé fica livre no painel;
# no dossiê o banner "DOSSIÊ · Cliente" ocupa o rodapé inteiro, mas com
# altura conhecida (~40px) — o toggle fica ACIMA dele (bottom:56px), sem
# sobrepor.
SIDEBAR_CSS += """
#ng-theme-toggle { position:fixed; bottom:56px; left:18px; z-index:60;
  display:flex; align-items:center; gap:8px; height:42px; padding:0 16px;
  background:var(--surface,#111); border:1px solid var(--border,#262626);
  color:var(--muted-foreground,#aaa); font-family:var(--font-sans,sans-serif);
  font-size:11px; letter-spacing:.08em; text-transform:uppercase; cursor:pointer;
  transition:border-color .25s, color .25s; }
#ng-theme-toggle:hover { border-color:var(--foreground,#fff); color:var(--foreground,#fff); }
"""

def sidebar_html(active_file):
    """gera a sidebar marcando o item ativo (active_file = nome do arquivo atual)."""
    items = []
    # itens de aplicação (primeiros)
    apps = [("Gerar", "gerar.html", "✎"), ("Banco de clientes", "clientes.html", "▤")]
    for label, file, ic in apps:
        cls = "ng-item ng-primary ng-team-only" + (" ng-active" if file == active_file else "")
        items.append(
            f'<a class="{cls}" href="{file}"><span class="ic">{ic}</span>{label}</a>'
        )
    nav = '<div class="ng-label">Dossiê</div>'
    pages = []
    for label, file in NAV_PAGES:
        cls = "ng-item" + (" ng-active" if file == active_file else "")
        pages.append(f'<a class="{cls}" href="{file}">{label}</a>')
    return (
        '<button id="ng-toggle" aria-label="Abrir menu"><span></span><span></span><span></span></button>'
        '<button id="ng-theme-toggle" aria-label="Alternar tema"><span id="ng-theme-label">Preto (premium)</span></button>'
        '<div id="ng-overlay"></div>'
        '<nav id="ng-side" aria-label="Navegação global">'
        '<div class="ng-brand"><div class="e">Consultoria Estratégica</div><div class="n">Noeds</div></div>'
        + "".join(items)
        + '<div class="ng-sep ng-team-only"></div>'
        + nav
        + "".join(pages)
        + "</nav>"
    )

SIDEBAR_JS = r"""
<script>
(function(){
  var t=document.getElementById('ng-toggle'), o=document.getElementById('ng-overlay');
  function close(){document.body.classList.remove('ng-open');}
  function toggle(){document.body.classList.toggle('ng-open');}
  if(t)t.addEventListener('click',toggle);
  if(o)o.addEventListener('click',close);
  document.addEventListener('keydown',function(e){if(e.key==='Escape')close();});
  var shareToken=new URLSearchParams(location.search).get("share");
  if(shareToken){
    document.body.classList.add('ng-share-view');
    // propaga o token em QUALQUER link interno pra outra página do dossiê —
    // não só os da sidebar (#ng-side a.ng-item), mas também os "Abrir
    // Documento" da home (index.html) e afins. Sem isso, o cliente clicava
    // num link, o "?share=" se perdia, e a página seguinte caía no modo
    // "preview sem dados" (placeholders tipo [Nome da Clínica]) em vez de
    // mostrar o próprio dossiê.
    document.querySelectorAll('a[href]').forEach(function(a){
      var href=a.getAttribute('href');
      if(href && /^[a-z0-9_-]+\.html$/i.test(href)){
        a.setAttribute('href', href+"?share="+encodeURIComponent(shareToken));
      }
    });
  }
  // tema: preferência pessoal por navegador (localStorage, não sincronizada
  // entre pessoas nem entre painel/dossiê e o link do cliente final). O
  // atributo já foi setado no <html> pelo script anti-FOUC do <head>, se
  // aplicável — aqui só sincroniza o rótulo do botão e liga o clique.
  var THEME_KEY='noeds_theme';
  var btnT=document.getElementById('ng-theme-toggle'), lblT=document.getElementById('ng-theme-label');
  function aplicarTema(t){
    if(t==='dark') document.documentElement.setAttribute('data-theme','dark');
    else document.documentElement.removeAttribute('data-theme');
    if(lblT) lblT.textContent = t==='dark' ? 'Branco (creme)' : 'Preto (premium)';
  }
  aplicarTema(localStorage.getItem(THEME_KEY)==='dark' ? 'dark' : 'light');
  if(btnT) btnT.addEventListener('click', function(){
    var atual = document.documentElement.getAttribute('data-theme')==='dark' ? 'dark' : 'light';
    var novo = atual==='dark' ? 'light' : 'dark';
    try{ localStorage.setItem(THEME_KEY, novo); }catch(e){}
    aplicarTema(novo);
  });
})();
</script>
"""

# ---------------------------------------------------------------------------
# RENDER_JS — injeta o conteúdo do cliente (localStorage.dossie_atual) nas 9 páginas.
# Lê {dados, documentos}. Sem dados -> página fica no modelo. Camada aditiva.
# O conteúdo da IA segue o contrato de gen_app.py (DOC_SPECS); aqui reconstruímos
# o miolo de cada seção conhecida com as MESMAS classes do design.
# ---------------------------------------------------------------------------
RENDER_JS = r"""
<script>
(async function(){
  var SHARE_SUPABASE_URL="https://cvzaqqlagwueldpookdf.supabase.co";
  var SHARE_SUPABASE_ANON="sb_publishable_guPZajaIZW8_hABcLqIx1w_AD3EKh_o";
  var shareToken=new URLSearchParams(location.search).get("share");
  var raw=null, shareErro=false;
  if(shareToken){
    try{
      var r=await fetch(SHARE_SUPABASE_URL+"/rest/v1/rpc/get_dossie_by_share",{method:"POST",
        headers:{apikey:SHARE_SUPABASE_ANON,Authorization:"Bearer "+SHARE_SUPABASE_ANON,"Content-Type":"application/json"},
        body:JSON.stringify({token:shareToken})});
      var rows=r.ok?await r.json():[];
      if(Array.isArray(rows)&&rows.length){ raw={dados:rows[0].dados||{}, documentos:rows[0].documentos||{}}; }
      else { shareErro=true; }
    }catch(_){ shareErro=true; }
  } else {
    try{ raw=JSON.parse(localStorage.getItem("dossie_atual")||"null"); }catch(_){ raw=null; }
  }
  if(shareErro){
    document.body.innerHTML='<div style="min-height:100vh;display:flex;align-items:center;justify-content:center;font-family:sans-serif;text-align:center;padding:24px"><div><p style="font-size:20px">Link inválido ou expirado.</p><p style="color:#888;margin-top:8px">Peça um novo link à equipe responsável.</p></div></div>';
    return;
  }
  if(shareToken){ document.body.classList.add("dossie-share-mode"); }
  if(!raw) return;
  var dados=raw.dados||{}, docs=raw.documentos||{};
  // preview interno (sem shareToken): dossie_atual é uma chave global, então
  // se a equipe gerar OUTRO cliente em outra aba, esta aba (se recarregada)
  // passa a ver o cliente novo sem aviso. sessionStorage é por aba: se essa
  // aba já tinha visto uma revisão diferente antes, o rev mudou por baixo
  // dela — mostra um aviso em vez de silenciosamente trocar de cliente.
  var trocouDeCliente=false;
  if(!shareToken && raw.rev){
    var revVista=sessionStorage.getItem("dossie_preview_rev");
    if(revVista && revVista!==(""+raw.rev)) trocouDeCliente=true;
    sessionStorage.setItem("dossie_preview_rev", ""+raw.rev);
  }

  // slug da página atual pelo arquivo
  var file=(location.pathname.split("/").pop()||"index.html").replace(/\.html$/,"")||"index";
  if(shareToken && dados.clinica){
    var PAGE_LABELS={"index":"","diagnostico":"Diagnóstico","swot":"SWOT","bcg":"Matriz BCG",
      "persona":"Persona","marketing":"Marketing","conteudo":"Conteúdo","playbook":"Playbook","certificado":"Certificado"};
    var pageLabel=PAGE_LABELS[file]||"";
    document.title=dados.clinica+(pageLabel?" - "+pageLabel:"")+" - Noeds";
  }
  function esc(s){return (s==null?"":(""+s)).replace(/[&<>"']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];});}

  // ---- classes do design (copiadas do markup original) ----
  var C={
    h2:"serif mt-6 text-[28px] leading-[1.1] tracking-tight sm:mt-8 sm:text-[32px] lg:text-[38px]",
    lead:"mt-4 max-w-2xl text-[15px] leading-[1.75] font-light text-muted-foreground sm:mt-5 sm:text-[16px] sm:leading-[1.8]",
    ul:"border-t border-border mt-8",
    li:"flex items-start gap-5 py-4 border-b border-border sm:gap-8 sm:py-5",
    num:"text-[10px] tracking-[0.32em] text-faint pt-1.5 w-6 shrink-0",
    liTxt:"text-[14px] leading-[1.75] font-light text-foreground/90 sm:text-[15px] sm:leading-[1.8]",
    eyebrow:"text-[10px] tracking-[0.32em] text-faint",
    para:"mt-5 text-[15px] leading-[1.8] font-light text-muted-foreground sm:text-[16px]",
    cardTitle:"serif text-[20px] leading-snug sm:text-[22px]",
    cardBody:"mt-3 text-[14px] leading-relaxed text-muted-foreground font-light"
  };
  function el(tag,cls,html){var e=document.createElement(tag); if(cls)e.className=cls; if(html!=null)e.innerHTML=html; return e;}
  function pad(i){return ("0"+(i+1)).slice(-2);}
  // lista numerada (ul/li) a partir de array de strings
  function numberedList(items){
    var ul=el("ul",C.ul);
    (items||[]).forEach(function(t,i){
      var li=el("li",C.li);
      li.appendChild(el("span",C.num,pad(i)));
      li.appendChild(el("p",C.liTxt,esc(t)));
      ul.appendChild(li);
    });
    return ul;
  }
  // bloco "eyebrow + título + corpo" (para cruzamentos, motores, pilares…)
  function block(eyebrow,title,body){
    var wrap=el("div","py-5 border-b border-border");
    if(eyebrow) wrap.appendChild(el("p",C.eyebrow,esc(eyebrow)));
    if(title) wrap.appendChild(el("p","serif mt-3 text-[18px] sm:text-[20px]",esc(title)));
    if(body) wrap.appendChild(el("p","mt-2 "+C.cardBody,esc(body)));
    return wrap;
  }
  // substitui o miolo de uma <section id> por novos nós (mantém o cabeçalho h2/lead se existir)
  function fillSection(id, builder){
    var sec=document.getElementById(id); if(!sec) return;
    // remove tudo após o parágrafo "lead" (mantém numeração, h2 e subtítulo)
    var keep=[]; var kids=[].slice.call(sec.children);
    var seenLead=false;
    for(var i=0;i<kids.length;i++){
      var k=kids[i], tag=k.tagName.toLowerCase();
      if(tag==="p"||tag==="h2"){ keep.push(k); if(tag==="p"&&/leading-\[1\.75\]/.test(k.className)) seenLead=true; }
      else break;
    }
    while(sec.children.length>keep.length) sec.removeChild(sec.lastChild);
    var frag=document.createDocumentFragment(); builder(frag);
    sec.appendChild(frag);
  }

  // ---- renderers por documento ----
  var R={
    diagnostico:function(d){
      // lista rótulo/texto (Resumo do Cliente, Indicadores, Metas) — formato do modelo
      function labeledRows(items, valKey, noteKey){
        var wrap=el("div","mt-8 border-t border-border");
        (items||[]).forEach(function(it){
          var row=el("div","flex flex-col gap-2 py-5 border-b border-border sm:flex-row sm:items-baseline sm:justify-between sm:gap-10");
          row.appendChild(el("p","text-[10px] tracking-[0.28em] text-faint uppercase sm:w-48 sm:shrink-0",esc(it.rotulo||"")));
          var rt=el("div","sm:flex-1");
          if(valKey&&it[valKey]) rt.appendChild(el("p","serif text-[18px] text-foreground",esc(it[valKey])));
          var body=it[noteKey!=null?noteKey:"texto"];
          if(body) rt.appendChild(el("p","text-[14px] leading-relaxed font-light text-muted-foreground"+(valKey&&it[valKey]?" mt-1":""),esc(body)));
          row.appendChild(rt); wrap.appendChild(row);
        });
        return wrap;
      }
      fillSection("resumo",function(f){
        f.appendChild(labeledRows(d.resumo_campos,null,"texto"));
      });
      fillSection("indicadores",function(f){
        f.appendChild(labeledRows(d.indicadores,"valor","nota"));
      });
      var motores=["motor-demanda","motor-conversao","motor-controle","motor-reativacao","motor-posicionamento","motor-indicacao","motor-prova-social"];
      (d.motores||[]).forEach(function(m,i){
        if(i<motores.length) fillSection(motores[i],function(f){
          f.appendChild(numberedList(m.itens||[]));
        });
      });
      fillSection("gargalo",function(f){ f.appendChild(numberedList(d.gargalo||[])); });
      fillSection("metas",function(f){
        f.appendChild(labeledRows(d.metas,null,"texto"));
        if(d.conclusao) f.appendChild(el("p",C.para+" mt-8",esc(d.conclusao)));
      });
    },
    swot:function(d){
      fillSection("forcas",function(f){ f.appendChild(numberedList(d.forcas)); });
      fillSection("fraquezas",function(f){ f.appendChild(numberedList(d.fraquezas)); });
      fillSection("oportunidades",function(f){ f.appendChild(numberedList(d.oportunidades)); });
      fillSection("ameacas",function(f){ f.appendChild(numberedList(d.ameacas)); });
      fillSection("cruzamentos",function(f){ (d.cruzamentos||[]).forEach(function(c){ f.appendChild(block(c.titulo,"",c.texto)); }); });
    },
    bcg:function(d){
      fillSection("portfolio",function(f){ if(d.portfolio) f.appendChild(el("p",C.para,esc(d.portfolio))); });
      [["estrela",d.estrela],["vaca",d.vaca],["interrogacao",d.interrogacao],["abacaxi",d.abacaxi]].forEach(function(p){
        fillSection(p[0],function(f){ var q=p[1]||{};
          if(q.nome) f.appendChild(el("p","mt-5 serif text-[20px]",esc(q.nome)));
          f.appendChild(numberedList(q.itens||[])); });
      });
      fillSection("alocacao",function(f){
        (d.alocacao||[]).forEach(function(a){ f.appendChild(block(a.rotulo,"",a.texto)); });
        if(d.conclusao) f.appendChild(el("p",C.para+" mt-8",esc(d.conclusao)));
      });
    },
    persona:function(d){
      fillSection("intro",function(f){ if(d.intro) f.appendChild(el("p",C.para,esc(d.intro))); });
      var ids=["persona-harmonizacao-facial","persona-estetica-avancada","persona-atendimento-geral"];
      (d.personas||[]).forEach(function(p,i){
        if(i<ids.length) fillSection(ids[i],function(f){
          if(p.titulo) f.appendChild(el("p","mt-5 serif text-[20px]",esc(p.titulo)));
          if(p.perfil) f.appendChild(el("p",C.para,esc(p.perfil)));
          if(p.dores&&p.dores.length){ f.appendChild(el("p",C.eyebrow+" mt-8","Dores")); f.appendChild(numberedList(p.dores)); }
          if(p.desejos&&p.desejos.length){ f.appendChild(el("p",C.eyebrow+" mt-8","Desejos")); f.appendChild(numberedList(p.desejos)); }
          if(p.objecoes&&p.objecoes.length){ f.appendChild(el("p",C.eyebrow+" mt-8","Medos e Objeções")); f.appendChild(numberedList(p.objecoes)); }
          if(p.gatilho) f.appendChild(el("p",C.para+" mt-6","<strong>Gatilho de decisão:</strong> "+esc(p.gatilho)));
        });
      });
      fillSection("motivos",function(f){ f.appendChild(numberedList(d.motivos)); });
    },
    marketing:function(d){
      fillSection("visao-geral",function(f){ if(d.visao_geral) f.appendChild(el("p",C.para,esc(d.visao_geral))); });
      var ids=["primeiros-38","metodologia-trafego","recuperacao-base","primeiros-90"];
      (d.blocos||[]).forEach(function(b,i){
        if(i<ids.length) fillSection(ids[i],function(f){
          if(b.titulo) f.appendChild(el("p","mt-5 serif text-[20px]",esc(b.titulo)));
          if(b.estrategia) f.appendChild(block("Estratégia","",b.estrategia));
          if(b.operacao) f.appendChild(block("Operação","",b.operacao));
          if(b.resultado) f.appendChild(block("Resultado Esperado","",b.resultado));
        });
      });
      fillSection("motores",function(f){ (d.motores||[]).forEach(function(m){ f.appendChild(block(m.rotulo,"",m.texto)); }); });
      fillSection("caminho-escala",function(f){ if(d.escala) f.appendChild(el("p",C.para,esc(d.escala))); });
    },
    conteudo:function(d){
      fillSection("porque",function(f){ if(d.porque) f.appendChild(el("p",C.para,esc(d.porque))); });
      fillSection("pilares",function(f){ (d.pilares||[]).forEach(function(p){
        f.appendChild(block((p.peso?p.peso+" · ":"")+p.nome,"",p.texto)); }); });
      fillSection("banco",function(f){
        var ul=el("div","mt-8 border-t border-border");
        (d.banco||[]).forEach(function(b,i){
          var row=el("div","py-5 border-b border-border");
          row.appendChild(el("p",C.eyebrow,("0"+(i+1)).slice(-2)+" · "+esc(b.tema||"")));
          if(b.gancho) row.appendChild(el("p","serif mt-3 text-[17px] text-foreground",esc(b.gancho)));
          if(b.desenvolvimento) row.appendChild(el("p","mt-2 "+C.cardBody,esc(b.desenvolvimento)));
          ul.appendChild(row);
        }); f.appendChild(ul);
      });
      fillSection("acao",function(f){ if(d.acao) f.appendChild(el("p",C.para,esc(d.acao))); });
    },
    playbook:function(d){
      fillSection("fundamentos",function(f){ f.appendChild(numberedList(d.fundamentos)); });
      fillSection("biblioteca",function(f){ (d.scripts||[]).forEach(function(s){ f.appendChild(block(s.situacao,"",s.mensagem)); }); });
      fillSection("objecoes-gerais",function(f){ (d.objecoes||[]).forEach(function(o){ f.appendChild(block(o.objecao,"",o.resposta)); }); });
    },
    certificado:function(d){
      fillSection("resumo",function(f){ if(d.resumo) f.appendChild(el("p",C.para,esc(d.resumo))); });
      fillSection("auditados",function(f){ f.appendChild(numberedList(d.auditados)); });
      fillSection("conformidade",function(f){ (d.conformidade||[]).forEach(function(c){ f.appendChild(block(c.area,"",c.escopo)); }); });
      fillSection("proximo",function(f){ if(d.proximo) f.appendChild(el("p",C.para,esc(d.proximo))); });
    }
  };

  // ---- 1) substitui placeholders globais ([Nome da Clínica] etc.) em TODA página ----
  var PH={
    "Nome da Clínica":dados.clinica, "Nome do Responsável":dados.responsavel,
    "Nome do responsável comercial":dados.responsavel, "Nicho da Clínica":dados.especialidade,
    "Cidade":dados.cidade, "Faturamento Atual":dados.faturamento, "Meta de Faturamento":dados.objetivo,
    "Principal Diferencial":dados.diferencial, "Principal Gargalo":dados.principal_dor
  };
  (function walk(node){
    if(node.nodeType===3){
      var t=node.nodeValue;
      if(t.indexOf("[")>=0){
        node.nodeValue=t.replace(/\[([^\]\[]{2,60})\]/g,function(m,key){
          for(var k in PH){ if(PH[k]&&new RegExp("^"+k,"i").test(key)) return PH[k]; }
          return m;
        });
      }
    } else if(node.nodeType===1 && !/SCRIPT|STYLE/.test(node.tagName)){
      for(var c=node.firstChild;c;c=c.nextSibling) walk(c);
    }
  })(document.body);

  // ---- 2) injeta o conteúdo do documento atual ----
  if(R[file] && docs[file]){ try{ R[file](docs[file]); }catch(e){ console.warn("render",file,e); } }

  // banner discreto indicando dossiê do cliente
  var b=document.createElement("div");
  b.style.cssText="position:fixed;bottom:0;left:0;right:0;z-index:50;background:var(--surface,#111);border-top:1px solid var(--border,#262626);padding:8px 16px 8px 72px;font-size:11px;letter-spacing:.1em;color:var(--muted-foreground,#aaa);display:flex;gap:14px;align-items:center;justify-content:space-between";
  b.innerHTML='<span>DOSSIÊ · '+esc(dados.clinica||"Cliente")+(trocouDeCliente?' · <span style="color:#e8a33d">esta aba mostrava outro cliente antes — confira se é o dossiê certo</span>':'')+'</span>';
  if(!shareToken){
    var x=document.createElement("button"); x.textContent="Sair do dossiê";
    x.style.cssText="background:none;border:1px solid var(--border,#333);color:inherit;padding:5px 12px;cursor:pointer;font-size:10px;letter-spacing:.2em;text-transform:uppercase";
    x.onclick=function(){ localStorage.removeItem("dossie_atual"); location.reload(); };
    b.appendChild(x);
  }
  document.body.appendChild(b);
})();
</script>
"""

TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="Consultoria estratégica proprietária Noeds.">
{theme_boot_js}
{fonts}
<style>{css}
{print_css}
{sidebar_css}</style>
</head>
<body>
{sidebar}
{body}
{enhance_js}
{sidebar_js}
{render_js}
</body>
</html>
"""

for slug, (outname, srcpath) in ROUTES.items():
    raw = srcpath.read_text(encoding="utf-8")
    body = relink(get_body(raw))
    doc = TEMPLATE.format(
        title=get_title(raw),
        theme_boot_js=THEME_BOOT_JS,
        fonts=FONTS_LINK,
        css=CSS,
        print_css=PRINT_CSS,
        sidebar_css=SIDEBAR_CSS,
        sidebar=sidebar_html(outname),
        body=body,
        enhance_js=ENHANCE_JS,
        sidebar_js=SIDEBAR_JS,
        render_js=RENDER_JS,
    )
    (OUT / outname).write_text(doc, encoding="utf-8")
    print(f"{outname:22s} <- {srcpath.name:18s} ({len(doc):>7d} B)")

# ---------------------------------------------------------------------------
# Páginas-app (Gerar + Banco de clientes) — geradas por gen_app.py
# ---------------------------------------------------------------------------
try:
    import gen_app
    gen_app.build(OUT, CSS, SIDEBAR_CSS, SIDEBAR_JS, sidebar_html, FONTS_LINK, PRINT_CSS, THEME_BOOT_JS)
    print("gerar.html / clientes.html   <- gen_app.py")
except Exception as e:
    print("aviso: páginas-app não geradas:", e)

# ---------------------------------------------------------------------------
# Formulário público do cliente (dossie.html) — gerado por gen_form.py.
# Página SEM sidebar: é o link que o cliente recebe (código MKT@2026).
# ---------------------------------------------------------------------------
def _page_public(title, body, extra_js="", extra_css=""):
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{FONTS_LINK}
<style>{CSS}
{extra_css}</style>
</head>
<body>
{body}
{extra_js}
</body>
</html>
"""

# Página dedicada do FORMULÁRIO — tema CLARO idêntico aos originais NOEDS.
# NÃO injeta o CSS dark do site (o extra_css do gen_form define seu próprio :root claro).
# Fontes: Instrument Serif (serif) + Work Sans (corpo) + JetBrains Mono (eyebrow).
FORM_FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" '
    'href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1'
    '&family=Work+Sans:wght@300;400;500;600'
    '&family=JetBrains+Mono:wght@400;500&display=swap">'
)

def _page_form(title, body, extra_js="", extra_css=""):
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
{FORM_FONTS}
<style>{extra_css}</style>
</head>
<body>
{body}
{extra_js}
</body>
</html>
"""

try:
    import gen_form
    gen_form.build(OUT, CSS, FORM_FONTS, _page_form)
    print("dossie.html                  <- gen_form.py (tema claro, 3 tipos)")
except Exception as e:
    print("aviso: formulário público não gerado:", e)

print("\nOK. Réplica gerada em", OUT)
