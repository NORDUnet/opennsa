#!/usr/bin/env bash 

function check_db()
{
## Wait for DB container to be up

until nc -z -v -w30 $POSTGRES_HOST $POSTGRES_PORT
do
  echo "Waiting 5 second until the database is receiving connections..."
  # wait for a second before checking again
  sleep 5
done

}

function run_app() 
{
  cd $HOME/opennsa
  rm -f twistd.pid; $cmd 
}


if [ $# -gt 0 ]; then
    cmd=$@
else 
    cmd='twistd -ny opennsa.tac'
fi


check_db
run_app $cmd

