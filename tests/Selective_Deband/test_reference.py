"""Run python Tests/test_reference.py. Requires NumPy and SciPy."""
import unittest
from itertools import product
import numpy as np
from reference import process,LUMA,STEP8,grid,rect_mask

def gray(x):return np.repeat(np.asarray(x)[...,None],3,axis=-1)
def gradient(width=513,height=33):
    truth=gray(np.tile(np.linspace(.2,.8,width),(height,1)))
    banded=np.round(truth*255)/255
    return truth,banded

class SelectiveDebandTests(unittest.TestCase):
    def test_constant_fields_including_dither(self):
        for q,shape,color in product(range(3),[(1,1),(3,5),(32,64),(33,65)],[(0,0,0),(.3,.3,.3),(.4,.2,.1),(1,1,1)]):
            image=np.full((*shape,3),color)
            out,_=process(image,q)
            np.testing.assert_array_equal(out,image)

    def test_strength_zero_and_hdr_bypass(self):
        image=np.random.default_rng(1).uniform(-1,4,(9,17,4))
        for q in range(3):
            out,_=process(image,q,Strength=0);np.testing.assert_array_equal(out,image)
        for space in [2,3,4]:
            out,_=process(image,color_space=space);np.testing.assert_array_equal(out,image)

    def test_quantized_gradient_error_reduced(self):
        truth,banded=gradient();area=np.s_[3:-3,32:-32,:]
        before=np.mean((banded[area]-truth[area])**2)
        for q in range(3):
            out,_=process(banded,q,Dither=0)
            after=np.mean((out[area]-truth[area])**2)
            self.assertLess(after,before*.95)
            print(f'quality={q}: float gradient MSE ratio={after/before:.4f}')

    def test_dither_can_change_final_8bit_quantization(self):
        truth,banded=gradient(height=65)
        for q in range(3):
            out,_=process(banded,q)
            quantized=np.round(out*255)/255
            changed=np.count_nonzero(quantized!=banded)
            self.assertGreater(changed,0)
            print(f'quality={q}: changed 8-bit components={changed}')
            area=np.s_[8:-8,32:-32,:]
            before=np.mean((banded[area].mean(0)-truth[area].mean(0))**2)
            after=np.mean((quantized[area].mean(0)-truth[area].mean(0))**2)
            self.assertLess(after,before*.95)
            print(f'quality={q}: 8-bit spatial-mean gradient MSE ratio={after/before:.4f}')

    def test_smooth_gradient_is_not_shifted(self):
        truth,_=gradient()
        for q in range(3):
            out,_=process(truth,q)
            np.testing.assert_array_equal(out[3:-3,32:-32],truth[3:-3,32:-32])

    def test_large_edges_and_thin_lines_are_preserved(self):
        for q,x,thin in product(range(3),[31,32,33],[False,True]):
            p=np.full((17,65),.2);p[:,x:x+1 if thin else 65]=.8
            image=gray(p);out,_=process(image,q)
            np.testing.assert_array_equal(out,image)

    def test_one_step_isolated_fine_feature_is_protected(self):
        p=np.full((33,65),128/255);p[16,32]+=STEP8
        for q in range(3):
            out,diag=process(gray(p),q)
            np.testing.assert_allclose(out[16,32],gray(p)[16,32],atol=1e-14)

    def test_high_contrast_texture_is_preserved(self):
        yy,xx=np.indices((33,65));p=.5+.04*((xx+yy)%2*2-1)
        for q in range(3):
            out,_=process(gray(p),q)
            np.testing.assert_array_equal(out,gray(p))

    def test_isoluminant_color_edge_is_protected(self):
        left=np.array([.50,.35,.30]);right=left+np.array([.1,-.1*LUMA[0]/LUMA[1],0])
        self.assertAlmostEqual(left@LUMA,right@LUMA)
        image=np.tile(left,(17,65,1));image[:,32:]=right
        for q in range(3):
            out,_=process(image,q)
            # Immediate high-contrast boundary is exactly rejected. Fractional
            # far samples can make tiny changes on the adjacent flat region;
            # require these to remain below 0.05 of one 8-bit code step.
            np.testing.assert_array_equal(out[:,31:33],image[:,31:33])
            self.assertLess(abs(out-image).max(),.05*STEP8)

    def test_correction_cap_and_color_bounds(self):
        truth,banded=gradient();image=banded.copy();image[...,1]+=1e-4
        for q in range(3):
            out,diag=process(image,q,Dither=0,MaxCorrection=.25)
            self.assertTrue(np.isfinite(out).all())
            self.assertGreaterEqual(out.min(),0);self.assertLessEqual(out.max(),1)
            self.assertLessEqual(abs(diag['delta']).max(),.25*STEP8*.85+1e-14)

    def test_alpha_grayscale_and_determinism(self):
        _,p=gradient(129,17);a=np.random.default_rng(2).random((17,129,1))
        image=np.concatenate([p,a],axis=-1)
        for q in range(3):
            out,_=process(image,q);again,_=process(image,q)
            np.testing.assert_array_equal(out,again)
            np.testing.assert_array_equal(out[...,3],image[...,3])
            np.testing.assert_allclose(out[...,0],out[...,1],atol=1e-13)
            np.testing.assert_allclose(out[...,1],out[...,2],atol=1e-13)

    def test_dither_switches_bit_depth_and_bounds(self):
        _,image=gradient(257,33)
        base,diag=process(image,Dither=0)
        off,_=process(image,enable_dither=False);np.testing.assert_array_equal(off,base)
        sixteen,_=process(image,bit_depth=16);np.testing.assert_array_equal(sixteen,base)
        for depth,step in [(8,1/255),(10,1/1023)]:
            out,diag=process(image,bit_depth=depth)
            self.assertTrue(np.isfinite(out).all())
            self.assertLessEqual(abs(diag['dither']).max(),.80*.85*step+1e-14)
            self.assertGreaterEqual(out.min(),0);self.assertLessEqual(out.max(),1)

    def test_hud_rectangles(self):
        _,image=gradient(257,33)
        for feather in [0,12]:
            out,diag=process(image,Mask1Enabled=True,Mask1Rect=(.2,.2,.8,.8),MaskFeather=feather)
            inside=diag['protection']==1
            self.assertTrue(inside.any());np.testing.assert_array_equal(out[inside],image[inside])
        out,_=process(image,Mask1Enabled=True,Mask1Rect=(0,0,1,1))
        np.testing.assert_array_equal(out,image)
        off,_=process(image,hud_masks=False,Mask1Enabled=True,Mask1Rect=(0,0,1,1))
        base,_=process(image);np.testing.assert_array_equal(off,base)
        uv=grid(33,257)
        np.testing.assert_array_equal(rect_mask(uv,(.2,.2,.8,.8),12,257,33),rect_mask(uv,(.8,.8,.2,.2),12,257,33))

    def test_rotation_equivariance_without_dither(self):
        _,image=gradient(65,65)
        for q in range(3):
            out,_=process(image,q,Dither=0)
            rotated,_=process(np.rot90(image),q,Dither=0)
            np.testing.assert_allclose(np.rot90(out),rotated,atol=2e-12)

    def test_radius_and_threshold_extremes_finite(self):
        image=np.random.default_rng(3).random((9,17,3))
        for q,radius in product(range(3),[2,32]):
            out,_=process(image,q,Radius=radius,LumaThreshold=12,ChromaThreshold=12,
                          TextureThreshold=8,EdgeThreshold=24,MaxCorrection=4,Dither=1)
            self.assertTrue(np.isfinite(out).all())
            self.assertGreaterEqual(out.min(),0);self.assertLessEqual(out.max(),1)

if __name__=='__main__':unittest.main(verbosity=2)
