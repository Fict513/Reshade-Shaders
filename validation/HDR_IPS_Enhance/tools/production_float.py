"""Extract production FX functions into a CPU float adapter; NOT GPU execution.
Local gathers are excluded; vector ops, diagnostics and Main execute production bodies.
"""
import pathlib,re,subprocess,ctypes,numpy as np
ROOT=pathlib.Path(__file__).resolve().parents[1]
BUILD=ROOT/'validation/build';BUILD.mkdir(parents=True,exist_ok=True)
SHIM=r'''
#include <cmath>
#include <algorithm>
using std::isnan;using std::isinf;using std::isnan;using std::isinf;using std::min;using std::max;using std::pow;using std::exp2;using std::log2;using std::abs;
struct bool3{bool x,y,z;};
bool all(bool3 v){return v.x&&v.y&&v.z;} bool any(bool3 v){return v.x||v.y||v.z;}
struct float2{float x,y;float2(float a=0,float b=0):x(a),y(b){}};
struct int2{int x,y;int2(float2 v):x(int(v.x)),y(int(v.y)){} };
struct float3{union{struct{float x,y,z;};struct{float r,g,b;};};float3(float a=0):x(a),y(a),z(a){} float3(float a,float b,float c):x(a),y(b),z(c){} };
struct float4{float3 rgb;float a;float2 xy;float4(float3 v=float3(),float w=0):rgb(v),a(w),xy(v.x,v.y){} };
#define OP(o) float3 operator o(float3 a,float3 b){return float3(a.x o b.x,a.y o b.y,a.z o b.z);}
OP(+) OP(-) OP(*) OP(/)
#define CMP(o) bool3 operator o(float3 a,float3 b){return {a.x o b.x,a.y o b.y,a.z o b.z};}
CMP(==) CMP(>=) CMP(<=)
bool3 isnan(float3 v){return {std::isnan(v.x),std::isnan(v.y),std::isnan(v.z)};}
bool3 isinf(float3 v){return {std::isinf(v.x),std::isinf(v.y),std::isinf(v.z)};}
float dot(float3 a,float3 b){return (a.x*b.x+a.y*b.y)+a.z*b.z;}
float saturate(float x){return min(max(x,0.f),1.f);}
float smoothstep(float a,float b,float x){float t=saturate((x-a)/(b-a));return t*t*(3-2*t);}
float3 lerp(float3 a,float3 b,float t){return a+(b-a)*t;}
float4 current;int HDRIPS_SourceSampler=0;
float4 tex2Dfetch(int,int2,int){return current;}
int InputColorSpace=1,DiagnosticView=0;bool AutoContractVerified=false;
float MasterStrength=.75,GlobalContrast=.12,MidtoneAnchor=100,ShadowProtection=.8,HighlightProtection=.85;
float ColorEnhancement=.06,SaturationProtection=.85,SplitPosition=.5;
const float3 HDRIPS_Y2020(.2627,.678,.0593);
#define HDRIPS_ENABLE_LOCAL 0
#define HDRIPS_ENABLE_COLOR 1
#define BUFFER_COLOR_SPACE 3
#include "HDRIPS_Math.fxh"
'''
def build(source=None):
    source=source or ROOT/'Shaders/HDR_IPS_Enhance.fx'
    text=source.read_text();functions=[]
    for m in re.finditer(r'^(?:int|bool|float|float3|float4) (HDRIPS_\w+)\([^;]*?\)\s*(?:: SV_Target)?\s*\{',text,re.M):
        if m[1] in ['HDRIPS_Prepare','HDRIPS_LocalDelta']:continue
        start=m.start();i=m.end();depth=1
        while depth:
            depth+=(text[i]=='{')-(text[i]=='}');i+=1
        fn=text[start:i];fn=re.sub(r'\s*: (?:SV_Position|TEXCOORD|SV_Target)','',fn)
        fn=fn.replace('out float compression','float &compression')
        functions.append(fn)
    wrapper=r'''
extern "C" void execute(const float *src,float *dst,int n,int mode,int diag,float master,float contrast,float color){
InputColorSpace=mode;DiagnosticView=diag;MasterStrength=master;GlobalContrast=contrast;ColorEnhancement=color;
for(int i=0;i<n;i++){current=float4(float3(src[4*i],src[4*i+1],src[4*i+2]),src[4*i+3]);
float4 v=HDRIPS_Main(float4(),float2(.75,.5));dst[4*i]=v.rgb.r;dst[4*i+1]=v.rgb.g;dst[4*i+2]=v.rgb.b;dst[4*i+3]=v.a;}}
'''
    cpp=BUILD/'production.cpp';so=BUILD/'production.so';cpp.write_text(SHIM+'\n'.join(functions)+wrapper)
    subprocess.run(['g++','-std=c++17','-O2','-shared','-fPIC','-ffp-contract=off','-fsingle-precision-constant','-I',str(ROOT/'Shaders'),str(cpp),'-o',str(so)],check=True)
    lib=ctypes.CDLL(str(so));ptr=ctypes.POINTER(ctypes.c_float)
    lib.execute.argtypes=[ptr,ptr,ctypes.c_int,ctypes.c_int,ctypes.c_int]+[ctypes.c_float]*3
    return lib
LIB=None
def execute(x,mode=1,diag=0,master=.75,contrast=.12,color=.06):
    global LIB
    if LIB is None:LIB=build()
    x=np.ascontiguousarray(x,dtype=np.float32);out=np.empty_like(x);ptr=ctypes.POINTER(ctypes.c_float)
    LIB.execute(x.ctypes.data_as(ptr),out.ctypes.data_as(ptr),x.size//4,mode,diag,master,contrast,color)
    return out
if __name__=='__main__':
    x=np.array([[.5,.5,.5,.7],[1e38,1e38,1e38,.8]],dtype=np.float32)
    print(execute(x,mode=2))
