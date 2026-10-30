"""Run python Tests/test_reference.py. Requires NumPy and SciPy."""
import unittest
from itertools import product
import numpy as np
from scipy.ndimage import gaussian_filter
from reference import process,decode,encode,reconstruct,LUMA,grid,rectangle_mask

def gray(x):return np.repeat(np.asarray(x)[...,None],3,axis=-1)

class AdaptiveClarityTests(unittest.TestCase):
    def test_constant_fields_odd_and_tiny_sizes(self):
        for quality,shape,value in product(range(3),[(1,1),(3,5),(32,64),(33,65)],[0,.01,.3,.8,1]):
            image=np.full((*shape,3),value)
            out,diag=process(image,quality)
            np.testing.assert_array_equal(out,image)
            self.assertLess(abs(diag['correction']).max(),1e-12)

    def test_strength_zero_and_both_gains_zero_are_identity(self):
        image=np.random.default_rng(5).random((23,31,4))
        for quality in range(3):
            out,_=process(image,quality,Strength=0)
            np.testing.assert_array_equal(out,image)
            out,_=process(image,quality,TextureStrength=0,EdgeStrength=0)
            np.testing.assert_array_equal(out,image)

    def test_hdr_is_exact_passthrough(self):
        image=np.random.default_rng(6).uniform(-1,4,(9,17,4))
        for space in [2,3,4]:
            out,_=process(image,color_space=space)
            np.testing.assert_array_equal(out,image)

    def test_alpha_and_grayscale_preservation(self):
        rng=np.random.default_rng(8);a=rng.random((23,31,1));p=rng.random((23,31))
        image=np.concatenate([gray(p),a],axis=-1)
        for quality in range(3):
            out,_=process(image,quality)
            np.testing.assert_array_equal(out[...,3],image[...,3])
            np.testing.assert_allclose(out[...,0],out[...,1],atol=2e-13)
            np.testing.assert_allclose(out[...,1],out[...,2],atol=2e-13)

    def test_color_reconstruction_gamut_and_luminance(self):
        rng=np.random.default_rng(9)
        rgb=np.vstack([rng.random((100000,3)),np.eye(3),np.zeros(3),np.ones(3),np.eye(3)*1e-12])
        y=rgb@LUMA
        for target in [y,rng.random(len(y)),np.zeros(len(y)),np.ones(len(y))]:
            out=reconstruct(rgb,y,target)
            self.assertTrue(np.isfinite(out).all())
            self.assertGreaterEqual(out.min(),0);self.assertLessEqual(out.max(),1)
            np.testing.assert_allclose(out@LUMA,target,atol=1e-12)
        np.testing.assert_allclose(reconstruct(rgb,y,y),rgb,atol=2e-15)

    def test_strict_local_extrema_limit(self):
        image=np.random.default_rng(10).random((33,65,3))
        for quality in range(3):
            out,diag=process(image,quality,Overshoot=0,Strength=1,TextureStrength=1,EdgeStrength=.75)
            actual=diag['guide']+diag['correction']
            self.assertGreaterEqual(np.min(actual-diag['lo']),-1e-12)
            self.assertLessEqual(np.max(actual-diag['hi']),1e-12)
            self.assertTrue(np.isfinite(out).all())
            self.assertGreaterEqual(out.min(),0);self.assertLessEqual(out.max(),1)

    def test_default_correction_limits_and_saturated_colors(self):
        image=np.random.default_rng(11).random((33,65,3))
        image[:3,:3]=np.eye(3)[:,None,:]
        for quality in range(3):
            out,diag=process(image,quality)
            actual=diag['guide']+diag['correction']
            self.assertGreaterEqual(np.min(actual-diag['lo']+diag['margin']),-1e-12)
            self.assertLessEqual(np.max(actual-diag['hi']-diag['margin']),1e-12)
            self.assertLessEqual(abs(diag['correction']).max(),.025*.75+1e-12)
            self.assertTrue(np.isfinite(out).all())
            self.assertGreaterEqual(out.min(),0);self.assertLessEqual(out.max(),1)

    def test_hard_edges_and_thin_lines_have_limited_ringing(self):
        for quality,x,thin in product(range(3),[31,32,33],[False,True]):
            image=np.full((17,65),.2);image[:,x:x+1 if thin else 65]=.8
            out,diag=process(gray(image),quality)
            self.assertLess(abs(diag['correction']).max(),.007)
            self.assertGreaterEqual(out.min(),.2-.007)
            self.assertLessEqual(out.max(),.8+.007)

    def test_subthreshold_noise_not_amplified(self):
        rng=np.random.default_rng(12)
        image=gray(.5+rng.uniform(-.001,.001,(65,129)))
        for quality in range(3):
            out,_=process(image,quality)
            np.testing.assert_array_equal(out,image)

    def test_subtle_blurred_texture_is_enhanced(self):
        yy,xx=np.indices((65,129))
        p=.5+.08*np.sin(2*np.pi*xx/8)*np.sin(2*np.pi*yy/8)
        image=gray(gaussian_filter(p,.7))
        for quality in range(3):
            out,_=process(image,quality)
            before=image[8:-8,8:-8,0].std();after=out[8:-8,8:-8,0].std()
            self.assertGreater(after,before*1.01)
            self.assertLess(after,before*1.5)

    def test_pattern_protection_reduces_checker_amplification(self):
        yy,xx=np.indices((33,65));p=.5+.08*((xx+yy)%2*2-1)
        for quality in range(3):
            _,lo=process(gray(p),quality,PatternProtection=0)
            _,hi=process(gray(p),quality,PatternProtection=1)
            self.assertLess(abs(hi['correction']).sum(),abs(lo['correction']).sum())

    def test_rotation_equivariance(self):
        rng=np.random.default_rng(13);image=rng.random((33,33,3))
        for quality in range(3):
            out,_=process(image,quality)
            rotated,_=process(np.rot90(image),quality)
            np.testing.assert_allclose(np.rot90(out),rotated,atol=2e-7)

    def test_manual_masks_and_hard_feather(self):
        rng=np.random.default_rng(14);image=rng.random((33,65,4))
        rect=(.2,.2,.8,.8)
        for feather in [0,12]:
            out,diag=process(image,Mask1Enabled=True,Mask1Rect=rect,MaskFeather=feather)
            inside=diag['protection']==1
            self.assertTrue(inside.any())
            np.testing.assert_array_equal(out[inside],image[inside])
        out,_=process(image,Mask1Enabled=True,Mask1Rect=(0,0,1,1))
        np.testing.assert_array_equal(out,image)
        a,_=process(image,Mask1Enabled=True,Mask1Rect=rect,hud_masks=False)
        b,_=process(image,Mask1Enabled=False)
        np.testing.assert_array_equal(a,b)
        uv=grid(33,65)
        a=rectangle_mask(uv,rect,12,65,33)
        b=rectangle_mask(uv,(.8,.8,.2,.2),12,65,33)
        np.testing.assert_array_equal(a,b)

    def test_smooth_ramps_preserve_order(self):
        image=gray(np.tile(np.linspace(0,1,257),(17,1)))
        for quality in range(3):
            out,_=process(image,quality)
            self.assertGreater(np.diff(out[...,0],axis=1).min(),0)
            self.assertLess(abs(out[3:-3,8:-8]-image[3:-3,8:-8]).max(),1e-6)

    def test_radius_range(self):
        image=np.random.default_rng(15).random((19,31,3))
        for quality,radius in product(range(3),[.75,1,1.5]):
            out,_=process(image,quality,Radius=radius)
            self.assertTrue(np.isfinite(out).all())
            self.assertGreaterEqual(out.min(),0);self.assertLessEqual(out.max(),1)

if __name__=='__main__':unittest.main(verbosity=2)
