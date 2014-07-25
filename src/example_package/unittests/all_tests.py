from .generation import (for_all_class1, for_all_class1_class2, 
    for_all_class1_class2_dynamic, for_all_class1_dynamic)


@for_all_class1
def check_class1(id_ob, ob):
    print('check_class1(%r)' % id_ob)
 
@for_all_class1_class2
def check_class1_class2(id_ob1, ob1, id_ob2, ob2):
    print('check_class1_class2(%r,%r)' % (id_ob1, id_ob2))


@for_all_class1_dynamic
def check_class1_dynamic(context, id_ob1, ob1):
    r = context.comp(report_class1, ob1)
    context.add_report(r, 'report_class1_single')

@for_all_class1_class2_dynamic
def check_class1_class2_dynamic(context, id_ob1, ob1, id_ob2, ob2):
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