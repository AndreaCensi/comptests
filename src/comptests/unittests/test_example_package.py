
from contextlib import contextmanager
import tempfile
import os

def test_example_package():
    from system_cmd import system_cmd_result

    # make sure it's installed
    import example_package  # @UnusedImport

    with create_tmp_dir() as cwd:
        print('Working in %r ' % cwd)
        cmd = ['comptests',
               '--contracts',
               #'--nonose', 
               'example_package']
        system_cmd_result(cwd, cmd, 
                          display_stdout=True,
                          display_stderr=True,
                          raise_on_error=True)
        
        fs = ['out-comptests/report/single/single-checkclass1dynamic'
              '-examplepackage-exampleclass1.html',
              'out-comptests/report/reportclass1single/reportclass1single'
              '-checkclass1dynamic-c1a-examplepackage-exampleclass1.html',
              'out-comptests/report.html'
              ]
    
        for f in fs:
            fn = os.path.join(cwd, f)
            print('Testing %r' % f)
            assert os.path.exists(fn)

@contextmanager
def create_tmp_dir():
    dirname = tempfile.mkdtemp()
    try:
        yield dirname
    except:
        raise


