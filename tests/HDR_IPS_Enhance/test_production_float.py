"""Production function bodies with CPU float adapters, explicitly not GPU tests."""
import itertools,pathlib,sys,unittest
import numpy as np
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'tools'))
from production_float import execute
from production_local import execute as local_execute
from reference import pq64,unpq64,pipeline,local_delta,MTO709,Y
METRICS={}
def rgba(rgb):
    rgb=np.asarray(rgb,dtype=np.float32)
    return np.column_stack([rgb,np.linspace(-.5,1.5,len(rgb),dtype=np.float32)])
def samebits(a,b):return np.array_equal(a.view(np.uint32),b.view(np.uint32))
class ProductionFloat(unittest.TestCase):
    def test_exact_paths_and_diagnostic_alpha(self):
        rng=np.random.default_rng(106)
        for mode in [0,1,2,3]:
            x=rgba(rng.random((10000,3)) if mode!=2 else rng.uniform(-3,20,(10000,3)))
            for diag in range(5):
                self.assertTrue(samebits(execute(x,mode=mode,diag=diag,master=0),x))
                out=execute(x,mode=mode,diag=diag)
                self.assertTrue(samebits(out[:,3],x[:,3]))
                if mode in [0,3]:self.assertTrue(samebits(out,x))
            self.assertTrue(samebits(execute(x,mode=mode,contrast=0,color=0),x))
    def test_extreme_finite_and_signed_scrgb(self):
        x=rgba([[1e38]*3,[-1,-2,-3],[0,0,0],[-.4,1,.3],[500,600,700],[-.2,.4,1.2]])
        out=execute(x,mode=2)
        self.assertTrue(np.isfinite(out).all())
        self.assertTrue(samebits(out[:3],x[:3]))
        self.assertLess(out[3,0],0);self.assertGreater(out[4,:3].max(),1)
        # Full finite FP16 range is representable in normal scRGB intermediates.
        rng=np.random.default_rng(105);x=rgba(rng.uniform(-65504,65504,(20000,3)))
        self.assertTrue(np.isfinite(execute(x,mode=2,master=1,contrast=.5,color=.3)).all())
    def test_gray_and_quantized_production_gradients(self):
        stats={}
        for name,lo,hi in [('near_black',.001,1),('shadow',.01,10),('highlight',80,1000)]:
            n=np.geomspace(lo,hi,65536);x=rgba(np.repeat(pq64(n)[:,None],3,axis=1))
            out=execute(x,contrast=.22,color=0,master=.85)
            q=np.rint(out[:,0]*np.float32(1023)).astype(int)
            self.assertTrue((np.diff(q)>=0).all())
            stats[name]=dict(reversals=int(np.sum(np.diff(q)<0)),output_unique_codes=len(np.unique(q)),max_adjacent_code_jump=int(np.diff(q).max()))
        METRICS['production_float_10bit_gradients']=stats
        n=np.r_[0.,np.geomspace(1e-6,10000,16000)]
        errors={}
        for mode in [1,2]:
            x=rgba(np.repeat((pq64(n) if mode==1 else n/80)[:,None],3,axis=1))
            out=execute(x,mode=mode,master=1,contrast=.5,color=.3)
            self.assertTrue(np.isfinite(out).all())
            err=np.max(np.ptp(out[:,:3],axis=1));errors[str(mode)]=float(err)
            np.testing.assert_allclose(out[:,0],out[:,1],rtol=1e-6,atol=2e-7)
            np.testing.assert_allclose(out[:,1],out[:,2],rtol=1e-6,atol=2e-7)
        METRICS['production_gray_max_channel_spread_signal_units']=errors
    def test_saturation_boundaries_and_reference_difference(self):
        rng=np.random.default_rng(107)
        x=rgba(np.r_[rng.random((100000,3)),np.array(list(itertools.product([0,1e-5,.25,.5,.75,1],repeat=3)))])
        out=execute(x,master=1,contrast=.5,color=.3)
        self.assertTrue(np.isfinite(out).all());self.assertGreaterEqual(out[:,:3].min(),0);self.assertLessEqual(out[:,:3].max(),1)
        ref=pipeline(x,master=1,c=.5,color=.3)
        METRICS['production_vs_numpy_max_PQ_code_error']=float(np.max(np.abs(out[:,:3]-ref[:,:3])))
        # Existing BT.2020 primaries outside the P3 proxy remain exact with color-only.
        prim=rgba(pq64(np.eye(3)*100))
        self.assertTrue(samebits(execute(prim,contrast=0,color=.3),prim))
    def test_invalid_signal_bypass(self):
        x=rgba([[-.01,.4,.3],[1.01,.4,.3],[np.nan,.4,.3],[np.inf,.4,.3]])
        self.assertTrue(samebits(execute(x),x))
    def test_diagnostic_encoding(self):
        # Source 100-nit neutral is in yellow bin (.9,.75,0), in linear BT.709.
        for mode in [1,2]:
            value=pq64(np.array([100.]))[0] if mode==1 else 1.25
            x=rgba([[value]*3]);out=execute(x,mode=mode,diag=2)
            lin709=(unpq64(out[0,:3])@MTO709.T) if mode==1 else out[0,:3]*80
            np.testing.assert_allclose(lin709,[90,75,0],rtol=5e-5,atol=.005)
    def test_extracted_local_edges_borders_and_bias(self):
        rng=np.random.default_rng(109);maximum_difference=0.;maximum_shift=0.;maximum_flat=0.
        for shape in [(1,1),(1,17),(19,1),(17,31),(48,96)]:
            yy,xx=np.indices(shape);flat=np.full(shape,30.);step=flat.copy();step[:,shape[1]//2:]=300
            thin=np.full(shape,20.);thin[:,shape[1]//2]=1000
            images=[flat,step,thin,50*np.exp2(rng.normal(0,.2,shape)),np.exp2(-5+xx/12+np.sin(yy*.7)*.3)]
            for q,radius in itertools.product(range(3),[1,6,24]):
                for idx,y in enumerate(images):
                    d=local_execute(y,q=q,radius=radius)
                    self.assertTrue(np.isfinite(d).all());self.assertLessEqual(np.abs(d).max(),.250002)
                    ref=local_delta(y,quality=q,radius=radius,strength=.5)
                    maximum_difference=max(maximum_difference,float(np.abs(d-ref).max()))
                    changed=y*np.exp2(d);maximum_shift=max(maximum_shift,abs(changed.mean()/y.mean()-1))
                    self.assertGreaterEqual(changed.min(),y.min()*(1-3e-6));self.assertLessEqual(changed.max(),y.max()*(1+3e-6))
                    if idx==0:maximum_flat=max(maximum_flat,float(np.abs(d).max()))
        self.assertLess(maximum_difference,5e-6)
        METRICS['extracted_local_max_difference_from_numpy_stops']=maximum_difference
        METRICS['extracted_local_max_abs_mean_shift_fraction']=maximum_shift
        METRICS['extracted_local_flat_max_stops']=maximum_flat
