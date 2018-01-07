from contextlib import contextmanager
import os
import tempfile


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

        fs = [
              'out-comptests/report.html',
              'out-comptests/report/reportclass1single/'
              'reportclass1single-c1a-checkclass1dynamic-examplepackage-exampleclass1.html',
              ]
#
#         if False:
#             # these are for reports
#             fs += ['out-comptests/report/single/single-checkclass1dynamic'
#                   '-examplepackage-exampleclass1.html',
#                   'out-comptests/report/reportclass1single/reportclass1single'
#                   '-checkclass1dynamic-c1a-examplepackage-exampleclass1.html',]

        errors = []
        for f in fs:
            fn = os.path.join(cwd, f)
            print('Testing %r' % f)
            if not os.path.exists(fn):
                errors.append(fn)

        if errors:
            msg = 'Files not found:\n' + '\n'.join(errors)
            raise Exception(msg)


@contextmanager
def create_tmp_dir():
    dirname = tempfile.mkdtemp()
    try:
        yield dirname
    except:
        raise

