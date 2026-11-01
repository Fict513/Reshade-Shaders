#!/usr/bin/env python3
"""Run production-adapted C++ vs independent NumPy tests. Requires numpy, g++.
Optional --frontend /path/to/fx_frontend runs the real ReShade frontend matrix.
"""
import argparse,ctypes,json,subprocess,sys,hashlib,csv
from pathlib import Path
import numpy as np
import reference as ref
ROOT=Path(__file__).resolve().parents[1];HERE=ROOT/'validation';OUT=HERE/'results';BUILD=HERE/'build'
OUT.mkdir(exist_ok=True);BUILD.mkdir(exist_ok=True)
args=argparse.ArgumentParser();args.add_argument('--frontend');opts=args.parse_args()
rng=np.random.default_rng(90210)
report={'scope':'Adapted production FX functions on CPU; no GPU/in-game testing','checks':[],'metrics':{}}
def check(name,ok,**details):
    report['checks'].append({'name':name,'pass':bool(ok),**details})
    if not ok:print('FAIL',name,details,flush=True)
def metric(name,v):report['metrics'][name]=float(v)
subprocess.run([sys.executable,str(HERE/'adapt_shader.py'),str(HERE/'adapted.cpp')],check=True)
libs={}
ptr=np.ctypeslib.ndpointer(np.float32,flags='C_CONTIGUOUS')
for q in range(3):
 for d in range(2):
    path=BUILD/f'adapted_q{q}_d{d}.so'
    subprocess.run(['g++','-std=c++17','-O2','-ffp-contract=off','-fPIC','-shared',f'-DADAPTIVE_DETAIL_QUALITY={q}',f'-DADAPTIVE_DETAIL_ENABLE_DETAIL={d}',str(HERE/'adapted.cpp'),'-o',str(path)],check=True)
    lib=ctypes.CDLL(str(path));lib.run.argtypes=[ptr,ptr,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ptr,ctypes.c_int]
    lib.transfer.argtypes=[ptr,ptr,ctypes.c_int,ctypes.c_int];libs[q,d]=lib

def run(a,c=3,p=(.65,.45,.1,.85,.8,.5),q=1,d=1,view=0,bits=0):
    a=np.ascontiguousarray(a,dtype=np.float32);o=np.empty_like(a);p=np.array(p,np.float32)
    libs[q,d].run(a,o,a.shape[1],a.shape[0],c,view,p,bits);return o

def transfer(a,op):
    a=np.ascontiguousarray(a,dtype=np.float32);o=np.empty_like(a);libs[1,1].transfer(a,o,a.size,op);return o

def rgba(rgb):
    a=np.asarray(rgb,dtype=np.float32)
    if a.ndim==2:a=np.repeat(a[...,None],3,axis=-1)
    return np.concatenate([a,rng.random((*a.shape[:2],1)).astype(np.float32)],axis=-1)

# Transfer references including toe, 80 nit white and standardized PQ landmarks.
x=np.array([0,.0031308,.18,1],np.float32)
check('sRGB encoding reference',np.max(abs(transfer(x,1)-ref.encode(x,1)))<2e-7)
x=np.array([0,.04045,.5,1],np.float32)
check('sRGB decoding reference',np.max(abs(transfer(x,0)-ref.decode(x,1)))<1e-7)
nits=np.array([0,.0001,.001,.01,.1,1,10,80,100,1000,10000],np.float32)
pq=transfer(nits,3);pqref=ref.encode(nits/80,2)
metric('PQ reference max code error',np.max(abs(pq-pqref)));check('PQ reference landmarks',np.max(abs(pq-pqref))<1e-5)
report['PQ_reference']=[{'nits':float(n),'reference':float(r),'production_f32':float(v)} for n,r,v in zip(nits,pqref,pq)]
for c,bits,dec,enc in [(1,8,0,1),(2,10,2,3)]:
    codes=np.linspace(0,1,2**bits,dtype=np.float32);back=transfer(transfer(codes,dec),enc)
    metric(f'{bits}bit roundtrip max code float error',np.max(abs(back-codes)))
    quant=np.floor(np.clip(back,0,1)*(2**bits-1)+.5).astype(int)
    check(f'all {2**bits} code round trips after actual {bits}bit rounding',np.array_equal(quant,np.arange(2**bits)))
    dense=np.linspace(0,1,100001,dtype=np.float32);d=transfer(dense,dec);r=ref.decode(dense,c)*(80 if c==2 else 1)
    metric(f'{bits}bit dense decode max linear error',np.max(abs(d-r)))
    metric(f'{bits}bit dense roundtrip max code float error',np.max(abs(transfer(d,enc)-dense)))

# Bit-identical zero/neutral and alpha paths, INCLUDING nonfinite alpha payloads.
a=rgba(rng.uniform(-.5,3,(13,17,3)));a[0,0,3]=np.nan;a[0,1,3]=-0.0
for q in range(3):
 for d in range(2):
  for view in range(5):
   for c in range(5):
    check(f'bypass q{q}d{d}v{view}c{c}',np.array_equal(run(a,c,(0,.8,.5,.8,.8,.5),q,d,view).view('u4'),a.view('u4')))
    check(f'alpha q{q}d{d}v{view}c{c}',np.array_equal(run(a,c,q=q,d=d,view=view)[...,3].view('u4'),a[...,3].view('u4')))
   check(f'neutral q{q}d{d}v{view}',np.array_equal(run(a,3,(1,0,0,.8,.8,.5),q,d,view).view('u4'),a.view('u4')))
   check(f'unknown contract q{q}d{d}v{view}',np.array_equal(run(a,0,q=q,d=d,view=view).view('u4'),a.view('u4')))

h,w=65,129;yy,xx=np.mgrid[:h,:w]
fixtures={
 'linear_ramp':np.broadcast_to(np.linspace(.02,.95,w),(h,w)),
 'near_black_ramp':np.broadcast_to(np.geomspace(1e-8,.01,w),(h,w)),
 'highlight_ramp':np.broadcast_to(np.linspace(.8,1,w),(h,w)),
 'step':np.where(xx<w//2,.05,.8),
 'impulse':np.where((xx==w//2)&(yy==h//2),.8,.05),
 'thin_line':np.where(xx==w//2,.8,.05),
 'checker':np.where((xx+yy)%2,.8,.05),
 'low_checker':.2+.006*(-1.)**(xx+yy),
 'fine_texture':.2+.008*np.sin(xx*2*np.pi/7)*np.cos(yy*2*np.pi/9),
 'low_texture':.2+.002*np.sin(xx*2*np.pi/7)*np.cos(yy*2*np.pi/9),
 'noise':.2+rng.normal(0,.003,(h,w)),
 'soft_edge':.05+.75/(1+np.exp(-(xx-w/2)/1.2)),
 'grain_texture':.2+.006*np.sin(xx*2*np.pi/7)+rng.normal(0,.003,(h,w)),
}
rows=[];worst={1:0,2:0,3:0};worst_quant={1:0,2:0};raw_diff_pixels={1:0,2:0}
for name,y in fixtures.items():
 for c,mult in [(1,1),(2,20),(3,20)]:
  src=rgba(ref.encode(np.repeat((y*mult)[...,None],3,axis=-1),c))
  expected=ref.run(src,c)
  for q in range(3):
   out=run(src,c,q=q)
   error=np.max(abs(out-expected));worst[c]=max(worst[c],error)
   lin=ref.decode(out[...,:3],c);yin=ref.luminance(ref.decode(src[...,:3],c),c);yo=ref.luminance(lin,c)
   rows.append({'fixture':name,'contract':c,'quality':q,'max_reference_error_encoded':float(error),'mean_delta_linear':float(np.mean(yo-yin)),
    'rms_delta_linear':float(np.sqrt(np.mean((yo-yin)**2))),'min_output_linear':float(yo.min()),'max_output_linear':float(yo.max())})
   check(f'finite grayscale {name} c{c} q{q}',np.isfinite(out).all() and np.array_equal(out[...,0],out[...,1]) and np.array_equal(out[...,0],out[...,2]))
   check(f'gain bounded {name} c{c} q{q}',np.max(abs(yo-yin)/np.maximum(yin,1e-12))<.1201)
   if c in (1,2):
    n=255 if c==1 else 1023
    quant=np.floor(np.clip(out[...,:3],0,1)*n+.5);qr=np.floor(np.clip(expected[...,:3],0,1)*n+.5)
    worst_quant[c]=max(worst_quant[c],np.max(abs(quant-qr)));raw_diff_pixels[c]+=np.count_nonzero(quant!=qr)
    check(f'output boundary {name} c{c} q{q}',out[...,:3].min()>=-2e-7 and out[...,:3].max()<=1+2e-6)
for c in worst:
 metric(f'max model error encoded contract {c}',worst[c]);check(f'independent model agreement c{c}',worst[c]<(3e-6 if c==1 else 4e-5 if c==2 else 3e-5))
for c in worst_quant:
 metric(f'final quantization worst reference difference c{c}',worst_quant[c]);metric(f'final quantization different RGB channels c{c}',raw_diff_pixels[c])
 check(f'final quantization at most one code c{c}',worst_quant[c]<=1)
with (OUT/'fixture_metrics.csv').open('w') as f:
 writer=csv.DictWriter(f,fieldnames=rows[0].keys());writer.writeheader();writer.writerows(rows)

# Exact constants for arbitrary representable encoded and signed colors; all tiers/features.
colors=[(0,0,0),(.04045,)*3,(.18,)*3,(1,)*3,(.2,.6,.8),(-.4,1,2),(-2,-1,-.1),(12.5,)*3,(65504,)*3]
for c in (1,2,3):
 for color in colors:
  if c!=3 and (min(color)<0 or max(color)>1):continue
  src=rgba(np.broadcast_to(color,(5,7,3)))
  for q in range(3):
   for d in range(2):check(f'constant {color} c{c} q{q} d{d}',np.array_equal(src.view('u4'),run(src,c,q=q,d=d).view('u4')))

# Signed/extended scRGB: retain chromaticity via common positive gain.
signed=rgba(np.stack([-.1-.05*np.sin(xx/3),.4+.1*np.cos(xx/4),2+.2*np.sin(yy/5)],axis=-1))
o=run(signed);ratio=o[...,:3]/signed[...,:3]
metric('signed scRGB max channel gain spread',np.max(np.ptp(ratio,axis=-1)))
check('signed scRGB signs preserved',np.array_equal(np.signbit(o[...,:3]),np.signbit(signed[...,:3])))
check('signed scRGB common gain',np.max(np.ptp(ratio,axis=-1))<4e-7)
check('signed scRGB reference',np.max(abs(o-ref.run(signed)))<2e-6)
# Near-zero Y cancellation, nonpositive Y and finite range boundaries.
for color in [(-1,.1,.2),(-1,0,0),(-.7152,.2126,0),(65504,65000,-65504),(1e17,-1e17,1e17)]:
 src=rgba(np.broadcast_to(color,(3,5,3)).copy());src[1,2,:3]*=.99;o=run(src)
 check(f'extended finite {color}',np.isfinite(o).all())
 if ref.luminance(src[...,:3],3).max()<=0:check(f'nonpositive unchanged {color}',np.array_equal(src.view('u4'),o.view('u4')))

# Saturated primaries and secondary colors approaching domain ceiling, force all strengths.
for c in (1,2,3):
 for color in [(1,0,0),(0,1,0),(0,0,1),(1,1,0),(1,0,1),(0,1,1)]:
  lin=np.array(color)[None,None,:]*(.85+.15*np.sin(xx/3)**2)[...,None]*(125 if c==2 else 1)
  src=rgba(ref.encode(lin,c));o=run(src,c,p=(1,1,1,0,0,.5));l=ref.decode(o[...,:3],c)
  check(f'saturated boundary c{c} {color}',np.isfinite(o).all() and (c==3 or (o[...,:3].max()<=1.000002 and o[...,:3].min()>=0)))
  # Black channels remain effectively black under canonical PQ zero encoding.
  check(f'zero channel retained c{c} {color}',np.max(np.abs(l[...,np.array(color)==0]))<1e-12)

# Strict extrema, relaxed extrema, combined-band budget across every q/d.
a=rgba(.1+rng.random((31,37))*.7);y=a[...,0]
lo=np.min([ref.shift(y,i,j) for i in (-1,0,1) for j in (-1,0,1)],axis=0);hi=np.max([ref.shift(y,i,j) for i in (-1,0,1) for j in (-1,0,1)],axis=0)
for q in range(3):
 for d in range(2):
  o=run(a,p=(1,1,1,1,0,.5),q=q,d=d)[...,0]
  check(f'strict extrema q{q}d{d}',np.all(o>=lo-1e-7) and np.all(o<=hi+1e-7))
  o=run(a,p=(1,1,1,0,0,.5),q=q,d=d)[...,0]
  check(f'combined budget q{q}d{d}',np.all(abs(o-y)<=.12*(hi-lo)+1e-7))
  check(f'relaxed extrema q{q}d{d}',np.all(o>=lo-.02*(hi-lo)-1e-7) and np.all(o<=hi+.02*(hi-lo)+1e-7))

# Actual-production diagnostics vs independent reconstruction, including split semantics.
a=rgba(fixtures['fine_texture'])
for c in (1,2,3):
 src=rgba(ref.encode(a[...,:3],c))
 for view in range(5):
  o=run(src,c,view=view);expected=ref.run(src,c,view=view)
  error=np.max(abs(o-expected));metric(f'diagnostic error c{c} v{view}',error)
  check(f'diagnostic agrees c{c} v{view}',error<(5e-4 if view>=2 else 2e-5))
  if view==1:check(f'split left exact c{c}',np.array_equal(o[:,:w//2].view('u4'),src[:,:w//2].view('u4')))

# Noise vs texture response (not a semantic skin/noise classification claim).
for name in ('noise','fine_texture','low_texture','low_checker','checker'):
 a=rgba(fixtures[name]);o=run(a);ratio=np.std(o[...,0])/np.std(a[...,0]);metric(name+' standard deviation ratio',ratio)
 if name=='noise':check('default noise gain below 5 percent',ratio<1.05)
 if name in ('fine_texture','low_texture'):check(name+' retained without blur',ratio>=.99999)

# Subpixel-motion: analytic continuous scene resampled at 1/16 pixel increments.
# Report changes in correction between frames; no motion compensation or temporal reuse.
for name in ('soft_edge','thin_peak','near_nyquist','texture'):
 frames=[];originals=[]
 for t in np.arange(17)/16:
  x=xx.astype(float)-t
  if name=='soft_edge':y=.05+.75/(1+np.exp(-(x-w/2)/1.2))
  elif name=='thin_peak':y=.05+.5*np.exp(-((x-w/2)/.55)**2)
  elif name=='near_nyquist':y=.2+.02*np.sin(2*np.pi*.47*x)*np.cos(yy*.9)
  else:y=.2+.008*np.sin(x*2*np.pi/7)*np.cos(yy*2*np.pi/9)
  a=rgba(y);o=run(a);frames.append(o[...,0]-a[...,0]);originals.append(a[...,0])
 motion=np.diff(frames,axis=0);metric(name+' motion correction max frame delta',np.max(abs(motion)));metric(name+' motion correction rms frame delta',np.sqrt(np.mean(motion**2)))
 check(name+' finite motion',np.isfinite(motion).all())

# Border and tiny/odd/full target dimensions. RGB alpha and texture addressing through shim.
for h,w in [(1,1),(1,19),(17,1),(2,2),(3,5),(17,31),(1440,3440)]:
 y,x=np.mgrid[:h,:w];a=rgba(.2+.01*np.sin(x*.7)*np.cos(y*.4))
 for q in range(3):
  for d in range(2):
   o=run(a,q=q,d=d)
   check(f'dimensions {w}x{h} q{q}d{d}',o.shape==a.shape and np.isfinite(o).all() and np.array_equal(o[...,3],a[...,3]))
   if w*h<10000:
    err=np.max(abs(o-ref.run(a,detail_enabled=bool(d))));check(f'border reference {w}x{h} q{q}d{d}',err<2e-6)
 # Compare same strength/radius across q, large resolution catches normalized UV rounding.
 q0=run(a,q=0);q1=run(a,q=1);q2=run(a,q=2);q0b=run(a,q=0,bits=8)
 metric(f'q0 vs q1 max {w}x{h}',np.max(abs(q0-q1)));metric(f'q0 8bit interpolation vs q1 max {w}x{h}',np.max(abs(q0b-q1)))
 check(f'Ultra exact High {w}x{h}',np.array_equal(q1.view('u4'),q2.view('u4')))
 check(f'Normal High near-equal {w}x{h}',np.max(abs(q0-q1))<2e-6)

# Half storage experiment: emulate intermediate quantization by quantizing linear grayscale
# input, then compare residuals. This isolates luma quantization rather than changing shader.
y=.2+.0001*np.sin(np.arange(257)[None,:]*2*np.pi/13);y=np.repeat(y,9,axis=0)
k=[.25,.5,.25];r32=y-ref.blur(y,k);half=y.astype(np.float16).astype(np.float64);rh=half-ref.blur(half,k)
metric('FP16 luma experiment residual RMS error',np.sqrt(np.mean((r32-rh)**2)))
metric('FP32 luma experiment residual RMS error',np.sqrt(np.mean((r32-(y.astype(np.float32).astype(float)-ref.blur(y.astype(np.float32).astype(float),k)))**2)))

# Frontend metadata verifies actual resource dimensions, flags, feature removal, and output.
if opts.frontend:
 compiles=[]
 for w,h in [(1,1),(1,19),(17,1),(3,5),(3440,1440)]:
  for q in range(3):
   for d in range(2):
    for c in (0,1,2,3,4):
     prefix=BUILD/f'fx_{w}_{h}_{q}_{d}_{c}';cmd=[opts.frontend,str(ROOT/'Shaders/Adaptive_Detail.fx'),str(prefix),str(w),str(h),str(q),str(d),str(c),'10']
     r=subprocess.run(cmd,capture_output=True,text=True);ok=r.returncode==0
     if ok:
      meta=prefix.with_suffix('.meta').read_text();ok=f'texture AD_Luma {w} {h} format 41' in meta and meta.count('pass ')==2 and 'srgb 1' not in meta and 'blend 1' not in meta
      if not d:ok=ok and 'AD_Detail;' not in prefix.with_suffix('.hlsl').read_text() and 'AD_LumaLinear' not in meta
     check(f'FX metadata {w}x{h} q{q}d{d}c{c}',ok)
     compiles.append({'width':w,'height':h,'q':q,'detail':d,'contract_macro':c,'status':r.returncode,'stderr':r.stderr})
 for fmt in (0,2,10,24,28):
  for q in range(3):
   for d in range(2):
    prefix=BUILD/f'fmt_{fmt}_{q}_{d}';r=subprocess.run([opts.frontend,str(ROOT/'Shaders/Adaptive_Detail.fx'),str(prefix),'3440','1440',str(q),str(d),'0',str(fmt)],capture_output=True,text=True)
    check(f'FX format {fmt} q{q}d{d}',r.returncode==0)
 (OUT/'frontend_matrix.json').write_text(json.dumps(compiles,indent=2))
 report['frontend']={'cases':180,'backends':['HLSL SM5','GLSL'],'driver_compilation':False}

report['summary']={'passed':sum(c['pass'] for c in report['checks']),'failed':sum(not c['pass'] for c in report['checks'])}
report['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'Shaders').glob('*')}
(OUT/'numerical_results.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'summary':report['summary'],'metrics':report['metrics']},indent=2),flush=True)
sys.exit(1 if report['summary']['failed'] else 0)
