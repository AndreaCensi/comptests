# -*- coding: utf-8 -*-
import os
import sys
import traceback
import warnings
from collections import defaultdict, namedtuple, OrderedDict

from compmake import Promise
from compmake.jobs import assert_job_exists
from conf_tools import ConfigMaster, GlobalConfig, ObjectSpec
from conf_tools.utils import expand_string
from contracts import contract
from contracts.utils import raise_desc, indent
from quickapp import iterate_context_names, iterate_context_names_pair

from . import logger
from .reports import (report_results_pairs, report_results_pairs_jobs,
                      report_results_single)

__all__ = [
    'comptest',
    'run_module_tests',
    'comptest_fails',
    'comptest_dynamic',
    'comptests_for_all',
    'comptests_for_all_pairs',
    'comptests_for_some',
    'comptests_for_some_pairs',
    'comptests_for_all_dynamic',
    'comptests_for_all_pairs_dynamic',
    'jobs_registrar',
    'jobs_registrar_simple',
]


class ComptestsRegistrar(object):
    """ Static storage """
    regular = []  # list of dict(function=f, dynamic=dynamic))
    # Once they are scheduled we add id(x) here, so we make sure we
    # don't register something twice
    regular_scheduled = set()

    objspec2tests = defaultdict(list)
    objspec2pairs = defaultdict(list)  # -> (objspec2, f)
    objspec2testsome = defaultdict(list)  # -> dict(function, id_object, dynamic=False)
    objspec2testsomepairs = defaultdict(list)


@contract(objspec=ObjectSpec, dynamic=bool)
def register_single(objspec, f, dynamic):
    ts = ComptestsRegistrar.objspec2tests[objspec.name]
    ts.append(dict(function=f, dynamic=dynamic))


def register_pair(objspec1, objspec2, f, dynamic):
    ts = ComptestsRegistrar.objspec2pairs[objspec1.name]
    ts.append(dict(objspec2=objspec2, function=f, dynamic=dynamic))


def register_for_some_pairs(objspec1, objspec2, f, which1, which2, dynamic):
    ts = ComptestsRegistrar.objspec2testsomepairs[objspec1.name]
    ts.append(dict(objspec2=objspec2, function=f, dynamic=dynamic,
                   which1=which1, which2=which2))


@contract(objspec=ObjectSpec, dynamic=bool)
def register_for_some(objspec, f, which, dynamic):
    ts = ComptestsRegistrar.objspec2testsome[objspec.name]
    ts.append(dict(function=f, which=which, dynamic=dynamic))


def register_indep(f, dynamic, args, kwargs):
    d = dict(function=f, dynamic=dynamic, args=args, kwargs=kwargs)
    ComptestsRegistrar.regular.append(d)


def comptest(f):
    register_indep(f, dynamic=False, args=(), kwargs={})
    return f


def check_fails(f, *args, **kwargs):
    try:
        f(*args, **kwargs)
    except BaseException as e:
        logger.error('Known failure for %s ' % f)
        logger.warn('Fails with error %s' % e)
        # comptest_fails = kwargs.get('comptest_fails', f.__name__)
        d = 'out/comptests-failures'
        if not os.path.exists(d):
            os.makedirs(d)
        try:
            from compmake.jobs.job_execution import JobCompute
            job_id = JobCompute.current_job_id
            if job_id is None:
                job_id = 'nojob-%s' % f.__name__
            out = os.path.join(d, job_id + '.txt')
            #         for i in range(1000):
            #             outi = out % i
            #             if not os.path.exists(outi):
            with open(out, 'w') as f:
                f.write(traceback.format_exc())
        except ImportError:
            pass

    else:
        msg = 'Function was supposed to fail.'
        raise_desc(Exception, msg, f=f, args=args, kwargs=kwargs)


class Wrap(object):
    """ Need to assign name """

    def __init__(self, f):
        self.f = f

    def __call__(self, *args, **kwargs):
        return self.f(*args, **kwargs)


def comptest_fails(f):
    check_fails_wrap = Wrap(check_fails)
    check_fails_wrap.__name__ = f.__name__
    check_fails_wrap.__module__ = f.__module__
    register_indep(check_fails_wrap, dynamic=False, args=(f,), kwargs={})
    return f


def comptest_dynamic(f):
    register_indep(f, dynamic=True, args=(), kwargs={})
    return f


@contract(objspec=ObjectSpec)
def comptests_for_all(objspec):
    """
        Returns a decorator for mcdp_lang_tests, which should take two parameters:
        id and object.
    """

    # from decorator import decorator
    # not sure why it doesn't work...
    # @decorator
    def register(f):
        register_single(objspec, f, dynamic=False)

        register.registered.append(f)

        return f

    register.registered = []

    return register


@contract(objspec=ObjectSpec)
def comptests_for_all_dynamic(objspec):
    """
        Returns a decorator for mcdp_lang_tests, which should take three parameters:
        context, id_object and object.
    """

    def register(f):
        register_single(objspec, f, dynamic=True)
        return f

    return register


@contract(objspec=ObjectSpec)
def comptests_for_some(objspec):
    """ Returns a decorator for a test involving one object only. """

    def dec(which):
        def register(f):
            register_for_some(objspec=objspec, f=f, which=which, dynamic=False)
            return f

        return register

    return dec


@contract(objspec=ObjectSpec)
def comptests_for_some_dynamic(objspec):
    """ Returns a decorator for a test involving one object only. """

    def dec(which):
        def register(f):
            register_for_some(objspec=objspec, f=f, which=which, dynamic=True)
            return f

        return register

    return dec


@contract(objspec1=ObjectSpec, objspec2=ObjectSpec)
def comptests_for_some_pairs(objspec1, objspec2):
    """ Returns a decorator for a test involving only a subset of objects. """

    def dec(which1, which2):
        def register(f):
            register_for_some_pairs(objspec1, objspec2, f, which1, which2, dynamic=False)
            return f

        return register

    return dec


@contract(objspec1=ObjectSpec, objspec2=ObjectSpec)
def comptests_for_some_pairs_dynamic(objspec1, objspec2):
    """ Returns a decorator for a test involving only a subset of objects. """

    def dec(which1, which2):
        def register(f):
            register_for_some_pairs(objspec1, objspec2, f, which1, which2, dynamic=True)
            return f

        return register

    return dec


@contract(objspec1=ObjectSpec, objspec2=ObjectSpec)
def comptests_for_all_pairs_dynamic(objspec1, objspec2):
    def register(f):
        register_pair(objspec1, objspec2, f, dynamic=True)
        return f

    return register


@contract(objspec1=ObjectSpec, objspec2=ObjectSpec)
def comptests_for_all_pairs(objspec1, objspec2):
    def register(f):
        register_pair(objspec1, objspec2, f, dynamic=False)
        return f

    return register


@contract(cm=ConfigMaster)
def jobs_registrar(context, cm, create_reports=False):
    assert isinstance(cm, ConfigMaster)

    # Sep 15: remove name
    #     context = context.child(cm.name)
    context = context.child("")

    names = sorted(cm.specs.keys())

    names2test_objects = context.comp_config_dynamic(get_testobjects_promises, cm)

    for c, name in iterate_context_names(context, names):
        pairs = ComptestsRegistrar.objspec2pairs[name]
        functions = ComptestsRegistrar.objspec2tests[name]
        some = ComptestsRegistrar.objspec2testsome[name]
        some_pairs = ComptestsRegistrar.objspec2testsomepairs[name]

        c.comp_config_dynamic(define_tests_for,
                              cm=cm,
                              name=name,
                              names2test_objects=names2test_objects,
                              pairs=pairs,
                              functions=functions,
                              some=some,
                              some_pairs=some_pairs,
                              create_reports=create_reports)

    jobs_registrar_simple(context)


def jobs_registrar_simple(context, only_for_module=None):
    """ Registers the simple "comptest" """
    prefix = context._job_prefix

    n = 0
    for x in ComptestsRegistrar.regular:
        function = x['function']
        dynamic = x['dynamic']
        args = x['args']
        kwargs = x['kwargs']

        if only_for_module is not None:
            this = function.__module__.split(".")[0]
            if this != only_for_module:
                msg = ('Skipping function %s in module %s because not in module %r' %
                       (function, function.__module__, only_for_module))
                #                 logger.error(msg)
                continue

        id_x = id(x)
        if id_x in ComptestsRegistrar.regular_scheduled:
            msg = 'Job already registered. Skipping.'
            logger.debug(msg)
            continue

        ComptestsRegistrar.regular_scheduled.add(id_x)

        # print('registering %s' % x)
        #         logger.debug("registering %s" % function.__name__)
        wrapper = WrapTest(function, prefix)
        if not dynamic:
            _res = context.comp_config(wrapper, *args, **kwargs)
        else:
            _res = context.comp_config_dynamic(wrapper, *args, **kwargs)

        n += 1

    print('Registered %d tests (reading a list of %s)' % (n, len(ComptestsRegistrar.regular)))


class WrapTest(object):

    def __init__(self, function, prefix):
        self.__name__ = function.__name__
        self.function = function
        from .comptests import CompTests
        if prefix is not None:
            self.output_dir = os.path.join(CompTests.global_output_dir,
                                           prefix, self.__name__)
        else:
            self.output_dir = os.path.join(CompTests.global_output_dir,
                                           self.__name__)

    def __call__(self, *args, **kwargs):
        from .comptests import CompTests
        CompTests.output_dir_for_current_test = self.output_dir
        return self.function(*args, **kwargs)


@contract(cm=ConfigMaster,
          returns='dict(str:dict(str:str))')
def get_testobjects_promises(context, cm):
    names2test_objects = {}
    for name in sorted(cm.specs.keys()):
        objspec = cm.specs[name]
        its = get_testobjects_promises_for_objspec(context, objspec)
        names2test_objects[name] = its
    return names2test_objects


@contract(name=str, create_reports='bool',
          names2test_objects='dict(str:dict(str:str))')
def define_tests_for(context, cm, name, names2test_objects,

                     pairs, functions, some, some_pairs,

                     create_reports):
    objspec = cm.specs[name]

    define_tests_single(context, objspec, names2test_objects,
                        functions=functions, create_reports=create_reports)
    define_tests_pairs(context, objspec, names2test_objects,
                       pairs=pairs, create_reports=create_reports)

    define_tests_some_pairs(context, objspec, names2test_objects,
                            some_pairs=some_pairs, create_reports=create_reports)

    define_tests_some(context, objspec, names2test_objects,
                      some=some, create_reports=create_reports)


@contract(names2test_objects='dict(str:dict(str:str))')
def define_tests_some(context, objspec, names2test_objects,
                      some, create_reports):
    test_objects = names2test_objects[objspec.name]

    if not test_objects:
        msg = 'No test_objects for objects of kind %r.' % objspec.name
        print(msg)
        return

    if not some:
        msg = 'No mcdp_lang_tests specified for objects of kind %r.' % objspec.name
        print(msg)
        return

    db = context.cc.get_compmake_db()

    for x in some:
        f = x['function']
        which = x['which']
        dynamic = x['dynamic']
        results = {}

        c = context.child(f.__name__)
        c.add_extra_report_keys(objspec=objspec.name, function=f.__name__)

        objects = expand_string(which, list(test_objects))
        if not objects:
            msg = 'Which = %r did not give anything in %r.' % (which, test_objects)
            raise ValueError(msg)

        print('Testing %s for %s' % (f, objects))

        it = iterate_context_names(c, objects, key=objspec.name)
        for cc, id_object in it:
            ob_job_id = test_objects[id_object]
            assert_job_exists(ob_job_id, db)
            ob = Promise(ob_job_id)
            # bjob_id = 'f'  # XXX
            job_id = '%s-%s' % (f.__name__, id_object)

            params = dict(job_id=job_id, command_name=f.__name__)
            if dynamic:
                res = cc.comp_config_dynamic(wrap_func_dyn, f, id_object, ob,
                                             **params)
            else:
                res = cc.comp_config(wrap_func, f, id_object, ob,
                                     **params)
            results[id_object] = res

        if create_reports:
            r = c.comp(report_results_single, f, objspec.name, results)
            c.add_report(r, 'some')


@contract(names2test_objects='dict(str:dict(str:str))')
def define_tests_single(context, objspec, names2test_objects,
                        functions, create_reports):
    test_objects = names2test_objects[objspec.name]
    if not test_objects:
        msg = 'No test_objects for objects of kind %r.' % objspec.name
        print(msg)
        return

    if not functions:
        msg = 'No mcdp_lang_tests specified for objects of kind %r.' % objspec.name
        print(msg)

    db = context.cc.get_compmake_db()

    for x in functions:
        f = x['function']
        dynamic = x['dynamic']
        results = {}

        c = context.child(f.__name__)
        c.add_extra_report_keys(objspec=objspec.name, function=f.__name__)

        it = iterate_context_names(c, list(test_objects), key=objspec.name)
        for cc, id_object in it:
            ob_job_id = test_objects[id_object]
            assert_job_exists(ob_job_id, db)
            ob = Promise(ob_job_id)
            job_id = 'f'

            params = dict(job_id=job_id, command_name=f.__name__)
            if dynamic:
                res = cc.comp_config_dynamic(wrap_func_dyn, f, id_object, ob,
                                             **params)
            else:
                res = cc.comp_config(wrap_func, f, id_object, ob,
                                     **params)
            results[id_object] = res

        if create_reports:
            r = c.comp(report_results_single, f, objspec.name, results)
            c.add_report(r, 'single')


@contract(names2test_objects='dict(str:dict(str:str))', create_reports='bool')
def define_tests_pairs(context, objspec1, names2test_objects, pairs, create_reports):
    objs1 = names2test_objects[objspec1.name]

    if not pairs:
        print('No %s+x pairs mcdp_lang_tests.' % (objspec1.name))
        return
    else:
        print('%d %s+x pairs mcdp_lang_tests.' % (len(pairs), objspec1.name))

    for x in pairs:
        objspec2 = x['objspec2']
        func = x['function']
        dynamic = x['dynamic']

        cx = context.child(func.__name__)
        cx.add_extra_report_keys(objspec1=objspec1.name, objspec2=objspec2.name,
                                 function=func.__name__, type='pairs')

        objs2 = names2test_objects[objspec2.name]
        if not objs2:
            print('No objects %r for pairs' % objspec2.name)
            continue

        results = {}
        jobs = {}

        db = context.cc.get_compmake_db()

        combinations = iterate_context_names_pair(cx, list(objs1), list(objs2),
                                                  key1=objspec1.name, key2=objspec2.name)
        for c, id_ob1, id_ob2 in combinations:
            assert_job_exists(objs1[id_ob1], db)
            assert_job_exists(objs2[id_ob2], db)
            ob1 = Promise(objs1[id_ob1])
            ob2 = Promise(objs2[id_ob2])

            params = dict(job_id='f', command_name=func.__name__)
            if dynamic:
                res = c.comp_config_dynamic(wrap_func_pair_dyn,
                                            func, id_ob1, ob1, id_ob2, ob2,
                                            **params)
            else:
                res = c.comp_config(wrap_func_pair,
                                    func, id_ob1, ob1, id_ob2, ob2,
                                    **params)
            results[(id_ob1, id_ob2)] = res
            jobs[(id_ob1, id_ob2)] = res.job_id

        warnings.warn('disabled report functionality')

        if create_reports:
            r = cx.comp_dynamic(report_results_pairs_jobs,
                                func, objspec1.name, objspec2.name, jobs)
            cx.add_report(r, 'jobs_pairs')

            r = cx.comp(report_results_pairs,
                        func, objspec1.name, objspec2.name, results)
            cx.add_report(r, 'pairs')


@contract(names2test_objects='dict(str:dict(str:str))', create_reports='bool')
def define_tests_some_pairs(context, objspec1, names2test_objects, some_pairs, create_reports):
    if not some_pairs:
        print('No %s+x pairs mcdp_lang_tests.' % (objspec1.name))
        return
    else:
        print('%d %s+x pairs mcdp_lang_tests.' % (len(some_pairs), objspec1.name))

    for x in some_pairs:
        objspec2 = x['objspec2']
        func = x['function']
        which1 = x['which1']
        which2 = x['which2']
        dynamic = x['dynamic']

        allobjs1 = names2test_objects[objspec1.name]
        allobjs2 = names2test_objects[objspec2.name]

        objs1 = expand_string(which1, list(allobjs1))
        objs2 = expand_string(which2, list(allobjs2))

        if not objs1:
            msg = 'No objects %r in %r.' % (which1, list(allobjs1))
            raise ValueError(msg)

        if not objs2:
            msg = 'No objects %r in %r.' % (which2, list(allobjs2))
            raise ValueError(msg)

        for x in objs1:
            if not x in allobjs1:
                msg = '%r expanded to %r but %r is not in universe %r.' % (which1, objs1, x, list(allobjs1))
                raise ValueError(msg)

        for x in objs2:
            if not x in allobjs2:
                msg = '%r expanded to %r but %r is not in universe %r.' % (which2, objs2, x, list(allobjs2))
                raise ValueError(msg)

        cx = context.child(func.__name__)
        cx.add_extra_report_keys(objspec1=objspec1.name, objspec2=objspec2.name,
                                 function=func.__name__, type='some')
        db = context.cc.get_compmake_db()

        use_objs1 = dict((k, allobjs1[k]) for k in objs1)
        use_objs2 = dict((k, allobjs2[k]) for k in objs2)
        define_tests_some_pairs_(cx, db, objspec1, objspec2, use_objs1, use_objs2, func, dynamic, create_reports)


def define_tests_some_pairs_(cx, db, objspec1, objspec2, objs1, objs2, func, dynamic, create_reports):
    results = {}
    jobs = {}
    combinations = iterate_context_names_pair(cx, list(objs1), list(objs2),
                                              key1=objspec1.name, key2=objspec2.name)
    for c, id_ob1, id_ob2 in combinations:
        assert_job_exists(objs1[id_ob1], db)
        assert_job_exists(objs2[id_ob2], db)
        ob1 = Promise(objs1[id_ob1])
        ob2 = Promise(objs2[id_ob2])

        params = dict(job_id='f', command_name=func.__name__)
        if dynamic:
            res = c.comp_config_dynamic(wrap_func_pair_dyn,
                                        func, id_ob1, ob1, id_ob2, ob2,
                                        **params)
        else:
            res = c.comp_config(wrap_func_pair,
                                func, id_ob1, ob1, id_ob2, ob2,
                                **params)
        results[(id_ob1, id_ob2)] = res
        jobs[(id_ob1, id_ob2)] = res.job_id

    if create_reports:
        r = cx.comp_dynamic(report_results_pairs_jobs,
                            func, objspec1.name, objspec2.name, jobs)
        cx.add_report(r, 'jobs_pairs_some')

        r = cx.comp(report_results_pairs,
                    func, objspec1.name, objspec2.name, results)
        cx.add_report(r, 'pairs_some')


def wrap_func(func, id_ob1, ob1):
    # print('%20s: %s' % (id_ob1, describe_value(ob1)))
    return func(id_ob1, ob1)


def wrap_func_dyn(context, func, id_ob1, ob1):
    # print('%20s: %s' % (id_ob1, describe_value(ob1)))
    return func(context, id_ob1, ob1)


def wrap_func_pair_dyn(context, func, id_ob1, ob1, id_ob2, ob2):
    # print('%20s: %s' % (id_ob1, describe_value(ob1)))
    # print('%20s: %s' % (id_ob2, describe_value(ob2)))
    return func(context, id_ob1, ob1, id_ob2, ob2)


def wrap_func_pair(func, id_ob1, ob1, id_ob2, ob2):
    # print('%20s: %s' % (id_ob1, describe_value(ob1)))
    # print('%20s: %s' % (id_ob2, describe_value(ob2)))
    return func(id_ob1, ob1, id_ob2, ob2)


@contract(objspec=ObjectSpec, returns='dict(str:str)')
def get_testobjects_promises_for_objspec(context, objspec):
    warnings.warn('Need to be smarter here.')
    objspec.master.load()
    warnings.warn('Select test objects here.')
    objects = sorted(objspec.keys())

    if False:
        warnings.warn("Maybe warn here.")
        if not objects:
            msg = 'Could not find any test objects for %r.' % objspec
            raise ValueError(msg)

    promises = {}
    for id_object in objects:
        params = dict(job_id='%s-instance-%s' % (objspec.name, id_object),
                      command_name='instance_%s' % objspec.name)
        if objspec.instance_method is None:
            job = context.comp_config(get_spec, master_name=objspec.master.name,
                                      objspec_name=objspec.name, id_object=id_object,
                                      **params)
        else:
            job = context.comp_config(instance_object,
                                      master_name=objspec.master.name,
                                      objspec_name=objspec.name, id_object=id_object,
                                      **params)
        promises[id_object] = job.job_id
        db = context.cc.get_compmake_db()
        assert_job_exists(job.job_id, db)
        # print('defined %r -> %s' % (id_object, job.job_id))
        if not job.job_id.endswith(params['job_id']):
            msg = 'Wanted %r but got %r' % (params['job_id'], job.job_id)
            raise ValueError(msg)
    return promises


def get_spec(master_name, objspec_name, id_object):
    objspec = get_objspec(master_name, objspec_name)
    return objspec[id_object]


def instance_object(master_name, objspec_name, id_object):
    objspec = get_objspec(master_name, objspec_name)
    return objspec.instance(id_object)


def get_objspec(master_name, objspec_name):
    master = GlobalConfig._masters[master_name]
    specs = master.specs
    if not objspec_name in specs:
        msg = '%s > %s not found' % (master_name, objspec_name)
        msg += '\n%s' % list(specs.keys())
        raise Exception(msg)
    objspec = master.specs[objspec_name]
    return objspec


def run_module_tests():
    """
        Runs directly the tests defined in this module.

        if __name__ == '__main__':
            run_module_tests()

        argument 1: grep
    """
    #     logger.debug('run_module_tests: args = %s' % sys.argv)
    grep = sys.argv[1] if len(sys.argv) > 1 else None

    #     logger.debug('grep = %r' % grep)
    def should_ignore(its_name):
        if grep is None:
            return False
        do_ignore = not grep in its_name
        #         if not do_ignore:
        #             print('found %s in %s' % ( grep, r))
        return do_ignore

    Res = namedtuple('Res', 'x es en')
    results = OrderedDict()
    all_tests_regular = list(ComptestsRegistrar.regular)
    seen = []
    for x in reversed(all_tests_regular):
        function = x['function']
        name = function.__name__
        if function.__module__ != '__main__':
            # logger.debug('not running test %s' % name)
            continue

        seen.append(name)

        if should_ignore(name):
            logger.debug('Ignoring test %s' % name)
            continue

        logger.debug('Running test %s' % name)

        try:
            wrapped = WrapTest(function, prefix=None)
            wrapped(*x['args'], **x['kwargs'])
            r = Res(x=x, es=None, en=None)

        except BaseException as e2:
            es = traceback.format_exc(e2)
            r = Res(x=x, es=es, en=type(e2).__name__)

        results[name] = r

    nerrors = 0
    msg = ""

    for name, r in list(results.items()):
        passed = r.es is None
        mark = '✓' if passed else r.en
        nerrors += 0 if passed else 1

        msg += '\n %30s : %s' % (name, mark)

        if r.es is not None:
            logger.error('Test %s failed: ' % name)
            logger.error(indent(r.es, '> '))
    #             errors[name] = r

    #             if args:
    #                 if name not in  args:
    #                     #logger.info('skipping %s because not in %s' % (name, args))
    #                     continue
    #             logger.info('run_module_tests: %s' % name)
    #             try:
    #                 seen.append(name)
    #                 function(*x['args'], **x['kwargs'])
    #             except Exception as e:
    #                 s = traceback.format_exc(e)
    #                 logger.error(s)
    #                 errors[name] = e
    #         else:
    #             pass
    #             logger.debug('skipping %s because not in module __main__ (%s)' %
    #                           (name, function.__module__))

    if nerrors > 0 and (len(seen) > 1):
        logger.error('There were %d errors' % nerrors)
    #         for k in seen:
    #             if k in errors:
    #                 s = '%s: Failed with %s' % (k, type(e).__name__)
    #                 s += '\n' + indent(traceback.format_exc(e), '%s | ' % k)
    #                 logger.error(s)
    #
    #         for k in seen:
    #             if k in errors:
    #                 s = '%s: Failed with %s' % (k, type(e).__name__)
    #                 logger.error(s)
    #             else:
    #                 logger.info('%s: OK' % k)
    #
    if nerrors == 0:
        if grep is not None and not results:
            msg = 'run_module_tests: no tests found matching %r' % grep
            msg += '\nKnown: %s' % seen
            logger.error(msg)
            sys.exit(2)
        l = ", ".join(sorted(results))
        logger.info('run_module_tests: run these tests successfully: %s' % l)
    else:
        sys.exit(1)
