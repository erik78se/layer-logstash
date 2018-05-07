from subprocess import check_output


def logstash_version():
    version_raw = \
        check_output(
            '/usr/share/logstash/bin/logstash --version'.split())
    return version_raw.strip().decode().strip("logstash ")
