extern "C" void run(const float *src,float *dst,int w,int h,int contract,int view,const float *params,int bilinearBits){
 width=w;height=h;input=src;linear_bits=bilinearBits;
 AD_Master=params[0];AD_Fine=params[1];AD_Detail=params[2];AD_Edge=params[3];AD_Noise=params[4];AD_Split=params[5];AD_Contract=contract;AD_View=view;
 luma.resize((size_t)w*h);
 for(int y=0;y<h;y++)for(int x=0;x<w;x++)luma[y*w+x]=AD_Prepare({},float2((x+0.5f)/w,(y+0.5f)/h));
 for(int y=0;y<h;y++)for(int x=0;x<w;x++){
  float4 v=AD_Apply({},float2((x+0.5f)/w,(y+0.5f)/h));float *p=dst+4*(y*w+x);p[0]=v.r;p[1]=v.g;p[2]=v.b;p[3]=v.a;
 }
}
extern "C" void transfer(const float *src,float *dst,int count,int op){
 for(int i=0;i<count;i++){
  float v=src[i];dst[i]=op==0?AD_SRGBDecode(v):op==1?AD_SRGBEncode(v):op==2?AD_PQDecodeNits(v):AD_PQEncodeNits(v);
 }
}
