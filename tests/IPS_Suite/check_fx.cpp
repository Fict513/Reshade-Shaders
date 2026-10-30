// ReShade FX parse/module/code-generation checks, not GPU compilation.
#include "effect_preprocessor.hpp"
#include "effect_parser.hpp"
#include "effect_codegen.hpp"
#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <set>
#include <sstream>
#include <stdexcept>
#include <vector>

static void check(const char *path, int quality, int flags, int space, int depth,
                  int width, int height, bool glsl)
{
    const bool contrast = flags & 1, deband = flags & 2, clarity = flags & 4;
    reshadefx::preprocessor pp;
    pp.add_include_path(std::filesystem::path(path).parent_path());
    pp.add_macro_definition("BUFFER_WIDTH", std::to_string(width));
    pp.add_macro_definition("BUFFER_HEIGHT", std::to_string(height));
    pp.add_macro_definition("BUFFER_RCP_WIDTH", "(1.0 / " + std::to_string(width) + ".0)");
    pp.add_macro_definition("BUFFER_RCP_HEIGHT", "(1.0 / " + std::to_string(height) + ".0)");
    if (space >= 0) pp.add_macro_definition("BUFFER_COLOR_SPACE", std::to_string(space));
    if (depth >= 0) pp.add_macro_definition("BUFFER_COLOR_BIT_DEPTH", std::to_string(depth));
    pp.add_macro_definition("IPS_SUITE_QUALITY", std::to_string(quality));
    pp.add_macro_definition("IPS_SUITE_CONTRAST", contrast ? "1" : "0");
    pp.add_macro_definition("IPS_SUITE_DEBAND", deband ? "1" : "0");
    pp.add_macro_definition("IPS_SUITE_CLARITY", clarity ? "1" : "0");
    pp.add_macro_definition("IPS_SUITE_DITHER", flags & 8 ? "1" : "0");
    if (!pp.append_file(path)) throw std::runtime_error(pp.errors());
    std::unique_ptr<reshadefx::codegen> cg(glsl ?
        reshadefx::create_codegen_glsl(true, false, false) :
        reshadefx::create_codegen_hlsl(50, false, false));
    reshadefx::parser parser;
    if (!parser.parse(pp.output(), cg.get())) throw std::runtime_error(parser.errors());
    if (!parser.errors().empty()) throw std::runtime_error("Unexpected warning: " + parser.errors());
    const auto &m = cg->module();
    std::vector<std::string> passes;
    std::map<std::string, std::array<int, 3>> textures;
    if (space <= 1) {
        if (contrast) {
            passes = {"ContrastLuma", "ContrastFineX", "ContrastFineY",
                      "ContrastBroadPrepare", "ContrastBroadX", "ContrastBroadY"};
            textures["LumaTexture"] = {width, height, 2};
            textures["FineXTexture"] = {width, height, 4};
            textures["FineYTexture"] = {width, height, 2};
            for (const char *name : {"BroadPrepTexture", "BroadXTexture", "BroadYTexture"})
                textures[name] = {(width + 1) / 2, (height + 1) / 2, 8};
            if (deband || clarity) {
                passes.push_back("ContrastOutput");
                textures["ContrastTexture"] = {width, height, 16};
            }
        }
        if (deband && clarity) {
            passes.push_back("DebandOutput");
            textures["DebandTexture"] = {width, height, 16};
        }
        if (clarity) {
            passes.push_back("ClarityGuide");
            textures["GuideTexture"] = {width, height, 4};
        }
    }
    passes.push_back("Output");
    if (m.techniques.size() != 1 || m.techniques[0].name != "IPS_Suite" ||
        m.techniques[0].passes.size() != passes.size())
        throw std::runtime_error("Unexpected technique/pass count");
    const std::map<std::string, std::string> target = {
        {"ContrastLuma", "LumaTexture"}, {"ContrastFineX", "FineXTexture"},
        {"ContrastFineY", "FineYTexture"}, {"ContrastBroadPrepare", "BroadPrepTexture"},
        {"ContrastBroadX", "BroadXTexture"}, {"ContrastBroadY", "BroadYTexture"},
        {"ContrastOutput", "ContrastTexture"}, {"DebandOutput", "DebandTexture"},
        {"ClarityGuide", "GuideTexture"}
    };
    for (size_t i = 0; i < passes.size(); ++i) {
        const auto &pass = m.techniques[0].passes[i];
        if (pass.name != passes[i]) throw std::runtime_error("Unexpected pass order: " + pass.name);
        if ((i + 1 == passes.size()) != pass.render_target_names[0].empty())
            throw std::runtime_error("Only final pass may write the back buffer");
        if (i + 1 != passes.size()) {
            bool matches = false;
            for (const auto &t : m.textures)
                matches |= t.name == target.at(pass.name) && t.unique_name == pass.render_target_names[0];
            if (!matches) throw std::runtime_error("Wrong output for pass " + pass.name);
        }
        std::string required;
        if (pass.name == "ContrastLuma" || pass.name == "ContrastOutput") required = "OriginalTexture";
        else if (pass.name == "ContrastFineX") required = "LumaTexture";
        else if (pass.name == "ContrastFineY") required = "FineXTexture";
        else if (pass.name == "ContrastBroadPrepare") required = "FineYTexture";
        else if (pass.name == "ContrastBroadX") required = "BroadPrepTexture";
        else if (pass.name == "ContrastBroadY") required = "BroadXTexture";
        else if (pass.name == "DebandOutput") required = contrast ? "ContrastTexture" : "OriginalTexture";
        else if (pass.name == "ClarityGuide") required = deband ? "DebandTexture" :
                                                         contrast ? "ContrastTexture" : "OriginalTexture";
        else if (pass.name == "Output") required = "OriginalTexture";
        const auto reads = [&](const std::string &name) {
            for (const auto &binding : pass.texture_bindings) {
                const auto &sampler = m.samplers.at(binding.index);
                for (const auto &t : m.textures)
                    if (t.name == name && t.unique_name == sampler.texture_name) return true;
            }
            return false;
        };
        if (!reads(required)) throw std::runtime_error("Pass " + pass.name + " does not read " + required);
        if (space <= 1 && pass.name == "Output") {
            if (clarity && (!reads("GuideTexture") ||
                !reads(deband ? "DebandTexture" : contrast ? "ContrastTexture" : "OriginalTexture")))
                throw std::runtime_error("Final clarity reads stale/missing guide or image");
            if (!clarity && deband && !reads(contrast ? "ContrastTexture" : "OriginalTexture"))
                throw std::runtime_error("Final deband reads stale/missing image");
        }
    }
    size_t bytes = 0, count = 0;
    for (const auto &t : m.textures) {
        if (!t.semantic.empty()) continue;
        auto it = textures.find(t.name);
        if (it == textures.end()) throw std::runtime_error("Unexpected texture: " + t.name);
        int bpp = t.format == reshadefx::texture_format::r16f ? 2 :
                  t.format == reshadefx::texture_format::rg16f ? 4 :
                  t.format == reshadefx::texture_format::rgba16f ? 8 :
                  t.format == reshadefx::texture_format::r32f ? 4 :
                  t.format == reshadefx::texture_format::rgba32f ? 16 : 0;
        if (int(t.width) != it->second[0] || int(t.height) != it->second[1] ||
            bpp != it->second[2]) throw std::runtime_error("Wrong texture format/size: " + t.name);
        bytes += size_t(t.width) * t.height * bpp;
        ++count;
    }
    if (count != textures.size()) throw std::runtime_error("Missing or duplicate intermediate texture");
    std::set<std::string> uniforms;
    for (const auto &u : m.uniforms)
        if (!uniforms.insert(u.name).second) throw std::runtime_error("Duplicate preset uniform " + u.name);
    if (space <= 1) {
        if (uniforms.count("ContrastStrength") != size_t(contrast) ||
            uniforms.count("DebandStrength") != size_t(deband) ||
            uniforms.count("ClarityStrength") != size_t(clarity) ||
            uniforms.count("OutputDither") != size_t(deband && (flags & 8)))
            throw std::runtime_error("Disabled stage retained uniforms or enabled stage missing uniforms");
    }
    if (space == 1 && flags == 15 && depth == 8 && width == 3440 && height == 1440 && !glsl) {
        for (const char *style : {"Balanced", "RTX_Companion"}) {
            const char *tier = quality == 0 ? "Normal" : quality == 1 ? "High" : "Ultra";
            auto preset = std::filesystem::path(path).parent_path().parent_path() / "Presets" /
                          "IPS_Suite" / (std::string("IPS_Suite_") + style + "_" + tier + ".ini");
            std::ifstream file(preset);
            if (!file) throw std::runtime_error("Missing preset: " + preset.string());
            std::string line;
            bool section = false, technique = false, definition = false;
            std::set<std::string> keys;
            while (std::getline(file, line)) {
                if (line == "[IPS_Suite.fx]") { section = true; continue; }
                if (line.rfind("Techniques=IPS_Suite@IPS_Suite.fx", 0) == 0) technique = true;
                if (line.rfind("PreprocessorDefinitions=IPS_SUITE_QUALITY=" + std::to_string(quality) + ",", 0) == 0)
                    definition = true;
                if (section && !line.empty()) {
                    auto pos = line.find('=');
                    if (pos == std::string::npos) throw std::runtime_error("Invalid preset line");
                    keys.insert(line.substr(0, pos));
                }
            }
            if (!technique || !definition || keys != uniforms)
                throw std::runtime_error("Preset technique, quality or uniform keys do not match parsed effect: " + preset.string());
        }
    }
    if (cg->finalize_code().empty()) throw std::runtime_error("Empty generated module");
    for (const auto &e : m.entry_points) {
        std::string code, assembly, errors;
        if (!cg->assemble_code_for_entry_point(e.first, code, assembly, errors) || code.empty())
            throw std::runtime_error("Entry-point generation failed: " + errors);
    }
    if (!glsl && quality == 1 && flags < 8 && space == 1 && depth == 8 &&
        width == 3440 && height == 1440)
        std::cout << "stages=" << flags << " passes=" << passes.size() << " bytes=" << bytes << '\n';
}

int main(int argc, char **argv)
{
    if (argc != 2) { std::cerr << "Usage: check_fx /absolute/path/IPS_Suite.fx\n"; return 1; }
    int count = 0;
    try {
        for (bool glsl : {false, true}) {
            for (int q = 0; q < 3; ++q)
                for (int flags = 0; flags < 16; ++flags) {
                    check(argv[1], q, flags, 1, 8, 3440, 1440, glsl); ++count;
                }
            for (int q = 0; q < 3; ++q) {
                for (int space : {-1, 0, 2, 3, 4}) {
                    check(argv[1], q, 15, space, 8, 3440, 1440, glsl); ++count;
                }
                for (int depth : {-1, 10, 12, 16}) {
                    check(argv[1], q, 15, 1, depth, 3440, 1440, glsl); ++count;
                }
                for (auto size : {std::array<int, 2>{1, 1}, {5, 3}, {3441, 1441}}) {
                    check(argv[1], q, 15, 1, 8, size[0], size[1], glsl); ++count;
                }
            }
        }
        std::cout << "PASS " << count << " FX parse/module/HLSL SM5 + GLSL entry-point generation configurations.\n"
                  << "Not GPU-driver compilation or runtime execution.\n";
    } catch (const std::exception &e) { std::cerr << e.what() << '\n'; return 2; }
}
