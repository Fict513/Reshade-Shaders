"""CPU reference, not GPU execution. Scalar production FXH runs through C++ float.
The vector pipeline and local filter below are independent NumPy reference ports.
"""
import ctypes
import pathlib
import subprocess
import tempfile
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUILD = ROOT / 'validation/build'
BUILD.mkdir(parents=True, exist_ok=True)
CPP = r'''
#include <cmath>
#include <algorithm>
using std::min; using std::max; using std::pow; using std::log2; using std::exp2;
float smoothstep(float a,float b,float x) {
 float t=min(max((x-a)/(b-a),0.0f),1.0f); return t*t*(3.0f-2.0f*t);
}
#include "HDRIPS_Math.fxh"
extern "C" void run(int op,const float *x,float *y,int n,float c,float a,float s,float h) {
 for(int i=0;i<n;i++) {
  if(op==0)y[i]=HDRIPS_PQDecode(x[i]);
  if(op==1)y[i]=HDRIPS_PQEncode(x[i]);
  if(op==2)y[i]=HDRIPS_Global(x[i],c,a,s,h);
  if(op==3)y[i]=HDRIPS_SoftBudget(x[i],c);
 }
}
'''
def build_scalar():
    cpp=BUILD/'scalar.cpp'; so=BUILD/'scalar.so'
    cpp.write_text(CPP)
    subprocess.run(['g++','-std=c++17','-O2','-shared','-fPIC','-ffp-contract=off',
                    '-fsingle-precision-constant','-I',str(ROOT/'Shaders'),str(cpp),
                    '-o',str(so)],check=True,capture_output=True)
    lib=ctypes.CDLL(str(so))
    lib.run.argtypes=[ctypes.c_int,ctypes.POINTER(ctypes.c_float),ctypes.POINTER(ctypes.c_float),
                      ctypes.c_int]+[ctypes.c_float]*4
    return lib
LIB=None
def scalar(op,x,c=0.,a=100.,s=.8,h=.85):
    global LIB
    if LIB is None: LIB=build_scalar()
    v=np.ascontiguousarray(x,dtype=np.float32); out=np.empty_like(v)
    LIB.run(op,v.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),
            out.ctypes.data_as(ctypes.POINTER(ctypes.c_float)),v.size,c,a,s,h)
    return out

Y=np.array([.2627,.6780,.0593])
M709=np.array([[.627403896,.329283038,.043313066],
               [.069097289,.919540395,.011362316],
               [.016391439,.088013308,.895595253]])
MTO709=np.array([[1.660491002,-.587641139,-.072849863],
                [-.124550475,1.132899897,-.008349422],
                [-.018150763,-.100578898,1.118729661]])
MP3=np.array([[1.343578253,-.282179670,-.061398583],
              [-.065297452,1.075787916,-.010490464],
              [.002821787,-.019598495,1.016776708]])
def smooth(a,b,x):
    t=np.clip((x-a)/(b-a),0,1);return t*t*(3-2*t)
def toe(s):return 2**(-10+10*s)
def high(a,h):return min(10000.,a*2**(6-4.5*h))
def pq64(v):
    p=np.maximum(v,0)/10000.;p=p**(2610/16384)
    return np.where(v<=0,0,((3424/4096+(2413/128)*p)/(1+(2392/128)*p))**(2523/32))
def unpq64(v):
    p=np.asarray(v)**(32/2523)
    return 10000*(np.maximum(p-3424/4096,0)/(2413/128-2392/128*p))**(16384/2610)
def soft(add,budget):
    knee=.5*np.maximum(budget,0);d=np.maximum(add-knee,0)
    return np.where(budget<=0,0,np.where(add<=knee,add,knee+knee*d/np.maximum(knee+d,1e-30)))

def local_delta(image,a=100,s=.8,h=.85,strength=.12,radius=8,quality=1,storage=np.float32):
    """Mirror the square, point-sampled bilateral gather including clamp borders."""
    guide=np.log2(np.maximum(image,.0001)).astype(storage).astype(np.float64)
    center=np.log2(np.maximum(image,.0001));low=center.copy();hi=center.copy()
    total=np.zeros_like(center);weight=np.zeros_like(center)
    yy,xx=np.indices(image.shape);q=quality+1
    for j in range(-q,q+1):
        for i in range(-q,q+1):
            # Shader round is nearest; tie handling doesn't affect our integer test radii.
            dx=int(np.rint(i/q*radius));dy=int(np.rint(j/q*radius))
            sample=guide[np.clip(yy+dy,0,image.shape[0]-1),np.clip(xx+dx,0,image.shape[1]-1)]
            d=(sample-center)/.75
            w=np.exp2(-2*((i/q)**2+(j/q)**2)-2*d*d)
            total+=sample*w;weight+=w;low=np.minimum(low,sample);hi=np.maximum(hi,sample)
    residual=center-total/np.maximum(weight,.000001)
    bounded=.5*residual/(.5+np.abs(residual))
    gate=smooth(toe(s),a*.25,image)*(1-smooth(a,high(a,h),image))
    return np.clip(center+strength*bounded*gate,low,hi)-center

def pipeline(signal,mode=1,master=.75,c=.12,a=100,s=.8,h=.85,color=.06,
             saturation=.85,delta=0):
    """Reference normal output; diagnostics and FX runtime executed only in game."""
    original=np.array(signal,copy=True)
    if mode==0 or master==0 or (c==0 and color==0 and np.all(np.asarray(delta)==0)):
        return original
    flat=original.reshape(-1,4);rgb=flat[:,:3].astype(np.float64)
    valid=np.isfinite(rgb).all(axis=1)
    if mode==1:valid&=((rgb>=0)&(rgb<=1)).all(axis=1)
    linear=np.zeros_like(rgb)
    if mode==1:linear[valid]=unpq64(rgb[valid])
    else:linear[valid]=(rgb[valid]*80)@M709.T
    lum=linear@Y;valid&=lum>0
    out=flat.copy()
    x=linear[valid];y=lum[valid]
    if not len(y):return original
    # Neutral scalar FX returns its float input exactly. Avoid inventing an
    # exposure change by dividing its float result by a double reference Y.
    target=(y.copy() if c==0 else scalar(2,y,c,a,s,h).astype(np.float64))
    target*=np.exp2(np.broadcast_to(delta,lum.shape)[valid])
    wanted=target/y;gain=wanted.copy()
    if mode==1:
        budget=np.maximum(10000/np.maximum(x.max(axis=1),1e-6)-1,0)
        gain=np.where(wanted>1,1+soft(wanted-1,budget),wanted)
    result=x*gain[:,None];yp=y*gain
    if color:
        proxy=result@MP3.T;chroma=result-yp[:,None]
        sat=np.maximum(0,1-proxy.min(axis=1)/yp)
        ratio=np.ptp(result,axis=1)/np.maximum(yp,.0001)
        gate=smooth(.015,.08,ratio)*smooth(a*.005,a*.15,yp)*(1-smooth(a,high(a,h),yp))
        gate*=1-smooth(.95-.45*saturation,1,sat)
        wanted=color*gate;budget=np.maximum(1/np.maximum(sat,1e-6)-1,0)
        if mode==1:
            for k in range(3):
                ch=chroma[:,k];pos=ch>0;neg=ch<0
                limit=np.full_like(ch,np.inf)
                limit[pos]=np.maximum((10000-result[pos,k])/ch[pos],0)
                limit[neg]=np.maximum(-result[neg,k]/ch[neg],0)
                budget=np.minimum(budget,limit)
        result+=chroma*soft(wanted,budget)[:,None]
    result=linear[valid]*(1-master)+result*master
    encoded=pq64(result) if mode==1 else (result@MTO709.T)/80
    unchanged=(result==linear[valid]).all(axis=1)
    encoded[unchanged]=rgb[valid][unchanged]
    out[valid,:3]=encoded
    return out.reshape(original.shape)
