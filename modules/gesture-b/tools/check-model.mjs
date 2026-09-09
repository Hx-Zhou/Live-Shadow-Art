import {readFile} from 'node:fs/promises';
import {validateModel,inferMLP} from '../web/src/gesture/core.mjs';
const [modelPath='models/gesture/model.json',parityPath='models/gesture/parity.json']=process.argv.slice(2);
const m=validateModel(JSON.parse(await readFile(modelPath,'utf8'))),p=JSON.parse(await readFile(parityPath,'utf8'));
for(let i=0;i<p.features.length;i++){const actual=inferMLP(p.features[i],m),expected=p.probabilities[i],max=Math.max(...expected),label=m.labels[expected.indexOf(max)];if(actual.label!==label||Math.abs(actual.confidence-max)>1e-8)throw Error('Python / JS inference mismatch at '+i);}
console.log('PASS: '+p.features.length+' Python / JavaScript inference comparisons');
