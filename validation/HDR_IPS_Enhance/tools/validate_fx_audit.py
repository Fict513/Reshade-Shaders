"""Check every quality/local/color/presentation variant with an official FX front end.
Usage: python3 tools/validate_fx_audit.py /absolute/path/to/fxcheck
"""
import itertools,json,pathlib,subprocess,sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
compiler=pathlib.Path(sys.argv[1]).resolve()
build=ROOT/'validation/build';build.mkdir(parents=True,exist_ok=True)
results=[]
for backend,q,local,color,cs in itertools.product(['hlsl','glsl'],range(3),range(2),range(2),range(5)):
    out=build/f'variant.{backend}'
    defs=[f'HDRIPS_QUALITY={q}',f'HDRIPS_ENABLE_LOCAL={local}',
          f'HDRIPS_ENABLE_COLOR={color}',f'BUFFER_COLOR_SPACE={cs}']
    p=subprocess.run([str(compiler),str(ROOT/'Shaders/HDR_IPS_Enhance.fx'),backend,str(out),*defs],
                     text=True,capture_output=True)
    expected=f'passes={1+local} intermediate_textures={local}'
    ok=p.returncode==0 and expected in p.stdout
    results.append(dict(backend=backend,quality=q,local=local,color=color,color_space=cs,
                        ok=ok,log=p.stdout+p.stderr))
    if not ok:print(results[-1]);sys.exit(1)
# Resolution defines are fed into the same parser; test tiny and nonstandard sizes too.
for width,height in [(1,1),(1,17),(19,1),(17,31),(1920,1080),(3440,1440),(5120,1440)]:
    p=subprocess.run([str(compiler),str(ROOT/'Shaders/HDR_IPS_Enhance.fx'),'hlsl',str(build/'resolution.hlsl'),
                      f'BUFFER_WIDTH={width}',f'BUFFER_HEIGHT={height}','BUFFER_COLOR_SPACE=2'],
                     text=True,capture_output=True)
    ok=p.returncode==0 and f"texture_size={width}x{height}" in p.stdout
    results.append(dict(resolution=[width,height],ok=ok,log=p.stdout+p.stderr))
    if not ok:print(results[-1]);sys.exit(1)
(ROOT/'validation/audit_fx_results.json').write_text(json.dumps(results,indent=2)+'\n')
print(f'{len(results)} FX parsing/code-generation configurations passed; no GPU compiler used.')
