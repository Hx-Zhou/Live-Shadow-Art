import {readFile,writeFile} from 'node:fs/promises';
import {features,LABELS,FEATURE_VERSION,valid} from '../web/src/gesture/core.mjs';
const [output,...inputs]=process.argv.slice(2);
if(!output||!inputs.length)throw Error('Usage: node tools/prepare.mjs prepared.json capture1.jsonl [capture2.jsonl ...]');
const rows=[],seen=new Set(),audit={skippedDynamic:0,duplicates:0};
for(const file of inputs){const lines=(await readFile(file,'utf8')).split(/\r?\n/);for(let i=0;i<lines.length;i++){
 if(!lines[i].trim())continue;let r;try{r=JSON.parse(lines[i]);}catch{throw Error(`${file}:${i+1}: invalid JSON`);}
 if(['swipe','raise'].includes(r.label)){audit.skippedDynamic++;continue;}
 if(!LABELS.includes(r.label)||!valid(r.landmarks)||!['left','right'].includes(r.hand)||!r.participant||!r.clipId||!Number.isFinite(r.timestamp))throw Error(`${file}:${i+1}: invalid sample`);
 const key=[r.participant,r.clipId,r.timestamp].join('|');if(seen.has(key)){audit.duplicates++;continue;}seen.add(key);
 // Never trust exported vectors: recompute with the same module used by live inference.
 rows.push({...r,featureVersion:FEATURE_VERSION,features:features(r.landmarks,r.hand).vector});
}}
await writeFile(output,JSON.stringify({featureVersion:FEATURE_VERSION,labels:LABELS,audit,rows}));console.log(JSON.stringify({samples:rows.length,participants:[...new Set(rows.map(r=>r.participant))],...audit},null,2));
