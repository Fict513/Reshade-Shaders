#!/usr/bin/env python3
"""Synthetic grayscale comparison; not a perceptual ranking or GPU CAS benchmark.
The CAS mathematical baseline adapts AMD's MIT-licensed no-scaling path with
CAS_GO_SLOWER, CAS_BETTER_DIAGONALS disabled. See THIRD_PARTY_NOTICES.md.
No CAS code is included in the production shader.
"""
from pathlib import Path
import ctypes,json,csv
import numpy as np
import reference as ref
HERE=Path(__file__).resolve().parent
lib=ctypes.CDLL(str(HERE/'build/adapted_q1_d1.so'))
ptr=np.ctypeslib.ndpointer(np.float32,flags='C_CONTIGUOUS')
lib.run.argtypes=[ptr,ptr,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ptr,ctypes.c_int]
def ad(y,p=(.65,.45,.1,.85,.8,.5),c=3):
    a=np.concatenate([np.repeat(ref.encode(y,c)[...,None],3,axis=-1),np.ones((*y.shape,1))],axis=-1).astype('f4')
    out=np.empty_like(a);lib.run(a,out,a.shape[1],a.shape[0],c,0,np.array(p,'f4'),0)
    return ref.decode(out[...,:3],c)[...,0]
def cas_gray(y,sharpness=0):
    n,s,e,w=[ref.shift(y,*d) for d in [(0,-1),(0,1),(1,0),(-1,0)]]
    low=np.minimum.reduce([y,n,s,e,w]);high=np.maximum.reduce([y,n,s,e,w])
    amp=np.sqrt(np.clip(np.minimum(low,1-high)/np.maximum(high,1e-30),0,1))
    weight=-amp/(8-3*sharpness)
    return np.clip((y+weight*(n+s+e+w))/(1+4*weight),0,1)
def usm(y):return y+.3*(y-ref.blur(y,[.25,.5,.25]))
x,y=np.meshgrid(np.arange(129),np.arange(65));rng=np.random.default_rng(130)
fixtures={'texture':.2+.008*np.sin(x*2*np.pi/7)*np.cos(y*2*np.pi/9),
'noise':.2+rng.normal(0,.003,x.shape),'step':np.where(x<64,.05,.8),
'soft_edge':.05+.75/(1+np.exp(-(x-64)/1.2)),
'impulse':np.where((x==64)&(y==32),.8,.05),'checker':np.where((x+y)%2,.8,.05)}
target=np.std(ad(fixtures['texture']))/np.std(fixtures['texture'])
def match(fn):
    base=fixtures['texture'];out=fn(base);lo,hi=0.,1.
    for _ in range(50):
        m=(lo+hi)/2
        if np.std(base+m*(out-base))/np.std(base)<target:lo=m
        else:hi=m
    return (lo+hi)/2
blend_cas=match(cas_gray);blend_usm=match(usm)
rows=[]
for name,a in fixtures.items():
 for label,fn in [('Adaptive Detail default',ad),('CAS math sharpness 0',cas_gray),('Unsharp amount 0.3',usm),
                  ('CAS matched texture gain',lambda v:v+blend_cas*(cas_gray(v)-v)),
                  ('Unsharp matched texture gain',lambda v:v+blend_usm*(usm(v)-v))]:
    out=fn(a);rows.append({'fixture':name,'filter':label,'std_ratio':float(np.std(out)/np.std(a)),
    'mean_bias':float(np.mean(out-a)),'overshoot_global':float(max(0,out.max()-a.max())),
    'undershoot_global':float(max(0,a.min()-out.min()))})
with (HERE/'results/baseline_comparison.csv').open('w') as f:
    wr=csv.DictWriter(f,fieldnames=rows[0]);wr.writeheader();wr.writerows(rows)
(HERE/'results/baseline_configuration.json').write_text(json.dumps({'CAS_sharpness':0,'CAS_math':'float64 grayscale no-scaling cross extrema, exact sqrt/reciprocal, output saturate',
 'target_texture_std_ratio':target,'CAS_blend_for_matching':blend_cas,'USM_blend_for_matching':blend_usm,
 'interpretation':'Matched only on one synthetic texture. No perceptual or performance superiority claim.'},indent=2))
# Exercise all 9 presets on all 6 fixtures. Record values, with domain/budget sanity checks.
import configparser
presets=[]
for path in sorted((HERE.parent/'Presets').glob('*.ini')):
 cfg=configparser.ConfigParser();cfg.read_string('[DEFAULT]\n'+path.read_text());s=cfg['Adaptive_Detail.fx']
 c=int(s['AD_Contract']);p=tuple(float(s[n]) for n in ['AD_Master','AD_Fine','AD_Detail','AD_Edge','AD_Noise','AD_Split'])
 for name,a in fixtures.items():
    lin=a*(20 if c!=1 else 1);out=ad(lin,p,c)
    ok=bool(np.isfinite(out).all() and np.max(abs(out-lin)/np.maximum(lin,1e-20))<.121)
    presets.append({'preset':path.name,'fixture':name,'pass':ok,'std_ratio':float(np.std(out)/np.std(lin)),'mean_bias':float(np.mean(out-lin))})
(HERE/'results/preset_validation.json').write_text(json.dumps(presets,indent=2))
assert all(x['pass'] for x in presets)
try:
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
 fig,axes=plt.subplots(1,3,figsize=(14,4),layout='constrained')
 f=np.linspace(0,.5,400);g=np.cos(np.pi*f)**2
 axes[0].plot(f,1-g,label='Fine: 1 − G₁');axes[0].plot(f,g-g*g,label='Detail: G₁ − G₂');axes[0].set(xlabel='Cycles per output pixel',ylabel='Unadapted response',title='Distinct bands, shared limiter');axes[0].legend()
 a=fixtures['soft_edge'];o=ad(a);axes[1].plot(np.arange(129)[54:75],a[32,54:75],label='Input',lw=2);axes[1].plot(np.arange(129)[54:75],o[32,54:75],label='Natural Detail',lw=1.5);axes[1].set(xlabel='Pixel',ylabel='Linear luminance',title='Restrained softened-edge change');axes[1].legend()
 a=fixtures['texture'];o=ad(a);axes[2].plot(np.arange(129)[20:49],a[32,20:49],label='Input',lw=2);axes[2].plot(np.arange(129)[20:49],o[32,20:49],label='Natural Detail',lw=1.5);axes[2].set(xlabel='Pixel',ylabel='Linear luminance',title='Low-contrast texture preserved');axes[2].legend()
 fig.savefig(HERE/'results/filter_behavior.png',dpi=160);plt.close(fig)
except ImportError:print('matplotlib not installed; metrics saved, optional chart skipped')
print('Saved baseline comparison and',len(presets),'preset checks')
