from contextlib import contextmanager
import os
import tempfile
import warnings

from contracts import contract
from system_cmd import system_cmd_result

from compmake.utils import safe_pickle_load

__all__ = ['jobs_nosetests']


@contextmanager
def create_tmp_dir():
    # TODO: delete dir
    dirname = tempfile.mkdtemp()
    try:
        yield dirname
    except:
        raise


def jobs_nosetests(context, module, do_coverage=False):
    """ Instances the mcdp_lang_tests for the given module. """
    if do_coverage:
        try:
            import coverage  # @UnusedImport
        except ImportError as e:
            print('No coverage module found: %s' % e)
            context.comp(call_nosetests, module,
                         job_id='nosetests')
        else:
            covdata = context.comp(call_nosetests_plus_coverage, module,
                                   job_id='nosetests')
            if do_coverage:
                outdir = os.path.join(context.get_output_dir(), 'coverage')
                context.comp(write_coverage_report, outdir, covdata, module)
            else:
                warnings.warn('Skipping coverage report.')
    else:
        context.comp(call_nosetests, module,
                     job_id='nosetests')


def call_nosetests(module):
    with create_tmp_dir() as cwd:
        cmd = ['nosetests', module]
        system_cmd_result(
            cwd=cwd, cmd=cmd,
            display_stdout=True,
            display_stderr=True,
            raise_on_error=True)


def call_nosetests_plus_coverage(module):
    """
        This also calls the coverage module.
        It returns the .coverage file as a string.
    """
    with create_tmp_dir() as cwd:
        prog = find_command_path('nosetests')
        cmd = [prog, module]

        # note: coverage -> python-coverage in Ubuntu14
        cmd = ['coverage', 'run'] + cmd
        system_cmd_result(
            cwd=cwd, cmd=cmd,
            display_stdout=True,
            display_stderr=True,
            raise_on_error=True)
        coverage_file = os.path.join(cwd, '.coverage')
        with open(coverage_file) as f:
            res = f.read()
        #print('read %d bytes in %s' % (len(res), coverage_file))
        return res


def find_command_path(prog):
    res = system_cmd_result(cwd=os.getcwd(),
                             cmd=['which', prog],
                             display_stdout=False,
                            display_stderr=False,
                            raise_on_error=True)
    prog = res.stdout
    return prog


@contract(covdata='str')
def write_coverage_report(outdir, covdata, module):
    print('Writing coverage data to %s' % outdir)
    outdir = os.path.abspath(outdir)
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    with create_tmp_dir() as cwd:
        coverage_file = os.path.join(cwd, '.coverage')
        with open(coverage_file, 'wb') as f:
            f.write(covdata)

        cmd = ['coverage', 'html', '-d', outdir,
               '--include=*/%s/*' % module]
        res = system_cmd_result(
            cwd=cwd, cmd=cmd,
            display_stdout=True,
            display_stderr=True,
            raise_on_error=True)
        print(res.stdout)
        print(res.stderr)

        system_cmd_result(
            cwd=cwd, cmd=['find', '.'],
            display_stdout=True,
            display_stderr=True,
            raise_on_error=True)


def jobs_nosetests_single(context, module):

    with create_tmp_dir() as cwd:
        out = os.path.join(cwd, '%s.pickle' % module)
        cmd = ['nosetests',
               '--collect-only',
               '--with-xunitext',
               '--xunitext-file' ,
               out,
               '-v', '-s', module]
        system_cmd_result(
            cwd=cwd, cmd=cmd,
            display_stdout=True,
            display_stderr=True,
            raise_on_error=True)

        tests = safe_pickle_load(out)
        print('found %d mcdp_lang_tests ' % len(tests))

        for t in tests:
            context.comp(execute, t)


def execute(t):
    print(t)


if False:

    def load_nosetests(self, context, module_name):
#         argv = ['-vv', module_name]
        ids = '.noseids'
        if os.path.exists(ids):
            os.remove(ids)
#
#         collect = CollectOnly()
#         testid = TestId()
#         plugins = []
#         plugins.append(collect)
#         plugins.append(testid)
#         argv = ['nosetests', '--collect-only', '--with-id', module_name]
        argv = ['nosetests', '-s', '--nologcapture', module_name]

        class FakeResult():

            def wasSuccessful(self):
                return False

        class Tr(object):

            def run(self, what):
                self.what = what
                print(what)
                print('here!')
                return FakeResult()

        mytr = Tr()

        from nose.core import TestProgram
        from nose.suite import ContextSuite

        class MyTestProgram(TestProgram):

            def runTests(self):
                print('hello')

#         print argv, plugins
        tp = MyTestProgram(module=module_name, argv=argv,
                       defaultTest=module_name,
                       addplugins=[],
                       exit=False,
                       testRunner=mytr)
        self.info('test: %s' % tp.test)

        def explore(a):
            for b in a._get_tests():

                if isinstance(b, ContextSuite):
                    for c in explore(b):
                        yield c
                else:
                    yield b

        # these things are not pickable
        for a in explore(tp.test):
            #context.comp(run_testcase, a)
            pass
#
#             if isinstance(a, FunctionTestCase):
#                 f = a.test
#                 args = a.arg
#                 print('f: %s %s ' % (f, args))
#                 context.comp(f, *args)
#             else:
#                 print('unknown testcase %s' % describe_type(a))

# #
# #         print describe_value(tp.test, clip=100)
# #         suite = tp.test
#         for tc in suite.mcdp_lang_tests:
#             print describe_value(tc, clip=100)
#

#         res = nose.run(module=module_name, argv=argv,
#                        defaultTest=module_name,
#                        addplugins=plugins)

#         print 'res', res
#         print module_name
#         print testid
#         print collect
#
#         if not os.path.exists(ids):
#             msg = 'module %r did not produce mcdp_lang_tests' % module_name
#             raise Exception(msg)
#         d = safe_pickle_load(ids)
#         for k, v in d['ids'].items():
#             print describe_value(v)
#             print k
#             print v
#

# from nose.case import FunctionTestCase
# from nose.core import TestProgram
# from nose.plugins.collect import CollectOnly
# from nose.plugins.testid import TestId
# from nose.suite import ContextSuite
# import nose

