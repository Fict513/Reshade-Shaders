#!/usr/bin/env python3
from pathlib import Path
import json,numpy as np
from reference import *
P=Path(__file__).resolve().parents[1];r={};checks=[]
def ck(name,ok,detail=None):checks.append({'test':name,'passed':bool(ok),'details':detail})
rng=np.random.default_rng(11440)
# Check production arithmetic order separately from the mathematical reference.
errors=[]
for h,w in [(1,1),(1,17),(19,1),(33,65),(1440,3440)]:
    a=(rng.random((h,w,1))*10000).astype(np.float32)
    ref=down(a.astype(np.float64));actual=production_down(a)
    errors.append({'size':[w,h],'max_nit_error':float(abs(actual-ref).max()),'mean_error':float(actual.mean(dtype=np.float64)-a.mean(dtype=np.float64))})
    ck(f'Production-area arithmetic {w}x{h}',abs(actual-ref).max()<.1)
r['production_area_arithmetic']=errors
errors=[]
for q in range(3):
 for spread in [.5,1,2]:
    a=rng.random((45,108,3)).astype(np.float32)*4000
    p=production_blur(a,q,spread,32,1440,3440);ref=blur(a.astype(np.float64),q,spread,32,1440,3440)
    errors.append({'quality':q,'spread':spread,'max_nit_error':float(abs(p-ref).max())})
    ck(f'Paired Gaussian versus independent integer taps {q,spread}',abs(p-ref).max()<.01)
r['paired_filter_arithmetic']=errors
# Cross-quality relative to a wider reference at the largest supported sigma.
# Discrete Gaussian tails added by higher quality must improve the approximation.
rows=[]
for sigma in [.75,1.5,3.014]:
    x=np.arange(-40,41);w=np.exp(-x*x/(2*sigma*sigma));w/=w.sum();errs=[]
    for q in range(3):
        xq,wq=kernel(q,sigma);base=np.zeros_like(w);base[(xq+40).astype(int)]=wq
        err=abs(base-w).sum();errs.append(err)
        rows.append({'sigma_texels':sigma,'quality':q,'kernel_L1_error':float(err),'variance':float(sum(wq*xq*xq))})
    ck(f'Quality monotonically improves Gaussian approximation sigma{sigma}',errs[2]<=errs[1]+1e-15 and errs[1]<=errs[0]+1e-15)
r['quality_vs_wide_reference']=rows
# Unit-energy bilinearly covered emitter, BEFORE nonlinear extraction.
flux=[];peak=[]
h,w=1440,256
for pos in np.linspace(100,102,17):
    a=np.zeros((h,w,1),np.float64);i=int(pos);f=pos-i;a[h//2,i]=10000*(1-f);a[h//2,i+1]=10000*f
    b=spatial(a);flux.append(float(b.sum()));peak.append(float(b.max()))
r['moving_extracted_light']={'flux_min':min(flux),'flux_max':max(flux),'peak_min':min(peak),'peak_max':max(peak),'peak_relative_range':float(np.ptp(peak)/np.mean(peak))}
ck('Prefiltered moving light maintains flux',np.ptp(flux)/10000<1e-8)
# Headroom, neutral/saturated/OOG patches and additive vs redistribution.
rows=[]
for mode,color,t,k in [(1,[1,1,1],.6,.3),(1,[1,0,0],.18,.24),(1,[0,1,0],.18,.24),(1,[0,0,1],.18,.24),(2,[1000,1000,1000],250,150),(2,[3000,0,0],250,150),(2,[0,0,10000],250,150),(3,[2000,-200,100],250,150)]:
    h,w=128,192;s=np.zeros((h,w,3),np.float64);s[60:68,92:100]=color;e=extract(s,mode,t,k);b=spatial(e);o,lim=compose(s,e,b,mode,.065)
    ys=(s@lw(mode)).sum();ye=(e@lw(mode)).sum();yo=(o@lw(mode)).sum();add=s+.065*b
    mask=np.any(s!=0,axis=2)
    rows.append({'mode':mode,'color':color,'source_Y_sum':float(ys),'extracted_Y_sum':float(ye),'redistribution_Y_sum':float(yo),'additive_Y_sum':float((add@lw(mode)).sum()),'core_max_before':float(s.max()),'core_max_after':float(o[mask].max()),'limiter_active_pixels':int((lim<1).sum()),'output_min_component':float(o.min())})
    ck(f'Color scenario finite {mode,color}',np.isfinite(o).all())
    # Isolated constant chromaticity source: all channels keep common linear
    # ratios across the image, absent limits. This is NOT a perceptual hue test.
    co=np.array(color);nonzero=np.flatnonzero(co)
    for ci in nonzero[1:]:
        a=o[...,ci]/co[ci];b0=o[...,nonzero[0]]/co[nonzero[0]]
        ck(f'Linear ratios isolated light {mode,color,ci}',np.max(abs(a-b0))<1e-10)
    if mode==3:ck('OOG spill keeps negative channel',o[...,1].min()<0)
r['compositing_and_colors']=rows
# Gradient through a real modeled bloom tail, then final rounding.
rows=[]
for mode,bits in [(1,8),(2,10)]:
    h,w=1440,256;s=np.full((h,w,3),.002 if mode==1 else .02);s[710:730,120:136]=1 if mode==1 else 1000
    e=extract(s,mode,.6 if mode==1 else 250,.3 if mode==1 else 150);b=spatial(e,q=1,spread=1.6);o,_=compose(s,e,b,mode,.065)
    codes=np.rint(encode(o,mode)*(2**bits-1));base=np.rint(encode(s,mode)*(2**bits-1))
    line=codes[720,136:,0];rows.append({'mode':mode,'bit_depth':bits,'tail_unique_codes':int(np.unique(line).size),'changed_pixel_fraction':float(np.mean(np.any(codes!=base,axis=2))),'rounded_tail_monotonic':bool(np.all(np.diff(line)<=0))})
    ck(f'Bloom tail actual {bits}-bit rounding finite and smooth-order',np.isfinite(codes).all() and np.all(np.diff(line)<=0))
r['quantized_bloom_tails']=rows
# Test every artistic preset values and intended contract from files.
import configparser
for f in sorted((P/'presets').glob('*.ini')):
    c=configparser.ConfigParser();c.read_string('[General]\n'+f.read_text());u=c['HDR_Bloom.fx'];m=int(u['InputMode'])
    a=rng.random((33,65,4)).astype(np.float32)
    if m==3:a[...,:3]*=20
    result=pipeline(a,m,float(u['Strength']),float(u['ThresholdSDR'] if m==1 else u['ThresholdNits']),float(u['KneeSDR'] if m==1 else u['KneeNits']),spread=float(u['Spread']))
    ck('Preset '+f.name,np.isfinite(result).all() and np.array_equal(result[...,3],a[...,3]))
r['checks']=checks;r['passed']=sum(x['passed'] for x in checks);r['failed']=sum(not x['passed'] for x in checks)
(P/'results/extended_validation.json').write_text(json.dumps(r,indent=2));print(json.dumps({'passed':r['passed'],'failed':r['failed']}));raise SystemExit(bool(r['failed']))
