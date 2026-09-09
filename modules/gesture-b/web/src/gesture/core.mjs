export const LABELS=['open_palm','fist','point','pinch','victory','None'];
export const FEATURE_VERSION='wrist-scale-mirror-72-v1';
export const clamp=(n,a=0,b=1)=>Math.max(a,Math.min(b,n));
export const distance=(a,b)=>Math.hypot(a.x-b.x,a.y-b.y,(a.z||0)-(b.z||0));
export function valid(p){return Array.isArray(p)&&p.length===21&&p.every(p=>['x','y','z'].every(k=>Number.isFinite(p[k])));}
const angle=(a,b,c)=>{const u=[a.x-b.x,a.y-b.y,a.z-b.z],v=[c.x-b.x,c.y-b.y,c.z-b.z];return Math.acos(clamp(u.reduce((s,n,i)=>s+n*v[i],0)/(Math.hypot(...u)*Math.hypot(...v)||1),-1,1))/Math.PI;};
export function features(p,hand='right'){
 if(!valid(p))throw Error('Expected 21 finite x/y/z landmarks');
 const scale=Math.max(distance(p[5],p[17]),distance(p[0],p[9]),1e-5);
 const q=p.map(v=>({x:(v.x-p[0].x)/scale*(hand==='left'?-1:1),y:(v.y-p[0].y)/scale,z:(v.z-p[0].z)/scale}));
 const angles=[[1,2,4],[5,6,8],[9,10,12],[13,14,16],[17,18,20]].map(([a,b,c])=>angle(q[a],q[b],q[c]));
 const distances=[8,12,16,20].map(i=>distance(q[4],q[i]));
 return {vector:[...q.flatMap(v=>[v.x,v.y,v.z]),...angles,...distances],angles,pinch:distances[0],scale};
}
export function classify(f,pinching=false,thresholds={enter:.28,exit:.42}){
 if(f.pinch<(pinching?thresholds.exit:thresholds.enter))return {label:'pinch',confidence:.85};
 const e=f.angles.map(a=>a>.78),b=f.angles.map(a=>a<.68);
 if(e.slice(1).every(Boolean)&&f.pinch>.55)return {label:'open_palm',confidence:.85};
 if(b.slice(1).every(Boolean))return {label:'fist',confidence:.85};
 if(e[1]&&b.slice(2).every(Boolean))return {label:'point',confidence:.85};
 if(e[1]&&e[2]&&b[3]&&b[4])return {label:'victory',confidence:.85};
 return {label:'None',confidence:0};
}
export function validateModel(m){
 if(m.featureVersion!==FEATURE_VERSION||m.labels?.length!==6||!LABELS.every(l=>m.labels.includes(l)))throw Error('Model labels / feature version mismatch');
 const finite=a=>Array.isArray(a)&&a.every(Number.isFinite);
 if(!finite(m.mean)||m.mean.length!==72||!finite(m.scale)||m.scale.length!==72||m.scale.some(v=>v<=0))throw Error('Invalid normalization');
 const sizes=[72,128,64,6];
 if(m.weights?.length!==3||m.biases?.length!==3)throw Error('Expected 72-128-64-6 MLP');
 for(let l=0;l<3;l++)if(!Array.isArray(m.weights[l])||m.weights[l].length!==sizes[l]||m.weights[l].some(r=>!finite(r)||r.length!==sizes[l+1])||!finite(m.biases[l])||m.biases[l].length!==sizes[l+1])throw Error('Invalid layer '+l);
 return m;
}
export function inferMLP(vector,m){
 let x=vector.map((v,i)=>(v-m.mean[i])/m.scale[i]);
 for(let l=0;l<m.weights.length;l++){const w=m.weights[l];x=m.biases[l].map((b,j)=>b+x.reduce((s,n,i)=>s+n*w[i][j],0));if(l<m.weights.length-1)x=x.map(v=>Math.max(0,v));}
 const max=Math.max(...x),p=x.map(v=>Math.exp(v-max)),sum=p.reduce((a,b)=>a+b,0),i=p.indexOf(Math.max(...p));return {label:m.labels[i],confidence:p[i]/sum};
}
// Ownership is approximate wrist continuity, not biometric identity recognition.
export class HandSelector{
 constructor(){this.reset();}
 reset(){this.owner=null;this.lastSeen=-Infinity;}
 select(hands,t){
  const candidates=hands.filter(h=>valid(h.points));
  if(this.owner){const match=candidates.filter(h=>h.hand===this.owner.hand).sort((a,b)=>distance(a.points[0],this.owner.points[0])-distance(b.points[0],this.owner.points[0]))[0];
   if(match&&distance(match.points[0],this.owner.points[0])<.25){this.owner=match;this.lastSeen=t;return match;}
   if(t-this.lastSeen<1000)return null;this.reset();
  }
  if(candidates.length!==1)return null;
  this.owner=candidates[0];this.lastSeen=t;return this.owner;
 }
}
export class GestureEngine{
 constructor(options={}){this.options={confidence:.75,holdMs:125,cooldown:500,...options};this.model=null;this.thresholds={enter:.28,exit:.42};this.range={minX:.12,maxX:.88,minY:.12,maxY:.88};this.reset();}
 reset(){this.lastT=-Infinity;this.lastSeen=-Infinity;this.history=[];this.path=[];this.smooth=null;this.stable='None';this.candidate='None';this.since=0;this.lastActions={};this.active=false;this.lost=true;this.pinching=false;}
 lose(t){if(t-this.lastSeen<=this.options.holdMs)return [];const changed=!this.lost;this.history=[];this.path=[];this.smooth=null;this.stable='None';this.candidate='None';this.pinching=false;this.active=false;this.lost=true;return changed?[{version:'1.0',type:'gesture_status',status:'lost',timestamp:t}]:[];}
 update(points,hand,t){
  if(!Number.isFinite(t)||t<=this.lastT)return [];this.lastT=t;
  if(!valid(points))return this.lose(t);
  if(t-this.lastSeen>this.options.holdMs)this.lose(t);
  const f=features(points,hand),classifierStart=performance.now();
  const raw=this.model?inferMLP(f.vector,this.model):classify(f,this.pinching,this.thresholds);
  this.classifierMs=performance.now()-classifierStart;
  this.pinching=raw.label==='pinch';const label=raw.confidence>=this.options.confidence?raw.label:'None';
  const events=[];if(this.lost)events.push({version:'1.0',type:'gesture_status',status:'tracking',timestamp:t});this.lost=false;this.lastSeen=t;
  this.history.push(label);if(this.history.length>5)this.history.shift();
  if(label!==this.candidate){this.candidate=label;this.since=t;}
  const votes=this.history.filter(x=>x===label).length;
  const center=[0,5,9,13,17].reduce((a,i)=>({x:a.x+(1-points[i].x)/5,y:a.y+points[i].y/5}),{x:0,y:0});
  this.smooth=this.smooth?{x:this.smooth.x*.65+center.x*.35,y:this.smooth.y*.65+center.y*.35}:center;
  const r=this.range,position={x:clamp((this.smooth.x-r.minX)/(r.maxX-r.minX)),y:clamp((this.smooth.y-r.minY)/(r.maxY-r.minY))};
  const dx=points[5].x-points[8].x,dy=points[8].y-points[5].y,len=Math.hypot(dx,dy)||1,direction={x:dx/len,y:dy/len};
  const fire=action=>{if(t-(this.lastActions[action]??-Infinity)<this.options.cooldown)return;this.lastActions[action]=t;const dynamic=['swipe','raise'].includes(action);events.push({version:'1.0',type:'gesture_action',action,confidence:dynamic?.85:raw.confidence,confidenceKind:dynamic?'trajectory_rule_score':this.model?'model_probability':'rule_score',hand,position,direction,timestamp:t});};
  if(label!==this.stable&&votes>=4&&(label!=='open_palm'||this.history.length===5&&votes===5)&&(label!=='fist'||t-this.since>=300)){
   this.stable=label;
   if(label==='open_palm'){this.active=true;fire('activate');}
   else if(label==='fist'){this.active=false;this.path=[];fire('pause');}
   else if(this.active&&['pinch','point','victory'].includes(label))fire(label);
  }
  if(this.active){
   this.path.push({x:center.x,y:center.y,t});this.path=this.path.filter(p=>t-p.t<=250);
   const old=this.path[0],dt=(t-old.t)/1000,mx=center.x-old.x,my=center.y-old.y;
   if(dt>=.08&&label!=='pinch'){
    if(Math.abs(mx)>.18&&Math.abs(mx)>Math.abs(my)*1.8&&Math.abs(mx)/dt>.85){fire('swipe');this.path=[];}
    else if(my<-.16&&Math.abs(my)>Math.abs(mx)*1.8&&-my/dt>.75){fire('raise');this.path=[];}
   }
  }else this.path=[];
  events.push({version:'1.0',type:'gesture_control',hand,position,direction,bodyAngle:Math.atan2(points[5].y-points[0].y,points[0].x-points[5].x),armAngle:clamp(Math.atan2(dy,dx),-2.6,2.6),pinchStrength:clamp(1-f.pinch/.65),active:this.active,label,confidence:raw.confidence,timestamp:t});
  return events;
 }
}
