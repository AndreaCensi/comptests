from collections import defaultdict
import itertools
import warnings

from contracts import contract

from conf_tools import ConfigMaster, GlobalConfig, ObjectSpec
from quickapp import iterate_context_names
from reprep import Report


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
def jobs_registrar(context, cm):
    names = sorted(cm.specs.keys())
    
    # str -> (str -> object promise)
    names2test_objects = get_testobjects_promises(context, cm, names)
    
    res = []
    for c, name in iterate_context_names(context, names):
        r = define_tests_for(c, cm.specs[name], names2test_objects)
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
def define_tests_for(context, objspec, names2test_objects):
    define_tests_single(context, objspec, names2test_objects)
    define_tests_pairs(context, objspec, names2test_objects)

@contract(names2test_objects='dict(str:dict(str:isinstance(Promise)))')
def define_tests_single(context, objspec, names2test_objects):
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
            res = context.comp_config(run_test, f, id_object, ob, job_id=job_id)
            results[id_object] = res

        r = context.comp_config(report_results_single, f, objspec.name, results)
        context.add_report(r, 'single', func=f.__name__, objspec=objspec.name)


@contract(results='dict(str:*)')
def report_results_single(func, objspec_name, results):
    r = Report()
    if not results:
        r.text('warning', 'no test objects defined')
        return
    rows = []
    data = []
    for id_object, res in results.items():
        rows.append(id_object)
        data.append([str(res)])

    r.table('summary', rows=rows, data=data)
    return r


@contract(names2test_objects='dict(str:dict(str:isinstance(Promise)))')
def define_tests_pairs(context, objspec1, names2test_objects):
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
        for (id_ob1, ob1), (id_ob2, ob2) in combinations:
            job_id = '%s-%s-%s' % (func.__name__, id_ob1, id_ob2)
            res = context.comp_config(run_test_pair,
                                      func, id_ob1, ob1, id_ob2, ob2,
                                      job_id=job_id)
            results[(id_ob1, id_ob2)] = res

        r = context.comp_config(report_results_pairs, func, objspec1.name, objspec2.name, results)
        context.add_report(r, 'pairs', func=func.__name__,
                           objspec1=objspec1.name, objspec2=objspec2.name)


@contract(results='dict(tuple(str,str):*)')
def report_results_pairs(func, objspec1_name, objspec2_name, results):
    r = Report()
    if not results:
        r.text('warning', 'no test objects defined')
        return r
    
    rows = sorted(set([a for a, _ in results]))
    cols = sorted(set([b for _, b in results]))
    data = [[None] * len(cols)] * len(rows)
    
    for ((i, id_object1), (j, id_object2)) in itertools.product(enumerate(rows), enumerate(cols)):
        res = results[(id_object1, id_object2)]
        data[i][j] = str(res)

    r.table('summary', rows=rows, data=data, cols=cols)
    return r



def run_test(function, id_ob, ob):
    return function(id_ob, ob)


def run_test_pair(function, id_ob, ob, id_ob2, ob2):
    return function(id_ob, ob, id_ob2, ob2)


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
                                  job_id='%s-%s' % (objspec.name, id_object))
        else:
            job = context.comp_config(instance_object, master_name=objspec.master.name,
                                  objspec_name=objspec.name, id_object=id_object,
                                  job_id='%s-%s' % (objspec.name, id_object))
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



#
# @contract(returns=Promise)
# def get_test_object_promise(context, objspec, id_object):
#     warnings.warn('Disabled reusing of instances for now.')
#
#     if False:
#         if objspec.instance_method is None:
#             resource = GETSPEC_TEST_OBJECT
#         else:
#             resource = INSTANCE_TEST_OBJECT
#         rm = context.get_resource_manager()
#         return rm.get_resource(resource,
#                                master=objspec.master.name,
#                                objspec=objspec.name, id_object=id_object)
#     else:
#         if objspec.instance_method is None:
#             job =
#         else:
#             job = context.comp_config(instance_object, master=objspec.master.name,
#                                   objspec=objspec.name, id_object=id_object,
#                                   job_id='inst-%s' % id_object)
#         return job

#
# @contract(returns='dict(str:*)')
# def get_test_objects(context, objspec):
#     objspec.master.load()
#     warnings.warn('Select test objects here')
#     objects = list(objspec.keys())
#     return dict([(x, get_test_object_promise(context, objspec, x))
#                  for x in objects])



# 
# @contract(objspec='str', id_object='str')
# def instance_test_object(context, master, objspec, id_object):
#     return context.comp_config(instance_object, master, objspec, id_object,
#                                job_id='i')
# 
# def recipe_instance_objects(context):
#         
#     rm = context.get_resource_manager()        
#     rm.set_resource_provider(INSTANCE_TEST_OBJECT, instance_test_object)
#     rm.set_resource_prefix_function(INSTANCE_TEST_OBJECT, _make_prefix)
# 
# 
# @contract(objspec='str', id_object='str')
# def get_the_spec(context, master, objspec, id_object):
#     return context.comp_config(get_spec, master, objspec, id_object,
#                                job_id='s')

# def recipe_get_spec(context):
#         
#     rm = context.get_resource_manager()        
#     rm.set_resource_provider(GETSPEC_TEST_OBJECT, get_the_spec)
#     rm.set_resource_prefix_function(GETSPEC_TEST_OBJECT, _make_prefix)


# def _make_prefix(rtype, master, objspec, id_object):  # @UnusedVariable
#     return 'instance-%s-%s' % (objspec, id_object)


#
# @contract(cm=ConfigMaster)
# def get_comptests_app(cm):
#     """
#         Returns a class subtype of QuickApp for instantiating tests
#         corresponding to all types of objects defined in the ConfigMaster
#         instance
#     """
#
#     class ComptestApp(QuickApp):
#         cmd = 'test-%s' % cm.name
#
#         def define_options(self, params):
#             pass
#
#         def define_jobs_context(self, context):
#             names = cm.specs.keys()
#             for c, name in iterate_context_names(context, names):
#                 define_tests_for(c, cm.specs[name])
#
#     ComptestApp.__name__ = 'ComptestApp%s' % cm.name
#     return ComptestApp
