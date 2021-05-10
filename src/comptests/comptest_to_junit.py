import sys

from compmake import all_jobs, Cache, CMJobID, get_job_cache, StorageFilesystem, UserError
from zuper_commons.cmds import ExitCode
from zuper_commons.types import check_isinstance
from zuper_utils_asyncio import SyncTaskInterface
from zuper_zapp import zapp1, ZappEnv


@zapp1()
async def comptest_to_junit_main(ze: ZappEnv) -> ExitCode:
    logger = ze.sti.logger
    args = ze.args
    if not args:
        msg = "Require the path to a Compmake DB."
        logger.user_error(msg)
        return ExitCode.WRONG_ARGUMENTS

    dirname = args[0]
    # try compressed
    # noinspection PyBroadException
    # try:
    db = StorageFilesystem(dirname, compress=True)
    # except Exception:
    #     db = StorageFilesystem(dirname, compress=False)

    jobs = list(all_jobs(db))

    if len(jobs) < 10:
        msg = "Could not enough jobs, compressed or not."
        logger.error(msg, n=len(jobs), dirname=dirname)
        return ExitCode.WRONG_ARGUMENTS

    s = await junit_xml(ze.sti, db)
    check_isinstance(s, str)
    s = s.encode("utf8")
    sys.stdout.buffer.write(s)


async def junit_xml(sti: SyncTaskInterface, compmake_db: StorageFilesystem):
    logger = sti.logger
    from junit_xml import TestSuite

    jobs = list(all_jobs(compmake_db))
    logger.info(f"Loaded {len(jobs)} jobs")

    test_cases = []
    for job_id in jobs:
        tc = junit_test_case_from_compmake(compmake_db, job_id)
        # logger.info(name=tc.name, status=tc.status)
        test_cases.append(tc)

    ts = TestSuite("comptests_test_suite", test_cases)

    res = TestSuite.to_xml_string([ts])
    return res


# def flatten_ascii(s):
#     if s is None:
#         return None
#     # if six.PY2:
#     #     # noinspection PyCompatibility
#     #     s = unicode(s, encoding='utf8', errors='replace')
#     #     s = s.encode('ascii', errors='ignore')
#     return s


def junit_test_case_from_compmake(db, job_id: CMJobID):
    from junit_xml import TestCase

    cache = get_job_cache(job_id, db=db)
    if cache.state == Cache.DONE:  # and cache.done_iterations > 1:
        # elapsed_sec = cache.walltime_used
        elapsed_sec = cache.cputime_used
    else:
        elapsed_sec = None

    check_isinstance(cache.captured_stderr, (type(None), str))
    check_isinstance(cache.captured_stdout, (type(None), str))
    check_isinstance(cache.exception, (type(None), str))
    stderr = remove_escapes(cache.captured_stderr)
    stdout = remove_escapes(cache.captured_stdout)

    tc = TestCase(
        name=job_id,
        classname=None,
        elapsed_sec=elapsed_sec,
        stdout=stdout,
        stderr=stderr,
    )

    if cache.state == Cache.FAILED:
        message = cache.exception
        output = cache.exception + "\n" + cache.backtrace
        tc.add_failure_info(message, output)

    return tc


def remove_escapes(s):
    if s is None:
        return None
    import re

    escape = re.compile("\x1b\[..?m")
    return escape.sub("", s)


if __name__ == "__main__":
    comptest_to_junit_main()
