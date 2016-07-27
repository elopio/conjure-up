from conjure.app_config import app
from conjure import utils
from conjure import async
from subprocess import CalledProcessError
import json
import os


import q

@q.t
def wait_for_applications(script, msg_cb):
    """ Processes a 00_deploy-done.sh to verify if applications are available

    Arguments:
    script: script to run (00_deploy-done.sh)
    msg_cb: message callback
    """
    if os.path.isfile(script) \
       and os.access(script, os.X_OK):
        msg_cb("Waiting for applications to start")
        try:
            rerun = True
            count = 0
            while rerun:
                q.q('running ', script)
                sh = utils.run_script(script)
                if sh.returncode != 0:
                    app.log.error("error running {}:\n{}".format(script,
                                                                 sh.stderr))
                    raise Exception("Error running {}".format(script))

                try:
                    result = json.loads(sh.stdout.decode('utf8'))
                except json.decoder.JSONDecodeError as e:
                    app.log.exception(sh.stdout.decode())
                    raise Exception(sh)

                if result['returnCode'] > 0:
                    app.log.error(
                        "Failure in deploy done: {}".format(result['message']))
                    raise Exception(result['message'])
                if not result['isComplete']:
                    q.q('not complete, sleeping')
                    async.sleep(5)
                    q.q('awake!')
                    if count == 0:
                        msg_cb("{}, please wait".format(
                            result['message']))
                        count += 1
                    continue
                count = 0
                rerun = False
        except CalledProcessError as e:
            raise e
