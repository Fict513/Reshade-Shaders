// Minimal Linux CLI around the OFFICIAL, unmodified ReShade FX front end.
// Build instructions in tools/README.md. No Windows driver compilation occurs.
#include "effect_parser.hpp"
#include "effect_codegen.hpp"
#include "effect_preprocessor.hpp"
#include <fstream>
#include <iostream>
#include <memory>
#include <string>
int main(int argc, char **argv) {
    if (argc < 4) return 64;
    reshadefx::preprocessor pp;
    pp.add_macro_definition("__RESHADE__", "60700");
    pp.add_macro_definition("__RENDERER__", "0xb000");
    pp.add_macro_definition("BUFFER_RCP_WIDTH", "(1.0/BUFFER_WIDTH)");
    pp.add_macro_definition("BUFFER_RCP_HEIGHT", "(1.0/BUFFER_HEIGHT)");
    pp.add_include_path(std::filesystem::path(argv[1]).parent_path());
    for (int i = 4; i < argc; ++i) {
        std::string d = argv[i]; auto at = d.find('=');
        pp.add_macro_definition(d.substr(0, at), d.substr(at + 1));
    }
    // ReShade retains the first definition: supplied dimensions precede defaults.
    pp.add_macro_definition("BUFFER_WIDTH", "3440");
    pp.add_macro_definition("BUFFER_HEIGHT", "1440");
    if (!pp.append_file(argv[1])) { std::cerr << pp.errors(); return 1; }
    std::unique_ptr<reshadefx::codegen> cg(
        std::string(argv[2]) == "glsl" ? reshadefx::create_codegen_glsl(false, false, false)
                                     : reshadefx::create_codegen_hlsl(50, false, false));
    reshadefx::parser parser;
    if (!parser.parse(pp.output(), cg.get())) {
        std::cerr << pp.errors() << parser.errors(); return 2;
    }
    std::ofstream(argv[3]) << cg->finalize_code();
    size_t passes = 0, textures = 0;
    for (auto &t : cg->module().techniques) passes += t.passes.size();
    for (auto &t : cg->module().textures) if (t.semantic.empty()) ++textures;
    std::cout << "passes=" << passes << " intermediate_textures=" << textures << '\n';
    for (auto &t : cg->module().textures) if (t.semantic.empty())
        std::cout << "texture_size=" << t.width << "x" << t.height << '\n';
    if (!parser.errors().empty()) std::cout << parser.errors();
}
