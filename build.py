#!/usr/bin/env python3
"""
Gerador da réplica estática fiel de noeds-architect-suite.lovable.app
Estratégia: usa o HTML server-rendered REAL de cada rota (já baixado via curl),
remove apenas o badge da plataforma Lovable e os scripts de hidratação,
religa os links internos para arquivos .html locais e inlina o CSS real.
Nada de conteúdo é inventado - markup e texto vêm da fonte original.
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

# Tema claro do dossiê (camada aditiva, vem DEPOIS do CSS original na cascata -
# mesma especificidade de seletor, então a ordem decide). Padrão é claro
# (:root:not([data-theme="dark"])); [data-theme="dark"] restaura a paleta
# escura original do design (era o :root fixo antes do toggle existir). O
# atributo data-theme é setado no <html> por um script anti-FOUC (ver
# THEME_BOOT_JS) que roda antes de qualquer paint, lendo a preferência salva
# no localStorage de CADA navegador (não é sincronizado entre pessoas).
#
# PDF/impressão ficam sempre claros de propósito, independente do tema da
# tela - não remover esses dois blocos ao mexer no tema.
CSS += """
:root:not([data-theme="dark"]) {
  --background:#ffffff; --foreground:#1a1a1a; --surface:#f7f6f3; --surface-2:#efeee9;
  --border:#e2e0d9; --muted-foreground:#5c5b56; --faint:#8f8d85;
  --color-background:#ffffff; --color-foreground:#1a1a1a; --color-border:#e2e0d9;
}
/* body nunca tem o atributo data-theme (só o <html> tem, ver THEME_BOOT_JS)
   - "body:not([data-theme=dark])" seria sempre verdadeiro mesmo no escuro
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
   tema escuro) - no claro isso é texto branco em fundo quase-branco, invisível
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
    # obs: id="lovable-badge" pode vir em outra linha/depois de outros atributos
    # dentro da tag <aside ...>, por isso o [^>]*? antes de procurar o id
    body = re.sub(r'<aside(?:(?!id=)[^>])*?id="lovable-badge".*?</aside>', "", body, flags=re.S)
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
# MELHORIAS (camada aditiva - não altera o markup/design original)
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

/* ---- visuais nível 5 (camada aditiva; renderizados só quando há dossiê gerado) ---- */
:root { --nd-ok:#5a9a6d; --nd-warn:#c98a3a; --nd-err:#c0473f; }
html[data-theme="dark"] { --nd-ok:#7bbf8a; --nd-warn:#c98a3a; --nd-err:#e0726a; }
/* título/rótulo em DESTAQUE nos cards e blocos gerados (Meta 6 meses, Estratégia,
   Dores, situações de script…) - cor plena + peso médio, vence o .text-faint do
   eyebrow original via !important */
.nd-lab { font-family:var(--font-sans) !important; font-size:11px !important; letter-spacing:.22em !important;
  text-transform:uppercase; color:var(--foreground) !important; font-weight:500 !important; }
/* KPIs (indicadores do diagnóstico) */
.nd-kpis { display:grid; grid-template-columns:repeat(3,1fr); gap:1px; background:var(--border); border:1px solid var(--border); margin-top:2rem; }
.nd-kpi { background:var(--surface); padding:1.25rem 1.4rem; }
.nd-kpi .k-label { font-family:var(--font-sans); font-size:11px; font-weight:500; letter-spacing:.22em; text-transform:uppercase; color:var(--foreground); min-height:2.6em; line-height:1.4; }
.nd-kpi .k-value { font-family:var(--font-serif); font-size:29px; line-height:1.1; margin-top:.45rem; letter-spacing:-.01em; }
.nd-kpi .k-note { font-size:11.5px; color:var(--muted-foreground); font-weight:300; margin-top:.55rem; line-height:1.5; }
.nd-chip { display:inline-block; font-family:var(--font-sans); font-size:9px; letter-spacing:.18em; text-transform:uppercase; color:var(--nd-warn); border:1px solid currentColor; padding:5px 10px; margin-top:.55rem; }
/* status por motor */
.nd-status-row { margin-top:1.4rem; display:flex; align-items:center; }
.nd-dot { display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--faint); }
.nd-dot.ok { background:var(--nd-ok); } .nd-dot.atencao { background:var(--nd-warn); } .nd-dot.critico { background:var(--nd-err); }
.nd-status-lbl { font-family:var(--font-sans); font-size:9px; letter-spacing:.24em; text-transform:uppercase; color:var(--muted-foreground); margin-left:9px; }
/* barra segmentada (alocação BCG / pesos dos pilares) */
.nd-bar { margin-top:2rem; }
.nd-bar .b-track { display:flex; height:10px; background:var(--surface-2); border:1px solid var(--border); }
.nd-bar .b-seg { height:100%; background:var(--foreground); }
.nd-bar .b-legend { display:flex; flex-wrap:wrap; gap:12px 22px; margin-top:12px; }
.nd-bar .b-item { font-family:var(--font-sans); font-size:10px; letter-spacing:.14em; text-transform:uppercase; color:var(--muted-foreground); display:flex; align-items:center; gap:7px; }
.nd-bar .b-swatch { width:9px; height:9px; display:inline-block; background:var(--foreground); }
/* bolha de chat (scripts do playbook) */
.nd-chat { margin-top:1.8rem; }
.nd-chat .c-tag { font-family:var(--font-sans); font-size:11px; font-weight:500; letter-spacing:.24em; text-transform:uppercase; color:var(--foreground); margin-bottom:10px; }
.nd-bubble { max-width:540px; background:var(--surface-2); border:1px solid var(--border); border-radius:14px 14px 14px 4px; padding:14px 18px; font-size:14px; line-height:1.7; font-weight:300; white-space:pre-line; }
.nd-copy { margin-top:9px; background:none; border:1px solid var(--border); color:var(--faint); font-family:var(--font-sans); font-size:9px; letter-spacing:.2em; text-transform:uppercase; padding:6px 13px; cursor:pointer; transition:color .2s, border-color .2s; }
.nd-copy:hover { color:var(--foreground); border-color:var(--foreground); }
/* par objeção -> resposta */
.nd-obj { margin-top:1.8rem; display:flex; flex-direction:column; }
.nd-obj .c-tag { font-family:var(--font-sans); font-size:11px; font-weight:500; letter-spacing:.24em; text-transform:uppercase; color:var(--foreground); margin-bottom:8px; }
.nd-obj .o-tag-r { align-self:flex-end; margin-top:12px; }
.nd-obj .o-cliente { align-self:flex-start; max-width:440px; background:var(--surface-2); border:1px solid var(--border); border-radius:14px 14px 14px 4px; padding:11px 16px; font-size:13.5px; font-weight:300; font-style:italic; color:var(--muted-foreground); }
.nd-obj .o-resposta { align-self:flex-end; max-width:540px; background:var(--foreground); color:var(--background); border-radius:14px 14px 4px 14px; padding:13px 18px; font-size:13.5px; line-height:1.65; font-weight:300; }
/* card de persona */
.nd-persona { border:1px solid var(--border); background:var(--surface); padding:1.75rem; margin-top:2rem; }
.nd-persona .p-head { display:flex; align-items:center; gap:16px; }
.nd-persona .p-mono { width:52px; height:52px; flex-shrink:0; border-radius:50%; border:1px solid var(--foreground); display:flex; align-items:center; justify-content:center; font-family:var(--font-serif); font-size:24px; }
.nd-persona .p-name { font-family:var(--font-serif); font-size:21px; line-height:1.2; }
.nd-persona .p-meta { font-family:var(--font-sans); font-size:10px; letter-spacing:.2em; text-transform:uppercase; color:var(--faint); margin-top:5px; }
.nd-persona .p-quote { font-family:var(--font-serif); font-style:italic; font-size:18px; margin-top:1.2rem; line-height:1.4; }
.nd-persona .p-perfil { font-size:13px; font-weight:300; color:var(--muted-foreground); margin-top:.9rem; line-height:1.7; }
.nd-persona .p-cols { display:grid; grid-template-columns:1fr 1fr; gap:1.4rem; margin-top:1.4rem; }
.nd-persona .p-col-t { font-family:var(--font-sans); font-size:11px; font-weight:500; letter-spacing:.24em; text-transform:uppercase; color:var(--foreground); margin-bottom:.4rem; }
.nd-persona .p-item { font-size:13px; font-weight:300; color:var(--muted-foreground); line-height:1.55; padding:7px 0; border-bottom:1px solid var(--border); }
.nd-persona .p-gatilho { margin-top:1.3rem; border-left:2px solid var(--foreground); padding-left:14px; font-size:13.5px; font-weight:300; line-height:1.65; }
/* checklist (auditados, operação, ação da semana) */
.nd-check { margin-top:1.4rem; border-top:1px solid var(--border); }
.nd-check .c-row { display:flex; gap:14px; align-items:baseline; padding:11px 0; border-bottom:1px solid var(--border); }
.nd-check .c-row p { font-size:14px; font-weight:300; line-height:1.65; }
.nd-check .c-mark { color:var(--nd-ok); font-size:13px; flex-shrink:0; }
/* linha do tempo (marketing) */
.nd-timeline { display:flex; margin-top:2.2rem; }
.nd-timeline .t-step { flex:1; position:relative; }
.nd-timeline .t-step::before { content:""; position:absolute; top:5px; left:16px; right:0; height:1px; background:var(--border); }
.nd-timeline .t-step:last-child::before { display:none; }
.nd-timeline .t-node { width:11px; height:11px; border-radius:50%; border:1px solid var(--foreground); background:var(--background); position:relative; z-index:1; }
.nd-timeline .t-step.t-fill .t-node { background:var(--foreground); }
.nd-timeline .t-label { font-family:var(--font-sans); font-size:10.5px; font-weight:500; letter-spacing:.2em; text-transform:uppercase; color:var(--foreground); margin-top:11px; }
.nd-timeline .t-name { font-family:var(--font-serif); font-size:15px; margin-top:4px; line-height:1.3; padding-right:10px; }
/* selo (certificado) - hierarquia: rótulo pequeno em cima, NOME DA EMPRESA em
   destaque no centro, assinatura da consultoria discreta embaixo. Sem data. */
.nd-selo { width:186px; height:186px; border-radius:50%; border:1px solid var(--foreground); box-shadow:0 0 0 1px var(--border), 0 0 0 7px var(--surface), 0 0 0 8px var(--border); display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; margin:2.8rem auto 0; padding:20px; }
.nd-selo .s-e { font-family:var(--font-sans); font-size:8px; letter-spacing:.3em; text-transform:uppercase; color:var(--faint); }
.nd-selo .s-empresa { font-family:var(--font-serif); font-size:18px; line-height:1.15; margin:9px 2px; font-weight:500; }
.nd-selo .s-rule { width:26px; height:1px; background:var(--border); margin:2px auto; }
.nd-selo .s-by { font-family:var(--font-sans); font-size:8.5px; letter-spacing:.24em; text-transform:uppercase; color:var(--muted-foreground); margin-top:4px; }
.nd-selo .s-n { font-family:var(--font-serif); font-size:20px; margin:7px 0; }
/* rótulo destacado (SWOT) */
.nd-rlab { font-family:var(--font-sans); font-size:11px; font-weight:500; letter-spacing:.22em; text-transform:uppercase; color:var(--foreground); }
.nd-rbody { margin-top:3px; }
/* grade de fatos rótulo+texto (resumo do cliente / metas do diagnóstico) */
.nd-facts { display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--border); border:1px solid var(--border); margin-top:2rem; }
.nd-fact { background:var(--surface); padding:1.35rem 1.5rem; }
.nd-fact .f-label { font-family:var(--font-sans); font-size:11px; font-weight:500; letter-spacing:.22em; text-transform:uppercase; color:var(--foreground); }
.nd-fact .f-text { font-size:13.5px; font-weight:300; line-height:1.7; margin-top:.65rem; color:var(--foreground); }
/* grade de ideias (banco de conteúdo) */
.nd-ideas { display:grid; grid-template-columns:1fr 1fr; gap:1px; background:var(--border); border:1px solid var(--border); margin-top:2rem; }
.nd-idea { background:var(--surface); padding:1.4rem 1.5rem; }
.nd-idea .i-top { display:flex; align-items:center; gap:8px; }
.nd-idea .i-num { font-family:var(--font-sans); font-size:10px; letter-spacing:.28em; color:var(--faint); }
.nd-tag { display:inline-block; font-family:var(--font-sans); font-size:8.5px; letter-spacing:.16em; text-transform:uppercase; color:var(--muted-foreground); border:1px solid var(--border); padding:4px 9px; }
.nd-idea .i-tema { font-family:var(--font-serif); font-size:17px; margin-top:.85rem; line-height:1.3; }
.nd-idea .i-gancho { font-style:italic; color:var(--muted-foreground); font-size:13.5px; margin-top:.6rem; font-weight:300; line-height:1.6; }
.nd-idea .i-dev { font-size:12.5px; color:var(--faint); margin-top:.6rem; font-weight:300; line-height:1.6; }
@media (max-width:640px){
  .nd-kpis { grid-template-columns:repeat(2,1fr); }
  .nd-ideas, .nd-facts, .nd-persona .p-cols { grid-template-columns:1fr; }
  .nd-timeline { flex-direction:column; gap:16px; }
  .nd-timeline .t-step::before { display:none; }
}
@media print {
  .nd-copy { display:none !important; }
  .nd-kpi, .nd-fact, .nd-persona, .nd-idea, .nd-bubble, .nd-obj .o-cliente { background:#fff !important; color:#000 !important; border-color:#ccc !important; }
  .nd-obj .o-resposta { background:#fff !important; color:#000 !important; border:1px solid #999 !important; }
  .nd-bar .b-seg, .nd-bar .b-swatch { background:#000 !important; }
  .nd-selo, .nd-timeline .t-node, .nd-persona .p-mono { border-color:#000 !important; }
}
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
  // - só o fork -pro suporta. jsPDF monta o PDF a partir do canvas
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
      +'<div><div class="s-tag" style="color:#cfcfcf">Forças</div><div class="s-body">Internas · positivas: o que já funciona e diferencia.</div></div>'
      +'<div><div class="s-tag" style="color:#cfcfcf">Fraquezas</div><div class="s-body">Internas · negativas: o que trava o crescimento.</div></div>'
      +'<div><div class="s-tag" style="color:#cfcfcf">Oportunidades</div><div class="s-body">Externas · positivas: o que pode ser aproveitado.</div></div>'
      +'<div><div class="s-tag" style="color:#cfcfcf">Ameaças</div><div class="s-body">Externas · negativas: o que precisa ser observado.</div></div>'
      +'</div>';
    swotFirst.appendChild(grid);
  }
})();
</script>
"""

# script anti-FOUC (Flash Of Unstyled Content): roda ANTES de qualquer CSS
# ser parseado, lendo a preferência de tema salva no localStorage deste
# navegador e já setando o atributo no <html> - sem isso, a página sempre
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
# botão de tema: elemento PRÓPRIO, fora de #ng-side de propósito - a regra
# acima esconde a sidebar inteira no modo "?share=" (link do cliente final),
# mas o toggle precisa continuar visível ali (é o cenário mais provável de
# alguém sem contexto do painel querer trocar de tema).
#
# Posição: canto SUPERIOR DIREITO (right:18px), longe do menu hambúrguer que
# fica à esquerda (left:18px) - assim nunca sobrepõe o menu, aberto ou fechado,
# durante scroll (é position:fixed). Nas páginas do DOSSIÊ (link do cliente) o
# topo-direito está livre, então o toggle ocupa right:18px. No PAINEL
# (.app-panel: gerar/clientes) o topo-direito tem até 5 botões de conta
# (.auth-logout, top:18px), então lá o toggle desce para top:64px pra não
# colidir. Detecta o painel pela classe .app-panel no <body>.
#
# Formato: switch de 2 zonas fixas (não é mais um botão único que alterna) -
# lua (premium/preto) na ponta esquerda, sol (creme) na direita, SEM texto
# (só ícone), com uma bolinha (thumb) que desliza para o lado escolhido.
# Clicar em qualquer ponta seleciona aquele tema diretamente (não faz toggle
# relativo ao estado atual).
SIDEBAR_CSS += """
#ng-theme-toggle { position:fixed; top:18px; right:18px; left:auto; z-index:60;
  display:flex; align-items:center; width:84px; height:42px; padding:0 4px;
  border-radius:21px; background:var(--surface,#111); border:1px solid var(--border,#262626);
  cursor:pointer; transition:border-color .25s; }
/* no painel (gerar/clientes) os botões de conta ocupam o topo-direito -
   desce o toggle pra linha de baixo, mantendo-o à direita e fora do menu. */
body.app-panel #ng-theme-toggle { top:64px; right:18px; }
#ng-theme-toggle:hover { border-color:var(--foreground,#fff); }
#ng-theme-toggle .ng-tt-lbl { flex:1; display:flex; align-items:center; justify-content:center;
  font-size:15px; line-height:1; color:var(--faint,#666); position:relative; z-index:2;
  transition:color .25s; background:none; border:none; padding:12px 0; cursor:pointer; }
#ng-theme-toggle .ng-tt-thumb { position:absolute; top:3px; left:3px; width:38px; height:34px;
  border-radius:17px; background:var(--foreground,#fff); z-index:1;
  transition:transform .28s cubic-bezier(.4,0,.2,1); }
#ng-theme-toggle[data-active="dark"] .ng-tt-lbl.ng-tt-dark,
#ng-theme-toggle[data-active="light"] .ng-tt-lbl.ng-tt-light { color:var(--background,#000); }
#ng-theme-toggle[data-active="light"] .ng-tt-thumb { transform:translateX(38px); }
@media (max-width:640px){
  /* telas estreitas: garante que o toggle não encoste na borda nem no menu */
  #ng-theme-toggle { top:14px; right:14px; }
  body.app-panel #ng-theme-toggle { top:60px; right:14px; }
}
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
        '<div id="ng-theme-toggle" role="radiogroup" aria-label="Tema do painel" data-active="dark">'
        '<div class="ng-tt-thumb"></div>'
        '<button type="button" class="ng-tt-lbl ng-tt-dark" data-theme-choice="dark" role="radio" aria-label="Tema Preto (premium)">&#9789;</button>'
        '<button type="button" class="ng-tt-lbl ng-tt-light" data-theme-choice="light" role="radio" aria-label="Tema Creme">&#9788;</button>'
        '</div>'
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
    // propaga o token em QUALQUER link interno pra outra página do dossiê -
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
  // aplicável - aqui só sincroniza a posição do switch e liga os cliques.
  // Switch de 2 zonas fixas: cada botão (Preto/Creme) seleciona aquele tema
  // diretamente, não alterna relativo ao estado atual (diferente do ícone
  // único de antes).
  var THEME_KEY='noeds_theme';
  var wrapT=document.getElementById('ng-theme-toggle');
  function aplicarTema(t){
    if(t==='dark') document.documentElement.setAttribute('data-theme','dark');
    else document.documentElement.removeAttribute('data-theme');
    if(wrapT) wrapT.setAttribute('data-active', t);
  }
  aplicarTema(localStorage.getItem(THEME_KEY)==='dark' ? 'dark' : 'light');
  if(wrapT) wrapT.querySelectorAll('[data-theme-choice]').forEach(function(b){
    b.addEventListener('click', function(){
      var novo = b.getAttribute('data-theme-choice');
      try{ localStorage.setItem(THEME_KEY, novo); }catch(e){}
      aplicarTema(novo);
    });
  });
})();
</script>
"""

# ---------------------------------------------------------------------------
# RENDER_JS - injeta o conteúdo do cliente (localStorage.dossie_atual) nas 9 páginas.
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
  // SKELETON: no link do cliente (?share=), o conteúdo real chega só depois do
  // fetch. Sem isso, o cliente veria por 1-3s o template com placeholders crus
  // ([Nome da Clínica], [nome]...) piscando antes da neutralização. Cobre a tela
  // com um overlay de carregamento até o render terminar (removido no finally).
  var skel=null;
  if(shareToken){
    skel=document.createElement("div");
    skel.id="ng-skeleton";
    skel.style.cssText="position:fixed;inset:0;z-index:9998;background:var(--background,#000);display:flex;align-items:center;justify-content:center";
    skel.innerHTML='<div style="width:26px;height:26px;border:2px solid var(--faint,#666);border-top-color:transparent;border-radius:50%;animation:ngspin .8s linear infinite"></div><style>@keyframes ngspin{to{transform:rotate(360deg)}}</style>';
    (document.body||document.documentElement).appendChild(skel);
  }
  var removerSkeleton=function(){ if(skel&&skel.parentNode){ skel.parentNode.removeChild(skel); skel=null; } };
  // rede de segurança: se algo travar antes do render terminar, não deixa o
  // cliente preso no spinner pra sempre - remove após 8s no pior caso.
  if(shareToken){ setTimeout(removerSkeleton, 8000); }
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
  // dela - mostra um aviso em vez de silenciosamente trocar de cliente.
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
  // eyebrow ganha .nd-lab (título em destaque, pedido do usuário)
  function block(eyebrow,title,body){
    var wrap=el("div","py-5 border-b border-border");
    if(eyebrow) wrap.appendChild(el("p",C.eyebrow+" nd-lab",esc(eyebrow)));
    if(title) wrap.appendChild(el("p","serif mt-3 text-[18px] sm:text-[20px]",esc(title)));
    if(body) wrap.appendChild(el("p","mt-2 "+C.cardBody,esc(body)));
    return wrap;
  }

  // ---- helpers visuais nível 5 (classes .nd-* definidas no CSS aditivo) ----
  // grade de KPIs; valor vazio/placeholder vira chip "Não informado"
  function statTiles(items){
    var wrap=el("div","nd-kpis");
    (items||[]).forEach(function(it){
      var t=el("div","nd-kpi");
      t.appendChild(el("p","k-label",esc(it.rotulo||"")));
      var v=(it.valor==null?"":""+it.valor).trim();
      if(!v || /^(n[aã]o informado|ponto a confirmar|a confirmar|-)$/i.test(v)) t.appendChild(el("span","nd-chip","Não informado"));
      else t.appendChild(el("p","k-value",esc(v)));
      if(it.nota) t.appendChild(el("p","k-note",esc(it.nota)));
      wrap.appendChild(t);
    });
    return wrap;
  }
  function pctFrom(s){ var m=/(\d{1,3})\s*%/.exec(s||""); return m?+m[1]:null; }
  // barra segmentada (tons de foreground com opacidade decrescente) + legenda
  function allocBar(segs){
    var ops=[".95",".6",".35",".18",".1"];
    var tot=segs.reduce(function(a,s){return a+(s.pct||0);},0)||100;
    var wrap=el("div","nd-bar"), track=el("div","b-track"), leg=el("div","b-legend");
    segs.forEach(function(s,i){
      var seg=el("div","b-seg"); seg.style.width=(100*(s.pct||0)/tot)+"%"; seg.style.opacity=ops[i]||".1";
      track.appendChild(seg);
      var it=el("span","b-item"); var sw=el("span","b-swatch"); sw.style.opacity=ops[i]||".1";
      it.appendChild(sw); it.appendChild(document.createTextNode((s.pct!=null?s.pct+"% · ":"")+(s.nome||"")));
      leg.appendChild(it);
    });
    wrap.appendChild(track); wrap.appendChild(leg); return wrap;
  }
  // status do motor (ok/atencao/critico) -> ponto colorido + rótulo
  function statusRow(st){
    var s=(""+(st||"")).toLowerCase(), n="";
    if(s.indexOf("crit")>=0) n="critico"; else if(s.indexOf("aten")>=0) n="atencao";
    else if(s.indexOf("ok")>=0||s.indexOf("saud")>=0) n="ok";
    if(!n) return null;
    var p=el("p","nd-status-row");
    p.innerHTML='<span class="nd-dot '+n+'"></span><span class="nd-status-lbl">'+({ok:"Saudável",atencao:"Atenção",critico:"Crítico"})[n]+"</span>";
    return p;
  }
  // bolha de chat com botão copiar (scripts prontos do playbook)
  function chatBubble(situacao,msg){
    var w=el("div","nd-chat");
    if(situacao) w.appendChild(el("p","c-tag",esc(situacao)));
    w.appendChild(el("div","nd-bubble",esc(msg||"")));
    var b=el("button","nd-copy","Copiar"); b.type="button";
    b.addEventListener("click",function(){
      var texto=msg||""; // preserva acentos e quebras de linha (writeText é fiel)
      var ok=function(){ b.textContent="Copiado ✓"; b.setAttribute("aria-live","polite");
        b.title="Conteúdo copiado com sucesso."; setTimeout(function(){b.textContent="Copiar"; b.title="";},1800); };
      var falhou=function(){ b.textContent="Não foi possível copiar"; b.title="Não foi possível copiar. Selecione o texto e copie manualmente.";
        setTimeout(function(){b.textContent="Copiar"; b.title="";},2600); };
      // fallback p/ navegador sem Clipboard API (ou http): usa execCommand.
      var fallback=function(){
        try{ var ta=document.createElement("textarea"); ta.value=texto;
          ta.style.cssText="position:fixed;top:-9999px;left:-9999px"; document.body.appendChild(ta);
          ta.focus(); ta.select(); var okc=document.execCommand("copy"); document.body.removeChild(ta);
          okc?ok():falhou();
        }catch(e){ falhou(); }
      };
      if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(texto).then(ok,fallback); }
      else fallback();
    });
    w.appendChild(b); return w;
  }
  // par "cliente diz -> você responde" (objeções)
  function objPair(o){
    var w=el("div","nd-obj");
    w.appendChild(el("p","c-tag","Cliente diz"));
    w.appendChild(el("div","o-cliente","“"+esc(o.objecao||"")+"”"));
    w.appendChild(el("p","c-tag o-tag-r","Você responde"));
    w.appendChild(el("div","o-resposta",esc(o.resposta||"")));
    return w;
  }
  // card de persona: monograma + meta + citação + colunas dores/desejos/objeções
  // monta um texto legível da persona (pra copiar)
  function personaTexto(p){
    var L=[];
    if(p.titulo) L.push(p.titulo);
    if(p.servico) L.push("Serviço: "+p.servico);
    if(p.frase) L.push("\""+p.frase+"\"");
    if(p.perfil) L.push("\nPerfil: "+p.perfil);
    function bloco(t,arr){ if(arr&&arr.length){ L.push("\n"+t+":"); arr.forEach(function(x){ L.push("- "+x); }); } }
    bloco("Dores",p.dores); bloco("Desejos",p.desejos); bloco("Medos e objeções",p.objecoes);
    if(p.gatilho) L.push("\nGatilho de decisão: "+p.gatilho);
    return L.join("\n");
  }
  function personaCard(p){
    var card=el("div","nd-persona");
    var head=el("div","p-head");
    head.appendChild(el("div","p-mono",esc(((p.titulo||"?").trim().charAt(0)||"?").toUpperCase())));
    var ht=el("div","");
    ht.appendChild(el("p","p-name",esc(p.titulo||"")));
    if(p.servico) ht.appendChild(el("p","p-meta",esc(p.servico)));
    head.appendChild(ht);
    // botão copiar persona (paridade com o template estático, que tinha
    // "Copiar persona" mas sem handler; aqui já vem funcional).
    var cp=el("button","nd-copy","Copiar persona"); cp.type="button"; cp.setAttribute("aria-label","Copiar persona");
    cp.style.cssText="margin-left:auto";
    cp.addEventListener("click",function(){
      var texto=personaTexto(p);
      var ok=function(){ cp.textContent="Copiado ✓"; cp.title="Conteúdo copiado com sucesso."; setTimeout(function(){cp.textContent="Copiar persona"; cp.title="";},1800); };
      var falhou=function(){ cp.textContent="Não foi possível copiar"; cp.title="Selecione o texto e copie manualmente."; setTimeout(function(){cp.textContent="Copiar persona"; cp.title="";},2600); };
      var fallback=function(){ try{ var ta=document.createElement("textarea"); ta.value=texto; ta.style.cssText="position:fixed;top:-9999px"; document.body.appendChild(ta); ta.focus(); ta.select(); var okc=document.execCommand("copy"); document.body.removeChild(ta); okc?ok():falhou(); }catch(e){ falhou(); } };
      if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(texto).then(ok,fallback); } else fallback();
    });
    head.appendChild(cp);
    card.appendChild(head);
    if(p.frase) card.appendChild(el("p","p-quote","“"+esc(p.frase)+"”"));
    if(p.perfil) card.appendChild(el("p","p-perfil",esc(p.perfil)));
    var cols=el("div","p-cols");
    function col(title,items){ var c=el("div",""); c.appendChild(el("p","p-col-t",title));
      (items||[]).forEach(function(t){ c.appendChild(el("p","p-item",esc(t))); }); return c; }
    if(p.dores&&p.dores.length) cols.appendChild(col("Dores",p.dores));
    if(p.desejos&&p.desejos.length) cols.appendChild(col("Desejos",p.desejos));
    if(p.objecoes&&p.objecoes.length) cols.appendChild(col("Medos e objeções",p.objecoes));
    card.appendChild(cols);
    if(p.gatilho) card.appendChild(el("p","p-gatilho","<strong>Gatilho de decisão:</strong> "+esc(p.gatilho)));
    return card;
  }
  // checklist com ✓ (auditados, passos de operação, ação da semana)
  function checkList(items){
    var w=el("div","nd-check");
    (items||[]).forEach(function(t){
      var r=el("div","c-row"); r.appendChild(el("span","c-mark","✓")); r.appendChild(el("p","",esc(t)));
      w.appendChild(r);
    });
    return w;
  }
  // linha do tempo horizontal (fases do plano de marketing)
  function timeLine(steps){
    var w=el("div","nd-timeline");
    steps.forEach(function(s,i){
      var st=el("div","t-step"+(i===0?" t-fill":""));
      st.appendChild(el("div","t-node"));
      st.appendChild(el("p","t-label",esc(s.label||"Fase "+(i+1))));
      if(s.name) st.appendChild(el("p","t-name",esc(s.name)));
      w.appendChild(st);
    });
    return w;
  }
  // lista numerada com rótulo destacado ("Rótulo: explicação" -> 2 linhas)
  function labeledList(items){
    var ul=el("ul",C.ul);
    (items||[]).forEach(function(t,i){
      var li=el("li",C.li);
      li.appendChild(el("span",C.num,pad(i)));
      var box=el("div",""), ix=(t||"").indexOf(":");
      if(ix>2&&ix<70){
        box.appendChild(el("p","nd-rlab",esc(t.slice(0,ix))));
        box.appendChild(el("p",C.liTxt+" nd-rbody",esc(t.slice(ix+1).trim())));
      } else box.appendChild(el("p",C.liTxt,esc(t)));
      li.appendChild(box); ul.appendChild(li);
    });
    return ul;
  }
  // divide um parágrafo em frases (p/ virar checklist quando houver 2+)
  function frases(s){
    return ((""+(s||"")).match(/[^.!?]+[.!?]*/g)||[]).map(function(x){return x.trim();}).filter(Boolean);
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

  // ---- JORNADA BASE (Playbook) ----
  // Espinha dorsal da venda: 6 transições fixas, iguais para todo procedimento.
  // Verbatim do modelo padrão-ouro (playbook-premium). Personalizada por
  // procedimento via os placeholders {FOCO} {ESPECIALISTA} {PRE_QUALIFICA}
  // {VALOR}, substituídos pelos valores de p.foco na renderização.
  var JORNADA_BASE=[
    { n:"01", etapa:"Saudação & Rapport", gatilho:"Reciprocidade + Prova de atenção",
      conversao:"Tirar o lead do frio e ganhar a primeira resposta. Quem responde nos primeiros 5 minutos converte até 3x mais. O objetivo aqui não é vender, é abrir conversa.",
      tecnica:"Resposta relâmpago + espelhamento + primeiro micro-sim. Use o nome, devolva a palavra que a pessoa usou, e faça uma pergunta tão fácil que é quase impossível não responder.",
      passos:[
        {p:"Responda em até 5 min, sempre pelo nome. Velocidade é o gatilho que ela nem percebe, mas sente.",g:"Resposta rápida"},
        {p:"Apresente-se com nome e vínculo ao profissional: \"Me chamo [seu nome] e faço parte da equipe de atendimento do [profissional], muito prazer!\". Humaniza e dá autoridade de uma vez.",g:"Apresentação humana"},
        {p:"Se ainda não tem o nome da pessoa, peça com gentileza antes de seguir: \"Poderia me informar seu nome?\". Tratar pelo nome muda o tom da conversa inteira.",g:"Personalização"},
        {p:"Espelhe o que ela buscou: repita a palavra dela (\"Vi que você quer {FOCO}…\"). Ela sente que foi ouvida.",g:"Espelhamento"},
        {p:"Faça uma pergunta aberta e leve, sem compromisso. O 1º sim pequeno abre o caminho para o sim grande.",g:"Micro-compromisso"}
      ],
      script:"Oi! Que bom te receber aqui 😊 Me chamo [seu nome] e faço parte da equipe de atendimento do [profissional], muito prazer! Vi que você se interessou por {FOCO}. Antes de qualquer coisa, me conta rapidinho: o que fez você buscar isso agora?",
      ponte:"Que bom que você falou isso, é mais comum do que parece e tem solução. Deixa eu te entender em 30 segundos pra já te indicar o melhor caminho, pode ser?",
      sinalVerde:"A pessoa respondeu e contou o motivo → avance para a pré-qualificação.",
      seSilencio:"Sem resposta em 1 a 2h: \"Oi, só pra garantir que minha mensagem chegou 🙂 quando puder, me conta como posso te ajudar.\" (sem cobrar)." },
    { n:"02", etapa:"Pré-Qualificação + Amplificação", gatilho:"Compromisso & Coerência + Aversão à perda",
      conversao:"Esta é a etapa que decide o agendamento. Não basta a dor: o lead precisa sentir a CONSEQUÊNCIA de não resolver. É aqui que 30% vira 50%. Faça a pessoa verbalizar o problema E o que perde se continuar parada.",
      tecnica:"Pergunta que faz admitir a dor, depois a pergunta de consequência (a que ninguém faz). Quem diz em voz alta o que está perdendo, se move. Uma pergunta de cada vez.",
      passos:[
        {p:"Pergunta de dor: {PRE_QUALIFICA} Deixe a pessoa responder antes de seguir.",g:"Admissão da dor"},
        {p:"Pergunta de intensidade: \"Numa escala de 0 a 10, o quanto isso te incomoda hoje?\" O número compromete.",g:"Compromisso"},
        {p:"Pergunta de consequência (a chave): \"E se continuar assim mais uns meses, o que te preocupa que possa acontecer?\" Ela mesma cria a urgência.",g:"Urgência gerada por ela"}
      ],
      script:"{PRE_QUALIFICA} E numa escala de 0 a 10, o quanto isso te incomoda no dia a dia? … Entendi. E se ficar assim mais um tempo, o que mais te preocupa?",
      ponte:"Faz total sentido querer resolver. Isso tem solução, e mais simples do que você imagina. Pra eu te dar a resposta certa (e não um chute), o ideal é {ESPECIALISTA} te ver de pertinho. É rápido e sem compromisso. Posso já garantir um horário pra você?",
      sinalVerde:"Deu uma nota alta ou falou de uma consequência que teme → está pronta. Vá direto ao horário.",
      seSilencio:"Se travar na consequência, não force: \"Sem pressão 🙂 só de você ter percebido isso já é meio caminho. Quando quiser, a avaliação te dá clareza total.\"" },
    { n:"03", etapa:"Agendamento (fechar o horário)", gatilho:"Prova social + Escassez real + Autoridade",
      conversao:"Transformar o desejo em um horário marcado e confirmado. O erro clássico é perguntar \"que dia você quer?\" (pergunta aberta esfria). Aqui você assume o controle com gentileza e prova social.",
      tecnica:"Prova social rápida → escassez verdadeira de agenda → escolha fechada (A ou B, nunca aberta) → confirmação ativa (a pessoa digita os dados, vira compromisso).",
      passos:[
        {p:"Prova social curta: \"Atendemos muita gente com esse mesmo caso, você vai estar em boas mãos.\" Reduz o medo de decidir.",g:"Prova social"},
        {p:"Escassez real: ofereça só os horários que existem de verdade. \"Essa semana consigo dois encaixes com {ESPECIALISTA}.\" Agenda cheia = valor.",g:"Escassez"},
        {p:"Escolha fechada: proponha dois horários específicos e pergunte qual fica melhor. A pessoa escolhe entre ir e ir, não entre ir e não ir.",g:"Escolha fechada"},
        {p:"Confirmação ativa: peça nome completo e WhatsApp AGORA. Quem digita os próprios dados assume o compromisso.",g:"Micro-investimento"},
        {p:"Já prometa a confirmação: \"Um dia antes eu te mando uma mensagem pra confirmar direitinho, tá? 😊\". A pessoa passa a esperar o contato, e o anti-falta começa aqui.",g:"Semente anti-falta"}
      ],
      script:"Olha, a gente atende muita gente com esse mesmo caso, você vai estar em ótimas mãos 🙌 Essa semana eu consigo te encaixar com {ESPECIALISTA}. Qual fica melhor pra você, um horário no começo ou no fim da semana?",
      ponte:"Fechado! 🎉 Já tô reservando esse horário no seu nome. Me confirma seu nome completo e o melhor WhatsApp pra eu te enviar o endereço e os detalhes? Ah, e um dia antes eu te mando uma mensagem pra confirmar direitinho, combinado? 😊",
      sinalVerde:"Escolheu o horário e mandou os dados → agendamento real. Siga para o anti-falta.",
      seSilencio:"Hesitou no horário: \"Sem problema! Esses encaixes costumam sair rápido. Qual chega mais perto de funcionar pra você que eu já tento segurar?\"" },
    { n:"04", etapa:"Anti-Falta (garantir o comparecimento)", gatilho:"Compromisso assumido + Cuidado + Valor a perder",
      conversao:"Aqui mora o vazamento de 40% de no-show. Lembrete passivo não basta. São 3 toques que pedem RESPOSTA ativa, reforçam o que a pessoa ganha (e perde) e criam um micro-investimento antes da consulta.",
      tecnica:"Confirmação ativa (a pessoa responde, não só recebe) + reforço do valor + micro-tarefa de preparo. Quem se prepara para algo, comparece. Tom de cuidado, nunca de cobrança.",
      passos:[
        {p:"Logo após agendar: reforce a decisão e peça um \"confirmado 👍\" de volta. Resposta ativa cria compromisso.",g:"Compromisso ativo"},
        {p:"Na véspera: lembre o valor que a pessoa vai receber, não só a hora. \"Amanhã {ESPECIALISTA} vai poder te dar a resposta exata que você queria.\"",g:"Reforço de valor"},
        {p:"Micro-investimento: peça algo simples (\"anota suas dúvidas pra trazer\"). Quem investe, aparece.",g:"Micro-investimento"},
        {p:"Tire os atritos do dia: mande o endereço com referência e oriente o que levar. Logística resolvida = menos desistência.",g:"Atrito zero"},
        {p:"2h antes: mensagem curta e calorosa, com endereço/link. Reduz a desistência de última hora.",g:"Cuidado"}
      ],
      script:"Oi! 💚 Tá tudo certo pra te receber no seu horário. {ESPECIALISTA} já vai poder te dar a resposta exata sobre {FOCO}, é a parte que você queria resolver. Me confirma com um 👍 que tá de pé?",
      ponte:"Combinado! 🙌 Te mando o endereço aqui, é bem fácil de chegar. Anota qualquer dúvida pra trazer. Qualquer imprevisto me avisa que a gente reagenda, mas vou contar com você 😊",
      sinalVerde:"Confirmou ativamente e/ou fez a micro-tarefa → comparecimento quase garantido.",
      seSilencio:"Sem confirmação na véspera: ligue (não só mensagem). \"Oi, passando pra confirmar pessoalmente e ver se ficou alguma dúvida antes de amanhã 🙂\"" },
    { n:"05", etapa:"Venda (na avaliação presencial)", gatilho:"Recapitulação + Ancoragem + Redução de risco + Futuro positivo",
      conversao:"Para subir a conversão: recapitule a dor DELA com as palavras dela, ancore o custo de não agir, mostre o valor antes do preço, tire o risco e feche por escolha (não por sim/não).",
      tecnica:"Recap da dor → custo de não resolver → ancoragem (o caro é não tratar) → valor e condições → reduzir risco → fechamento por escolha. Nunca pergunte \"quer fazer?\". Pergunte \"começamos por A ou B?\".",
      passos:[
        {p:"Recapitule com as palavras dela: \"Você me disse que {FOCO} te incomoda e te preocupa por X. Confere?\" Ela diz sim e revive a dor.",g:"Recapitulação"},
        {p:"Ancore no custo de não agir: \"Esperar tende a piorar e encarecer.\" O caro vira NÃO tratar, não o tratamento.",g:"Ancoragem na perda"},
        {p:"Apresente o valor e SÓ DEPOIS o preço, já com condições: \"{VALOR}, e a gente parcela do jeito que cabe pra você.\"",g:"Valor antes do preço"},
        {p:"Reduza o risco: avaliação sem compromisso, planejamento explicado, acompanhamento. Tirar o medo destrava o sim.",g:"Redução de risco"},
        {p:"Feche por escolha: \"Começamos já pela primeira etapa hoje ou prefere deixar agendado pra semana que vem?\" Decisão entre dois sins.",g:"Fechamento por escolha"}
      ],
      script:"Então, pelo que você mesma me contou, {FOCO} te incomoda e te preocupa, e isso tende a piorar (e ficar mais caro) se a gente esperar. A boa notícia é que dá pra resolver, e {ESPECIALISTA} já planejou tudo pro seu caso. Antes do valor, deixa eu te mostrar o que está incluído: o planejamento completo, o acompanhamento em cada etapa e uma equipe que cuida de você do início ao fim. Tudo isso fica em {VALOR}, que a gente parcela do jeito que cabe no seu orçamento.",
      ponte:"O que faz mais sentido pra você: a gente já começa pela primeira etapa hoje, ou prefere que eu deixe agendado pra semana que vem? 😊",
      sinalVerde:"Pergunta sobre parcelar, prazo ou \"como funciona depois\" → é compra. Feche por escolha agora.",
      seSilencio:"Se travar no \"vou pensar\": \"Claro! Só me diz o que mais pesa: o valor, o tempo ou alguma dúvida? Quase sempre é algo que eu resolvo aqui em 2 minutos.\"" },
    { n:"06", etapa:"Indicação (pós-fechamento)", gatilho:"Reciprocidade + Prova social",
      conversao:"Cada cliente satisfeita pode virar 1 a 2 leads quentes e gratuitos. O momento certo é o pico de emoção: logo após o sim ou após o resultado. Quem foi bem cuidado quer retribuir.",
      tecnica:"Peça no auge da satisfação e facilite ao máximo o ato. \"Manda meu número\" converte mais que \"indica a gente\", porque tira o trabalho da pessoa.",
      passos:[
        {p:"Espere o pico: logo após o sim ou ao ver o resultado. Emoção alta = generosidade alta.",g:"Timing"},
        {p:"Peça com leveza e elogio sincero, nunca como cobrança.",g:"Reciprocidade"},
        {p:"Facilite o ato: ofereça mandar o seu número pra pessoa, em vez de pedir o contato dela.",g:"Atrito zero"}
      ],
      script:"Fico muito feliz que você confiou na gente! 💚 Tenho certeza que você conhece alguém que também merece esse cuidado. Se quiser, me passa o contato ou manda o meu número, e eu cuido dessa pessoa com o mesmo carinho que cuidei de você.",
      ponte:"Combinado? Qualquer amigo ou familiar seu já entra com prioridade na minha agenda 😊",
      sinalVerde:"Mandou um contato ou disse \"vou indicar sim\" → registre e acompanhe esse novo lead como quente.",
      seSilencio:"Sem indicação na hora, tudo bem: plante a semente. \"Quando lembrar de alguém, é só mandar pra mim 💚\" e siga no pós-venda." }
  ];
  function aplicaFoco(txt,foco){ if(!txt) return ""; foco=foco||{};
    var s=(""+txt).replace(/\{(FOCO|PRE_QUALIFICA|ESPECIALISTA|VALOR)\}/g,function(m,k){ return foco[k]||""; });
    // A JORNADA_BASE (fixa) traz dois marcadores que NÃO vêm da IA:
    // - [profissional]: o profissional/especialista da clínica -> usa o ESPECIALISTA
    //   real, mas sem artigo (o texto já tem "do ...": "equipe de atendimento do
    //   [profissional]" viraria "...do o Dr. Aramis"). Remove artigo inicial.
    // - [seu nome]: é o nome da PRÓPRIA atendente, que não temos. Vira uma dica
    //   entre parênteses "(seu nome)" - some do alvo da neutralização (que só
    //   apaga colchetes) e o script fica com um campo claro pra ela preencher.
    var esp=(foco.ESPECIALISTA||"").replace(/^\s*(o|a|os|as)\s+/i,"").trim();
    s=s.replace(/\[profissional\]/gi, esp||"(nome do profissional)");
    s=s.replace(/\[seu nome\]/gi,"(seu nome)");
    return s; }

  // ======================================================================
  // ARQUITETURA 80/20: templates FIXOS nível-5 + costura de campos curtos.
  // O corpo analítico dos documentos vive aqui como texto fixo (escrito uma
  // vez, neutro, alto padrão), com marcadores {slot} que aplicaCampos()
  // substitui pelos poucos valores objetivos (do formulário) e interpretativos
  // (curtos, da IA). Reduz alucinação: a IA nunca escreve parágrafo inteiro.
  // ======================================================================
  // dados objetivos vindos do FORMULÁRIO (não passam pela IA)
  function dobj(k){ var v=(dados&&dados[k]!=null)?(""+dados[k]).trim():""; return v; }
  function temNum(v){ return v && /[0-9]/.test(v); }
  // normaliza um campo curto vindo da IA: se a IA respondeu "não informado",
  // "a confirmar", "n/a", "-", etc., trata como VAZIO (""), para o fallback do
  // renderer (dado objetivo do form) assumir em vez de vazar o "não informado"
  // no meio de uma frase-modelo (ex.: "chegando por não informado").
  function campoIA(v){ v=(v==null?"":(""+v)).trim();
    if(!v || /^(n[aã]o informad[oa]|a confirmar|ponto a confirmar|n\/a|indispon[ií]vel|sem informa[çc][aã]o|-{1,3})$/i.test(v)) return "";
    return v; }
  // substitui {slot} pelos valores de um mapa; slot sem valor vira "" e a frase
  // é limpa (espaços/vírgulas órfãs) - mesma disciplina anti-placeholder.
  function aplicaCampos(txt, map){ if(txt==null) return "";
    var s=(""+txt).replace(/\{([a-z_]+)\}/gi,function(m,k){ return (map&&map[k]!=null)?(""+map[k]):""; });
    return s.replace(/\s{2,}/g," ").replace(/\s+([,.;:!?])/g,"$1").replace(/,\s*\./g,".").trim(); }
  // primeira letra maiúscula (para começar frase com slot)
  function ucfirst(s){ s=(s==null?"":""+s); return s ? s.charAt(0).toUpperCase()+s.slice(1) : s; }

  // ---- MÓDULOS FIXOS do Playbook ----
  // Conteúdo NEUTRO (sem vocabulário de nicho), igual para todo cliente, derivado
  // do modelo padrão-ouro (playbook-premium). 10 módulos; a Biblioteca de
  // Procedimentos (gerada por IA) é inserida como Módulo 2, no meio.
  var MOD_FIXOS=[
    { id:"fundamentos", titulo:"Fundamentos do Atendimento", lead:"A base antes de qualquer script.",
      tipo:"texto+listas", blocos:[
        {p:"Na maioria das vezes, o WhatsApp é o primeiro contato da pessoa com a empresa. Cada mensagem, cada palavra e cada minuto de demora moldam a percepção de valor, de confiança e de credibilidade. Atender bem não é responder rápido por responder. É conduzir com método, do primeiro contato até a avaliação."},
        {eyebrow:"O que é um lead",p:"Um lead é um cliente em potencial que demonstrou interesse. Mas nem todo lead está no mesmo momento: alguns só estão curiosos, outros já sabem o que querem. Tratar todos igual é o erro que faz lead virar cliente da concorrência. Identifique o perfil e adapte a abordagem: cada conversa é uma chance de acolher e construir confiança, nunca só uma tentativa de venda imediata."},
        {eyebrow:"Papel da equipe",lista:["Representar a empresa em todos os canais, com a mesma excelência do presencial.","Acolher, orientar e educar antes de tentar vender.","Entender de verdade a necessidade da pessoa, com escuta ativa.","Conduzir para a avaliação e o serviço, sem deixar a conversa esfriar.","Organizar o CRM e a agenda, registrando dor, interesse e histórico de cada lead."]},
        {eyebrow:"Princípios",lista:["Empatia genuína em toda interação.","Escuta ativa: ouça mais, fale menos.","Comunicação clara, respeitosa e transparente.","Atendimento personalizado, nunca robótico.","Ética acima de qualquer fechamento.","Venda consistente, sem pressão insustentável."]},
        {eyebrow:"Regra dos 5 minutos",p:"Todo lead é prioridade: responda em até 5 minutos. Quem responde nos primeiros minutos vende muito mais, porque chega enquanto a pessoa ainda está pensando no assunto. Mas velocidade nunca atropela qualidade: responda rápido E com cuidado. Trate pelo nome desde a primeira mensagem e sempre termine com uma pergunta, para manter a conversa viva."},
        {eyebrow:"O que evitar",lista:["Começar a conversa falando de preço.","Enviar textos longos e sem contexto.","Mandar áudios longos que ninguém ouve.","Usar linguagem técnica demais, que afasta em vez de aproximar.","Responder de forma automática e impessoal."]}
      ]},
    { id:"biblioteca", titulo:"Biblioteca de Procedimentos", lead:"Um roteiro de venda completo para cada serviço da empresa.", tipo:"biblioteca" },
    { id:"follow-up", titulo:"Régua de Follow Up", lead:"Cinco toques para reabrir a conversa sem soar cobrança.",
      tipo:"toques", intro:"A régua existe para a pessoa sentir cuidado, não para forçar resposta. Cada mensagem é um gesto leve, e cada dia puxa o próximo. Um dos toques entrega valor de verdade (uma dica útil). Sem resposta no 5º toque, o lead segue para Repescagem.",
      toques:[
        {when:"Follow Up 1 · 1 a 2h sem resposta",title:"Reabrir com leveza",goal:"Garantir que a mensagem chegou, sem cobrar.",msg:"Oi, só passando aqui para garantir que minha mensagem chegou. Sei que o dia corre. Quando puder, me conta como posso te ajudar."},
        {when:"Follow Up 2 · 3 a 4h",title:"Cuidado real",goal:"Mostrar que existe alguém do outro lado.",msg:"Oi, fiquei pensando aqui. Se preferir, pode me responder por áudio, do jeito que for mais fácil para você. Estou por aqui."},
        {when:"Follow Up 3 · Final do dia",title:"Fechar o dia com presença",goal:"Encerrar o dia sem pressão.",msg:"Vou encerrar o meu dia daqui a pouco. Fico à disposição amanhã desde cedo. Boa noite e cuide de você."},
        {when:"Follow Up 4 · Manhã seguinte",title:"Entregar valor",goal:"Reabrir entregando algo útil, não cobrando resposta.",msg:"Bom dia! Lembrei de você e separei uma dica rápida que acho que vai te ajudar. Dá uma olhada, e se quiser, me chama por aqui quando puder 💚"},
        {when:"Follow Up 5 · Terceiro dia",title:"Última tentativa carinhosa",goal:"Encerrar com elegância antes da nutrição.",msg:"Oi. Vou parar de te mandar mensagem por aqui para não te incomodar. Sempre que quiser conversar, sabe onde me encontrar. Vou continuar te lembrando com carinho."}
      ]},
    { id:"nivel-consciencia", titulo:"Níveis de Consciência do Lead", lead:"Ler o momento certo muda o tom da conversa e a conversão.",
      tipo:"niveis", intro:"Cada pessoa chega num momento diferente. Saber ler esse momento separa quem empurra script de quem conduz com naturalidade. Identifique o perfil nas primeiras mensagens e ajuste o tom.",
      niveis:[
        {nome:"Inconsciente",gat:"Educação + Autoridade",perfil:"Ainda não reconhece o problema com clareza, ou nem sabe que existe solução. Chegou por curiosidade.",abordagem:"Educativa, leve e informativa. Não tente vender. Ensine. Mostre que aquele incômodo tem nome e tem solução, sem pressa.",sinal:"Faz perguntas genéricas, \"só estou dando uma olhada\", não cita um problema específico."},
        {nome:"Problema",gat:"Empatia + Validação da dor",perfil:"Já sente a dor ou sabe que tem um problema, mas não sabe qual é a solução nem por onde começar.",abordagem:"Valide a dor e acolha. Mostre que entende o que a pessoa sente, e só então apresente o caminho como solução natural.",sinal:"Descreve um incômodo, mas pergunta \"o que vocês indicam?\"."},
        {nome:"Solução",gat:"Diferenciação + Autoridade",perfil:"Já conhece as opções, talvez já pesquisou em outros lugares, chega pedindo algo específico. Mas ainda não conhece a sua empresa.",abordagem:"Apresente o valor da empresa e convide para a avaliação. Mostre o diferencial (planejamento, equipe, cuidado) antes de qualquer número.",sinal:"Já chega pedindo o serviço pelo nome e compara."},
        {nome:"Indeciso",gat:"Segurança + Prova social",perfil:"Quer resolver, mas tem medo de errar. Precisa de segurança para decidir.",abordagem:"Passe segurança e autoridade. Reforce o acompanhamento, a experiência da equipe e o cuidado em cada etapa. Tire o medo antes de pedir a decisão.",sinal:"Diz \"vou pensar\", \"tenho medo\", \"será que vai dar certo comigo?\"."},
        {nome:"Decidido",gat:"Agilidade + Escolha fechada",perfil:"Já quer fechar. Pergunta sobre valores, agenda e disponibilidade.",abordagem:"Vá direto ao ponto, com objetividade. Proposta clara, dois horários fechados e fechamento. Não perca o tempo da venda enrolando.",sinal:"Pergunta \"quanto custa?\", \"quando tem horário?\", \"aceita cartão?\"."}
      ]},
    { id:"repescagem", titulo:"Repescagem e Nutrição", lead:"Quando o lead esfria, reaquecer com paciência e valor.",
      tipo:"toques", intro:"O Follow Up reabre a conversa nas primeiras horas. A Repescagem é o passo seguinte: o lead esfriou, sumiu ou disse \"depois eu vejo\". Aqui o jogo é reaquecer com paciência e valor, nunca insistir. Cada lead é uma pessoa, não um número. A cadência vai até 8 tentativas, com intervalos crescentes.",
      toques:[
        {when:"Tentativa 1 · 4 horas",title:"Proximidade gentil",goal:"Reabrir com leveza, focando na pessoa.",msg:"Oi, tudo bem com você? Fiquei pensando na nossa conversa e queria saber como você está em relação ao que conversamos. Teve um tempinho pra pensar? O que mais está pesando na sua decisão agora?"},
        {when:"Tentativa 2 · 24 horas",title:"Interesse verdadeiro",goal:"Validar a autonomia e despertar curiosidade.",msg:"Oi! Você chegou a resolver isso em outro lugar, ou ainda está avaliando suas opções? Se quiser, posso te mandar mais detalhes pra você decidir com segurança. Faz sentido?"},
        {when:"Tentativa 3 · 48 horas",title:"Cooperação consultiva",goal:"Mostrar esforço real e parceria para destravar.",msg:"Fico aqui pensando em como te ajudar de um jeito que faça sentido de verdade pra você. Me conta: o que ainda está te impedindo de dar esse passo? Pode ser o valor, o tempo ou uma dúvida. Quero te entender pra resolver junto."},
        {when:"Tentativa 4 · 3 dias",title:"Reativação com valor",goal:"Trazer um motivo genuíno para retomar, sem oferta.",msg:"Oi! Lembrei de você e queria compartilhar uma dica rápida que pode te ajudar. O que você achou? Se fizer sentido, seguimos a conversa por aqui 💚"},
        {when:"Tentativa 5 · 5 dias",title:"Convite sem pressão",goal:"Remover a barreira oferecendo experiência.",msg:"Quero te fazer um convite. Que tal vir conhecer e fazer uma avaliação sem compromisso? Sem precisar decidir nada na hora, só pra você sentir de perto como a gente cuida. Pode ser?"},
        {when:"Tentativa 6 · 8 dias",title:"Prova e segurança",goal:"Reforçar autoridade e tirar o medo de errar.",msg:"Oi! Só passando pra reforçar que, quando você decidir cuidar disso, vai estar em mãos seguras. Nossa equipe acompanha cada etapa de pertinho."},
        {when:"Tentativa 7 · 15 dias",title:"Última leveza",goal:"Sinalizar que a régua vai pausar, com carinho.",msg:"Oi! Vou parar de te escrever por aqui pra não te incomodar. Mas quero que saiba: sempre que quiser cuidar disso, é só me chamar. Vou continuar aqui, na torcida por você."},
        {when:"Tentativa 8 · Encerramento",title:"Porta aberta de verdade",goal:"Encerrar com elegância e deixar boa impressão.",msg:"Entendo que talvez não seja o momento agora, e tudo bem, cada pessoa tem o seu tempo e eu respeito muito isso. Se um dia você quiser conversar, vou estar aqui. Foi um prazer te conhecer!"}
      ],
      principios:["Repescagem é cuidado e acompanhamento, nunca cobrança.","Intervalos crescentes: comece em horas, termine em semanas. Pressa afasta.","Personalize sempre: cite algo que a pessoa falou. Mensagem genérica ela percebe.","Nunca repita \"viu minha mensagem?\". Cada toque precisa trazer algo novo.","Pare quando o lead pedir, ou no 8º toque. Insistir além disso queima a marca."]},
    { id:"objecoes-gerais", titulo:"Biblioteca de Objeções", lead:"As objeções que aparecem em qualquer serviço, com o gatilho que desarma.",
      tipo:"objecoes", intro:"Objeção não é barreira, é interesse disfarçado de dúvida. Quem objeta está considerando. A regra: acolha primeiro, isole o que realmente pesa, e só então responda com segurança. Objeção respondida com pressa vira discussão; objeção acolhida vira agendamento.",
      objecoes:[
        {q:"Está caro",gat:"Reancoragem em valor",a:"Entendo, é uma decisão importante. Mas pensa comigo: não é só um serviço, é o seu bem-estar, com uma equipe cuidando de cada etapa. E temos condições que cabem no seu orçamento. Posso te mostrar na avaliação?"},
        {q:"Vou pensar",gat:"Isolar a objeção real",a:"Claro, super importante decidir com calma. Só me diz uma coisa: o que exatamente ainda te deixa em dúvida, o valor, o tempo ou o serviço em si? Às vezes é algo que eu esclareço agora em dois minutos."},
        {q:"Tenho medo / receio",gat:"Segurança + Prova social",a:"É super normal sentir isso, muita gente chega assim. Hoje o processo é tranquilo e você é acompanhada do início ao fim. O cuidado vem antes de tudo aqui. Quer que eu te explique como funciona, passo a passo?"},
        {q:"Vou falar com meu marido / família",gat:"Inclusão + Baixo compromisso",a:"Faz todo sentido decidir junto. Que tal eu já deixar uma avaliação reservada pra vocês irem juntos? Vendo o caso de perto, a conversa em casa fica muito mais fácil. E se decidirem diferente, a gente desmarca sem compromisso."},
        {q:"Agora não vou conseguir",gat:"Reserva sem pressão",a:"Tudo bem! Posso deixar registrado aqui e te lembrar quando for melhor pra você. Só me confirma: quer que eu te procure daqui a uns 15 dias?"},
        {q:"Não tenho tempo",gat:"Flexibilidade",a:"Imagina, por isso a gente adapta tudo ao seu ritmo. Temos horários alternativos, inclusive que cabem na correria. Qual período funciona melhor pra você: manhã, tarde ou noite?"},
        {q:"Achei mais barato em outro lugar",gat:"Diferenciação por qualidade",a:"Vale comparar mesmo, e fico feliz que esteja pesquisando. Só cuide pra que seja o mesmo padrão, o mesmo planejamento e a mesma equipe. Barato que precisa refazer sai caro. Posso te mostrar exatamente o que está incluso aqui?"},
        {q:"Só queria saber o valor",gat:"Reposicionar para a avaliação",a:"Entendo, e eu quero muito te passar um valor justo, não um chute. Cada caso é diferente, e sem ver de perto eu poderia te dar um número errado. Por isso a avaliação existe: é rápida e é nela que você recebe o valor certo, do seu caso. Posso já reservar um horário pra você?"},
        {q:"Depois eu marco / depois eu vejo",gat:"Baixo atrito + Reserva ativa",a:"Sem problema nenhum, sem pressa 🙂 Só que \"depois\" costuma sumir na correria do dia a dia, né? Pra não deixar isso pra trás, posso já deixar um horário reservado no seu nome, e se precisar a gente remarca numa boa. Prefere começo ou fim de semana?"}
      ]},
    { id:"venda-consultiva", titulo:"Venda Consultiva e Fechamento", lead:"Valor antes de preço, sempre.",
      tipo:"venda", intro:"Fechar não é forçar. É conduzir a pessoa até o sim com clareza e segurança. A regra de ouro: valor antes de preço, sempre. Quando a pessoa entende o que está recebendo, o preço faz sentido, e o desconto, quando vem, parece um presente, não uma obrigação.",
      valorAntesPreco:["O nosso serviço é planejado caso a caso, com base no seu histórico e no que você quer resolver. Nada aqui é padrão.","Além do resultado, o que a gente entrega é tranquilidade: você é acompanhada de perto, em cada etapa, por uma equipe que cuida de verdade.","Antes de falar de valor, deixa eu te mostrar por que tanta gente diz que aqui é diferente. O cuidado começa no momento em que você chega.","A maioria dos nossos clientes conta que saiu mais confiante, não só com o problema resolvido, mas com a autoestima de volta."],
      guiaBolso:[
        {n:"01",passo:"Abordagem",oQueFazer:"Cumprimente pelo nome, seja caloroso e termine com uma pergunta."},
        {n:"02",passo:"Qualificação",oQueFazer:"Descubra a dor real e o que a pessoa quer resolver. Ouça mais, fale menos."},
        {n:"03",passo:"Conscientização",oQueFazer:"Mostre que entende a dor e que existe solução. Crie valor antes do preço."},
        {n:"04",passo:"Apresentação",oQueFazer:"Explique o serviço em linguagem simples, focando no benefício final."},
        {n:"05",passo:"Objeções",oQueFazer:"Acolha a dúvida, isole o que pesa e responda com segurança. Objeção é interesse."},
        {n:"06",passo:"Fechamento",oQueFazer:"Conduza ao sim com pergunta direta e dois horários fechados, sem pressão."},
        {n:"07",passo:"Agendamento",oQueFazer:"Confirme nome, data, horário e o que trazer. Reforce o cuidado."},
        {n:"08",passo:"Pós e fidelização",oQueFazer:"Reduza falta com lembretes, peça indicação no auge e mantenha o relacionamento."}
      ]},
    { id:"pos-venda", titulo:"Pós Venda e Fidelização", lead:"A venda não termina no sim, começa nele.",
      tipo:"toques", intro:"O pós-venda é o que transforma um cliente em fã e em fonte de novos clientes. Acompanhar bem reduz falta, aumenta satisfação, gera indicação e traz a pessoa de volta. Mostre que a empresa se importa com a jornada, não só com a venda.",
      toques:[
        {when:"Em até 24h após fechar",title:"Agradecimento personalizado",goal:"Reforçar a boa escolha e o acolhimento.",msg:"Que alegria ter você com a gente 💚 Obrigada por confiar. Estamos felizes em te acompanhar nessa jornada de cuidado."},
        {when:"Antes do serviço",title:"Confirmação e orientação",goal:"Reduzir ansiedade e a falta, passando segurança.",msg:"Passando pra confirmar o seu horário e te deixar tranquila: está tudo preparado pra te receber. Qualquer dúvida antes do dia, é só me chamar. Vai dar tudo certo!"},
        {when:"Após a primeira etapa",title:"Follow-up de experiência",goal:"Ouvir como foi e fortalecer o vínculo.",msg:"Como você se sentiu depois da sua primeira etapa? Quero saber tudo, sua experiência é o que mais importa pra gente. Qualquer coisa que precisar, estou por aqui."},
        {when:"Ao longo do acompanhamento",title:"Educação e reforço de valor",goal:"Manter presença com conteúdo útil, sem vender.",msg:"Separei uma dica rápida pra você manter o seu resultado. A gente se importa com a sua jornada inteira, não só com o dia da consulta 😊"},
        {when:"No auge da satisfação",title:"Pedido de indicação",goal:"Transformar satisfação em novos clientes quentes.",msg:"Fico muito feliz que você está gostando do resultado! 💚 Com certeza você conhece alguém que também merece esse cuidado. Se quiser, é só mandar o meu contato pra essa pessoa, que eu cuido dela com o mesmo carinho que cuidei de você."}
      ]},
    { id:"crm", titulo:"CRM Operacional", lead:"Onde cada lead vive e por que nunca se perde de vista.",
      tipo:"crm", intro:"Script bom sem CRM é venda no improviso. O CRM é onde cada cliente em potencial vive: em que etapa está, qual o próximo passo e quando ele acontece. Não precisa ser um sistema caro, pode ser uma planilha bem feita. O que importa é a disciplina: todo lead tem etapa, etiquetas e uma data do próximo contato. Lead sem próximo passo marcado é lead que vai esfriar.",
      regraOuro:"Toda conversa termina com uma pergunta na cabeça da atendente: \"qual é o próximo passo e quando ele acontece?\". Se não houver resposta, o lead ainda não foi tratado. Ninguém sai do CRM sem uma data de retorno ou um motivo de fechamento.",
      funil:[
        {n:"01",etapa:"Novo Lead",entra:"Assim que a primeira mensagem chega.",sai:"Quando a atendente responde e o lead reage, vai para Em Conversa."},
        {n:"02",etapa:"Em Conversa",entra:"Quando o lead respondeu e o diálogo está aberto, ainda sem qualificar.",sai:"Quando você entendeu a dor e o momento, vai para Qualificado."},
        {n:"03",etapa:"Qualificado",entra:"Quando há dor real, serviço identificado e intenção de resolver.",sai:"Quando um horário de avaliação é proposto e aceito, vai para Agendado."},
        {n:"04",etapa:"Agendado",entra:"Quando o lead escolheu o horário e confirmou nome e telefone.",sai:"No dia, se comparecer vai para Compareceu; se faltar, vai para Follow-up Ativo."},
        {n:"05",etapa:"Compareceu",entra:"Quando a pessoa esteve na avaliação presencial.",sai:"Quando recebe a proposta e demonstra interesse, vai para Em Negociação."},
        {n:"06",etapa:"Em Negociação",entra:"Quando a proposta foi apresentada e há conversa de valor ou decisão.",sai:"Fechou: vai para Ganho. Esfriou: vai para Follow-up Ativo."},
        {n:"07",etapa:"Ganho",entra:"Quando a pessoa fecha o serviço.",sai:"Encerra o funil de venda e entra no Pós-Venda."},
        {n:"08",etapa:"Follow-up Ativo",entra:"Lead que parou de responder ou faltou.",sai:"Respondeu: volta ao funil. Esgotou os 5 toques: vai para Repescagem."},
        {n:"09",etapa:"Repescagem",entra:"Lead recém-esfriado que não respondeu ao follow-up.",sai:"Respondeu: volta ao funil. Esgotou as 8 tentativas: vai para Perdido."},
        {n:"10",etapa:"Perdido",entra:"Lead que esgotou a repescagem OU pediu para parar.",sai:"Após 90 dias, entra na Reativação de Base. Nunca é apagado."}
      ],
      tags:["Serviço de interesse (define o script e o ticket esperado).","Nível de consciência (define o tom da abordagem).","Objeção principal (mostra o que destravar).","Origem (liga ao custo por lead).","Ticket estimado (prioriza o esforço).","Motivo de perda (alimenta relatórios e reativação)."]},
    { id:"metricas", titulo:"Métricas e Gestão", lead:"O que não se mede não melhora.",
      tipo:"metricas", intro:"Sem número, gestão vira achismo. Este painel é o termômetro semanal do comercial: poucas métricas, mas as que importam. Cada uma tem uma fórmula, uma meta e um plano de ação quando fica abaixo. Olhe uma vez por semana, no mesmo dia, e ataque o gargalo, não tudo de uma vez.",
      regraOuro:"Não tente melhorar tudo ao mesmo tempo. Encontre a etapa que mais vaza (o maior buraco do funil) e ataque só ela por uma semana. Métrica sem ação é só um número bonito no relatório.",
      kpis:[
        {meta:"< 5 min",nome:"Tempo médio de resposta",formula:"Soma do tempo até a 1ª resposta ÷ nº de leads respondidos.",baixa:"Acima de 5 min: defina quem cobre cada faixa de horário e ative atalhos de resposta. Velocidade é a métrica que mais mexe na conversão."},
        {meta:"> 90%",nome:"Taxa de resposta",formula:"Leads respondidos ÷ total recebidos × 100.",baixa:"Abaixo de 90%: tem lead caindo no vácuo. Cheque horários sem cobertura e mensagens não vistas."},
        {meta:"35–50%",nome:"Taxa de agendamento",formula:"Leads que agendaram ÷ leads qualificados × 100.",baixa:"Abaixo de 35%: revise a pré-qualificação e a oferta de horário. Use a pergunta de consequência e ofereça sempre dois horários fechados."},
        {meta:"> 70%",nome:"Taxa de comparecimento",formula:"Compareceram ÷ total agendado × 100.",baixa:"Abaixo de 70%: reforce a régua anti-falta (confirmação ativa, véspera e 2h antes). No-show alto quase sempre é confirmação fraca."},
        {meta:"40–60%",nome:"Taxa de fechamento",formula:"Fecharam ÷ total que compareceu × 100.",baixa:"Abaixo de 40%: trabalhe valor antes de preço, treine objeções e o fechamento por escolha."},
        {meta:"Acompanhar",nome:"Ticket médio",formula:"Faturamento fechado ÷ nº que fecharam.",baixa:"Caindo: revise o mix de serviços e cuide para não dar desconto cedo demais."},
        {meta:"Acompanhar",nome:"Custo por lead",formula:"Investimento em mídia ÷ nº de leads gerados.",baixa:"Subindo: revise a segmentação dos anúncios. Corte o que traz lead caro e ruim."}
      ]},
    { id:"reativacao", titulo:"Reativação de Base", lead:"O ouro enterrado: cliente antigo, orçamento frio, fim de acompanhamento.",
      tipo:"toques", intro:"A repescagem cuida do lead que acabou de esfriar. A reativação cuida do ouro enterrado na sua base: o cliente antigo que sumiu, o orçamento aprovado que nunca voltou e quem terminou o serviço e não fez manutenção. Esses contatos já confiam na empresa, o custo de trazê-los de volta é quase zero. Reativar a base é a venda mais barata que existe.",
      toques:[
        {when:"Cliente antigo · Toque 1",title:"Reencontro com cuidado",goal:"Reabrir com carinho, sem cobrar.",msg:"Oi! Tudo bem? 💚 Faz um tempinho que a gente não te vê por aqui e lembrei de você. Como você está? Se quiser dar aquela renovada ou só fazer um check-up, é só me chamar."},
        {when:"Orçamento frio · Toque 1",title:"Retomada leve",goal:"Reabrir sem soar cobrança do orçamento.",msg:"Oi! Tudo bem? 🙂 Fiquei pensando em você e no que a gente tinha conversado. Como você está em relação a isso hoje? Sem pressa nenhuma, só queria saber se ainda faz sentido pra você."},
        {when:"Fim de acompanhamento · Toque 1",title:"Celebrar e checar",goal:"Voltar pelo resultado conquistado.",msg:"Oi! 💚 Lembrei de você aqui e fiquei curiosa: como está o resultado? Tudo certinho? Quero saber se você está aproveitando bastante!"}
      ],
      principios:["Reative em lotes pequenos e personalizados, nunca um disparo em massa genérico.","Use o histórico como ponte: serviço feito, data da última visita, o que ficou pendente.","Respeite quem não responde: até 3 toques por ciclo, depois descanse a base por meses.","Reativação é relacionamento de longo prazo: a meta é reabrir a porta, não forçar o fechamento."]}
  ];

  // ---- renderers por documento ----
  var R={
    diagnostico:function(d){
      // 80/20: corpo FIXO nível-5 (títulos/análises dos motores) + campos curtos da IA
      // (status + 1 insight por motor, gargalo, foco) + dados objetivos do formulário.
      var c=d.campos||{};
      var nicho=(campoIA(c.nicho)||dobj("especialidade")||"empresa").toLowerCase();
      // Resumo do Cliente: TODO objetivo, direto do formulário (a IA não toca nisto).
      var resumo=[
        {rotulo:"Empresa", texto: dobj("clinica")},
        {rotulo:"Responsável", texto: dobj("responsavel")},
        {rotulo:"Segmento", texto: dobj("especialidade")},
        {rotulo:"Cidade", texto: dobj("cidade")},
        {rotulo:"Equipe", texto: dobj("equipe")? (dobj("equipe")+ (/[0-9]/.test(dobj("equipe"))?" colaboradores":"")):""},
        {rotulo:"Funcionamento", texto: dobj("funcionamento")}
      ];
      function factGrid(items){
        var wrap=el("div","nd-facts");
        (items||[]).forEach(function(it){
          var c2=el("div","nd-fact");
          c2.appendChild(el("p","f-label",esc(it.rotulo||"")));
          var txt=(it.texto==null?"":""+it.texto).trim();
          if(!txt || /^(n[aã]o informado|ponto a confirmar|a confirmar|-)$/i.test(txt)) c2.appendChild(el("span","nd-chip","Não informado"));
          else c2.appendChild(el("p","f-text",esc(txt)));
          wrap.appendChild(c2);
        });
        return wrap;
      }
      fillSection("resumo",function(f){
        if(c.sintese) f.appendChild(el("p",C.para,esc(ucfirst(c.sintese))));
        f.appendChild(factGrid(resumo));
      });
      // Indicadores: rótulo + valor FIXOS (valor do form quando existe), nota da IA.
      var notas=c.metricas_nota||[];
      var indicadores=[
        {rotulo:"Leads no topo", valor:"", nota:notas[0]||"Contatos novos que chegam por mês."},
        {rotulo:"Conversão em agendamento", valor:"", nota:notas[1]||"Percentual de contatos que viram agendamento."},
        {rotulo:"Comparecimento", valor:"", nota:notas[2]||"Percentual dos agendados que comparecem."},
        {rotulo:"Ticket médio", valor: temNum(dobj("ticket"))?("R$ "+dobj("ticket")):"", nota:notas[3]||"Valor médio por venda fechada."},
        {rotulo:"Reativação de base", valor:"", nota:notas[4]||"Clientes antigos reativados por mês."},
        {rotulo:"Indicação", valor:"", nota:notas[5]||"Clientes novos vindos de indicação."}
      ];
      fillSection("indicadores",function(f){ f.appendChild(statTiles(indicadores)); });
      // Os 7 motores: TÍTULO + 4 análises-modelo FIXAS (nível-5, com slot {nicho}) +
      // o insight curto da IA no topo (status). A IA nunca escreve as 4 análises.
      var MOT=[
        {id:"motor-demanda", base:[
          "Mapeie de onde vêm os contatos hoje e qual canal traz o cliente certo para {nicho}.",
          "Garanta presença ativa onde seu público pesquisa: busca local, perfil atualizado e redes.",
          "Crie uma oferta de entrada que reduza o risco de dar o primeiro passo com você.",
          "Meça o custo por lead para saber quanto vale abrir a torneira de demanda."]},
        {id:"motor-conversao", base:[
          "Padronize a primeira resposta: velocidade e tom definem a conversão em {nicho}.",
          "Registre cada orçamento por escrito e implante follow-up em até 48h na recusa.",
          "Tenha um roteiro de qualificação que descobre a real necessidade antes de falar preço.",
          "Feche por escolha (horário A ou B), nunca por sim/não, para não esfriar a decisão."]},
        {id:"motor-controle", base:[
          "Centralize os números do negócio num painel simples: leads, agendamentos e vendas.",
          "Acompanhe uma métrica por semana e ataque o maior vazamento do funil, não tudo de uma vez.",
          "Separe o faturamento por serviço para saber o que realmente dá retorno.",
          "Sem dado não há gestão: o que não se mede vira achismo e decisão no escuro."]},
        {id:"motor-reativacao", base:[
          "Consolide a base antiga num só lugar: cliente parado é a venda mais barata que existe.",
          "Crie uma cadência de reencontro com cuidado, sem cobrança, para reabrir a conversa.",
          "Programe lembretes de retorno e manutenção conforme o ciclo de {nicho}.",
          "Reative orçamentos aprovados que nunca voltaram: parte deles ainda quer fechar."]},
        {id:"motor-posicionamento", base:[
          "Assuma seu diferencial publicamente: o que você faz melhor tem que estar dito com clareza.",
          "Deixe a oferta legível: o cliente precisa entender o valor antes de olhar o preço.",
          "Padronize a identidade (perfil, fachada, materiais) para transmitir o mesmo padrão em tudo.",
          "Comunique a transformação que você entrega, não só o procedimento técnico."]},
        {id:"motor-indicacao", base:[
          "Peça indicação no auge da satisfação e inclua o pedido no checklist de entrega.",
          "Facilite o ato: ofereça mandar seu contato em vez de pedir o contato da pessoa.",
          "Rastreie a origem de cada cliente novo para saber quem mais indica.",
          "Dê um motivo claro para indicar: reciprocidade converte melhor que sorte."]},
        {id:"motor-prova-social", base:[
          "Peça avaliação pública ao final de cada atendimento bem-sucedido.",
          "Documente antes/depois e resultados reais para mostrar prova concreta.",
          "Colete depoimentos em vídeo: nada convence mais que um cliente satisfeito falando.",
          "Exiba credenciais e selos que reduzem o medo de decidir por você."]}
      ];
      var mot=c.motores||[];
      MOT.forEach(function(m,i){
        var g=mot[i]||{};
        fillSection(m.id,function(f){
          var st=statusRow(g.status); if(st) f.appendChild(st);
          var itens=[];
          if(g.insight) itens.push(g.insight);           // insight específico da IA no topo
          m.base.forEach(function(b){ itens.push(aplicaCampos(b,{nicho:nicho})); });
          f.appendChild(numberedList(itens));
        });
      });
      fillSection("gargalo",function(f){
        var intro="Cruzando os sete motores, o ponto que mais trava a receita hoje é este:";
        f.appendChild(el("p",C.para,esc(intro)));
        if(c.gargalo) f.appendChild(el("p","serif mt-4 text-[20px] leading-snug",esc(ucfirst(c.gargalo))));
      });
      // Metas: objetivas, direto do formulário.
      var metas=[
        {rotulo:"Faturamento atual", texto: temNum(dobj("faturamento"))?("R$ "+dobj("faturamento")):""},
        {rotulo:"Meta 6 meses", texto: temNum(dobj("meta6"))?("R$ "+dobj("meta6")):""},
        {rotulo:"Meta 12 meses", texto: temNum(dobj("meta12"))?("R$ "+dobj("meta12")):""},
        {rotulo:"Foco dos próximos 90 dias", texto: dobj("objetivo")}
      ];
      fillSection("metas",function(f){
        f.appendChild(factGrid(metas));
        if(c.foco) f.appendChild(el("p",C.para+" mt-8",esc(ucfirst(c.foco))));
      });
    },
    swot:function(d){
      // 80/20: moldura/rótulos FIXOS + 4 itens curtos por quadrante e 4 estratégias da IA.
      var c=d.campos||{};
      function rotulos(items){
        return (items||[]).map(function(t){ var ix=(t||"").indexOf(":");
          return esc(ix>2&&ix<70 ? t.slice(0,ix) : (t||"").slice(0,42)); }).join(" · ");
      }
      function quadReal(){
        var wrap=el("div","noeds-chart");
        wrap.innerHTML='<div class="noeds-swot">'
          +'<div><div class="s-tag" style="color:var(--foreground)">Forças</div><div class="s-body">'+rotulos(c.forcas)+'</div></div>'
          +'<div><div class="s-tag" style="color:var(--foreground)">Fraquezas</div><div class="s-body">'+rotulos(c.fraquezas)+'</div></div>'
          +'<div><div class="s-tag" style="color:var(--foreground)">Oportunidades</div><div class="s-body">'+rotulos(c.oportunidades)+'</div></div>'
          +'<div><div class="s-tag" style="color:var(--foreground)">Ameaças</div><div class="s-body">'+rotulos(c.ameacas)+'</div></div>'
          +'</div>';
        return wrap;
      }
      fillSection("forcas",function(f){ f.appendChild(quadReal()); f.appendChild(labeledList(c.forcas)); });
      fillSection("fraquezas",function(f){ f.appendChild(labeledList(c.fraquezas)); });
      fillSection("oportunidades",function(f){ f.appendChild(labeledList(c.oportunidades)); });
      fillSection("ameacas",function(f){ f.appendChild(labeledList(c.ameacas)); });
      // Títulos dos 4 cruzamentos são FIXOS; a IA só dá o TEXTO de cada estratégia.
      var TIT=["Forças × Oportunidades","Forças × Ameaças","Fraquezas × Oportunidades","Fraquezas × Ameaças"];
      var cruz=c.cruzamentos||[];
      fillSection("cruzamentos",function(f){ TIT.forEach(function(t,i){
        if(cruz[i]) f.appendChild(block(t,"",cruz[i])); }); });
    },
    bcg:function(d){
      // 80/20: explicação de cada quadrante e alocação FIXAS; a IA só classifica os
      // serviços REAIS (nome+porque). Quadrante sem serviço -> omitido.
      var c=d.campos||{};
      var PCT={estrela:60,vaca:25,interrogacao:15};
      function nomeReal(obj){ var n=((obj||{}).nome||"").trim();
        if(!n || /^(portf[óo]lio enxuto|a definir|n[ãa]o informado|n\/a)$/i.test(n)) return ""; return n; }
      fillSection("portfolio",function(f){
        var intro="A Matriz BCG organiza o portfólio para decidir onde investir energia e verba: o que puxa "
          +"crescimento (Estrela), o que sustenta o caixa (Vaca Leiteira), o que tem potencial a validar "
          +"(Interrogação) e o que drena esforço sem retorno (Abacaxi).";
        f.appendChild(el("p",C.para,esc(intro)));
        function q(tag,obj,meta,p){ var n=nomeReal(obj); if(!n) return "";
          return '<div><div><div class="q-tag">'+tag+'</div><div class="q-name">'+esc(n)
          +'</div></div><div class="q-meta">'+meta+(p!=null?" · "+p+"%":"")+'</div></div>'; }
        var quads=q("Estrela",c.estrela,"Foco do investimento",PCT.estrela)
          +q("Interrogação",c.interrogacao,"Validar demanda",PCT.interrogacao)
          +q("Vaca Leiteira",c.vaca,"Caixa e recorrência",PCT.vaca)
          +q("Abacaxi",c.abacaxi,"Revisar ou descontinuar",null);
        if(quads){ var wrap=el("div","noeds-chart");
          wrap.innerHTML='<div class="noeds-axis" style="margin-bottom:.6rem">Crescimento de mercado ↑ · Participação →</div>'
            +'<div class="noeds-quad">'+quads+'</div>';
          f.appendChild(wrap); }
      });
      // por-quadrante: nome real + 1 justificativa da IA + 1 orientação-modelo FIXA
      var GUIA={
        estrela:"Concentre aqui a maior parte da verba de captação: é o serviço que mais cresce e mais paga.",
        vaca:"Proteja a recorrência e a experiência: este serviço banca o caixa enquanto os outros amadurecem.",
        interrogacao:"Teste oferta e comunicação antes de escalar: valide a demanda com verba controlada.",
        abacaxi:"Revise preço, processo ou descontinuação: não deixe drenar tempo da equipe sem retorno."};
      [["estrela",c.estrela],["vaca",c.vaca],["interrogacao",c.interrogacao],["abacaxi",c.abacaxi]].forEach(function(p){
        fillSection(p[0],function(f){ var q=p[1]||{}; var n=nomeReal(q);
          if(!n){ f.appendChild(el("p",C.para,"Sem serviço classificado neste quadrante a partir do portfólio informado.")); return; }
          f.appendChild(el("p","mt-5 serif text-[20px]",esc(n)));
          var itens=[]; if(q.porque) itens.push(q.porque); itens.push(GUIA[p[0]]);
          f.appendChild(numberedList(itens)); });
      });
      fillSection("alocacao",function(f){
        var segs=[{nome:"Estrela",pct:60},{nome:"Vaca Leiteira",pct:25},{nome:"Interrogação",pct:15}];
        f.appendChild(allocBar(segs));
        f.appendChild(block("Estrela (60%)","","Foco do investimento em captação e crescimento."));
        f.appendChild(block("Vaca Leiteira (25%)","","Manutenção da recorrência que sustenta o caixa."));
        f.appendChild(block("Interrogação (15%)","","Verba controlada para validar potencial."));
        if(c.foco_estrela) f.appendChild(el("p",C.para+" mt-8",esc(ucfirst(c.foco_estrela))));
      });
    },
    persona:function(d){
      // 80/20: intro FIXA + cards das 3 personas (recortes reais do público, campos da IA).
      var c=d.campos||{};
      var personas=c.personas||[];
      fillSection("intro",function(f){
        var intro="Mapeamento das personas prioritárias desta empresa. Cada perfil abaixo é um recorte real do "
          +"público atendido, com as dores, os desejos e os medos que conduzem a decisão. Conhecer quem está do "
          +"outro lado muda o tom da conversa e a taxa de conversão.";
        f.appendChild(el("p",C.para,esc(intro)));
      });
      var ids=["persona-harmonizacao-facial","persona-estetica-avancada","persona-atendimento-geral"];
      var letras=["A","B","C"];
      // monta card compatível com personaCard (titulo, perfil, servico, frase, dores, desejos, objecoes, gatilho)
      function toCard(p){ return {
        titulo: (p.nome||"")+(p.faixa?(", "+p.faixa):""),
        perfil: p.perfil||"", servico: p.servico||"", frase: p.frase||"",
        dores: p.dores||[], desejos: p.desejos||[], objecoes: p.objecoes||[], gatilho: p.gatilho||"" }; }
      var rotulos=personas.map(function(p,i){ var s=(p.servico||"").trim(); return "Persona "+letras[i]+(s?" · "+s:""); });
      [].slice.call(document.querySelectorAll("span,a,button,li")).forEach(function(elx){
        if(elx.children.length) return;
        var m=/^\s*Persona\s+([ABC])\s*·/i.exec(elx.textContent||"");
        if(m){ var idx="ABC".indexOf(m[1].toUpperCase()); if(idx>=0 && rotulos[idx]) elx.textContent=rotulos[idx]; }
      });
      personas.forEach(function(p,i){
        if(i<ids.length){
          var sec=document.getElementById(ids[i]);
          if(sec){ var h2=sec.querySelector("h2"); if(h2 && rotulos[i]) h2.textContent=rotulos[i]; }
          fillSection(ids[i],function(f){ f.appendChild(personaCard(toCard(p))); });
        }
      });
      fillSection("motivos",function(f){ f.appendChild(numberedList(c.motivos||[])); });
    },
    marketing:function(d){
      // 80/20: plano de execução INTEIRO fixo (metodologia da consultoria), personalizado
      // por slots curtos da IA ({nicho}/{oferta_foco}/{canal}/{publico}). Sem prosa da IA.
      var c=d.campos||{};
      var M={ nicho:(campoIA(c.nicho)||dobj("especialidade")||"empresa").toLowerCase(),
        oferta_foco:(campoIA(c.oferta_foco)||dobj("objetivo")||"o serviço principal"),
        canal:(campoIA(c.canal_entrada)||campoIA(dobj("canalEntrada"))||"indicação"),
        publico:(campoIA(c.publico_curto)||dobj("publico")||"o público-alvo") };
      function ap(t){ return aplicaCampos(t,M); }
      fillSection("visao-geral",function(f){
        f.appendChild(el("p",C.para,esc(ap("O plano é executado em fases: primeiro estruturamos a base de captação e "
          +"atendimento, depois ativamos tráfego, recuperamos a base e escalamos. O foco de investimento recai sobre "
          +"{oferta_foco}, com o público de {publico} chegando principalmente por {canal}."))));
        var steps=[{label:"Primeiros 38 dias",name:"Fundação"},{label:"Fase 2",name:"Tráfego Pago"},
          {label:"Fase 3",name:"Recuperação de Base"},{label:"Primeiros 90 dias",name:"Consolidação"},{label:"Depois",name:"Escala"}];
        f.appendChild(timeLine(steps));
      });
      var BLOCOS=[
        {id:"primeiros-38", titulo:"Primeiros 38 dias · Fundação",
          estrategia:ap("Antes de acelerar, organizar a base: atendimento, oferta clara e captação mínima funcionando para {nicho}."),
          operacao:[ap("Padronizar a resposta no primeiro contato e o tempo até o retorno."),
            "Registrar todo lead num painel simples com etapa e próximo passo.",
            ap("Deixar a oferta de {oferta_foco} legível: valor antes do preço."),
            "Ativar e atualizar o perfil onde o público pesquisa."],
          resultado:"Base pronta para converter o que já chega, sem depender de sorte."},
        {id:"metodologia-trafego", titulo:"Fase 2 · Metodologia de Tráfego Pago",
          estrategia:ap("Com a base pronta, atrair demanda qualificada de {publico} de forma previsível."),
          operacao:[ap("Estruturar campanha de busca/local para quem procura {nicho} agora."),
            "Começar com verba controlada e medir custo por lead antes de escalar.",
            "Levar cada lead para o mesmo fluxo de atendimento padronizado.",
            "Acompanhar o custo por agendamento, não só o custo por clique."],
          resultado:"Fluxo de novos contatos que se paga e pode ser aberto no ritmo certo."},
        {id:"recuperacao-base", titulo:"Fase 3 · Recuperação de Base",
          estrategia:"A venda mais barata está na base: reativar quem já conhece a empresa.",
          operacao:["Consolidar contatos antigos e orçamentos não fechados num só lugar.",
            "Criar uma cadência de reencontro com cuidado, sem cobrança.",
            ap("Programar lembretes de retorno conforme o ciclo de {nicho}."),
            "Priorizar quem já demonstrou interesse: são os mais quentes."],
          resultado:"Receita adicional sem custo de mídia, só de organização e atenção."},
        {id:"primeiros-90", titulo:"Primeiros 90 dias · Consolidação",
          estrategia:ap("Transformar as três frentes num sistema que capta, converte e retém {publico} de forma constante."),
          operacao:["Revisar semanalmente o maior vazamento do funil e atacar só ele.",
            "Padronizar indicação no fim de cada atendimento bem-sucedido.",
            "Documentar prova social (avaliações, antes/depois, depoimentos).",
            ap("Escalar a verba de {oferta_foco} conforme o retorno se confirma.")],
          resultado:"Crescimento previsível apoiado em processo, não em esforço pontual."}
      ];
      BLOCOS.forEach(function(b){
        fillSection(b.id,function(f){
          f.appendChild(el("p","mt-5 serif text-[20px]",esc(b.titulo)));
          f.appendChild(block("Estratégia","",b.estrategia));
          var wop=el("div","py-5 border-b border-border");
          wop.appendChild(el("p",C.eyebrow+" nd-lab","Operação"));
          wop.appendChild(checkList(b.operacao));
          f.appendChild(wop);
          var wr=el("div","py-5 border-b border-border");
          wr.appendChild(el("p",C.eyebrow+" nd-lab","Resultado Esperado"));
          wr.appendChild(el("p","serif mt-3 text-[18px] leading-snug",esc(b.resultado)));
          f.appendChild(wr);
        });
      });
      var MOTORES=[
        {rotulo:"Geração de Demanda", texto:ap("Atrair {publico} por busca local, conteúdo e tráfego pago.")},
        {rotulo:"Conversão Comercial", texto:"Padronizar atendimento e follow-up para converter o que chega."},
        {rotulo:"Indicadores", texto:"Medir leads, agendamentos e vendas para decidir com dado."},
        {rotulo:"Reativação", texto:"Trazer de volta base antiga e orçamentos parados."},
        {rotulo:"Posicionamento e Oferta", texto:ap("Comunicar o diferencial e deixar {oferta_foco} clara.")},
        {rotulo:"Indicação", texto:"Transformar cliente satisfeito em novo lead quente."},
        {rotulo:"Prova Social", texto:"Acumular avaliações e resultados que reduzem o medo de decidir."}
      ];
      fillSection("motores",function(f){ MOTORES.forEach(function(m){ f.appendChild(block(m.rotulo,"",m.texto)); }); });
      fillSection("caminho-escala",function(f){
        f.appendChild(el("p",C.para,esc(ap("A escala vem quando as quatro fases viram rotina: captação previsível, "
          +"conversão padronizada, base reativada e prova social crescente. A partir daí, aumentar a verba de "
          +"{oferta_foco} amplia o resultado sem quebrar o processo."))));
      });
    },
    conteudo:function(d){
      // 80/20: os 5 pilares (peso+texto), o porquê e a ação são FIXOS; a IA só traz o
      // banco de 8 ideias ancoradas nos serviços reais.
      var c=d.campos||{};
      var nicho=(dobj("especialidade")||"empresa").toLowerCase();
      fillSection("porque",function(f){
        f.appendChild(el("p",C.para,esc(aplicaCampos("O conteúdo existe para gerar autoridade e confiança antes da venda. "
          +"Em vez de postar por postar, cada publicação cumpre um papel: educar, provar resultado ou levar à ação. "
          +"O plano abaixo organiza o que falar para o público de {nicho} de forma consistente.",{nicho:nicho}))));
      });
      var PILARES=[
        {peso:"25%", nome:"Autoridade", texto:"Mostrar domínio técnico e bastidores do trabalho: por que confiar em você."},
        {peso:"25%", nome:"Prova Social", texto:"Resultados reais, antes/depois e depoimentos que reduzem o medo de decidir."},
        {peso:"20%", nome:"Educação", texto:"Ensinar o público a reconhecer o problema e entender que tem solução."},
        {peso:"15%", nome:"Desejo", texto:"Despertar a vontade de resolver, ligando o serviço à transformação desejada."},
        {peso:"15%", nome:"Conversão", texto:"Chamar para a ação: avaliação, contato, agendamento, com passo claro."}
      ];
      fillSection("pilares",function(f){
        var segs=PILARES.map(function(p){ return {nome:p.nome,pct:pctFrom(p.peso)}; }).filter(function(s){return s.pct!=null;});
        if(segs.length) f.appendChild(allocBar(segs));
        PILARES.forEach(function(p){ f.appendChild(block(p.peso+" · "+p.nome,"",p.texto)); });
      });
      fillSection("banco",function(f){
        var grid=el("div","nd-ideas");
        (c.banco||[]).forEach(function(b,i){
          var card=el("div","nd-idea");
          var top=el("p","i-top");
          top.innerHTML='<span class="i-num">'+pad(i)+'</span>'
            +(b.pilar?'<span class="nd-tag">'+esc(b.pilar)+'</span>':"")
            +(b.formato?'<span class="nd-tag">'+esc(b.formato)+'</span>':"");
          card.appendChild(top);
          if(b.tema) card.appendChild(el("p","i-tema",esc(b.tema)));
          if(b.gancho) card.appendChild(el("p","i-gancho",esc(b.gancho)));
          if(b.desenvolvimento) card.appendChild(el("p","i-dev",esc(b.desenvolvimento)));
          grid.appendChild(card);
        }); f.appendChild(grid);
      });
      fillSection("acao",function(f){
        f.appendChild(checkList([
          "Escolher 3 ideias do banco e gravar esta semana, uma por pilar diferente.",
          "Definir um dia fixo de publicação para criar constância.",
          "Guardar cada depoimento e resultado que aparecer, para alimentar Prova Social."]));
      });
    },
    playbook:function(d){
      // Reconstrói o Playbook INTEIRO a partir de MOD_FIXOS (10 módulos neutros,
      // fixos) + a Biblioteca de Procedimentos (gerada por IA). O template
      // original só serve de casca (head/sidebar/design); aqui limpamos as
      // seções antigas e montamos as novas, na ordem certa, com o mesmo visual.
      var SURF="bg-surface p-6 sm:p-8", EB="eyebrow";
      var procs=d.procedimentos||[];
      var SECCLS="doc-section mx-auto max-w-[840px] border-t border-border px-6 py-16 scroll-mt-20 sm:px-10 sm:py-24 lg:px-12 lg:py-28";
      var H2CLS="serif mt-6 text-[28px] leading-[1.1] tracking-tight sm:mt-8 sm:text-[32px] lg:text-[38px]";
      var LEADCLS="mt-4 max-w-2xl text-[15px] leading-[1.75] font-light text-muted-foreground sm:mt-5 sm:text-[16px] sm:leading-[1.8]";
      function ulLista(items,cls){ var ul=el("ul","mt-4 space-y-2"); (items||[]).forEach(function(t){
        ul.appendChild(el("li",cls||"text-[13px] leading-[1.7] font-light text-foreground/90",esc(t))); }); return ul; }
      function painel(titulo,builder){ var d1=el("div",SURF); d1.appendChild(el("p",EB,esc(titulo))); builder(d1); return d1; }
      function grid2(a,b){ var g=el("div","mt-10 grid grid-cols-1 gap-px overflow-hidden border border-border bg-border md:grid-cols-2"); g.appendChild(a); if(b) g.appendChild(b); return g; }

      // cria uma <section> de módulo com cabeçalho padrão (número, h2, lead)
      function novaSecao(id, num, total, titulo, lead){
        var sec=el("section",SECCLS); sec.id=id;
        sec.appendChild(el("p","text-[10px] tracking-[0.32em] text-faint", num+"  /  "+total));
        sec.appendChild(el("h2",H2CLS,esc(titulo)));
        if(lead) sec.appendChild(el("p",LEADCLS,esc(lead)));
        return sec;
      }

      // ---------- renderizadores dos módulos FIXOS (por tipo) ----------
      function modTextoListas(sec,m){
        (m.blocos||[]).forEach(function(b){
          var w=el("div","mt-10");
          if(b.eyebrow) w.appendChild(el("p",EB,esc(b.eyebrow)));
          if(b.p) w.appendChild(el("p",(b.eyebrow?"mt-3 ":"")+C.para,esc(b.p)));
          if(b.lista) w.appendChild(numberedList(b.lista));
          sec.appendChild(w);
        });
      }
      function modToques(sec,m){
        if(m.intro) sec.appendChild(el("p",C.para+" mt-8",esc(m.intro)));
        (m.toques||[]).forEach(function(t){
          var card=el("div","mt-8 border border-border bg-surface p-6 sm:p-8");
          card.appendChild(el("p","text-[10px] tracking-[0.2em] uppercase text-faint",esc(t.when||"")));
          if(t.title) card.appendChild(el("p","serif mt-2 text-[19px] leading-snug",esc(t.title)));
          if(t.goal) card.appendChild(el("p","mt-1 text-[13px] leading-[1.6] font-light text-muted-foreground",esc(t.goal)));
          if(t.msg) card.appendChild(chatBubble("Mensagem pronta",t.msg));
          sec.appendChild(card);
        });
        if(m.principios){ sec.appendChild(el("p",EB+" mt-10","Princípios")); sec.appendChild(numberedList(m.principios)); }
      }
      function modNiveis(sec,m){
        if(m.intro) sec.appendChild(el("p",C.para+" mt-8",esc(m.intro)));
        (m.niveis||[]).forEach(function(nv){
          var card=el("div","mt-8 border border-border bg-surface p-6 sm:p-8");
          card.appendChild(el("p","serif text-[20px] leading-snug",esc(nv.nome||"")));
          if(nv.gat) card.appendChild(el("p","mt-1 text-[10px] tracking-[0.2em] uppercase text-faint",esc(nv.gat)));
          if(nv.perfil){ card.appendChild(el("p",EB+" mt-4","Perfil")); card.appendChild(el("p","mt-1 "+C.cardBody,esc(nv.perfil))); }
          if(nv.abordagem){ card.appendChild(el("p",EB+" mt-4","Abordagem")); card.appendChild(el("p","mt-1 "+C.cardBody,esc(nv.abordagem))); }
          if(nv.sinal){ card.appendChild(el("p",EB+" mt-4","Como identificar")); card.appendChild(el("p","mt-1 "+C.cardBody,esc(nv.sinal))); }
          sec.appendChild(card);
        });
      }
      function modObjecoes(sec,m){
        if(m.intro) sec.appendChild(el("p",C.para+" mt-8",esc(m.intro)));
        (m.objecoes||[]).forEach(function(o){ sec.appendChild(objPair({objecao:o.q, resposta:o.a})); });
      }
      function modVenda(sec,m){
        if(m.intro) sec.appendChild(el("p",C.para+" mt-8",esc(m.intro)));
        if(m.valorAntesPreco){ sec.appendChild(el("p",EB+" mt-10","Valor antes de preço")); sec.appendChild(numberedList(m.valorAntesPreco)); }
        if(m.guiaBolso){
          sec.appendChild(el("p",EB+" mt-10","Guia de bolso"));
          var ol=el("div","mt-4 border-t border-border");
          m.guiaBolso.forEach(function(g){
            var row=el("div","flex items-start gap-5 border-b border-border py-4");
            row.appendChild(el("span","text-[10px] tracking-[0.32em] text-faint pt-1 w-6 shrink-0",esc(g.n||"")));
            var bx=el("div",""); bx.appendChild(el("p","serif text-[16px] leading-snug",esc(g.passo||"")));
            if(g.oQueFazer) bx.appendChild(el("p","mt-1 "+C.cardBody,esc(g.oQueFazer)));
            row.appendChild(bx); ol.appendChild(row);
          });
          sec.appendChild(ol);
        }
      }
      function modCrm(sec,m){
        if(m.intro) sec.appendChild(el("p",C.para+" mt-8",esc(m.intro)));
        if(m.regraOuro){ var rg=el("div","mt-8 border-l-2 border-foreground pl-4"); rg.appendChild(el("p","text-[14px] leading-[1.7] font-light",esc(m.regraOuro))); sec.appendChild(rg); }
        if(m.funil){
          sec.appendChild(el("p",EB+" mt-10","Funil"));
          var ol=el("div","mt-4 border-t border-border");
          m.funil.forEach(function(e){
            var row=el("div","border-b border-border py-4");
            var top=el("div","flex items-baseline gap-4");
            top.appendChild(el("span","text-[10px] tracking-[0.32em] text-faint",esc(e.n||"")));
            top.appendChild(el("p","serif text-[17px] leading-snug",esc(e.etapa||"")));
            row.appendChild(top);
            if(e.entra) row.appendChild(el("p","mt-2 text-[12.5px] leading-[1.6] font-light text-muted-foreground","Entra: "+esc(e.entra)));
            if(e.sai) row.appendChild(el("p","mt-1 text-[12.5px] leading-[1.6] font-light text-muted-foreground","Sai: "+esc(e.sai)));
            ol.appendChild(row);
          });
          sec.appendChild(ol);
        }
        if(m.tags){ sec.appendChild(el("p",EB+" mt-10","Etiquetas obrigatórias")); sec.appendChild(numberedList(m.tags)); }
      }
      function modMetricas(sec,m){
        if(m.intro) sec.appendChild(el("p",C.para+" mt-8",esc(m.intro)));
        if(m.regraOuro){ var rg=el("div","mt-8 border-l-2 border-foreground pl-4"); rg.appendChild(el("p","text-[14px] leading-[1.7] font-light",esc(m.regraOuro))); sec.appendChild(rg); }
        (m.kpis||[]).forEach(function(k){
          var card=el("div","mt-6 border border-border bg-surface p-6 sm:p-8");
          var top=el("div","flex items-baseline justify-between gap-4");
          top.appendChild(el("p","serif text-[18px] leading-snug",esc(k.nome||"")));
          if(k.meta) top.appendChild(el("span","text-[11px] tracking-[0.14em] uppercase text-faint",esc(k.meta)));
          card.appendChild(top);
          if(k.formula) card.appendChild(el("p","mt-2 text-[12.5px] leading-[1.6] font-light text-muted-foreground","Fórmula: "+esc(k.formula)));
          if(k.baixa) card.appendChild(el("p","mt-1 text-[12.5px] leading-[1.6] font-light text-foreground/90","Se baixa: "+esc(k.baixa)));
          sec.appendChild(card);
        });
      }
      function renderModuloFixo(sec,m){
        if(m.tipo==="texto+listas") modTextoListas(sec,m);
        else if(m.tipo==="toques") modToques(sec,m);
        else if(m.tipo==="niveis") modNiveis(sec,m);
        else if(m.tipo==="objecoes") modObjecoes(sec,m);
        else if(m.tipo==="venda") modVenda(sec,m);
        else if(m.tipo==="crm") modCrm(sec,m);
        else if(m.tipo==="metricas") modMetricas(sec,m);
      }

      // ---------- biblioteca: índice + páginas de procedimento ----------
      function indiceBiblioteca(sec){
        if(!procs.length){ sec.appendChild(el("p",C.para+" mt-8","A biblioteca é montada a partir dos procedimentos do cliente.")); return; }
        var grid=el("div","mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2");
        procs.forEach(function(p,i){
          var card=el("div","border border-border p-6");
          card.appendChild(el("p","text-[10px] tracking-[0.28em] text-faint","Procedimento "+pad(i)));
          card.appendChild(el("p","serif mt-2 text-[19px] leading-snug",esc(p.nome||"")));
          if(p.sub) card.appendChild(el("p","mt-2 text-[13px] leading-relaxed text-muted-foreground font-light",esc(p.sub)));
          grid.appendChild(card);
        });
        sec.appendChild(grid);
      }

      // uma seção rica por procedimento (formato do modelo padrão-ouro)
      function bloco10s(p){
        if(!(p.dezSegundos&&p.dezSegundos.length)) return null;
        var w=el("div","mt-10 border border-border bg-surface p-6 sm:p-8");
        w.appendChild(el("p",EB,"Se você tiver 10 segundos"));
        var g=el("div","mt-5 grid grid-cols-1 gap-5 sm:grid-cols-3");
        p.dezSegundos.forEach(function(it){
          var c=el("div","");
          c.appendChild(el("p","text-[10px] tracking-[0.24em] text-faint uppercase",esc(it.k||"")));
          c.appendChild(el("p","mt-2 text-[14px] leading-[1.7] font-light text-foreground/90",esc(it.v||"")));
          g.appendChild(c);
        });
        w.appendChild(g); return w;
      }
      // etapa da jornada base, personalizada com p.foco
      function etapaJornada(et,foco){
        var card=el("div","mt-8 border border-border bg-surface p-6 sm:p-8");
        var head=el("div","flex items-baseline gap-4");
        head.appendChild(el("span","text-[10px] tracking-[0.32em] text-faint",et.n));
        head.appendChild(el("p","serif text-[20px] leading-snug",esc(et.etapa)));
        card.appendChild(head);
        if(et.gatilho) card.appendChild(el("p","mt-2 text-[10px] tracking-[0.2em] uppercase text-faint",esc(et.gatilho)));
        card.appendChild(el("p","mt-4 "+EB,"Por que converte"));
        card.appendChild(el("p","mt-2 text-[13.5px] leading-[1.7] font-light text-muted-foreground",esc(aplicaFoco(et.conversao,foco))));
        if(et.tecnica) card.appendChild(el("p","mt-3 text-[13.5px] leading-[1.7] font-light text-foreground/90",esc(aplicaFoco(et.tecnica,foco))));
        // micro-passos
        var ul=el("ul","mt-5 space-y-3");
        (et.passos||[]).forEach(function(ps){
          var li=el("li","");
          li.appendChild(el("p","text-[10px] tracking-[0.2em] uppercase text-faint",esc(ps.g||"")));
          li.appendChild(el("p","mt-1 text-[13.5px] leading-[1.7] font-light text-foreground/90",esc(aplicaFoco(ps.p,foco))));
          ul.appendChild(li);
        });
        card.appendChild(ul);
        // script pronto (copiável)
        if(et.script) card.appendChild(chatBubble("Script pronto",aplicaFoco(et.script,foco)));
        if(et.ponte){ card.appendChild(el("p",EB+" mt-5","Ponte →")); card.appendChild(el("p","mt-2 text-[13.5px] leading-[1.7] font-light text-muted-foreground",esc(aplicaFoco(et.ponte,foco)))); }
        var g2=el("div","mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2");
        if(et.sinalVerde){ var a=el("div",""); a.appendChild(el("p",EB,"✓ Avançar quando")); a.appendChild(el("p","mt-2 text-[13px] leading-[1.6] font-light text-foreground/90",esc(aplicaFoco(et.sinalVerde,foco)))); g2.appendChild(a); }
        if(et.seSilencio){ var b=el("div",""); b.appendChild(el("p",EB,"↻ Se travar")); b.appendChild(el("p","mt-2 text-[13px] leading-[1.6] font-light text-foreground/90",esc(aplicaFoco(et.seSilencio,foco)))); g2.appendChild(b); }
        card.appendChild(g2);
        return card;
      }
      // preenche o MIOLO de uma seção de procedimento (f = a própria section)
      function renderProcConteudo(f,p){
          var foco=p.foco||{};
          // 1) Se você tiver 10 segundos
          var b10=bloco10s(p); if(b10) f.appendChild(b10);
          // 2) Objetivo
          if(p.objetivo){ var obj=el("div","mt-10"); obj.appendChild(el("p",EB,"Objetivo")); obj.appendChild(el("p","mt-3 "+C.para,esc(p.objetivo))); f.appendChild(obj); }
          // 3) Como conduzir o atendimento (fluxo de 6 etapas resumidas)
          if(p.fluxo&&p.fluxo.length){
            var cond=el("div","mt-12");
            cond.appendChild(el("p",EB,"Fluxo"));
            cond.appendChild(el("p","serif mt-3 text-[24px] leading-tight","Como conduzir o atendimento"));
            var ol=el("div","mt-6 border-t border-border");
            p.fluxo.forEach(function(passo){
              var row=el("div","flex items-start gap-5 border-b border-border py-5");
              row.appendChild(el("span","text-[10px] tracking-[0.32em] text-faint pt-1 w-6 shrink-0",esc(passo.n||"")));
              var bx=el("div","");
              bx.appendChild(el("p","serif text-[17px] leading-snug",esc(passo.t||"")));
              if(passo.d) bx.appendChild(el("p","mt-1 text-[13.5px] leading-[1.7] font-light text-muted-foreground",esc(passo.d)));
              if(passo.trig&&passo.trig.length) bx.appendChild(el("p","mt-2 text-[10px] tracking-[0.2em] uppercase text-faint",esc(passo.trig.join(" · "))));
              row.appendChild(bx); ol.appendChild(row);
            });
            cond.appendChild(ol); f.appendChild(cond);
          }
          // 4) A jornada do lead, etapa por etapa (jornada base personalizada)
          var jor=el("div","mt-16");
          jor.appendChild(el("p",EB,"Condução"));
          jor.appendChild(el("p","serif mt-3 text-[24px] leading-tight","A jornada do lead, etapa por etapa"));
          JORNADA_BASE.forEach(function(et){ jor.appendChild(etapaJornada(et,foco)); });
          f.appendChild(jor);
          // 5) Script de ouro
          if(p.gold){
            var gold=el("div","mt-16 border border-border bg-surface p-6 sm:p-8");
            gold.appendChild(el("p",EB,"★ Script que mais converte"));
            gold.appendChild(chatBubble("Script de ouro",p.gold));
            f.appendChild(gold);
          }
          // 6) Diagnóstico: descobrir & evitar
          if((p.descobrir&&p.descobrir.length)||(p.evitar&&p.evitar.length)){
            f.appendChild(grid2(
              painel("O que descobrir",function(box){ box.appendChild(ulLista(p.descobrir,"text-[14px] leading-[1.7] font-light text-foreground/90")); }),
              painel("O que evitar falar",function(box){ box.appendChild(ulLista(p.evitar)); })
            ));
          }
          // 7) Sinais de compra -> ação  (+ sinais de desinteresse)
          if(p.sinaisCompra&&p.sinaisCompra.length){
            var sc=el("div","mt-12");
            sc.appendChild(el("p",EB,"Sinais de compra → ação"));
            var ul=el("ul","mt-4 border-t border-border");
            p.sinaisCompra.forEach(function(it){
              var li=el("li","border-b border-border py-4");
              li.appendChild(el("p","serif text-[16px] leading-snug",esc(it.s||"")));
              if(it.acao) li.appendChild(el("p","mt-1 text-[13.5px] leading-[1.6] font-light text-muted-foreground","Ação: "+esc(it.acao)));
              ul.appendChild(li);
            });
            sc.appendChild(ul);
            if(p.sinaisDesinteresse&&p.sinaisDesinteresse.length){
              sc.appendChild(el("p",EB+" mt-6","Sinais de desinteresse"));
              sc.appendChild(ulLista(p.sinaisDesinteresse));
            }
            f.appendChild(sc);
          }
      }

      // ---------- RECONSTRUÇÃO da página ----------
      // localiza o container das seções (pai da 1ª .doc-section) e o footer,
      // remove as seções antigas do template e monta as novas na ordem certa.
      var primeira=document.querySelector(".doc-section");
      if(!primeira) return;
      var container=primeira.parentNode;
      var footer=container.querySelector("footer");
      [].slice.call(container.querySelectorAll(".doc-section")).forEach(function(s){ container.removeChild(s); });
      // ordem final de seções: os 10 módulos fixos, com as páginas de
      // procedimento inseridas logo após o módulo "biblioteca".
      var itens=[]; // {tipo:'mod'|'proc', ...}
      MOD_FIXOS.forEach(function(m){
        itens.push({tipo:"mod", m:m});
        if(m.id==="biblioteca"){ procs.forEach(function(p,i){ itens.push({tipo:"proc", p:p, i:i}); }); }
      });
      var total=("0"+itens.length).slice(-2);
      var navItens=[]; // p/ reconstruir o índice lateral / capítulos
      itens.forEach(function(it,idx){
        var num=("0"+(idx+1)).slice(-2);
        var sec, titulo, lead;
        if(it.tipo==="mod"){
          titulo=it.m.titulo; lead=it.m.lead;
          sec=novaSecao(it.m.id, num, total, titulo, lead);
          if(it.m.tipo==="biblioteca") indiceBiblioteca(sec);
          else renderModuloFixo(sec, it.m);
        } else {
          titulo="Procedimento "+("0"+(it.i+1)).slice(-2)+" · "+(it.p.nome||"");
          lead=it.p.sub||"";
          sec=novaSecao("proc-"+(it.i+1), num, total, titulo, lead);
          renderProcConteudo(sec, it.p);
        }
        container.insertBefore(sec, footer||null);
        navItens.push({id:sec.id, titulo:titulo});
      });

      // reconstrói o índice de navegação lateral (menu de capítulos), se existir:
      // troca os itens antigos pelos novos, na mesma UL.
      var navUL=document.querySelector("nav ul.space-y-1, aside ul.space-y-1, ul.space-y-1");
      if(navUL){
        var modeloLi=navUL.querySelector("li");
        navUL.innerHTML="";
        navItens.forEach(function(nv,i){
          var li=modeloLi?modeloLi.cloneNode(false):el("li","");
          var btn=el("button","group flex w-full items-baseline gap-5 py-2.5 text-left transition-colors");
          btn.type="button"; btn.setAttribute("data-goto",nv.id);
          btn.appendChild(el("span","text-[10px] tracking-[0.2em] text-faint w-6",("0"+(i+1)).slice(-2)));
          btn.appendChild(el("span","text-[13px] leading-snug transition-colors text-muted-foreground",esc(nv.titulo)));
          btn.addEventListener("click",function(){ var t=document.getElementById(nv.id); if(t) t.scrollIntoView({behavior:"smooth"}); });
          li.appendChild(btn); navUL.appendChild(li);
        });
      }
    },
    certificado:function(d){
      // 80/20: lista de documentos e rótulos das 4 áreas FIXOS; a IA só dá síntese,
      // escopo curto por área e próximo passo. Nome da empresa vem do formulário.
      var c=d.campos||{};
      fillSection("resumo",function(f){
        if(c.sintese) f.appendChild(el("p",C.para,esc(ucfirst(c.sintese))));
        var selo=el("div","nd-selo");
        selo.appendChild(el("p","s-e","Ciclo concluído"));
        var nomeEmpresa=(dados.clinica||"").trim();
        if(nomeEmpresa){
          selo.appendChild(el("p","s-empresa",esc(nomeEmpresa)));
          selo.appendChild(el("div","s-rule"));
          selo.appendChild(el("p","s-by","por Noeds"));
        } else { selo.appendChild(el("p","s-n","Noeds")); }
        f.appendChild(selo);
      });
      var AUDITADOS=["Diagnóstico de Impacto","Análise SWOT","Matriz BCG","Persona Estratégica",
        "Plano de Marketing Inteligente","Plano de Conteúdo Estratégico","Playbook Comercial"];
      fillSection("auditados",function(f){ f.appendChild(checkList(AUDITADOS)); });
      var AREAS=["Estratégia","Posicionamento","Marketing","Comercial"];
      var esc4=c.escopos||[];
      fillSection("conformidade",function(f){ AREAS.forEach(function(a,i){
        if(esc4[i]) f.appendChild(block(a,"",esc4[i])); }); });
      fillSection("proximo",function(f){ if(c.proximo) f.appendChild(el("p",C.para,esc(ucfirst(c.proximo)))); });
    }
  };

  // ---- 1) substitui placeholders globais ([Nome da Clínica] etc.) em TODA página ----
  var PH={
    "Nome da Clínica":dados.clinica, "Nome do Responsável":dados.responsavel,
    "Nome do responsável comercial":dados.responsavel, "Nicho da Clínica":dados.especialidade,
    "Cidade":dados.cidade, "Faturamento Atual":dados.faturamento, "Meta de Faturamento":dados.objetivo,
    "Principal Diferencial":dados.diferencial, "Principal Gargalo":dados.principal_dor
  };
  // sinônimos p/ resolver placeholder residual não-global (ex. "[Nome]" solto num
  // script do playbook) sem expor o colchete cru ao cliente. Chave = miolo em
  // minúsculas; valor = função que devolve o texto final (ou "" p/ apagar o campo).
  var PH_RESIDUAL=[
    [/^nome( do cliente| completo)?$/i, function(){ return dados.responsavel||dados.clinica||""; }],
    [/^clínica|^cl[ií]nica|^empresa|^nome da empresa$/i, function(){ return dados.clinica||""; }],
    [/^cidade$/i, function(){ return dados.cidade||""; }],
    [/^respons[áa]vel/i, function(){ return dados.responsavel||""; }]
  ];
  // seções "Prompt para a IA" / "prompt pronto" são TEMPLATES que o cliente vai
  // COPIAR e preencher em outra ferramenta - ali os colchetes ([Procedimento
  // Principal], [COLE AQUI O DOCUMENTO PERSONA]) são marcadores legítimos do
  // prompt, não dado faltando. Essas subárvores são ISENTAS da limpeza. Detecta
  // pelo cabeçalho .eyebrow do bloco (ex.: "Prompt para a IA").
  function ehBlocoPromptModelo(node){
    for(var el=(node.nodeType===1?node:node.parentElement), up=0; el && up<8; el=el.parentElement, up++){
      var eb=el.querySelector&&el.querySelector(".eyebrow");
      if(eb && /prompt (para a ia|pronto|modelo|de ia)/i.test(eb.textContent||"")) return true;
    }
    return false;
  }
  function neutralizarPlaceholders(root){
    (function walk(node){
      if(node.nodeType===3){
        var t=node.nodeValue;
        if(t.indexOf("[")>=0){
          if(ehBlocoPromptModelo(node)) return; // isenta prompt-modelo
          node.nodeValue=t.replace(/\[([^\]\[]{2,60})\]/g,function(m,key){
            for(var k in PH){ if(PH[k]&&new RegExp("^"+k,"i").test(key)) return PH[k]; }
            // não casou com placeholder global conhecido: tenta sinônimo residual...
            var kk=key.trim();
            for(var i=0;i<PH_RESIDUAL.length;i++){
              if(PH_RESIDUAL[i][0].test(kk)){ var v=PH_RESIDUAL[i][1](); if(v) return v; }
            }
            // ...e, como último recurso, remove o marcador SÓ se ele tiver "cara
            // de campo a preencher": começa com letra/underscore E NÃO contém
            // dígito nem o símbolo de moeda "R$". Assim apaga "[Nome]",
            // "[endereço]", "[confirmar convênios]" (placeholders) mas PRESERVA
            // valores legítimos como "[R$ 30]", "[1]", "[2024]". Importante:
            // testa "R$" como PAR (moeda), nunca a letra "R" isolada - senão
            // qualquer palavra com R (ex. PERSONA, PROCEDIMENTO) escaparia da
            // limpeza. O que não casar fica como está.
            if(/^[A-Za-zÀ-ÿ_]/.test(kk) && !/[0-9]|R\$/.test(kk)) return "";
            return m;
          }).replace(/\s{2,}/g," ").replace(/\s+([,.;:!?])/g,"$1");
        }
      } else if(node.nodeType===1 && !/SCRIPT|STYLE/.test(node.tagName)){
        for(var c=node.firstChild;c;c=c.nextSibling) walk(c);
      }
    })(root);
  }
  neutralizarPlaceholders(document.body);
  // o <title> (aba do navegador) não está em document.body, então o walk não o
  // alcança - resolve os placeholders dele à parte pra não aparecer "[Nome da
  // Clínica]" no título da aba.
  if(document.title && document.title.indexOf("[")>=0){
    document.title=document.title.replace(/\[([^\]\[]{2,60})\]/g,function(m,key){
      for(var k in PH){ if(PH[k]&&new RegExp("^"+k,"i").test(key)) return PH[k]; }
      return dados.clinica||m;
    });
  }

  // ---- 2) injeta o conteúdo do documento atual ----
  if(R[file] && docs[file]){ try{ R[file](docs[file]); }catch(e){ console.warn("render",file,e); } }
  // 2b) o conteúdo injetado por R[file] NÃO passou pelo walk acima (ele roda
  // antes da injeção). Alguns docs (ex. playbook) trazem scripts com "[Nome]",
  // "[dia]" etc. vindos da IA, e o template estático ainda tem seções próprias
  // com placeholders. Roda a neutralização DE NOVO sobre a página toda, agora
  // com o conteúdo final montado - garante que nenhum colchete cru chegue ao
  // cliente (regra: placeholder nunca visível).
  neutralizarPlaceholders(document.body);

  // conteúdo final já montado e limpo -> pode revelar (tira o skeleton do share)
  removerSkeleton();

  // ---- 3) religa os botões de copiar ESTÁTICOS do template ----
  // O template das páginas (playbook, conteúdo, persona) já vem com dezenas de
  // botões "Copiar mensagem"/"Copiar persona" no HTML, mas SEM handler de clique
  // - só os botões criados pelo próprio RENDER_JS (chatBubble) copiavam. Aqui a
  // gente varre todos os botões de copiar da página e liga o comportamento
  // (clipboard + fallback execCommand + feedback visual e acessível). Idempotente:
  // marca cada botão com data-copy-ligado pra nunca ligar 2x.
  (function ligarCopiasEstaticas(){
    // acha o texto que ESTE botão deve copiar, por proximidade no DOM:
    // 1) irmão/descendente com .whitespace-pre-line (scripts prontos), senão
    // 2) o bloco/card ancestral mais próximo (persona), usando seu texto visível.
    function textoDoBotao(btn){
      // 1) scripts prontos ("Copiar mensagem"): a mensagem está no
      // .whitespace-pre-line dentro do mesmo bloco-card do botão.
      var cont=btn.parentElement;
      for(var up=0; up<4 && cont; up++){
        var pre=cont.querySelector(".whitespace-pre-line");
        if(pre) return pre.innerText;
        cont=cont.parentElement;
      }
      // 2) "Copiar persona": o botão fica num header (só nome + botão); o
      // conteúdo da persona são os elementos irmãos desse header, dentro do card
      // pai. Sobe até o ancestral que tenha conteúdo bem maior que o header,
      // clona, remove header(s)/botão(ões) e usa o texto restante.
      var header=btn.parentElement; // div "nome + botão"
      var card=header?header.parentElement:null; // card da persona inteira
      if(card){
        var clone=card.cloneNode(true);
        clone.querySelectorAll("button").forEach(function(x){ x.remove(); });
        var t=(clone.innerText||"").replace(/\n{3,}/g,"\n\n").trim();
        // só usa se sobrou conteúdo real (mais que o próprio nome do header)
        if(t && t.length>40) return t;
      }
      // 3) último recurso: texto do bloco imediato sem o botão.
      var box=btn.parentElement;
      if(box){ var c2=box.cloneNode(true); c2.querySelectorAll("button").forEach(function(x){x.remove();});
        var t2=(c2.innerText||"").trim(); if(t2) return t2; }
      return "";
    }
    function ligar(btn){
      if(btn.getAttribute("data-copy-ligado")) return;
      btn.setAttribute("data-copy-ligado","1");
      var rotuloOriginal=btn.getAttribute("aria-label")||"Copiar";
      btn.addEventListener("click",function(){
        var texto=textoDoBotao(btn);
        var restaura=function(){ btn.setAttribute("aria-label",rotuloOriginal); btn.title=""; };
        var ok=function(){ btn.setAttribute("aria-label","Copiado"); btn.title="Conteúdo copiado com sucesso.";
          setTimeout(restaura,1800); };
        var falhou=function(){ btn.setAttribute("aria-label","Não foi possível copiar");
          btn.title="Não foi possível copiar. Selecione o texto e copie manualmente."; setTimeout(restaura,2600); };
        if(!texto){ falhou(); return; }
        var fallback=function(){
          try{ var ta=document.createElement("textarea"); ta.value=texto;
            ta.style.cssText="position:fixed;top:-9999px;left:-9999px"; document.body.appendChild(ta);
            ta.focus(); ta.select(); var okc=document.execCommand("copy"); document.body.removeChild(ta);
            okc?ok():falhou();
          }catch(e){ falhou(); }
        };
        if(navigator.clipboard&&navigator.clipboard.writeText){ navigator.clipboard.writeText(texto).then(ok,fallback); }
        else fallback();
      });
    }
    // pega todo botão cujo aria-label começa com "Copiar" (Copiar mensagem,
    // Copiar persona, etc.) e ainda não é um .nd-copy (esses já têm handler).
    document.querySelectorAll('button[aria-label^="Copiar"]').forEach(function(btn){
      if(btn.classList.contains("nd-copy")) return;
      ligar(btn);
    });
  })();

  // banner discreto indicando dossiê do cliente
  var b=document.createElement("div");
  b.style.cssText="position:fixed;bottom:0;left:0;right:0;z-index:50;background:var(--surface,#111);border-top:1px solid var(--border,#262626);padding:8px 16px 8px 72px;font-size:11px;letter-spacing:.1em;color:var(--muted-foreground,#aaa);display:flex;gap:14px;align-items:center;justify-content:space-between";
  b.innerHTML='<span>DOSSIÊ · '+esc(dados.clinica||"Cliente")+(trocouDeCliente?' · <span style="color:#e8a33d">esta aba mostrava outro cliente antes. Confira se é o dossiê certo</span>':'')+'</span>';
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
# Páginas-app (Gerar + Banco de clientes) - geradas por gen_app.py
# ---------------------------------------------------------------------------
try:
    import gen_app
    gen_app.build(OUT, CSS, SIDEBAR_CSS, SIDEBAR_JS, sidebar_html, FONTS_LINK, PRINT_CSS, THEME_BOOT_JS)
    print("gerar.html / clientes.html   <- gen_app.py")
except Exception as e:
    print("aviso: páginas-app não geradas:", e)

# ---------------------------------------------------------------------------
# Formulário público do cliente (dossie.html) - gerado por gen_form.py.
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

# Página dedicada do FORMULÁRIO - tema CLARO idêntico aos originais NOEDS.
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
