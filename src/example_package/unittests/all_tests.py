from typing import NoReturn

from comptests import comptest, comptest_dynamic, comptest_fails
from quickapp import QuickAppContext
from reprep import Report
from .generation import (
    for_all_class1,
    for_all_class1_class2,
    for_all_class1_class2_dynamic,
    for_all_class1_dynamic,
    for_some_class1,
    for_some_class1_class2,
)


@comptest
def simple_check() -> None:
    pass


@comptest
def actual_failure() -> NoReturn:
    msg = "This is a controlled failure."
    raise Exception(msg)


@comptest_dynamic
def dyn_simple_check(context: QuickAppContext) -> None:
    pass


@for_all_class1
def check_class1(id_ob: str, _: object) -> None:
    print("check_class1(%r)" % id_ob)


@for_some_class1("c1a")
def check_some_class1(id_ob: str, _: object) -> None:
    assert id_ob == "c1a"


@for_some_class1_class2("c1*", "c2*")
def check_some_class1_class2(id_ob1: str, _: object, id_ob2: str, _2: object) -> None:
    assert id_ob1 in ["c1a", "c1b"]
    assert id_ob2 == "c2a"


#
# @for_some_class1_class2('c1b', 'c2*')
# def check_some_class1_class2_2(id_ob1, _, id_ob2, _2):
#     assert id_ob1 == 'c1b'
#     assert id_ob2 == 'c2a'


@for_all_class1_class2
def check_all_class1_class2(id_ob1: str, _: object, id_ob2: str, _2: object) -> None:
    print("check_class1_class2(%r,%r)" % (id_ob1, id_ob2))


@for_all_class1_dynamic
def check_class1_dynamic(context: QuickAppContext, _: str, ob1: object) -> None:
    r = context.comp(report_class1, ob1)
    context.add_report(r, "report_class1_single")


@for_all_class1_class2_dynamic
def check_class1_class2_dynamic(context: QuickAppContext, _: str, ob1: object, _2: str, ob2: object) -> None:
    r = context.comp(report_class1, ob1)
    context.add_report(r, "report_class1")

    r = context.comp(report_class2, ob2)
    context.add_report(r, "report_class2")


def report_class1(ob1: object) -> Report:
    r = Report()
    r.text("ob1", "%s" % ob1)
    return r


def report_class2(ob2: object) -> Report:
    r = Report()
    r.text("ob2", "%s" % ob2)
    return r


# normal test
def test_dummy() -> None:
    pass


#
# @comptest
# def a_real_failure():
#     raise Exception('A failure')


@comptest_fails
def expected_failure() -> None:
    raise Exception("expected_failure")
