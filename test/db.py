# Common database stuff for test


import json

from opennsa import database


# Trial switches the work directory to <project>/_trial_temp, so we go up a notch
CONFIG_FILE="../.opennsa-test.json"



def setupDatabase(config_file=CONFIG_FILE):

    tc = json.load( open(config_file) )

    database.setupDatabase( tc['database'], tc['user'], tc['password'], host='127.0.0.1')


