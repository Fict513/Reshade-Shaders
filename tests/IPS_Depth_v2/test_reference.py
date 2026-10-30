"""Run from any directory: python Tests/test_reference.py. Requires numpy scipy."""
import unittest
from itertools import product
import numpy as np
from reference import tone, reconstruct, process, LUMA, decode, encode

class IPSDepthTests(unittest.TestCase):
    def test_tone_monotonic_endpoints_pivot(self):
        p=np.linspace(0,1,100001)
        for c,s,h in product([0,.34,.75],[0,.9,1],[0,.15,1]):
            with self.subTest(contrast=c,shadow=s,highlight=h):
                t=tone(p,c,s,h)
                self.assertTrue(np.isfinite(t).all())
                self.assertGreater(np.diff(t).min(),0)
                self.assertGreaterEqual(t.min(),0);self.assertLessEqual(t.max(),1)
                np.testing.assert_allclose(t[[0,50000,-1]],[0,.5,1],atol=1e-14)

    def test_gamut_projection_and_identity(self):
        rng=np.random.default_rng(7)
        rgb=np.vstack([rng.random((100000,3)),np.eye(3),np.zeros(3),np.ones(3),np.eye(3)*1e-12])
        y=rgb@LUMA
        for target in [y,rng.random(len(y)),np.zeros(len(y)),np.ones(len(y))]:
            out=reconstruct(rgb,y,target)
            self.assertTrue(np.isfinite(out).all())
            self.assertGreaterEqual(out.min(),0);self.assertLessEqual(out.max(),1)
            np.testing.assert_allclose(out@LUMA,target,atol=1e-12)
        np.testing.assert_allclose(reconstruct(rgb,y,y),rgb,atol=2e-15)

    def test_constant_fields_and_odd_sizes(self):
        for quality,shape,value in product(range(3),[(1,1),(3,5),(32,64),(33,65)],[0,.03,.30,.8,1]):
            rgb=np.full((*shape,3),value)
            out,detail,_=process(rgb,quality,crop_height=1080)
            self.assertTrue(np.isfinite(out).all())
            self.assertLess(abs(detail).max(),1e-10)
            expected=tone(value)
            np.testing.assert_allclose(out,expected,atol=5e-10)

    def test_disabled_controls_retain_identity(self):
        rng=np.random.default_rng(2);rgb=rng.random((19,31,3))
        for local,broad in [(False,False),(True,False),(True,True)]:
            out,_,_=process(rgb,1,local,broad,Contrast=0,FineContrast=0,BroadContrast=0,Sharpen=0)
            np.testing.assert_allclose(out,rgb,atol=2e-13)

    def test_edges_and_thin_features(self):
        for quality,x,thin in product(range(3),[63,64,65],[False,True]):
            rgb=np.full((17,129,3),.15)
            rgb[:,x:x+1 if thin else 129,:]=.85
            out,detail,_=process(rgb,quality,crop_height=1080)
            self.assertTrue(np.isfinite(out).all())
            self.assertLess(abs(detail).max(),.001)
            self.assertGreaterEqual(out.min(),0);self.assertLessEqual(out.max(),1)

    def test_smooth_gradients_preserve_order(self):
        for quality,direction in product(range(3),[1,-1]):
            img=np.tile(np.linspace(0,1,257)[::direction],(17,1))
            out,_,_=process(np.repeat(img[...,None],3,axis=-1),quality,crop_height=1080)
            self.assertGreater(np.diff(out[:,::direction,0],axis=1).min(),0)
            self.assertTrue(np.isfinite(out).all())

    def test_random_images_remain_bounded(self):
        rng=np.random.default_rng(19);rgb=rng.random((33,65,3))
        for quality in range(3):
            out,detail,_=process(rgb,quality,crop_height=1080,Contrast=.75,FineContrast=.50,BroadContrast=.40,Sharpen=.30)
            self.assertTrue(np.isfinite(out).all())
            self.assertGreaterEqual(out.min(),-1e-14);self.assertLessEqual(out.max(),1+1e-14)

if __name__=='__main__':unittest.main(verbosity=2)
