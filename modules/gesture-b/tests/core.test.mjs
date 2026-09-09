import test from 'node:test';
import assert from 'node:assert/strict';
import {features,classify,GestureEngine,HandSelector,inferMLP,validateModel,FEATURE_VERSION,LABELS} from '../web/src/gesture/core.mjs';
const open=()=>[[.5,.8],[.4,.72],[.32,.65],[.25,.6],[.18,.55],[.4,.6],[.4,.45],[.4,.32],[.4,.2],[.5,.57],[.5,.4],[.5,.27],[.5,.14],[.6,.59],[.6,.43],[.6,.3],[.6,.19],[.69,.64],[.69,.5],[.69,.39],[.69,.3]].map(([x,y])=>({x,y,z:0}));
const fist=()=>{const p=open();for(const [b,j,t] of [[5,6,8],[9,10,12],[13,14,16],[17,18,20]]){p[j]={x:p[b].x,y:p[b].y-.08,z:0};p[t]={x:p[b].x+.015,y:p[b].y+.06,z:0};}return p;};
const pinch=()=>{const p=open();p[4]={...p[8],x:p[8].x+.01};return p;};
const run=(e,p,start,n,delta=33)=>Array.from({length:n},(_,i)=>e.update(p,'right',start+i*delta)).flat();
test('72 features are translation / scale invariant and mirror normalized',()=>{
 const p=open(),a=features(p).vector,b=features(p.map(q=>({x:q.x*2+1,y:q.y*2-1,z:0}))).vector,c=features(p.map(q=>({...q,x:1-q.x})),'left').vector;
 assert.equal(a.length,72);a.forEach((v,i)=>{assert.ok(Math.abs(v-b[i])<1e-7);assert.ok(Math.abs(v-c[i])<1e-7);});
});
test('reject malformed landmarks',()=>{assert.throws(()=>features([]));const p=open();p[0].x=NaN;assert.throws(()=>features(p));});
test('rule labels and pinch hysteresis',()=>{
 assert.equal(classify(features(open())).label,'open_palm');assert.equal(classify(features(fist())).label,'fist');assert.equal(classify(features(pinch())).label,'pinch');
 const p=fist();for(const i of [5,6,7,8])p[i]=open()[i];assert.equal(classify(features(p)).label,'point');for(const i of [9,10,11,12])p[i]=open()[i];assert.equal(classify(features(p)).label,'victory');
 const f={pinch:.35,angles:[0,0,0,0,0]};assert.notEqual(classify(f,false).label,'pinch');assert.equal(classify(f,true).label,'pinch');
});
test('activation needs five frames; holding pinch fires once; release re-arms',()=>{
 const e=new GestureEngine();assert.equal(run(e,open(),0,4).filter(x=>x.action==='activate').length,0);
 assert.equal(e.update(open(),'right',132).filter(x=>x.action==='activate').length,1);
 assert.equal(run(e,pinch(),165,30).filter(x=>x.action==='pinch').length,1);
 run(e,open(),1155,6);assert.equal(run(e,pinch(),1353,6).filter(x=>x.action==='pinch').length,1);
});
test('fist requires 300ms; paused input cannot trigger attack',()=>{
 const e=new GestureEngine();run(e,open(),0,5);assert.equal(run(e,fist(),165,9).filter(x=>x.action==='pause').length,0);
 assert.equal(run(e,fist(),462,3).filter(x=>x.action==='pause').length,1);assert.equal(e.active,false);
 assert.equal(run(e,pinch(),561,8).filter(x=>x.action==='pinch').length,0);
});
test('short dropout holds; >125ms loss pauses; reacquisition needs activation',()=>{
 const e=new GestureEngine();run(e,open(),0,5);assert.deepEqual(e.update(null,'right',200),[]);assert.equal(e.active,true);
 assert.equal(e.update(null,'right',260)[0].status,'lost');assert.equal(e.active,false);assert.deepEqual(e.update(null,'right',300),[]);
 assert.equal(run(e,pinch(),330,8).filter(x=>x.action==='pinch').length,0);
});
test('clamps stage position and ignores out of order timestamp',()=>{
 const e=new GestureEngine(),p=open().map(q=>({...q,x:q.x+3}));const events=e.update(p,'right',1);assert.equal(events.at(-1).position.x,0);assert.deepEqual(e.update(p,'right',1),[]);
});
test('fast horizontal motion emits swipe; stationary open hand does not',()=>{
 const e=new GestureEngine();assert.equal(run(e,open(),0,10).filter(x=>x.action==='swipe').length,0);
 let events=[];for(let i=1;i<=6;i++)events.push(...e.update(open().map(p=>({...p,x:p.x-i*.045})),'right',297+i*33));
 assert.equal(events.filter(x=>x.action==='swipe').length,1);
});
test('fast upward motion emits raise; paused motion does not',()=>{
 for(const active of [true,false]){const e=new GestureEngine();if(active)run(e,open(),0,5);const events=[];for(let i=1;i<=6;i++)events.push(...e.update(open().map(p=>({...p,y:p.y-i*.045})),'right',132+i*33));assert.equal(events.filter(x=>x.action==='raise').length,active?1:0);}
});
test('hand ownership does not jump to bystander and ambiguous initial input is ignored',()=>{
 const s=new HandSelector(),a={points:open(),hand:'right'},b={points:open().map(p=>({...p,x:p.x+.6})),hand:'left'};
 assert.equal(s.select([a,b],0),null);assert.equal(s.select([a],10),a);assert.equal(s.select([b],100),null);assert.equal(s.select([b],1200),b);
});
test('model validator rejects NaN / incompatible dimensions; softmax is stable',()=>{
 const sizes=[72,128,64,6],m={featureVersion:FEATURE_VERSION,labels:LABELS,mean:Array(72).fill(0),scale:Array(72).fill(1),weights:sizes.slice(0,-1).map((n,i)=>Array.from({length:n},()=>Array(sizes[i+1]).fill(0))),biases:sizes.slice(1).map(n=>Array(n).fill(0))};
 m.biases[2][1]=1000;validateModel(m);assert.deepEqual(inferMLP(Array(72).fill(0),m),{label:'fist',confidence:1});m.scale[0]=0;assert.throws(()=>validateModel(m));
});
