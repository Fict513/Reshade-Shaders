"""CPU model of Adaptive_Clarity.fx, not GPU shader execution.

Uses float32 guide writes and SciPy bilinear CLAMP sampling. Floating-point
execution and interpolation may differ from GPU hardware.
"""
import numpy as np
from scipy.ndimage import map_coordinates

LUMA=np.array([.2126,.7152,.0722])
DEFAULTS=dict(Strength=.75,TextureStrength=.40,EdgeStrength=.15,Radius=1.,
              NoiseThreshold=.0025,NoiseProtection=.65,DirectionProtection=.80,
              PatternProtection=.70,RingingProtection=.85,Overshoot=.03,
              MaxCorrection=.025,Mask1Enabled=False,Mask1Rect=(0,.82,.35,1),
              Mask2Enabled=False,Mask2Rect=(.65,.82,1,1),MaskFeather=12.)

def smooth(a,b,x):
    t=np.clip((x-a)/(b-a),0,1)
    return t*t*(3-2*t)

def decode(x):return np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
def encode(x):return np.where(x<=.0031308,x*12.92,1.055*np.maximum(x,0)**(1/2.4)-.055)

def reconstruct(rgb,y,target):
    chroma=rgb*(target/np.where(y>0,y,1))[...,None]-target[...,None]
    high=chroma.max(-1);low=chroma.min(-1)
    factor=np.minimum(1,np.where(high>0,(1-target)/np.where(high>0,high,1),1))
    factor=np.minimum(factor,np.where(low<0,target/np.where(low<0,-low,1),1))
    result=target[...,None]+chroma*factor[...,None]
    result=np.where((y<=0)[...,None],target[...,None],result)
    return np.clip(result,0,1)

def grid(h,w):
    yy,xx=np.indices((h,w))
    return np.array([(xx+.5)/w,(yy+.5)/h])

def sample(src,uv):
    h,w=src.shape
    return map_coordinates(src,np.array([uv[1]*h-.5,uv[0]*w-.5]),order=1,mode='nearest')

def rectangle_mask(uv,rect,feather,width,height):
    rect=np.array(rect);lo=np.minimum(rect[:2],rect[2:]);hi=np.maximum(rect[:2],rect[2:])
    outside=np.maximum(np.maximum(lo[:,None,None]-uv,uv-hi[:,None,None]),0)
    distance=np.sqrt(np.sum((outside*np.array([width,height])[:,None,None])**2,axis=0))
    if feather<=0:return (distance<=0).astype(float)
    return 1-smooth(0,feather,distance)

def structure(a,b,c,d,e,f,g,h,i):
    gx=.5*np.stack([b-a+e-d,c-b+f-e,e-d+h-g,f-e+i-h])
    gy=.5*np.stack([d-a+e-b,e-b+f-c,g-d+h-e,h-e+i-f])
    xx=np.sum(gx*gx,axis=0);yy=np.sum(gy*gy,axis=0);xy=np.sum(gx*gy,axis=0)
    trace=xx+yy;anis=np.sqrt(np.maximum((xx-yy)**2+4*xy*xy,0))
    coherence=np.clip(anis/np.maximum(trace,1e-8),0,1)
    lam=.5*(trace+anis);vx=xy;vy=lam-xx
    fallback=vx*vx+vy*vy<=1e-12
    vx=np.where(fallback,(xx>=yy).astype(float),vx)
    vy=np.where(fallback,(xx<yy).astype(float),vy)
    norm=np.sqrt(np.maximum(vx*vx+vy*vy,1e-12))
    return vx/norm,vy/norm,coherence

def process(image,quality=1,hud_masks=True,color_space=1,**overrides):
    """RGB or RGBA in [0,1]; returns image plus diagnostics, including correction."""
    c=DEFAULTS|overrides
    h,w=image.shape[:2];uv=grid(h,w);zero=np.zeros((h,w))
    if color_space>1 or c['Strength']<=0:
        return image.copy(),dict(correction=zero,coherence=zero,protection=zero)
    source=np.clip(image[...,:3],0,1);linear=decode(source);y=linear@LUMA
    guide=encode(y).astype(np.float32).astype(float)
    protect=zero.copy()
    if hud_masks:
        for key in ['Mask1','Mask2']:
            if c[key+'Enabled']:
                protect=np.maximum(protect,rectangle_mask(uv,c[key+'Rect'],c['MaskFeather'],w,h))
    radius=c['Radius'];pixel=np.array([radius/w,radius/h])[:,None,None]
    values={}
    for j in range(-1,2):
        for k in range(-1,2):values[(k,j)]=sample(guide,uv+pixel*np.array([k,j])[:,None,None])
    a,b,cc,d,e,f,g,hh,i=[values[(x,j)] for j in range(-1,2) for x in range(-1,2)]
    nx,ny,coherence=structure(a,b,cc,d,e,f,g,hh,i)
    lo=np.min(list(values.values()),axis=0);hi=np.max(list(values.values()),axis=0)
    def sw(value,dx,dy):
        alignment=dx*nx+dy*ny
        mix=coherence*c['DirectionProtection']
        directional=1-mix+mix/(1+4*alignment*alignment)
        sigma=.30*(1-c['DirectionProtection'])+.06*c['DirectionProtection']
        return directional/(1+((value-e)/sigma)**2)
    def gate(delta):
        threshold=c['NoiseThreshold']*(1+c['NoiseProtection']*(1-coherence))
        return smooth(threshold,threshold+.006,abs(delta))
    total=4*e;weights=np.full_like(e,4.)
    for (k,j),value in values.items():
        if k==0 and j==0:continue
        length=np.hypot(k,j);spatial=2 if k==0 or j==0 else 1
        weight=spatial*sw(value,k/length,j/length)
        total=total+value*weight;weights=weights+weight
    near=total/weights;fine=e-near
    gain=c['TextureStrength']*(1-coherence)+c['EdgeStrength']*coherence
    correction=gain*fine*gate(fine)
    if c['TextureStrength']>0:
        directions=[4,8,16][quality];total=e.copy();weights=np.ones_like(e)
        for k in range(directions):
            angle=2*np.pi*k/directions;dx,dy=np.cos(angle),np.sin(angle)
            value=sample(guide,uv+pixel*np.array([dx,dy])[:,None,None]*2)
            weight=sw(value,dx,dy)*(4/directions)
            total+=value*weight;weights+=weight
        band=near-total/weights
        correction+=.5*c['TextureStrength']*(1-.75*coherence)*band*gate(band)
    axial=.25*(b+d+f+hh);diagonal=.25*(a+cc+g+i)
    alternating=abs(e-axial)/np.maximum(abs(e-axial)+abs(e-diagonal),1e-7)
    pattern=smooth(.60,.90,alternating)*smooth(.01,.10,hi-lo)
    correction*=1-c['PatternProtection']*pattern
    correction=correction*c['MaxCorrection']/(c['MaxCorrection']+abs(correction))
    margin=c['Overshoot']*(hi-lo)*(1-.8*c['RingingProtection']*coherence)
    correction=np.clip(correction,lo-margin-e,hi+margin-e)
    endpoint=smooth(.02,.12,e)*(1-smooth(.90,.995,e))
    correction*=endpoint*c['Strength']*(1-protect)
    target=decode(np.clip(encode(y)+correction,0,1))
    result=encode(reconstruct(linear,y,target))
    result=np.where((correction==0)[...,None],image[...,:3],np.clip(result,0,1))
    if image.shape[-1]==4:result=np.concatenate([result,image[...,3:4]],axis=-1)
    diagnostics=dict(correction=correction,coherence=coherence,protection=protect,
                     lo=lo,hi=hi,margin=margin,guide=guide,endpoint=endpoint)
    return result,diagnostics
