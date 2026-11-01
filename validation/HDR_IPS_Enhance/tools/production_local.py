"""CPU adapter for the extracted production LocalDelta function. Not GPU sampling.
Guide storage is float32. Nearest-even offsets and clamped point reads are emulated.
"""
import ctypes,re,subprocess,numpy as np
from production_float import ROOT,BUILD,SHIM
LIBS={}
def build(q):
    src=(ROOT/'Shaders/HDR_IPS_Enhance.fx').read_text()
    begin=src.index('float HDRIPS_LocalDelta(');end=src.index('\n#endif',begin)
    fn=src[begin:end].replace("[loop]", "")
    extra=r'''
float2 operator +(float2 a,float2 b){return float2(a.x+b.x,a.y+b.y);}
float2 operator /(float2 a,float2 b){return float2(a.x/b.x,a.y/b.y);}
float2 operator /(float2 a,float b){return float2(a.x/b,a.y/b);}
float2 operator /(float a,float2 b){return float2(a/b.x,a/b.y);}
float2 operator -(float a,float2 b){return float2(a-b.x,a-b.y);}
float2 operator *(float2 a,float b){return float2(a.x*b,a.y*b);}
float dot(float2 a,float2 b){return a.x*b.x+a.y*b.y;}
float2 round(float2 a){return float2(std::nearbyint(a.x),std::nearbyint(a.y));}
float2 clamp(float2 a,float2 lo,float2 hi){return float2(min(max(a.x,lo.x),hi.x),min(max(a.y,lo.y),hi.y));}
float clamp(float a,float lo,float hi){return min(max(a,lo),hi);}
float2 HDRIPS_Size;float LocalContrast=.5,LocalRadius=6;int HDRIPS_GuideSampler=0;
int W,H;const float *guide;
float3 tex2Dlod(int,float4 uv){int x=min(max(int(uv.xy.x*W),0),W-1),y=min(max(int(uv.xy.y*H),0),H-1);return float3(guide[y*W+x]);}
'''
    shim=SHIM.replace('float4(float3 v=', 'float4(float2 u,float z,float w):rgb(),a(w),xy(u){} float4(float3 v=')
    wrapper=r'''
extern "C" void runlocal(const float *y,const float *g,float *out,int w,int h,float radius){
W=w;H=h;guide=g;HDRIPS_Size=float2(w,h);LocalRadius=radius;
for(int j=0;j<h;j++)for(int i=0;i<w;i++)out[j*w+i]=HDRIPS_LocalDelta(float2((i+.5)/w,(j+.5)/h),y[j*w+i]);}
'''
    cpp=BUILD/f'local{q}.cpp';so=BUILD/f'local{q}.so'
    cpp.write_text(shim+f'\n#define HDRIPS_QUALITY {q}\n'+extra+fn+wrapper)
    subprocess.run(['g++','-std=c++17','-O2','-shared','-fPIC','-ffp-contract=off','-fsingle-precision-constant','-I',str(ROOT/'Shaders'),str(cpp),'-o',str(so)],check=True)
    lib=ctypes.CDLL(str(so));ptr=ctypes.POINTER(ctypes.c_float)
    lib.runlocal.argtypes=[ptr,ptr,ptr,ctypes.c_int,ctypes.c_int,ctypes.c_float]
    return lib

def execute(y,q=1,radius=6):
    if q not in LIBS:LIBS[q]=build(q)
    y=np.ascontiguousarray(y,dtype=np.float32)
    # Storage/guide generation is emulated; only the filter function is extracted.
    g=np.ascontiguousarray(np.log2(np.maximum(y,np.float32(.0001))),dtype=np.float32)
    out=np.empty_like(y);ptr=ctypes.POINTER(ctypes.c_float)
    LIBS[q].runlocal(y.ctypes.data_as(ptr),g.ctypes.data_as(ptr),out.ctypes.data_as(ptr),y.shape[1],y.shape[0],radius)
    return out
