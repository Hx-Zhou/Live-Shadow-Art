"""NumPy MLP baseline; no frame-random split, no fabricated training samples."""
import argparse, copy, hashlib, json, pathlib
import numpy as np

LABELS = ['open_palm', 'fist', 'point', 'pinch', 'victory', 'None']
FEATURE_VERSION = 'wrist-scale-mirror-72-v1'

def softmax(logits):
    e = np.exp(logits - logits.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)

def forward(x, weights, biases):
    a1 = np.maximum(0, x @ weights[0] + biases[0])
    a2 = np.maximum(0, a1 @ weights[1] + biases[1])
    return [x, a1, a2], softmax(a2 @ weights[2] + biases[2])

def gradients(x, y, weights, biases):
    activations, probs = forward(x, weights, biases)
    delta = probs.copy()
    delta[np.arange(len(y)), y] -= 1
    delta /= len(y)
    gw, gb = [None]*3, [None]*3
    for layer in (2, 1, 0):
        gw[layer] = activations[layer].T @ delta
        gb[layer] = delta.sum(axis=0)
        if layer:
            delta = (delta @ weights[layer].T) * (activations[layer] > 0)
    return gw, gb

def metrics(y, probs, threshold=.75):
    pred = probs.argmax(axis=1)
    pred[probs.max(axis=1) < threshold] = LABELS.index('None')
    cm = np.zeros((6, 6), dtype=int)
    np.add.at(cm, (y, pred), 1)
    tp = np.diag(cm)
    precision = tp / np.maximum(1, cm.sum(axis=0))
    recall = tp / np.maximum(1, cm.sum(axis=1))
    f1 = 2*precision*recall / np.maximum(1e-12, precision+recall)
    return dict(labels=LABELS, confusionMatrix=cm.tolist(), macroF1=float(f1.mean()),
                coreGestureMacroF1=float(f1[:5].mean()), accuracy=float((pred == y).mean()),
                perClass=[dict(label=l, precision=float(p), recall=float(r), f1=float(f), support=int(s))
                          for l,p,r,f,s in zip(LABELS,precision,recall,f1,cm.sum(axis=1))], confidenceThreshold=threshold)

def split_rows(rows, groups):
    sets = [set(g.split(',')) for g in groups]
    if any(not s or '' in s for s in sets) or any(sets[i]&sets[j] for i in range(3) for j in range(i)):
        raise ValueError('Train/validation/test participants must be nonempty and disjoint')
    all_people = {r['participant'] for r in rows}
    if set.union(*sets) != all_people:
        raise ValueError('Every participant must appear exactly once in the split; check IDs')
    result = [[r for r in rows if r['participant'] in s] for s in sets]
    for name, part in zip(['train','validation','test'], result):
        if {r['label'] for r in part} != set(LABELS):
            raise ValueError(name+' must contain all six labels')
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('data');ap.add_argument('--train',required=True);ap.add_argument('--validation',required=True);ap.add_argument('--test',required=True)
    ap.add_argument('--out',default='models/gesture');ap.add_argument('--epochs',type=int,default=250);ap.add_argument('--seed',type=int,default=42)
    args=ap.parse_args()
    raw=pathlib.Path(args.data).read_bytes();data=json.loads(raw)
    if data['featureVersion'] != FEATURE_VERSION: raise ValueError('Feature version mismatch')
    rows=data['rows']
    if not rows or sum(r['label']=='None' for r in rows)/len(rows)<.35: raise ValueError('None/transition samples must be at least 35% of all frames')
    parts=split_rows(rows,[args.train,args.validation,args.test])
    arrays=[]
    for part in parts:
        x=np.asarray([r['features'] for r in part],dtype=np.float64)
        if x.shape[1:] != (72,) or not np.isfinite(x).all(): raise ValueError('Invalid feature vector')
        arrays.append((x,np.array([LABELS.index(r['label']) for r in part])))
    mean=arrays[0][0].mean(axis=0);scale=arrays[0][0].std(axis=0);scale[scale<1e-8]=1
    arrays=[((x-mean)/scale,y) for x,y in arrays]
    rng=np.random.default_rng(args.seed);sizes=[72,128,64,6]
    weights=[rng.normal(0,np.sqrt(2/a),(a,b)) for a,b in zip(sizes,sizes[1:])];biases=[np.zeros(b) for b in sizes[1:]]
    params=weights+biases;m=[np.zeros_like(p) for p in params];v=copy.deepcopy(m)
    step=0;best_loss=float('inf');best=None;stale=0;history=[]
    for epoch in range(args.epochs):
        x,y=arrays[0];order=rng.permutation(len(y))
        for start in range(0,len(y),64):
            idx=order[start:start+64];gw,gb=gradients(x[idx],y[idx],weights,biases);step+=1
            for j,(p,g) in enumerate(zip(params,gw+gb)):
                m[j]=.9*m[j]+.1*g;v[j]=.999*v[j]+.001*g*g
                p-=.001*(m[j]/(1-.9**step))/(np.sqrt(v[j]/(1-.999**step))+1e-8)
        vx,vy=arrays[1];_,probs=forward(vx,weights,biases);loss=float(-np.log(probs[np.arange(len(vy)),vy]+1e-12).mean())
        history.append(dict(epoch=epoch+1,validationLoss=loss))
        if loss<best_loss-1e-5: best_loss=loss;best=copy.deepcopy((weights,biases));stale=0
        else: stale+=1
        if stale>=25: break
    if best is None: raise ValueError('No training epochs completed')
    weights,biases=best
    report=dict(status='measured-offline-only',datasetSha256=hashlib.sha256(raw).hexdigest(),seed=args.seed,
                split=dict(train=args.train,validation=args.validation,test=args.test),sampleCounts=[len(p) for p in parts],
                validation=metrics(arrays[1][1],forward(arrays[1][0],weights,biases)[1]),
                test=metrics(arrays[2][1],forward(arrays[2][0],weights,biases)[1]),history=history,
                endToEndP95Ms=None,falseTriggersPerMinute=None,stageFps=None,
                note='Frame metrics are not event false-trigger rates. Final hardware and stage acceptance remain pending.')
    model=dict(featureVersion=FEATURE_VERSION,modelVersion='mlp-'+report['datasetSha256'][:12],labels=LABELS,
               mean=mean.tolist(),scale=scale.tolist(),weights=[w.tolist() for w in weights],biases=[b.tolist() for b in biases])
    out=pathlib.Path(args.out);out.mkdir(parents=True,exist_ok=True)
    (out/'model.json').write_text(json.dumps(model),encoding='utf-8')
    (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    # Cross-language inference parity fixture, using actual held-out frames.
    x=parts[2][:10];fx=np.array([r['features'] for r in x]);p=forward((fx-mean)/scale,weights,biases)[1]
    (out/'parity.json').write_text(json.dumps(dict(features=fx.tolist(),probabilities=p.tolist())),encoding='utf-8')
    print(json.dumps(dict(model=str(out/'model.json'),test=report['test']),indent=2))

if __name__=='__main__':main()
