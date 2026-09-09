import {GestureEngine,HandSelector} from './core.mjs';
export class GestureSDK extends EventTarget{
 constructor(video){super();this.video=video;this.engine=new GestureEngine();this.selector=new HandSelector();this.running=false;this.generation=0;}
 emit(type,detail){this.dispatchEvent(new CustomEvent(type,{detail}));}
 async start(){
  this.stop();const generation=++this.generation;
  if(!navigator.mediaDevices?.getUserMedia)throw Error('摄像头需要 localhost 或 HTTPS，请勿双击 HTML 文件运行。');
  // MediaPipe's WASM loader calls importScripts; it requires a classic Worker.
  const worker=new Worker(new URL('./worker.mjs',import.meta.url));this.worker=worker;
  try{
   await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(Error('模型加载超时；请先运行 npm run setup')),60000);this.cancelInit=()=>{clearTimeout(timeout);reject(Error('启动已取消'));};worker.onerror=e=>{clearTimeout(timeout);reject(Error(e.message||'Worker 启动失败'));};worker.onmessage=({data})=>{if(data.type==='ready'){clearTimeout(timeout);resolve();}else if(data.type==='error'){clearTimeout(timeout);reject(Error(data.message));}};worker.postMessage({type:'init'});});
   if(generation!==this.generation)throw Error('启动已取消');this.cancelInit=null;
   const stream=await navigator.mediaDevices.getUserMedia({video:{width:{ideal:640},height:{ideal:480},frameRate:{ideal:30,max:30}},audio:false});
   if(generation!==this.generation){stream.getTracks().forEach(t=>t.stop());throw Error('启动已取消');}
   this.stream=stream;this.video.srcObject=stream;await this.video.play();
   if(generation!==this.generation)throw Error('启动已取消');
   this.running=true;this.busy=false;this.lastVideo=-1;this.lastSent=-Infinity;this.engine.reset();this.selector.reset();
   this.stream.getVideoTracks()[0].addEventListener('ended',()=>this.fail('摄像头已断开，请重新启动。'));
   worker.onerror=e=>this.fail(e.message||'推理线程异常');
   worker.onmessage=({data})=>{
    if(generation!==this.generation)return;
    if(data.type==='error'){this.fail(data.message);return;}
    if(data.type!=='result')return;this.busy=false;
    const now=performance.now();if(now-data.timestamp>250){this.emitEvents(this.engine.lose(now));return;}
    const hand=this.selector.select(data.hands,data.timestamp),begin=performance.now();
    this.emitEvents(this.engine.update(hand?.points,hand?.hand,data.timestamp));
    this.emit('frame',{...data,selected:hand,classifierMs:hand?this.engine.classifierMs:null,classifierAndFilterMs:performance.now()-begin,pipelineMs:performance.now()-data.timestamp});
   };
   const loop=async()=>{
    if(!this.running||generation!==this.generation)return;
    this.raf=requestAnimationFrame(loop);const now=performance.now();
    this.emitEvents(this.engine.lose(now));
    if(this.busy&&now-this.lastSent>5000){this.fail('推理线程无响应，请重启摄像头。');return;}
    if(this.busy||this.video.readyState<2||this.video.currentTime===this.lastVideo||now-this.lastSent<32)return;
    this.busy=true;this.lastSent=now;this.lastVideo=this.video.currentTime;
    try{const bitmap=await createImageBitmap(this.video);if(generation!==this.generation){bitmap.close();return;}worker.postMessage({type:'frame',bitmap,timestamp:now},[bitmap]);}catch(e){this.fail(e.message);}
   };this.raf=requestAnimationFrame(loop);
  }catch(e){if(generation===this.generation)this.stop();throw e;}
 }
 emitEvents(events){for(const e of events)this.emit('gesture',e);}
 fail(message){if(!this.worker&&!this.stream)return;this.stop();this.emit('error',{message});}
 stop(){this.generation++;this.running=false;this.cancelInit?.();this.cancelInit=null;cancelAnimationFrame(this.raf);this.worker?.terminate();this.worker=null;this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;this.video.srcObject=null;this.engine.reset();this.selector.reset();this.emit('gesture',{version:'1.0',type:'gesture_status',status:'lost',timestamp:performance.now()});}
}
