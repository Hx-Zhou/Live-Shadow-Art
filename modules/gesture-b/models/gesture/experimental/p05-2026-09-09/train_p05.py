"""Retrain with P01/P02/P05, validate on P03, leave P04 unscored."""
import copy, hashlib, importlib.util, json, pathlib
import numpy as np
ROOT=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('baseline',ROOT/'trainer_snapshot.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
raw=(ROOT/'prepared.json').read_bytes();data=json.loads(raw)
parts=[[r for r in data['rows'] if r['participant'] in group] for group in [{'P01','P02','P05'},{'P03'}]]
assert {r['participant'] for r in parts[0]}=={'P01','P02','P05'}
assert all({r['label'] for r in part}==set(t.LABELS) for part in parts)
assert sum(r['label']=='None' for r in parts[0])/len(parts[0])>=.35
arrays=[]
for part in parts:
    x=np.asarray([r['features'] for r in part],dtype=np.float64)
    assert x.shape[1:]==(72,) and np.isfinite(x).all()
    arrays.append((x,np.array([t.LABELS.index(r['label']) for r in part])))
mean=arrays[0][0].mean(axis=0);scale=arrays[0][0].std(axis=0);scale[scale<1e-8]=1
(x,y),(vx,vy)=[((a-mean)/scale,b) for a,b in arrays]
rng=np.random.default_rng(42);sizes=[72,128,64,6]
w=[rng.normal(0,np.sqrt(2/a),(a,b)) for a,b in zip(sizes,sizes[1:])];b=[np.zeros(n) for n in sizes[1:]]
params=w+b;mom=[np.zeros_like(p) for p in params];var=copy.deepcopy(mom)
step=0;best_loss=float('inf');best=None;stale=0;history=[];best_epoch=0
for epoch in range(250):
    order=rng.permutation(len(y))
    for start in range(0,len(y),64):
        idx=order[start:start+64];gw,gb=t.gradients(x[idx],y[idx],w,b);step+=1
        for j,(p,g) in enumerate(zip(params,gw+gb)):
            mom[j]=.9*mom[j]+.1*g;var[j]=.999*var[j]+.001*g*g
            p-=.001*(mom[j]/(1-.9**step))/(np.sqrt(var[j]/(1-.999**step))+1e-8)
    probs=t.forward(vx,w,b)[1];loss=float(-np.log(probs[np.arange(len(vy)),vy]+1e-12).mean())
    history.append({'epoch':epoch+1,'validationLoss':loss})
    if loss<best_loss-1e-5:best_loss=loss;best=copy.deepcopy((w,b));best_epoch=epoch+1;stale=0
    else:stale+=1
    if stale>=25:break
w,b=best;probs=t.forward(vx,w,b)[1]
def score(labels,p,threshold):
    r=t.metrics(labels,p,threshold);cm=np.array(r['confusionMatrix'])
    r.update(noneFalsePositiveCount=int(cm[5,:5].sum()),noneSupport=int(cm[5].sum()),noneFalsePositiveRate=float(cm[5,:5].sum()/cm[5].sum()))
    return r
validation={str(th):score(vy,probs,th) for th in [.7,.75]}
model={'featureVersion':t.FEATURE_VERSION,'modelVersion':'mlp-p05-'+hashlib.sha256(raw).hexdigest()[:12],'labels':t.LABELS,'mean':mean.tolist(),'scale':scale.tolist(),'weights':[a.tolist() for a in w],'biases':[a.tolist() for a in b]}
report={'status':'exploratory-validation-only','split':{'train':['P01','P02','P05'],'validation':['P03'],'testNotEvaluated':['P04']},'sampleCounts':{'train':len(y),'validation':len(vy)},'datasetSha256':hashlib.sha256(raw).hexdigest(),'seed':42,'l2':0,'learningRate':.001,'batchSize':64,'maxEpochs':250,'patience':25,'bestEpoch':best_epoch,'epochsRun':len(history),'history':history,'validation':validation,'train':{str(th):score(y,t.forward(x,w,b)[1],th) for th in [.7,.75]},'endToEndP95Ms':None,'falseTriggersPerMinute':None,'note':'Retrained from the same random seed, not warm-started. P03 was reused for model selection; no final independent-test claim. Original labels and out-of-frame samples retained.'}
(ROOT/'model.json').write_text(json.dumps(model),encoding='utf8')
(ROOT/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
indices=[next(i for i,r in enumerate(parts[1]) if r['label']==label) for label in t.LABELS]
features=np.array([parts[1][i]['features'] for i in indices])
(ROOT/'parity.json').write_text(json.dumps({'features':features.tolist(),'probabilities':t.forward((features-mean)/scale,w,b)[1].tolist()}))
print(json.dumps({'bestEpoch':best_epoch,'epochsRun':len(history),'sampleCounts':report['sampleCounts'],'validation':validation},indent=2))
