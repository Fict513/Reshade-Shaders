"""Independent float64 NumPy model, separate convolution formulation.
No imports or translations of production arithmetic. Clamp-to-edge boundaries.
"""
import numpy as np

def decode(x,c):
    x=np.asarray(x,dtype=np.float64)
    if c==1:return np.where(x<=.04045,x/12.92,((np.maximum(x,0)+.055)/1.055)**2.4)
    if c==2:
        p=np.maximum(x,0)**(32/2523)
        return 125*(np.maximum(p-3424/4096,0)/(2413/128-2392/128*p))**(16384/2610)
    return x.copy()
def encode(x,c):
    x=np.asarray(x,dtype=np.float64)
    if c==1:return np.where(x<=.0031308,12.92*x,1.055*np.maximum(x,0)**(1/2.4)-.055)
    if c==2:
        p=(np.maximum(x,0)/125)**(2610/16384)
        return ((3424/4096+2413/128*p)/(1+2392/128*p))**(2523/32)
    return x.copy()
def luminance(x,c):
    return np.sum(x*np.array([.2627,.678,.0593] if c==2 else [.2126,.7152,.0722]),axis=-1)
def shift(a,dx,dy):
    h,w=a.shape
    return a[np.clip(np.arange(h)+dy,0,h-1)[:,None],np.clip(np.arange(w)+dx,0,w-1)[None,:]]
def blur(y,k):
    r=len(k)//2
    out=np.zeros_like(y)
    for j,wy in enumerate(k):
        for i,wx in enumerate(k):out+=wx*wy*shift(y,i-r,j-r)
    return out

def run(src,c=3,p=(.65,.45,.1,.85,.8,.5),detail_enabled=True,view=0,fmt=10):
    src=np.asarray(src,dtype=np.float64)
    master,fine,detail,edge,noise,split=p
    detail=detail if detail_enabled else 0
    if c not in (1,2,3) or master==0 or fine==detail==0:return src.copy()
    rgb=decode(src[...,:3],c);y=luminance(rgb,c)
    samples=[shift(y,i,j) for j in (-1,0,1) for i in (-1,0,1)]
    nw,n,ne,w,_,e,sw,s,se=samples
    lo=np.min(samples,axis=0);hi=np.max(samples,axis=0);span=hi-lo
    b1=blur(y,[.25,.5,.25]);b2=blur(y,np.array([1,4,6,4,1])/16)
    scale=np.maximum(np.abs(y),np.abs(b1))+.01
    eg=1/(1+12*edge*(span/scale)**2)
    tv=np.abs(n-y)+np.abs(s-y)+np.abs(e-y)+np.abs(w-y)+.5*(np.abs(nw-y)+np.abs(ne-y)+np.abs(sw-y)+np.abs(se-y))
    coherent=np.clip((np.abs(e-w)+np.abs(n-s)+.5*(np.abs(ne-sw)+np.abs(nw-se)))/np.maximum(tv,1e-20),0,1)
    ng=(1-.9*noise*(1-coherent))*np.divide(span,span+noise*.04*scale,out=np.zeros_like(span),where=span+noise*.04*scale!=0)
    gate=eg*ng*np.maximum(y,0)/(np.maximum(y,0)+.002)
    raw=master*gate*(fine*(y-b1)+detail*(b1-b2))
    extension=(1-edge)*.02*span
    room=np.where(raw>=0,hi-y+extension,y-lo+extension)
    up=np.full(y.shape,.12)
    if c!=3:up=np.maximum((1 if c==1 else 125)/np.maximum(np.max(rgb,axis=-1),1e-20)-1,0)
    elif fmt in (0,10):up=np.maximum(65504/np.maximum(np.max(np.abs(rgb),axis=-1),1e-20)-1,0)
    budget=np.minimum(np.minimum(.12*span,np.maximum(room,0)),np.maximum(y,0)*np.where(raw>=0,np.minimum(.12,up),.12))
    delta=np.divide(raw*budget,budget+np.abs(raw),out=np.zeros_like(raw),where=budget+np.abs(raw)>0)
    # Constant fields/unsupported nonpositive Y are identity in production.
    delta=np.where((y>0)&(span>0),delta,0)
    effective=np.where((y>0)&(span>0),master*gate,0)
    limiter=np.divide(np.abs(delta),np.abs(raw),out=np.ones_like(raw),where=raw!=0)
    limiter=np.where((y>0)&(span>0),np.clip(1-limiter,0,1),0) * np.abs(raw)/(np.abs(raw)+.001*scale)
    gain=1+np.divide(delta,y,out=np.zeros_like(y),where=y>0)
    out=src.copy();out[...,:3]=np.where((delta!=0)[...,None],encode(rgb*gain[...,None],c),src[...,:3])
    if view==1:out[:,(np.arange(y.shape[1])+.5)/y.shape[1]<split]=src[:,(np.arange(y.shape[1])+.5)/y.shape[1]<split]
    if view>=2:
        if view==2:
            t=np.clip(delta/np.maximum(np.abs(y),.002)/.05,-1,1)
            palette=.18+np.abs(t)[...,None]*(np.where((t>=0)[...,None],np.array([.75,.22,.04]),np.array([.04,.30,.75]))-.18)
        else:palette=np.repeat((.02+.78*(effective if view==3 else limiter))[...,None],3,axis=-1)
        out[...,:3]=encode(palette,c)
    return out
