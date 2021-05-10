import importlib
import inspect
import os
import tempfile
import warnings
from contextlib import contextmanager
from typing import cast

from system_cmd import system_cmd_result
from zuper_commons.fs import read_bytes_from_file, read_ustring_from_utf8_file
from zuper_commons.text import PythonModuleName, XMLString
from zuper_commons.types import ZValueError
from zuper_html.to_xml import tag_from_xml_str
from zuper_utils_asyncio import SyncTaskInterface
from zuper_utils_python.listing import get_modules_in_dir_detailed
from . import logger

__all__ = ["jobs_nosetests", "jobs_nosetests_single"]


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

            logger.info("Loaded coverage module")
        except ImportError as e:
            logger.info("No coverage module found: %s" % e)
            context.comp(call_nosetests, module, job_id="nosetests")
        else:
            covdata = context.comp(call_nosetests_plus_coverage, module, job_id="nosetests")
            if do_coverage:
                outdir = os.path.join(context.get_output_dir(), "coverage")
                context.comp(write_coverage_report, outdir, covdata, module)
            else:
                warnings.warn("Skipping coverage report.")
    else:
        context.comp(call_nosetests, module, job_id="nosetests")


def call_nosetests(module):
    with create_tmp_dir() as cwd:
        cmd = ["nosetests", module]
        system_cmd_result(
            cwd=cwd,
            cmd=cmd,
            display_stdout=True,
            display_stderr=True,
            raise_on_error=True,
        )


def call_nosetests_plus_coverage(module) -> bytes:
    """
    This also calls the coverage module.
    It returns the .coverage file as bytes.
    """
    with create_tmp_dir() as cwd:
        prog = find_command_path("nosetests")
        cmd = [prog, module]

        # note: coverage -> python-coverage in Ubuntu14
        cmd = ["coverage", "run"] + cmd
        system_cmd_result(
            cwd=cwd,
            cmd=cmd,
            display_stdout=True,
            display_stderr=True,
            raise_on_error=True,
        )
        coverage_file = os.path.join(cwd, ".coverage")
        res = read_bytes_from_file(coverage_file)
        # with open(coverage_file, 'rb') as f:
        #     res = f.read()
        # print('read %d bytes in %s' % (len(res), coverage_file))
        return res


def find_command_path(prog):
    res = system_cmd_result(
        cwd=os.getcwd(),
        cmd=["which", prog],
        display_stdout=False,
        display_stderr=False,
        raise_on_error=True,
    )
    prog = res.stdout
    return prog


def write_coverage_report(outdir, covdata: bytes, module):
    logger.info(f"Writing coverage data to {outdir}")
    outdir = os.path.abspath(outdir)
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    with create_tmp_dir() as cwd:
        coverage_file = os.path.join(cwd, ".coverage")
        with open(coverage_file, "wb") as f:
            f.write(covdata)

        logger.info("Running coverage html")
        cmd = ["coverage", "html", "-d", outdir, "--include=*/%s/*" % module]
        res = system_cmd_result(
            cwd=cwd,
            cmd=cmd,
            display_stdout=True,
            display_stderr=True,
            raise_on_error=True,
        )
        # print(res.stdout)
        # print(res.stderr)

        system_cmd_result(
            cwd=cwd,
            cmd=["find", "."],
            display_stdout=True,
            display_stderr=True,
            raise_on_error=True,
        )


def jobs_nosetests_single(context, module: str):
    assert "." not in module, module
    m = importlib.import_module(module)
    d = os.path.dirname(m.__file__)
    d0 = os.path.dirname(d)
    mods0 = get_modules_in_dir_detailed(d0)
    mods = {k for k in mods0 if k.startswith(f"{module}.")}

    # modules = {module+'.'+m: v for m,v in .items()}
    logger.info(module=module, modules=mods)

    def is_test(k, v):
        if hasattr(v, "__test__"):
            return bool(getattr(v, "__test__"))
        if not inspect.isfunction(v):
            logger.info(f"This is not a function:  {module}.{k}  {type(v)}")
            return False
        return "_test" in k or "test_" in k

    for test_module in mods:
        s = importlib.import_module(test_module)
        ks = {k: v for k, v in s.__dict__.items() if is_test(k, v)}

        logger.info(test_module=test_module, symbols=ks)

        for k, v in ks.items():
            job_id = f"{test_module}-{k}"
            context.comp(execute, module_name=test_module, func_name=k, job_id=job_id)

    return

    #
    # raise ZValueError(module=module, modules=mods, mods=mods0)
    #
    # with create_tmp_dir() as cwd:
    #     out = os.path.join(cwd, f"{module}.pickle")
    #     cmd = [
    #         "nosetests",
    #         "--collect-only",
    #         # "--with-xunitext",
    #         # "--xunitext-file",
    #         "--with-xunit",
    #         "--xunit-file",
    #         out,
    #         "-v",
    #         "-s",
    #         module,
    #     ]
    #     system_cmd_result(
    #         cwd=cwd,
    #         cmd=cmd,
    #         display_stdout=True,
    #         display_stderr=True,
    #         raise_on_error=True,
    #     )
    #
    #     contents = read_ustring_from_utf8_file(out)
    #     tag = tag_from_xml_str(cast(XMLString, contents))
    #     # logger.info(f"the a tag {tag}", tag=tag)
    #     # print(str(tag))
    #
    #     for child in tag.contents:
    #         assert child.tagname == "testcase"
    #         classname = child.attrs["classname"]
    #         name = child.attrs["name"]
    #         module_name, _, func_name = classname.rpartition(".")
    #         context.comp(execute, module_name=module_name, func_name=func_name, job_id=name)
    #
    #     # tests = safe_pickle_load(out)
    #     # logger.info(f"found {len(tests):d} tests from nose ")
    #     #
    #     # for t in tests:
    #     #


async def execute(sti: SyncTaskInterface, module_name: PythonModuleName, func_name: str):
    f = importlib.import_module(module_name)
    ff = getattr(f, func_name)

    logger.info(func_name=func_name, ff=ff, attrs=ff.__dict__)
    print(f"{func_name} {ff} {ff.__dict__}")
    if hasattr(ff, "__original__"):
        orig = getattr(ff, "__original__")
        print('calling "orig"')

        t = await sti.create_child_task2(func_name, orig)
        await t.wait_for_outcome_success()

    else:
        return ff()


#
# if False:
#
#     def load_nosetests(self, context, module_name):
#         #         argv = ['-vv', module_name]
#         ids = ".noseids"
#         if os.path.exists(ids):
#             os.remove(ids)
#         #
#         #         collect = CollectOnly()
#         #         testid = TestId()
#         #         plugins = []
#         #         plugins.append(collect)
#         #         plugins.append(testid)
#         #         argv = ['nosetests', '--collect-only', '--with-id', module_name]
#         argv = ["nosetests", "-s", "--nologcapture", module_name]
#
#         class FakeResult:
#             def wasSuccessful(self):
#                 return False
#
#         class Tr(object):
#             def run(self, what):
#                 self.what = what
#                 print(what)
#                 print("here!")
#                 return FakeResult()
#
#         mytr = Tr()
#
#         from nose.core import TestProgram
#         from nose.suite import ContextSuite
#
#         class MyTestProgram(TestProgram):
#             def runTests(self):
#                 print("hello")
#
#         #         print argv, plugins
#         tp = MyTestProgram(
#             module=module_name,
#             argv=argv,
#             defaultTest=module_name,
#             addplugins=[],
#             exit=False,
#             testRunner=mytr,
#         )
#         self.info("test: %s" % tp.test)
#
#         def explore(a):
#             for b in a._get_tests():
#
#                 if isinstance(b, ContextSuite):
#                     for c in explore(b):
#                         yield c
#                 else:
#                     yield b
#
#         # these things are not pickable
#         for a in explore(tp.test):
#             # context.comp(run_testcase, a)
#             pass


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
