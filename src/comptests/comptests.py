import asyncio
import os
from typing import Any, Callable, cast, Iterator, Optional

from conf_tools import GlobalConfig, import_name, reset_config
from quickapp import DecentParams, QuickApp, QuickAppContext
from zuper_commons.fs import AbsDirPath, abspath
from zuper_commons.types import ZException, ZValueError
from zuper_utils_asyncio import SyncTaskInterface
from . import logger
from .find_modules_imp import find_modules, find_modules_main
from .nose import jobs_nosetests, jobs_nosetests_single

__all__ = [
    "CompTests",
    "get_comptests_output_dir",
    "main_comptests",
]


def get_comptests_output_dir() -> AbsDirPath:
    """when run from the comptests executable, returns the output dir."""
    if CompTests.output_dir_for_current_test is None:
        msg = "Variable output_dir_for_current_test not set."
        logger.warning(msg)
        return abspath(get_comptests_global_output_dir())
    else:
        return abspath(CompTests.output_dir_for_current_test)


def get_comptests_global_output_dir() -> AbsDirPath:
    return abspath(CompTests.global_output_dir)


HOOK_NAME = "jobs_comptests"


class CompTests(QuickApp):
    """
    Runs the unit tests defined as @comptest.

    """

    global_output_dir = cast(AbsDirPath, os.path.join(os.getcwd(), "out/DEFAULT-comptests"))
    output_dir_for_current_test: Optional[AbsDirPath] = None

    cmd: str = "comptests"

    def define_options(self, params: DecentParams) -> None:
        params.add_string("exclude", default="", help="exclude these modules (comma separated)")

        params.add_flag("nonose", help="Disable nosetests")
        params.add_flag("nosesingle", help="Create nose single as tasks")
        params.add_flag("coverage", help="Enable coverage module")
        params.add_flag("nocomp", help="Disable comptests hooks")
        # params.add_string("prefix", help="Comptests prefix", default=None)

        params.add_flag("reports", help="Create reports jobs")
        params.add_flag("circle", help="Do CircleCI optimization")

        params.accept_extra()

    async def define_jobs_context(self, sti: SyncTaskInterface, context: QuickAppContext) -> None:
        logger = sti.logger
        CompTests.global_output_dir = self.get_options().output
        logger.info("Setting output dir to %s" % CompTests.global_output_dir)
        CompTests.output_dir_for_current_test = None

        GlobalConfig.global_load_dir("default")

        modules = list(self.get_modules())

        # noinspection PyUnresolvedReferences
        if self.options.circle:
            env = os.environ
            v_index, v_total = "CIRCLE_NODE_INDEX", "CIRCLE_NODE_TOTAL"
            if v_index in env and v_total in env:
                index = int(os.environ[v_index])
                total = int(os.environ[v_total])
                msg = f"Detected I am worker #{index} of {total} in CircleCI."
                self.info(msg)
                mine = []
                for i in range(len(modules)):
                    if i % total == index:
                        mine.append(modules[i])

                msg = f"I am only doing these modules: {mine}, instead of {modules}"
                self.info(msg)
                modules = mine

        if not modules:
            raise Exception("No modules found.")  # XXX: what's the nicer way?

        options = self.get_options()

        do_coverage = options.coverage
        # if do_coverage:
        #     import coverage
        #     coverage.process_startup()
        # if options.prefix:
        #     context = context.child(options.prefix)

        if not options.nonose:
            await self.instance_nosetests_jobs(sti, context.child("nt"), modules, do_coverage)

        if options.nosesingle:
            await self.instance_nosesingle_jobs(sti, context.child("ns"), modules)

        if not options.nocomp:
            await self.instance_comptests_jobs(sti, context.child("ct"), modules, create_reports=options.reports)

        sti.logger.info("Finished defining jobs.")

    def get_modules(self) -> set[str]:
        """ " Parses the command line argument and interprets them as modules."""
        extras = self.options.get_extra()
        if not extras:
            raise ValueError("No modules given")

        modules = list(self.interpret_modules_names(set(extras)))
        if not modules:
            msg = "No modules given"
            raise ZValueError(msg, extras=extras)
        # only get the main ones
        is_first = lambda module_name: not "." in module_name
        modules = list(filter(is_first, modules))
        # noinspection PyUnresolvedReferences
        excludes = self.options.exclude.split(",")
        to_exclude = lambda module_name: not module_name in excludes
        modules = list(filter(to_exclude, modules))
        return set(modules)

    def interpret_modules_names(self, names: set[str]) -> Iterator[str]:
        """yields a list of modules"""

        # First, extract tokens
        names2 = []
        for m in names:
            names2.extend(m.split(","))

        for m in names2:
            if os.path.exists(m):
                # if it's a path, look for 'setup.py' subdirs
                self.info(f"Interpreting {m!r} as path.")
                self.info("modules main: %s" % " ".join(find_modules_main(m)))
                modules = list(find_modules(m))
                if not modules:
                    self.warn("No modules found in %r" % m)

                for module in modules:
                    yield module
            else:
                self.info("Interpreting %r as module." % m)
                yield m

    async def instance_nosetests_jobs(
        self, sti: SyncTaskInterface, context: QuickAppContext, modules: list[str], do_coverage: bool
    ) -> None:
        # sti.logger.info("instancing nosetests jobs", modules=modules)
        await asyncio.sleep(0)
        for module in modules:
            c = context.child(module)
            jobs_nosetests(c, module, do_coverage=do_coverage)

    async def instance_nosesingle_jobs(self, sti: SyncTaskInterface, context: QuickAppContext, modules: list[str]) -> None:
        # sti.logger.info("instancing nosesingle jobs", modules=modules)
        await asyncio.sleep(0)
        for module in modules:
            c = context.child(module)
            c.comp_dynamic(jobs_nosetests_single, module, job_id="nosesingle")

    async def instance_comptests_jobs(
        self, sti: SyncTaskInterface, context: QuickAppContext, modules: list[str], create_reports: bool
    ):
        # sti.logger.info("instancing jobs", modules=modules)
        await asyncio.sleep(0)
        for module in modules:
            c = context.child(module)

            c.add_extra_report_keys(module=module)
            c.comp_config_dynamic(
                instance_comptests_jobs2_m,
                module_name=module,
                create_reports=create_reports,
                job_id="comptests",
            )


def instance_comptests_jobs2_m(context: QuickAppContext, module_name: str, create_reports: bool) -> None:
    from .registrar import jobs_registrar_simple

    is_first = "." not in module_name
    warn_errors = is_first

    # important: first import!
    try:
        module = import_name(module_name)
    except ValueError as e:
        msg = f"Could not import module {module_name!r}"

        if warn_errors:
            logger.error(msg)

        raise ZException(msg) from e

    # important: need to import the module above!
    jobs_registrar_simple(context.child("reg"), only_for_module=module_name)

    if not HOOK_NAME in module.__dict__:
        msg = f"Module {module_name} does not have function {HOOK_NAME}()."
        logger.warn(msg)
        # if warn_errors:
        #     logger.debug(msg)
    else:
        msg = f"Module {module_name}: found hook {HOOK_NAME}()."
        logger.warn(msg)
        ff = module.__dict__[HOOK_NAME]
        context.child(HOOK_NAME).comp_dynamic(comptests_jobs_wrap, ff, job_id=module_name)
        # context.comp_dynamic(comptests_jobs_wrap, ff, job_id=HOOK_NAME)


def comptests_jobs_wrap(context: QuickAppContext, ff: Callable[[QuickAppContext], Any]) -> None:
    reset_config()
    ff(context)


main_comptests = CompTests.get_sys_main()
