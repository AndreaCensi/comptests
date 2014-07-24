from .reports import (report_results_pairs, report_results_pairs_jobs, 
    report_results_single)
from collections import defaultdict
from conf_tools import ConfigMaster, GlobalConfig, ObjectSpec
from contracts import contract
from quickapp import iterate_context_names
import itertools
import warnings

__all__ = [
    'comptests_for_all',
    'comptests_for_all_pairs',
    'jobs_registrar',
]


class ComptestsRegistrar(object):
    """ Static storage """
    objspec2tests = defaultdict(list)
    objspec2pairs = defaultdict(list)  # -> (objspec2, f)

    
@contract(objspec=ObjectSpec)
def register_single(objspec, f):
    ComptestsRegistrar.objspec2tests[objspec.name].append(f)


def register_pair(objspec1, objspec2, f):
    ComptestsRegistrar.objspec2pairs[objspec1.name].append((objspec2, f))


@contract(objspec=ObjectSpec)
def comptests_for_all(objspec):
    """ 
        Returns a decorator for tests, which should take two parameters:
        id and object. 
    """
    
    # from decorator import decorator
    # not sure why it doesn't work...
    # @decorator
    def register(f):
        register_single(objspec, f)  
        return f
    
    return register    

@contract(objspec1=ObjectSpec, objspec2=ObjectSpec)
def comptests_for_all_pairs(objspec1, objspec2):
    def register(f):
        register_pair(objspec1, objspec2, f)  
        return f
    return register    

@contract(cm=ConfigMaster)
def jobs_registrar(context, cm, create_reports=True):
    names = sorted(cm.specs.keys())
    
    # str -> (str -> object promise)
    names2test_objects = get_testobjects_promises(context, cm, names)
    
    res = []
    for c, name in iterate_context_names(context, names):
        r = define_tests_for(c, cm.specs[name], names2test_objects, create_reports=create_reports)
        res.append(r)
    return res

@contract(names='list(str)', cm=ConfigMaster, returns='dict(str:dict(str:isinstance(Promise)))')
def get_testobjects_promises(context, cm, names):
    names2test_objects = {}
    for name in names:
        objspec = cm.specs[name]
        names2test_objects[name] = get_testobjects_promises_for_objspec(context, objspec)
    return names2test_objects 


@contract(objspec=ObjectSpec, names2test_objects='dict(str:dict(str:isinstance(Promise)))')
def define_tests_for(context, objspec, names2test_objects, create_reports):
    define_tests_single(context, objspec, names2test_objects, create_reports=create_reports)
    define_tests_pairs(context, objspec, names2test_objects, create_reports=create_reports)

@contract(names2test_objects='dict(str:dict(str:isinstance(Promise)))')
def define_tests_single(context, objspec, names2test_objects, create_reports):
    test_objects = names2test_objects[objspec.name]
    if not test_objects:
        msg = 'No test_objects for objects of kind %r.' % objspec.name
        print(msg)

    functions = ComptestsRegistrar.objspec2tests[objspec.name]
    if not functions:
        msg = 'No tests specified for objects of kind %r.' % objspec.name
        print(msg)

    for f in functions:
        results = {}

        for id_object, ob in test_objects.items():
            job_id = '%s-%s' % (f.__name__, id_object)
            res = context.comp_config(f, id_object, ob, job_id=job_id)
            results[id_object] = res

        if create_reports:
            r = context.comp(report_results_single, f, objspec.name, results)
            context.add_report(r, 'single', function=f.__name__, objspec=objspec.name)


@contract(names2test_objects='dict(str:dict(str:isinstance(Promise)))', create_reports='bool')
def define_tests_pairs(context, objspec1, names2test_objects, create_reports):
    objs1 = names2test_objects[objspec1.name]

    pairs = ComptestsRegistrar.objspec2pairs[objspec1.name]
    if not pairs:
        print('No %s+x pairs tests.' % (objspec1.name))
    else:
        print('%d %s+x pairs tests.' % (len(pairs), objspec1.name))
    for objspec2, func in pairs:
        objs2 = names2test_objects[objspec2.name]
        if not objs2:
            print('No objects %r for pairs' % objspec2.name)
        combinations = itertools.product(objs1.items(), objs2.items())

        results = {}
        jobs = {}
        for (id_ob1, ob1), (id_ob2, ob2) in combinations:
            job_id = '%s-%s-%s' % (func.__name__, id_ob1, id_ob2)
            res = context.comp_config(func, id_ob1, ob1, id_ob2, ob2,
                                      job_id=job_id)
            results[(id_ob1, id_ob2)] = res
            jobs[(id_ob1,id_ob2)] = res.job_id

            
        if create_reports:
            r = context.comp_dynamic(report_results_pairs_jobs, 
                                     func, objspec1.name, objspec2.name, jobs)
            context.add_report(r, 'jobs_pairs', function=func.__name__,
                               objspec1=objspec1.name, objspec2=objspec2.name)
    
            r = context.comp(report_results_pairs, 
                             func, objspec1.name, objspec2.name, results)
            context.add_report(r, 'pairs', function=func.__name__,
                               objspec1=objspec1.name, objspec2=objspec2.name)
 

@contract(objspec=ObjectSpec, returns='dict(str:isinstance(Promise))')
def get_testobjects_promises_for_objspec(context, objspec):
    warnings.warn('Need to be smarter here.')
    objspec.master.load()
    warnings.warn('Select test objects here.')
    objects = sorted(objspec.keys())
    promises = {}
    for id_object in objects:
        if objspec.instance_method is None:
            job = context.comp_config(get_spec, master_name=objspec.master.name,
                                  objspec_name=objspec.name, id_object=id_object,
                                  job_id='%s-instance-%s' % (objspec.name, id_object))
        else:
            # Cannot change name, otherwise cannot be pickled
            # instance_object.__name__ = 'instance_%s' % objspec.name
            job = context.comp_config(instance_object, master_name=objspec.master.name,
                                  objspec_name=objspec.name, id_object=id_object,
                                  job_id='%s-instance-%s' % (objspec.name, id_object))
        promises[id_object] = job
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
        msg += str(specs.keys())
        raise Exception(msg)
    objspec = master.specs[objspec_name]
    return objspec

