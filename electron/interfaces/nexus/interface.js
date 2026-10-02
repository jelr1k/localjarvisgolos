(() => {
  const pages = [
    ["home","Обзор","◈"],["chat","Чат","◌"],["commands","Команды","⌘"],["workspace","Workspace","◎"],["ai","ИИ","◇"]
  ];

  function go(page){
    if(typeof window.go === "function") window.go(page);
  }

  function installShell(){
    if(document.querySelector(".nx-shell")) return;
    const shell=document.createElement("header");
    shell.className="nx-shell";
    shell.innerHTML=`
      <div class="nx-brand"><span class="nx-logo">N</span><div><b>NEXUS</b><small>JARVIS WORKSPACE</small></div></div>
      <nav class="nx-nav">${pages.map(([id,label,icon])=>`<button type="button" data-nx-page="${id}">${icon} ${label}</button>`).join("")}</nav>
      <button class="nx-shell-action" type="button" data-nx-page="settings" title="Настройки">⚙</button>`;
    document.body.appendChild(shell);
    shell.querySelectorAll("[data-nx-page]").forEach(b=>b.addEventListener("click",()=>go(b.dataset.nxPage)));
  }

  function sync(page){
    document.querySelectorAll("[data-nx-page]").forEach(b=>b.classList.toggle("active",b.dataset.nxPage===page));
  }

  function bindWorkspace(){
    const viewport=document.querySelector(".nx-viewport");
    const world=document.querySelector(".nx-world");
    if(!viewport||!world||world.dataset.bound==="true") return;
    world.dataset.bound="true";
    const nodes=[...world.querySelectorAll(".nx-node")];
    const links=[...world.querySelectorAll(".nx-links line")];
    const state={x:0,y:0,scale:1,pan:false,px:0,py:0,selected:null};
    const clamp=(n,min,max)=>Math.max(min,Math.min(max,n));

    function render(){
      world.style.transform=`translate(${state.x}px,${state.y}px) scale(${state.scale})`;
      document.querySelectorAll("[data-nx-zoom]").forEach(e=>e.textContent=Math.round(state.scale*100)+"%");
      links.forEach(line=>{
        const a=document.querySelector(`[data-node-id="${line.dataset.a}"]`);
        const b=document.querySelector(`[data-node-id="${line.dataset.b}"]`);
        if(!a||!b)return;
        const ax=parseFloat(a.style.left)+a.offsetWidth/2, ay=parseFloat(a.style.top)+a.offsetHeight/2;
        const bx=parseFloat(b.style.left)+b.offsetWidth/2, by=parseFloat(b.style.top)+b.offsetHeight/2;
        line.setAttribute("x1",ax);line.setAttribute("y1",ay);line.setAttribute("x2",bx);line.setAttribute("y2",by);
      });
    }

    nodes.forEach(node=>{
      node.addEventListener("pointerdown",e=>{
        e.stopPropagation(); node.setPointerCapture(e.pointerId); node.classList.add("dragging");
        state.selected=node; nodes.forEach(n=>n.classList.toggle("selected",n===node));
        const sx=e.clientX,sy=e.clientY,ox=parseFloat(node.style.left),oy=parseFloat(node.style.top);
        const move=ev=>{node.style.left=(ox+(ev.clientX-sx)/state.scale)+"px";node.style.top=(oy+(ev.clientY-sy)/state.scale)+"px";render()};
        const up=ev=>{node.releasePointerCapture(ev.pointerId);node.classList.remove("dragging");node.removeEventListener("pointermove",move);node.removeEventListener("pointerup",up)};
        node.addEventListener("pointermove",move);node.addEventListener("pointerup",up);
      });
      node.addEventListener("click",e=>{e.stopPropagation();const title=node.querySelector("strong")?.textContent||"Узел";const desc=node.querySelector("small")?.textContent||"";const out=document.querySelector(".nx-selected");if(out)out.innerHTML=`<span class="nx-label">Выбранный узел</span><strong>${title}</strong><p>${desc}</p>`;});
    });

    viewport.addEventListener("pointerdown",e=>{
      if(e.target.closest(".nx-node"))return;
      state.pan=true;state.px=e.clientX;state.py=e.clientY;viewport.classList.add("is-panning");
    });
    window.addEventListener("pointermove",e=>{if(!state.pan)return;state.x+=e.clientX-state.px;state.y+=e.clientY-state.py;state.px=e.clientX;state.py=e.clientY;render()});
    window.addEventListener("pointerup",()=>{state.pan=false;viewport.classList.remove("is-panning")});

    function zoomAt(delta,cx=innerWidth/2,cy=innerHeight/2){
      const old=state.scale,next=clamp(old+delta,.45,2.4);
      const wx=(cx-state.x)/old,wy=(cy-state.y)/old;
      state.scale=next;state.x=cx-wx*next;state.y=cy-wy*next;render();
    }
    document.querySelector("[data-nx-plus]")?.addEventListener("click",()=>zoomAt(.15));
    document.querySelector("[data-nx-minus]")?.addEventListener("click",()=>zoomAt(-.15));
    document.querySelector("[data-nx-reset]")?.addEventListener("click",()=>{state.x=0;state.y=0;state.scale=1;render()});
    viewport.addEventListener("wheel",e=>{e.preventDefault();zoomAt(e.deltaY<0?.1:-.1,e.clientX,e.clientY)},{passive:false});
    render();
  }

  function bindDynamicPage(){
    const workspace=document.querySelector(".nx-viewport");
    if(workspace) bindWorkspace();
    const form=document.querySelector("#nxChatForm"),input=document.querySelector("#nxChatInput"),messages=document.querySelector("#nxMessages");
    if(form&&input&&messages&&!form.dataset.bound){form.dataset.bound="true";form.addEventListener("submit",e=>{e.preventDefault();const v=input.value.trim();if(!v)return;const item=document.createElement("div");item.className="nx-msg user";item.innerHTML="<label>ВЫ</label><p></p>";item.querySelector("p").textContent=v;messages.appendChild(item);messages.scrollTop=messages.scrollHeight;input.value=""})}
  }

  installShell();
  new MutationObserver(()=>bindDynamicPage()).observe(document.querySelector("#pageContainer")||document.body,{childList:true,subtree:true});
  document.addEventListener("click",e=>{const b=e.target.closest("[data-nx-page]");if(b)sync(b.dataset.nxPage)});
  window.NexusInterface=Object.freeze({go,sync});
  window.dispatchEvent(new CustomEvent("nexus-interface-ready"));
})();