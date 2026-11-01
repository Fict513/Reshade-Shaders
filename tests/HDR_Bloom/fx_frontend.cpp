// Harness around the unmodified official ReShade FX preprocessor/parser.
#include "effect_preprocessor.hpp"
#include "effect_parser.hpp"
#include "effect_codegen.hpp"
#include <iostream>
#include <fstream>
#include <memory>
int main(int argc,char**argv){
 if(argc<8) return 2;
 reshadefx::preprocessor pp;
 pp.add_macro_definition("BUFFER_WIDTH",argv[2]);
 pp.add_macro_definition("BUFFER_HEIGHT",argv[3]);
 pp.add_macro_definition("HDRBLOOM_QUALITY",argv[4]);
 pp.add_macro_definition("HDRBLOOM_DIAGNOSTICS",argv[5]);
 pp.add_macro_definition("HDRBLOOM_AUTO_CONTRACT",argv[6]);
 pp.add_macro_definition("__RENDERER__","0xb000");
 if(!pp.append_file(argv[1])){std::cerr<<pp.errors();return 1;}
 std::unique_ptr<reshadefx::codegen> cg(argv[7][0]=='g' ? reshadefx::create_codegen_glsl(false,false,false) : reshadefx::create_codegen_hlsl(50,false,false));
 reshadefx::parser p;
 bool ok=p.parse(pp.output(),cg.get());
 std::cerr<<p.errors(); if(!ok)return 1;
 auto &m=cg->module();
 std::cout<<"{\"textures\":[";
 bool first=true;for(auto &t:m.textures){if(!first)std::cout<<",";first=false;std::cout<<"{\"name\":\""<<t.unique_name<<"\",\"width\":"<<t.width<<",\"height\":"<<t.height<<",\"format\":"<<int(t.format)<<"}";}
 std::cout<<"],\"passes\":"<<m.techniques[0].passes.size()<<",\"entries\":"<<m.entry_points.size()<<"}\n";
 if(argc>8)std::ofstream(argv[8])<<cg->finalize_code();
 return 0;
}
