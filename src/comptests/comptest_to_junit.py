import os.path
from dataclasses import dataclass
from typing import Any, Literal, Mapping, Set, cast

import yaml
from junit_xml import TestCase, TestSuite, to_xml_report_string

from compmake import CMJobID, Cache, StorageFilesystem, all_jobs, get_job_cache
from zuper_commons.apps import ZArgumentParser
from zuper_commons.cmds import ExitCode
from zuper_commons.fs import DirPath, make_sure_dir_exists
from zuper_commons.text import joinlines, remove_escapes
from zuper_commons.types import check_isinstance
from zuper_utils_asyncio import SyncTaskInterface
from zuper_zapp import ZappEnv, zapp1
from zuper_zapp_interfaces import get_fs2

TestStatusString = Literal["test_success", "test_skipped", "test_failed", "test_error", "test_not_started", "test_blocked"]
TEST_SUCCESS: TestStatusString = "test_success"
TEST_SKIPPED: TestStatusString = "test_skipped"
TEST_FAILED: TestStatusString = "test_failed"
TEST_ERROR: TestStatusString = "test_error"
TEST_NOT_STARTED: TestStatusString = "test_not_started"
TEST_BLOCKED: TestStatusString = "test_blocked"


@zapp1()
async def comptest_to_junit_main(ze: ZappEnv) -> ExitCode:
    fs2 = await get_fs2(ze.sti)
    ze.sti.started()
    logger = ze.sti.logger

    parser = ZArgumentParser()
    # parser.add_argument("--db", required=True, type=str, help="Output file")
    parser.add_argument("--output", required=True, type=str, help="Output file")
    parser.add_argument(
        "--fail-if-failed",
        default=False,
        action="store_true",
        help="Returns nonzero exit code if there are failed or errored tests",
    )
    parser.add_argument("--known-failures", type=str, help="yaml file with dict known failures")
    parser.add_argument("--output-txt", type=str, help="Output file")

    parsed, rest = parser.parse_known_args(args=ze.args)  # ok

    if not rest:
        msg = "Require the path to a Compmake DB."
        logger.user_error(msg)
        return ExitCode.WRONG_ARGUMENTS

    dirname = cast(DirPath, rest[0])
    db = StorageFilesystem(dirname, compress=True)  # OK: comptests to junit

    jobs = sorted(all_jobs(db))

    if len(jobs) < 10:
        msg = "Could not enough jobs, compressed or not."
        logger.error(msg, n=len(jobs), dirname=dirname)
        return ExitCode.WRONG_ARGUMENTS

    known_failures: dict[CMJobID, Any] = {}
    if parsed.known_failures:
        if not os.path.exists(parsed.known_failures):
            msg = f"File {parsed.known_failures} does not exist."
            logger.error(msg)
            return ExitCode.WRONG_ARGUMENTS
        with open(parsed.known_failures) as f:
            known_failures = yaml.load(f, Loader=yaml.FullLoader)
            logger.info(f"Loaded {len(known_failures)} known failures.")
    tcr = await junit_xml(ze.sti, db, known_failures=set(known_failures))
    stats_reduce: Mapping[TestStatusString, int] = {k: len(v) for k, v in tcr.stats.items()}
    ze.sti.logger.info(output=parsed.output, stats_reduce=stats_reduce)

    fn = parsed.output
    ze.sti.logger.info(f"Writing XML report to {fn}")
    xml = to_xml_report_string([tcr.test_suite])
    async with fs2.session("comptest_to_junit_main") as fs:
        await fs.write_str(parsed.output, xml)

    if parsed.output_txt:
        for status in [TEST_SUCCESS, TEST_SKIPPED, TEST_FAILED, TEST_ERROR]:
            bn, ext = os.path.splitext(parsed.output_txt)
            fn = f"{bn}_{status}{ext}"
            res = []
            tc: TestCase
            for job_id, cr in tcr.job2cr.items():
                if cr.status == status:
                    res.append(job_id)
            if not res:
                logger.info(f"{status}: {len(res)} jobs ")
            else:
                dn = os.path.dirname(fn)
                make_sure_dir_exists(dn)
                with open(fn, "w") as f:
                    f.write(" ".join(sorted(res)))
                logger.info(f"{status:>16}: {len(res):>8} jobs - written to {fn}")

    n_should_exit = stats_reduce["test_failed"] + stats_reduce["test_error"]
    if n_should_exit > 0 and parsed.fail_if_failed:
        return ExitCode.OTHER_EXCEPTION
    return ExitCode.OK


@dataclass
class JUnitResults:
    test_suite: TestSuite
    stats: Mapping[TestStatusString, set[CMJobID]]
    job2cr: "dict[CMJobID, ClassificationResult]"


# @dataclass
# class DBResults:
#     jur: JUnitResults
#
#     job_statuses: dict[CMJobID, TestStatusString]
#     known_failures: set[CMJobID]


async def junit_xml(sti: SyncTaskInterface, compmake_db: StorageFilesystem, known_failures: Set[str]) -> JUnitResults:
    logger = sti.logger
    from junit_xml import TestSuite

    jobs = list(all_jobs(compmake_db))
    logger.info(f"Loaded {len(jobs)} jobs")

    test_cases = []

    stats: dict[TestStatusString, set[CMJobID]] = {
        "test_success": set(),
        "test_skipped": set(),
        "test_failed": set(),
        "test_error": set(),
        TEST_NOT_STARTED: set(),
        TEST_BLOCKED: set(),
    }
    job2cr = {}
    for job_id in jobs:
        cache = get_job_cache(job_id, db=compmake_db)
        if cache.state == Cache.NOT_STARTED:
            stats[TEST_NOT_STARTED].add(job_id)
            continue
        if cache.state == Cache.BLOCKED:
            stats[TEST_BLOCKED].add(job_id)
            continue

        r = junit_test_case_from_compmake(compmake_db, job_id, known_failures)
        job2cr[job_id] = r

        stats[r.status].add(job_id)
        test_cases.append(r.tc)

    if stats[TEST_NOT_STARTED]:
        tc = TestCase(
            name=f"not_started-{len(stats[TEST_NOT_STARTED])}",
            classname=None,
            elapsed_sec=None,
            stdout="",
            stderr=joinlines(sorted(stats[TEST_NOT_STARTED])),
        )
        test_cases.append(tc)

    if stats[TEST_BLOCKED]:
        tc = TestCase(
            name=f"blocked-{len(stats[TEST_BLOCKED])}",
            classname=None,
            elapsed_sec=None,
            stdout="",
            stderr=joinlines(sorted(stats[TEST_BLOCKED])),
        )
        test_cases.append(tc)

    ts = TestSuite("comptests_test_suite", test_cases)
    return JUnitResults(ts, dict(stats), job2cr)


@dataclass
class ClassificationResult:
    tc: TestCase
    status: TestStatusString


from . import logger


def junit_test_case_from_compmake(db: StorageFilesystem, job_id: CMJobID, known_failures: Set[str]) -> ClassificationResult:
    cache = get_job_cache(job_id, db=db)
    # if cache.state == Cache.DONE:  # and cache.done_iterations > 1:
    #     # elapsed_sec = cache.walltime_used
    #     elapsed_sec = cache.cputime_used
    # else:
    elapsed_sec = cache.cputime_used

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
    if cache.state == Cache.DONE:

        # TODO: look at object - Skipped result
        if job_id in known_failures:
            logger.error(f"Job {job_id} was marked as a known failure but it succeeded.")
            return ClassificationResult(tc, TEST_ERROR)

        if "Skip" in cache.result_type:
            message = "Returned Skipped"
            tc.add_skipped_info(message)

            return ClassificationResult(tc, TEST_SKIPPED)

        return ClassificationResult(tc, TEST_SUCCESS)

    if cache.state == Cache.FAILED:
        message = remove_escapes(cache.exception)
        output = (cache.exception or "") + "\n" + (cache.backtrace or "")
        output = remove_escapes(output)

        max_length = 2048
        message = message[:max_length] + " ... " if len(message) > max_length else ""
        output = output[:max_length] + " ... " if len(message) > max_length else ""
        if job_id in known_failures:
            tc.add_skipped_info(message)
            logger.info(f"Job {job_id} is a known failure.")
            return ClassificationResult(tc, TEST_SKIPPED)
        elif "SkipTest" in message:
            tc.add_skipped_info(message)
            return ClassificationResult(tc, TEST_SKIPPED)
        elif cache.is_timed_out():
            tc.add_skipped_info(message)
            return ClassificationResult(tc, TEST_SKIPPED)
        elif cache.is_oom():
            tc.add_skipped_info(message)
            return ClassificationResult(tc, TEST_SKIPPED)
        else:
            tc.add_failure_info(message, output)
            return ClassificationResult(tc, TEST_FAILED)

    if cache.state == Cache.PROCESSING:
        message = "Job still processing. Probably interrupted."
        if job_id in known_failures:
            tc.add_skipped_info(message)
            return ClassificationResult(tc, TEST_SKIPPED)
        # tc.add_error_info(message)
        # return ClassificationResult(tc, TEST_ERROR)
        tc.add_skipped_info(message)
        return ClassificationResult(tc, TEST_SKIPPED)

    if cache.state == Cache.NOT_STARTED:
        message = "Job not started."
        tc.add_error_info(message)
        return ClassificationResult(tc, TEST_ERROR)
    if cache.state == Cache.BLOCKED:
        message = "Job is blocked."
        tc.add_skipped_info(message)
        return ClassificationResult(tc, TEST_SKIPPED)

    raise AssertionError(f"Unknown state {cache.state}")
