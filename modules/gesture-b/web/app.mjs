import {GestureSDK} from './src/gesture/sdk.mjs';
import {features,FEATURE_VERSION,validateModel,clamp} from './src/gesture/core.mjs';
const $=id=>document.getElementById(id),sdk=new GestureSDK($('video'));
const ctx=$('stage').getContext('2d'),ov=$('overlay').getContext('2d');
let character={x:.5,y:.62,arm:-.5,facing:1,attack:0,jump:0,active:false},rows=[],clips=0,capture=null,calibration=null,observation=null;
let frames=[],renders=[],latencies=[],inferences=[],classifiers=[],actions=[],latest=null,lastHud=0;
const connections=[[0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],[9,13],[13,14],[14,15],[15,16],[13,17],[17,18],[18,19],[19,20],[0,17]];
const quantile=(a,q)=>a.length?[...a].sort((a,b)=>a-b)[Math.min(a.length-1,Math.floor((a.length-1)*q))]:null;
function download(name,data,type='application/json'){const url=URL.createObjectURL(new Blob([data],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);}
function message(text){$('message').textContent=text;}
function cancelActivities(){capture=null;calibration=null;$('capture').disabled=false;$('calibrate').disabled=false;}
function consume(e){
 if(e.type==='gesture_status'){character.active=false;$('status').textContent=e.status==='lost'?'未跟踪 · 安全待机':'已跟踪 · 请张掌';}
 if(e.type==='gesture_control'){
  $('gesture').textContent=e.label;character.active=e.active;
  if(e.active){character.x=e.position.x;character.y=e.position.y;character.arm=e.armAngle;}
  $('status').textContent=e.active?'控制已激活':'已暂停 · 张掌激活';
 }
 if(e.type==='gesture_action'){
  if(e.action==='pinch')character.attack=performance.now();if(e.action==='raise')character.jump=performance.now();if(e.action==='swipe')character.facing*=-1;
  actions.unshift(e);actions=actions.slice(0,12);$('events').textContent=actions.map(x=>JSON.stringify(x)).join('\n');
  if(observation)observation.actions.push(e);
 }
}
sdk.addEventListener('gesture',e=>consume(e.detail));
sdk.addEventListener('error',e=>{message(e.detail.message);cancelActivities();$('start').disabled=false;});
$('start').onclick=async()=>{$('start').disabled=true;message('正在加载本地模型，随后申请摄像头权限…');try{await sdk.start();frames=[];latencies=[];inferences=[];classifiers=[];message('模型已加载。先张掌激活控制；可开始校准或采集。');}catch(e){const map={NotAllowedError:'摄像头权限被拒绝。请在浏览器站点设置中允许摄像头后重试。',NotFoundError:'未找到摄像头，请连接设备。',NotReadableError:'摄像头被其他程序占用或不可读取。'};message(map[e.name]||e.message);}finally{$('start').disabled=false;}};
$('stop').onclick=()=>{sdk.stop();cancelActivities();ov.clearRect(0,0,640,480);latest=null;message('摄像头已停止；尚未导出的采集数据仍保留在本页。');};
$('reset').onclick=()=>{sdk.engine.reset();sdk.selector.reset();character={x:.5,y:.62,arm:-.5,facing:1,attack:0,jump:0,active:false};cancelActivities();message('控制已重置，请重新张掌激活。');};
$('rule').onclick=()=>{if(observation)return message('请先结束当前观察，再切换分类器。');sdk.engine.model=null;sdk.engine.reset();character.active=false;$('mode').textContent='规则基线 · 尚未训练';};
$('model').onchange=async e=>{const f=e.target.files[0];if(!f)return;if(observation){$('model').value='';return message('请先结束当前观察，再切换分类器。');}try{const m=validateModel(JSON.parse(await f.text()));sdk.engine.model=m;sdk.engine.reset();character.active=false;$('mode').textContent='MLP · '+(m.modelVersion||'本地模型');message('模型已加载；独立测试集指标请查看训练输出报告。');}catch(e){message('模型未加载：'+e.message);}finally{$('model').value='';}};
$('capture').onclick=()=>{
 if(!sdk.running)return message('请先启动摄像头。');
 if(calibration)return message('请先完成校准。');
 if(!/^[A-Za-z0-9_-]{1,32}$/.test($('participant').value))return message('参与者编号请使用字母、数字、短横线或下划线。');
 const now=performance.now(),label=$('label').value,dynamic=['swipe','raise'].includes(label);
 capture={start:now+3000,end:now+3000+(dynamic?2000:10000),last:-Infinity,interval:dynamic?30:190,id:crypto.randomUUID(),count:0,meta:{participant:$('participant').value,label,light:$('light').value,distance:$('distance').value,device:$('device').value,dynamic}};
 $('capture').disabled=true;message('3 秒后采集 '+label+'；静态保持 10 秒，动态完成一次动作。');
};
$('export').onclick=()=>{if(!rows.length)return message('尚无可导出的数据。');download('gesture-'+new Date().toISOString().replaceAll(':','-')+'.jsonl',rows.map(x=>JSON.stringify(x)).join('\n')+'\n','application/x-ndjson');message('已导出 '+rows.length+' 帧。请保留匿名参与者编号，避免跨人划分泄漏。');};
const phases=['张掌','握拳','指向','捏合','移动覆盖舒适范围'];
$('calibrate').onclick=()=>{if(!sdk.running)return message('请先启动摄像头。');if(capture)return message('请先完成采集。');calibration={start:performance.now(),samples:[[],[],[],[],[]]};$('calibrate').disabled=true;};
function finishCalibration(c){
 $('calibrate').disabled=false;calibration=null;
 if(c.samples.some(s=>s.length<20)){ $('calibration').textContent='校准失败：部分步骤有效帧不足，请重试。';return;}
 const [open,fist,point,pinch,range]=c.samples,enter=clamp(quantile(pinch.map(x=>x.pinch),.9)+.04,.1,.4),exit=Math.max(enter+.08,Math.min(.6,quantile(open.map(x=>x.pinch),.1)*.65));
 const minX=quantile(range.map(p=>p.x),.05),maxX=quantile(range.map(p=>p.x),.95),minY=quantile(range.map(p=>p.y),.05),maxY=quantile(range.map(p=>p.y),.95);
 if(maxX-minX<.2||maxY-minY<.2||quantile(open.map(x=>x.pinch),.5)-quantile(pinch.map(x=>x.pinch),.5)<.2){$('calibration').textContent='校准失败：活动范围或张掌/捏合区分不足。请重试。';return;}
 sdk.engine.thresholds={enter,exit};sdk.engine.range={minX,maxX,minY,maxY};sdk.engine.reset();character.active=false;
 $('calibration').textContent='校准完成 · 已更新捏合阈值及舒适范围；请张掌激活。';
 // Fist/point steps are recorded for diagnostic feedback, not used to fit a classifier.
 download('calibration.json',JSON.stringify({version:'1.0',createdAt:new Date().toISOString(),thresholds:sdk.engine.thresholds,range:sdk.engine.range,counts:c.samples.map(s=>s.length),note:'握拳/指向仅采样确认，不代表分类验收通过'},null,2));
}
sdk.addEventListener('frame',({detail:d})=>{
 const now=performance.now();frames.push(now);latencies.push(d.pipelineMs);inferences.push(d.inferenceMs);classifiers.push(d.classifierMs);if(latencies.length>10000){latencies.shift();inferences.shift();classifiers.shift();}
 if(observation){observation.pipeline.push(d.pipelineMs);observation.inference.push(d.inferenceMs);if(d.classifierMs!==null)observation.classifier.push(d.classifierMs);}
 latest=d.selected;ov.clearRect(0,0,640,480);
 for(const h of d.hands){ov.strokeStyle=h===d.selected?'#e6b36a':'#768b98';ov.lineWidth=3;for(const [a,b] of connections){ov.beginPath();ov.moveTo(h.points[a].x*640,h.points[a].y*480);ov.lineTo(h.points[b].x*640,h.points[b].y*480);ov.stroke();}for(const p of h.points){ov.beginPath();ov.arc(p.x*640,p.y*480,3,0,Math.PI*2);ov.fillStyle='#fff2d0';ov.fill();}}
 if(!latest)return;
 const f=features(latest.points,latest.hand);
 if(capture&&now>=capture.start&&now<capture.end&&now-capture.last>=capture.interval){
  rows.push({schemaVersion:'1.0',featureVersion:FEATURE_VERSION,...capture.meta,clipId:capture.id,timestamp:d.timestamp,capturedAt:new Date().toISOString(),hand:latest.hand,landmarks:latest.points,features:f.vector});capture.last=now;capture.count++;
  $('count').textContent=rows.length+' 帧 · '+clips+' 段已完成';
 }
 if(calibration){const elapsed=now-calibration.start,phase=Math.floor(elapsed/6000);if(phase<5&&elapsed%6000>1000){calibration.samples[phase].push({pinch:f.pinch,x:1-latest.points[9].x,y:latest.points[9].y});}}
});
$('observe').onclick=()=>{if(!sdk.running)return message('请先启动摄像头。');if(observation)return message('观察已在进行，请先结束并导出。');observation={start:performance.now(),createdAt:new Date().toISOString(),falseTriggers:0,actions:[],pipeline:[],inference:[],classifier:[],model:sdk.engine.model?.modelVersion||'rule-baseline',renderIntervals:[]};};
$('false').onclick=()=>{if(!observation)return message('请先开始观察。');observation.falseTriggers++;};
$('report').onclick=()=>{if(!observation)return message('请先开始观察。');const o=observation,minutes=(performance.now()-o.start)/60000;observation=null;download('performance-report.json',JSON.stringify({createdAt:o.createdAt,durationMinutes:minutes,falseTriggers:o.falseTriggers,falseTriggersPerMinute:o.falseTriggers/minutes,observedActionCount:o.actions.length,actions:o.actions,pipelineP95Ms:quantile(o.pipeline,.95),inferenceP95Ms:quantile(o.inference,.95),classifierP95Ms:quantile(o.classifier,.95),classifierSampleCount:o.classifier.length,renderFrameIntervalP95Ms:quantile(o.renderIntervals,.95),meanRenderFps:o.renderIntervals.length?1000/(o.renderIntervals.reduce((a,b)=>a+b,0)/o.renderIntervals.length):null,model:o.model,minimumDurationMet:minutes>=5,endToEndP95Ms:null,macroF1:null,acceptance:'pending-real-device-and-independent-test',note:'仅处理链路计时；误触由观察员手动标注；无真人准确率与端到端测量'},null,2));$('observation').textContent='报告已导出 · 未自动宣称验收通过';};
window.addEventListener('keydown',e=>{if(['INPUT','SELECT','TEXTAREA'].includes(e.target.tagName)||e.repeat)return;const keys=['ArrowLeft','ArrowRight','ArrowUp','ArrowDown',' ','a','j','t'];if(!keys.includes(e.key))return;e.preventDefault();if(e.key==='ArrowLeft')character.x=clamp(character.x-.04);if(e.key==='ArrowRight')character.x=clamp(character.x+.04);if(e.key==='ArrowUp')character.y=clamp(character.y-.04);if(e.key==='ArrowDown')character.y=clamp(character.y+.04);if(e.key==='a')character.attack=performance.now();if(e.key==='j')character.jump=performance.now();if(e.key==='t')character.facing*=-1;if(e.key===' '){sdk.engine.active=false;character.active=false;}});
let previous=performance.now();
function draw(t){
 requestAnimationFrame(draw);renders.push(t);frames=frames.filter(x=>t-x<1000);renders=renders.filter(x=>t-x<1000);if(observation)observation.renderIntervals.push(t-previous);previous=t;
 ctx.clearRect(0,0,800,480);const g=ctx.createRadialGradient(400,210,30,400,230,460);g.addColorStop(0,'#fff1c4');g.addColorStop(1,'#c69758');ctx.fillStyle=g;ctx.fillRect(0,0,800,480);
 ctx.strokeStyle='#98683255';ctx.lineWidth=1;for(let x=40;x<800;x+=40){ctx.beginPath();ctx.moveTo(x,35);ctx.lineTo(x,435);ctx.stroke();}ctx.fillStyle='#684832';ctx.fillRect(0,430,800,50);ctx.fillStyle='#5a3029';ctx.fillRect(0,0,28,480);ctx.fillRect(772,0,28,480);ctx.fillRect(0,0,800,22);
 ctx.font='16px sans-serif';ctx.fillStyle='#684832';ctx.fillText('占位角色 / 手势接口验证',48,53);
 const jt=(t-character.jump)/650,jump=character.jump&&jt<1?Math.sin(jt*Math.PI)*65:0,attack=character.attack&&t-character.attack<350;
 const x=80+character.x*640,y=150+character.y*225-jump;
 ctx.save();ctx.translate(x,y);ctx.scale(character.facing,1);ctx.fillStyle='#772f24dd';ctx.strokeStyle='#3e281e';ctx.lineWidth=4;
 ctx.beginPath();ctx.moveTo(-23,-45);ctx.lineTo(25,-45);ctx.lineTo(37,37);ctx.lineTo(-35,37);ctx.closePath();ctx.fill();ctx.stroke();
 ctx.beginPath();ctx.arc(0,-69,26,0,Math.PI*2);ctx.fill();ctx.stroke();ctx.fillStyle='#e3b665';ctx.beginPath();ctx.arc(11,-74,3,0,Math.PI*2);ctx.fill();
 ctx.strokeStyle='#5a2b20';ctx.lineWidth=13;for(const side of [-1,1]){ctx.beginPath();ctx.moveTo(side*17,35);ctx.lineTo(side*29,76);ctx.stroke();}
 const a=attack?-.2:character.arm;const ax=20+Math.cos(a)*62,ay=-25+Math.sin(a)*62;ctx.lineWidth=12;ctx.beginPath();ctx.moveTo(20,-30);ctx.lineTo(ax,ay);ctx.stroke();ctx.strokeStyle='#563e2a';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(ax,ay);ctx.lineTo(ax+20,480-y);ctx.moveTo(0,20);ctx.lineTo(0,480-y);ctx.stroke();ctx.fillStyle='#e3b665';for(let j=-1;j<=1;j++){ctx.beginPath();ctx.arc(j*13,0,4,0,Math.PI*2);ctx.fill();}ctx.restore();
 if(capture){if(t<capture.start)message('准备：'+Math.ceil((capture.start-t)/1000)+' 秒后开始 '+capture.meta.label);else if(t<capture.end)message('采集中：'+capture.meta.label+' · 剩余 '+Math.ceil((capture.end-t)/1000)+' 秒 · '+capture.count+' 帧');else{if(capture.count>0)clips++;message(capture.count?'本段完成：'+capture.count+' 帧；可更换手型、左右手或环境后继续。':'本段无有效手，请重新采集。');capture=null;$('capture').disabled=false;$('count').textContent=rows.length+' 帧 · '+clips+' 段';}}
 if(calibration){const phase=Math.floor((t-calibration.start)/6000);if(phase>=5)finishCalibration(calibration);else $('calibration').textContent=(phase+1)+'/5：'+phases[phase]+' · '+(6-Math.floor((t-calibration.start)%6000/1000))+' 秒';}
 if(observation)$('observation').textContent=((t-observation.start)/60000).toFixed(1)+' 分钟 · '+observation.falseTriggers+' 次误触';
 if(t-lastHud>500){lastHud=t;$('renderFps').textContent=renders.length;$('inferFps').textContent=frames.length;$('p95').textContent=frames.length?(quantile(latencies,.95)?.toFixed(1)||'—'):'—';}
}
requestAnimationFrame(draw);
document.addEventListener('visibilitychange',()=>{if(document.hidden&&sdk.running){sdk.stop();cancelActivities();message('页面进入后台，已停止摄像头。返回后请重新启动。');}});
window.addEventListener('beforeunload',e=>{sdk.stop();if(rows.length){e.preventDefault();e.returnValue='';}});
