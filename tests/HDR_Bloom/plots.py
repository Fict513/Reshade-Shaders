"""CPU evidence plots; not game screenshots or an HDR display preview."""
from pathlib import Path
import json,numpy as np,matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from reference import *
P=Path(__file__).resolve().parents[1];r=json.loads((P/'results/validation.json').read_text());e=json.loads((P/'results/extended_validation.json').read_text())
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(2,2,figsize=(11,7.5),layout='constrained')
y=np.linspace(0,800,1000);rgb=np.repeat(y[:,None],3,1)
ax[0,0].plot(y,extract(rgb,2,250,150)[:,0],color='#1468a0');ax[0,0].axvspan(175,325,color='#1468a0',alpha=.1)
ax[0,0].set(title='Continuous bright-pass: T=250, full knee=150',xlabel='Source luminance (nits)',ylabel='Extracted luminance (nits)')
st=r['moving_subpixel_source'];ax[0,1].plot([v['position'] for v in st],[v['extracted_Y_sum'] for v in st],label='Extracted sum')
ax[0,1].plot([v['position'] for v in st],[v['blurred_Y_sum'] for v in st],'--',label='Filtered sum');ax[0,1].legend()
ax[0,1].set(title='Constant-energy light moving across pixels',xlabel='Position (pixels)',ylabel='Summed source-unit luminance')
for q in range(3):
 x,w=kernel(q,3.014);ax[1,0].semilogy(x,w,label=['Normal','High','Ultra'][q])
ax[1,0].legend();ax[1,0].set(title='Same Gaussian; progressively longer tails',xlabel='Offset (level texels)',ylabel='Normalized weight',ylim=(1e-7,1))
x=np.geomspace(1e-6,.01,2048);codes=np.rint(encode(x,1)*255)/255
ax[1,1].semilogx(x,encode(x,1)*255,label='Unquantized');ax[1,1].semilogx(x,codes*255,label='Rounded to 8 bit');ax[1,1].legend()
ax[1,1].set(title='SDR tail: final encoded rounding still matters',xlabel='Linear reference-white fraction',ylabel='sRGB code value')
for a in ax.flat:a.grid(alpha=.15)
fig.suptitle('HDR Bloom — synthetic CPU validation',fontsize=16)
fig.savefig(P/'results/validation_plots.png',dpi=160)
plt.close(fig)
