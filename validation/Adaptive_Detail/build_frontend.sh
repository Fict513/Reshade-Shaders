#!/usr/bin/env bash
set -eu
# Usage: bash build_frontend.sh /path/to/reshade /path/to/output
src="$1/source"
g++ -std=c++17 -O2 -I"$src" "$(dirname "$0")/fx_frontend.cpp" \
 "$src/effect_lexer.cpp" "$src/effect_preprocessor.cpp" "$src/effect_expression.cpp" \
 "$src/effect_parser_exp.cpp" "$src/effect_parser_stmt.cpp" "$src/effect_symbol_table.cpp" \
 "$src/effect_codegen_hlsl.cpp" "$src/effect_codegen_glsl.cpp" -o "$2"
