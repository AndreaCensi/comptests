import os.path
from collections.abc import Mapping
from dataclasses import dataclass
from typing import AbstractSet, Any, cast, Literal

import yaml
from junit_xml import TestCase, TestSuite, to_xml_report_string

from compmake import all_jobs, Cache, CacheQueryDB, CMJobID, StorageFilesystem
from zuper_commons.apps import ZArgumentParser
from zuper_commons.cmds import ExitCode
from zuper_commons.fs import DirPath, make_sure_dir_exists
from zuper_commons.text import joinlines, remove_escapes
from zuper_commons.types import check_isinstance
from zuper_commons.ui import duration_compact, size_compact
from zuper_utils_asyncio import SyncTaskInterface
from zuper_zapp import zapp1, ZappEnv
from zuper_zapp_interfaces import get_fs2

TestStatusString = Literal[
    "test_success", "test_skipped", "test_failed", "test_error", "test_not_started", "test_blocked", "test_timedout", "test_oom"
]
TEST_SUCCESS: TestStatusString = "test_success"
TEST_SKIPPED: TestStatusString = "test_skipped"
TEST_FAILED: TestStatusString = "test_failed"
TEST_ERROR: TestStatusString = "test_error"
TEST_NOT_STARTED: TestStatusString = "test_not_started"
TEST_BLOCKED: TestStatusString = "test_blocked"
TEST_TIMEDOUT: TestStatusString = "test_timedout"
TEST_OOM: TestStatusString = "test_oom"


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
    parser.add_argument("--warn-if-known-failures-unknown", default=False, action="store_true")
    parser.add_argument("--output-txt", type=str, help="Output file")

    parsed, rest = parser.parse_known_args(args=ze.args)  # ok

    parsed_known_failures = parsed.known_failures
    parsed_output = parsed.output
    parsed_output_txt = parsed.output_txt
    parsed_fail_if_failed = parsed.fail_if_failed
    warn_if_known_failures_unknown = parsed.warn_if_known_failures_unknown

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
            logger.user_info(f"Loaded {len(known_failures)} known failures.")

    unknown_known_failures = set(known_failures) - set(jobs)
    testsuite_name = parsed_output
    r = await junit_xml(ze.sti, testsuite_name, db, known_failures=set(known_failures))
    tcr = r.jur

    used_known_failures = r.used_known_failures
    if used_known_failures:
        logger.user_info(f"Used {len(used_known_failures)} known failures.", used=joinlines(sorted(used_known_failures)))

    if unknown_known_failures:
        if warn_if_known_failures_unknown:
            logger.warn(f"Unknown known failures, not present in job list", unknown=joinlines(sorted(unknown_known_failures)))

    stats_reduce: Mapping[TestStatusString, int] = {k: len(v) for k, v in tcr.stats.items()}

    xml = to_xml_report_string([tcr.test_suite])

    postfix = "".join(f"-{k}_{v}" for k, v in stats_reduce.items() if v > 0 and k != TEST_SUCCESS)

    if used_known_failures:
        postfix += f"-used_known_failures_{len(used_known_failures)}"
    postfix = postfix.replace("test_", "")
    xml_fn = os.path.splitext(parsed_output)[0] + postfix + ".xml"
    logger.user_info(output=xml_fn, stats_reduce=stats_reduce)
    logger.user_info(f"Writing XML report to {xml_fn}")

    async with fs2.session("comptest_to_junit_main") as fs:
        await fs.write_str(xml_fn, xml)

    if parsed_output_txt:
        sec2statuses = {
            TEST_SKIPPED: {TEST_SKIPPED},
            TEST_FAILED: {TEST_FAILED},
            TEST_ERROR: {TEST_ERROR},
            TEST_NOT_STARTED: {TEST_NOT_STARTED},
            TEST_TIMEDOUT: {TEST_TIMEDOUT},
            TEST_OOM: {TEST_OOM},
            TEST_SUCCESS: {TEST_SUCCESS},
            "test_all": {TEST_SKIPPED, TEST_FAILED, TEST_ERROR, TEST_NOT_STARTED, TEST_TIMEDOUT, TEST_OOM, TEST_SUCCESS},
        }

        for sec_name, statuses in sec2statuses.items():
            # for status in [TEST_SKIPPED, TEST_FAILED, TEST_ERROR, TEST_NOT_STARTED, TEST_TIMEDOUT, TEST_OOM, TEST_SUCCESS]:  # TEST_SUCCESS,
            bn, ext = os.path.splitext(parsed_output_txt)

            res = []
            tc: TestCase
            n = 0
            for job_id, cr in tcr.job2cr.items():
                if cr.status in statuses:
                    res.append(job_id)
                    n += 1

            fn = f"{bn}_{sec_name}_{n}{ext}"
            if not res:
                logger.user_info(f"{sec_name}: {len(res)} jobs ")
            else:
                if n:
                    comment = f" # {fn}"
                    make_sure_dir_exists(fn)
                    with open(fn, "w") as f:
                        res = [_.ljust(200) + comment for _ in res]

                        f.write(joinlines(sorted(res)))
                    logger.user_info(f"{sec_name:>16}: {len(res):>8} jobs - written to {fn}")

    n_should_exit = stats_reduce[TEST_FAILED] + stats_reduce[TEST_ERROR]
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
    sti: SyncTaskInterface, testsuite_name: str, compmake_db: StorageFilesystem, known_failures: set[str]
) -> ProcRes:
    logger = sti.logger
    from junit_xml import TestSuite

    test_cases = []

    used_known_failures = set()
    add_not_started_as_failed = False  # TODO
    add_blocked_as_failed = False  # TODO
    stats: dict[TestStatusString, set[CMJobID]] = {
        TEST_SUCCESS: set(),
        TEST_SKIPPED: set(),
        TEST_FAILED: set(),
        TEST_ERROR: set(),
        TEST_NOT_STARTED: set(),
        TEST_BLOCKED: set(),
        TEST_TIMEDOUT: set(),
        TEST_OOM: set(),
    }
    job2cr = {}
    cq = CacheQueryDB(compmake_db)
    with cq.session() as session:
        jobs = session.all_jobs()
        logger.user_info(f"Loaded {len(jobs)} jobs")

        for job_id in jobs:
            cache = session.get_job_cache(job_id)
            # cache = get_job_cache(job_id, db=compmake_db)
            if cache.state == Cache.NOT_STARTED:
                stats[TEST_NOT_STARTED].add(job_id)
                continue
            if cache.state == Cache.BLOCKED:
                stats[TEST_BLOCKED].add(job_id)
                continue

            r = junit_test_case_from_compmake(cache, job_id, known_failures, used_known_failures)
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
    cache: Cache,
    job_id: CMJobID,
    known_failures: AbstractSet[str],
    used_known_failures: set[str],
) -> ClassificationResult:
    elapsed_sec = cache.cputime_used

    check_isinstance(cache.captured_stderr, (type(None), str))
    check_isinstance(cache.captured_stdout, (type(None), str))
    check_isinstance(cache.exception, (type(None), str))
    stderr: str = "\n" + remove_escapes(cache.captured_stderr or "[no stderr captured]") + "\n"
    stdout: str = "\n" + remove_escapes(cache.captured_stdout or "[no stdout captured]") + "\n"

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
            logger0.user_error(f"Job {job_id} was marked as a known failure but it succeeded.")
            used_known_failures.add(job_id)
            return ClassificationResult(tc, TEST_ERROR)

        if "Skip" in cache.result_type:
            message = "Returned Skipped"
            tc.add_skipped_info(message)

            return ClassificationResult(tc, TEST_SKIPPED)

        return ClassificationResult(tc, TEST_SUCCESS)

    elif cache.state == Cache.FAILED:
        message = remove_escapes(cache.exception or "")
        output = (cache.exception or "") + "\n" + (cache.backtrace or "")
        output = remove_escapes(output)

        max_length = 16000
        message = message[:max_length] + ("\n ... clipped ...\n\n" if len(message) > max_length else "")

        output = output[:max_length] + ("\n ... clipped ...\n\n " if len(message) > max_length else "")

        if job_id in known_failures:
            tc.add_skipped_info(message)
            logger0.user_info(f"Job {job_id} is a known failure.")
            used_known_failures.add(job_id)
            return ClassificationResult(tc, TEST_SKIPPED)
        elif "SkipTest" in message:
            tc.add_skipped_info(message, output)
            return ClassificationResult(tc, TEST_SKIPPED)
        elif elapsed := cache.is_timed_out():
            message = "Job timed out after " + duration_compact(elapsed)
            tc.add_skipped_info(message, output)
            return ClassificationResult(tc, TEST_TIMEDOUT)
        elif b := cache.is_oom():
            message = f"OOM: {size_compact(b)}"
            tc.add_skipped_info(message, output)
            return ClassificationResult(tc, TEST_OOM)
        elif cache.is_skipped_test():
            message = "Skipped test."
            tc.add_skipped_info(message, output)
            return ClassificationResult(tc, TEST_SKIPPED)
        else:
            tc.add_failure_info(message, output)
            return ClassificationResult(tc, TEST_FAILED)

    elif cache.state == Cache.PROCESSING:
        message = "Job still processing. Probably interrupted."
        if job_id in known_failures:
            tc.add_skipped_info(message)
            return ClassificationResult(tc, TEST_SKIPPED)
        # tc.add_error_info(message)
        # return ClassificationResult(tc, TEST_ERROR)
        tc.add_skipped_info(message)
        return ClassificationResult(tc, TEST_SKIPPED)

    elif cache.state == Cache.NOT_STARTED:
        message = "Job not started."
        tc.add_error_info(message)
        return ClassificationResult(tc, TEST_ERROR)
    elif cache.state == Cache.BLOCKED:
        message = "Job is blocked."
        tc.add_skipped_info(message)
        return ClassificationResult(tc, TEST_SKIPPED)
    else:
        raise AssertionError(f"Unknown state {cache.state}")
