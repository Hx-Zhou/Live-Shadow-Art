import {mkdir,writeFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
const base='https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304';
const files=[['vision_bundle.mjs',base+'/vision_bundle.mjs'],...['vision_wasm_internal.js','vision_wasm_internal.wasm','vision_wasm_nosimd_internal.js','vision_wasm_nosimd_internal.wasm'].map(f=>['wasm/'+f,base+'/wasm/'+f]),['hand_landmarker.task','https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task']];
const manifest=[];
for(const [name,url] of files){const res=await fetch(url,{signal:AbortSignal.timeout(120000)});if(!res.ok)throw Error(`${res.status}: ${url}`);const bytes=Buffer.from(await res.arrayBuffer());const dest=new URL('../web/vendor/'+name,import.meta.url);await mkdir(new URL('./',dest),{recursive:true});await writeFile(dest,bytes);manifest.push({name,url,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')});console.log(name,bytes.length);}
await writeFile(new URL('../web/vendor/manifest.json',import.meta.url),JSON.stringify(manifest,null,2));
