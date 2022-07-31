import argparse
import xml.etree.ElementTree as ET
from collections import Counter

from zuper_commons.cmds import ExitCode
from zuper_zapp import zapp1, ZappEnv
from zuper_zapp_interfaces import get_fs2


@zapp1()
async def junit_compare_main(ze: ZappEnv) -> ExitCode:
    fs2 = await get_fs2(ze.sti)
    logger = ze.sti.logger

    parser = argparse.ArgumentParser()
    # parser.add_argument("--db", required=True, type=str, help="Output file")
    # parser.add_argument("--output", required=True, type=str, help="Output file")
    # parser.add_argument(
    #     "--fail-if-failed",
    #     default=False,
    #     action="store_true",
    #     help="Returns nonzero exit code if there are failed or errored tests",
    # )
    parsed, rest = parser.parse_known_args(args=ze.args)
    jobs: dict[str, set[str]] = {}
    for fn in rest:
        jobs[fn] = set()
        # Passing the path of the
        # xml document to enable the
        # parsing process
        tree = ET.parse(fn)

        # getting the parent tag of
        # the xml document
        root = tree.getroot()

        print(root.tag, root.attrib)

        for testsuite in root.findall("testsuite"):
            for testcase in testsuite.findall("testcase"):
                jobs[fn].add(testcase.attrib["name"])
        print(f"{fn}: {len(jobs[fn])}")
    counter = Counter()
    for fn in jobs:
        counter.update(jobs[fn])

    ndups = 0
    for k, v in counter.items():
        if v > 1:
            print(f"{v} copies of {k}")
            ndups += 1

    print(f"found {ndups} duplicates")

    return ExitCode.OK


if __name__ == "__main__":
    junit_compare_main()
