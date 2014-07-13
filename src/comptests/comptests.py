from .find_modules_imp import find_modules, find_modules_main
from .nose import jobs_nosetests
from conf_tools import GlobalConfig, import_name
from contracts import contract
from quickapp import QuickApp, iterate_context_names
import os
from .nose import jobs_nosetests_single


__all__ = [
    'CompTests', 
    'main_comptests',
]


class CompTests(QuickApp):
    """ 
        Runs the modules tests using compmake as a backend. 
        
    """ 

    cmd = 'comptests'
    
    hook_name = 'jobs_comptests'

    def define_options(self, params):
        params.add_string('exclude', default='', 
                          help='exclude these modules (comma separated)')
        # params.add_flag('nosetests', help='Use nosetests')
        params.accept_extra()
         
    def define_jobs_context(self, context):
        self.activate_dynamic_reports()

        GlobalConfig.global_load_dir('default')
        
        modules = self.get_modules()
        
        self.instance_nosetests_jobs(context, modules)
        #self.instance_nosesingle_jobs(context, modules)
        self.instance_comptests_jobs(context, modules)

    @contract(returns='list(str)')
    def get_modules(self):
        """" Parses the command line argument and interprets them as modules. """
        extras = self.options.get_extra()
        if not extras:
            raise ValueError('No modules given')

        modules = list(self.interpret_modules_names(extras))
        
        # only get the main ones
        is_first = lambda module_name: not '.' in module_name
        modules = filter(is_first, modules)
        
        excludes = self.options.exclude.split(',')
        to_exclude = lambda module_name: not module_name in excludes
        modules = filter(to_exclude, modules)
        return modules
    
    @contract(names='list(str)')
    def interpret_modules_names(self, names):
        """ yields a list of modules """ 
        for m in names:
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

    def instance_nosetests_jobs(self, context, modules):
        for c, module in iterate_context_names(context, modules):
            jobs_nosetests(c, module)
    
    def instance_nosesingle_jobs(self, context, modules):
        for c, module in iterate_context_names(context, modules):
            c.comp_dynamic(jobs_nosetests_single, module, job_id='nosesingle')
            
                    
    
    @contract(modules='list(str)')
    def instance_comptests_jobs(self, context, modules):
        for c, module in iterate_context_names(context, modules):
            c.add_extra_report_keys(module=module)
            c.comp_config_dynamic(instance_comptests_jobs2_m, module,
                                  job_id='comptests')



def instance_comptests_jobs2_m(context, module_name):
    is_first = not '.' in module_name
    warn_errors = is_first

    try:
        module = import_name(module_name)
    except ValueError as e:
        if warn_errors:
            print(e)  # 'Could not import %r: %s' % (module_name, e))
            raise Exception(e)
        return []
    
    fname = CompTests.hook_name
    
    if not fname in module.__dict__:
        msg = 'Module %s does not have function %s().' % (module_name, fname)
        if warn_errors:
            print(msg)
        return []

    ff = module.__dict__[fname]

    context.comp_config_dynamic(ff)


    
main_comptests = CompTests.get_sys_main()
