import json,pathlib,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
import test_numerical,test_production_float
suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
result=unittest.TextTestRunner(verbosity=2).run(suite)
report={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'scope':'Production scalar/vector/Main/local bodies in CPU float adapters plus NumPy references. Not GPU execution.',
        'metrics':test_numerical.METRICS,'production_metrics':test_production_float.METRICS}
(ROOT/'validation/audit_numerical_results.json').write_text(json.dumps(report,indent=2)+'\n')
sys.exit(not result.wasSuccessful())
