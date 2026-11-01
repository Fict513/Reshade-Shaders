import itertools
import unittest
import numpy as np
from reference import scalar,pq64,unpq64,pipeline,local_delta,Y,M709,MTO709,MP3,toe,high

METRICS={}
class HDRNumerical(unittest.TestCase):
    def test_pq_reference_points_and_float_roundtrip(self):
        nits=np.array([0,.0001,.001,.01,.1,1,10,100,203,400,1000,4000,10000])
        enc=scalar(1,nits);dec=scalar(0,enc)
        np.testing.assert_allclose(enc,pq64(nits),rtol=0,atol=1.5e-5)
        np.testing.assert_allclose(dec,nits,rtol=2e-4,atol=1e-7)
        # Dense range; actual scalar FX math compiled as C++ float, no NumPy port here.
        grid=np.geomspace(1e-6,10000,200001)
        rt=scalar(0,scalar(1,grid));rel=np.abs(rt-grid)/grid
        self.assertTrue(np.isfinite(rt).all())
        self.assertLess(rel.max(),3e-4)
        METRICS['pq_float_max_relative_roundtrip_error']=float(rel.max())
    def test_all_1024_pq_codes_requantize_identically(self):
        code=np.arange(1024)/1023
        rt=scalar(1,scalar(0,code))
        q=np.rint(rt*1023).astype(int)
        np.testing.assert_array_equal(q,np.arange(1024))
    def test_anchored_monotonic_curves(self):
        grid=np.r_[0.,np.geomspace(1e-6,1e7,60001)]
        minimum=1.
        for c,a,s,h in itertools.product([0,.12,.5],[40,100,250],[0,.8,1],[0,.85,1]):
            output=scalar(2,grid,c,a,s,h)
            self.assertTrue(np.all(np.diff(output)>=0),(c,a,s,h))
            keep=np.array([0,toe(s)*.5,a,high(a,h)*2],dtype=np.float32)
            np.testing.assert_array_equal(scalar(2,keep,c,a,s,h),keep)
        METRICS['monotonic_curve_parameter_combinations']=81
    def test_soft_budget_is_bounded_monotonic_and_identity_below_knee(self):
        grid=np.linspace(0,1,10001,dtype=np.float32)
        for budget in [0,1e-6,.01,.1,1,100]:
            r=scalar(3,grid,c=budget)
            self.assertTrue((r>=0).all());self.assertTrue((r<=budget+1e-7).all())
            self.assertTrue((np.diff(r)>=-1e-7).all())
            keep=grid<=budget*.5
            np.testing.assert_array_equal(r[keep],grid[keep])
    def test_identity_and_alpha(self):
        rng=np.random.default_rng(87)
        for mode in [0,1,2]:
            x=rng.random((10000,4)).astype(np.float32)
            if mode==2:x[:,:3]=x[:,:3]*20-2
            np.testing.assert_array_equal(pipeline(x,mode,master=0),x)
            np.testing.assert_array_equal(pipeline(x,mode,c=0,color=0),x)
            result=pipeline(x,mode)
            np.testing.assert_array_equal(result[:,3].view(np.uint32),x[:,3].view(np.uint32))
    def test_gray_is_neutral_and_finite(self):
        n=np.r_[0.,np.geomspace(1e-6,10000,16000)]
        for mode in [1,2]:
            values=pq64(n) if mode==1 else n/80
            x=np.column_stack([values,values,values,np.ones_like(values)])
            result=pipeline(x,mode,c=.5,color=.3,master=1)
            self.assertTrue(np.isfinite(result).all())
            np.testing.assert_allclose(result[:,0],result[:,1],atol=2e-7)
            np.testing.assert_allclose(result[:,1],result[:,2],atol=2e-7)
            self.assertTrue((np.diff(result[:,0])>=-1e-7).all())
    def test_signed_extended_scrgb(self):
        # Includes BT.2020 green represented with a negative BT.709 red channel.
        lin=np.array([[0,100,0],[0,0,100],[20,40,70],[20000,30000,50000.]])
        rgb=(lin@MTO709.T)/80
        x=np.column_stack([rgb,np.array([.25,.5,.75,1])])
        result=pipeline(x,2,c=.2,color=.3)
        self.assertTrue(np.isfinite(result).all())
        self.assertLess(result[0,0],0)
        self.assertGreater(result[-1,:3].max(),1)
        np.testing.assert_allclose(result[-1],x[-1],rtol=1e-8,atol=1e-8)
        negative=np.array([[-1,-2,-3,.4],[0,0,0,.1]])
        np.testing.assert_array_equal(pipeline(negative,2),negative)
    def test_matrices_and_gray_preservation(self):
        np.testing.assert_allclose(M709@MTO709,np.eye(3),atol=2e-9)
        np.testing.assert_allclose(MP3@np.ones(3),np.ones(3),atol=2e-9)
        # Re-derive conversions from primary chromaticities, not just inverses.
        white=np.array([.3127/.3290,1,(1-.3127-.3290)/.3290])
        def matrix(primaries):
            p=np.array(primaries)
            v=np.column_stack([p[:,0]/p[:,1],np.ones(3),(1-p.sum(axis=1))/p[:,1]]).T
            return v@np.diag(np.linalg.solve(v,white))
        m709=matrix([[.64,.33],[.30,.60],[.15,.06]])
        m2020=matrix([[.708,.292],[.17,.797],[.131,.046]])
        mp3=matrix([[.68,.32],[.265,.69],[.15,.06]])
        np.testing.assert_allclose(np.linalg.solve(m2020,m709),M709,atol=1e-9)
        np.testing.assert_allclose(np.linalg.solve(mp3,m2020),MP3,atol=1e-9)
    def test_random_saturated_pq_and_gamut_boundaries(self):
        rng=np.random.default_rng(77)
        rgb=np.r_[rng.random((100000,3)),
                  np.array(list(itertools.product([0,1e-5,.25,.5,.75,1],repeat=3)))]
        x=np.column_stack([rgb,np.ones(len(rgb))])
        result=pipeline(x,1,master=1,c=.5,color=.3,delta=.24)
        self.assertTrue(np.isfinite(result).all())
        self.assertGreaterEqual(result[:,:3].min(),0)
        self.assertLessEqual(result[:,:3].max(),1+1e-12)
        # Color alone preserves Y; black/white/saturated boundary sources unchanged.
        colors=unpq64(rgb);out=unpq64(pipeline(x,1,c=0,color=.3,master=1)[:,:3])
        np.testing.assert_allclose(out@Y,colors@Y,rtol=3e-10,atol=1e-7)
    def test_invalid_pq_signal_bypasses(self):
        x=np.array([[-.01,.4,.3,.2],[1.01,.4,.3,.7],[np.nan,.2,.3,.6]])
        np.testing.assert_array_equal(pipeline(x,1),x)
    def test_edges_borders_resolutions_quality_and_bounds(self):
        max_flat=0.;max_step=0.
        for shape in [(1,1),(1,17),(19,1),(17,31),(48,96)]:
            for quality,radius in itertools.product([0,1,2],[1,6,24]):
                flat=np.full(shape,30.)
                d=local_delta(flat,quality=quality,radius=radius)
                max_flat=max(max_flat,float(np.abs(d).max()))
                self.assertLess(np.abs(d).max(),1e-6)
                edge=flat.copy();edge[:,shape[1]//2:]=300
                d=local_delta(edge,quality=quality,radius=radius,strength=.5)
                self.assertTrue(np.isfinite(d).all())
                self.assertLessEqual(np.abs(d).max(),.25+1e-12)
                max_step=max(max_step,float(np.abs(d).max()))
        METRICS['local_flat_max_stops']=max_flat
        METRICS['local_30_to_300_nit_step_max_stops']=max_step
    def test_local_precision_quantization(self):
        yy,xx=np.indices((63,129))
        image=np.exp2(-8+xx/10+np.sin(yy)*.15)
        d32=local_delta(image,strength=.5)
        d16=local_delta(image,strength=.5,storage=np.float16)
        d64=local_delta(image,strength=.5,storage=np.float64)
        err32=np.max(np.abs(d32-d64));err16=np.max(np.abs(d16-d64))
        # Half an R32F ULP at logY=8 is 4.77e-7 stops; use that
        # representational bound, rather than demanding sub-ULP storage.
        self.assertLess(err32,5e-7)
        METRICS['local_R32F_max_stops_error']=float(err32)
        METRICS['local_R16F_max_stops_error']=float(err16)
    def test_local_textures_noise_and_bright_thin_edge(self):
        yy,xx=np.indices((65,129));rng=np.random.default_rng(42)
        noise=50*np.exp2(rng.normal(0,.2,xx.shape))
        line=np.full(xx.shape,20.);line[:,64]=1000
        ramp=np.exp2(-5+xx/12+np.sin(yy*.7)*.3)
        max_mean_shift=0.
        for image in [noise,line,ramp]:
            for q in range(3):
                d=local_delta(image,quality=q,strength=.5,radius=6)
                self.assertTrue(np.isfinite(d).all())
                self.assertLessEqual(np.max(np.abs(d)),.25+1e-12)
                changed=image*np.exp2(d)
                # Extrema live in the stored R32F logarithmic guide; allow
                # float32 log/exp round-trip error when comparing linear nits.
                self.assertGreaterEqual(changed.min(),image.min()*(1-1e-6))
                self.assertLessEqual(changed.max(),image.max()*(1+1e-6))
                max_mean_shift=max(max_mean_shift,abs(changed.mean()/image.mean()-1))
        METRICS['local_texture_max_abs_mean_luminance_shift_fraction_at_max_strength']=float(max_mean_shift)
    def test_protected_near_black_ramp_is_exact_global_identity(self):
        for protection in [0,.5,.8,1]:
            y=np.linspace(0,toe(protection)*.999,10001,dtype=np.float32)
            np.testing.assert_array_equal(scalar(2,y,c=.5,s=protection),y)
    def test_output_10bit_gradients(self):
        # Examine actual quantization in PQ code space, never linear nits / 1023.
        stats={}
        for name,lo,hi in [('near_black',.001,1),('shadow',.01,10),('highlight',80,1000)]:
            n=np.geomspace(lo,hi,65536)
            code=np.repeat(pq64(n)[:,None],3,axis=1)
            x=np.column_stack([code,np.ones(len(n))])
            qin=np.rint(code[:,0]*1023).astype(int)
            out=pipeline(x,1,c=.22,color=0,master=.85)
            q=np.rint(out[:,0]*1023).astype(int)
            self.assertTrue((np.diff(q)>=0).all())
            stats[name]={'input_unique_codes':len(np.unique(qin)),
                         'output_unique_codes':len(np.unique(q)),
                         'max_adjacent_code_jump':int(np.diff(q).max())}
        METRICS['10bit_gradients']=stats

if __name__=='__main__':unittest.main()
