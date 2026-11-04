"""Execute parser-generated production HLSL on D3D11 hardware, offscreen.
SPDX-License-Identifier: MIT. Run validate.py first to produce DXBC.
"""
import argparse, ctypes, json
from pathlib import Path
import numpy as np
from validate import ROOT, OUT, GEN, RESOLUTIONS, ASSET, reference, bit_equal, q, stats

FORMATS={2:(np.float32,4,16),10:(np.float16,4,8),28:(np.uint8,4,4),24:(np.uint32,1,4)}
checks=[]
def check(name,ok):
    checks.append(dict(name=name,passed=bool(ok)))
    if not ok: raise AssertionError(name)
def pack(a,fmt):
    if fmt in (2,10): return np.ascontiguousarray(a,dtype=FORMATS[fmt][0])
    if fmt==28:return np.ascontiguousarray(np.rint(np.clip(a,0,1)*255),dtype=np.uint8)
    rgb=np.rint(np.clip(a[...,:3],0,1)*1023).astype(np.uint32)
    alpha=np.rint(np.clip(a[...,3],0,1)*3).astype(np.uint32)
    return np.ascontiguousarray(rgb[...,0]|(rgb[...,1]<<10)|(rgb[...,2]<<20)|(alpha<<30))
def unpack(a,fmt):
    if fmt in (2,10):return a.astype(np.float32)
    if fmt==28:return a.astype(np.float32)/255
    return np.stack([(a&1023)/1023,((a>>10)&1023)/1023,((a>>20)&1023)/1023,(a>>30)/3],-1).astype(np.float32)
def main(dll_path):
    dll=ctypes.CDLL(str(Path(dll_path).resolve()))
    dll.gpu_init.restype=ctypes.c_long
    hr=dll.gpu_init()
    if hr<0:raise RuntimeError(f'Hardware D3D11 device failed HRESULT {hr:#x}; no WARP fallback')
    dll.gpu_adapter.restype=ctypes.c_wchar_p
    adapter=dll.gpu_adapter()
    dll.gpu_run.restype=ctypes.c_long
    dll.gpu_run.argtypes=[ctypes.c_void_p]*3+[ctypes.c_int]*6+[ctypes.c_void_p,ctypes.c_size_t]*2+[ctypes.c_int]*3+[ctypes.c_float]
    calls=0
    def render(a,infmt=2,outfmt=2,contract=1,target=0,strength=1,bypass=0,enabled=1):
        nonlocal calls
        h,w,_=a.shape
        src=pack(a,infmt)
        dt,channels,bpp=FORMATS[outfmt]
        dst=np.empty((h,w,channels) if channels>1 else (h,w),dtype=dt)
        prefix=f'output_{w}x{h}_{enabled}'
        vs=(GEN/(prefix+'_F__OD_VS.dxbc')).read_bytes(); ps=(GEN/(prefix+'_F__OD_PS.dxbc')).read_bytes()
        hr=dll.gpu_run(src.ctypes.data,dst.ctypes.data,ASSET.ctypes.data,w,h,infmt,outfmt,FORMATS[infmt][2],bpp,vs,len(vs),ps,len(ps),bypass,contract,target,strength)
        calls+=1
        if hr<0:raise RuntimeError(f'gpu_run HRESULT {hr:#x}')
        return unpack(dst,outfmt),dst,src
    rows=[]; same_grid=[]
    for w,h in RESOLUTIONS:
        a=np.empty((h,w,4),np.float32)
        a[...,:3]=np.linspace(0,1,w,dtype=np.float32)[None,:,None]
        a[...,3]=np.linspace(0,1,w,dtype=np.float32)[None,:]
        for contract,target in ((1,0),(1,1),(2,2)):
            b,_,_=render(a,contract=contract,target=target)
            ref=reference(a,contract=contract,target=target)
            diff=float(np.max(abs(b-ref)))
            check(f'GPU precise input {w}x{h} {contract}/{target}',diff<=1.2e-7)
            check(f'GPU float alpha {w}x{h} {target}',bit_equal(b[...,3].copy(),a[...,3].copy()))
            rows.append(dict(width=w,height=h,contract=contract,target=target,max_abs_difference=diff))
        for fmt,target,contract in ((28,0,1),(24,1,1),(24,2,2)):
            _,dest,source=render(a,infmt=fmt,outfmt=fmt,target=target,contract=contract)
            delta=(unpack(dest,fmt)-unpack(source,fmt))*(255 if fmt==28 else 1023)
            same_grid.append(dict(width=w,height=h,format=fmt,contract=contract,target=target,
                changed_rgb_fraction=float(np.mean(abs(delta[...,:3])>.1)),delta_codes=stats(delta[...,:3])))
            check(f'GPU same UNORM grid changes bounded to adjacent codes {w}x{h} {contract}/{target}',np.max(abs(delta[...,:3]))<1.001)
            check(f'GPU UNORM alpha unchanged {w}x{h} {contract}/{target}',np.array_equal(unpack(dest,fmt)[...,3],unpack(source,fmt)[...,3]))
            if w==1920 and h==1080:
                for opts in (dict(bypass=1),dict(strength=0)):
                    _,passthrough,source=render(a,infmt=fmt,outfmt=fmt,target=target,contract=contract,**opts)
                    check(f'GPU exact UNORM pass-through {contract}/{target} {opts}',np.array_equal(passthrough,source))
        for kwargs in (dict(strength=0),dict(bypass=1),dict(contract=0),dict(contract=3),dict(contract=1,target=2),dict(enabled=0)):
            b,_,_=render(a,**kwargs)
            check(f'GPU exact float pass-through {w}x{h} {kwargs}',bit_equal(b,a))
    # Whole-frame constant tiles test quantizer thresholds without gradient phase confounds.
    constant=[]; w,h=1920,1080
    for L,fmt,target,contract in ((255,28,0,1),(1023,24,1,1),(1023,24,2,2)):
        for code in (.05,.25,.49,.5,.75,12.25,L-.25):
            a=np.full((h,w,4),code/L,np.float32); a[...,3]=1
            b,_,_=render(a,outfmt=fmt,contract=contract,target=target)
            expected=q(reference(a,contract=contract,target=target)[...,:3],L)
            delta=(b[...,:3]-expected)*L
            # Hardware UNORM tie handling and permitted conversion tolerance can
            # disagree at thresholds; report mismatch instead of hiding it.
            error=(b[...,:3]-a[...,:3])*L
            row=dict(levels=L,contract=contract,input_code=code,error=stats(error),cpu_code_mismatch_fraction=float(np.mean(abs(delta)>.1)))
            check(f'GPU constant mean bias bounded {L}/{contract}/{code}',abs(error.mean())<.1)
            check(f'GPU quantizer within one code CPU {L}/{contract}/{code}',np.max(abs(delta))<=1.001)
            constant.append(row)
    # Controlled high-precision inputs; distinguish immediate UNORM writes from
    # an encoded floating/10-bit intermediate followed by an IDEAL CPU quantizer.
    usefulness=[]; w,h=1920,1080
    for infmt,outfmt,target,contract,L,label in (
        (2,28,0,1,255,'FP32 to actual UNORM8'),
        (2,24,1,1,1023,'FP32 to actual UNORM10 sRGB'),
        (2,24,2,2,1023,'FP32 to actual UNORM10 PQ'),
        (10,10,0,1,255,'encoded FP16 to FP16 then ideal 8-bit'),
        (10,10,1,1,1023,'encoded FP16 to FP16 then ideal 10-bit'),
        (24,24,0,1,255,'sRGB UNORM10 to UNORM10 then ideal 8-bit')):
        a=np.empty((h,w,4),np.float32); a[...,3]=1
        a[...,:3]=(np.linspace(32,48,w,dtype=np.float32)/L)[None,:,None]
        plain,_,_=render(a,infmt=infmt,outfmt=outfmt,target=target,contract=contract,bypass=1)
        dither,_,_=render(a,infmt=infmt,outfmt=outfmt,target=target,contract=contract)
        if outfmt==10 or (outfmt==24 and L==255):
            plain=q(plain,L); dither=q(dither,L)
        e0=(plain[...,0]-a[...,0])*L; e1=(dither[...,0]-a[...,0])*L
        row=dict(path=label,plain_error=stats(e0),dither_error=stats(e1),
            plain_column_mean_rms=stats(e0.mean(0))['rms'],dither_column_mean_rms=stats(e1.mean(0))['rms'])
        check(f'GPU controlled gradient reduces column error: {label}',row['dither_column_mean_rms']<row['plain_column_mean_rms']*.3)
        usefulness.append(row)
    # Float32 and FP16 bypass: signed/extended scRGB, NaN, infinities, alpha.
    w,h=137,1
    a=np.full((h,w,4),.4,np.float32)
    vals=np.array([-0.,-1.,2.,65504.,-65504.,np.nan,np.inf,-np.inf,0.,1.],np.float32)
    a[0,:len(vals),0]=vals; a[0,:len(vals),3]=vals
    for fmt in (2,10):
        for kwargs in (dict(contract=3),dict(contract=0),dict(bypass=1),dict(strength=0),dict(enabled=0)):
            _,dst,src=render(a,infmt=fmt,outfmt=fmt,**kwargs)
            check(f'GPU signed extended invalid bypass fmt={fmt} {kwargs}',np.array_equal(dst.view(np.uint8),src.view(np.uint8)))
    b,_,_=render(a)
    check('GPU invalid RGB bypass whole pixel',bit_equal(b[0,1:8].copy(),a[0,1:8].copy()))
    check('GPU nonfinite alpha preserved',bit_equal(b[...,3].copy(),a[...,3].copy()))
    result=dict(adapter=adapter,api='D3D11 hardware FL11_0, offscreen, no presentation',draws=calls,
                checks_passed=len(checks),checks=checks,precise_input=rows,constant_quantization=constant,same_grid=same_grid,usefulness=usefulness,
                not_tested=['ReShade runtime execution','D3D9/10/12/Vulkan/OpenGL GPU execution','Windows composition','physical display link','in-game inspection'])
    (OUT/'gpu_results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(adapter=adapter,draws=calls,checks_passed=len(checks),max_error=max(r['max_abs_difference'] for r in rows)),indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dll',required=True)
    main(p.parse_args().dll)
