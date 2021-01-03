import os
import tempfile
from contextlib import contextmanager

from zuper_commons.fs import write_ustring_to_utf8_file


def test_example_package():
    from system_cmd import system_cmd_result

    # make sure it's installed
    # noinspection PyUnresolvedReferences
    import example_package  # @UnusedImport

    with create_tmp_dir() as cwd:
        print("Working in %r " % cwd)
        rc = os.path.join(cwd, ".compmake.rc")
        write_ustring_to_utf8_file("config echo 1", rc)
        cmd = [
            "comptests",
            # '--contracts',
            "--coverage",
            # '--nonose',
            "example_package",
        ]

        res = system_cmd_result(
            cwd, cmd, display_stdout=True, display_stderr=True, raise_on_error=False
        )
        assert res.ret != 0, res

        fs = [
            "out-comptests/report.html",
            "out-comptests/report/reportclass1single/"
            "reportclass1single-c1a-checkclass1dynamic-examplepackage-exampleclass1.html",
        ]
        #
        #         if False:
        #             # these are for reports
        #             fs += ['out-comptests/report/single/single-checkclass1dynamic'
        #                   '-examplepackage-exampleclass1.html',
        #                   'out-comptests/report/reportclass1single/reportclass1single'
        #                   '-checkclass1dynamic-c1a-examplepackage-exampleclass1.html',]

        errors = []
        for f in fs:
            fn = os.path.join(cwd, f)
            print("Testing %r" % f)
            if not os.path.exists(fn):
                errors.append(fn)

        if errors:
            msg = "Files not found:\n" + "\n".join(errors)
            raise Exception(msg)

        print("now calling comptests-to-junit")
        cmd = ["comptests-to-junit", "out-comptests/compmake"]
        system_cmd_result(
            cwd, cmd, display_stdout=True, display_stderr=True, raise_on_error=True
        )


@contextmanager
def create_tmp_dir():
    dirname = tempfile.mkdtemp()
    try:
        yield dirname
    except:
        raise


if __name__ == "__main__":
    test_example_package()