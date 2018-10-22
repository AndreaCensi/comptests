import itertools

from contracts import contract
from contracts.utils import describe_value

from compmake.jobs.storage import get_job_cache, get_job_userobject
from compmake.structures import Cache
from reprep import Report

from .results import PartiallySkipped, Skipped

__all__ = [
    'report_results_single',
    'report_results_pairs',
    'report_results_pairs_jobs',
]


@contract(results='dict(str:*)')
def report_results_single(func, objspec_name, results):

    def get_string_result(res):
        if res is None:
            s = 'ok'
        elif isinstance(res, Skipped):
            s = 'skipped'
        elif isinstance(res, PartiallySkipped):
            parts = res.get_skipped_parts()
            s = 'no ' + ','.join(parts)
        else:
            print('how to interpret %s? ' % describe_value(res))
            s = '?'
        return s

    r = Report()
    if not results:
        r.text('warning', 'no test objects defined')
        return r

    rows = []
    data = []
    for id_object, res in list(results.items()):
        rows.append(id_object)

        data.append([get_string_result(res)])

    r.table('summary', rows=rows, data=data)
    return r


@contract(results='dict(tuple(str,str):*)')
def report_results_pairs(func, objspec1_name, objspec2_name, results):
    reason2symbol = {}

    def get_string_result(res):
        if res is None:
            s = 'ok'
        elif isinstance(res, Skipped):
            s = 'skipped'
            reason = res.get_reason()
            if not reason in reason2symbol:
                reason2symbol[reason] = len(reason2symbol) + 1
            s += '(%s)' % reason2symbol[reason]

        elif isinstance(res, PartiallySkipped):
            parts = res.get_skipped_parts()
            s = 'no ' + ','.join(parts)
        else:
            print('how to interpret %s? ' % describe_value(res))
            s = '?'
        return s

    r = Report()
    if not results:
        r.text('warning', 'no test objects defined')
        return r

    rows = sorted(set([a for a, _ in results]))
    cols = sorted(set([b for _, b in results]))
    data = [[None for a in range(len(cols))] for b in range(len(rows))]
    # a nice bug: data = [[None * len(cols)] * len(rows)

    for ((i, id_object1), (j, id_object2)) in itertools.product(enumerate(rows), enumerate(cols)):
        res = results[(id_object1, id_object2)]
        data[i][j] = get_string_result(res)

    r.table('summary', rows=rows, data=data, cols=cols)

    expl = ""
    for reason, symbol in list(reason2symbol.items()):
        expl += '(%s): %s\n' % (symbol, reason)
    r.text('notes', expl)

    return r


@contract(jobs='dict(tuple(str,str):str)')
def report_results_pairs_jobs(context, func, objspec1_name, objspec2_name, jobs):
    """ This version gets the jobs ID """
    reason2symbol = {}

    def get_string_result(res):
        if res is None:
            s = 'ok'
        elif isinstance(res, Skipped):
            s = 'skipped'
            reason = res.get_reason()
            if not reason in reason2symbol:
                reason2symbol[reason] = len(reason2symbol) + 1
            s += '(%s)' % reason2symbol[reason]

        elif isinstance(res, PartiallySkipped):
            parts = res.get_skipped_parts()
            s = 'no ' + ','.join(parts)
        else:
            print('how to interpret %s? ' % describe_value(res))
            s = '?'
        return s

    r = Report()
    if not jobs:
        r.text('warning', 'no test objects defined')
        return r

    rows = sorted(set([a for a, _ in jobs]))
    cols = sorted(set([b for _, b in jobs]))
    data = [[None for a in range(len(cols))] for b in range(len(rows))]
    # a nice bug: data = [[None * len(cols)] * len(rows)

    db = context.get_compmake_db()

    comb = itertools.product(enumerate(rows), enumerate(cols))
    for ((i, id_object1), (j, id_object2)) in comb:
        job_id = jobs[(id_object1, id_object2)]
        cache = get_job_cache(job_id, db)

        if cache.state == Cache.DONE:
            res = get_job_userobject(job_id, db)
            s = get_string_result(res)
        elif cache.state == Cache.FAILED:
            s = 'FAIL'
        elif cache.state == Cache.BLOCKED:
            s = 'blocked'
#         elif cache.state == Cache.IN_PROGRESS:
#             s = '(in progress)'
        elif cache.state == Cache.NOT_STARTED:
            s = ' '
        else:
            s = '?'

        data[i][j] = s

    r.table('summary', rows=rows, data=data, cols=cols)

    expl = ""
    for reason, symbol in list(reason2symbol.items()):
        expl += '(%s): %s\n' % (symbol, reason)
    r.text('notes', expl)

    return r
