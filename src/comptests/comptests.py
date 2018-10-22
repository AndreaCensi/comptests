import os

from conf_tools import GlobalConfig, import_name, reset_config
from contracts import contract
from contracts.utils import raise_desc, raise_wrapped

from quickapp import QuickApp

from . import logger
from .find_modules_imp import find_modules, find_modules_main
from .nose import jobs_nosetests, jobs_nosetests_single

__all__ = [
    'CompTests',
    'main_comptests',
    'get_comptests_output_dir',
]


def get_comptests_output_dir():
    """ when run from the comptests executable, returns the output dir. """
    if CompTests.output_dir_for_current_test is None:
        msg = 'Variable output_dir_for_current_test not set.'
        logger.warning(msg)
        return get_comptests_global_output_dir()
    else:
        return CompTests.output_dir_for_current_test


def get_comptests_global_output_dir():
    return CompTests.global_output_dir


class CompTests(QuickApp):
    """
        Runs the unit tests defined as @comptest.

    """

    global_output_dir = 'out-comptests'
    output_dir_for_current_test = None

    cmd = 'comptests'

    hook_name = 'jobs_comptests'

    def define_options(self, params):
        params.add_string('exclude', default='',
                          help='exclude these modules (comma separated)')

        params.add_flag('nonose', help='Disable nosetests')
        params.add_flag('coverage', help='Enable coverage module')
        params.add_flag('nocomp', help='Disable comptests hooks')

        params.add_flag('reports', help='Create reports jobs')
        params.add_flag('circle', help='Do CircleCI optimization')

        params.accept_extra()

    def define_jobs_context(self, context):

        CompTests.global_output_dir = self.get_options().output
        self.info('Setting output dir to %s' % CompTests.global_output_dir)
        CompTests.output_dir_for_current_test = None

        GlobalConfig.global_load_dir('default')

        modules = self.get_modules()

        if self.options.circle:
            env = os.environ
            v_index, v_total = 'CIRCLE_NODE_INDEX', 'CIRCLE_NODE_TOTAL'
            if v_index in env and v_total in env:
                index = int(os.environ[v_index])
                total = int(os.environ[v_total])
                msg = 'Detected I am worker #%s of %d in CircleCI.' % (index, total)
                self.info(msg)
                mine = []
                for i in range(len(modules)):
                    if i % total == index:
                        mine.append(modules[i])

                msg = 'I am only doing these modules: %s, instead of %s' % (mine, modules)
                self.info(msg)
                modules = mine

        if not modules:
            raise Exception('No modules found.')  # XXX: what's the nicer way?

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
        modules = list(filter(is_first, modules))

        excludes = self.options.exclude.split(',')
        to_exclude = lambda module_name: not module_name in excludes
        modules = list(filter(to_exclude, modules))
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

                for module in modules:
                    yield module
            else:
                self.info('Interpreting %r as module.' % m)
                yield m

    def instance_nosetests_jobs(self, context, modules, do_coverage):
        for module in modules:
            c = context.child(module)
            jobs_nosetests(c, module, do_coverage=do_coverage)

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
    from .registrar import jobs_registrar_simple
    is_first = not '.' in module_name
    warn_errors = is_first

    try:
        module = import_name(module_name)
    except ValueError as e:

        msg = 'Could not import module %r' % module_name

        if warn_errors:
            logger.error(msg)

        raise_wrapped(Exception, e, msg)

    fname = CompTests.hook_name

    if not fname in module.__dict__:
        msg = 'Module %s does not have function %s().' % (module_name, fname)
        if warn_errors:
            logger.debug(msg)
    else:
        ff = module.__dict__[fname]
        context.comp_dynamic(comptests_jobs_wrap, ff, job_id=module_name)

    jobs_registrar_simple(context, only_for_module=module_name)


def comptests_jobs_wrap(context, ff):
    reset_config()
    ff(context)


main_comptests = CompTests.get_sys_main()
