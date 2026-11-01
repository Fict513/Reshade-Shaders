"""Independent CPU architectural reference, not GPU execution.
Float64 is the reference; float32 is a modeled pipeline. Texture filtering is
ideal bilinear here (hardware fractional precision and FMA may differ).
"""
import numpy as np
from scipy.special import ndtr
from scipy.sparse import csr_matrix
from functools import lru_cache

@lru_cache(None)
def area_matrix(n,m):
    rows=[];cols=[];data=[]
    for j in range(m):
        lo=j*n/m;hi=(j+1)*n/m
        for i in range(int(np.floor(lo)),min(n,int(np.ceil(hi)))):
            w=max(0., min(hi,i+1)-max(lo,i))/(hi-lo)
            if w:rows.append(j);cols.append(i);data.append(w)
    return csr_matrix((data,(rows,cols)),shape=(m,n))

def reflect(i,n):
    j=i%(2*n)
    return np.where(j<n,j,2*n-1-j)

@lru_cache(None)
def linear_matrix(n,m,offset=0.):
    x=(np.arange(m)+.5)*n/m-.5+offset
    a=np.floor(x).astype(int);f=x-a
    rows=np.repeat(np.arange(m),2)
    cols=np.stack([reflect(a,n),reflect(a+1,n)],1).ravel()
    data=np.stack([1-f,f],1).ravel()
    return csr_matrix((data,(rows,cols)),shape=(m,n))

def axis_apply(im,mat,axis):
    a=np.moveaxis(im,axis,0); old=a.shape
    a=mat.astype(im.dtype).dot(a.reshape(old[0],-1))
    return np.moveaxis(a.reshape((mat.shape[0],)+old[1:]),0,axis)

def down(im):
    h,w=im.shape[:2]
    return axis_apply(axis_apply(im,area_matrix(w,(w+1)//2),1),area_matrix(h,(h+1)//2),0)

def up(im,h,w):
    return axis_apply(axis_apply(im,linear_matrix(im.shape[1],w),1),linear_matrix(im.shape[0],h),0)

@lru_cache(None)
def kernel(q,sigma=1.5):
    radius=[10,12,14][q];x=np.arange(-radius,radius+1,dtype=float)
    w=np.exp(-x*x/(2*sigma*sigma));w/=w.sum()
    return x,w

def blur(im,q,spread,scale,fullh,fullw,half=False):
    sigmafull=1.5*scale*spread*fullh/1440
    for axis,full in [(1,fullw),(0,fullh)]:
        sigma=sigmafull*im.shape[axis]/full
        # Paired implementation in the production shader; equivalent to these
        # integer taps with ideal bilinear interpolation. Float arithmetic differs.
        x,weights=kernel(q,float(sigma))
        result=np.zeros_like(im)
        for node,weight in zip(x,weights):
            result+=im.dtype.type(weight)*axis_apply(im,linear_matrix(im.shape[axis],im.shape[axis],float(node)),axis)
        im=quant(result,half)
    return im

def quant(a,half):
    return a.astype(np.float16).astype(a.dtype) if half else a

def spatial(e,q=1,spread=1,half=False):
    h,w=e.shape[:2];p=e;out=np.zeros_like(e)
    for lev in range(1,6):
        p=quant(down(p),half)
        if lev in [1,3,5]:
            b=blur(p,q,spread,2**lev,h,w,half)
            out+=e.dtype.type({1:.55,3:.30,5:.15}[lev])*up(b,h,w)
    return out

def decode(v,mode):
    v=np.asarray(v)
    if mode==3:return v*80
    if mode==1:return np.where(v<=.04045,v/12.92,((v+.055)/1.055)**2.4)
    p=v**(1/78.84375)
    return 10000*(np.maximum(p-.8359375,0)/(18.8515625-18.6875*p))**(1/.1593017578125)

def encode(v,mode):
    v=np.asarray(v)
    if mode==3:return v/80
    if mode==1:return np.where(v<=.0031308,12.92*v,1.055*np.maximum(v,0)**(1/2.4)-.055)
    p=(v/10000)**.1593017578125
    return ((.8359375+18.8515625*p)/(1+18.6875*p))**78.84375

def lw(mode):return np.array([.2627,.678,.0593] if mode==2 else [.2126,.7152,.0722])

def extract(rgb,mode,t,k):
    y=rgb@lw(mode).astype(rgb.dtype);k=np.clip(k,0,2*t)
    excess=np.maximum(y-t,0)
    if k>0:
        soft=.5*k*(np.maximum(y-(t-.5*k),0)/k)**2
        excess=np.where(y<t+.5*k,soft,excess)
    f=np.minimum(np.divide(excess,y,out=np.zeros_like(y),where=y>0),1)
    return rgb*f[...,None]

def compose(source,e,b,mode,strength):
    d=np.asarray(strength,dtype=source.dtype)*(b-e)
    f=np.ones(source.shape[:-1],dtype=source.dtype)
    if mode!=3:
        cap=1 if mode==1 else 10000
        a=np.ones_like(d)
        np.divide(cap-source,d,out=a,where=(d>0)&(d>cap-source))
        np.divide(source,-d,out=a,where=(d<0)&(-d>source))
        f=np.minimum(a.min(axis=-1),1)
        f=np.where(f<1,np.maximum(f,0)*(1-2e-6),f)
    return source+f[...,None]*d,f

def pipeline(encoded,mode,strength=.04,t=250,k=150,q=1,spread=1,half=False):
    if strength<=0 or mode not in [1,2,3]:return encoded.copy()
    s=decode(encoded[...,:3],mode);e=extract(s,mode,t,k)
    b=spatial(e,q,spread,half);o,f=compose(s,e,b,mode,strength)
    result=np.concatenate([encode(o,mode),encoded[...,3:4]],axis=-1)
    return result

# Adaptation of production Downsample arithmetic (not GPU execution).
def production_down(im,dtype=np.float32):
    im=im.astype(dtype);h,w=im.shape[:2];oh,ow=(h+1)//2,(w+1)//2
    yy,xx=np.indices((oh,ow));cell=np.stack([xx,yy],-1).astype(dtype)
    ins=np.array([w,h],dtype=dtype);outs=np.array([ow,oh],dtype=dtype)
    lo=cell*ins/outs;hi=(cell+1)*ins/outs;start=np.floor(lo)
    total=np.zeros((oh,ow,im.shape[2]),dtype=dtype)
    for j in range(3):
      for i in range(3):
        p=start+np.array([i,j],dtype=dtype)
        overlap=np.maximum(0,np.minimum(hi,p+1)-np.maximum(lo,p))
        weight=overlap[...,0]*overlap[...,1]
        values=im[np.clip(p[...,1].astype(int),0,h-1),np.clip(p[...,0].astype(int),0,w-1)]
        total+=values*weight[...,None]
    return total/((hi[...,0]-lo[...,0])*(hi[...,1]-lo[...,1]))[...,None]

# Adaptation of production paired Gaussian arithmetic; sampling is ideal CPU
# linear interpolation, not a hardware sampler emulation.
def production_blur(im,q,spread,scale,fullh,fullw):
    h,w=im.shape[:2]
    sf=np.float32(1.5*scale*spread*(fullh/1440))
    for axis,full in [(1,fullw),(0,fullh)]:
        sigma=sf*np.float32(im.shape[axis]/full);inv=np.float32(.5)/(sigma*sigma)
        total=im.copy();norm=np.float32(1)
        for i in range([5,6,7][q]):
            a=np.float32(2*i+1);wa=np.exp(-a*a*inv);wb=np.exp(-(a+1)*(a+1)*inv);weight=np.float32(wa+wb)
            if weight>0:
                offset=np.float32(a+wb/weight)
                plus=axis_apply(im,linear_matrix(im.shape[axis],im.shape[axis],float(offset)),axis)
                minus=axis_apply(im,linear_matrix(im.shape[axis],im.shape[axis],float(-offset)),axis)
                total+=weight*(plus+minus);norm+=2*weight
        im=total/norm
    return im
