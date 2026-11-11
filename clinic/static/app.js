/* Tulia Care demo. No real patient records, appointments or medical services. */
"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const page = document.body.dataset.page;
  const STORAGE = "tulia-demo-patient-key";
  const TOKEN = () => localStorage.getItem(STORAGE);
  const fmtTime = value => {
    if (!value) return "Before arrival";
    try { return new Intl.DateTimeFormat("en-KE",{hour:"2-digit",minute:"2-digit",timeZone:"Africa/Nairobi"}).format(new Date(value)); }
    catch {return "—";}
  };
  function elem(tag, className="", text="") {
    const el = document.createElement(tag);
    if (className) el.className=className;
    if (text !== "") el.textContent=String(text);
    return el;
  }
  async function api(path,options={}) {
    let response;
    try {
      response=await fetch(path,{credentials:"same-origin",cache:"no-store",...options});
    } catch { throw Error("Connection unavailable. Please check your internet and try again."); }
    let data;
    try { data=await response.json(); } catch {data={};}
    if (!response.ok) {
      let message=data.detail||"Something went wrong. Please try again.";
      if (Array.isArray(message)) message=message.map(x=>x.msg||"Invalid input").join("; ");
      throw Error(message);
    }
    return data;
  }
  const jsonBody = (data,headers={})=>({method:"POST",headers:{"Content-Type":"application/json",...headers},body:JSON.stringify(data)});
  const patientHeaders = ()=>({"X-Patient-Token":TOKEN()||""});
  function setError(target,message){
    if(!target)return;
    target.hidden=!message;
    target.textContent=message||"";
  }
  function iconFor(id){
    return {general:"✚",dental:"◇",pediatrics:"♡",lab:"⚗",physio:"⌁",wellness:"✳"}[id]||"✚";
  }
  function setupNavigation(){
    document.querySelectorAll(".desktop-links a[data-nav]").forEach(link=>{
      if(link.getAttribute("data-nav")===location.pathname)link.classList.add("active");
    });
    const toggle=$("nav-toggle"), mobile=$("mobile-nav");
    if(toggle&&mobile){
      toggle.addEventListener("click",()=>{
        const opening=mobile.hidden;
        mobile.hidden=!opening;
        toggle.setAttribute("aria-expanded",String(opening));
        toggle.setAttribute("aria-label",opening?"Close navigation":"Open navigation");
      });
      mobile.querySelectorAll("a").forEach(a=>a.addEventListener("click",()=>{
        mobile.hidden=true;toggle.setAttribute("aria-expanded","false");
      }));
    }
    if("serviceWorker" in navigator){
      window.addEventListener("load",()=>navigator.serviceWorker.register("/sw.js").catch(()=>{}));
    }
  }
  function makeServiceCard(service){
    const a=elem("a","service-card");
    a.href="/register?service="+encodeURIComponent(service.id);
    const icon=elem("div","service-icon tone-"+service.tone,iconFor(service.id));
    a.append(icon,elem("h3","",service.name),elem("p","",service.description));
    const foot=elem("div","service-foot");
    foot.append(elem("span","",service.waiting+" in demo queue"),elem("strong","","Check in ↗"));
    a.append(foot);
    return a;
  }
  async function home(){
    const holder=$("home-services"), queue=$("public-queue");
    async function refresh(){
      try {
        const services=await api("/api/services");
        holder.replaceChildren(...services.map(makeServiceCard));
        queue.replaceChildren();
        services.forEach(s=>{
          const row=elem("div","queue-line"),left=elem("div"),icon=elem("span","queue-mini-icon",iconFor(s.id));
          const data=elem("div");
          data.append(elem("strong","",s.name),elem("small","",s.being_seen?"A visit is in progress":"No consultation in progress"));
          left.append(icon,data);
          row.append(left,elem("span","",s.waiting+" waiting"));
          queue.append(row);
        });
      } catch(err) {
        holder.replaceChildren(elem("p","loading","Services are temporarily unavailable."));
        queue.replaceChildren(elem("p","loading","Queue updates are unavailable."));
      }
    }
    refresh();
    window.setInterval(()=>{if(!document.hidden)refresh();},30000);
  }
  async function register(){
    const form=$("register-form"), submit=$("register-submit");
    let serviceSelected=new URLSearchParams(location.search).get("service")||"general";
    let existing=null;
    async function checkExisting(){
      if(!TOKEN()){setExisting(null);return;}
      try {
        const p=await api("/api/me",{headers:patientHeaders()});
        setExisting(p);
      } catch {localStorage.removeItem(STORAGE);setExisting(null);}
    }
    function setExisting(p){
      existing=p;
      $("existing-patient").hidden=!p;
      form.hidden=!!p;
      if(p)$("existing-name").textContent="Welcome back, "+p.display_name;
      submit.textContent=p?"Continue with this profile ↗":"Create my digital check-in ↗";
    }
    $("switch-profile").addEventListener("click",()=>{
      localStorage.removeItem(STORAGE);
      setExisting(null);
      setError($("register-error"),"");
    });
    try {
      const services=await api("/api/services");
      const host=$("register-services");
      host.replaceChildren();
      if(!services.some(s=>s.id===serviceSelected)) serviceSelected="general";
      services.forEach(service=>{
        const button=elem("button","select-service");
        button.type="button";
        button.setAttribute("aria-pressed",String(service.id===serviceSelected));
        button.dataset.service=service.id;
        const icon=elem("span","mini-symbol",iconFor(service.id)),details=elem("span");
        details.append(elem("strong","",service.name),elem("small","",service.waiting+" in line · demo"));
        button.append(icon,details);
        button.addEventListener("click",()=>{
          serviceSelected=service.id;
          host.querySelectorAll("button").forEach(b=>b.setAttribute("aria-pressed",String(b===button)));
        });
        host.append(button);
      });
      submit.disabled=false;
    } catch(err) {
      $("register-services").replaceChildren(elem("p","loading","Service list unavailable."));
      submit.disabled=true;
    }
    await checkExisting();
    submit.addEventListener("click",async()=>{
      setError($("register-error"),"");
      submit.disabled=true;
      submit.textContent="Preparing your check-in…";
      try {
        if(!TOKEN()){
          const name=$("display-name").value.trim();
          if(name.length<2)throw Error("Enter a display name of at least two characters.");
          if(!$("demo-consent").checked)throw Error("Please confirm that you will use fictional information only.");
          const patient=await api("/api/patients",jsonBody({display_name:name,accepted_demo_terms:true}));
          localStorage.setItem(STORAGE,patient.access_token);
        }
        // An existing active visit is preserved; avoid duplicate queue tickets.
        const profile=await api("/api/me",{headers:patientHeaders()});
        if(profile.visit&&["prechecked","waiting","called"].includes(profile.visit.status)){
          location.assign("/my-visit");
          return;
        }
        const onsite=document.querySelector('input[name="arrival"]:checked')?.value==="onsite";
        await api("/api/visits",jsonBody({service_id:serviceSelected,onsite},patientHeaders()));
        location.assign("/my-visit");
      } catch(err){
        setError($("register-error"),err.message);
        submit.disabled=false;
        submit.textContent=existing?"Continue with this profile ↗":"Create my digital check-in ↗";
      }
    });
  }
  function setVisitSteps(status){
    const classes=["step-registered","step-arrived","step-called"];
    classes.forEach((id,i)=>{
      const node=$(id),done=i===0||((i===1)&&["waiting","called","completed","missed"].includes(status))||
        ((i===2)&&["called","completed"].includes(status));
      node.classList.toggle("complete",done);
      node.classList.toggle("active",i===1&&status==="prechecked"||i===2&&status==="waiting");
      node.querySelector("span").textContent=done?"✓":String(i+1);
    });
  }
  async function visit(){
    const loading=$("visit-loading"), empty=$("visit-empty"), main=$("visit-dashboard");
    if(!TOKEN()){
      loading.hidden=true;empty.hidden=false;return;
    }
    let busy=false;
    async function refresh(){
      if(busy)return;
      busy=true;
      try {
        const profile=await api("/api/me",{headers:patientHeaders()});
        loading.hidden=true;
        if(!profile.visit){empty.hidden=false;main.hidden=true;return;}
        empty.hidden=true;main.hidden=false;
        const v=profile.visit;
        $("visit-greeting").textContent="Hello, "+profile.display_name+"!";
        $("ticket-number").textContent=v.ticket;
        $("ticket-service").textContent=v.service_name;
        const statuses={prechecked:"PRE-CHECKED",waiting:"IN THE QUEUE",called:"YOUR TURN!",completed:"COMPLETED",missed:"MISSED"};
        $("queue-status").textContent=statuses[v.status]||"PENDING";
        let label="Your place in line",value="—",message="";
        switch(v.status){
          case "prechecked":
            label="Ready for your arrival";value="Not in queue yet";
            message="Your pre-check-in is saved. Once you arrive at the clinic, tap the button below to join the queue. This is a fictional demo.";
            break;
          case "waiting":
            value=v.position===1?"You're next!":"#"+v.position;
            message=v.people_ahead===0?"You're first in the waiting queue. Reception will call your number when a consultation spot opens.":
              v.people_ahead+" fictional visitor"+(v.people_ahead===1?" is":"s are")+" ahead of you. You can follow your position here.";
            break;
          case "called":
            label="Your ticket has been called";value="Please proceed!";
            message="Reception has called your demo ticket. Follow the instructions shown by the clinic staff.";
            break;
          case "completed":
            label="Your visit";value="Complete ✓";message="Your fictional clinic visit has been completed. Thank you!";
            break;
          case "missed":
            label="Your visit";value="Missed";message="Reception marked your demo ticket as missed. Please ask staff to restore it.";
            break;
        }
        $("position-label").textContent=label;
        $("position-value").textContent=value;
        $("visit-status-message").textContent=message;
        $("arrive-button").hidden=v.status!=="prechecked";
        $("last-refreshed").textContent="Updated "+new Date().toLocaleTimeString("en-KE",{hour:"2-digit",minute:"2-digit"});
        setVisitSteps(v.status);
      } catch(err){
        loading.hidden=true;empty.hidden=true;main.hidden=true;
        setError($("visit-error"),err.message);
        empty.hidden=false;
        if(err.message.includes("not found"))localStorage.removeItem(STORAGE);
      } finally {busy=false;}
    }
    $("refresh-visit").addEventListener("click",refresh);
    $("arrive-button").addEventListener("click",async()=>{
      const b=$("arrive-button");b.disabled=true;
      try { await api("/api/visits/arrive",{method:"POST",headers:patientHeaders()});await refresh(); }
      catch(err){$("visit-status-message").textContent=err.message;}finally{b.disabled=false;}
    });
    refresh();
    window.setInterval(()=>{if(!document.hidden)refresh();},12000);
  }
  async function reception(){
    const loginArea=$("staff-login"),dashboard=$("admin-dashboard"),message=$("staff-message");
    let data=null,selected="general",refreshing=false;
    function showDashboard(active){loginArea.hidden=active;dashboard.hidden=!active;}
    function notify(msg,error=false){
      message.textContent=msg||"";
      message.classList.toggle("error",!!error);
    }
    const statusLabel = status=>({prechecked:"Pre-checked",waiting:"Waiting",called:"Called",completed:"Completed",missed:"Missed"})[status]||status;
    function renderStats(){
      $("stat-registered").textContent=data.totals.registered_today;
      $("stat-waiting").textContent=data.totals.waiting;
      $("stat-called").textContent=data.totals.called;
      $("stat-completed").textContent=data.totals.completed;
    }
    function renderTabs(){
      const tabs=$("department-tabs");tabs.replaceChildren();
      data.services.forEach(s=>{
        const btn=elem("button","department-tab"+(selected===s.id?" active":""));
        btn.type="button";
        btn.append(elem("span","",s.name),elem("span","dept-count",s.waiting));
        btn.addEventListener("click",()=>{selected=s.id;renderTabs();renderQueue();});
        tabs.append(btn);
      });
    }
    async function action(path,body={}){
      try{
        const result=await api(path,jsonBody(body));
        notify("Updated "+result.ticket+" to "+statusLabel(result.status)+".");
        await refresh();
      }catch(err){notify(err.message,true);}
    }
    function rowAction(cell,label,fn,warn=false){
      const button=elem("button",warn?"warn":"",label);
      button.type="button";
      button.addEventListener("click",async()=>{
        button.disabled=true;
        await fn();
        button.disabled=false;
      });
      cell.append(button);
    }
    function renderQueue(){
      const department=data.services.find(s=>s.id===selected);
      $("department-title").textContent=department.name;
      $("department-summary").textContent=department.waiting+" waiting · "+department.called+" being seen · "+department.prechecked+" pre-checked";
      $("call-next").disabled=!department.waiting||!!department.called;
      const table=$("queue-body");
      table.replaceChildren();
      const visits=data.visits.filter(v=>v.service_id===selected).sort((a,b)=>{
        const order={called:0,waiting:1,prechecked:2,missed:3,completed:4};
        return order[a.status]-order[b.status]||a.id-b.id;
      });
      if(!visits.length){
        const tr=elem("tr"),td=elem("td","", "No visits here yet. New check-ins will appear automatically.");
        td.colSpan=5;tr.append(td);table.append(tr);return;
      }
      visits.forEach(v=>{
        const tr=elem("tr");
        const ticket=elem("td","",v.ticket);
        const name=elem("td","visitor-alias",v.display_name);
        const arrival=elem("td","",v.arrived_at?fmtTime(v.arrived_at):"Not arrived");
        const st=elem("td");st.append(elem("span","status-pill "+v.status,statusLabel(v.status)));
        const buttons=elem("td"),wrap=elem("div","action-buttons");
        if(v.status==="called"){
          rowAction(wrap,"Complete",()=>action("/api/staff/visits/"+v.id+"/status",{status:"completed"}));
          rowAction(wrap,"Missed",()=>action("/api/staff/visits/"+v.id+"/status",{status:"missed"}),true);
        }
        if(v.status==="waiting"){
          rowAction(wrap,"No show",()=>action("/api/staff/visits/"+v.id+"/status",{status:"missed"}),true);
        }
        if(v.status==="missed"){
          rowAction(wrap,"Restore",()=>action("/api/staff/visits/"+v.id+"/status",{status:"waiting"}));
        }
        if(!wrap.children.length)wrap.append(elem("span","", "—"));
        buttons.append(wrap);
        tr.append(ticket,name,arrival,st,buttons);
        table.append(tr);
      });
    }
    async function refresh(){
      if(refreshing)return;
      refreshing=true;
      try{
        data=await api("/api/staff/overview");
        showDashboard(true);
        renderStats();renderTabs();renderQueue();
      }catch(err){
        if(/sign-in|401|unauthor/i.test(err.message))showDashboard(false);
        else if(!dashboard.hidden)notify(err.message,true);
      }finally{refreshing=false;}
    }
    $("staff-login-form").addEventListener("submit",async event=>{
      event.preventDefault();
      setError($("staff-login-error"),"");
      const submit=event.target.querySelector("button");
      submit.disabled=true;
      try{
        await api("/api/staff/login",jsonBody({password:$("staff-password").value}));
        $("staff-password").value="";
        await refresh();
      }catch(err){setError($("staff-login-error"),err.message);}
      finally{submit.disabled=false;}
    });
    $("staff-logout").addEventListener("click",async()=>{
      try{await api("/api/staff/logout",{method:"POST"});}catch{}
      showDashboard(false);
    });
    $("dashboard-refresh").addEventListener("click",refresh);
    $("call-next").addEventListener("click",async()=>{
      const btn=$("call-next");
      btn.disabled=true;
      await action("/api/staff/call-next",{service_id:selected});
      btn.disabled=false;
    });
    await refresh();
    window.setInterval(()=>{if(!document.hidden&&!dashboard.hidden)refresh();},12000);
  }
  setupNavigation();
  if(page==="home")home();
  if(page==="register")register();
  if(page==="visit")visit();
  if(page==="reception")reception();
})();
