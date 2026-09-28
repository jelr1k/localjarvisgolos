let blackHoleCleanup=null;
function initBlackHole(){
  if (blackHoleCleanup) blackHoleCleanup();
  const canvas=document.getElementById("blackHoleCanvas");
  if(!canvas) return;
  const ctx=canvas.getContext("2d");
  let W=0,H=0,DPR=1,cx=0,cy=0,scale=1;

const TAU=Math.PI*2;
const particles=[];
const PARTICLES=2200;

function resize(){
  DPR=Math.min(devicePixelRatio||1,2);
  W=canvas.clientWidth; H=canvas.clientHeight;
  canvas.width=W*DPR; canvas.height=H*DPR;
  canvas.style.width=W+"px"; canvas.style.height=H+"px";
  ctx.setTransform(DPR,0,0,DPR,0,0);

  cx=W*.5;
  cy=H*.52;
  scale=Math.min(W,H)/700;
}
window.addEventListener("resize",resize);
resize();

function rand(a,b){return a+Math.random()*(b-a)}

function newParticle(p){
  p.r=rand(92,310)*scale;
  p.a=rand(0,TAU);
  p.speed=(0.0018 + 0.020*Math.pow(105*scale/Math.max(p.r,80*scale),.78));
  p.speed*=rand(.72,1.28);
  p.size=rand(.45,2.0)*scale;
  p.alpha=rand(.18,.85);
  const hot=Math.max(0,1-(p.r/(230*scale)));
  p.hue=rand(14,38)-hot*5;
  p.light=55+hot*30;
  p.trail=[];
}
for(let i=0;i<PARTICLES;i++){
  const p={};
  newParticle(p);
  particles.push(p);
}

const stars=[];
for(let i=0;i<150;i++){
  stars.push({
    x:Math.random(),
    y:Math.random(),
    r:rand(.25,1.15),
    a:rand(.25,.9)
  });
}

function drawStars(t){
  ctx.save();
  for(const s of stars){
    const x=s.x*W, y=s.y*H;
    const pulse=.82+.18*Math.sin(t*.0007+s.x*20);
    ctx.fillStyle=`rgba(255,220,190,${s.a*pulse})`;
    ctx.beginPath();
    ctx.arc(x,y,s.r,0,TAU);
    ctx.fill();
  }
  ctx.restore();
}

function drawNebula(){
  const g=ctx.createRadialGradient(cx,cy,20,cx,cy,Math.max(W,H)*.72);
  g.addColorStop(0,"rgba(46,15,5,.42)");
  g.addColorStop(.25,"rgba(18,7,5,.22)");
  g.addColorStop(.58,"rgba(5,3,5,.12)");
  g.addColorStop(1,"rgba(0,0,2,0)");
  ctx.fillStyle=g;
  ctx.fillRect(0,0,W,H);
}

function drawDisk(t){
  ctx.save();
  ctx.globalCompositeOperation="lighter";

  const R=320*scale;
  const haze=ctx.createRadialGradient(cx,cy,65*scale,cx,cy,R);
  haze.addColorStop(0,"rgba(255,90,15,.20)");
  haze.addColorStop(.23,"rgba(255,65,5,.15)");
  haze.addColorStop(.48,"rgba(210,40,3,.055)");
  haze.addColorStop(1,"rgba(120,15,0,0)");

  ctx.fillStyle=haze;
  ctx.beginPath();
  ctx.ellipse(cx,cy,R,R*.27,0,0,TAU);
  ctx.fill();

  for(const p of particles){
    p.a += p.speed;
    const wobble=Math.sin(p.a*4.0+p.r*.018)*2.4*scale;
    const rr=p.r+wobble;
    const x=cx+Math.cos(p.a)*rr;
    const y=cy+Math.sin(p.a)*rr*.245;

    p.trail.push([x,y]);
    if(p.trail.length>7)p.trail.shift();

    for(let j=1;j<p.trail.length;j++){
      const q=p.trail[j-1];
      const u=j/p.trail.length;
      ctx.strokeStyle=`hsla(${p.hue},100%,${p.light+u*10}%,${p.alpha*u*u*.42})`;
      ctx.lineWidth=p.size*(.4+u*1.1);
      ctx.beginPath();
      ctx.moveTo(q[0],q[1]);
      ctx.lineTo(p.trail[j][0],p.trail[j][1]);
      ctx.stroke();
    }

    ctx.fillStyle=`hsla(${p.hue},100%,${p.light}%,${p.alpha})`;
    ctx.beginPath();
    ctx.arc(x,y,p.size,0,TAU);
    ctx.fill();
  }

  ctx.restore();
}

function drawInnerRing(t){
  const r=92*scale;
  ctx.save();
  ctx.globalCompositeOperation="lighter";

  for(let i=0;i<5;i++){
    const rr=r+i*5*scale;
    const grad=ctx.createLinearGradient(cx-rr,cy,cx+rr,cy);
    grad.addColorStop(0,"rgba(255,65,5,0)");
    grad.addColorStop(.18,"rgba(255,100,15,.20)");
    grad.addColorStop(.40,"rgba(255,195,75,.72)");
    grad.addColorStop(.50,"rgba(255,245,190,.95)");
    grad.addColorStop(.60,"rgba(255,130,20,.72)");
    grad.addColorStop(.82,"rgba(255,50,5,.16)");
    grad.addColorStop(1,"rgba(255,50,5,0)");

    ctx.strokeStyle=grad;
    ctx.lineWidth=(5-i)*1.15*scale;
    ctx.beginPath();
    ctx.ellipse(cx,cy,rr,rr*.25,0,0,TAU);
    ctx.stroke();
  }

  ctx.restore();
}

function drawLens(){
  ctx.save();
  ctx.globalCompositeOperation="lighter";
  const r=88*scale;

  for(const side of [-1,1]){
    const g=ctx.createLinearGradient(cx-r*1.5,cy,cx+r*1.5,cy);
    g.addColorStop(0,"rgba(255,60,5,0)");
    g.addColorStop(.28,"rgba(255,105,20,.16)");
    g.addColorStop(.5,"rgba(255,225,145,.82)");
    g.addColorStop(.72,"rgba(255,100,10,.16)");
    g.addColorStop(1,"rgba(255,40,0,0)");

    ctx.strokeStyle=g;
    ctx.lineWidth=4*scale;
    ctx.beginPath();
    ctx.arc(cx,cy,r,Math.PI+(side<0?0:.02),TAU-(side<0?.02:0));
    ctx.stroke();
  }

  ctx.restore();
}

function drawBlackHole(t){
  const r=72*scale;

  const glow=ctx.createRadialGradient(cx,cy,r*.72,cx,cy,r*1.65);
  glow.addColorStop(0,"rgba(0,0,0,1)");
  glow.addColorStop(.52,"rgba(0,0,0,1)");
  glow.addColorStop(.72,"rgba(255,80,10,.13)");
  glow.addColorStop(1,"rgba(255,45,0,0)");

  ctx.fillStyle=glow;
  ctx.beginPath();
  ctx.arc(cx,cy,r*1.65,0,TAU);
  ctx.fill();

  ctx.fillStyle="#000000";
  ctx.beginPath();
  ctx.arc(cx,cy,r,0,TAU);
  ctx.fill();

  ctx.strokeStyle="rgba(255,105,25,.24)";
  ctx.lineWidth=1.5*scale;
  ctx.stroke();
}

function drawPulse(t){
  const p=.5+.5*Math.sin(t*.0015);
  const r=(115+p*7)*scale;

  const g=ctx.createRadialGradient(cx,cy,r*.35,cx,cy,r);
  g.addColorStop(0,"rgba(255,150,30,0)");
  g.addColorStop(.72,"rgba(255,80,5,0)");
  g.addColorStop(.91,`rgba(255,100,15,${.08+p*.04})`);
  g.addColorStop(1,"rgba(255,40,0,0)");

  ctx.fillStyle=g;
  ctx.beginPath();
  ctx.arc(cx,cy,r,0,TAU);
  ctx.fill();
}

let stopped=false;
let rafId=0;
function frame(t){
  ctx.clearRect(0,0,W,H);
  drawNebula();
  drawStars(t);
  drawDisk(t);
  drawLens();
  drawInnerRing(t);
  drawBlackHole(t);
  drawPulse(t);

  if(!stopped) rafId=requestAnimationFrame(frame);
}
rafId=requestAnimationFrame(frame);

blackHoleCleanup=()=>{
  stopped=true;
  cancelAnimationFrame(rafId);
  window.removeEventListener("resize",resize);
  blackHoleCleanup=null;
};
}