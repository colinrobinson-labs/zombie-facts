(()=>{
const $=id=>document.getElementById(id)||document.createElement("div");
const has=id=>!!document.getElementById(id);
const BASE=new URL("../",document.currentScript&&document.currentScript.src||location.href).href;
/* old one-page links (/#register etc.) now live on their own pages */
(()=>{const m={"#worst":"/","#register":"/register/","#desk":"/desk/","#autopsy":"/autopsy/","#check":"/check/","#method":"/method/"}[location.hash];if(m&&location.pathname!==m)location.replace(m)})();
const TPL=`A note from Zombie Facts, a free public tracker of retracted research.

The article "{PAGE}" ({SECTION}) cites
  {TITLE}
  https://doi.org/{DOI}
which was retracted on {DATE}: https://doi.org/{NOTICE}

It supports this sentence: "{SAID}"

If the citation is there to discuss the retraction, nothing to do. Otherwise it may need replacing, or marking with {{tl|Retracted}}. ~~~~`;
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fmt=n=>n==null?"—":n>=1e6?(n/1e6).toFixed(n>=1e7?0:1)+"M":n>=1e4?Math.round(n/1e3)+"K":n.toLocaleString("en-US");
const full=n=>(n||0).toLocaleString("en-US");
const NOW=new Date(),NY=NOW.getFullYear()+NOW.getMonth()/12;
const yr=s=>s?+s.slice(0,4)+((+s.slice(5,7)||1)-1)/12:null;
const wurl=(t,sec)=>"https://en.wikipedia.org/wiki/"+encodeURIComponent(t.replace(/ /g,"_"))+(sec&&sec!=="Lead"?"#"+encodeURIComponent(sec.replace(/ /g,"_")):"");
const cleanT=t=>(t||"").replace(/^(RETRACTED( ARTICLE)?|WITHDRAWN|Retracted)\s*:\s*/i,"").replace(/\s+/g," ").trim();
const toast=m=>{const e=$("toast");e.textContent=m;e.classList.add("on");clearTimeout(e._t);e._t=setTimeout(()=>e.classList.remove("on"),1800)};
$("edDate").textContent=NOW.toLocaleDateString("en-US",innerWidth<641?{month:"short",day:"numeric",year:"numeric"}:{weekday:"long",month:"long",day:"numeric",year:"numeric"});
$("theme").onclick=()=>{const r=document.documentElement,d=r.dataset.theme?r.dataset.theme==="dark":matchMedia("(prefers-color-scheme:dark)").matches;r.dataset.theme=d?"light":"dark";try{localStorage.zfTheme=r.dataset.theme}catch(_){}};
try{if(localStorage.zfTheme)document.documentElement.dataset.theme=localStorage.zfTheme}catch(_){}

/* cause of death: group Retraction Watch's ~100 reason codes */
const CAUSES=[
 ["Fabricated data",/fabricat|falsif/i],["Manipulated images",/image/i],["Paper mill or fake review",/paper mill|fake peer|peer review|compromised|randomly generated|computer-aided/i],
 ["Plagiarism",/plagiar|euphemism/i],["Duplicate publication",/duplicat/i],["Misconduct finding",/misconduct/i],["Error or not reproducible",/error|unreliable|reproduc|contamina|results not/i],
 ["Ethics or consent",/ethic|consent|irb|iacuc/i],["Authorship or legal",/authorship|author unaware|legal|copyright|third party|objections/i]];
const SUP=/out of date|retract and replace/i;
const causesOf=p=>{const s=new Set();(p.reasons||[]).forEach(r=>{for(const [n,re] of CAUSES)if(re.test(r)){s.add(n);break}});const o=CAUSES.map(c=>c[0]).filter(n=>s.has(n));if(!o.length)o.push((p.reasons||[]).some(r=>SUP.test(r))?"Superseded by a newer version":"Reason not stated");return o};
const primary=p=>causesOf(p)[0];

/* ---------- EKG hero ---------- */
(function ekg(){
  if(!has("ekg"))return;
  const c=$("ekg"),x=c.getContext("2d");let W,H,t=0,dpr=Math.min(2,devicePixelRatio||1);
  const css=v=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
  const size=()=>{W=c.clientWidth;H=c.clientHeight;c.width=W*dpr;c.height=H*dpr;x.setTransform(dpr,0,0,dpr,0,0)};size();addEventListener("resize",size);
  const beat=p=>{p=((p%1)+1)%1;if(p<.08)return Math.sin(p/.08*Math.PI)*.08;if(p<.14)return 0;if(p<.16)return -.12;if(p<.19)return 1;if(p<.22)return -.32;if(p<.26)return 0;if(p<.4)return Math.sin((p-.26)/.14*Math.PI)*.18;return 0};
  const rnd=i=>{const s=Math.sin(i*127.1)*43758.5;return s-Math.floor(s)};
  const zomb=(u)=>{const i=Math.floor(u*6),f=u*6-i;const on=rnd(i)>.45;if(!on)return (rnd(i*3.1+f)-.5)*.03;const a=.25+rnd(i+.5)*.55;if(f<.05)return -a*.3;if(f<.1)return a*(rnd(i+2)>.5?1:-.6);if(f<.14)return -a*.4;return (rnd(i*7+f*40)-.5)*.04};
  const reduce=matchMedia("(prefers-reduced-motion:reduce)").matches;
  function y(px){ // px from 0..W
    const u=px/W;
    if(u<.46)return beat(px/Math.max(90,W/7.5)-t*1.2);
    if(u<.54)return 0;
    return zomb((px-W*.54)/Math.max(60,W/12)/6+t*.15);
  }
  function draw(){
    x.clearRect(0,0,W,H);const mid=H*.58,amp=H*.42;
    const seg=[[0,.46,css("--ink")],[.46,.54,css("--blood")],[.54,1,css("--acidInk")]];
    seg.forEach(([a,b,col],k)=>{x.beginPath();for(let px=Math.floor(W*a);px<=Math.ceil(W*b);px++){const yy=mid-y(px)*amp;px===Math.floor(W*a)?x.moveTo(px,yy):x.lineTo(px,yy)}
      x.strokeStyle=col;x.lineWidth=k===2?2:1.8;x.lineJoin="round";if(k===2){x.shadowColor=css("--acid");x.shadowBlur=8}x.stroke();x.shadowBlur=0});
    // scan head
    const hx=(t*90)%W;x.fillStyle=css("--paper");x.globalAlpha=.85;x.fillRect(hx,0,18,H);x.globalAlpha=1;
    t+=1/60;if(!reduce)requestAnimationFrame(draw);
  }
  draw();
})();

/* ---------- life-line SVG: beats until publication→retraction, flat, then undead blips ---------- */
function lifeSVG(p,h=30,big){
  const y0=yr(p.published)||(yr(p.retracted)-2),y1=yr(p.retracted)||y0+1,span=Math.max(1,NY-y0),W=300;
  const xr=Math.max(8,Math.min(W-30,(y1-y0)/span*W));let d=`M0 ${h*.6}`;
  for(let px=0;px<xr;px+=12){const yy=h*.6;d+=` L${px} ${yy} L${px+3} ${yy-h*.45} L${px+5} ${yy+h*.2} L${px+7} ${yy}`}
  d+=` L${xr} ${h*.6}`;
  const fl=`M${xr} ${h*.6} L${Math.min(W,xr+16)} ${h*.6}`;
  let z=`M${Math.min(W,xr+16)} ${h*.6}`;const n=Math.max(1,p.zombies||1);
  for(let px=xr+16,i=0;px<W;px+=Math.max(8,(W-xr)/Math.min(30,n*3)),i++){z+=` L${px} ${h*.6} L${px+2} ${h*.6-(i%3?h*.22:h*.38)} L${px+4} ${h*.6+h*.12} L${px+5} ${h*.6}`}
  return `<svg class="life" viewBox="0 0 ${W} ${h}" preserveAspectRatio="none" aria-hidden="true"><path d="${d}" fill="none" stroke="var(--ink)" stroke-width="1.3" vector-effect="non-scaling-stroke"/><path d="${fl}" stroke="var(--blood)" stroke-width="2" vector-effect="non-scaling-stroke"/><circle cx="${xr}" cy="${h*.6}" r="3" fill="var(--blood)"/><path d="${z}" fill="none" stroke="var(--acidInk)" stroke-width="1.4" vector-effect="non-scaling-stroke"/></svg>`;
}
const undeadYears=p=>{const r=yr(p.retracted);return r?Math.max(0,NY-r):0};
const ago=p=>{const u=undeadYears(p);return u<1?Math.max(1,Math.round(u*12))+" months":(u<2?"1 year":Math.floor(u)+" years")};
const z1=p=>(p.wiki||[]).find(w=>w.status==="zombie"&&said(w))||(p.wiki||[]).find(w=>w.status==="zombie")||p.wiki[0];
const LISTSEC=/^(references|further reading|bibliography|sources|notes|external links|citations|works cited|literature)/i;
const said=(w,max=260)=>{if(!w||LISTSEC.test(w.section||"")||/^\d{4} in /.test(w.page||""))return "";let s=(w.said||"").replace(/^.*\}\}\s*/,"").replace(/\{\{.*$/,"").replace(/^[\s|\]\[}"]+/,"").replace(/^[\s*#:;]+/,"").trim();if(/https?:|\[|\]/.test(s)||s.split(/\s+/).length<8)return "";if(/\|\s*[\w-]+\s*=|^\W*title\s*=/.test(s))return "";if(s.length<25||/^[\W\d]+$/.test(s)||/^(doi|isbn|pmid)\b/i.test(s))return "";if(s.length>max)s="…"+s.slice(-max).replace(/^\S*\s/,"");return s};

/* ---------- data ---------- */
let D=null,ZP=[],OUT=[];
async function load(){
  try{const r=await fetch(BASE+"data.json",{cache:"no-cache"});if(!r.ok)throw 0;D=await r.json()}catch(_){D=null}
  try{const r=await fetch(BASE+"outreach.json",{cache:"no-cache"});if(r.ok)OUT=(await r.json()).notes||[]}catch(_){}
  if(!D||!D.papers||!D.papers.length){fallback();return}
  ZP=D.papers.map((p,i)=>({...p,title:cleanT(p.title),i,_c:causesOf(p),_sup:!!p.superseded||!causesOf(p).some(c=>CAUSES.some(x=>x[0]===c))&&(p.reasons||[]).some(r=>SUP.test(r)),_s:(p.title+" "+p.journal+" "+(p.authors||[]).join(" ")+" "+p.wiki.map(w=>w.page).join(" ")+" "+(p.subject||[]).join(" ")).toLowerCase()}));
  const S=D.stats;
  HOLD=new Set(OUT.filter(n=>n.hold).map(n=>n.key));
  const DIS=new Set(OUT.filter(n=>n.status==="dismissed").map(n=>n.key));
  ZP.forEach(p=>{p.wiki.forEach(w=>{if(w.status==="zombie"&&DIS.has(p.doi+"|"+w.page))w.status="reviewed"});p.zombies=p.wiki.filter(w=>w.status==="zombie").length;p.reach=p.wiki.reduce((a,w)=>a+(w.status==="zombie"?w.views:0),0);p.wiki.sort((a,b)=>(a.status!=="zombie")-(b.status!=="zombie")||b.views-a.views);p._z=p._sup?0:p.zombies});
  const LZ=ZP.filter(p=>p._z),pg={};LZ.forEach(p=>p.wiki.forEach(w=>{if(w.status==="zombie")pg[w.page]=w.views}));
  const C={zc:LZ.reduce((a,p)=>a+p._z,0),zp:Object.keys(pg).length,mr:Object.values(pg).reduce((a,b)=>a+b,0)};
  document.querySelectorAll("[data-c]").forEach(el=>countUp(el,C[el.dataset.c]));
  document.querySelectorAll("[data-n]").forEach(el=>countUp(el,S[el.dataset.n]));
  $("kick").textContent=`Updated ${new Date(D.checked||D.built).toLocaleDateString("en-US",{month:"long",day:"numeric",year:"numeric"})} · ${full(ZP.filter(p=>p._z).length)} retracted papers still cited with no warning`;
  $("built").textContent="data rebuilt "+D.built.replace("T"," ").replace("Z"," UTC");
  $("mLinks").textContent=fmt(S.links_scanned);
  if(has("tick"))ticker();if(has("feat"))featured();if(has("toetag"))toetag();if(has("reg")){chips();render()}if(has("reasons"))autopsy();if(has("board"))desk();
  if(has("xReg"))$("xReg").textContent=`${full(ZP.filter(p=>p._z).length)} retracted papers Wikipedia still cites, searchable by topic, journal and cause.`;
  const m=location.hash.match(/^#p=(.+)/);if(m)openP(decodeURIComponent(m[1]));
}
function countUp(el,v){if(v==null)return;const dur=1600,t0=performance.now(),f=v>=1e6?fmt:full;
  const io=new IntersectionObserver(es=>{if(!es[0].isIntersecting)return;io.disconnect();(function s(now){const k=Math.min(1,(now-t0)/dur),e=1-Math.pow(1-k,4);el.textContent=f(Math.round(v*e));if(k<1)requestAnimationFrame(s)})(performance.now())});io.observe(el)}

function ticker(){
  const items=ZP.filter(p=>p._z&&!held(p)).slice(0,40).map(p=>{const w=z1(p),s=said(w,150);return s?`<span class="it"><b>${esc(w.page)}</b>“${esc(s)}”<s>source retracted ${esc((p.retracted||"").slice(0,4))}</s></span>`:""}).filter(Boolean);
  if(!items.length)return;$("tick").innerHTML=items.join("")+items.join("");
}

let HOLD=new Set();const held=p=>HOLD.has(p.doi+"|"+z1(p).page);
function toetag(){const p=ZP.find(p=>p._z&&!held(p)&&said(z1(p),200));if(!p)return;const w=z1(p),t=$("toetag");
  t.innerHTML=`<div class="tn"><span>Case No. 1</span><span>Undead ${ago(p)}</span></div><q>${esc(said(w,190))}</q><p>Still on Wikipedia in <b>${esc(w.page)}</b>. Source: ${esc(p.title.slice(0,80))}${p.title.length>80?"…":""}, retracted ${esc(fmtDate(p.retracted))}.</p>`;
  t.hidden=false;t.onclick=()=>show(p)}
function quoteHTML(w,max){const s=said(w,max);return s?`<p class="quote"><mark>${esc(s)}</mark><sup>[retracted]</sup></p>`:""}
function featured(){
  const list=ZP.filter(p=>p._z&&!held(p)&&said(z1(p))).slice(0,innerWidth<641?8:11);
  $("feat").innerHTML=list.map((p,k)=>{const w=z1(p);return `<article class="f${k===0?" big":""}" data-i="${p.i}" tabindex="0">
    <div class="rank"><span>No. ${k+1} · ${fmt(p.reach)} reads/mo</span><span class="cod">${esc(primary(p))}</span></div>
    ${quoteHTML(w,k===0?380:220)}
    <p class="src">Wikipedia · <a href="${wurl(w.page,w.section)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${esc(w.page)}</a>${w.section&&w.section!=="Lead"?" › "+esc(w.section):""}</p>
    <div class="dead"><h3>${esc(p.title)}</h3><p>${esc([p.journal,(p.published||"").slice(0,4)].filter(Boolean).join(" · "))} · retracted ${esc(fmtDate(p.retracted))}, undead ${ago(p)}</p>${lifeSVG(p)}
    <div class="meta"><span class="pill z">${p.zombies} zombie cite${p.zombies>1?"s":""}</span>${p.wiki.length>p.zombies?`<span class="pill fl">${p.wiki.length-p.zombies} flagged</span>`:""}${p.cites?`<span class="pill">${full(p.cites)} scholarly cites</span>`:""}</div></div></article>`}).join("");
  bindOpen($("feat"),".f");
}
const fmtDate=s=>s?new Date(s+"T12:00").toLocaleDateString("en-US",{month:"short",year:"numeric"}):"";

/* register */
let cause=null,shown=30;
function chips(){
  const c={};ZP.filter(p=>p._z).forEach(p=>p._c.forEach(x=>c[x]=(c[x]||0)+1));
  const all=Object.entries(c).sort((a,b)=>b[1]-a[1]);
  $("causes").innerHTML=`<button class="chip" aria-pressed="true" data-c="">All causes</button>`+all.map(([k,v])=>`<button class="chip" aria-pressed="false" data-c="${esc(k)}">${esc(k)}<small>${v}</small></button>`).join("");
  $("causes").onclick=e=>{const b=e.target.closest(".chip");if(!b)return;cause=b.dataset.c||null;$("causes").querySelectorAll(".chip").forEach(x=>x.setAttribute("aria-pressed",x===b));shown=30;render()};
}
function filtered(){
  const q=$("q").value.trim().toLowerCase(),fl=$("showFlagged").checked,sp=$("showSup").checked,s=$("sort").value;
  let L=ZP.filter(p=>(p._sup?sp&&(fl||p.zombies):(fl||p.zombies))&&(!cause||p._c.includes(cause))&&(!q||q.split(/\s+/).every(t=>p._s.includes(t))));
  const key={reach:p=>-p.reach-p.zombies/1e3,zombies:p=>-p.zombies,undead:p=>-undeadYears(p),recent:p=>-(yr(p.retracted)||0),cites:p=>-(p.cites||0)}[s];
  return L.sort((a,b)=>key(a)-key(b));
}
function render(){
  const L=filtered();$("cnt").textContent=`${full(L.length)} retracted paper${L.length===1?"":"s"} · ${(z=>full(z)+" zombie citation"+(z===1?"":"s"))(L.reduce((a,p)=>a+p.zombies,0))}`;
  if(!L.length){$("reg").innerHTML=`<li class="empty" style="display:block;cursor:default">Nothing matches. Try a broader word, or include flagged citations.</li>`;$("more").hidden=true;return}
  $("reg").innerHTML=L.slice(0,shown).map((p,k)=>{const w=z1(p),s=said(w,200);return `<li data-i="${p.i}" tabindex="0">
    <span class="n">${k+1}</span>
    <div><h3>${esc(p.title)}</h3><div class="j">${esc([p.journal,(p.published||"").slice(0,4)].filter(Boolean).join(" · "))} · <span style="color:var(--blood)">${esc(primary(p))}</span></div>
      ${s?`<p class="said"><b>${esc(w.page)}</b>“${esc(s)}”</p>`:`<p class="said"><b>${esc(w.page)}</b></p>`}</div>
    <div class="st"><div class="c3"><span class="k">Zombie cites</span><span class="v ${p.zombies?"z":""}">${p.zombies}${p.wiki.length>p.zombies?`<small class="mono" style="font-size:11px;color:var(--flag)"> +${p.wiki.length-p.zombies}</small>`:""}</span></div>
    <div class="c4"><span class="k">Undead</span><span class="v">${ago(p).replace(" years","y").replace(" year","y").replace(" months","mo")}</span></div></div></li>`}).join("");
  $("more").hidden=L.length<=shown;$("more").textContent=L.length-shown>30?`Show 30 more · ${full(L.length-shown)} left`:`Show the last ${full(L.length-shown)}`;
  bindOpen($("reg"),"li[data-i]");
}
$("more").onclick=()=>{shown+=30;render()};
let qT;$("q").oninput=()=>{clearTimeout(qT);qT=setTimeout(()=>{shown=30;render()},140)};
$("sort").onchange=$("showSup").onchange=$("showFlagged").onchange=()=>{shown=30;render()};
function bindOpen(root,sel){root.querySelectorAll(sel).forEach(el=>{el.onclick=()=>openI(+el.dataset.i);el.onkeydown=e=>{if(e.key==="Enter")openI(+el.dataset.i)}})}

/* autopsy */
function autopsy(){
  const z=ZP.filter(p=>p._z),c={};z.forEach(p=>p._c.forEach(x=>c[x]=(c[x]||0)+1));
  const R=Object.entries(c).sort((a,b)=>b[1]-a[1]),mx=R[0]?R[0][1]:1;
  $("reasons").innerHTML=R.map(([k,v],i)=>`<li><span>${esc(k)}</span><span>${v}</span><i style="--w:${(v/mx*100).toFixed(1)}%;--d:${i*.06}s"></i></li>`).join("");
  const S={};z.forEach(p=>(p.subject||[]).forEach(s=>{s=s.replace(/^\(\w+\)\s*/,"").split(/[-–]/)[0].trim();if(s)S[s]=(S[s]||0)+1}));
  const SS=Object.entries(S).sort((a,b)=>b[1]-a[1]).slice(0,8),sm=SS[0]?SS[0][1]:1;
  $("subjects").innerHTML=SS.map(([k,v],i)=>`<li><span>${esc(k)}</span><span>${v}</span><i style="--w:${(v/sm*100).toFixed(1)}%;--d:${i*.06}s"></i></li>`).join("");
  const Y={};z.forEach(p=>{const y=(p.retracted||"").slice(0,4);if(y)Y[y]=(Y[y]||0)+1});
  const ys=Object.keys(Y).map(Number).sort(),a=Math.max(ys[0]||2000,1990),b=NOW.getFullYear(),ym=Math.max(...Object.values(Y),1);
  let h="";for(let y=a;y<=b;y++)h+=`<div title="${y}: ${Y[y]||0} papers" style="--h:${((Y[y]||0)/ym*100).toFixed(1)}%;--d:${(y-a)*.025}s"></div>`;
  $("hist").innerHTML=h;$("hx").innerHTML=`<span>${a}</span><span>${Math.round((a+b)/2)}</span><span>${b}</span>`;
  const u=z.map(undeadYears).sort((a,b)=>a-b),med=u[Math.floor(u.length/2)]||0,old=z.slice().sort((a,b)=>undeadYears(b)-undeadYears(a))[0];
  $("undead").innerHTML=`The typical zombie here was retracted <b>${med.toFixed(1)} years ago</b> and is still cited.${old?` The oldest, <a href="#p=${encodeURIComponent(old.doi)}">${esc(old.title.slice(0,90))}${old.title.length>90?"…":""}</a>, has been dead since ${esc((old.retracted||"").slice(0,4))}.`:""}`;
  const sec=$("autopsy");new IntersectionObserver((es,o)=>{if(es[0].isIntersecting){sec.classList.add("on");o.disconnect()}},{threshold:.15}).observe(sec);
}

/* drawer */
function openI(i){const p=ZP[i];if(p)show(p)}
function openP(doi){const p=ZP.find(x=>x.doi===doi.toLowerCase());if(p)show(p)}
function reviewBlock(p,w){const n=noteOf(p.doi+"|"+w.page);if(!n)return "";
  const st={queued:"Reviewed · note queued",approved:"Reviewed · note goes up next",posted:"Note posted",replied:"Note posted · editors replied",dismissed:"Reviewed · no fix needed",skipped:"Fixed before we posted"}[n.status]||n.status;
  return `<div class="review"><b>Our review · ${esc(st)}</b>${esc(n.verdict)}${n.posted?` <a href="https://en.wikipedia.org/wiki/${encodeURIComponent("Talk:"+w.page)}" target="_blank" rel="noopener">Read the talk page</a>`:""}${(n.replies||[]).map(r=>`<div class="rp"><span>${esc(r.user)} · ${esc(shortD((r.at||"").slice(0,10)||n.posted.slice(0,10)))}</span>${esc(r.said)}</div>`).join("")}</div>`}
function fixRow(p,w,wi){const c=caseOf(p,w);
  const n=noteOf(p.doi+"|"+w.page);
  if(n&&n.status!=="dismissed"&&n.status!=="skipped")return reviewBlock(p,w)+`<div class="wcase">${c?`Case open since ${esc(shortD(c.o))}`:""} · We're handling the note on this one. <a href="${editURL(w)}" target="_blank" rel="noopener">Fix it yourself</a> if you edit Wikipedia.</div>`;
  return reviewBlock(p,w)+`<div class="wcase">${c?`Case open since ${esc(shortD(c.o))}${c.re?` · reopened ${c.re}×`:""}`:"New this week"}</div><div class="wfix"><a class="p" data-talk="${wi}" href="${talkURL(p,w)}" target="_blank" rel="noopener">Post a note on the talk page</a><a href="${editURL(w)}" target="_blank" rel="noopener">Edit the article</a><button type="button" data-note="${wi}">Copy note</button></div>`}
function show(p){
  history.replaceState(null,"","#p="+encodeURIComponent(p.doi));
  const ws=p.wiki;
  $("dKind").textContent=p.zombies?`Case file · ${p.zombies} zombie citation${p.zombies>1?"s":""}`:"Case file · flagged";
  $("db").innerHTML=`<div class="meta">${p._c.map(c=>`<span class="pill r">${esc(c)}</span>`).join("")}</div>
   <h2 id="dTitle">${esc(p.title)}</h2>
   <p class="by">${esc((p.authors||[]).slice(0,4).join(", "))}${(p.authors||[]).length>4?" et al.":""}<br>${esc(p.journal)}${p.publisher?" · "+esc(p.publisher):""}${p.cites?` · cited ${full(p.cites)} times by other papers`:""}</p>
   <div class="tl">${lifeSVG(p,56,1)}<div class="ty"><span>Published ${esc(fmtDate(p.published)||"?")}</span><span style="color:var(--blood)">Retracted ${esc(fmtDate(p.retracted))}</span><span style="color:var(--acidInk)">Now · ${ago(p)} undead</span></div></div>
   ${p.reasons&&p.reasons.length?`<div class="cause">${p.reasons.slice(0,8).map(r=>`<span>${esc(r)}</span>`).join("")}</div>`:""}
   <div class="ws"><h4>Where Wikipedia still uses it</h4>${ws.map((w,wi)=>`<div class="w ${w.status==="zombie"?"":"fl"}"><div class="wt"><a href="${wurl(w.page,w.section)}" target="_blank" rel="noopener">${esc(w.page)}</a><span class="pill ${w.status==="zombie"?"z":"fl"}">${w.status==="author"?"author's own page":w.status==="reviewed"?"reviewed · ok":w.status}</span></div>
     ${said(w,500)?`<blockquote>${esc(said(w,500))}</blockquote>`:""}<div class="wm">${w.section?esc(w.section)+" · ":""}${full(w.views)} views in the last 30 days</div>${w.status==="zombie"?fixRow(p,w,wi):""}</div>`).join("")}</div>
   <div class="acts"><a class="p" href="https://doi.org/${esc(p.notice||p.doi)}" target="_blank" rel="noopener">Retraction notice</a><a href="https://doi.org/${esc(p.doi)}" target="_blank" rel="noopener">The paper</a>${p.zombies?`<button id="cpy">Copy note to editors</button>`:""}<button id="shr">Share</button>${p.zombies&&said(z1(p))?`<button id="card">Save share image</button>`:""}</div>`;
  const z=ws.find(w=>w.status==="zombie");
  const c=$("cpy");if(c)c.onclick=()=>copy(noteFor(p,z),"Note copied");
  $("db").querySelectorAll("[data-talk]").forEach(a=>a.onclick=()=>{copy(noteFor(p,ws[+a.dataset.talk]),"Note copied. Paste it into the talk page.")});
  $("db").querySelectorAll("[data-note]").forEach(b=>b.onclick=()=>copy(noteFor(p,ws[+b.dataset.note]),"Note copied"));
  const cb=$("card");if(cb)cb.onclick=()=>shareCard(p,z1(p),cb);
  $("shr").onclick=async()=>{const u=location.href,t=`Wikipedia still cites this retracted paper: ${p.title}`;if(navigator.share){try{await navigator.share({title:"Zombie Facts",text:t,url:u})}catch(_){}}else copy(u,"Link copied")};
  $("db").scrollTop=0;$("drawer").classList.add("on");$("scrim").classList.add("on");document.body.style.overflow="hidden";setTimeout(()=>$("dClose").focus(),50);
}
async function copy(s,m){try{await navigator.clipboard.writeText(s);toast(m)}catch(_){prompt("Copy this:",s)}}
function close(){$("drawer").classList.remove("on");$("scrim").classList.remove("on");document.body.style.overflow="";history.replaceState(null,"",location.pathname)}
$("dClose").onclick=$("scrim").onclick=close;addEventListener("keydown",e=>{if(e.key==="Escape")close()});
addEventListener("hashchange",()=>{const m=location.hash.match(/^#p=(.+)/);if(m)openP(decodeURIComponent(m[1]))});
/* swipe down to close on phones */
(()=>{let y0=null;const d=$("drawer");d.addEventListener("touchstart",e=>{if($("db").scrollTop<=0)y0=e.touches[0].clientY},{passive:true});d.addEventListener("touchmove",e=>{if(y0==null)return;const dy=e.touches[0].clientY-y0;if(dy>0)d.style.transform=`translateY(${dy}px)`},{passive:true});d.addEventListener("touchend",e=>{if(y0==null)return;const dy=e.changedTouches[0].clientY-y0;d.style.transform="";y0=null;if(dy>110)close()})})();

/* reveal */
const ro=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add("on");ro.unobserve(e.target)}}),{threshold:.08});
document.querySelectorAll(".reveal").forEach(e=>ro.observe(e));



/* ---------- share image (1080x1350, drawn in the browser) ---------- */
async function shareCard(p,w,btn){
  btn.disabled=true;const lbl=btn.textContent;btn.textContent="Drawing…";
  try{
    await Promise.all(['400 40px "UnifrakturMaguntia"','400 40px "Anton"','italic 400 40px "Newsreader"','500 20px "IBM Plex Mono"','600 20px "IBM Plex Mono"'].map(f=>document.fonts.load(f).catch(()=>0)));
    const W=1080,H=1350,M=84,c=document.createElement("canvas");c.width=W;c.height=H;const g=c.getContext("2d");
    const INK="#141412",PAPER="#ece7da",ACID="#c6f432",BLOOD="#b42318",MUTE="#6c675b";
    g.fillStyle=PAPER;g.fillRect(0,0,W,H);
    g.fillStyle=INK;g.font='400 52px "UnifrakturMaguntia",serif';g.textBaseline="alphabetic";g.fillText("Zombie Facts",M,M+40);
    g.font='600 20px "IBM Plex Mono",monospace';g.textAlign="right";g.fillStyle=BLOOD;g.fillText("SOURCE RETRACTED "+(p.retracted||"").slice(0,4),W-M,M+34);g.textAlign="left";
    g.fillStyle=INK;g.fillRect(M,M+66,W-2*M,3);
    g.font='600 22px "IBM Plex Mono",monospace';g.fillStyle=MUTE;
    const kick=("STILL ON WIKIPEDIA · "+w.page.toUpperCase());g.fillText(kick.length>52?kick.slice(0,51)+"…":kick,M,M+130);
    // quote, auto-sized to fit
    const q="“"+said(w,420).replace(/"([^"]*)"/g,"‘$1’")+"”";let fs=80,lines;
    const wrap=(t,max)=>{const out=[];let cur="";t.split(/\s+/).forEach(x=>{const tr=cur?cur+" "+x:x;if(g.measureText(tr).width>max&&cur){out.push(cur);cur=x}else cur=tr});if(cur)out.push(cur);return out};
    for(;fs>=34;fs-=4){g.font=`italic 400 ${fs}px "Newsreader",Georgia,serif`;lines=wrap(q,W-2*M-16);if(lines.length*fs*1.3<=640)break}
    const lh=fs*1.3,top=M+170,bot=H-460;let y=top+Math.max(0,(bot-top-lines.length*lh)/2)+fs;
    lines.forEach(l=>{const tw=g.measureText(l).width;g.fillStyle=ACID;g.fillRect(M-6,y+fs*.22-lh+fs*.38,tw+12,lh*.78);g.fillStyle=INK;g.fillText(l,M,y+fs*.12);y+=lh});
    // source block
    y=Math.max(y+40,H-420);g.strokeStyle=INK;g.setLineDash([8,8]);g.lineWidth=2;g.beginPath();g.moveTo(M,y);g.lineTo(W-M,y);g.stroke();g.setLineDash([]);
    g.font='500 36px "Newsreader",Georgia,serif';g.fillStyle=INK;const tl=wrap(p.title,W-2*M).slice(0,3);if(wrap(p.title,W-2*M).length>3)tl[2]=tl[2].replace(/\s*\S+$/,"…");
    tl.forEach((l,i)=>g.fillText(l,M,y+56+i*46));y+=56+tl.length*46;
    g.font='500 22px "IBM Plex Mono",monospace';g.fillStyle=MUTE;
    const meta=[p.journal,"retracted "+fmtDate(p.retracted)].filter(Boolean).join(" · ");wrap(meta,W-2*M).slice(0,2).forEach((l,i)=>g.fillText(l,M,y+10+i*32));
    // footer
    g.fillStyle=INK;g.fillRect(0,H-118,W,118);g.fillStyle=ACID;g.font='400 46px "Anton",Impact,sans-serif';g.fillText("THE PAPER DIED. THE FACT KEPT WALKING.",M,H-46);
    const blob=await new Promise(r=>c.toBlob(r,"image/png"));const name="zombie-facts-"+w.page.replace(/[^a-z0-9]+/gi,"-").toLowerCase().slice(0,40)+".png";
    const file=new File([blob],name,{type:"image/png"});
    if(navigator.canShare&&navigator.canShare({files:[file]})){try{await navigator.share({files:[file],text:`Wikipedia still cites a retracted paper on “${w.page}”. ${location.href}`})}catch(_){}}
    else{const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=name;document.body.appendChild(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),4000);toast("Image saved")}
  }catch(e){toast("Couldn't draw the image")}
  btn.disabled=false;btn.textContent=lbl;
}
/* ---------- correction desk ---------- */
const CASES=()=>(D&&D.ledger&&D.ledger.cases)||{};
const caseOf=(p,w)=>CASES()[p.doi+"|"+w.page];
const dayMs=864e5,dd=s=>new Date(s+"T12:00Z");
const daysBetween=(a,b)=>Math.max(0,Math.round((dd(b)-dd(a))/dayMs));
const shortD=s=>dd(s).toLocaleDateString("en-US",{month:"short",day:"numeric",timeZone:"UTC"});
const talkURL=(p,w)=>"https://en.wikipedia.org/w/index.php?title="+encodeURIComponent("Talk:"+w.page)+"&action=edit&section=new&preloadtitle="+encodeURIComponent("Retracted source cited: "+(p.title.length>70?p.title.slice(0,68)+"…":p.title));
const editURL=w=>"https://en.wikipedia.org/w/index.php?title="+encodeURIComponent(w.page)+"&action=edit";
const noteFor=(p,w)=>{let t=TPL.replace("{PAGE}",w.page).replace("{SECTION}",w.section||"Lead").replace("{TITLE}",p.title).replace("{DOI}",p.doi).replace("{DATE}",fmtDate(p.retracted)).replace("{NOTICE}",p.notice||p.doi);const sd=said(w,400);return sd?t.replace("{SAID}",sd):t.replace(/\n\nIt supports this sentence: "\{SAID\}"/,"")};
function nextCheck(){const b=dd(D.built.slice(0,10));const n=new Date(b);n.setUTCDate(b.getUTCDate()+((8-b.getUTCDay())%7||7));return n.toISOString().slice(0,10)}
const noteOf=k=>OUT.find(n=>n.key===k);
const toldS=n=>n&&(n.status==="posted"||n.status==="replied");
function desk(){
  const L=D.ledger;if(!L){$("desk").hidden=true;return}
  const today=(D.checked||D.built).slice(0,10),byDoi={};ZP.forEach(p=>byDoi[p.doi]=p);
  const all=Object.entries(L.cases).map(([k,c])=>{const doi=k.slice(0,k.indexOf("|"));return {...c,k,doi,p:byDoi[doi],n:noteOf(k)}}).filter(c=>!(c.p&&c.p._sup));
  const open=all.filter(c=>!c.c).sort((a,b)=>(b.v||0)-(a.v||0));
  const kept=open.filter(c=>c.n&&c.n.status==="dismissed"),told=open.filter(c=>toldS(c.n)),waiting=open.filter(c=>!kept.includes(c)&&!told.includes(c));
  const shut=all.filter(c=>c.c&&c.how!=="author").sort((a,b)=>b.c.localeCompare(a.c));
  const ds=shut.map(c=>daysBetween(c.o,c.c)).sort((a,b)=>a-b),med=ds.length?ds[Math.floor(ds.length/2)]:null;
  const fixedReads=shut.reduce((a,c)=>a+(c.v||0),0),posted=OUT.filter(toldS),replies=posted.reduce((a,n)=>a+(n.replies||[]).length,0);
  $("board").innerHTML=`<div><b>${full(waiting.length+told.length)}</b><span>Open cases</span></div><div><b>${full(posted.length)}</b><span>Notes posted${replies?` · ${replies} ${replies>1?"replies":"reply"}`:""}</span></div><div class="fx"><b>${full(shut.length)}</b><span>Fixed${fixedReads?` · ${fmt(fixedReads)} reads/mo now clean`:""}</span></div><div><b>${med==null?"—":med+" d"}</b><span>Median days to fix · tracking since ${esc(shortD(L.since))}</span></div>`;
  const cap=innerWidth<641?6:10;
  const row=(c,right,sub)=>`<li><button class="cp" data-doi="${esc(c.doi)}">${esc(c.pg)}</button><span class="cd${right[1]?" ok":""}">${right[0]}</span><span class="ca">${sub}</span></li>`;
  const titleBit=c=>`${esc(cleanT(c.t).slice(0,80))}${(c.t||"").length>80?"…":""} · retracted ${esc((c.r||"").slice(0,4))}`;
  const nil=t=>`<li class="nil">${t}</li>`;
  $("openCases").innerHTML=waiting.slice(0,cap).map(c=>row(c,[`${daysBetween(c.o,today)?"Open "+daysBetween(c.o,today)+" d":"Opened "+esc(shortD(c.o))}<small>${fmt(c.v)} reads/mo</small>`],titleBit(c)+(c.n&&c.n.status==="approved"?`<span class="tag2 a">Note next</span>`:c.n&&c.n.status==="queued"?`<span class="tag2 q">Reviewed</span>`:""))).join("")+(waiting.length>cap?`<li><a class="ca" href="/register/">+ ${waiting.length-cap} more in the register →</a></li>`:"")||nil("Every open case has a note.");
  $("toldCases").innerHTML=told.map(c=>{const r=(c.n.replies||[]).length;return row(c,[`${r?r+" "+(r>1?"replies":"reply"):"No reply yet"}<small>posted ${esc(shortD(c.n.posted.slice(0,10)))}</small>`],titleBit(c))}).join("")||nil("The first notes go up this week. Each one shows here with the editors' replies.");
  $("fixedCases").innerHTML=shut.slice(0,cap).map(c=>row(c,[`${c.how==="flagged"?"Now flagged":"Citation removed"}<small>${esc(shortD(c.c))} · ${daysBetween(c.o,c.c)} d</small>`,1],titleBit(c))).join("")||nil(`Nothing fixed yet. Fixes show here with the date and how they were made.`);
  $("keptCases").innerHTML=kept.map(c=>row(c,["Reviewed<small>"+esc(shortD(c.n.reviewed))+"</small>"],esc(c.n.verdict))).join("")||nil("None yet.");
  $("desk").querySelectorAll(".cp").forEach(b=>b.onclick=()=>openP(b.dataset.doi));
  feed(all);
}
function feed(all){
  const ev=[],pg=k=>k.slice(k.indexOf("|")+1),doi=k=>k.slice(0,k.indexOf("|")),btn=k=>`<button data-doi="${esc(doi(k))}">${esc(pg(k))}</button>`;
  all.forEach(c=>{if(c.c&&c.how!=="author")ev.push([c.c,"fix","Fixed",`${btn(c.k)}: ${c.how==="flagged"?"an editor marked the retracted source":"the retracted source was removed"}, ${daysBetween(c.o,c.c)} days after we found it.`])});
  OUT.forEach(n=>{
    if(n.posted)ev.push([n.posted.slice(0,10),"post","Note posted",`${btn(n.key)}: <a href="https://en.wikipedia.org/wiki/${encodeURIComponent("Talk:"+n.page)}" target="_blank" rel="noopener">talk page</a>`]);
    (n.replies||[]).forEach(r=>ev.push([(r.at||"").slice(0,10),"rep","Reply",`${btn(n.key)}: ${esc(r.user)} wrote <q>${esc(r.said.slice(-160))}</q>`]));
  });
  const rv={};OUT.forEach(n=>{if(n.reviewed)(rv[n.reviewed]=rv[n.reviewed]||[]).push(n)});
  Object.entries(rv).forEach(([d,ns])=>{const by=s=>ns.filter(n=>n.status===s||(s==="queued"&&n.status==="approved")).length;ev.push([d,"rev","Reviewed",`${ns.length} cases read by hand: ${by("queued")} need a note, ${by("dismissed")} don't.`])});
  ev.sort((a,b)=>b[0].localeCompare(a[0])||(a[1]==="rev")-(b[1]==="rev"));
  $("feed").innerHTML=ev.slice(0,10).map(e=>`<li><time>${esc(shortD(e[0]))}</time><span class="k ${e[1]}">${e[2]}</span><span>${e[3]}</span></li>`).join("")||`<li class="nil">Nothing yet.</li>`;
  $("feed").querySelectorAll("button[data-doi]").forEach(b=>b.onclick=()=>openP(b.dataset.doi));
}
/* ---------- live tools (browser → Crossref + Wikipedia) ---------- */
const CR="https://api.crossref.org",MAILTO="&mailto=zombiefacts@users.noreply.github.com",WP="https://en.wikipedia.org/w/api.php";
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function getJSON(u,t=2){for(let i=0;i<=t;i++){try{const r=await fetch(u);if(r.status===429){await sleep(1500*(i+1));continue}if(!r.ok)throw new Error("HTTP "+r.status);return await r.json()}catch(e){if(i===t)throw e;await sleep(700)}}}
const dp=x=>x&&x["date-parts"]&&x["date-parts"][0]?x["date-parts"][0].map(v=>String(v).padStart(2,"0")).join("-"):"";
async function works(dois){const out={};for(let i=0;i<dois.length;i+=40){const c=dois.slice(i,i+40);try{const j=await getJSON(`${CR}/works?filter=${c.map(d=>"doi:"+encodeURIComponent(d)).join(",")}&rows=40&select=DOI,title,container-title,issued,updated-by,is-referenced-by-count${MAILTO}`);j.message.items.forEach(w=>out[w.DOI.toLowerCase()]=w)}catch(_){}}return out}
const retr=w=>{const r=(w&&w["updated-by"]||[]).filter(u=>/retract/i.test(u.type||""));if(!r.length)return null;return {notice:(r.find(x=>x.DOI)||{}).DOI||"",date:dp(r[0].updated)}};
["Ivermectin","Hydroxychloroquine","Amyloid beta","Stem cell","Superconductivity","Graphene","Microbiome","Placebo"].forEach(t=>{if(!has("tryScan"))return;const b=document.createElement("button");b.className="chip";b.textContent=t;b.onclick=()=>{$("qScan").value=t;$("bScan").click()};$("tryScan").appendChild(b)});
$("qScan").onkeydown=e=>{if(e.key==="Enter")$("bScan").click()};
$("bScan").onclick=async()=>{
  const st=$("sScan"),o=$("oScan"),b=$("bScan");let q=$("qScan").value.trim();if(!q)return;const m=q.match(/wikipedia\.org\/wiki\/([^?#]+)/);if(m)q=decodeURIComponent(m[1]).replace(/_/g," ");
  b.disabled=true;o.innerHTML="";st.innerHTML="<i></i>Reading the article…";
  try{const j=await getJSON(`${WP}?action=query&prop=revisions&rvprop=content&rvslots=main&titles=${encodeURIComponent(q)}&redirects=1&format=json&formatversion=2&origin=*`);
    const pg=j.query.pages[0];if(pg.missing)throw new Error(`there's no article called “${q}”`);const txt=pg.revisions[0].slots.main.content,low=txt.toLowerCase();
    const dois=[...new Set((txt.match(/10\.\d{4,9}\/[^\s|}<\]"]+/g)||[]).map(d=>d.replace(/[.,;)]+$/,"").toLowerCase()))];
    st.innerHTML=`<i></i>${dois.length} DOIs in “${esc(pg.title)}”. Asking Crossref…`;
    const W=await works(dois),dead=dois.filter(d=>retr(W[d]));
    if(!dead.length){st.textContent=`“${pg.title}” cites ${dois.length} DOIs. None are retracted. Clean.`;b.disabled=false;return}
    o.innerHTML=dead.map(d=>{const w=W[d],r=retr(w),i=low.indexOf(d),ri=low.lastIndexOf("<ref",i),ctx=low.slice(Math.max(0,ri<0||i-ri>4000?i-300:ri-600),i+900),fl=/\{\{\s*retracted|\bretract(ed|ion)\b|expression of concern/.test(ctx);
      return `<div class="hit"><span class="pill ${fl?"fl":"z"}">${fl?"flagged":"zombie"}</span><h5>${esc(cleanT((w.title||[])[0]||d))}</h5><p>${esc((w["container-title"]||[])[0]||"")} · retracted ${esc(r.date)} · <a href="https://doi.org/${esc(r.notice||d)}" target="_blank" rel="noopener">notice</a></p></div>`}).join("");
    st.textContent=`“${pg.title}” cites ${dois.length} DOIs, and ${dead.length} of them are retracted.`;
  }catch(e){st.textContent="Couldn't scan: "+e.message}
  b.disabled=false};
$("bFresh").onclick=async()=>{
  const st=$("sFresh"),o=$("oFresh"),b=$("bFresh");b.disabled=true;o.innerHTML="";st.innerHTML="<i></i>Fetching the newest notices…";
  try{const j=await getJSON(`${CR}/works?filter=update-type:retraction&sort=created&order=desc&rows=25&select=DOI,update-to,created${MAILTO}`);
    const L=[],seen=new Set();j.message.items.forEach(n=>(n["update-to"]||[]).forEach(u=>{const k=(u.DOI||"").toLowerCase();if(/retract/i.test(u.type)&&k&&!seen.has(k)){seen.add(k);L.push({doi:k,notice:n.DOI,date:dp(n.created)})}}));
    const W=await works(L.map(x=>x.doi));let done=0;
    const res=[];for(const x of L){let n=0;try{const s=await getJSON(`${WP}?action=query&list=search&srsearch=${encodeURIComponent('insource:"'+x.doi+'"')}&srnamespace=0&srlimit=5&format=json&origin=*`);n=s.query.searchinfo?s.query.searchinfo.totalhits:0}catch(_){}st.innerHTML=`<i></i>Checking Wikipedia ${++done}/${L.length}`;res.push({...x,n});await sleep(250)}
    res.sort((a,b)=>b.n-a.n);
    o.innerHTML=res.map(x=>{const w=W[x.doi]||{};return `<div class="hit">${x.n?`<span class="pill z">on Wikipedia ×${x.n}</span>`:""}<h5>${esc(cleanT((w.title||[])[0]||x.doi))}</h5><p>${esc((w["container-title"]||[])[0]||"")} · notice filed ${esc(x.date)} · <a href="https://doi.org/${esc(x.notice)}" target="_blank" rel="noopener">notice</a></p></div>`}).join("");
    const hit=res.filter(x=>x.n).length;st.textContent=`${L.length} newest retractions · ${hit?hit+" already cited on Wikipedia":"none cited on Wikipedia yet"} · ${new Date().toLocaleTimeString()}`;
  }catch(e){st.textContent="Couldn't reach Crossref: "+e.message}
  b.disabled=false};

/* fallback if the weekly dataset isn't there: show live famous cases */
function fallback(){if(!has("kick"))return;
  $("kick").textContent="Live mode · checking famous retractions now";
  $("feat").innerHTML=`<p class="empty">The weekly register is being rebuilt. Use the live scanner below in the meantime.</p>`;
  $("reg").innerHTML="";$("cnt").textContent="";$("tick").innerHTML=`<span class="it">The register is rebuilding. Try the live scanner below.</span>`;
}
/* ---------- newsroom (reads news.json; only human-confirmed cases are shown in detail) ---------- */
async function newsroom(){
  let N=null;try{const r=await fetch(BASE+"news.json",{cache:"no-cache"});if(r.ok)N=await r.json()}catch(_){}
  const S=(N&&N.stats)||{},items=(N&&N.items)||[];
  const ok=items.filter(i=>i.review==="confirmed"),fixed=ok.filter(i=>i.outcome==="fixed");
  const nd=s=>s?new Date(s+"T00:00:00Z").toLocaleDateString("en-US",{month:"short",day:"numeric",year:"numeric",timeZone:"UTC"}):"";
  if(!N||!S.factchecks){$("nBoard").style.display="none"}else $("nBoard").innerHTML=`<div><b>${N?full(S.factchecks):"—"}</b><span>Fact-checks read · last ${S.days>=700?"2 years":S.days>=360?"year":Math.round((S.days||120)/30)+" months"}</span></div>${S.titlesSearched>=50?`<div><b>${full(S.titlesSearched)}</b><span>Retracted papers searched in the news</span></div>`:`<div><b>${full(S.checkers)}</b><span>Fact-checking teams followed</span></div>`}<div><b>${N?full(ok.length):"—"}</b><span>Confirmed news cases${S.unreviewed?` · ${full(S.unreviewed)} being read`:""}</span></div><div class="fx"><b>${N?full(fixed.length):"—"}</b><span>Fixed by the outlet</span></div>`;
  $("nCases").innerHTML=ok.length?ok.map(i=>`<li><a class="cp" href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.headline||i.url)}</a><span class="cd${i.outcome==="fixed"?" ok":""}">${esc(i.outcome||"open")}<small>${esc(nd(i.first))}</small></span><span class="ca">${esc(i.outlet||i.domain)} · ${i.kind==="paper"?`cites a paper retracted ${esc(nd(i.retracted))}`:`repeats a claim ${esc(i.checker)} rated “${esc(i.verdict)}”`}</span></li>`).join("")
    :`<li><span class="nil">${S.unreviewed?`No confirmed cases yet. ${full(S.unreviewed)} ${S.unreviewed>1?"leads are":"lead is"} being read by hand.`:"No confirmed cases yet. Leads are read by hand before anything is posted here."}</span></li>`;
  const F=(N&&N.factchecks)||[];
  $("nChecks").innerHTML=F.length?F.slice(0,24).map(f=>`<li><q>${esc(f.claim.replace(/^[\s"“”']+|[\s"“”']+$/g,""))}</q><div class="m"><span class="pill r">${esc(f.verdict)}</span><span>${esc(f.checker)} · ${esc(nd(f.date))}</span>${f.url?`<a href="${esc(f.url)}" target="_blank" rel="noopener">Read the fact-check</a>`:""}</div></li>`).join("")
    :"";if(!F.length)$("nChecks").parentNode.style.display="none";
}
if(has("nBoard"))newsroom();
load();
})();
