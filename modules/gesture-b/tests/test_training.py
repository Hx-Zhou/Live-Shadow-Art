import importlib.util, pathlib, unittest
import numpy as np
spec=importlib.util.spec_from_file_location('train',pathlib.Path(__file__).resolve().parents[1]/'tools/train.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)

class TrainingTests(unittest.TestCase):
    def test_split_rejects_participant_leakage(self):
        with self.assertRaises(ValueError):t.split_rows([],['P1','P1','P2'])
    def test_missing_class_rejected(self):
        rows=[dict(participant=p,label='None') for p in ['P1','P2','P3']]
        with self.assertRaises(ValueError):t.split_rows(rows,['P1','P2','P3'])
    def test_confusion_matrix_and_none_rejection(self):
        y=np.arange(6);p=np.eye(6);r=t.metrics(y,p)
        self.assertEqual(r['macroF1'],1)
        p[0]=np.full(6,1/6);r=t.metrics(y,p)
        self.assertEqual(r['confusionMatrix'][0][5],1)
    def test_gradient_matches_finite_difference(self):
        rng=np.random.default_rng(11)
        w=[rng.normal(size=(3,4))*.2,rng.normal(size=(4,4))*.2,rng.normal(size=(4,6))*.2]
        b=[np.ones(4)*.5,np.ones(4)*.5,np.zeros(6)]
        x=rng.normal(size=(5,3));y=np.array([0,1,2,3,4]);gw,_=t.gradients(x,y,w,b)
        eps=1e-6
        for layer,i,j in [(0,0,0),(1,2,1),(2,1,3)]:
            old=w[layer][i,j];w[layer][i,j]=old+eps
            plus=-np.log(t.forward(x,w,b)[1][np.arange(5),y]).mean()
            w[layer][i,j]=old-eps
            minus=-np.log(t.forward(x,w,b)[1][np.arange(5),y]).mean()
            w[layer][i,j]=old
            self.assertAlmostEqual(gw[layer][i,j],(plus-minus)/(2*eps),places=6)

if __name__=='__main__':unittest.main()
