"""CPU reference for IPS_Depth_v2.fx (not GPU execution).

NumPy/SciPy implement bilinear clamp sampling and half-float target writes.
GPU arithmetic and interpolation can differ. crop_height lets a small test
image exercise kernel radii belonging to a larger output image/crop.
"""
import numpy as np
from scipy.ndimage import map_coordinates, minimum_filter, maximum_filter, convolve

LUMA = np.array([0.2126, 0.7152, 0.0722])
DEFAULTS = dict(Contrast=.34, ShadowProtection=.90, HighlightLift=.15,
                FineContrast=.18, BroadContrast=.12, Radius=6.,
                EdgeProtection=.80, HaloProtection=.85, NoiseFloor=.003, Sharpen=0.)

def smooth(a, b, x):
    t = np.clip((x-a)/(b-a), 0, 1)
    return t*t*(3-2*t)

def decode(x):
    return np.where(x <= .04045, x / 12.92, ((x+.055)/1.055)**2.4)

def encode(x):
    return np.where(x <= .0031308, x * 12.92,
                    1.055*np.maximum(x, 0)**(1/2.4)-.055)

def tone(x, contrast=.34, shadow=.9, highlight=.15):
    protection = 1-shadow+shadow*smooth(.015,.18,x)
    upper = 1+(highlight-1)*smooth(.45,.70,x)
    return x+contrast*x*(1-x)*(2*x-1)*protection*upper

def reconstruct(rgb, y, target):
    chroma = rgb*(target/np.where(y>0,y,1))[...,None]-target[...,None]
    high = chroma.max(axis=-1)
    low = chroma.min(axis=-1)
    scale = np.minimum(1., np.where(high>0,(1-target)/np.where(high>0,high,1),1))
    scale = np.minimum(scale,np.where(low<0,target/np.where(low<0,-low,1),1))
    out = target[...,None]+chroma*scale[...,None]
    out = np.where((y<=0)[...,None],target[...,None],out)
    return np.clip(out,0,1)

def quantize(x):
    return np.asarray(x).astype(np.float16).astype(float)

def grid(h,w):
    yy,xx = np.indices((h,w))
    return np.array([(xx+.5)/w,(yy+.5)/h])

def sample(src,uv):
    h,w=src.shape[:2]
    coords=np.array([uv[1]*h-.5,uv[0]*w-.5])
    if src.ndim==2:
        return map_coordinates(src,coords,order=1,mode='nearest')
    return np.stack([map_coordinates(src[...,k],coords,order=1,mode='nearest')
                     for k in range(src.shape[2])],axis=-1)

def weight(i,d,taps,edge):
    sigma=.18*(1-edge)+.025*edge
    return np.exp2(-6.49212768*(i/taps)**2-.72134752*(d/sigma)**2)

def fine_filter(guide,radius,taps,edge):
    h,w=guide.shape;uv=grid(h,w)
    total=guide.copy();weights=np.ones_like(guide)
    for i in range(-taps,taps+1):
        if i==0:continue
        shift=uv.copy();shift[0]+=i*radius/taps/w
        v=sample(guide,shift);ww=weight(i,v-guide,taps,edge)
        total+=v*ww;weights+=ww
    horizontal=quantize(np.stack([total/weights,guide],axis=-1))
    total=horizontal[...,0].copy();weights=np.ones_like(guide)
    for i in range(-taps,taps+1):
        if i==0:continue
        shift=uv.copy();shift[1]+=i*radius/taps/h
        v=sample(horizontal,shift);ww=weight(i,v[...,1]-horizontal[...,1],taps,edge)
        total+=v[...,0]*ww;weights+=ww
    return quantize(total/weights)

def prepare_broad(fine,guide):
    h,w=guide.shape;uv=grid((h+1)//2,(w+1)//2)
    samples=[]
    for dx,dy in [(-.5,-.5),(.5,-.5),(-.5,.5),(.5,.5)]:
        shift=uv+np.array([dx/w,dy/h])[:,None,None]
        samples.append(np.stack([sample(fine,shift),sample(guide,shift)],axis=-1))
    values=np.stack(samples);average=values.mean(axis=0)
    confidence=1-smooth(.02,.12,np.ptp(values[...,1],axis=0))
    return quantize(np.stack([average[...,0],average[...,1],confidence],axis=-1))

def broad_filter(src,radius,taps,edge,fullshape):
    h,w=src.shape[:2];fh,fw=fullshape;uv=grid(h,w)
    result=src
    for axis in (0,1):
        center=result;initial=np.maximum(center[...,2]**4,.0001)
        total=center[...,0]*initial;weights=initial.copy()
        for i in range(-taps,taps+1):
            if i==0:continue
            shift=uv.copy();shift[axis]+=i*radius/taps/(fw if axis==0 else fh)
            v=sample(result,shift)
            ww=weight(i,v[...,1]-center[...,1],taps,edge)*v[...,2]**4
            total+=v[...,0]*ww;weights+=ww
        result=quantize(np.stack([total/weights,center[...,1],center[...,2]],axis=-1))
    return result

def upsample(src,guide,fallback,edge):
    h,w=guide.shape;sh,sw=src.shape[:2];uv=grid(h,w)
    size=np.array([sw,sh])[:,None,None];pos=uv*size-.5
    origin=np.floor(pos);f=pos-origin;total=np.zeros_like(guide);residual=np.zeros_like(guide)
    sigma=.18*(1-edge)+.025*edge
    for j in (0,1):
        for i in (0,1):
            v=sample(src,(origin+np.array([i+.5,j+.5])[:,None,None])/size)
            spatial=(1-f[0] if i==0 else f[0])*(1-f[1] if j==0 else f[1])
            ww=spatial*np.exp2(-.72134752*((v[...,1]-guide)/sigma)**2)*v[...,2]**4
            residual+=(v[...,0]-v[...,1])*ww;total+=ww
    confidence=smooth(.00001,.01,total)
    value=fallback*(1-confidence)+(guide+residual/np.maximum(total,.000001))*confidence
    return value,confidence

def limit(x,m):return x*m/(m+abs(x))

def process(rgb,quality=1,local=True,broad=True,crop_height=None,**overrides):
    c=DEFAULTS|overrides
    h,w=rgb.shape[:2];linear=decode(rgb);y=linear@LUMA;p=encode(y)
    guide=quantize(p) if local else p
    taps=[4,6,10][quality];radius=c['Radius']*(crop_height or h)/1080
    detail=np.zeros_like(p);confidence=np.zeros_like(p)
    gate=lambda d:smooth(c['NoiseFloor'],c['NoiseFloor']+.006,abs(d))
    if local:
        fine=fine_filter(guide,radius,taps,c['EdgeProtection'])
        d=guide-fine;detail=limit(c['FineContrast']*d*gate(d),.020)
        if broad:
            src=prepare_broad(fine,guide)
            src=broad_filter(src,3*radius,taps,c['EdgeProtection'],(h,w))
            base,confidence=upsample(src,guide,fine,c['EdgeProtection'])
            d=fine-base;detail+=limit(c['BroadContrast']*d*gate(d),.025)
    edge=1
    if c['Sharpen']>0 or (local and c['HaloProtection']>0):
        lo=minimum_filter(guide,3,mode='nearest');hi=maximum_filter(guide,3,mode='nearest')
        blur=convolve(guide,np.array([[1,2,1],[2,4,2],[1,2,1]])/16,mode='nearest')
        edge=1-c['HaloProtection']*smooth(.06,.28,hi-lo)
        d=guide-blur;sharp=limit(c['Sharpen']*d*gate(d),.010);margin=.04*(hi-lo)
        detail+=np.clip(sharp,lo-margin-guide,hi+margin-guide)
    target=tone(p,c['Contrast'],c['ShadowProtection'],c['HighlightLift'])
    envelope=smooth(.02,.14,p)*(1-smooth(.80,.98,p))
    room=np.maximum(0,np.minimum(target,1-target))
    detail=np.clip(detail*edge*envelope,-.25*room,.25*room)
    target=np.clip(target+detail,0,1)
    out=encode(reconstruct(linear,y,decode(target)))
    return out,detail,confidence
