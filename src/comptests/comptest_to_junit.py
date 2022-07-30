import argparse
from typing import cast, Tuple

from junit_xml import TestCase

from compmake import all_jobs, Cache, CMJobID, get_job_cache, StorageFilesystem
from zuper_commons.cmds import ExitCode
from zuper_commons.fs import DirPath
from zuper_commons.text import remove_escapes
from zuper_commons.types import check_isinstance
from zuper_utils_asyncio import SyncTaskInterface
from zuper_zapp import zapp1, ZappEnv
from zuper_zapp_interfaces import get_fs2


@zapp1()
async def comptest_to_junit_main(ze: ZappEnv) -> ExitCode:
    fs2 = await get_fs2(ze.sti)
    logger = ze.sti.logger

    parser = argparse.ArgumentParser()
    # parser.add_argument("--db", required=True, type=str, help="Output file")
    parser.add_argument("--output", required=True, type=str, help="Output file")
    parser.add_argument(
        "--fail-if-failed",
        default=False,
        action="store_true",
        help="Returns nonzero exit code if there are failed tests",
    )
    parsed, rest = parser.parse_known_args(args=ze.args)

    if not rest:
        msg = "Require the path to a Compmake DB."
        logger.user_error(msg)
        return ExitCode.WRONG_ARGUMENTS

    dirname = cast(DirPath, rest[0])
    db = StorageFilesystem(dirname, compress=True)

    jobs = list(all_jobs(db))

    if len(jobs) < 10:
        msg = "Could not enough jobs, compressed or not."
        logger.error(msg, n=len(jobs), dirname=dirname)
        return ExitCode.WRONG_ARGUMENTS

    nseen, nmarked, s = await junit_xml(ze.sti, db)

    async with fs2.session("comptest_to_junit_main") as fs:
        await fs.write_str(parsed.output, s)

    ze.sti.logger.info(nseen=nseen, nmarked=nmarked, output=parsed.output)
    if nmarked > 0 and parsed.fail_if_failed:
        return ExitCode.OTHER_EXCEPTION
    return ExitCode.OK


async def junit_xml(sti: SyncTaskInterface, compmake_db: StorageFilesystem) -> Tuple[int, int, str]:
    logger = sti.logger
    from junit_xml import TestSuite

    jobs = list(all_jobs(compmake_db))
    logger.info(f"Loaded {len(jobs)} jobs")

    test_cases = []
    nmarked = 0
    nseen = 0
    for job_id in jobs:
        nseen += 1
        marked_error, tc = junit_test_case_from_compmake(compmake_db, job_id)
        if marked_error:
            nmarked += 1
        # logger.info(name=tc.name, status=tc.status)
        test_cases.append(tc)

    ts = TestSuite("comptests_test_suite", test_cases)

    res = TestSuite.to_xml_string([ts])
    return nseen, nmarked, res


# def flatten_ascii(s):
#     if s is None:
#         return None
#     # if six.PY2:
#     #     # noinspection PyCompatibility
#     #     s = unicode(s, encoding='utf8', errors='replace')
#     #     s = s.encode('ascii', errors='ignore')
#     return s


def junit_test_case_from_compmake(db: StorageFilesystem, job_id: CMJobID) -> Tuple[bool, TestCase]:
    cache = get_job_cache(job_id, db=db)
    if cache.state == Cache.DONE:  # and cache.done_iterations > 1:
        # elapsed_sec = cache.walltime_used
        elapsed_sec = cache.cputime_used
    else:
        elapsed_sec = None

    check_isinstance(cache.captured_stderr, (type(None), str))
    check_isinstance(cache.captured_stdout, (type(None), str))
    check_isinstance(cache.exception, (type(None), str))
    stderr: str = remove_escapes(cache.captured_stderr or "")
    stdout: str = remove_escapes(cache.captured_stdout or "")

    tc = TestCase(
        name=job_id,
        classname=None,
        elapsed_sec=elapsed_sec,
        stdout=stdout,
        stderr=stderr,
    )
    marked_as_error = False
    failed = cache.state == Cache.FAILED
    if failed:
        marked_as_error = True
        message = cache.exception
        output = (cache.exception or "") + "\n" + (cache.backtrace or "")
        tc.add_failure_info(message, output)
    else:
        notdone = cache.state != Cache.DONE
        if notdone:
            marked_as_error = True
            tc.add_error_info(f"Not done: {Cache.state2desc[cache.state]} ")

    return marked_as_error, tc


if __name__ == "__main__":
    comptest_to_junit_main()
