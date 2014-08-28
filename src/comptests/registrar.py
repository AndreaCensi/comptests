from .reports import (report_results_pairs, report_results_pairs_jobs, 
    report_results_single)
from collections import defaultdict
from conf_tools import ConfigMaster, GlobalConfig, ObjectSpec
from contracts import contract, describe_value
from quickapp import iterate_context_names, iterate_context_names_pair
import warnings
from compmake.structures import Promise

__all__ = [
    'comptests_for_all',
    'comptests_for_all_pairs',
    'comptests_for_all_dynamic',
    'comptests_for_all_pairs_dynamic',
    'jobs_registrar',
]


class ComptestsRegistrar(object):
    """ Static storage """
    objspec2tests = defaultdict(list)
    objspec2pairs = defaultdict(list)  # -> (objspec2, f)

    
@contract(objspec=ObjectSpec, dynamic=bool)
def register_single(objspec, f, dynamic):
    ts = ComptestsRegistrar.objspec2tests[objspec.name]
    ts.append(dict(function=f, dynamic=dynamic))

def register_pair(objspec1, objspec2, f, dynamic):
    ts = ComptestsRegistrar.objspec2pairs[objspec1.name]
    ts.append(dict(objspec2=objspec2, function=f, dynamic=dynamic))


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
        register_single(objspec, f, dynamic=False)  
        return f
    
    return register    


@contract(objspec=ObjectSpec)
def comptests_for_all_dynamic(objspec):
    """ 
        Returns a decorator for tests, which should take three parameters:
        context, id_object and object. 
    """
    def register(f):
        register_single(objspec, f, dynamic=True)  
        return f    
    return register    

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
def jobs_registrar(context, cm, create_reports=True):
    assert isinstance(cm, ConfigMaster)
    
    context = context.child(cm.name)
    
    names = sorted(cm.specs.keys())
    res = []
    names2test_objects = context.comp_config_dynamic(get_testobjects_promises, cm)
    
    
    for c, name in iterate_context_names(context, names):
        pairs = ComptestsRegistrar.objspec2pairs[name]
        functions = ComptestsRegistrar.objspec2tests[name]
        r = c.comp_config_dynamic(define_tests_for, 
                                  cm=cm,
                                  name=name,
                                  names2test_objects=names2test_objects, 
                                  pairs=pairs,functions=functions,
                                  create_reports=create_reports)
        res.append(r)
    # If we return then we trigger making of the children automatically
    # return res
 
@contract(cm=ConfigMaster, 
          returns='dict(str:dict(str:str))')
def get_testobjects_promises(context, cm):
    names2test_objects = {}
    for name in sorted(cm.specs.keys()):
        objspec = cm.specs[name]
        names2test_objects[name] = get_testobjects_promises_for_objspec(context, objspec)
    return names2test_objects 

@contract(name=str, create_reports='bool', names2test_objects='dict(str:dict(str:str))') 
def define_tests_for(context, cm, name, names2test_objects, pairs, functions, create_reports):
    objspec = cm.specs[name]
    define_tests_single(context, objspec, names2test_objects, functions=functions, create_reports=create_reports)
    define_tests_pairs(context, objspec, names2test_objects, pairs=pairs,create_reports=create_reports)

@contract(names2test_objects='dict(str:dict(str:str))')
def define_tests_single(context, objspec, names2test_objects, functions, create_reports):
    test_objects = names2test_objects[objspec.name]
    if not test_objects:
        msg = 'No test_objects for objects of kind %r.' % objspec.name
        print(msg)
        return

    if not functions:
        msg = 'No tests specified for objects of kind %r.' % objspec.name
        print(msg)

    for x in functions:
        f = x['function']
        dynamic = x['dynamic']
        results = {}
        
        c = context.child(f.__name__)
        c.add_extra_report_keys(objspec=objspec.name, function=f.__name__)

        for cc, id_object in iterate_context_names(c, test_objects, key='id_object'):
            ob = Promise(test_objects[id_object])
            job_id = 'f'
            if dynamic:
                res = cc.comp_config_dynamic(wrap_func_dyn, 
                                             f, id_object, ob, 
                                             job_id=job_id, command_name=f.__name__)
            else:
                res = cc.comp_config(wrap_func,
                                     f, id_object, ob, 
                                     job_id=job_id, command_name=f.__name__)
            results[id_object] = res

        if create_reports:
            r = c.comp(report_results_single, f, objspec.name, results)
            c.add_report(r, 'single')


@contract(names2test_objects='dict(str:dict(str:str))', create_reports='bool')
def define_tests_pairs(context, objspec1, names2test_objects, pairs, create_reports):
    objs1 = names2test_objects[objspec1.name]

    if not pairs:
        print('No %s+x pairs tests.' % (objspec1.name))
        return
    else:
        print('%d %s+x pairs tests.' % (len(pairs), objspec1.name))
        
    for x in pairs:
        objspec2 = x['objspec2']
        func = x['function']
        dynamic = x['dynamic']
        
        cx = context.child(func.__name__)
        cx.add_extra_report_keys(objspec1=objspec1.name, objspec2=objspec2.name,
                                 function=func.__name__)
        
        objs2 = names2test_objects[objspec2.name]
        if not objs2:
            print('No objects %r for pairs' % objspec2.name)
            continue

        results = {}
        jobs = {}
        
        combinations = iterate_context_names_pair(cx, objs1, objs2)
        for c, id_ob1, id_ob2 in combinations:
            ob1 = Promise(objs1[id_ob1])
            ob2 = Promise(objs2[id_ob2])
            
            job_id = 'f'
            if dynamic:
                res = c.comp_config_dynamic(wrap_func_pair_dyn,
                                            func, id_ob1, ob1, id_ob2, ob2,
                                              job_id=job_id,
                                              command_name=func.__name__)
            else:
                res = c.comp_config(wrap_func_pair,
                                    func, id_ob1, ob1, id_ob2, ob2,
                                      job_id=job_id,
                                      command_name=func.__name__)
            results[(id_ob1, id_ob2)] = res
            jobs[(id_ob1,id_ob2)] = res.job_id

        if create_reports:
            r = cx.comp_dynamic(report_results_pairs_jobs, 
                                 func, objspec1.name, objspec2.name, jobs)
            cx.add_report(r, 'jobs_pairs')
    
            r = cx.comp(report_results_pairs, 
                             func, objspec1.name, objspec2.name, results)
            cx.add_report(r, 'pairs')

def wrap_func(func, id_ob1, ob1):
    print('%20s: %s' % (id_ob1, describe_value(ob1)))
    return func(id_ob1, ob1)

def wrap_func_dyn(context, func, id_ob1, ob1):
    print('%20s: %s' % (id_ob1, describe_value(ob1)))
    return func(context, id_ob1,ob1)
  
def wrap_func_pair_dyn(context, func, id_ob1, ob1, id_ob2, ob2):
    print('%20s: %s' % (id_ob1, describe_value(ob1)))
    print('%20s: %s' % (id_ob2, describe_value(ob2)))
    return func(context, id_ob1,ob1,id_ob2,ob2)
 
def wrap_func_pair(func, id_ob1, ob1, id_ob2, ob2):
    print('%20s: %s' % (id_ob1, describe_value(ob1)))
    print('%20s: %s' % (id_ob2, describe_value(ob2)))
    return func(id_ob1,ob1,id_ob2,ob2)

@contract(objspec=ObjectSpec, returns='dict(str:str)')
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
            job = context.comp_config(instance_object, 
                                      master_name=objspec.master.name,
                                      objspec_name=objspec.name, id_object=id_object,
                                      job_id='%s-instance-%s' % (objspec.name, id_object))
        promises[id_object] = job.job_id
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

