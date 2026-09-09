import {readFile,writeFile} from 'node:fs/promises';
import {GestureEngine,valid} from '../web/src/gesture/core.mjs';
const [output,...inputs]=process.argv.slice(2);if(!output||!inputs.length)throw Error('Usage: node tools/evaluate-trajectories.mjs report.json capture.jsonl [...]');
const clips=new Map();
for(const file of inputs)for(const line of (await readFile(file,'utf8')).split(/\r?\n/)){
 if(!line.trim())continue;const r=JSON.parse(line);if(!['swipe','raise'].includes(r.label))continue;
 if(!r.clipId||!r.participant||!Number.isFinite(r.timestamp)||!valid(r.landmarks))throw Error('Invalid dynamic sample');
 const key=r.participant+'|'+r.clipId;if(!clips.has(key))clips.set(key,[]);clips.get(key).push(r);
}
const results=[];
for(const [id,rows] of clips){rows.sort((a,b)=>a.timestamp-b.timestamp);if(new Set(rows.map(r=>r.label)).size!==1)throw Error('Inconsistent clip label '+id);
 const e=new GestureEngine(),events=[];e.lost=false;e.active=true;e.lastSeen=rows[0].timestamp;
 for(const r of rows)events.push(...e.update(r.landmarks,r.hand,r.timestamp).filter(x=>x.type==='gesture_action'&&['swipe','raise'].includes(x.action)));
 const label=rows[0].label,hits=events.filter(x=>x.action===label);
 results.push({id,participant:rows[0].participant,label,frames:rows.length,durationMs:rows.at(-1).timestamp-rows[0].timestamp,hit:hits.length>0,duplicate:Math.max(0,hits.length-1),wrong:events.length-hits.length,firstHitFromClipStartMs:hits.length?hits[0].timestamp-rows[0].timestamp:null,events});
}
if(!results.length)throw Error('No dynamic clips found');
await writeFile(output,JSON.stringify({status:'clip-level-only',initialControlState:'active',clips:results.length,clipRecall:results.filter(r=>r.hit).length/results.length,duplicateEvents:results.reduce((a,r)=>a+r.duplicate,0),wrongEvents:results.reduce((a,r)=>a+r.wrong,0),results,note:'Clip start is NOT annotated motion onset; this timing is NOT end-to-end latency. False triggers require natural negative sequences and manual observation.'},null,2));console.log('Evaluated '+results.length+' labeled clips');
