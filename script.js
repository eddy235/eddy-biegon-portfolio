const qs=(s,r=document)=>r.querySelector(s), qsa=(s,r=document)=>[...r.querySelectorAll(s)];

// Mobile menu
const menu=qs('.menu'), links=qs('.nav-links');
if(menu&&links){menu.addEventListener('click',()=>links.classList.toggle('open'));}
qsa('.nav-links a').forEach(a=>a.addEventListener('click',()=>links?.classList.remove('open')));

// Active nav from current page
const current=(location.pathname.split('/').pop()||'index.html').toLowerCase();
qsa('.nav-links a').forEach(a=>a.classList.toggle('active',(a.getAttribute('href')||'').toLowerCase()===current));

// Scroll progress
const progress=document.createElement('div'); progress.className='scroll-progress'; document.body.appendChild(progress);
const updateProgress=()=>{const d=document.documentElement; const max=d.scrollHeight-d.clientHeight; progress.style.width=(max?d.scrollTop/max*100:0)+'%';};
addEventListener('scroll',updateProgress,{passive:true}); updateProgress();

// Reveal content
const revealObserver=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('visible');revealObserver.unobserve(e.target);}}),{threshold:.12});
qsa('.reveal').forEach(el=>revealObserver.observe(el));

// Animated counters
const counterObserver=new IntersectionObserver(es=>es.forEach(e=>{if(!e.isIntersecting)return; const el=e.target; const end=Number(el.dataset.count||0); const suffix=el.dataset.suffix||''; const t0=performance.now(); const dur=900; const tick=t=>{const p=Math.min((t-t0)/dur,1); el.textContent=Math.floor(end*(1-Math.pow(1-p,3)))+suffix; if(p<1)requestAnimationFrame(tick)}; requestAnimationFrame(tick); counterObserver.unobserve(el);}),{threshold:.5});
qsa('[data-count]').forEach(el=>counterObserver.observe(el));

// Theme toggle with persistence
const themeBtn=document.createElement('button'); themeBtn.className='theme-toggle'; themeBtn.type='button'; themeBtn.setAttribute('aria-label','Toggle theme');
const savedTheme=localStorage.getItem('eddy-theme'); if(savedTheme)document.documentElement.dataset.theme=savedTheme;
const setThemeIcon=()=>themeBtn.textContent=document.documentElement.dataset.theme==='light'?'☾':'☀'; setThemeIcon();
themeBtn.addEventListener('click',()=>{document.documentElement.dataset.theme=document.documentElement.dataset.theme==='light'?'dark':'light'; localStorage.setItem('eddy-theme',document.documentElement.dataset.theme); setThemeIcon();});
qs('.nav-inner')?.appendChild(themeBtn);

// Pointer glow + tilt
const glow=qs('.cursor-glow');
if(glow&&matchMedia('(pointer:fine)').matches)addEventListener('pointermove',e=>{glow.style.left=e.clientX+'px';glow.style.top=e.clientY+'px';});
qsa('.tilt').forEach(card=>{card.addEventListener('pointermove',e=>{if(!matchMedia('(pointer:fine)').matches)return;const r=card.getBoundingClientRect(),x=(e.clientX-r.left)/r.width-.5,y=(e.clientY-r.top)/r.height-.5;card.style.transform=`perspective(900px) rotateX(${-y*5}deg) rotateY(${x*7}deg)`});card.addEventListener('pointerleave',()=>card.style.transform='')});

// Typewriter on homepage
const typer=qs('[data-roles]');
if(typer){const roles=JSON.parse(typer.dataset.roles);let i=0,j=0,del=false;const run=()=>{const word=roles[i]; typer.textContent=word.slice(0,j)+(j<word.length?'_':''); if(!del&&j<word.length){j++;setTimeout(run,70)}else if(!del){del=true;setTimeout(run,1200)}else if(j>0){j--;setTimeout(run,35)}else{del=false;i=(i+1)%roles.length;setTimeout(run,250)}};run();}

// Project filters + search
const filters=qsa('.filter');
let activeFilter='all';
function applyProjectFilters(){const term=(qs('#project-search')?.value||'').toLowerCase();qsa('[data-category]').forEach(card=>{const catOK=activeFilter==='all'||card.dataset.category===activeFilter;const textOK=!term||card.textContent.toLowerCase().includes(term);card.classList.toggle('hidden',!(catOK&&textOK));});}
filters.forEach(btn=>btn.addEventListener('click',()=>{filters.forEach(x=>x.classList.remove('active'));btn.classList.add('active');activeFilter=btn.dataset.filter;applyProjectFilters()}));
qs('#project-search')?.addEventListener('input',applyProjectFilters);

// Project quick-view modal
const projectDetails={
  knls:{title:'KNLS Website',body:'WordPress migration, content restructuring, server configuration, troubleshooting and launch preparation.',tags:['WordPress','Virtualmin','Apache','Gutenberg'],url:'https://www.knls.ac.ke/'},
  mint:{title:'Mint Dental Centre',body:'Responsive multi-page clinic website with appointment booking, WhatsApp handoff, accessibility controls and mobile-first navigation.',tags:['HTML','CSS','JavaScript','UX'],url:'https://mintdentalcentre.co.ke/'},
  api:{title:'API Security Risk Analysis',body:'Security review focused on authentication, authorization, data exposure, rate limiting and input validation.',tags:['Postman','API Security','Risk'],url:'https://github.com/eddy235'},
  va:{title:'Vulnerability Assessment',body:'Practical web assessment using common security tools, risk classification and concise reporting.',tags:['Nmap','OWASP ZAP','Reporting'],url:'https://github.com/eddy235'}
};
function openModal(key){const d=projectDetails[key];if(!d)return;let m=qs('#project-modal');if(!m){m=document.createElement('div');m.id='project-modal';m.className='modal';m.innerHTML='<div class="modal-card"><button class="modal-close" aria-label="Close">×</button><div class="eyebrow">Project quick view</div><h2></h2><p></p><div class="tags"></div><a class="btn primary modal-link" target="_blank">Open project ↗</a></div>';document.body.appendChild(m);m.addEventListener('click',e=>{if(e.target===m||e.target.closest('.modal-close'))m.classList.remove('open')});}
qs('h2',m).textContent=d.title;qs('p',m).textContent=d.body;qs('.tags',m).innerHTML=d.tags.map(t=>`<span class="tag">${t}</span>`).join('');qs('.modal-link',m).href=d.url;m.classList.add('open');}
qsa('[data-project]').forEach(b=>b.addEventListener('click',e=>{e.preventDefault();openModal(b.dataset.project)}));
addEventListener('keydown',e=>{if(e.key==='Escape')qs('#project-modal')?.classList.remove('open')});

// Live GitHub feed
async function loadGithub(){const host=qs('#github-feed');if(!host)return;try{const r=await fetch('https://api.github.com/users/eddy235/repos?sort=updated&per_page=6');if(!r.ok)throw new Error();const repos=await r.json();host.innerHTML=repos.slice(0,4).map(repo=>`<a class="repo-card" href="${repo.html_url}" target="_blank" rel="noreferrer"><div><strong>${repo.name}</strong><span>${repo.language||'Project'}</span></div><p>${repo.description||'Public GitHub repository'}</p><small>Updated ${new Date(repo.updated_at).toLocaleDateString()}</small></a>`).join('');}catch(e){host.innerHTML='<p class="small-note">Live GitHub activity could not load. <a href="https://github.com/eddy235" target="_blank">Open GitHub ↗</a></p>';}}
loadGithub();

// Smart contact form: no backend, opens WhatsApp with entered message
const form=qs('#contact-form');
if(form){form.addEventListener('submit',e=>{e.preventDefault();const fd=new FormData(form);const name=fd.get('name')||'there',msg=fd.get('message')||'I would like to connect.';const url=`https://wa.me/254717697883?text=${encodeURIComponent(`Hi Eddy, I’m ${name}. ${msg}`)}`;window.open(url,'_blank','noopener');});}

// Command palette Ctrl/Cmd + K
const palette=document.createElement('div');palette.className='command-palette';palette.innerHTML='<div class="command-box"><input id="command-input" placeholder="Type a page or action…" autocomplete="off"><div class="command-list"></div><small>Esc to close · Enter to open</small></div>';document.body.appendChild(palette);
const commands=[['Home','index.html'],['About','about.html'],['Experience','experience.html'],['Projects','projects.html'],['Cyber Lab','cyberlab.html'],['Certifications','certifications.html'],['Contact','contact.html'],['GitHub','https://github.com/eddy235'],['TryHackMe','https://tryhackme.com/p/EddyB']];
const input=qs('#command-input'),list=qs('.command-list');let visible=commands;
function renderCommands(){const q=input.value.toLowerCase();visible=commands.filter(c=>c[0].toLowerCase().includes(q));list.innerHTML=visible.map((c,i)=>`<button data-url="${c[1]}" class="${i===0?'selected':''}">${c[0]} <span>↗</span></button>`).join('');}
function togglePalette(open){palette.classList.toggle('open',open);if(open){input.value='';renderCommands();setTimeout(()=>input.focus(),50)}}
addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();togglePalette(true)}else if(e.key==='Escape')togglePalette(false);else if(e.key==='Enter'&&palette.classList.contains('open')){const b=qs('.command-list button');if(b)location.href=b.dataset.url}});
palette.addEventListener('click',e=>{if(e.target===palette)togglePalette(false);const b=e.target.closest('button[data-url]');if(b)location.href=b.dataset.url});input.addEventListener('input',renderCommands);

// CMS content: projects, certifications and cyber activity
let cmsProjects=[];
const esc=s=>String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#039;','"':'&quot;'}[c]));
const safeUrl=u=>/^https?:\/\//i.test(String(u||''))?String(u):'#';
async function fetchCMS(endpoint){const r=await fetch(endpoint,{headers:{'Accept':'application/json'}});if(!r.ok)throw new Error('CMS unavailable');return r.json();}
function renderCMSProject(p){const tags=String(p.tags||'').split(',').map(x=>x.trim()).filter(Boolean);const img=p.image_url?`<a class="project-shot" href="${safeUrl(p.url)}" target="_blank" rel="noreferrer"><span class="browser-label">Project preview</span><img src="${esc(p.image_url)}" alt="${esc(p.title)} preview" loading="lazy"><span class="shot-overlay">Open project ↗</span></a>`:'';return `<article class="project ${img?'':'project-compact'} interactive-card reveal visible" data-category="${esc(p.category||'web')}">${img}<div class="project-body">${!img?`<div class="cyber-mark">${esc((p.category||'PR').slice(0,2).toUpperCase())}</div>`:''}<div class="eyebrow">${esc(p.eyebrow||p.category||'Project')}</div><h2>${esc(p.title)}</h2><p>${esc(p.summary)}</p><div class="tags">${tags.map(t=>`<span class="tag">${esc(t)}</span>`).join('')}</div>${p.url?`<a class="text-link" href="${safeUrl(p.url)}" target="_blank" rel="noopener noreferrer">Live demo ↗</a>`:''}${p.title.includes('SecureScan')?` <a class="text-link portfolio-source" href="https://github.com/eddy235/SecureScan" target="_blank" rel="noopener noreferrer">GitHub source ↗</a>`:''}${p.title.includes('NexusDesk')?` <a class="text-link portfolio-source" href="https://github.com/eddy235/NexusDesk" target="_blank" rel="noopener noreferrer">GitHub source ↗</a>`:''}<button class="quick-view" data-cms-project="${p.id}">Quick view</button></div></article>`}
async function loadCMSProjects(){const host=qs('#cms-projects'),featured=qs('#cms-featured-projects');if(!host&&!featured)return;try{cmsProjects=await fetchCMS('/api/projects');if(host){host.innerHTML=cmsProjects.map(renderCMSProject).join('')||'<p class="cms-empty">No published projects yet.</p>';applyProjectFilters();}if(featured){const fp=cmsProjects.filter(p=>p.featured).slice(0,4);if(fp.length)featured.innerHTML=fp.map((p,i)=>`<a class="feature-tile reveal visible ${p.category==='security'?'cyber':''}" href="${safeUrl(p.url||'projects.html')}" ${p.url?'target="_blank" rel="noreferrer"':''}><span>${String(i+1).padStart(2,'0')}</span><h3>${esc(p.title)}</h3><p>${esc(p.summary)}</p><b>${p.url?'Open project ↗':'View project →'}</b></a>`).join('');}}catch(e){if(host)host.innerHTML='<p class="cms-empty">Projects are temporarily unavailable.</p>';}}
async function loadCMSCerts(){const host=qs('#cms-certifications');if(!host)return;try{const items=await fetchCMS('/api/certifications');host.innerHTML=items.map(c=>`<article class="cert reveal visible">${c.image_url?`<img class="cert-image" src="${esc(c.image_url)}" alt="${esc(c.title)}">`:''}<h3>${esc(c.title)}</h3><p>${esc([c.issuer,c.date_text].filter(Boolean).join(' · '))}</p>${c.summary?`<p>${esc(c.summary)}</p>`:''}${c.credential_url?`<a class="text-link credential-link" href="${safeUrl(c.credential_url)}" target="_blank" rel="noreferrer">View credential ↗</a>`:''}</article>`).join('')||'<p class="cms-empty">No published certifications yet.</p>';}catch(e){host.innerHTML='<p class="cms-empty">Certifications are temporarily unavailable.</p>';}}
async function loadCMSCyber(){const host=qs('#cms-cyber-activities');if(!host)return;try{const items=await fetchCMS('/api/cyber-activities');host.innerHTML=items.map(a=>`<article class="activity-card reveal visible"><div class="activity-icon">✓</div><div class="eyebrow">${esc(a.activity_type||'Cyber Lab')}</div><h3>${esc(a.title)}</h3><p>${esc(a.summary||'Hands-on cybersecurity practice.')}</p><div class="cms-meta"><span class="tag">${esc(a.status||'Completed')}</span>${a.completed_date?`<span class="tag">${esc(a.completed_date)}</span>`:''}</div>${a.url?`<a class="text-link credential-link" href="${safeUrl(a.url)}" target="_blank" rel="noreferrer">View activity ↗</a>`:''}</article>`).join('')||'<p class="cms-empty">Add completed rooms and labs from the CMS.</p>';}catch(e){host.innerHTML='<p class="cms-empty">Cyber activity is temporarily unavailable.</p>';}}
document.addEventListener('click',e=>{const b=e.target.closest('[data-cms-project]');if(!b)return;const p=cmsProjects.find(x=>x.id==b.dataset.cmsProject);if(!p)return;let m=qs('#project-modal');if(!m){m=document.createElement('div');m.id='project-modal';m.className='modal';m.innerHTML='<div class="modal-card"><button class="modal-close" aria-label="Close">×</button><div class="eyebrow">Project quick view</div><h2></h2><p></p><div class="tags"></div><a class="btn primary modal-link" target="_blank" rel="noreferrer">Open project ↗</a></div>';document.body.appendChild(m);m.addEventListener('click',ev=>{if(ev.target===m||ev.target.closest('.modal-close'))m.classList.remove('open')});}qs('h2',m).textContent=p.title;qs('p',m).textContent=p.summary;qs('.tags',m).innerHTML=String(p.tags||'').split(',').filter(Boolean).map(t=>`<span class="tag">${esc(t.trim())}</span>`).join('');const l=qs('.modal-link',m);l.href=safeUrl(p.url);l.style.display=p.url?'inline-flex':'none';m.classList.add('open')});
loadCMSProjects();loadCMSCerts();loadCMSCyber();

// v6 Packet Defender mini-game
(()=>{
  const grid=qs('#packet-grid'), start=qs('#game-start'), scoreEl=qs('#game-score'), timeEl=qs('#game-time'), bestEl=qs('#game-best'), message=qs('#game-message');
  if(!grid||!start)return;
  const labels=['HTTPS','DNS','SSH','TLS','API','SMTP','SQL','PING','AUTH','JSON','TCP','GET'];
  let score=0,time=20,timer=null,spawn=null,running=false;
  const bestKey='eddy-packet-defender-best';
  let best=Number(localStorage.getItem(bestKey)||0); bestEl.textContent=best;
  function setMessage(text,type=''){message.textContent=text;message.className='game-message '+type}
  function makePacket(){
    const b=document.createElement('button');
    const threat=Math.random()<.43;
    b.type='button'; b.className='packet '+(threat?'threat':'safe');
    b.dataset.threat=threat?'1':'0';
    const ip=`${Math.floor(Math.random()*223)+1}.${Math.floor(Math.random()*255)}.${Math.floor(Math.random()*255)}.${Math.floor(Math.random()*255)}`;
    b.innerHTML=`${labels[Math.floor(Math.random()*labels.length)]}<br><small>${ip}</small>`;
    b.addEventListener('click',()=>{
      if(!running||b.disabled)return;
      if(b.dataset.threat==='1'){
        score+=10; b.classList.add('hit'); b.disabled=true; setMessage('Threat blocked. +10','good');
        setTimeout(()=>b.remove(),150);
      }else{
        score=Math.max(0,score-5); b.classList.add('miss'); setMessage('Legitimate traffic — false positive. −5','bad');
        setTimeout(()=>b.classList.remove('miss'),260);
      }
      scoreEl.textContent=score;
    });
    return b;
  }
  function refill(){
    if(!running)return;
    const packets=[...grid.querySelectorAll('.packet')];
    while(packets.length<12){grid.appendChild(makePacket());packets.push(1)}
    const live=[...grid.querySelectorAll('.packet:not(:disabled)')];
    if(live.length>14)live[0]?.remove();
  }
  function finish(){
    running=false; clearInterval(timer); clearInterval(spawn); timer=spawn=null;
    grid.querySelectorAll('.packet').forEach(p=>p.disabled=true);
    if(score>best){best=score;localStorage.setItem(bestKey,String(best));bestEl.textContent=best;setMessage(`New best score: ${score}. Nice defense.`,`good`)}
    else setMessage(`Scan complete. Score: ${score}. Best: ${best}.`,`good`);
    start.textContent='Play again ↻'; start.disabled=false;
  }
  function begin(){
    score=0;time=20;running=true;scoreEl.textContent='0';timeEl.textContent='20';grid.innerHTML='';start.disabled=true;start.textContent='Challenge running…';setMessage('Traffic stream detected. Block the threats.','good');
    for(let i=0;i<12;i++)grid.appendChild(makePacket());
    spawn=setInterval(()=>{if(!running)return; const all=[...grid.querySelectorAll('.packet')]; if(all.length>13)all[0]?.remove();grid.appendChild(makePacket())},700);
    timer=setInterval(()=>{time-=1;timeEl.textContent=time;if(time<=0)finish()},1000);
  }
  start.addEventListener('click',begin);
})();
