from .generation import (for_all_class1, for_all_class1_class2, 
    for_all_class1_class2_dynamic, for_all_class1_dynamic)
from example_package.unittests.generation import for_some_class1, \
    for_some_class1_class2
from comptests.registrar import comptest, comptest_dynamic, comptest_fails


@comptest
def simple_check():
    pass

@comptest_dynamic
def dyn_simple_check(context):
    pass


@for_all_class1
def check_class1(id_ob, _):
    print('check_class1(%r)' % id_ob)


@for_some_class1('c1a')
def check_some_class1(id_ob, _):
    assert id_ob == 'c1a'


@for_some_class1_class2('c1*', 'c2*')
def check_some_class1_class2(id_ob1, _, id_ob2, _2):
    assert id_ob1 in ['c1a', 'c1b']
    assert id_ob2 == 'c2a'

#
# @for_some_class1_class2('c1b', 'c2*')
# def check_some_class1_class2_2(id_ob1, _, id_ob2, _2):
#     assert id_ob1 == 'c1b'
#     assert id_ob2 == 'c2a'

 
@for_all_class1_class2
def check_class1_class2(id_ob1, _, id_ob2, _2):
    print('check_class1_class2(%r,%r)' % (id_ob1, id_ob2))


@for_all_class1_dynamic
def check_class1_dynamic(context, _, ob1):
    r = context.comp(report_class1, ob1)
    context.add_report(r, 'report_class1_single')


@for_all_class1_class2_dynamic
def check_class1_class2_dynamic(context, _, ob1, _2, ob2):
    r = context.comp(report_class1, ob1)
    context.add_report(r, 'report_class1')

    r = context.comp(report_class2, ob2)
    context.add_report(r, 'report_class2')


def report_class1(ob1):
    from reprep import Report
    r = Report()
    r.text('ob1', ob1)
    return r


def report_class2(ob2):
    from reprep import Report
    r = Report()
    r.text('ob2', ob2)
    return r


# normal test
def test_dummy():
    pass

# 
# @comptest
# def a_real_failure():
#     raise Exception('A failure')

@comptest_fails
def expected_failure():
    raise Exception('expected_failure')

