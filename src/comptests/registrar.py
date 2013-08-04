from collections import defaultdict
from compmake import Promise
from conf_tools import ConfigMaster, GlobalConfig, ObjectSpec
from contracts import contract
from quickapp import QuickApp, iterate_context_names
import itertools

__all__ = ['get_comptests_app', 'comptests_for_all', 'comptests_for_all_pairs']

INSTANCE_TEST_OBJECT = 'instance'
GETSPEC_TEST_OBJECT = 'getspec'

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
def get_comptests_app(cm):
    """ 
        Returns a class subtype of QuickApp for instantiating tests
        corresponding to all types of objects defined in the ConfigMaster
        instance 
    """
    
    class ComptestApp(QuickApp):
        cmd = 'test-%s' % cm.name
        
        def define_options(self, params):
            pass
        
        def define_jobs_context(self, context):
            names = cm.specs.keys()
            for c, name in iterate_context_names(context, names):
                self.define_tests_for(c, cm.specs[name])
        
        @contract(objspec=ObjectSpec)
        def define_tests_for(self, context, objspec):
            # load default
            self.define_tests_single(context, objspec)
            self.define_tests_pairs(context, objspec)

        def define_tests_single(self, context, objspec):            
            test_objects = self.get_test_objects(context, objspec)
            
            if not test_objects:
                msg = 'No test_objects for objects of kind %r.' % objspec.name
                self.error(msg)
            
            functions = ComptestsRegistrar.objspec2tests[objspec.name]
            if not functions:
                msg = 'No tests specified for objects of kind %r.' % objspec.name
                self.error(msg)
                
            for id_object, ob in test_objects.items():    
                for f in functions:
                    job_id = '%s-%s' % (f.__name__, id_object)
                    context.comp_config(run_test, f, id_object, ob, job_id=job_id)
            
        def define_tests_pairs(self, context, objspec1):
            objs1 = self.get_test_objects(context, objspec1)
            
            pairs = ComptestsRegistrar.objspec2pairs[objspec1.name]
            if not pairs:
                self.warn('No %s+x pairs tests.' % (objspec1.name))
            else:
                self.info('%d %s+x pairs tests.' % (len(pairs), objspec1.name))
            for objspec2, func in pairs:
                objs2 = self.get_test_objects(context, objspec2)
                if not objs2:
                    self.error('No objects %r for pairs' % objspec2.name)
                combinations = itertools.product(objs1.items(), objs2.items()) 
                for (id_ob1, ob1), (id_ob2, ob2) in combinations:
                    job_id = '%s-%s-%s' % (func.__name__, id_ob1, id_ob2)
                    context.comp_config(run_test_pair, func, id_ob1, ob1, id_ob2, ob2,
                                 job_id=job_id)
            
        @contract(returns='dict(str:*)')
        def get_test_objects(self, context, objspec):
            objspec.master.load()
            objects = list(objspec.keys())
            return dict([(x, self.get_test_object_promise(context, objspec, x))
                         for x in objects])
                
        @contract(returns=Promise)
        def get_test_object_promise(self, context, objspec, id_object):
            if objspec.instance_method is None:
                resource = GETSPEC_TEST_OBJECT
            else:
                resource = INSTANCE_TEST_OBJECT
            rm = context.get_resource_manager()
            return rm.get_resource(resource,
                                   master=objspec.master.name,
                                   objspec=objspec.name, id_object=id_object)
                    
    ComptestApp.__name__ = 'ComptestApp%s' % cm.name
    return ComptestApp 

def run_test(function, id_ob, ob):
    return function(id_ob, ob)

def run_test_pair(function, id_ob, ob, id_ob2, ob2):
    return function(id_ob, ob, id_ob2, ob2)

def recipe_instance_objects(context):
    @contract(objspec='str', id_object='str')
    def instance_test_object(context, master, objspec, id_object):
        return context.comp_config(instance_object, master, objspec, id_object,
                                   job_id='i')
        
    rm = context.get_resource_manager()        
    rm.set_resource_provider(INSTANCE_TEST_OBJECT, instance_test_object)
    rm.set_resource_prefix_function(INSTANCE_TEST_OBJECT, _make_prefix)


def recipe_get_spec(context):
    @contract(objspec='str', id_object='str')
    def get_the_spec(context, master, objspec, id_object):
        return context.comp_config(get_spec, master, objspec, id_object,
                                   job_id='s')
        
    rm = context.get_resource_manager()        
    rm.set_resource_provider(GETSPEC_TEST_OBJECT, get_the_spec)
    rm.set_resource_prefix_function(GETSPEC_TEST_OBJECT, _make_prefix)


def get_objspec(master_name, objspec_name):
    master = GlobalConfig._masters[master_name]
    specs = master.specs
    if not objspec_name in specs:
        msg = '%s > %s not found' % (master_name, objspec_name)
        msg += str(specs.keys())
        raise Exception(msg)
    objspec = master.specs[objspec_name]
    return objspec


def get_spec(master_name, objspec_name, id_object):
    objspec = get_objspec(master_name, objspec_name)
    return objspec[id_object]


def _make_prefix(rtype, master, objspec, id_object):  # @UnusedVariable
    return 'instance-%s-%s' % (objspec, id_object)
    
    
def instance_object(master_name, objspec_name, id_object):
    objspec = get_objspec(master_name, objspec_name)
    return objspec.instance(id_object)


