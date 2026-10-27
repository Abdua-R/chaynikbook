"""Render index.html in headless Chrome and check that the page actually works.

Usage: python <kit>/verify_render.py [--shot out.png], run from the book folder after build.py --local.

Checks the rendered DOM for: equations that clip, the lookup rail, marks outside their axes, the notes drawer,
fixed axes, the panel frame (what-to-watch, Table, Reset), the bird's-eye maps, every predict-then-test check
pressed and answered, no sideways scroll at 390px, MathJax errors, drawn charts, no panel error, no NaN or
undefined shown to the reader, no leftover markup, and the engine badge when the book has an engine.js. A probe
whose subject the book does not have (no panels, no maps, no checks, no engine) is skipped and says so.
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path.cwd()  # the book folder
BOOK = {"data_global": "BOOK_DATA", "checks_per_chapter": [1, 5],
        **json.loads((ROOT / "book.json").read_text(encoding="utf-8"))}
GLOBAL = BOOK["data_global"]
MAN = json.loads((ROOT / "chapters/manifest.json").read_text(encoding="utf-8"))
CHROME = pathlib.Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


def run_chrome(url, extra=()):
    with tempfile.TemporaryDirectory() as profile:
        cmd = [str(CHROME), "--headless=new", "--disable-gpu", "--no-sandbox",
               f"--user-data-dir={profile}", "--virtual-time-budget=20000",
               "--run-all-compositor-stages-before-draw", *extra, url]
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=180)
    return out


def main():
    idx = ROOT / "index.html"
    if not idx.exists():
        sys.exit("index.html not built; run python build.py --local first")
    url = idx.resolve().as_uri()
    problems = []

    if "--shot" in sys.argv:
        target = sys.argv[sys.argv.index("--shot") + 1]
        run_chrome(url, ["--window-size=1400,2600", f"--screenshot={target}"])
        print(f"  screenshot written to {target}")

    # MathJax puts an explicit width on its SVG, so an over-wide equation can clip with no
    # scrollbar while scrollWidth reports nothing wrong. Measure the SVG instead.
    probe = ("<script>window.addEventListener('load',function(){setTimeout(function(){"
             "var bad=[];document.querySelectorAll('.eq .row > span:last-child, .steps .st-math').forEach(function(sp){"
             "var eq=sp.closest('.eq,.steps'),g=sp.querySelector('svg');if(!g)return;"
             "var w=Math.round(g.getBoundingClientRect().width);"
             "if(w>sp.clientWidth+2&&sp.scrollWidth<=sp.clientWidth+2)"
             "bad.push((eq.id||'steps')+' '+sp.clientWidth+'<'+w);});"
             "document.title='EQCLIP:'+bad.length+'|'+bad.slice(0,5).join(' ; ');},7000);});</script>")
    src = idx.read_text(encoding="utf-8")
    probed = ROOT / "_verify_probe.html"
    anchor_tag = "<script>window." + GLOBAL + " ="
    PRE = '<script>window.__G = "%s";</script>' % GLOBAL
    probed.write_text(src.replace(anchor_tag, probe + PRE + anchor_tag, 1), encoding="utf-8")
    try:
        pr = run_chrome(probed.resolve().as_uri(), ["--dump-dom"]).stdout
        mm = re.search(r"<title>EQCLIP:(\d+)\|([^<]*)</title>", pr)
        if mm:
            n = int(mm.group(1))
            print(f"  equations clipping with no scrollbar: {n}")
            if n:
                problems.append("equations clip silently: " + mm.group(2))
        else:
            problems.append("equation clip probe did not report")
    finally:
        probed.unlink(missing_ok=True)

    # The lookup rail: hovering must fill the card and must never scroll the document. An
    # earlier version called scrollIntoView, which scrolls every scrollable ancestor including
    # the page, so the symbol slid out from under the cursor and could not be hovered at all.
    hv = ("<script>window.addEventListener('load',function(){setTimeout(function(){"
          "var bad=[];"
          "function t(sel,label){var el=document.querySelector(sel);"
          "if(!el){bad.push(label+' missing');return;}"
          "el.scrollIntoView({block:'center'});var y=window.scrollY;"
          "el.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));"
          "if(window.scrollY!==y)bad.push(label+' scrolled the page');"
          "var c=document.getElementById('defcard').textContent.trim();"
          "if(c.length<25)bad.push(label+' left the card empty');}"
          "t('.sym[data-sym]','symbol');"
          "if(document.querySelector('.term[data-term]'))t('.term[data-term]','term');"
          "if(document.querySelector('.eq'))t('.eq g[data-sym]','symbol inside an equation');"
          "window.MATHTAGS=document.querySelectorAll('g[data-sym]').length;"
          "var el=document.querySelector('.term[data-term]')||document.querySelector('.sym[data-sym]');"
          "el.dispatchEvent(new MouseEvent('click',{bubbles:true}));"
          "if(!document.querySelector('.dc-unpin'))bad.push('click did not pin');"
          "document.title='HOVER:'+bad.length+'|tags='+window.MATHTAGS+'|'"
          "+bad.join(' ; ');},7000);});</script>")
    hprobe = ROOT / "_verify_hover.html"
    hprobe.write_text(src.replace(anchor_tag, hv + PRE + anchor_tag, 1), encoding="utf-8")
    try:
        hr = run_chrome(hprobe.resolve().as_uri(), ["--dump-dom"]).stdout
        hm = re.search(r"<title>HOVER:(\d+)\|tags=(\d+)\|([^<]*)</title>", hr)
        if hm:
            print(f"  lookup rail faults: {hm.group(1)}, "
                  f"pressable symbols inside equations: {hm.group(2)}")
            if int(hm.group(1)):
                problems.append("lookup rail: " + hm.group(3))
            if int(hm.group(2)) < src.count('class="eq"'):
                problems.append(f"only {hm.group(2)} symbols in the math are pressable")
        else:
            problems.append("lookup rail probe did not report")
    finally:
        hprobe.unlink(missing_ok=True)

    # Nothing may be drawn outside the axes it belongs to. Every mark a plot makes goes inside
    # a clipped group; a cost line once ran off the top of its chart and over the sliders.
    clip = ("<script>window.addEventListener('load',function(){setTimeout(function(){"
            "var loose=0,charts=0;"
            "document.querySelectorAll('.panel svg').forEach(function(sv){"
            "if(!sv.querySelector('clipPath'))return;charts++;"
            "sv.querySelectorAll('circle,line,path').forEach(function(n){"
            "if(n.closest('clipPath'))return;"
            "if(n.getAttribute('class')==='gridline'||n.getAttribute('class')==='baseline')return;"
            "if(!n.closest('g[clip-path]'))loose++;});});"
            "document.title='CLIP:'+loose+'|'+charts;},6000);});</script>")
    cprobe = ROOT / "_verify_clip.html"
    cprobe.write_text(src.replace(anchor_tag, clip + PRE + anchor_tag, 1), encoding="utf-8")
    try:
        cr = run_chrome(cprobe.resolve().as_uri(), ["--dump-dom"]).stdout
        cm = re.search(r"<title>CLIP:(\d+)\|(\d+)</title>", cr)
        if cm:
            print(f"  marks drawn outside their own axes: {cm.group(1)} "
                  f"(across {cm.group(2)} charts)")
            if int(cm.group(1)):
                problems.append(f"{cm.group(1)} marks are drawn outside their chart's axes")
            if src.count('class="panel"') and int(cm.group(2)) == 0:
                problems.append("no clipped chart found")
        else:
            problems.append("clip probe did not report")
    finally:
        cprobe.unlink(missing_ok=True)

    # Reader notes (notes.js): open the drawer in the first chapter that has a paragraph, with a passage selected, save a note,
    # edit it, check it is listed under the section with its quote and kept in localStorage, delete it.
    nt = ("<script>window.addEventListener('load',function(){setTimeout(async function(){var r=[];try{"
          "var s=[].slice.call(document.querySelectorAll('main section')).find(function(x){return x.querySelector('p')});s.scrollIntoView();await new Promise(function(f){setTimeout(f,300)});"
          "var p=s.querySelector('p');var rg=document.createRange();rg.selectNodeContents(p);var sl=getSelection();sl.removeAllRanges();sl.addRange(rg);"
          "await new Promise(function(f){setTimeout(f,100)});"
          "document.querySelector('.nt-tab').click();var box=document.querySelector('.nt-box');if(box.hidden)r.push('drawer did not open');"
          "box.querySelector('.nt-new').value='probe note';box.querySelector('.nt-add').click();"
          "await new Promise(function(f){setTimeout(f,100)});"
          "var card=box.querySelector('.nt-card');if(!card)r.push('no card');"
          "else{if(!card.querySelector('.nt-quote'))r.push('no quote');"
          "var sec=card.parentElement.querySelector('.nt-sec');if(!sec||!/^#./.test(sec.getAttribute('href')))r.push('no section link');"
          "var ed=[...card.querySelectorAll('button')].find(function(b){return b.textContent==='Edit'});ed.click();"
          "card.querySelector('textarea').value='probe edited';ed.click();await new Promise(function(f){setTimeout(f,100)});"
          "if(box.querySelector('.nt-text').textContent!=='probe edited')r.push('edit lost');"
          "if(!/^1\\*/.test(card.textContent.trim()))r.push('card does not show its number 1*');}"
          # the note's number sits in the right margin, level with the passage it quotes
          "var mk=document.querySelector('.nt-mark');if(!mk)r.push('no margin mark');"
          "else{if(mk.textContent.trim()!=='1*')r.push('mark reads '+mk.textContent);"
          "var pr=p.getBoundingClientRect(),mr=mk.getBoundingClientRect();"
          "if(mr.left<pr.right-1)r.push('mark not right of the text');if(Math.abs(mr.top-pr.top)>30)r.push('mark not level with the passage');"
          "if(mr.right>innerWidth)r.push('mark off screen');}"
          "var k=Object.keys(localStorage).find(function(x){return x.indexOf('chaynikbook-notes:')===0});"
          "var st=k?JSON.parse(localStorage.getItem(k)):[];if(st.length!==1||st[0].text!=='probe edited')r.push('not stored');"
          "window.confirm=function(){return true};[...box.querySelectorAll('.nt-card button')].find(function(b){return b.textContent==='Delete'}).click();"
          "await new Promise(function(f){setTimeout(f,100)});if(JSON.parse(localStorage.getItem(k)).length!==0)r.push('delete not stored');"
          "if(document.querySelector('.nt-mark'))r.push('margin mark left after delete');"
          "}catch(e){r.push('error '+e.message)}document.title='NOTES:'+r.length+'|'+r.join(' ; ');},6000);});</script>")
    nprobe = ROOT / "_verify_notes.html"
    nprobe.write_text(src.replace(anchor_tag, nt + PRE + anchor_tag, 1), encoding="utf-8")
    try:
        nr = run_chrome(nprobe.resolve().as_uri(), ["--dump-dom"]).stdout
        nm = re.search(r"<title>NOTES:(\d+)\|([^<]*)</title>", nr)
        if nm:
            print(f"  notes drawer: {nm.group(1)} problems {nm.group(2)}")
            if int(nm.group(1)):
                problems.append("notes drawer: " + nm.group(2))
        else:
            problems.append("notes probe did not report")
    finally:
        nprobe.unlink(missing_ok=True)

    # Fixed axes. After the background sweep is done (its time is reported), for every panel and for up to
    # three options of each dropdown that keeps its own axes: each control alone at its ends, then six random
    # settings of all controls at once, must leave every tick label where it was. Labels that end up
    # pointing at a mark off the chart are listed, so a panel whose watched mark leaves the chart shows up.
    axes = r"""<script>window.addEventListener('load',function(){var tl=Math.round(performance.now());
      if(!document.querySelector('.panel')){document.title='AXES:0,0,'+tl+','+tl+',0||';return;}
      (function wait(){if(window.__axesReady!==true){setTimeout(wait,200);return;}var ts=Math.round(performance.now());
      var bad=[],off=[],n=0,moved=0,seed=7;
      function rnd(){seed=(seed*16807)%2147483647;return seed/2147483647;}
      function ticks(p){return [].slice.call(p.querySelectorAll('.chart text.tick')).map(function(t){return t.textContent;}).join('|');}
      function shared(p){return [].slice.call(p.querySelectorAll('input[type=range], select:not([data-axes=own])'));}
      function set(c,v){c.value=v;c.dispatchEvent(new Event(c.tagName==='SELECT'?'change':'input',{bubbles:true}));}
      function vals(c){return c.tagName==='SELECT'?[].slice.call(c.options).map(function(o){return o.value;}):[c.min,c.max];}
      function any(c){if(c.tagName==='SELECT')return c.options[Math.floor(rnd()*c.options.length)].value;
        return String(+c.min+rnd()*(c.max-c.min));}
      document.querySelectorAll('.panel').forEach(function(p,i){
        var h=p.querySelector('h4'),name=h?h.textContent:'panel '+i,rb=p.querySelector('.ptools .preset');
        if(!shared(p).length||!p.querySelector('.chart'))return;
        n++;var own=p.querySelector('select[data-axes=own]'),opts=own?[].slice.call(own.options).slice(0,3).map(function(o){return o.value;}):[null];
        var hit=null;
        opts.forEach(function(ov){if(hit)return;
          if(ov!==null){var o2=p.querySelector('select[data-axes=own]');if(o2.value!==ov)set(o2,ov);}
          var base=ticks(p),bv=shared(p).map(function(c){return c.value;});
          function back(){shared(p).forEach(function(c,k){if(c.value!==bv[k])set(c,bv[k]);});}
          function check(what){if(!hit&&ticks(p)!==base)hit=what;
            if(p.querySelector('.tag.offchart'))off.push(name+' ('+what+')');}
          shared(p).forEach(function(c,k){vals(c).forEach(function(v){var c2=shared(p)[k];if(!c2||hit)return;set(c2,v);
            check((ov?ov+' ':'')+(c2.closest('label')||{}).textContent.slice(0,24)+'='+v);});
            back();});
          for(var r=0;r<6&&!hit;r++){shared(p).forEach(function(c){set(c,any(c));});check((ov?ov+' ':'')+'random '+r);back();}
          if(rb)rb.click();});
        if(hit){moved++;bad.push(name+' ('+hit+')');}});
      var uoff=off.filter(function(x,j){return off.indexOf(x)===j;});
      document.title='AXES:'+[n,moved,tl,ts,uoff.length].join(',')+'|'+bad.slice(0,10).join(' ; ')+'||'+uoff.slice(0,40).join(' ; ');
      })();});</script>"""
    aprobe = ROOT / "_verify_axes.html"
    aprobe.write_text(src.replace(anchor_tag, axes + PRE + anchor_tag, 1), encoding="utf-8")
    try:
        ar = run_chrome(aprobe.resolve().as_uri(), ["--dump-dom"]).stdout
        am = re.search(r"<title>AXES:([\d,]+)\|([^<]*)\|\|([^<]*)</title>", ar)
        if am:
            na, nmv, tload, tsweep, noff = map(int, am.group(1).split(","))
            print(f"  fixed axes: {na} panels with controls and charts, {nmv} whose axes move; "
                  f"page loaded at {tload} ms, background sweep done at {tsweep} ms")
            print(f"  labels pointing off the chart at some setting: {noff}" + (": " + am.group(3) if noff else ""))
            if nmv:
                problems.append("axes move with the controls: " + am.group(2))
        else:
            problems.append("axes probe did not report")
    finally:
        aprobe.unlink(missing_ok=True)

    # The shared panel frame, pressed the way a reader would: every panel has a what-to-watch line;
    # Table shows a non-empty table and hides the drawings; Reset, after the first and last controls
    # are moved, brings every control back to its base value and the drawing back to what it was.
    # Then the bird's-eye maps: a full map lists what every step computes, every step chapter that is not
    # an aside ends with one map lighting exactly its own step, and every link points at an id in the page.
    frame = r"""<script>window.addEventListener('load',function(){setTimeout(function(){
      var o={panels:0,watch:0,table:0,reset:0,noctl:0,bad:[]};
      var STEPS=window[window.__G].manifest.filter(function(c){return c.step&&!c.aside;}).map(function(c){return c.id;});
      function nudge(c){
        if(c.tagName==='SELECT'){c.selectedIndex=c.selectedIndex===0?c.options.length-1:0;
          c.dispatchEvent(new Event('change',{bubbles:true}));}
        else{c.value=String(c.value===c.min?c.max:c.min);c.dispatchEvent(new Event('input',{bubbles:true}));}}
      function body(p){var q=p.cloneNode(true);q.querySelectorAll('.ptable').forEach(function(t){t.remove();});return q.textContent;}
      document.querySelectorAll('.panel').forEach(function(p,i){
        o.panels++;
        var h=p.querySelector('h4'),name=h?h.textContent:'panel '+i;
        var w=p.querySelector(':scope > .watch');
        if(w&&w.textContent.trim().length>30)o.watch++;else o.bad.push(name+': no what-to-watch line');
        var tb=p.querySelector('.ptools .ptoggle'),tv=p.querySelector(':scope > .ptable');
        if(!tb||!tv)o.bad.push(name+': no Table toggle');
        else{tb.click();
          var rows=tv.querySelectorAll('tbody tr').length,txt=tv.textContent;
          var hid=[].slice.call(p.querySelectorAll('.chart, .sankey')).every(function(c){return c.offsetParent===null;});
          if(!tv.hidden&&rows>0&&!/NaN|undefined|Infinity/.test(txt)&&hid)o.table++;
          else o.bad.push(name+': table view rows='+rows+' drawings hidden='+hid);
          tb.click();
          if(!tv.hidden)o.bad.push(name+': Table did not toggle back');}
        function ctl(){return [].slice.call(p.querySelectorAll('input, select'));}
        var cs=ctl(),rb=p.querySelector('.ptools .preset');
        if(!cs.length){o.noctl++;if(rb)o.bad.push(name+': Reset with nothing to reset');return;}
        if(!rb){o.bad.push(name+': no Reset');return;}
        var base=cs.map(function(c){return c.value;}),snap=body(p);
        (cs.length>1?[0,cs.length-1]:[0]).forEach(function(k){var c=ctl()[k];if(c)nudge(c);});
        if(!ctl().some(function(c,k){return c.value!==base[k];}))o.bad.push(name+': could not move a control');
        rb.click();
        var back=ctl().map(function(c){return c.value;});
        if(back.join('|')!==base.join('|'))o.bad.push(name+': Reset left '+back.join(',')+' for '+base.join(','));
        else if(body(p)!==snap)o.bad.push(name+': Reset restored the controls and left a different drawing');
        else o.reset++;});
      var ids={};document.querySelectorAll('[id]').forEach(function(e){ids[e.id]=1;});
      var maps=[].slice.call(document.querySelectorAll('figure.map')),links=0,dead=0,lit=0,where=[];
      maps.forEach(function(m){
        var sec=m.closest('section'),sid=sec?sec.id:'none',on=m.querySelectorAll('li.lit');
        where.push(sid);
        m.querySelectorAll('a').forEach(function(a){links++;var hr=a.getAttribute('href')||'';
          if(hr[0]!=='#'||!ids[hr.slice(1)])dead++;});
        if(m.getBoundingClientRect().height<40+30*m.querySelectorAll('li').length)o.bad.push(sid+' map did not render, height '+Math.round(m.getBoundingClientRect().height));
        if(!m.dataset.lit){if(on.length)o.bad.push(sid+' full map lights a step');
          if(m.querySelectorAll('.mdoes').length<STEPS.length)o.bad.push(sid+' full map lacks what each step computes');return;}
        if(on.length!==1||on[0].querySelector('a').getAttribute('href')!=='#'+sid)o.bad.push(sid+' map lights '+on.length+' steps, not its own');
        else{lit++;var a=on[0].querySelector('a'),other=m.querySelector('li:not(.lit) a');
          if(other&&getComputedStyle(a).backgroundColor===getComputedStyle(other).backgroundColor)o.bad.push(sid+' lit step looks like the others');}
        if(sec.lastElementChild!==m)o.bad.push(sid+' map is not at the chapter end');});
      if(STEPS.length&&!maps.some(function(m){return !m.dataset.lit;}))o.bad.push('no full map although the manifest has steps');
      STEPS.forEach(function(s){if(maps.filter(function(m){var sec=m.closest('section');return sec&&sec.id===s&&m.dataset.lit===s;}).length!==1)o.bad.push(s+' does not end with a map lighting its step');});
      document.title='FRAME:'+[o.panels,o.watch,o.table,o.reset,o.noctl,maps.length,lit,links,dead].join(',')+'|'+o.bad.slice(0,8).join(' ; ');
    },7000);});</script>"""
    fprobe = ROOT / "_verify_frame.html"
    fprobe.write_text(src.replace(anchor_tag, frame + PRE + anchor_tag, 1), encoding="utf-8")
    try:
        fr = run_chrome(fprobe.resolve().as_uri(), ["--dump-dom"]).stdout
        fm = re.search(r"<title>FRAME:([\d,]+)\|([^<]*)</title>", fr)
        if fm:
            np_, nw, nt, nr, nc, nm, nl, nlink, ndead = map(int, fm.group(1).split(","))
            print(f"  panel frame: {np_} panels, what-to-watch {nw}, table view {nt}, "
                  f"reset {nr} (+{nc} with no controls to reset)")
            print(f"  map: {nm} maps, {nl} with their own step lit, {nlink} links, {ndead} dead")
            if fm.group(2):
                problems.append("panel frame or map: " + fm.group(2))
            if not (nw == nt == np_ and nr + nc == np_):
                problems.append("panel frame incomplete")
            n_steps = sum(1 for c in MAN if c.get("step") and not c.get("aside"))
            if nm != src.count('<figure class="map"') or nl != n_steps or ndead:
                problems.append("map incomplete")
        else:
            problems.append("panel frame probe did not report")
    finally:
        fprobe.unlink(missing_ok=True)

    # Predict then test, pressed the way a reader would: every chapter (but those with "checks": false in the
    # manifest) holds book.json's checks_per_chapter [min, max] checks; each of the three
    # buttons reveals an answer with no error, exactly one of them is called right, an engine answer shows two
    # numbers and starts from the exported case's value, every link lands on an id, and "no change" is the answer
    # at most once per chapter
    checks = r"""<script>window.addEventListener('load',function(){setTimeout(function(){
      var B=window[window.__G],E=window.ENGINE,want=B.manifest.filter(function(c){return c.checks!==false;}).map(function(c){return c.id;}),
        lim=B.book.checks_per_chapter||[1,5],per={},eng=0,rev=0,links=0,bad=[];
      var ids={};document.querySelectorAll('[id]').forEach(function(e){ids[e.id]=1;});
      var D=B.data;
      function at(o,p){return p.split('.').reduce(function(x,k){return x==null?x:x[k];},o);}
      document.querySelectorAll('.check').forEach(function(c,i){
        var sec=c.closest('section'),sid=sec?sec.id:'none',spec=JSON.parse(c.dataset.check||'{}'),name=sid+' '+(spec.id||i);
        per[sid]=per[sid]||{n:0,same:0};per[sid].n++;
        var bs=[].slice.call(c.querySelectorAll('.controls button')),ans=c.querySelector('.answer'),right=0;
        if(bs.length!==3||!ans){bad.push(name+': not mounted');return;}
        bs.forEach(function(b){b.click();var t=ans.textContent;
          if(t.trim().length<40||/check error|NaN|undefined/.test(t))bad.push(name+' '+b.textContent+': answer '+t.slice(0,60));
          if(ans.querySelector('.ok'))right++;});
        if(right!==1)bad.push(name+': '+right+' buttons called right');
        if(ans.dataset.truth==='no change')per[sid].same++;
        if(ans.dataset.kind==='engine'){eng++;var v0=+ans.dataset.v0,v1=+ans.dataset.v1;
          if(ans.dataset.truth!==spec.expect)bad.push(name+': engine says '+ans.dataset.truth+', the text explains '+spec.expect);
          if(!isFinite(v0)||!isFinite(v1))bad.push(name+': engine answer not a number');
          var p=E&&E.CHECK_BASE&&E.CHECK_BASE[spec.out],x=p?at(D,p.replace('{case}',String(spec.case))):undefined;
          if(typeof x!=='number'||!isFinite(x))bad.push(name+': no exported base value for '+spec.out+' (ENGINE.CHECK_BASE '+(p||'has no entry')+')');
          else if(Math.abs(x-v0)>1e-8*Math.max(1,Math.abs(x)))bad.push(name+': base '+v0+' against exported '+x);}
        else rev++;
        ans.querySelectorAll('a').forEach(function(a){links++;var h=a.getAttribute('href')||'';if(h[0]!=='#'||!ids[h.slice(1)])bad.push(name+': dead link '+h);});});
      var counts=want.map(function(s){var o=per[s]||{n:0,same:0};
        if(o.n<lim[0]||o.n>lim[1])bad.push(s+' has '+o.n+' checks');if(o.same>1)bad.push(s+' answers no change '+o.same+' times');return s+'='+o.n;});
      document.title='CHECKS:'+[eng,rev,links].join(',')+'|'+counts.join(' ')+'|'+bad.slice(0,8).join(' ; ');
    },7000);});</script>"""
    kprobe = ROOT / "_verify_checks.html"
    kprobe.write_text(src.replace(anchor_tag, checks + PRE + anchor_tag, 1), encoding="utf-8")
    try:
        kr = run_chrome(kprobe.resolve().as_uri(), ["--dump-dom"]).stdout
        km = re.search(r"<title>CHECKS:(\d+),(\d+),(\d+)\|([^|<]*)\|([^<]*)</title>", kr)
        if km:
            print(f"  checks: {int(km.group(1)) + int(km.group(2))} ({km.group(1)} computed by the engine, "
                  f"{km.group(2)} revealed), {km.group(3)} links; per chapter {km.group(4)}")
            if km.group(5):
                problems.append("checks: " + km.group(5))
        else:
            problems.append("checks probe did not report")
    finally:
        kprobe.unlink(missing_ok=True)

    # at phone width the map, the panel heads and every panel control fit their column, and the page itself does
    # not scroll sideways: an equation or a wide table scrolls inside its own box. Headless Chrome will not make a
    # window narrower than about 500px, so the page is loaded in a 390px iframe, which is a real 390px viewport,
    # and reports to the wrapper's title
    narrow = ("<script>window.addEventListener('load',function(){setTimeout(function(){"
              "var bad=0;document.querySelectorAll('figure.map, .phead').forEach(function(e){"
              "if(e.scrollWidth>e.clientWidth+1||e.getBoundingClientRect().right>innerWidth+1)bad++;});"
              "document.querySelectorAll('.panel .controls select, .panel .controls input').forEach(function(e){"
              "if(e.getBoundingClientRect().right>e.closest('.panel').getBoundingClientRect().right+1)bad++;});"
              "parent.document.title='NARROW:'+bad+'|'+(document.documentElement.scrollWidth-innerWidth)+'|'+innerWidth;},6000);});</script>")
    nprobe = ROOT / "_verify_narrow.html"
    nprobe.write_text(src.replace(anchor_tag, narrow + PRE + anchor_tag, 1), encoding="utf-8")
    nwrap = ROOT / "_verify_narrow_wrap.html"
    nwrap.write_text('<!doctype html><title>none</title><body style="margin:0"><iframe src="_verify_narrow.html" '
                     'style="width:390px;height:900px;border:0"></iframe>', encoding="utf-8")
    try:
        nr_ = run_chrome(nwrap.resolve().as_uri(), ["--window-size=800,1000", "--allow-file-access-from-files",
                                                     "--dump-dom"]).stdout
        nm_ = re.search(r"<title>NARROW:(\d+)\|(-?\d+)\|390</title>", nr_)
        if nm_:
            print(f"  at 390px: maps, panel heads and controls that overflow {nm_.group(1)}; "
                  f"page wider than the window by {max(0, int(nm_.group(2)))}px")
            if int(nm_.group(1)):
                problems.append(f"{nm_.group(1)} maps, panel heads or panel controls overflow at 390px")
            if int(nm_.group(2)) > 0:
                problems.append(f"at 390px the page is {nm_.group(2)}px wider than the window")
        else:
            problems.append("narrow probe did not report")
    finally:
        nprobe.unlink(missing_ok=True)
        nwrap.unlink(missing_ok=True)

    for what, mark in (("panels", 'class="panel"'), ("maps", '<figure class="map"'), ("checks", 'class="check"')):
        if mark not in src:
            print(f"  skip {what}: the book has none")
    raw = run_chrome(url, ["--dump-dom"]).stdout
    # the page inlines its own scripts, so scan the rendered body only: the source of
    # panels.js contains the very strings that signal a failure
    dom = re.sub(r"<script.*?</script>", " ", raw, flags=re.S)

    m = re.search(r'id="engine-badge"[^>]*>([^<]*)<', dom)
    badge = m.group(1).strip() if m else "missing"
    if (ROOT / "engine.js").exists():
        print(f"  engine badge: {badge}")
        if not re.fullmatch(r"engine: (\d+)/\1", badge):
            problems.append(f"engine badge reads {badge!r}")
    else:
        print("  skip engine badge: the book has no engine.js")
        if m:
            problems.append("engine badge shown although the book has no engine.js")

    n_panels = dom.count('<div class="panel"')
    n_svg = len(re.findall(r"<svg", dom))
    n_err = len(re.findall(r"panel error|unknown panel type|unknown output", dom))
    print(f"  panels {n_panels}, drawings {n_svg}, panel errors {n_err}")
    if n_err:
        for snip in set(re.findall(r"panel error: [^<]*|unknown panel type [^<]*|unknown output [^<]*", dom)):
            problems.append(snip)
    if n_panels and n_svg == 0:
        problems.append("no chart was drawn")
    # MathJax draws a TeX error as yellow text in place of the equation (data-mjx-error)
    tex_err = set(re.findall(r'data-mjx-error="([^"]*)"', dom))
    print(f"  equations MathJax could not typeset: {len(tex_err)}")
    problems += [f"TeX error: {e}" for e in tex_err]

    # stray markup means text a reader would see, so look at text content only: tag
    # attributes legitimately carry JSON with nested brackets
    text = re.sub(r"<[^>]+>", " ", dom)
    for stray in ["{{", "```", "[[", "<div class", "NaN", "undefined", "Infinity"]:
        if stray in text:
            problems.append(f"unrendered markup visible in the page: {stray}")
    if "data-sym" not in dom:
        problems.append("no glossary symbols in the page")

    if problems:
        print()
        for p in problems:
            print("  RENDER " + p)
        sys.exit(1)
    print("  render ok")


if __name__ == "__main__":
    main()
