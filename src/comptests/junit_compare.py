import os.path
import re
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

from zuper_commons.apps import ZArgumentParser
from zuper_commons.cmds import ExitCode
from zuper_zapp import zapp1, ZappEnv


@zapp1()
async def junit_compare_main(ze: ZappEnv) -> ExitCode:
    logger = ze.sti.logger
    parser = ZArgumentParser()
    parser.add_argument("--ignore-std", default=False, action="store_true")

    ignores = [
        ".*_dynreports_.*",
        ".*-context$",
        ".*-mcdplib_tst_setup_spec$",
        ".*-comptests$",
        ".*-jobs_comptests-.*_tests$",
        ".*-nosesingle$",
        ".*-define_tsts_rendering$",
        ".*-sources-mcdplib_tst_setup_sources$",
        ".*-define_tsts_for_repo$",
        # "^ct-mcdp_tests-jobs_comptests-[^-]+$",
    ]

    parsed, rest = parser.parse_known_args(args=ze.args)  # ok
    ignore_std = parsed.ignore_std
    jobs: dict[str, set[str]] = {}
    tc2time: dict[str, float] = {}
    tc2bn: dict[str, set[str]] = defaultdict(set)
    for fn in rest:
        bn = os.path.basename(fn)
        jobs[fn] = set()
        # Passing the path of the
        # xml document to enable the
        # parsing process
        tree = ET.parse(fn)

        # getting the parent tag of
        # the xml document
        root = tree.getroot()

        for testsuite in root.findall("testsuite"):
            for testcase in testsuite.findall("testcase"):
                name = testcase.attrib["name"]

                # ttype = testcase.attrib.get("type", 'success')
                # if ttype == "skip":
                #     t = 0
                # else:

                t = float(testcase.attrib.get("time", 0))

                if ignore_std:
                    if any(re.match(ignore, name) for ignore in ignores):
                        continue
                jobs[fn].add(name)
                tc2bn[name].add(bn)
                tc2time[name] = t
        print(f"{fn}: {len(jobs[fn])}")
    counter = Counter()
    for fn in jobs:
        counter.update(jobs[fn])

    ntot = sum(len(jobs[fn]) for fn in jobs)

    ndups = 0
    for k in sorted(counter):
        v = counter[k]
        if v > 1:
            print(f"{v} copies of {k}")
            # print(f"{v} copies of {k} in {tc2bn[k]}")
            ndups += 1

    print(f"found {ndups} duplicates")
    N = 20
    names = sorted(tc2time.keys(), reverse=True, key=tc2time.get)

    print()
    print(f"Top {N} jobs by time")
    for name in names[:N]:
        print(f"{tc2time[name]:.2f} {name:<40} ")

    print(f"Total number of tests: {ntot}")

    return ExitCode.OK


if __name__ == "__main__":
    junit_compare_main()
