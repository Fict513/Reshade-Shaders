"""Usage: python3 tools/check_baseline.py /path/to/original_v1.0.0.zip
Rebuild original bodies in a fresh temporary directory; no GPU execution.
"""
import pathlib,sys,tempfile,zipfile,shutil,subprocess,json,hashlib
ROOT=pathlib.Path(__file__).resolve().parents[1]
archive=pathlib.Path(sys.argv[1]).resolve()
with tempfile.TemporaryDirectory(prefix="hdrips_baseline_") as d:
    dst=pathlib.Path(d);(dst/'Shaders').mkdir();(dst/'tools').mkdir()
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if '/Shaders/' in name and name.endswith(('.fx','.fxh')):
                (dst/'Shaders'/pathlib.Path(name).name).write_bytes(z.read(name))
    shutil.copyfile(ROOT/'tools/production_float.py',dst/'tools/production_float.py')
    code="""import sys,json,numpy as np
from production_float import execute
sys.path.insert(0,sys.argv[1]);from reference import pq64
n=np.geomspace(80,1000,65536)
x=np.column_stack([np.repeat(pq64(n)[:,None],3,axis=1),np.ones(len(n))])
q=np.rint(execute(x,contrast=.22,color=0,master=.85)[:,0]*np.float32(1023)).astype(int)
large=np.array([[1e38,1e38,1e38,.8]],dtype=np.float32)
print(json.dumps(dict(highlight_10bit_reversals=int(np.sum(np.diff(q)<0)),extreme_finite_scrgb_output_all_finite=bool(np.isfinite(execute(large,mode=2)).all()))))
"""
    result=subprocess.run([sys.executable,'-c',code,str(ROOT/'tests')],cwd=dst/'tools',capture_output=True,text=True,check=True)
    report=json.loads(result.stdout)
    report['original_zip_sha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
    print(json.dumps(report,indent=2))
