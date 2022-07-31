import argparse
from dataclasses import dataclass
from typing import cast, Literal, Mapping

from junit_xml import TestCase, TestSuite, to_xml_report_string

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
        help="Returns nonzero exit code if there are failed or errored tests",
    )
    parsed, rest = parser.parse_known_args(args=ze.args)

    if not rest:
        msg = "Require the path to a Compmake DB."
        logger.user_error(msg)
        return ExitCode.WRONG_ARGUMENTS

    dirname = cast(DirPath, rest[0])
    db = StorageFilesystem(dirname, compress=True)

    jobs = sorted(all_jobs(db))

    if len(jobs) < 10:
        msg = "Could not enough jobs, compressed or not."
        logger.error(msg, n=len(jobs), dirname=dirname)
        return ExitCode.WRONG_ARGUMENTS

    tcr = await junit_xml(ze.sti, db)
    stats_reduce: Mapping[TestStatusString, int] = {k: len(v) for k, v in tcr.stats.items()}
    ze.sti.logger.info(output=parsed.output, stats_reduce=stats_reduce)

    fn = parsed.output
    ze.sti.logger.info(f"Writing XML report to {fn}")
    xml = to_xml_report_string([tcr.test_suite])
    async with fs2.session("comptest_to_junit_main") as fs:
        await fs.write_str(parsed.output, xml)

    n_should_exit = stats_reduce["test_failed"] + stats_reduce["test_error"]
    if n_should_exit > 0 and parsed.fail_if_failed:
        return ExitCode.OTHER_EXCEPTION
    return ExitCode.OK


TestStatusString = Literal["test_success", "test_skipped", "test_failed", "test_error"]


@dataclass
class JUnitResults:
    test_suite: TestSuite
    stats: Mapping[TestStatusString, set[CMJobID]]


async def junit_xml(sti: SyncTaskInterface, compmake_db: StorageFilesystem) -> JUnitResults:
    logger = sti.logger
    from junit_xml import TestSuite

    jobs = list(all_jobs(compmake_db))
    logger.info(f"Loaded {len(jobs)} jobs")

    test_cases = []

    stats: dict[TestStatusString, set[CMJobID]] = {}
    stats["test_success"] = set()
    stats["test_skipped"] = set()
    stats["test_failed"] = set()
    stats["test_error"] = set()

    for job_id in jobs:
        r = junit_test_case_from_compmake(compmake_db, job_id)
        stats[r.status].add(job_id)
        test_cases.append(r.tc)

    ts = TestSuite("comptests_test_suite", test_cases)
    return JUnitResults(ts, dict(stats))


@dataclass
class ClassificationResult:
    tc: TestCase
    status: TestStatusString


def junit_test_case_from_compmake(db: StorageFilesystem, job_id: CMJobID) -> ClassificationResult:
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
    if cache.state == Cache.DONE:
        # TODO: look at object - Skipped result
        return ClassificationResult(tc, "test_success")

    if cache.state == Cache.FAILED:
        message = cache.exception
        output = (cache.exception or "") + "\n" + (cache.backtrace or "")
        tc.add_failure_info(message, output)
        return ClassificationResult(tc, "test_failed")

    if cache.state == Cache.PROCESSING:
        message = "Job still processing. Probably interrupted."
        tc.add_error_info(message)
        return ClassificationResult(tc, "test_error")
    if cache.state == Cache.NOT_STARTED:
        message = "Job not started."
        tc.add_error_info(message)
        return ClassificationResult(tc, "test_error")

    if cache.state == Cache.BLOCKED:
        message = "Job is blocked."
        tc.add_skipped_info(message)
        return ClassificationResult(tc, "test_skipped")

    assert False, f"Unknown state {cache.state}"


if __name__ == "__main__":
    comptest_to_junit_main()
