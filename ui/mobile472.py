"""First-party Streamlit v2 components: mobile sports rating and inbox.

Trusted static HTML/CSS/JS only. External text is passed exclusively through
JSON data and inserted with textContent; never template interpolation into HTML.
"""
from __future__ import annotations
import streamlit as st

BOARD_CSS = r'''
:host{display:block;color:#23312e;font-family:system-ui,-apple-system,sans-serif}
*{box-sizing:border-box}.board{background:#fff;border:1px solid #e1e5e1;border-radius:15px;overflow:hidden;box-shadow:0 9px 28px #183d3020}
.hero{background:#233b32;color:#f7faf6;padding:23px 23px 18px}
.kicker{font-size:10px;letter-spacing:2px;color:#b0cbbd;font-weight:760;text-transform:uppercase}
.hero h2{font:600 clamp(24px,5vw,32px)/1.14 Georgia,serif;margin:9px 0}.hero p{font-size:13px;color:#c5d2ca;margin:0;line-height:1.5}
.content{padding:22px}.section{font-size:10px;letter-spacing:1.5px;font-weight:780;color:#ad564a;margin:0 0 12px;text-transform:uppercase}
.rating{display:grid;grid-template-columns:83px 1fr;gap:17px;align-items:center}
.value{font:700 64px/1 Georgia,serif;white-space:nowrap}.value small{font:400 14px system-ui;color:#89978e}
.range{width:100%;accent-color:#a44239;cursor:pointer;min-height:35px}.anchors{display:flex;justify-content:space-between;font-size:11px;color:#788780}
.muted{font-size:12px;color:#788780}.rule{border:0;border-top:1px solid #e5e9e5;margin:23px 0}
.tabline{display:flex;gap:15px;align-items:center;margin-bottom:16px;border-bottom:1px solid #e5e9e5}
.tab{border:0;background:transparent;color:#718178;font-size:13px;padding:0 0 12px;font-weight:650;border-bottom:2px solid transparent;cursor:pointer}
.tab.active{color:#973d35;border-color:#973d35}.list{border:1px solid #e4e8e3;border-radius:11px;overflow:hidden}
.player{border:0;border-bottom:1px solid #edf0ec;background:#fff;width:100%;padding:12px;display:flex;justify-content:space-between;align-items:center;gap:12px;text-align:left;cursor:pointer;min-height:63px}
.player:last-child{border-bottom:0}.player:hover,.player.active{background:#f9f5f2}.pname{font-weight:730;font-size:13px;display:block}.pmeta{font-size:11px;color:#81918a;display:block;margin-top:3px}
.pnumber{background:#f3f5f2;border-radius:8px;min-width:35px;text-align:center;padding:8px;font-weight:730;font-size:12px}
.pscore{font:700 20px Georgia,serif;color:#9b4038}.editor{margin-top:17px;padding:20px;background:#f6f7f3;border:1px solid #e5e9e3;border-radius:11px}
.editor h3{font:600 21px Georgia,serif;margin:0 0 8px}.editor .rating{margin-top:12px}
textarea{display:block;width:100%;border:1px solid #d7deda;border-radius:9px;padding:12px;font:14px/1.45 system-ui;resize:vertical;min-height:80px;background:white;color:#23312e;margin:14px 0 10px}
label.check{display:flex;gap:10px;align-items:center;font-size:13px;color:#394e43}.check input{accent-color:#9b4038;width:18px;height:18px}
.foot{display:flex;gap:12px;align-items:center;justify-content:space-between;margin-top:20px;flex-wrap:wrap}
.save{border:0;border-radius:8px;background:#973d35;color:#fff;min-height:48px;padding:10px 22px;font-weight:750;font-size:14px;cursor:pointer}
.save:hover{background:#772f29}.soft{border:0;background:transparent;text-decoration:underline;color:#973d35;padding:8px;cursor:pointer;font-size:12px}
.notice{font-size:12px;color:#596b60;line-height:1.5}.error{color:#a12820;font-size:13px;margin-top:9px}
button:focus-visible,input:focus-visible,textarea:focus-visible{outline:3px solid #c88e59;outline-offset:2px}
@media(max-width:620px){.hero{padding:19px 17px}.content{padding:18px 15px}.value{font-size:55px}.rating{grid-template-columns:70px 1fr;gap:10px}.editor{padding:15px}.foot{display:block}.save{width:100%;margin-top:12px}}
'''

BOARD_HTML = '<section class="board"><div class="hero"><div class="kicker">ÁREA TÉCNICA · VALORACIÓN</div><h2 id="fixture">Partido</h2><p id="subtitle"></p></div><div class="content"><div class="section">Puntúa a los jugadores que hayas visto</div><div class="tabline"><button class="tab active" id="own-tab" type="button"></button><button class="tab" id="rival-tab" type="button"></button></div><p class="muted" id="roster-hint"></p><div class="list" id="players"></div><div id="player-editor"></div><div class="foot"><div class="notice">Las notas son privadas para el autor y Dirección Deportiva.<br/>Solo los favoritos marcados se proponen expresamente a Aarón.</div><button class="save" id="save" type="button">Guardar valoración</button></div><div class="error" id="error" role="alert"></div></div></section>'

BOARD_JS = r'''
export default function({parentElement, data, setTriggerValue}) {
 const root=parentElement, val=(x)=>x==null?'':String(x);
 const txt=(node,text)=>{node.textContent=val(text);return node;};
 const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)txt(n,text);return n;};
 const src=data||{}, initial=src.initial||{};
 const items={};
 for(const [key,obj] of Object.entries(initial))items[key]={score:obj.score??null,comment:obj.comment||'',favorite:!!obj.favorite,proposed:!!obj.favorite,wasSaved:true};
 let active='own', selected=null;
 txt(root.querySelector('#fixture'),src.fixture||'Partido');txt(root.querySelector('#subtitle'),src.subtitle||'');
 txt(root.querySelector('#own-tab'),src.own_name||'Noname');txt(root.querySelector('#rival-tab'),src.rival_name||'Rival');
 const own=src.own||[],rival=src.rival||[];
 const noteFor=(p,side)=>{const k=side+':'+p.key;if(!items[k])items[k]={score:null,comment:'',favorite:false};return items[k]};
 const scoreControl=(value,onChange)=>{
   const wrap=el('div','rating'), n=el('div','value'), right=el('div','');
   const r=el('input','range');r.type='range';r.min='1';r.max='10';r.step='1';r.value=value??7;
   r.setAttribute('aria-label','Seleccionar nota de 1 a 10');
   const render=(v)=>{n.textContent=v==null?'—':val(v);n.appendChild(el('small','', ' /10'))};render(value);
   r.addEventListener('input',()=>{render(+r.value);onChange(+r.value)});
   right.appendChild(r);const anchors=el('div','anchors');anchors.appendChild(el('span','', '1 · Muy mal'));anchors.appendChild(el('span','', '10 · Excelente'));right.appendChild(anchors);
   wrap.append(n,right);return wrap;
 };
 function storeEditor(){const e=root.querySelector('#player-editor');if(!selected||!e)return;const state=noteFor(selected.p,selected.side);const comment=e.querySelector('textarea');if(comment)state.comment=comment.value;const fav=e.querySelector('input[type=checkbox]');if(fav)state.favorite=fav.checked}
 function renderRows(){const list=root.querySelector('#players');list.replaceChildren();const side=active,all=side==='own'?own:rival;
    txt(root.querySelector('#roster-hint'),side==='own'?src.own_hint:src.rival_hint);
    root.querySelector('#own-tab').classList.toggle('active',side==='own');root.querySelector('#rival-tab').classList.toggle('active',side==='rival');
    if(!all.length){list.appendChild(el('div','player muted',side==='own'?'Aún no hay jugadores cargados. Pega la alineación desde este partido.':'Todavía no hay datos disponibles.'));return}
    for(const p of all){const k=side+':'+p.key,st=noteFor(p,side);
      const row=el('button','player');row.type='button';row.classList.toggle('active',selected?.side===side&&selected?.p.key===p.key);
      const meta=el('div','');meta.appendChild(el('span','pname',p.name));meta.appendChild(el('span','pmeta',[(p.position||''),(p.status||'')].filter(Boolean).join(' · ')));
      const tail=el('div','');tail.style.display='flex';tail.style.alignItems='center';tail.style.gap='11px';
      if(st.score!=null)tail.appendChild(el('span','pscore',val(st.score)));else if(st.comment)tail.appendChild(el('span','pmeta','✎'));
      tail.appendChild(el('span','pnumber',p.dorsal==null?'›':'#'+val(p.dorsal)));row.append(meta,tail);
      row.onclick=()=>{storeEditor();selected={side,p};renderRows();renderEditor()};list.appendChild(row);
    }
 }
 function renderEditor(){const area=root.querySelector('#player-editor');area.replaceChildren();if(!selected)return;
   const p=selected.p, s=noteFor(p,selected.side),box=el('div','editor');
   box.appendChild(el('div','section','VALORACIÓN INDIVIDUAL'));box.appendChild(el('h3','',p.name));box.appendChild(scoreControl(s.score,v=>s.score=v));
   const clear=el('button','soft','Sin nota individual');clear.type='button';clear.onclick=()=>{s.score=null;renderEditor()};box.appendChild(clear);
   const ta=el('textarea','');ta.placeholder='Observación breve (opcional)';ta.value=s.comment;ta.maxLength=1200;box.appendChild(ta);
   const lab=el('label','check'),ch=el('input','');ch.type='checkbox';ch.checked=s.favorite;ch.disabled=!!s.proposed;lab.append(ch,el('span','', s.proposed?'Ya propuesto a Aarón · decisión pendiente de DD':'Destacar expresamente para Aarón'));box.appendChild(lab);
   const close=el('button','soft','Cerrar jugador');close.type='button';close.onclick=()=>{storeEditor();selected=null;renderRows();renderEditor()};box.appendChild(close);
   area.appendChild(box);
 }
 root.querySelector('#own-tab').onclick=()=>{storeEditor();active='own';selected=null;renderRows();renderEditor()};
 root.querySelector('#rival-tab').onclick=()=>{storeEditor();active='rival';selected=null;renderRows();renderEditor()};
 renderRows();
 root.querySelector('#save').onclick=()=>{
    storeEditor();const err=root.querySelector('#error');err.textContent='';
    const packet={team_score:null,players:[],cleared:[],formation:src.formation||'4-2-3-1'};
    for(const side of ['own','rival'])for(const p of (side==='own'?own:rival)){
      const s=items[side+':'+p.key];if(s&&(s.score!=null||s.comment?.trim()||s.favorite)){
        if(s.favorite&&s.score==null&&!s.comment.trim())s.comment='Jugador señalado como interesante';
        packet.players.push({side,key:p.key,score:s.score,comment:(s.comment||'').trim(),favorite:!!s.favorite});
      } else if(s?.wasSaved){packet.cleared.push({side,key:p.key});}
    }
    if(!packet.players.length&&!packet.cleared.length){err.textContent='No hay cambios que guardar.';return}
    setTriggerValue('save',packet);
 };
}
'''

INBOX_HTML = '<div class="inbox"><header><span>NOVEDADES</span><strong id="qty"></strong></header><div id="items"></div></div>'
INBOX_CSS = r'''
:host{display:block;font-family:system-ui;color:#22312d}*{box-sizing:border-box}.inbox{background:white;border:1px solid #e3e6e1;border-radius:13px;overflow:hidden}
header{display:flex;justify-content:space-between;align-items:center;padding:17px 18px;border-bottom:1px solid #e5e9e5;font-size:11px;letter-spacing:1.6px;font-weight:750;color:#9a483e}header strong{color:#5e6c61;font-size:12px;letter-spacing:0}
.item{display:flex;align-items:center;gap:9px;padding:13px 16px;border-bottom:1px solid #edf0ed;min-height:67px}
.item:last-child{border-bottom:0}.item:hover{background:#faf8f5}.main{flex:1;min-width:0;border:0;background:none;text-align:left;cursor:pointer;color:inherit;padding:5px}
.main strong{display:block;font-size:13px}.main small{display:block;color:#839188;font-size:11px;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.date{font-size:10px;color:#88978e;white-space:nowrap}.action{border:0;background:#f6f7f4;color:#66786a;width:35px;height:35px;border-radius:8px;cursor:pointer;font-size:18px}.action:hover{background:#efeae4;color:#9a483e}.unread{width:7px;height:7px;border-radius:50%;background:#a04439;flex-shrink:0}.none{padding:24px;color:#78877e;font-size:13px}
button:focus-visible{outline:3px solid #c88e59;outline-offset:2px}@media(max-width:600px){.item{padding:10px 8px}.date{display:none}.action{width:34px;height:38px}}
'''
INBOX_JS = r'''
export default function({parentElement,data,setTriggerValue}){
 const root=parentElement;root.querySelector('#items').replaceChildren();const entries=data?.items||[];
 root.querySelector('#qty').textContent=String(entries.length)+' elementos';
 const node=(tag,cls,txt)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(txt!==undefined)n.textContent=String(txt??'');return n};
 if(!entries.length){root.querySelector('#items').append(node('div','none','No tienes novedades en esta bandeja.'));return}
 entries.forEach(x=>{const row=node('div','item');if(!x.seen)row.append(node('span','unread'));
 const main=node('button','main');main.type='button';main.append(node('strong','',x.title),node('small','',x.detail));main.onclick=()=>setTriggerValue('action',{id:x.id,action:'open'});
 const date=node('span','date',x.date);row.append(main,date);
 const save=node('button','action',x.saved?'★':'☆');save.type='button';save.title=x.saved?'Quitar de guardados':'Guardar para después';save.setAttribute('aria-label',save.title);save.onclick=()=>setTriggerValue('action',{id:x.id,action:x.saved?'unsave':'save'});
 const seen=node('button','action',x.seen?'↶':'×');seen.type='button';seen.title=x.seen?'Volver a marcar como nuevo':'Marcar como visto';seen.setAttribute('aria-label',seen.title);seen.onclick=()=>setTriggerValue('action',{id:x.id,action:x.seen?'unsee':'seen'});
 row.append(save,seen);root.querySelector('#items').appendChild(row)})
}
'''

# Registration happens once per process. No untrusted database text in HTML or JS.
scoreboard_component = st.components.v2.component('noname_mobile_scoreboard_472',html=BOARD_HTML,css=BOARD_CSS,js=BOARD_JS)
inbox_component = st.components.v2.component('noname_inbox_472',html=INBOX_HTML,css=INBOX_CSS,js=INBOX_JS)

PLAYERLIST_HTML = '<div class="list" id="results" role="list"></div>'
PLAYERLIST_CSS = r'''
:host{display:block;font-family:system-ui;color:#26372f}.list{border:1px solid #dfe5df;border-radius:10px;overflow:hidden;background:#fff}
.entry{display:flex;gap:12px;align-items:center;justify-content:space-between;border:0;border-bottom:1px solid #ebeeea;background:white;width:100%;text-align:left;padding:13px 16px;cursor:pointer;min-height:58px}
.entry:last-child{border-bottom:0}.entry:hover,.entry.selected{background:#f9f2ee}.entry strong{display:block;font-size:13px}.entry small{display:block;color:#7a8980;font-size:11px;margin-top:3px}.chev{font-size:21px;color:#a0443a}.none{padding:16px;color:#7a8980;font-size:13px}
.entry:focus-visible{outline:3px solid #c88e59;outline-offset:-3px}
'''
PLAYERLIST_JS = r'''
export default function({parentElement,data,setTriggerValue}){
 const box=parentElement.querySelector('#results');box.replaceChildren();
 const items=data?.items||[];
 if(!items.length){const n=document.createElement('p');n.className='none';n.textContent='No se encontraron resultados';box.appendChild(n);return;}
 for(const item of items){const row=document.createElement('button');row.type='button';row.className='entry';
 if(item.id===data.selected)row.classList.add('selected');
 const content=document.createElement('span');const title=document.createElement('strong');title.textContent=item.name||'';
 const desc=document.createElement('small');desc.textContent=item.detail||'';content.append(title,desc);
 const right=document.createElement('span');right.className='chev';right.textContent='›';row.append(content,right);
 row.onclick=()=>setTriggerValue('select',item.id);box.appendChild(row);}
}
'''
player_list_component=st.components.v2.component('noname_player_list_472',html=PLAYERLIST_HTML,css=PLAYERLIST_CSS,js=PLAYERLIST_JS)

POST_HTML = '''<div class="post"><div class="header"><div class="eyebrow">CUADERNO TÉCNICO · ANÁLISIS</div><h2 id="title">Postpartido</h2><p>No hace falta completar todos los apartados. Guarda tu borrador o envía el informe cuando termines.</p></div><div class="work"><label id="own-label" for="own-note">Noname · Observación</label><textarea id="own-note" placeholder="¿Qué viste? ¿Qué destacarías?" maxlength="12000"></textarea><label id="rival-label" for="rival-note">Rival · Observación</label><textarea id="rival-note" placeholder="Lo más relevante del otro equipo…" maxlength="12000"></textarea><details><summary>Otros apuntes y datos (opcional)</summary><div id="optional"></div></details><div class="actions"><button id="draft" class="secondary" type="button">Guardar borrador privado</button><button id="publish" class="primary" type="button">Compartir con Aarón</button></div><p id="post-error" role="alert"></p></div></div>'''
POST_CSS = r'''
:host{display:block;font-family:system-ui;color:#26362f}*{box-sizing:border-box}.post{background:white;border:1px solid #e1e6e0;border-radius:14px;overflow:hidden}
.header{background:#243b33;color:#fff;padding:23px}.eyebrow{color:#d5a19a;font-size:10px;font-weight:750;letter-spacing:1.5px}
.header h2{font:600 27px Georgia,serif;margin:8px 0}.header p{font-size:13px;color:#c2cec5;line-height:1.5;margin:0}
.work{padding:24px}.work label{display:block;font-size:13px;font-weight:700;margin:0 0 9px}.work textarea,.work input{display:block;width:100%;padding:12px 13px;border:1px solid #dce3dc;border-radius:8px;font:14px/1.5 system-ui;color:#27392f;background:#fff;margin:0 0 22px}
.work textarea{resize:vertical;min-height:130px}.work input[type=number]{max-width:170px;min-height:43px}
.work textarea:focus-visible,.work input:focus-visible,button:focus-visible,summary:focus-visible{outline:3px solid #c88e59;outline-offset:2px}
details{border:1px solid #e2e7e2;border-radius:9px;margin-bottom:20px;padding:13px 15px}
summary{font-size:13px;font-weight:690;cursor:pointer;color:#9a4339}#optional{margin:16px 0 0}
.actions{display:flex;gap:12px;flex-wrap:wrap;justify-content:flex-end}.actions button{border-radius:8px;min-height:48px;padding:12px 20px;font-size:13px;font-weight:730;cursor:pointer}
.primary{background:#a0443a;color:#fff;border:1px solid #a0443a}.primary:hover{background:#832e27}.secondary{border:1px solid #d6deda;background:#fff;color:#354f42}
#post-error{color:#9f3028;font-size:12px;min-height:0}@media(max-width:620px){.header{padding:19px 16px}.work{padding:17px 15px}.actions{display:block}.actions button{width:100%;margin-bottom:10px}.work textarea{min-height:110px}}
'''
POST_JS = r'''
export default function({parentElement,data,setTriggerValue}){
 const root=parentElement,src=data||{},saved=src.old||{};
 const get=id=>root.querySelector('#'+id),set=(id,val)=>{get(id).textContent=val||''};
 set('title',src.title||'Postpartido');set('own-label',src.own_label||'Noname');set('rival-label',src.rival_label||'Rival');
 get('own-note').value=saved.equipo_propio||'';get('rival-note').value=saved.rival||'';
 const opts=[['nota_propio','Nota del primer equipo (1–10)','number'],['nota_rival','Nota del segundo equipo (1–10)','number'],
 ['conclusion','Conclusión','textarea'],['fortalezas','Fortalezas','textarea'],['debilidades','Debilidades','textarea'],
 ['datos_individuales','Estadísticas o pases','textarea'],['cortes_video','Referencia a cortes de vídeo','text']];
 for(const [id,label,type] of opts){const l=document.createElement('label');l.setAttribute('for',id);l.textContent=label;
 const field=document.createElement(type==='textarea'?'textarea':'input');field.id=id;
 if(type!=='textarea')field.type=type;if(type==='number'){field.min='1';field.max='10';field.step='1'}
 field.value=saved[id]??'';get('optional').append(l,field);
 }
 function submit(publish){const values={equipo_propio:get('own-note').value.trim(),rival:get('rival-note').value.trim()};
 for(const [id,,type] of opts){const raw=get(id).value.trim();if(type==='number'){
   if(raw&&(!/^\d+$/.test(raw)||Number(raw)<1||Number(raw)>10)){get('post-error').textContent='Las notas deben estar entre 1 y 10.';return;}
   values[id]=raw?Number(raw):null;
 }else values[id]=raw;}
 if(!Object.values(values).some(v=>v!==null&&String(v).trim())){get('post-error').textContent='Escribe una observación o una nota antes de guardar.';return}
 get('post-error').textContent='';setTriggerValue('save',{publish,values});}
 get('draft').onclick=()=>submit(false);get('publish').onclick=()=>submit(true);
}
'''
postmatch_component=st.components.v2.component('noname_postmatch_472',html=POST_HTML,css=POST_CSS,js=POST_JS)
