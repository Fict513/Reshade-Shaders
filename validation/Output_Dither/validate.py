"""Reproducible analytical/CPU validation; never a claim of GPU equivalence.
SPDX-License-Identifier: MIT
python validate.py --cpu-dll /path/core_cpu.dll --fx-compiler /path/fx_probe.exe
"""
from pathlib import Path
import os
import argparse, ctypes, hashlib, json, math, platform, re, subprocess
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'validation'/'.work'/'Output_Dither'/'results'
OUT.mkdir(exist_ok=True)
GEN = ROOT/'validation'/'.work'/'Output_Dither'/'generated'
GEN.mkdir(exist_ok=True)
RESOLUTIONS = [(1920,1080),(1920,1200),(2560,1440),(3440,1440),(1919,1079),(1,137),(137,1),(1,1)]
ASSET = np.array(Image.open(ROOT/'Textures'/'Output_Dither_BN128.png'))
NOISE = (ASSET.astype(np.float64)+.5)/256-.5
checks=[]
report={'environment':dict(python=platform.python_version(),numpy=np.__version__), 'checks':checks}
def check(name, condition):
    checks.append(dict(name=name,passed=bool(condition)))
    if not condition: raise AssertionError(name)
def stats(x):
    a=np.asarray(x,dtype=np.float64)
    return dict(mean=float(a.mean()), rms=float(np.sqrt(np.mean(a*a))), min=float(a.min()),max=float(a.max()))
def q(x,L):
    return np.floor(np.clip(x,0,1)*L+.5)/L
def tiled(w,h):
    return NOISE[np.arange(h)[:,None]%128,np.arange(w)[None,:]%128]
def apply_scalar(x,n,s,L):
    return np.where((x==0)|(x==1),x,np.clip(x+n*s/L,0,1))
def reference(a,s=1,contract=1,target=0,bypass=False):
    out=a.copy()
    if bypass or not ((contract==1 and target in (0,1)) or (contract==2 and target==2)) or not 0<s<=1:
        return out
    h,w,_=a.shape
    n=((ASSET[np.arange(h)[:,None]%128,np.arange(w)[None,:]%128].astype(np.float32)/np.float32(255)*np.float32(255)+np.float32(.5))/np.float32(256)-np.float32(.5))
    rgb=a[...,:3]
    valid=np.all((rgb>=0)&(rgb<=1),axis=-1)
    val=np.clip(rgb+n[...,None]*(np.float32(s)/np.float32(255 if target==0 else 1023)),0,1)
    val=np.where((rgb==0)|(rgb==1),rgb,val)
    out[...,:3]=np.where(valid[...,None],val,rgb)
    return out
def srgb_encode(x):
    return np.where(x<=.0031308,12.92*x,1.055*np.maximum(x,0)**(1/2.4)-.055)
def srgb_decode(x):
    return np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
def pq_encode(x):
    m1=2610/16384; m2=2523/32; c1=3424/4096; c2=2413/128; c3=2392/128
    a=np.maximum(x,0)**m1
    return ((c1+c2*a)/(1+c3*a))**m2
def pq_decode(x):
    m1=2610/16384; m2=2523/32; c1=3424/4096; c2=2413/128; c3=2392/128
    a=np.maximum(x,0)**(1/m2)
    return (np.maximum(a-c1,0)/(c2-c3*a))**(1/m1)
def low_fraction(x):
    a=x-x.mean()
    p=abs(np.fft.fft2(a))**2
    fy=np.fft.fftfreq(a.shape[0])[:,None]; fx=np.fft.fftfreq(a.shape[1])[None,:]
    return float(p[(fx*fx+fy*fy)<.1**2].sum()/max(p.sum(),1e-30))
def bit_equal(a,b):
    return np.array_equal(a.view(np.uint32),b.view(np.uint32))

def run(cpu_dll=None, compiler=None):
    check('asset dimensions and R8 payload',ASSET.shape==(128,128) and ASSET.dtype==np.uint8)
    check('exact uniform finite histogram',np.all(np.bincount(ASSET.ravel(),minlength=256)==64))
    check('exact centered tile mean',NOISE.mean()==0)
    check('finite extrema',NOISE.min()==-127.5/256 and NOISE.max()==127.5/256)
    check('finite RMS formula',abs(np.mean(NOISE**2)-(256**2-1)/(12*256**2))<1e-15)
    report['asset']=dict(stats=stats(NOISE),sha256=hashlib.sha256(ASSET.tobytes()).hexdigest())
    white=np.random.default_rng(42).permutation(NOISE.ravel()).reshape(128,128)
    spectrum={}
    for name,a in [('scalar',NOISE),('threshold_10', (NOISE<-.4).astype(float)),('threshold_50',(NOISE<0).astype(float)),('threshold_90',(NOISE<.4).astype(float))]:
        spectrum[name]=low_fraction(a)
    spectrum['white_scalar']=low_fraction(white)
    check('scalar low frequency suppression',spectrum['scalar']<.25*spectrum['white_scalar'])
    check('10/50/90 percent threshold low-frequency suppression',all(spectrum[k]<.01 for k in ('threshold_10','threshold_50','threshold_90')))
    report['spectrum_energy_below_0_1_cycles_per_pixel']=spectrum
    seams={}
    for axis in (0,1):
        d=np.diff(NOISE,axis=axis)
        edge=np.take(NOISE,0,axis=axis)-np.take(NOISE,-1,axis=axis)
        seams[str(axis)]={'internal_rms':stats(d)['rms'],'seam_rms':stats(edge)['rms']}
        check(f'wrap seam axis {axis} comparable to internal differences',.65<stats(edge)['rms']/stats(d)['rms']<1.35)
    report['seams']=seams
    cpu=None
    if cpu_dll:
        lib=ctypes.CDLL(str(Path(cpu_dll).resolve()))
        ptr=np.ctypeslib.ndpointer(dtype=np.float32,flags='C_CONTIGUOUS')
        lib.od_run.argtypes=[ptr,ptr,np.ctypeslib.ndpointer(dtype=np.uint8,flags='C_CONTIGUOUS')]+[ctypes.c_int]*5+[ctypes.c_float]
        def cpu(a,s=1,contract=1,target=0,bypass=False):
            a=np.ascontiguousarray(a,dtype=np.float32); b=np.empty_like(a)
            lib.od_run(a,b,ASSET,a.shape[1],a.shape[0],int(bypass),contract,target,s)
            return b
    evaluate=cpu or reference
    report['adapted_production_cpu']='executed' if cpu else 'NOT RUN'
    resolution_results=[]
    for w,h in RESOLUTIONS:
        n=tiled(w,h)
        a=np.empty((h,w,4),np.float32)
        a[...,:3]=np.linspace(0,1,w,dtype=np.float32)[None,:,None]
        a[...,3]=np.linspace(-.5,1.5,w,dtype=np.float32)[None,:]
        maxdiff=0
        for contract,target in ((1,0),(1,1),(2,2)):
            b=evaluate(a,contract=contract,target=target)
            ref=reference(a,contract=contract,target=target)
            maxdiff=max(maxdiff,float(np.max(abs(b-ref))))
            check(f'{w}x{h} contract {contract} target {target} CPU agreement',np.allclose(b,ref,atol=1.2e-7,rtol=0))
            check(f'{w}x{h} alpha unchanged {target}',bit_equal(b[...,3].copy(),a[...,3].copy()))
            check(f'{w}x{h} bounded normalized output {target}',np.all((b[...,:3]>=0)&(b[...,:3]<=1)))
        # Simulate the same pixel-center calculation used by the production PS.
        for size in (w,h):
            uv=(np.arange(size,dtype=np.float32)+np.float32(.5))/np.float32(size)
            idx=np.floor(uv*np.float32(size)).astype(int)
            check(f'{w}x{h} float32 center indices axis {size}',np.array_equal(idx,np.arange(size)))
        check(f'{w}x{h} exact zero strength',bit_equal(evaluate(a,s=0),a))
        check(f'{w}x{h} exact master bypass',bit_equal(evaluate(a,bypass=True),a))
        resolution_results.append(dict(width=w,height=h,noise_stats=stats(n),tiles_across=w/128,tiles_down=h/128,max_cpu_difference=maxdiff))
    report['resolutions']=resolution_results
    # All mode/target combinations, including corrupted enums, preserve alpha.
    a=np.random.default_rng(5).random((19,23,4),dtype=np.float32)
    for contract in (-1,0,1,2,3,4):
        for target in (-1,0,1,2,3):
            b=evaluate(a,contract=contract,target=target)
            valid=(contract==1 and target in (0,1)) or (contract==2 and target==2)
            check(f'contract matrix {contract}/{target}',np.allclose(b,reference(a,contract=contract,target=target),atol=1.2e-7,rtol=0) if valid else bit_equal(a,b))
    for s in (-1,0,.25,.5,1,1.1,float('nan'),float('inf')):
        b=evaluate(a,s=s)
        check(f'strength {s}',np.allclose(b,reference(a,s=s),atol=1.2e-7,rtol=0) if 0<s<=1 else bit_equal(a,b))
    values=np.array([0.,-0.,1.,-1.,2.,65504.,-65504.,np.finfo(np.float32).max,np.nan,np.inf,-np.inf,np.nextafter(np.float32(0),np.float32(1))],np.float32)
    extreme=np.zeros((1,len(values),4),np.float32)
    extreme[...,:3]=values[None,:,None]; extreme[...,3]=values
    for contract in (0,3):
        check(f'signed/extended/nonfinite bypass {contract}',bit_equal(evaluate(extreme,contract=contract),extreme))
    b=evaluate(extreme)
    invalid=(~np.isfinite(values))|(values<0)|(values>1)|(values==0)|(values==1)
    check('invalid and exact endpoint pixel returns',bit_equal(b[:,invalid,:].copy(),extreme[:,invalid,:].copy()))
    check('nonfinite alpha preserved',bit_equal(b[...,3].copy(),extreme[...,3].copy()))
    mixed=np.full((1,len(values),4),.4,np.float32); mixed[0,:,1]=values
    inv=(~np.isfinite(values))|(values<0)|(values>1)
    check('one invalid RGB channel bypasses whole pixel',bit_equal(evaluate(mixed)[:,inv,:].copy(),mixed[:,inv,:].copy()))
    # Constant full tiles provide controlled enumeration of the finite distribution.
    endpoints=[]
    for L in (255,1023):
        for code in (0,.001,.05,.1,.25,.49,.5,.51,.75,1,1.25,L-1.25,L-.75,L-.25,L-.05,L):
            x=code/L
            raw=apply_scalar(x,NOISE,1,L)
            err=(q(raw,L)-x)*L
            row=dict(levels=L,input_code=code,prequant_mean_shift_codes=float((raw.mean()-x)*L),quantized_error=stats(err))
            endpoints.append(row)
            check(f'finite RPDF quantized bias bound {L}/{code}',abs(err.mean())<=1/512+1e-10)
    report['endpoints']=endpoints
    gradients=[]
    plot_data=[]
    w,h=1920,1080; n=tiled(w,h)
    for L in (255,1023):
        x=np.broadcast_to(np.linspace(32,48,w)/L,(h,w))
        plain=q(x,L); dither=q(apply_scalar(x,n,1,L),L)
        old=q(x,L); repeat=q(apply_scalar(old,n,1,L),L)
        large=q(apply_scalar(old,n,2,L),L) # CPU test ONLY: production refuses >1.
        check(f'already-quantized same-grid identical {L}',np.array_equal(old,repeat))
        check(f'larger noise perturbs old codes {L}',np.any(old!=large))
        row=dict(levels=L,without=stats((plain-x)*L),with_dither=stats((dither-x)*L),
                 column_mean_rms_without=stats(((plain-x)*L).mean(axis=0))['rms'],
                 column_mean_rms_with=stats(((dither-x)*L).mean(axis=0))['rms'],
                 error_low_frequency_without=low_fraction(plain-x),error_low_frequency_with=low_fraction(dither-x),
                 same_grid_changed_pixels=int(np.count_nonzero(old!=repeat)),
                 double_strength_changed_fraction=float(np.mean(old!=large)),
                 double_strength_error_to_original=stats((large-x)*L))
        check(f'gradient spatial band error reduced {L}',row['column_mean_rms_with']<row['column_mean_rms_without']*.2)
        check(f'gradient low frequency error reduced {L}',row['error_low_frequency_with']<row['error_low_frequency_without']*.2)
        gradients.append(row)
        plot_data.append((x,plain,dither,repeat))
    report['gradients']=gradients
    # Same-grid preservation at every code and byte, float32 adapted arithmetic.
    for target,contract,L in ((0,1,255),(1,1,1023),(2,2,1023)):
        a=np.empty((128,L+1,4),np.float32)
        a[...,:3]=(np.arange(L+1,dtype=np.float32)/np.float32(L))[None,:,None]; a[...,3]=.7
        check(f'production float32 all code positions same-grid {target}',np.array_equal(q(evaluate(a,contract=contract,target=target)[...,:3],L),q(a[...,:3],L)))
        codes=np.arange(L+1,dtype=np.float64)[:,None]/L
        samples=(np.arange(256,dtype=np.float64)+.5)/256-.5
        for strength in (.25,.5,1):
            check(f'exhaustive ideal every code and byte {target}/{strength}',np.all(q(apply_scalar(codes,samples,strength,L),L)==codes))
    # Why a uniform LINEAR step does not correspond to a uniform encoded step.
    domains=[]
    for name,L,enc,dec in [('sRGB8',255,srgb_encode,srgb_decode),('sRGB10',1023,srgb_encode,srgb_decode),('PQ10',1023,pq_encode,pq_decode)]:
        for e in (.01,.05,.18,.5,.9):
            correct=apply_scalar(e,NOISE,1,L)
            wrong=enc(np.clip(dec(e)+NOISE/L,0,1))
            domains.append(dict(contract=name,encoded_value=e,correct_delta_codes=stats((correct-e)*L),incorrect_linear_delta_codes=stats((wrong-e)*L),wrong_quantized_error_codes=stats((q(wrong,L)-e)*L)))
    report['encoded_vs_incorrect_linear']=domains
    # Shifted tile channels are an evaluated alternative, not an independence claim.
    noise_rgb=np.stack([NOISE,np.roll(NOISE,(37,59),(0,1)),np.roll(NOISE,(83,17),(0,1))],axis=-1)
    report['shifted_channel_correlation']=np.corrcoef(noise_rgb.reshape(-1,3),rowvar=False).tolist()
    colors=[]
    for encoding,L,decode,weights in [('sRGB',255,srgb_decode,[.2126,.7152,.0722]),('PQ',1023,pq_decode,[.2627,.6780,.0593])]:
        for color in ([.5,.5,.5],[.123,.457,.789],[1,0,0],[0,1,0],[0,0,1],[1,.2,0],[.0001,.01,.1],[.9999,.95,.8]):
            x=np.array(color)
            for method,nn in [('correlated',NOISE[...,None]),('shifted_channels',noise_rgb)]:
                y=q(apply_scalar(x,nn,1,L),L)
                delta=(y-x)*L
                linear=decode(y); baseline=decode(x)
                lum=linear@np.array(weights); base_lum=baseline@np.array(weights)
                chroma=np.stack([delta[...,0]-delta[...,1],delta[...,2]-delta[...,1]],-1)
                colors.append(dict(encoding=encoding,color=color,method=method,bias_codes=delta.mean(axis=(0,1)).tolist(),rgb_rms_codes=np.sqrt((delta**2).mean(axis=(0,1))).tolist(),opponent_change_rms_codes=stats(chroma)['rms'],linear_luminance_delta=stats(lum-base_lum)))
                if color==[.5,.5,.5] and method=='correlated':
                    check(f'neutral remains neutral in tested {encoding} quantizer',np.array_equal(y[...,0],y[...,1]) and np.array_equal(y[...,1],y[...,2]))
                if color in ([1,0,0],[0,1,0],[0,0,1]):
                    check(f'saturated endpoint {encoding}/{color}/{method}',np.all(y==x))
    report['colors']=colors
    # Produce scientific figures, not screenshots claiming a display improvement.
    fig,axes=plt.subplots(2,3,figsize=(13,7))
    axes[0,0].imshow(NOISE,cmap='gray',vmin=-.5,vmax=.5); axes[0,0].set_title('128 x 128 generated scalar mask')
    p=abs(np.fft.fftshift(np.fft.fft2(NOISE)))**2
    axes[0,1].imshow(np.log10(p+1e-8),cmap='magma'); axes[0,1].set_title('Log10 power spectrum (DC removed)')
    bins=np.linspace(0,.7072,65); fy,fx=np.meshgrid(np.fft.fftfreq(128),np.fft.fftfreq(128)); r=np.sqrt(fx*fx+fy*fy)
    for label,v in [('blue',NOISE),('shuffled white',white)]:
        power=abs(np.fft.fft2(v-v.mean()))**2
        means=[power[(r>=lo)&(r<hi)].mean() if np.any((r>=lo)&(r<hi)) else np.nan for lo,hi in zip(bins[:-1],bins[1:])]
        axes[0,2].semilogy((bins[1:]+bins[:-1])/2,means,label=label)
    axes[0,2].legend(); axes[0,2].set_xlabel('cycles / pixel'); axes[0,2].set_title('Radial power')
    x,plain,dither,repeat=plot_data[0]
    for label,v in [('undithered',plain),('dithered',dither)]:
        axes[1,0].plot((v-x).mean(0)*255,label=label,lw=1)
    axes[1,0].legend(); axes[1,0].set_title('Gradient: mean error over rows (codes)')
    axes[1,1].imshow((dither-x)[:128,:512]*255,cmap='coolwarm',vmin=-1,vmax=1,aspect='auto'); axes[1,1].set_title('Dithered error, deliberately magnified')
    axes[1,2].plot((plain-x)[0]*255,label='already quantized')
    axes[1,2].plot((repeat-x)[0]*255,ls='--',label='same-grid dither: identical'); axes[1,2].legend(); axes[1,2].set_title('Negative result: no recovered gradient')
    fig.tight_layout(); fig.savefig(OUT/'analysis.png',dpi=150); plt.close(fig)
    if compiler: compile_fx(compiler)
    else: report['fx_parsing']='NOT RUN'
    report['checks_passed']=sum(x['passed'] for x in checks)
    report['checks_total']=len(checks)
    (OUT/'results.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:report[k] for k in ('checks_passed','checks_total','asset','spectrum_energy_below_0_1_cycles_per_pixel','gradients')},indent=2))

def compile_fx(compiler):
    compiler=str(Path(compiler).resolve())
    fixture=GEN/'resolution_probe.fx'
    shader_include = Path(os.path.relpath(ROOT/'Shaders'/'Output_Dither.fx', GEN)).as_posix()
    fixture.write_text('#include "'+shader_include+'"\ntexture2D ResolutionProbe { Width = BUFFER_WIDTH; Height = BUFFER_HEIGHT; Format = R8; };\n')
    logs=[]; artifacts=[]
    for w,h in RESOLUTIONS:
        for enabled in (0,1):
            for backend in ('hlsl','glsl'):
                path=GEN/f'output_{w}x{h}_{enabled}.{backend}'
                proc=subprocess.run([compiler,str(fixture),str(w),str(h),str(enabled),backend,str(path)],capture_output=True,text=True)
                check(f'FX parser {w}x{h} enabled={enabled} {backend}',proc.returncode==0)
                text=proc.stdout+proc.stderr
                check(f'FX resolution override {w}x{h} {enabled} {backend}',f'texture ResolutionProbe {w}x{h}' in text)
                check(f'FX raw nonblended pass {w}x{h} {enabled} {backend}','srgb=0 blend=0' in text)
                check(f'FX resource removal {w}x{h} {enabled} {backend}',('texture OD_BlueNoise 128x128' in text)==bool(enabled))
                code=path.read_text()
                check(f'codegen removes noise {w}x{h} {enabled} {backend}',('OD_NoiseSampler' in code)==bool(enabled))
                logs.append(dict(width=w,height=h,enabled=enabled,backend=backend,output=text,code_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
                if backend=='hlsl': artifacts.append(path)
    report['fx_parsing']=dict(variants=len(logs),log=logs)
    # Isolate a shader without its include or PNG: compile-time removal must make
    # both unnecessary. An active build must fail for the missing include.
    isolated=GEN/'isolated'; isolated.mkdir(exist_ok=True)
    isolated_fx=isolated/'Output_Dither.fx'
    isolated_fx.write_bytes((ROOT/'Shaders'/'Output_Dither.fx').read_bytes())
    missing=[]
    for enabled in (0,1):
        proc=subprocess.run([compiler,str(isolated_fx),'1920','1080',str(enabled),'hlsl',str(isolated/'out.hlsl')],capture_output=True,text=True)
        check(f'missing include and asset compile-time removal {enabled}',(proc.returncode==0)==(enabled==0))
        missing.append(dict(enabled=enabled,exit_code=proc.returncode,log=proc.stdout+proc.stderr))
    report['missing_resources']=dict(compile_tests=missing,missing_png_runtime='Not executed in ReShade; upstream runtime reports load failure. Parser does not load PNGs.')
    report['d3dcompile']=d3dcompile(artifacts)

def d3dcompile(paths):
    # Microsoft's CPU DXBC compiler is distinct from driver compilation/execution.
    try: dll=ctypes.WinDLL('d3dcompiler_47.dll')
    except (OSError,AttributeError): return {'status':'unavailable'}
    fn=dll.D3DCompile
    fn.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_char_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_uint,ctypes.c_uint,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(ctypes.c_void_p)]
    fn.restype=ctypes.c_long
    def blob_data(blob):
        if not blob: return b''
        table=ctypes.cast(blob,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        ptr=ctypes.WINFUNCTYPE(ctypes.c_void_p,ctypes.c_void_p)(table[3])(blob)
        size=ctypes.WINFUNCTYPE(ctypes.c_size_t,ctypes.c_void_p)(table[4])(blob)
        data=ctypes.string_at(ptr,size)
        ctypes.WINFUNCTYPE(ctypes.c_ulong,ctypes.c_void_p)(table[2])(blob)
        return data
    rows=[]
    for path in paths:
        code=path.read_bytes()
        for entry,profile in [(b'F__OD_VS',b'vs_5_0'),(b'F__OD_PS',b'ps_5_0')]:
            binary=ctypes.c_void_p(); error=ctypes.c_void_p()
            hr=fn(code,len(code),str(path).encode(),None,None,entry,profile,1<<11,0,ctypes.byref(binary),ctypes.byref(error))
            errors=blob_data(error).decode(errors='replace'); data=blob_data(binary)
            if hr<0: print(errors)
            check(f'D3DCompile {path.name} {entry.decode()}',hr>=0)
            (GEN/(path.stem+'_'+entry.decode()+'.dxbc')).write_bytes(data)
            rows.append(dict(file=path.name,entry=entry.decode(),bytes=len(data),messages=errors))
    return dict(status='executed CPU bytecode compilation only',variants=len(rows),log=rows)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--cpu-dll'); p.add_argument('--fx-compiler')
    a=p.parse_args(); run(a.cpu_dll,a.fx_compiler)
