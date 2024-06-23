import os.path
from dataclasses import dataclass
from typing import AbstractSet, Any, Literal, Mapping, Set, cast

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

    parsed_known_failures = parsed.known_failures
    parsed_output = parsed.output
    parsed_output_txt = parsed.output_txt
    parsed_fail_if_failed = parsed.fail_if_failed

    del parsed

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
    if parsed_known_failures:
        if not os.path.exists(parsed_known_failures):
            msg = f"File {parsed_known_failures} does not exist."
            logger.error(msg)
            return ExitCode.WRONG_ARGUMENTS
        with open(parsed_known_failures) as f:
            known_failures = yaml.load(f, Loader=yaml.FullLoader)
            logger.info(f"Loaded {len(known_failures)} known failures.")
    testsuite_name = parsed_output
    r = await junit_xml(ze.sti, testsuite_name, db, known_failures=set(known_failures))
    tcr = r.jur

    used_known_failures = r.used_known_failures
    if used_known_failures:
        logger.info(f"Used {len(used_known_failures)} known failures.", used=used_known_failures)
    stats_reduce: Mapping[TestStatusString, int] = {k: len(v) for k, v in tcr.stats.items()}

    xml = to_xml_report_string([tcr.test_suite])

    postfix = "".join(f"-{k}_{v}" for k, v in stats_reduce.items() if v > 0 and k != "test_success")

    if used_known_failures:
        postfix += f"-used_known_failures_{len(used_known_failures)}"
    postfix = postfix.replace("test_", "")
    xml_fn = os.path.splitext(parsed_output)[0] + postfix + ".xml"
    logger.info(output=xml_fn, stats_reduce=stats_reduce)
    logger.info(f"Writing XML report to {xml_fn}")

    async with fs2.session("comptest_to_junit_main") as fs:
        await fs.write_str(xml_fn, xml)

    if parsed_output_txt:
        for status in [TEST_SKIPPED, TEST_FAILED, TEST_ERROR]:  # TEST_SUCCESS,
            bn, ext = os.path.splitext(parsed_output_txt)

            res = []
            tc: TestCase
            n = 0
            for job_id, cr in tcr.job2cr.items():
                if cr.status == status:
                    res.append(job_id)
                    n += 1

            fn = f"{bn}_{status}_{n}{ext}"
            if not res:
                logger.info(f"{status}: {len(res)} jobs ")
            else:
                if n:
                    dn = os.path.dirname(fn)
                    make_sure_dir_exists(dn)
                    with open(fn, "w") as f:
                        f.write(" ".join(sorted(res)))
                    logger.info(f"{status:>16}: {len(res):>8} jobs - written to {fn}")

    n_should_exit = stats_reduce["test_failed"] + stats_reduce["test_error"]
    if n_should_exit > 0 and parsed_fail_if_failed:
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
@dataclass
class ProcRes:
    jur: JUnitResults
    used_known_failures: set[CMJobID]


async def junit_xml(
    sti: SyncTaskInterface, testsuite_name: str, compmake_db: StorageFilesystem, known_failures: Set[str]
) -> ProcRes:
    logger = sti.logger
    from junit_xml import TestSuite

    jobs = list(all_jobs(compmake_db))
    logger.info(f"Loaded {len(jobs)} jobs")

    test_cases = []

    used_known_failures = set()
    add_not_started_as_failed = False  # TODO
    add_blocked_as_failed = False  # TODO
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

        r = junit_test_case_from_compmake(compmake_db, job_id, known_failures, used_known_failures)
        # r.tc.stderr = cache.captured_stderr or ""
        # r.tc.stdout = cache.captured_stdout or ""
        job2cr[job_id] = r

        stats[r.status].add(job_id)
        test_cases.append(r.tc)

    if add_not_started_as_failed:
        if stats[TEST_NOT_STARTED]:
            tc = TestCase(
                name=f"not_started-{len(stats[TEST_NOT_STARTED])}",
                classname=None,
                elapsed_sec=None,
                stdout="",
                stderr="",
            )
            tc.add_error_info(joinlines(sorted(stats[TEST_NOT_STARTED])))
            test_cases.append(tc)

    if add_blocked_as_failed:
        if stats[TEST_BLOCKED]:
            tc = TestCase(
                name=f"blocked-{len(stats[TEST_BLOCKED])}",
                classname=None,
                elapsed_sec=None,
                stdout="",
                stderr="",
            )
            tc.add_error_info(joinlines(sorted(stats[TEST_BLOCKED])))
            test_cases.append(tc)

    ts = TestSuite(testsuite_name, test_cases)
    jur = JUnitResults(ts, dict(stats), job2cr)

    return ProcRes(jur, used_known_failures)


@dataclass
class ClassificationResult:
    tc: TestCase
    status: TestStatusString


from . import logger as logger0


def junit_test_case_from_compmake(
    db: StorageFilesystem, job_id: CMJobID, known_failures: AbstractSet[str], used_known_failures: set[str]
) -> ClassificationResult:
    cache = get_job_cache(job_id, db=db)
    # if cache.state == Cache.DONE:  # and cache.done_iterations > 1:
    #     # elapsed_sec = cache.walltime_used
    #     elapsed_sec = cache.cputime_used
    # else:
    elapsed_sec = cache.cputime_used

    check_isinstance(cache.captured_stderr, (type(None), str))
    check_isinstance(cache.captured_stdout, (type(None), str))
    check_isinstance(cache.exception, (type(None), str))
    stderr: str = remove_escapes(cache.captured_stderr or "no stderr")
    stdout: str = remove_escapes(cache.captured_stdout or "no stdout")

    tc = TestCase(
        name=job_id,
        classname=None,
        elapsed_sec=elapsed_sec,
        stdout=f"\n\nStdout:\n{stdout}",
        stderr=f"\n\nStdout:\n{stderr}",
    )
    if cache.state == Cache.DONE:

        # TODO: look at object - Skipped result
        if job_id in known_failures:
            logger0.error(f"Job {job_id} was marked as a known failure but it succeeded.")
            used_known_failures.add(job_id)
            return ClassificationResult(tc, TEST_ERROR)

        if "Skip" in cache.result_type:
            message = "Returned Skipped"
            tc.add_skipped_info(message)

            return ClassificationResult(tc, TEST_SKIPPED)

        return ClassificationResult(tc, TEST_SUCCESS)

    if cache.state == Cache.FAILED:
        message = remove_escapes(cache.exception or "")
        output = (cache.exception or "") + "\n" + (cache.backtrace or "")
        output = remove_escapes(output)

        max_length = 16000
        message = message[:max_length] + "\n ... clipped ...\n\n" if len(message) > max_length else ""

        output = output[:max_length] + "\n ... clipped ...\n\n " if len(message) > max_length else ""

        if job_id in known_failures:
            tc.add_skipped_info(message)
            logger0.info(f"Job {job_id} is a known failure.")
            used_known_failures.add(job_id)
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
        elif cache.is_skipped_test():
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
