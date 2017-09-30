import sys

from junit_xml import TestSuite, TestCase  # @UnresolvedImport

from compmake import logger
from compmake.exceptions import UserError
from compmake.jobs.storage import all_jobs, get_job_cache
from compmake.storage.filesystem import StorageFilesystem
from compmake.structures import Cache


def comptest_to_junit_main():
    args = sys.argv[1:]
    if not args:
        msg = 'Require the path to a Compmake DB.'
        raise UserError(msg)
    
    dirname = args[0]
    db = StorageFilesystem(dirname, compress=True)
    s = junit_xml(db)
    sys.stdout.write(s)
    

def junit_xml(compmake_db):
    jobs = list(all_jobs(compmake_db))
    logger.info('Loaded %d jobs' % len(jobs))
    if len(jobs) < 10:
        logger.error('too few jobs')
        sys.exit(128)
        
    test_cases = []
    for job_id in jobs:
        tc = junit_test_case_from_compmake(compmake_db, job_id)
        test_cases.append(tc)
        
    ts = TestSuite("comptests_test_suite", test_cases)
    
    return TestSuite.to_xml_string([ts])

def flatten_ascii(s):
    if s is None:
        return None
    s = unicode(s, encoding='utf8', errors='replace')
    s = s.encode('ascii', errors='ignore')
    return s
    
def junit_test_case_from_compmake(db, job_id):
    cache = get_job_cache(job_id, db=db)
    if cache.state == Cache.DONE:  # and cache.done_iterations > 1:
        #elapsed_sec = cache.walltime_used
        elapsed_sec = cache.cputime_used
    else:
        elapsed_sec = None
        
    stderr = flatten_ascii(remove_escapes(cache.captured_stderr))
    stdout = flatten_ascii(remove_escapes(cache.captured_stdout))
    
    tc = TestCase(name=job_id, classname=None, elapsed_sec=elapsed_sec,
                  stdout=stdout, stderr=stderr)
    
    if cache.state == Cache.FAILED:
        message = cache.exception
        output = cache.exception + "\n" + cache.backtrace
        tc.add_failure_info(flatten_ascii(message), flatten_ascii(output))
    
    return tc  

def remove_escapes(s):
    if s is None:
        return None
    import re
    escape = re.compile('\x1b\[..?m')
    return escape.sub("", s)


if __name__ == '__main__':
    comptest_to_junit_main()


