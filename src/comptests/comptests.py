import os

from conf_tools import GlobalConfig, import_name, reset_config
from quickapp import QuickApp
from quickapp import logger

from contracts import contract
from contracts.utils import raise_desc

from .find_modules_imp import find_modules, find_modules_main
from .nose import jobs_nosetests, jobs_nosetests_single


__all__ = [
    'CompTests',
    'main_comptests',
]

def get_comptests_output_dir():
    """ when run from the comptests executable, returns the output dir. """
    if CompTests.global_output_dir is None:
        x = 'out/comptests/build'
        msg = 'No comptests output dir set. Returning %s' % x
        logger.warn(msg)
        return x
    
    return CompTests.global_output_dir

class CompTests(QuickApp):
    """
        Runs the unit tests defined as @comptests.

    """
    
    global_output_dir = None

    cmd = 'comptests'

    hook_name = 'jobs_comptests'

    def define_options(self, params):
        params.add_string('exclude', default='',
                          help='exclude these modules (comma separated)')

        params.add_flag('nonose', help='Disable nosetests')
        params.add_flag('coverage', help='Enable coverage module')
        params.add_flag('nocomp', help='Disable comptests hooks')

        params.add_flag('reports', help='Create reports jobs')

        params.accept_extra()

    def define_jobs_context(self, context):
        
        CompTests.global_output_dir = self.get_options().output
        
        
        GlobalConfig.global_load_dir('default')

        modules = self.get_modules()

        if not modules:
            raise Exception('No modules found.') # XXX: what's the nicer way?

        options = self.get_options()
        if not options.nonose:
            do_coverage = options.coverage
            self.instance_nosetests_jobs(context, modules, do_coverage)

        #self.instance_nosesingle_jobs(context, modules)

        if not options.nocomp:
            self.instance_comptests_jobs(context, modules,
                                         create_reports=options.reports)

    @contract(returns='list(str)')
    def get_modules(self):
        """" Parses the command line argument and interprets them as modules. """
        extras = self.options.get_extra()
        if not extras:
            raise ValueError('No modules given')

        modules = list(self.interpret_modules_names(extras))
        if not modules:
            msg = 'No modules given'
            raise_desc(ValueError, msg, extras=extras)
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
        # First, extract tokens
        names2 = []
        for m in names:
            names2.extend(m.split(','))
            
        for m in names2:
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

    def instance_nosetests_jobs(self, context, modules, do_coverage):
        for module in modules:
            c = context.child(module)
            jobs_nosetests(c, module, do_coverage = do_coverage)

    def instance_nosesingle_jobs(self, context, modules):
        for module in modules:
            c = context.child(module)
            c.comp_dynamic(jobs_nosetests_single, module, job_id='nosesingle')


    @contract(modules='list(str)', create_reports='bool')
    def instance_comptests_jobs(self, context, modules, create_reports):

        for module in modules:

            if True:
                c = context.child(module)
            else:
                c = context.child("")

            c.add_extra_report_keys(module=module)
            c.comp_config_dynamic(instance_comptests_jobs2_m, module_name=module,
                                  create_reports=create_reports,
                                  job_id='comptests')

def instance_comptests_jobs2_m(context, module_name, create_reports):
    is_first = not '.' in module_name
    warn_errors = is_first

    try:
        module = import_name(module_name)
    except ValueError as e:
        if warn_errors:
            logger.debug(e)  # 'Could not import %r: %s' % (module_name, e))
            raise Exception(e)
        return []

    fname = CompTests.hook_name

    if not fname in module.__dict__:
        msg = 'Module %s does not have function %s().' % (module_name, fname)
        if warn_errors:
            logger.debug(msg)
        return []

    ff = module.__dict__[fname]

    context.comp_dynamic(comptests_jobs_wrap, ff, job_id=module_name)

def comptests_jobs_wrap(context, ff):
    reset_config()
    ff(context)

main_comptests = CompTests.get_sys_main()
