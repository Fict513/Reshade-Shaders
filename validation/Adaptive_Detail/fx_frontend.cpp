// Original harness; links unmodified official ReShade FX parser and code generators.
#include "effect_parser.hpp"
#include "effect_preprocessor.hpp"
#include "effect_codegen.hpp"
#include <fstream>
#include <iostream>
int main(int argc,char **argv) {
 if(argc<8) {std::cerr<<"source outprefix width height quality detail verified [format]\n";return 1;}
 reshadefx::preprocessor pp;
 pp.add_macro_definition("BUFFER_WIDTH",argv[3]); pp.add_macro_definition("BUFFER_HEIGHT",argv[4]);
 pp.add_macro_definition("BUFFER_RCP_WIDTH","(1.0 / BUFFER_WIDTH)"); pp.add_macro_definition("BUFFER_RCP_HEIGHT","(1.0 / BUFFER_HEIGHT)");
 pp.add_macro_definition("ADAPTIVE_DETAIL_QUALITY",argv[5]); pp.add_macro_definition("ADAPTIVE_DETAIL_ENABLE_DETAIL",argv[6]);
 pp.add_macro_definition("ADAPTIVE_DETAIL_VERIFIED_CONTRACT",argv[7]); pp.add_macro_definition("BUFFER_COLOR_FORMAT",argc>8?argv[8]:"10");
 if(!pp.append_file(argv[1])) {std::cerr<<pp.errors(); return 2;}
 for(int gl=0;gl<2;gl++) {
  std::unique_ptr<reshadefx::codegen> cg(gl?reshadefx::create_codegen_glsl(false,false,false,false,false):reshadefx::create_codegen_hlsl(50,false,false));
  reshadefx::parser parser;
  if(!parser.parse(pp.output(),cg.get())) {std::cerr<<parser.errors();return 3;}
  if(!parser.errors().empty()) std::cerr<<parser.errors();
  std::ofstream(std::string(argv[2])+(gl?".glsl":".hlsl"))<<cg->finalize_code();
  if(!gl) {
   std::ofstream meta(std::string(argv[2])+".meta");
   for(auto &t:cg->module().textures) meta<<"texture "<<t.name<<" "<<t.width<<" "<<t.height<<" format "<<int(t.format)<<" semantic "<<t.semantic<<"\n";
   for(auto &s:cg->module().samplers) meta<<"sampler "<<s.name<<" srgb "<<s.srgb<<"\n";
   for(auto &t:cg->module().techniques) for(auto &p:t.passes) meta<<"pass "<<p.name<<" srgb "<<p.srgb_write_enable<<" blend "<<p.blend_enable[0]<<"\n";
  }
 }
}
