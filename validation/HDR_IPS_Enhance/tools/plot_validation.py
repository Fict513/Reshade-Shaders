"""Generate numerical illustrations, not photographs or display measurements."""
import pathlib,sys,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from reference import scalar,pq64
y=np.geomspace(.001,2000,4000)
presets=[('Natural HDR',.70,.10,.85,.90),('IPS Depth HDR',.85,.22,.90,.90),
         ('Rich Color HDR',.80,.08,.85,.90)]
fig,axes=plt.subplots(1,2,figsize=(12,4.7),layout='constrained')
axes[0].loglog(y,y,color='.6',ls='--',label='Original')
for name,master,c,s,h in presets:
    output=y*(1-master)+scalar(2,y,c,100,s,h)*master
    axes[0].loglog(y,output,label=name)
    axes[1].semilogx(y,np.log2(output/y),label=name)
axes[0].set(xlabel='Source luminance (nits)',ylabel='Output luminance (nits)',title='Global stage only')
axes[1].axhline(0,color='.6',ls='--')
axes[1].set(xlabel='Source luminance (nits)',ylabel='Correction (stops)',title='Near-black and high highlights protected')
for a in axes:a.grid(alpha=.2);a.legend(fontsize=8)
fig.suptitle('CPU numerical illustration — not a measured display response',fontsize=13)
fig.savefig(ROOT/'validation/global_curves.png',dpi=150)
plt.close(fig)
