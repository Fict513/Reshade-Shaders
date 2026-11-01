#!/usr/bin/env python3
from pathlib import Path
import ctypes as C, json, subprocess, sys, hashlib
import numpy as np
from reference import *
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results';OUT.mkdir(exist_ok=True)
r={};checks=[]
def check(name,condition,details=None):
    checks.append({'test':name,'passed':bool(condition),'details':details})
    if not condition:print('FAIL',name,details)
def metric(name,value):r[name]=value
subprocess.run(['g++','-std=c++17','-O2','-fno-fast-math','-ffp-contract=off','-shared','-fPIC',str(ROOT/'tests/math_bridge.cpp'),'-o',str(ROOT/'tests/math_bridge.so')],check=True)
lib=C.CDLL(str(ROOT/'tests/math_bridge.so'))
for n in ['pq_decode','pq_encode','srgb_decode','srgb_encode','fraction','channel_limit']:
    fn=getattr(lib,n);fn.restype=C.c_float;fn.argtypes=[C.c_float]* (3 if n in ['fraction','channel_limit'] else 1)
def call(name,arr):return np.array([getattr(lib,name)(float(v)) for v in np.asarray(arr).flat]).reshape(np.asarray(arr).shape)
rng=np.random.default_rng(20261031)
# Production scalar functions, float32 native execution vs independent float64.
points=np.array([0,.001,.01,.1,1,80,100,203,1000,4000,10000.])
pq=call('pq_encode',points);back=call('pq_decode',pq)
metric('pq_reference',[{'nits':float(n),'encoded_float32':float(v),'decoded_float32':float(b),'reference_float64':float(encode(n,2))} for n,v,b in zip(points,pq,back)])
check('PQ points finite',np.isfinite(back).all())
check('PQ reference tolerance',np.max(abs(pq-encode(points,2)))<2e-5,float(np.max(abs(pq-encode(points,2)))))
v=np.linspace(0,1,100001);dec=call('pq_decode',v);enc=call('pq_encode',dec)
err=np.max(abs(enc-v));metric('pq_roundtrip_max_encoded_error',float(err));check('PQ dense float32 roundtrip',err<2e-5)
check('PQ 10-bit codes roundtrip',np.array_equal(np.rint(call('pq_encode',call('pq_decode',np.arange(1024)/1023))*1023),np.arange(1024)))
srgbpts=np.array([0,.0031308,.18,.5,1.])
metric('srgb_reference',[{'linear':float(n),'encoded':float(v)} for n,v in zip(srgbpts,call('srgb_encode',srgbpts))])
v=np.arange(256)/255;rt=call('srgb_encode',call('srgb_decode',v))
check('All 256 SDR grayscale codes roundtrip',np.array_equal(np.rint(rt*255),np.arange(256)),float(np.max(abs(rt-v))))
x=np.linspace(0,1,100001);rt=call('srgb_encode',call('srgb_decode',x));metric('srgb_roundtrip_max_error',float(np.max(abs(rt-x))));check('sRGB float32 roundtrip',np.max(abs(rt-x))<3e-7)
# Knee continuity and agreement with independent expression.
for t,k in [(250,150),(.6,.3),(20,1000),(.05,0),(.05,1)]:
    kk=min(k,2*t); y=np.unique(np.r_[np.linspace(0,4*t,3000),t-kk/2,t+kk/2]);f=np.array([lib.fraction(a,t,k) for a in y])
    ref=extract(np.repeat(y[:,None],3,axis=1),1,t,k)[:,0]
    check(f'Knee bounds and monotonic excess {t,k}',np.all((f>=0)&(f<=1)) and np.min(np.diff(y*f))>-1e-5)
    check(f'Production extraction reference {t,k}',np.max(abs(y*f-ref))<max(1e-6,t*1e-6))
    for edge in [t-kk/2,t+kk/2]:
        eps=max(1e-7,t*1e-5)
        left=lib.fraction(edge-eps,t,k)*(edge-eps);right=lib.fraction(edge+eps,t,k)*(edge+eps)
        check(f'Knee continuity {t,k,edge}',abs(right-left)<=2.1*eps)
# Kernel row and column stochasticity, measured independently.
for q in range(3):
    x,w=kernel(q)
    check(f'Kernel q{q} normalization',abs(w.sum()-1)<1e-9)
    check(f'Kernel q{q} variance',abs(sum(w*x*x)-2.25)<1e-7)
    for n in [1,2,3,17,108]:
        mat=sum(float(wi)*linear_matrix(n,n,float(xi*2.4)) for xi,wi in zip(x,w))
        check(f'Mirror filter mean and DC q{q} n{n}',max(np.max(abs(np.asarray(mat.sum(0))-1)),np.max(abs(np.asarray(mat.sum(1))-1)))<1e-8)
# Exact zero and alpha tests include signed extended values, all modes.
a=rng.uniform(-3,30,(17,31,4)).astype(np.float32)
for mode in range(5):
    b=pipeline(a,mode,strength=0)
    check(f'Zero-strength modeled float4 bit identity mode{mode}',np.array_equal(a.view(np.uint32),b.view(np.uint32)))
for mode in [1,2,3]:
    a=rng.random((17,31,4)).astype(np.float32)
    if mode==3:a[...,:3]=a[...,:3]*100-10
    o=pipeline(a,mode,t=.5 if mode==1 else 250,k=.3 if mode==1 else 150)
    check(f'Alpha preservation modeled mode{mode}',np.array_equal(a[...,3].view(np.uint32),o[...,3].view(np.uint32)))
    check(f'Finite output modeled mode{mode}',np.isfinite(o).all())
# Signed color extraction / redistribution: negative components must survive.
colors=np.array([[1000,1000,1000],[3000,0,0],[0,3000,0],[0,0,10000],[5000,-200,100],[0,0,0],[-100,-10,-1],[5240320,-800,80]],dtype=np.float32)
e=extract(colors,3,250,150);check('Signed positive-luminance extraction retains negatives',e[4,1]<0);check('Nonpositive luminance extracts zero',np.all(e[6]==0))
metric('signed_scrgb_extraction_examples',[{'source_nits':list(map(float,c)),'extracted_nits':list(map(float,v))} for c,v in zip(colors,e)])
# Output limiter: direction of change is shared; saturated boundary is intentional.
for mode,cap in [(1,1.),(2,10000.)]:
    s=rng.random((10000,3)).astype(np.float32)*cap;b=rng.random((10000,3)).astype(np.float32)*cap*4;e=extract(s,mode,.5*cap,.25*cap)
    o,f=compose(s,e,b,mode,.25)
    check(f'Output box domain mode{mode}',np.all(o>=0)&np.all(o<=cap))
    for j in range(100):
        d=.25*(b[j]-e[j]);ff=min(lib.channel_limit(s[j,i],d[i],cap) for i in range(3));ff=ff*(1-2e-6) if ff<1 else ff
        check(f'Production limiter mode{mode} sample{j}',abs(ff-f[j])<2e-6)
    s=np.array([[cap,0,0],[cap,cap,cap]],dtype=np.float32);b=np.full_like(s,cap);e=np.zeros_like(s);o,f=compose(s,e,b,mode,.1)
    check(f'Boundary veto mode{mode}',np.array_equal(o,s)&np.all(f==0))
# Constants, impulses, edges, odd and 1-pixel dimensions, target resolution.
spatial_stats=[]
for h,w in [(1,1),(1,17),(19,1),(2,3),(33,65),(128,192),(1440,3440)]:
    a=np.ones((h,w,1),dtype=np.float32)*1000;b=spatial(a)
    check(f'Constant field {w}x{h}',np.max(abs(b-a))<.002,float(np.max(abs(b-a))))
    for yy,xx,label in [(h//2,w//2,'center'),(0,0,'corner'),(0,w//2,'edge')]:
        a.fill(0);a[yy,xx]=10000;b=spatial(a)
        ratio=float(b.sum(dtype=np.float64)/a.sum(dtype=np.float64))
        spatial_stats.append({'size':[w,h],'location':label,'blurred_to_extracted_sum_ratio':ratio,'finite':bool(np.isfinite(b).all()),'minimum':float(b.min())})
        check(f'Impulse nonnegative finite {w}x{h} {label}',np.isfinite(b).all() and b.min()>=0)
        # Odd reconstruction is deliberately measured, not falsely asserted exact.
        if w%32==0 and h%32==0:check(f'Even-grid mass {w}x{h} {label}',abs(ratio-1)<2e-5)
metric('spatial_impulses',spatial_stats)
# Full spatial profiles at target HEIGHT in a compact strip (same y scale).
h,w=1440,256
a=np.zeros((h,w,1),np.float64);a[h//2,w//2]=10000
profiles=[];bs=[]
for q in range(3):
    b=spatial(a,q);bs.append(b);yy,xx=np.indices((h,w));mass=b.sum();cx=(b[...,0]*xx).sum()/mass;cy=(b[...,0]*yy).sum()/mass
    rms=np.sqrt((b[...,0]*((xx-cx)**2+(yy-cy)**2)).sum()/mass)
    profiles.append({'quality':q,'sum':float(mass),'rms_radius_px':float(rms),'peak':float(b.max())})
metric('quality_profiles',profiles)
check('Quality flux consistency',np.ptp([v['sum'] for v in profiles])/10000<1e-7)
check('Quality RMS radius consistency',np.ptp([v['rms_radius_px'] for v in profiles])/profiles[2]['rms_radius_px']<.005)
metric('quality_L1_vs_ultra',[float(abs(b-bs[2]).sum()/10000) for b in bs])
# Thin lines, checkerboards, strong edges, signed patches.
h,w=96,160;yy,xx=np.indices((h,w))
for name,gray in [('thin_line',(xx==w//2)*1000.),('checker',((xx+yy)%2)*1000.),('edge',(xx>w//2)*1000.)]:
    s=np.repeat(gray[...,None],3,2).astype(np.float32);e=extract(s,2,250,150);b=spatial(e);o,_=compose(s,e,b,2,.065)
    check(name+' finite neutral bounded',np.isfinite(o).all() and np.max(np.ptp(o,axis=2))==0 and o.min()>=0 and o.max()<=1000.001)
# Moving, pixel-integrated point: extraction nonlinearity vs downsample instability.
h,w=144,256;stats=[]
for pos in np.linspace(100,102,33):
    a=np.zeros((h,w,1),np.float64);ix=int(pos);f=pos-ix;a[h//2,ix]=1000*(1-f);a[h//2,ix+1]=1000*f
    rgb=np.repeat(a,3,2);e=extract(rgb,2,250,150);b=spatial(e)
    stats.append({'position':float(pos),'extracted_Y_sum':float(e[...,0].sum()),'blurred_Y_sum':float(b[...,0].sum()),'peak':float(b[...,0].max())})
metric('moving_subpixel_source',stats)
metric('moving_extraction_relative_peak_to_peak',float(np.ptp([v['extracted_Y_sum'] for v in stats])/np.mean([v['extracted_Y_sum'] for v in stats])))
check('Moving source finite',all(np.isfinite(v['peak']) for v in stats))
# Intermediate quantization: compare complete FP32 and simulated FP16 storage.
h,w=144,256;scene=rng.random((h,w,3))*4000
scene[:h//3]*=.000001;scene[h//2:h//2+4,w//2:w//2+4]=[5000,-500,50]
e=extract(scene,3,250,150);ref=spatial(e);f32=spatial(e.astype(np.float32));half=spatial(e.astype(np.float32),half=True)
metric('storage_error_nits',{'float32_max':float(abs(f32-ref).max()),'float32_rms':float(np.sqrt(np.mean((f32-ref)**2))),'float16_max':float(abs(half-ref).max()),'float16_rms':float(np.sqrt(np.mean((half-ref)**2)))})
check('FP32 accumulated error',abs(f32-ref).max()<.02)
bright=np.full((32,32,3),5240320.,np.float32)
with np.errstate(over='ignore'):metric('fp16_direct_nit_storage_overflows',bool(np.isinf(bright.astype(np.float16)).all()))
# Quantized tails and gradients, actual encoded-domain rounding.
tail=np.geomspace(1e-8,.1,4096)
metric('rounded_tail_codes',{})
for mode,bits,linear in [(1,8,tail),(2,10,tail*10000)]:
    encoded=call('srgb_encode' if mode==1 else 'pq_encode',linear)
    codes=np.rint(encoded*(2**bits-1)).astype(int);decoded=decode(codes/(2**bits-1),mode)
    metric(f'rounding_{bits}bit',{'unique_codes':int(np.unique(codes).size),'zero_samples':int((codes==0).sum()),'first_nonzero_linear':float(linear[np.flatnonzero(codes)[0]]) if np.any(codes) else None,'max_linear_quant_error':float(abs(decoded-linear).max()),'monotonic':bool(np.all(np.diff(codes)>=0))})
    check(f'{bits}-bit tail monotonic rounding',np.all(np.diff(codes)>=0))
# Shader source contracts, distinct from GPU execution.
fx=(ROOT/'HDR_Bloom.fx').read_text()
check('Non-sRGB sampler/write states', 'SRGBTexture=true' not in fx and 'SRGBWriteEnable=true' not in fx)
check('Production exact original early return', 'if(!Active()) return original;' in fx)
check('All effect and diagnostic alpha use original', 'float4(Encode(result,m),original.a)' in fx and 'float4(Diagnostic(e,b,result-source,limit,m),original.a)' in fx)
# FX front-end compile matrix: real resource dimensions inspected, not fake test macros.
compiler=ROOT/'tests/fx_frontend';matrix=[]
if compiler.exists():
    for w,h in [(1,1),(1,17),(19,1),(2,3),(65,33),(3440,1440)]:
      for q in range(3):
       for diagnostics in range(2):
        for auto in range(4):
         for backend in ['h','g']:
          proc=subprocess.run([str(compiler),str(ROOT/'HDR_Bloom.fx'),str(w),str(h),str(q),str(diagnostics),str(auto),backend],capture_output=True,text=True)
          ok=proc.returncode==0
          if ok:
            meta=json.loads(proc.stdout);tex=meta['textures'];ok=meta['passes']==12 and len(tex)==12
            for t in tex:
              if t['name'].endswith('Source'):continue
              level=int(t['name'][-1]);factor=2**level
              ok=ok and t['width']==(w+factor-1)//factor and t['height']==(h+factor-1)//factor and t['format']==2
          matrix.append({'width':w,'height':h,'quality':q,'diagnostics':diagnostics,'auto_contract':auto,'backend':backend,'passed':bool(ok),'stderr':proc.stderr})
    check('All FX parser/codegen/resource permutations',all(v['passed'] for v in matrix),len(matrix))
    (OUT/'compiler_matrix.json').write_text(json.dumps(matrix,indent=2))
else:check('FX front-end available',False,'Run build_frontend.sh first')
metric('checks',checks);metric('pass_count',sum(v['passed'] for v in checks));metric('fail_count',sum(not v['passed'] for v in checks))
r['shader_sha256']=hashlib.sha256((ROOT/'HDR_Bloom.fx').read_bytes()).hexdigest()
(OUT/'validation.json').write_text(json.dumps(r,indent=2));print(json.dumps({'passed':r['pass_count'],'failed':r['fail_count'],'compiler_variants':len(matrix)},indent=2))
sys.exit(bool(r['fail_count']))
