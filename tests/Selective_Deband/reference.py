"""CPU reference for Selective_Deband.fx. Not GPU execution.

Bilinear CLAMP sampling uses SciPy. Dither hashes follow the same formula but
GPU floating-point rounding can produce a different static noise pattern.
"""
import numpy as np
from scipy.ndimage import map_coordinates

LUMA=np.array([.2126,.7152,.0722])
STEP8=1/255
DEFAULTS=dict(Strength=.85,Radius=8.,LumaThreshold=3.,ChromaThreshold=2.,
              TextureThreshold=1.,EdgeThreshold=4.,MaxCorrection=1.,Dither=.80,
              Mask1Enabled=False,Mask1Rect=(0,.82,.35,1),Mask2Enabled=False,
              Mask2Rect=(.65,.82,1,1),MaskFeather=12.)

def smooth(a,b,x):
    t=np.clip((x-a)/(b-a),0,1);return t*t*(3-2*t)
def accept(difference,threshold):return 1-smooth(.5*threshold,threshold,difference)
def grid(h,w):
    yy,xx=np.indices((h,w));return np.array([(xx+.5)/w,(yy+.5)/h])
def sample(src,uv):
    h,w=src.shape[:2];coord=np.array([uv[1]*h-.5,uv[0]*w-.5])
    return np.stack([map_coordinates(src[...,k],coord,order=1,mode='nearest')
                     for k in range(src.shape[2])],axis=-1)
def rect_mask(uv,rect,feather,width,height):
    r=np.array(rect);lo=np.minimum(r[:2],r[2:]);hi=np.maximum(r[:2],r[2:])
    outside=np.maximum(np.maximum(lo[:,None,None]-uv,uv-hi[:,None,None]),0)
    distance=np.sqrt(np.sum((outside*np.array([width,height])[:,None,None])**2,axis=0))
    if feather<=0:return (distance<=0).astype(float)
    return 1-smooth(0,feather,distance)
def frac(x):return x-np.floor(x)
def hash2(x,y):return frac(52.9829189*frac(x*.06711056+y*.00583715))

def process(image,quality=1,color_space=1,bit_depth=8,enable_dither=True,hud_masks=True,**overrides):
    image=np.asarray(image,dtype=float)
    c=DEFAULTS|overrides;h,w=image.shape[:2];uv=grid(h,w);zero=np.zeros((h,w))
    if color_space>1 or c['Strength']<=0:
        return image.copy(),dict(delta=np.zeros((h,w,3)),eligible=zero,protection=zero,dither=zero)
    center=np.clip(image[...,:3],0,1);y=center@LUMA;chroma=center-y[...,None]
    protect=zero.copy()
    if hud_masks:
        for key in ['Mask1','Mask2']:
            if c[key+'Enabled']:protect=np.maximum(protect,rect_mask(uv,c[key+'Rect'],c['MaskFeather'],w,h))
    values={(0,0):center}
    for j in range(-1,2):
        for k in range(-1,2):
            if k or j:values[(k,j)]=sample(center,uv+np.array([k/w,j/h])[:,None,None])
    a,b,cc,d,e,f,g,hh,i=[values[(k,j)] for j in range(-1,2) for k in range(-1,2)]
    lo=np.min(list(values.values()),axis=0);hi=np.max(list(values.values()),axis=0)
    span=np.max(hi-lo,axis=-1)
    curvature=np.maximum.reduce([abs(a-2*b+cc),abs(g-2*hh+i),abs(a-2*d+g),abs(cc-2*f+i),abs(d-2*center+f),abs(b-2*center+hh)]).max(-1)
    local=accept(span,c['EdgeThreshold']*STEP8)*(1-smooth(c['TextureThreshold']*STEP8,2*c['TextureThreshold']*STEP8,curvature))
    endpoint=smooth(0,.02,y)*(1-smooth(.98,1,y))
    local*=endpoint*(1-protect)
    pairs=[4,8,16][quality];total=center.copy();weights=np.ones((h,w));accepted=np.zeros((h,w))
    for pair in range(pairs):
        angle=np.pi*pair/pairs;dx,dy=np.cos(angle),np.sin(angle)
        for ring in (0,1):
            radius=c['Radius']*(.5 if ring==0 else 1.)
            shift=np.array([dx*radius/w,dy*radius/h])[:,None,None]
            positive=sample(center,uv+shift);negative=sample(center,uv-shift)
            yp=positive@LUMA;yn=negative@LUMA
            brightness=np.maximum(abs(yp-y),abs(yn-y))
            color=np.maximum(abs((positive-yp[...,None])-chroma).max(-1),abs((negative-yn[...,None])-chroma).max(-1))
            ww=accept(brightness,c['LumaThreshold']*STEP8)*accept(color,c['ChromaThreshold']*STEP8)
            ww*=(1 if ring==0 else .65)/pairs
            total+=.5*(positive+negative)*ww[...,None];weights+=ww;accepted+=ww
    eligible=local*smooth(.05,.35,np.clip(accepted/1.65,0,1))
    delta=total/weights[...,None]-center
    magnitude=abs(delta).max(-1)
    delta*=np.minimum(1,c['MaxCorrection']*STEP8/np.maximum(magnitude,1e-8))[...,None]
    delta*=(c['Strength']*eligible)[...,None]
    change=abs(delta).max(-1);active=change>1e-7
    result=center+delta;noise=zero.copy()
    step=0 if bit_depth>=16 else 1/1023 if bit_depth==10 else STEP8
    if enable_dither and c['Dither']>0 and step>0:
        yy,xx=np.indices((h,w));d=hash2(xx,yy)-hash2(xx+37,yy+17)
        minimum=result.min(-1);maximum=result.max(-1)
        headroom=smooth(0,2*step,np.minimum(minimum,1-maximum))
        changed=smooth(.01*STEP8,.25*STEP8,change)
        de=smooth(0,.25,eligible)
        noise=d*c['Dither']*step*de*c['Strength']*changed*headroom
        result+=noise[...,None]
    result=np.where(active[...,None],np.clip(result,0,1),image[...,:3])
    noise=np.where(active,noise,0)
    if image.shape[-1]==4:result=np.concatenate([result,image[...,3:4]],axis=-1)
    return result,dict(delta=delta,eligible=eligible,protection=protect,dither=noise,active=active)
