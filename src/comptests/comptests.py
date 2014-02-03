import os
from os.path import dirname, join

from contracts import contract

from compmake.utils import describe_type
from conf_tools import GlobalConfig, import_name
from conf_tools.utils import locate_files
from quickapp import QuickApp


# from compmake.utils.describe import  describe_value
# from compmake.utils.safe_pickle import safe_pickle_load
# from nose.case import FunctionTestCase
# from nose.core import TestProgram
# from nose.plugins.collect import CollectOnly
# from nose.plugins.testid import TestId
# from nose.suite import ContextSuite
# import nose
__all__ = ['CompTests', 'main_comptests']


class CompTests(QuickApp):
    """ 
        Runs the modules tests using compmake as a backend. 
        
        
    """ 

    cmd = 'compmake-tests'

    function_name = 'get_comptests'

    def define_options(self, params):
        params.add_string('exclude', default='', help='exclude these modules (comma separated)')
        params.add_flag('nosetests', help='Use nosetests')
        params.add_flag('nocomptests', help='Do not use get_comptests()')
        params.accept_extra()
         
    def define_jobs_context(self, context):
        from .registrar import recipe_get_spec, recipe_instance_objects

        GlobalConfig.global_load_dir('default')
        recipe_instance_objects(context)
        recipe_get_spec(context)
        
        modules = list(self.interpret_extras_as_modules())
        # only get the main ones
        is_first = lambda module_name: not '.' in module_name
        modules = filter(is_first, modules)
        
        excludes = self.options.exclude.split(',')
        to_exclude = lambda module_name: not module_name in excludes
        modules = filter(to_exclude, modules)
        
        if self.options.nosetests:
            for m in modules:
                self.load_nosetests(context, m)
            
        self.try_importing_modules(modules)
        
        if not self.options.nocomptests:
            self.instance_comptests_jobs(context, modules)
      
    @contract(modules='list(str)')
    def instance_comptests_jobs(self, context, modules):
        apps = []
        names2m = {}
        for m in modules:
            # c = context.child(m)
            mapps = self.get_jobs_module(m)
            self.info('m apps: %s' % m)
            for a in mapps:
                id_app = a.__name__
                if id_app in names2m:
                    self.info('%s: App %s already used by %s' % 
                              (m, id_app, names2m[id_app]))
                else:
                    apps.append(a)
                    names2m[id_app] = m
        
        
        self.info('Found %d apps: %s' % (len(apps), apps))
        
        for a in apps:
            # print('Subtasking %r' % a)
            context.subtask(a)
            
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
                print what
                print('here!')
                return FakeResult()
        
        mytr = Tr()
        
        from nose.core import TestProgram
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
                from nose.suite import ContextSuite
                if isinstance(b, ContextSuite):
                    for c in explore(b):
                        yield c
                else:
                    yield b
        
        # these things are not pickable
        for a in explore(tp.test):
            context.comp(run_testcase, a)
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
#         for tc in suite.tests:
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
#             msg = 'module %r did not produce tests' % module_name
#             raise Exception(msg)
#         d = safe_pickle_load(ids)
#         for k, v in d['ids'].items():
#             print describe_value(v)
#             print k
#             print v
#         
    def try_importing_modules(self, modules):
        errors = []
        for m in modules:
            try:            
                import_name(m)
                self.debug('Imported %r' % m)
            except ValueError as e:
                self.error('Importing %r failed: %s' % (m, str(e)))
                errors.append((m, e))
                
        if errors:
            es = ['%s: %s' % (m, e) for e in errors]
            msg = 'Could not import modules:\n' + '\n'.join(es)
            self.error(msg)
            
      
    def interpret_extras_as_modules(self):
        """ yields a list of modules """ 
        extras = self.options.get_extra()
        if not extras:
            raise ValueError('No modules given')

        for m in extras:
            if os.path.exists(m):
                # if it's a path, look for 'setup.py' subdirs
                self.info('Interpreting %r as path.' % m)
                self.info('modules main: %s' % " ".join(find_modules_main(m)))
                modules = list(find_modules(m))
                if not modules:
                    self.warn('No modules found in %r' % m)
                
                for m in modules:
                    yield m
            else:
                self.info('Interpreting %r as module.' % m)
                yield m
                
    @contract(returns='seq')
    def get_jobs_module(self, module_name):
        """ Returns list of QuickApp subclasses """
        is_first = not '.' in module_name
        warn_errors = is_first
        
        try:            
            module = import_name(module_name)
        except ValueError as e:
            if warn_errors:
                self.error(e)  # 'Could not import %r: %s' % (module_name, e))
                raise Exception(e)
            return []
        
        f = CompTests.function_name
        if not f in module.__dict__:
            msg = 'Module %s does not have function %s().' % (module_name, f)
            if warn_errors: 
                self.warn(msg)
            return []
        
        ff = module.__dict__[f]
        apps = ff()
        if not isinstance(apps, list):
            msg = 'Unexpected value: %s' % describe_type(apps)
            raise Exception(msg)
        return apps
             

def find_modules_main(root):
    """ Finds the main modules (not '.' in the name) """
    is_main = lambda d: not '.' in d
    return filter(is_main, find_modules(root))

def find_modules(root):
    """ 
        Looks for modules defined in packages that have the structure: ::
        
            dirname/setup.py
            dirname/src/
            dirname/src/module/__init__.py
            dirname/src/module/module2/__init__.py
            
        This will yield ['module', 'module.module2']
    """ 
    setups = locate_files(root, 'setup.py')
    for s in setups:
        # look for '__init__.py'
        base = join(dirname(s), 'src')
        for i in locate_files(base, '__init__.py'):
            p = os.path.relpath(i, base)
            components = p.split('/')[:-1]  # remove __init__
            module = ".".join(components)
            yield module
            
def run_testcase(x):
    print(x)
    
main_comptests = CompTests.get_sys_main()
